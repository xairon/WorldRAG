"""Book-level post-processing for v4 extraction pipeline.

Runs after all chapters are extracted. Three operations:
1. Iterative clustering (KGGen-style global dedup)
2. Entity summaries (LLM-generated per significant entity)
3. Community clustering (Leiden + LLM summaries)
"""
import time
from typing import Any

import structlog

from app.schemas.extraction_v4 import EntitySummary

logger = structlog.get_logger()


async def iterative_cluster(
    driver,
    book_id: str,
    embedder=None,
    max_rounds: int = 3,
    similarity_threshold: float = 0.85,
) -> dict[str, str]:
    """KGGen-style iterative clustering on all entities of a book.

    Algorithm:
    1. Fetch all entity names + descriptions from Neo4j
    2. Group by entity_type
    3. For each type with >5 entities:
       a. Embed names + descriptions (bge-m3)
       b. Compute cosine similarity matrix
       c. Pairs with similarity > threshold → candidates
       d. LLM-as-Judge on candidates (batch Instructor)
       e. Apply merges
    4. Iterate (max_rounds) until convergence

    Returns: alias_map {alias -> canonical}
    """
    alias_map: dict[str, str] = {}

    async with driver.session() as session:
        # Fetch all entities for this book
        result = await session.run(
            """
            MATCH (e)
            WHERE e.book_id = $book_id
              AND e.canonical_name IS NOT NULL
            RETURN e.canonical_name AS name,
                   labels(e)[0] AS entity_type,
                   e.description AS description
            """,
            book_id=book_id,
        )
        records = [r async for r in result]

    if not records:
        return alias_map

    # Group by entity_type
    groups: dict[str, list[dict]] = {}
    for r in records:
        et = r["entity_type"]
        groups.setdefault(et, []).append({
            "name": r["name"],
            "description": r["description"] or "",
        })

    for round_num in range(max_rounds):
        merges_this_round = 0

        for entity_type, entities in groups.items():
            if len(entities) < 5:
                continue

            # Embed names + descriptions
            if embedder is None:
                continue

            texts = [f"{e['name']}: {e['description']}" for e in entities]
            embeddings = await embedder.embed_texts(texts)

            # Compute pairwise cosine similarity
            import numpy as np

            emb_matrix = np.array(embeddings)
            norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized = emb_matrix / norms
            sim_matrix = normalized @ normalized.T

            # Find candidate pairs above threshold
            candidates = []
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    if sim_matrix[i][j] > similarity_threshold:
                        candidates.append((
                            entities[i]["name"],
                            entities[j]["name"],
                            float(sim_matrix[i][j]),
                        ))

            if not candidates:
                continue

            # LLM-as-Judge for ambiguous pairs
            from app.llm.providers import get_instructor_for_task
            from app.services.deduplication import deduplicate_entities

            try:
                client, model = get_instructor_for_task("dedup")
                # Use existing dedup logic for the candidate names
                entity_names = list({c[0] for c in candidates} | {c[1] for c in candidates})
                simple_entities = [{"name": n} for n in entity_names]
                _, new_alias_map = await deduplicate_entities(
                    simple_entities,
                    entity_type=entity_type,
                    client=client,
                    model=model,
                )
                alias_map.update(new_alias_map)
                merges_this_round += len(new_alias_map)
            except Exception:
                logger.warning(
                    "iterative_cluster_dedup_failed",
                    entity_type=entity_type,
                    exc_info=True,
                )

        logger.info("iterative_cluster_round", round=round_num + 1, merges=merges_this_round)
        if merges_this_round == 0:
            break

    # Apply merges in Neo4j
    if alias_map:
        async with driver.session() as session:
            for alias, canonical in alias_map.items():
                await session.run(
                    """
                    MATCH (e {canonical_name: $alias, book_id: $book_id})
                    SET e.canonical_name = $canonical,
                        e.merged_from = $alias
                    """,
                    alias=alias,
                    canonical=canonical,
                    book_id=book_id,
                )

    logger.info("iterative_cluster_done", book_id=book_id, total_merges=len(alias_map))
    return alias_map


async def generate_entity_summaries(
    driver,
    book_id: str,
    min_mentions: int = 3,
    batch_id: str = "",
) -> list[EntitySummary]:
    """Generate LLM summaries for significant entities.

    1. Fetch entities with >= min_mentions GROUNDED_IN relationships
    2. For each: collect extraction_texts, generate summary via Instructor
    3. Store summary on Neo4j node
    """
    if not batch_id:
        batch_id = f"summary:{book_id}:{int(time.time())}"

    summaries: list[EntitySummary] = []

    # Fetch significant entities
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (e)-[g:GROUNDED_IN]->(c:Chunk)
            WHERE e.book_id = $book_id
              AND e.canonical_name IS NOT NULL
            WITH e, count(g) AS mention_count,
                 collect(g.extraction_text)[..10] AS texts,
                 min(c.chapter_number) AS first_ch,
                 max(c.chapter_number) AS last_ch
            WHERE mention_count >= $min_mentions
            RETURN e.canonical_name AS name,
                   labels(e)[0] AS entity_type,
                   mention_count,
                   texts,
                   first_ch, last_ch
            ORDER BY mention_count DESC
            LIMIT 100
            """,
            book_id=book_id,
            min_mentions=min_mentions,
        )
        records = [r async for r in result]

    if not records:
        return summaries

    # Generate summaries via Instructor
    from app.llm.providers import get_instructor_for_task

    try:
        client, model = get_instructor_for_task("classification")
    except Exception:
        logger.warning("entity_summary_no_client", exc_info=True)
        return summaries

    for record in records:
        try:
            texts_joined = "\n".join(record["texts"])
            summary_result = await client.chat.completions.create(
                model=model,
                response_model=EntitySummary,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Résume cette entité en 2-5 phrases basées sur les extraits suivants.\n"
                        f"Entité: {record['name']} (type: {record['entity_type']})\n"
                        f"Extraits:\n{texts_joined}"
                    ),
                }],
                max_retries=2,
            )
            summary_result.entity_name = record["name"]
            summary_result.entity_type = record["entity_type"]
            summary_result.first_chapter = record["first_ch"] or 0
            summary_result.last_chapter = record["last_ch"] or 0
            summary_result.mention_count = record["mention_count"]
            summaries.append(summary_result)

            # Persist to Neo4j
            from app.repositories.entity_repo import EntityRepository

            repo = EntityRepository(driver)
            await repo.upsert_entity_summary(
                entity_name=record["name"],
                summary=summary_result.summary,
                key_facts=summary_result.key_facts,
                mention_count=record["mention_count"],
                batch_id=batch_id,
                book_id=book_id,
            )
        except Exception:
            logger.warning("entity_summary_failed", entity=record["name"], exc_info=True)

    logger.info("entity_summaries_done", book_id=book_id, count=len(summaries))
    return summaries


async def community_cluster(
    driver,
    book_id: str,
    batch_id: str = "",
    min_community_size: int = 3,
    resolution: float = 1.0,
) -> list[dict[str, Any]]:
    """Community clustering via Leiden algorithm.

    1. Export Neo4j graph to igraph
    2. Run Leiden clustering
    3. Generate LLM summaries for each community
    4. Store Community nodes in Neo4j
    """
    if not batch_id:
        batch_id = f"community:{book_id}:{int(time.time())}"

    communities: list[dict[str, Any]] = []

    # Export graph
    async with driver.session() as session:
        # Get nodes
        node_result = await session.run(
            """
            MATCH (e)
            WHERE e.book_id = $book_id
              AND e.canonical_name IS NOT NULL
            RETURN e.canonical_name AS name, labels(e)[0] AS label
            """,
            book_id=book_id,
        )
        nodes = [r async for r in node_result]

        # Get edges
        edge_result = await session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE a.book_id = $book_id AND b.book_id = $book_id
              AND a.canonical_name IS NOT NULL AND b.canonical_name IS NOT NULL
            RETURN a.canonical_name AS source, b.canonical_name AS target, type(r) AS rel_type
            """,
            book_id=book_id,
        )
        edges = [r async for r in edge_result]

    if len(nodes) < min_community_size:
        return communities

    # Build igraph
    try:
        import igraph as ig
        import leidenalg
    except ImportError:
        logger.warning("community_cluster_missing_deps", exc_info=True)
        return communities

    name_to_idx = {n["name"]: i for i, n in enumerate(nodes)}
    g = ig.Graph(n=len(nodes), directed=False)
    g.vs["name"] = [n["name"] for n in nodes]
    g.vs["label"] = [n["label"] for n in nodes]

    edge_list = []
    for e in edges:
        src_idx = name_to_idx.get(e["source"])
        tgt_idx = name_to_idx.get(e["target"])
        if src_idx is not None and tgt_idx is not None and src_idx != tgt_idx:
            edge_list.append((src_idx, tgt_idx))

    if edge_list:
        g.add_edges(edge_list)

    # Leiden clustering
    partition = leidenalg.find_partition(
        g,
        leidenalg.ModularityVertexPartition,
        n_iterations=10,
    )

    # Process communities
    from app.repositories.entity_repo import EntityRepository

    repo = EntityRepository(driver)

    for comm_idx, members in enumerate(partition):
        member_names = [g.vs[m]["name"] for m in members]
        if len(member_names) < min_community_size:
            continue

        community_id = f"{book_id}:comm:{comm_idx}"

        # Generate summary via LLM
        summary = f"Community of {len(member_names)} entities"
        try:
            from app.llm.providers import get_instructor_for_task
            from app.schemas.extraction_v4 import EntitySummary as CommEntitySummary

            class CommSummary(CommEntitySummary):
                """One-field wrapper used only for community summary generation."""

            client, model = get_instructor_for_task("classification")
            member_desc = ", ".join(member_names[:20])
            result = await client.chat.completions.create(
                model=model,
                response_model=CommSummary,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Résume en 1-2 phrases ce groupe d'entités d'un roman: {member_desc}"
                    ),
                }],
                max_retries=1,
            )
            if result.summary:
                summary = result.summary
        except Exception:
            pass  # Use default summary

        await repo.upsert_community(
            community_id=community_id,
            book_id=book_id,
            summary=summary,
            member_names=member_names,
            batch_id=batch_id,
        )

        communities.append({
            "id": community_id,
            "members": member_names,
            "summary": summary,
        })

    logger.info("community_cluster_done", book_id=book_id, communities=len(communities))
    return communities
