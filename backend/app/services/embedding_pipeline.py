"""Embedding pipeline service.

Generates local sentence-transformers embeddings for Chunk nodes and writes
them back to Neo4j via batch UNWIND Cypher. Tracks cost via CostTracker.

Handles partial failures: failed batches are logged and skipped,
not propagated as fatal errors. This allows the pipeline to embed
as many chunks as possible even when some fail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.core.cost_tracker import count_tokens
from app.core.logging import get_logger
from app.llm.embeddings import LocalEmbedder

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from app.core.cost_tracker import CostTracker

logger = get_logger(__name__)


@dataclass
class EmbeddingResult:
    """Result of an embedding pipeline run."""

    book_id: str
    total_chunks: int
    embedded: int
    failed: int
    failed_keys: list[tuple[str, int]] = field(default_factory=list)
    total_tokens: int = 0
    cost_usd: float = 0.0


async def embed_book_chunks(
    driver: AsyncDriver,
    book_id: str,
    chunks: list[dict[str, Any]],
    cost_tracker: CostTracker | None = None,
) -> EmbeddingResult:
    """Embed all chunks for a book and write embeddings to Neo4j.

    Args:
        driver: Neo4j async driver.
        book_id: Book identifier (for cost tracking and logging).
        chunks: List of chunk descriptors from get_chunks_for_embedding().
            Each dict must have keys: chapter_id, position, text.
        cost_tracker: Optional CostTracker for cost recording.

    Returns:
        EmbeddingResult with stats and partial failure info.
    """
    result = EmbeddingResult(
        book_id=book_id,
        total_chunks=len(chunks),
        embedded=0,
        failed=0,
    )

    if not chunks:
        return result

    embedder = LocalEmbedder()
    batch_size = settings.embedding_batch_size

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]

        try:
            embeddings = await embedder.embed_texts(texts, input_type="document")
        except Exception:
            logger.exception(
                "embedding_batch_failed",
                book_id=book_id,
                batch_start=i,
                batch_size=len(batch),
            )
            result.failed += len(batch)
            result.failed_keys.extend((c["chapter_id"], int(c["position"])) for c in batch)
            continue

        # Count tokens for tracking (approximation)
        batch_tokens = sum(count_tokens(t) for t in texts)
        result.total_tokens += batch_tokens

        # Write embeddings to Neo4j via UNWIND
        await _write_embeddings(driver, batch, embeddings)
        result.embedded += len(batch)

        # Record cost ($0 for local embeddings, but track for stats)
        if cost_tracker:
            await cost_tracker.record(
                model=settings.embedding_model,
                provider="local",
                input_tokens=batch_tokens,
                output_tokens=0,
                operation="embedding",
                book_id=book_id,
            )

    logger.info(
        "embedding_pipeline_completed",
        book_id=book_id,
        total=result.total_chunks,
        embedded=result.embedded,
        failed=result.failed,
        total_tokens=result.total_tokens,
    )

    return result


@dataclass
class RelationshipEmbeddingResult:
    """Result of a relationship embedding pipeline run."""

    book_id: str
    total_rels: int
    embedded: int
    failed: int
    total_tokens: int = 0


async def embed_book_relationships(
    driver: AsyncDriver,
    book_id: str,
    cost_tracker: CostTracker | None = None,
) -> RelationshipEmbeddingResult:
    """Embed all RELATES_TO relationships for a book and write embeddings to Neo4j.

    Queries for relationships without embeddings, builds text representations
    from source/target names + type + context, embeds them locally, and writes
    the vectors back to the relationship properties.

    Args:
        driver: Neo4j async driver.
        book_id: Book identifier.
        cost_tracker: Optional CostTracker for cost recording.

    Returns:
        RelationshipEmbeddingResult with stats.
    """
    # Fetch relationships without embeddings
    async with driver.session() as session:
        query_result = await session.run(
            """
            MATCH (a)-[r:RELATES_TO {book_id: $book_id}]->(b)
            WHERE r.embedding IS NULL
            RETURN id(r) AS rel_id, a.canonical_name AS source, b.canonical_name AS target,
                   r.type AS rel_type, r.context AS context, r.subtype AS subtype
            """,
            {"book_id": book_id},
        )
        rels = [dict(record) for record in await query_result.data()]

    result = RelationshipEmbeddingResult(
        book_id=book_id,
        total_rels=len(rels),
        embedded=0,
        failed=0,
    )

    if not rels:
        return result

    # Build text representations
    for rel in rels:
        source = rel.get("source") or "Unknown"
        target = rel.get("target") or "Unknown"
        rel_type = rel.get("rel_type") or "RELATES_TO"
        context = rel.get("context") or ""
        text = f"{source} {rel_type} {target}"
        if context:
            text += f": {context}"
        rel["text"] = text

    embedder = LocalEmbedder()
    batch_size = settings.embedding_batch_size

    for i in range(0, len(rels), batch_size):
        batch = rels[i : i + batch_size]
        texts = [r["text"] for r in batch]

        try:
            embeddings = await embedder.embed_texts(texts, input_type="document")
        except Exception:
            logger.exception(
                "relationship_embedding_batch_failed",
                book_id=book_id,
                batch_start=i,
                batch_size=len(batch),
            )
            result.failed += len(batch)
            continue

        batch_tokens = sum(count_tokens(t) for t in texts)
        result.total_tokens += batch_tokens

        # Write embeddings back to relationships
        await _write_relationship_embeddings(driver, batch, embeddings)
        result.embedded += len(batch)

        if cost_tracker:
            await cost_tracker.record(
                model=settings.embedding_model,
                provider="local",
                input_tokens=batch_tokens,
                output_tokens=0,
                operation="relationship_embedding",
                book_id=book_id,
            )

    logger.info(
        "relationship_embedding_completed",
        book_id=book_id,
        total=result.total_rels,
        embedded=result.embedded,
        failed=result.failed,
        total_tokens=result.total_tokens,
    )

    return result


@dataclass
class EntityEmbeddingResult:
    """Result of an entity embedding pipeline run."""

    book_id: str
    total_entities: int
    embedded: int
    failed: int
    total_tokens: int = 0


async def embed_book_entities(
    driver: AsyncDriver,
    book_id: str,
    cost_tracker: CostTracker | None = None,
) -> EntityEmbeddingResult:
    """Embed entity descriptions and store vectors on entity nodes.

    Queries for entity nodes with descriptions but no embeddings,
    builds text from label + name + description, embeds locally,
    and writes the vectors back to the node properties.

    Args:
        driver: Neo4j async driver.
        book_id: Book identifier.
        cost_tracker: Optional CostTracker for cost recording.

    Returns:
        EntityEmbeddingResult with stats.
    """
    # Fetch entities without embeddings (include those with no description)
    async with driver.session() as session:
        query_result = await session.run(
            """
            MATCH (n {book_id: $book_id})
            WHERE n.embedding IS NULL
              AND n.canonical_name IS NOT NULL
              AND NOT n:Book AND NOT n:Chapter AND NOT n:Chunk AND NOT n:Paragraph
            RETURN id(n) AS node_id, n.canonical_name AS name,
                   n.description AS description, labels(n)[0] AS label
            """,
            {"book_id": book_id},
        )
        entities = [dict(record) for record in await query_result.data()]

    result = EntityEmbeddingResult(
        book_id=book_id,
        total_entities=len(entities),
        embedded=0,
        failed=0,
    )

    if not entities:
        return result

    # Build text representations (handle missing description gracefully)
    for ent in entities:
        label = ent.get("label") or "Entity"
        name = ent.get("name") or "Unknown"
        description = ent.get("description") or ""
        if description:
            ent["text"] = f"{label}: {name}. {description}"
        else:
            ent["text"] = f"{label}: {name}"

    embedder = LocalEmbedder()
    batch_size = settings.embedding_batch_size

    for i in range(0, len(entities), batch_size):
        batch = entities[i : i + batch_size]
        texts = [e["text"] for e in batch]

        try:
            embeddings = await embedder.embed_texts(texts, input_type="document")
        except Exception:
            logger.exception(
                "entity_embedding_batch_failed",
                book_id=book_id,
                batch_start=i,
                batch_size=len(batch),
            )
            result.failed += len(batch)
            continue

        batch_tokens = sum(count_tokens(t) for t in texts)
        result.total_tokens += batch_tokens

        # Write embeddings back to entity nodes
        await _write_entity_embeddings(driver, batch, embeddings)
        result.embedded += len(batch)

        if cost_tracker:
            await cost_tracker.record(
                model=settings.embedding_model,
                provider="local",
                input_tokens=batch_tokens,
                output_tokens=0,
                operation="entity_embedding",
                book_id=book_id,
            )

    logger.info(
        "entity_embedding_completed",
        book_id=book_id,
        total=result.total_entities,
        embedded=result.embedded,
        failed=result.failed,
        total_tokens=result.total_tokens,
    )

    return result


async def _write_entity_embeddings(
    driver: AsyncDriver,
    batch: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    """Write a batch of embeddings to entity nodes via UNWIND."""
    payload = [
        {
            "node_id": batch[j]["node_id"],
            "embedding": embeddings[j],
        }
        for j in range(len(batch))
    ]

    async with driver.session() as session:
        await session.run(
            """
            UNWIND $items AS item
            MATCH (n) WHERE id(n) = item.node_id
            SET n.embedding = item.embedding
            """,
            {"items": payload},
        )


async def _write_relationship_embeddings(
    driver: AsyncDriver,
    batch: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    """Write a batch of embeddings to RELATES_TO relationships via UNWIND."""
    payload = [
        {
            "rel_id": batch[j]["rel_id"],
            "embedding": embeddings[j],
        }
        for j in range(len(batch))
    ]

    async with driver.session() as session:
        await session.run(
            """
            UNWIND $items AS item
            MATCH ()-[r:RELATES_TO]->() WHERE id(r) = item.rel_id
            SET r.embedding = item.embedding
            """,
            {"items": payload},
        )


async def _write_embeddings(
    driver: AsyncDriver,
    batch: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    """Write a batch of embeddings to Chunk nodes via UNWIND.

    Matches on (chapter_id, position) — the compound unique key
    for Chunk nodes in this schema.
    """
    payload = [
        {
            "chapter_id": batch[j]["chapter_id"],
            "position": int(batch[j]["position"]),
            "embedding": embeddings[j],
        }
        for j in range(len(batch))
    ]

    async with driver.session() as session:
        await session.run(
            """
            UNWIND $items AS item
            MATCH (ck:Chunk {chapter_id: item.chapter_id, position: item.position})
            SET ck.embedding = item.embedding
            """,
            {"items": payload},
        )
