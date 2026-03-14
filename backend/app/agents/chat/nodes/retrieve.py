"""Hybrid retrieval node: dense + BM25 + graph traversal with RRF fusion.

Runs three parallel retrieval arms against Neo4j, then fuses results
using Reciprocal Rank Fusion (RRF) with configurable weights.
"""

import asyncio
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

RRF_K = 60  # Standard RRF constant


def rrf_fuse(
    result_lists: list[list[dict[str, Any]]],
    weights: list[float],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Fuse multiple ranked result lists using Reciprocal Rank Fusion.

    Args:
        result_lists: List of ranked result lists. Each result must have "node_id".
        weights: Weight per result list. Higher = more influence on final ranking.
        top_k: Maximum number of results to return.

    Returns:
        Fused results sorted by RRF score descending, with "rrf_score" added.
    """
    scores: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}

    for result_list, weight in zip(result_lists, weights, strict=True):
        for rank, result in enumerate(result_list):
            nid = result["node_id"]
            scores[nid] = scores.get(nid, 0.0) + weight / (RRF_K + rank + 1)
            if nid not in metadata:
                metadata[nid] = result

    sorted_ids = sorted(scores, key=scores.__getitem__, reverse=True)[:top_k]

    return [{**metadata[nid], "rrf_score": scores[nid]} for nid in sorted_ids]


def _escape_lucene(query: str) -> str:
    """Escape Lucene special characters for Neo4j fulltext queries."""
    special = r'+-&|!(){}[]^"~*?:\/'
    return "".join(f"\\{c}" if c in special else c for c in query)


async def _dense_search(
    repo,
    query_embedding: list[float],
    book_id: str,
    top_k: int,
    max_chapter: int | None,
) -> list[dict[str, Any]]:
    """Vector similarity search on chunk embeddings."""
    return await repo.execute_read(
        """
        CALL db.index.vector.queryNodes('chunk_embedding', $top_k, $embedding)
        YIELD node AS chunk, score
        MATCH (chap:Chapter)-[:HAS_CHUNK]->(chunk)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN elementId(chunk) AS node_id,
               chunk.text AS text,
               chap.number AS chapter_number,
               chap.title AS chapter_title,
               chunk.position AS position,
               score
        ORDER BY score DESC
        """,
        {
            "embedding": query_embedding,
            "book_id": book_id,
            "top_k": top_k,
            "max_chapter": max_chapter,
        },
    )


async def _sparse_search(
    repo,
    query_text: str,
    book_id: str,
    top_k: int,
    max_chapter: int | None,
) -> list[dict[str, Any]]:
    """BM25 fulltext search on chunk text."""
    escaped = _escape_lucene(query_text)
    if not escaped.strip():
        return []
    return await repo.execute_read(
        """
        CALL db.index.fulltext.queryNodes('chunk_fulltext', $query)
        YIELD node AS chunk, score
        MATCH (chap:Chapter)-[:HAS_CHUNK]->(chunk)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN elementId(chunk) AS node_id,
               chunk.text AS text,
               chap.number AS chapter_number,
               chap.title AS chapter_title,
               chunk.position AS position,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """,
        {
            "query": escaped,
            "book_id": book_id,
            "top_k": top_k,
            "max_chapter": max_chapter,
        },
    )


async def _graph_search(
    repo,
    query_text: str,
    book_id: str,
    top_k: int,
    max_chapter: int | None,
) -> list[dict[str, Any]]:
    """Entity-centric graph traversal: entity_fulltext -> GROUNDED_IN -> Chunk."""
    escaped = _escape_lucene(query_text)
    if not escaped.strip():
        return []
    return await repo.execute_read(
        """
        CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
        YIELD node AS entity, score AS entity_score
        WHERE entity_score > 0.5
        WITH entity
        ORDER BY entity_score DESC
        LIMIT 5
        MATCH (entity)-[:GROUNDED_IN|MENTIONED_IN]->(chunk:Chunk)<-[:HAS_CHUNK]-(chap:Chapter)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN DISTINCT elementId(chunk) AS node_id,
               chunk.text AS text,
               chap.number AS chapter_number,
               chap.title AS chapter_title,
               chunk.position AS position,
               1.0 AS score
        LIMIT $top_k
        """,
        {
            "query": escaped,
            "book_id": book_id,
            "top_k": top_k,
            "max_chapter": max_chapter,
        },
    )


async def hybrid_retrieve(
    repo,
    query_text: str,
    query_embedding: list[float],
    book_id: str,
    *,
    extra_dense_embeddings: list[list[float]] | None = None,
    extra_bm25_queries: list[str] | None = None,
    top_k_per_arm: int = 30,
    final_top_k: int = 15,
    max_chapter: int | None = None,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    graph_weight: float = 0.5,
) -> list[dict[str, Any]]:
    """Run multi-arm hybrid retrieval with RRF fusion.

    Dense arms: primary embedding + extra_dense_embeddings (multi-query + HyDE).
    Sparse arms: primary BM25 + extra_bm25_queries (multi-query variants).
    Graph arm: entity_fulltext → GROUNDED_IN → Chunk traversal.

    All arms are run in parallel, then fused via RRF.
    """
    # Dense tasks: primary embedding + extra embeddings (query variants + HyDE)
    dense_tasks = [_dense_search(repo, query_embedding, book_id, top_k_per_arm, max_chapter)]
    for emb in extra_dense_embeddings or []:
        dense_tasks.append(_dense_search(repo, emb, book_id, top_k_per_arm, max_chapter))

    # Sparse tasks: primary BM25 + multi-query variants
    sparse_tasks = [_sparse_search(repo, query_text, book_id, top_k_per_arm, max_chapter)]
    for variant in extra_bm25_queries or []:
        sparse_tasks.append(_sparse_search(repo, variant, book_id, top_k_per_arm, max_chapter))

    all_tasks = [
        *dense_tasks,
        *sparse_tasks,
        _graph_search(repo, query_text, book_id, top_k_per_arm, max_chapter),
    ]
    results = await asyncio.gather(*all_tasks)

    dense_result_lists = results[: len(dense_tasks)]
    sparse_result_lists = results[len(dense_tasks) : len(dense_tasks) + len(sparse_tasks)]
    graph_results = results[-1]

    # Fuse all dense results into one via RRF
    if len(dense_result_lists) > 1:
        dense_results = rrf_fuse(
            dense_result_lists,
            weights=[1.0] * len(dense_result_lists),
            top_k=top_k_per_arm,
        )
    else:
        dense_results = dense_result_lists[0]

    # Fuse all sparse results into one via RRF
    if len(sparse_result_lists) > 1:
        sparse_results = rrf_fuse(
            sparse_result_lists,
            weights=[1.0] * len(sparse_result_lists),
            top_k=top_k_per_arm,
        )
    else:
        sparse_results = sparse_result_lists[0]

    logger.info(
        "hybrid_retrieval_completed",
        dense_arms=len(dense_tasks),
        sparse_arms=len(sparse_tasks),
        dense_count=len(dense_results),
        sparse_count=len(sparse_results),
        graph_count=len(graph_results),
        book_id=book_id,
    )

    fused = rrf_fuse(
        [dense_results, sparse_results, graph_results],
        weights=[dense_weight, sparse_weight, graph_weight],
        top_k=final_top_k,
    )

    return fused
