"""Book-level post-processing for v4 extraction pipeline.

Runs after all chapters are extracted. Three operations:
1. Iterative clustering (KGGen-style global dedup)
2. Entity summaries (LLM-generated per significant entity)
3. Community clustering (Leiden + LLM summaries)
"""

import asyncio
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
        groups.setdefault(et, []).append(
            {
                "name": r["name"],
                "description": r["description"] or "",
            }
        )

    for round_num in range(max_rounds):
        merges_this_round = 0

        for entity_type, entities in groups.items():
            if len(entities) < 5:
                continue

            # Hybrid BM25 + embedding candidate generation (G2)
            from app.services.deduplication import hybrid_candidate_generation

            candidates = await hybrid_candidate_generation(
                entities,
                embedder=embedder,
                top_k=5,
                threshold=similarity_threshold,
            )

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

    # Apply merges in Neo4j: rename, transfer relationships, delete alias nodes
    if alias_map:
        # Step 1: Rename alias nodes to canonical name
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

        # Step 2: Fix edge source/target properties on all typed relationships
        async with driver.session() as session:
            for old_name, new_name in alias_map.items():
                await session.run(
                    """
                    MATCH ()-[r]->()
                    WHERE r.book_id = $book_id
                      AND (toLower(r.source) = $old OR toLower(r.target) = $old)
                    SET r.source = CASE WHEN toLower(r.source) = $old THEN $new ELSE r.source END,
                        r.target = CASE WHEN toLower(r.target) = $old THEN $new ELSE r.target END
                    """,
                    book_id=book_id,
                    old=old_name.lower(),
                    new=new_name.lower(),
                )

        # Step 3: Merge duplicate nodes — transfer edges from alias to canonical, then delete alias
        merged_count = 0
        async with driver.session() as session:
            for _old_name, new_name in alias_map.items():
                # Find pairs of nodes that now share the same canonical_name
                # The canonical node is the one WITHOUT merged_from (or the first one)
                result = await session.run(
                    """
                    MATCH (n {canonical_name: $canonical, book_id: $book_id})
                    RETURN id(n) AS nid, n.merged_from AS merged_from
                    ORDER BY n.merged_from IS NOT NULL ASC, id(n) ASC
                    """,
                    canonical=new_name,
                    book_id=book_id,
                )
                node_records = [r async for r in result]

                if len(node_records) < 2:
                    continue

                # First node (no merged_from) is canonical; rest are aliases to merge
                canonical_id = node_records[0]["nid"]
                alias_ids = [r["nid"] for r in node_records[1:]]

                for alias_id in alias_ids:
                    # Transfer all outgoing relationships from alias to canonical
                    # Uses apoc.merge.relationship for dynamic typed edges
                    await session.run(
                        """
                        MATCH (alias)-[r]->(target)
                        WHERE id(alias) = $alias_id AND id(target) <> $canonical_id
                        WITH alias, r, target, type(r) AS rel_type, properties(r) AS props
                        MATCH (canonical) WHERE id(canonical) = $canonical_id
                        WITH alias, r, target, canonical, rel_type, props
                        WHERE NOT EXISTS {
                            MATCH (canonical)-[existing]->(target)
                            WHERE type(existing) = type(r)
                        }
                        CALL apoc.merge.relationship(canonical, rel_type, {}, props, target, {})
                        YIELD rel AS nr
                        RETURN nr
                        """,
                        alias_id=alias_id,
                        canonical_id=canonical_id,
                    )

                    # Transfer all incoming relationships from alias to canonical
                    await session.run(
                        """
                        MATCH (source)-[r]->(alias)
                        WHERE id(alias) = $alias_id AND id(source) <> $canonical_id
                        WITH alias, r, source, type(r) AS rel_type, properties(r) AS props
                        MATCH (canonical) WHERE id(canonical) = $canonical_id
                        WITH alias, r, source, canonical, rel_type, props
                        WHERE NOT EXISTS {
                            MATCH (source)-[existing]->(canonical)
                            WHERE type(existing) = type(r)
                        }
                        CALL apoc.merge.relationship(source, rel_type, {}, props, canonical, {})
                        YIELD rel AS nr
                        RETURN nr
                        """,
                        alias_id=alias_id,
                        canonical_id=canonical_id,
                    )

                    # Delete the alias node and all its remaining relationships
                    await session.run(
                        "MATCH (n) WHERE id(n) = $alias_id DETACH DELETE n",
                        alias_id=alias_id,
                    )
                    merged_count += 1

        logger.info(
            "iterative_cluster_nodes_merged",
            book_id=book_id,
            edges_updated=len(alias_map),
            nodes_merged=merged_count,
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

    1. Fetch entities with >= min_mentions MENTIONED_IN relationships
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
            MATCH (e)-[g:MENTIONED_IN]->(c:Chapter)
            WHERE e.book_id = $book_id
              AND e.canonical_name IS NOT NULL
            WITH e, count(g) AS mention_count,
                 collect(g.mention_text)[..10] AS texts,
                 min(c.number) AS first_ch,
                 max(c.number) AS last_ch
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

    from app.repositories.entity_repo import EntityRepository

    repo = EntityRepository(driver)
    sem = asyncio.Semaphore(10)  # max 10 concurrent LLM calls

    async def _summarize_one(record: dict) -> EntitySummary | None:
        async with sem:
            try:
                texts_joined = "\n".join(record["texts"])
                summary_result = await client.chat.completions.create(
                    model=model,
                    response_model=EntitySummary,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Résume cette entité en 2-5 phrases basées sur les extraits suivants.\n"
                                f"Entité: {record['name']} (type: {record['entity_type']})\n"
                                f"Extraits:\n{texts_joined}"
                            ),
                        }
                    ],
                    max_retries=2,
                )
                summary_result.entity_name = record["name"]
                summary_result.entity_type = record["entity_type"]
                summary_result.first_chapter = record["first_ch"] or 0
                summary_result.last_chapter = record["last_ch"] or 0
                summary_result.mention_count = record["mention_count"]

                # Persist to Neo4j
                await repo.upsert_entity_summary(
                    entity_name=record["name"],
                    summary=summary_result.summary,
                    key_facts=summary_result.key_facts,
                    mention_count=record["mention_count"],
                    batch_id=batch_id,
                    book_id=book_id,
                )
                return summary_result
            except Exception:
                logger.warning("entity_summary_failed", entity=record["name"], exc_info=True)
                return None

    results = await asyncio.gather(
        *(_summarize_one(record) for record in records),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, EntitySummary):
            summaries.append(result)

    logger.info("entity_summaries_done", book_id=book_id, count=len(summaries))
    return summaries


async def _generate_community_summary(
    client,
    model: str,
    members_text: str,
    level: int,
    is_rollup: bool = False,
) -> tuple[str, list[str]]:
    """Generate an LLM summary for a community.

    Args:
        client: Instructor async client.
        model: Model name.
        members_text: Comma-separated entity names (level 0) or child summaries (level 1+).
        level: Hierarchy level (0=finest).
        is_rollup: If True, members_text contains child community summaries.

    Returns:
        Tuple of (summary, key_themes).
    """
    from app.schemas.extraction_v4 import CommunitySummary

    if is_rollup:
        prompt = (
            "You are summarizing a high-level community in a fiction novel's knowledge graph.\n"
            "This community is composed of smaller sub-communities. "
            "Based on their summaries below, write a 1-3 sentence summary that captures "
            "the overarching theme and role of this group in the story.\n\n"
            f"Sub-community summaries:\n{members_text}"
        )
    else:
        prompt = (
            "You are summarizing a community of entities from a fiction novel's knowledge graph.\n"
            "Based on the entity names below, write a 1-3 sentence summary describing "
            "who/what this group is and their role in the story.\n\n"
            f"Entities: {members_text}"
        )

    result = await client.chat.completions.create(
        model=model,
        response_model=CommunitySummary,
        messages=[{"role": "user", "content": prompt}],
        max_retries=1,
    )
    return result.summary, result.key_themes


def _build_igraph(nodes: list, edges: list):
    """Build an igraph Graph from Neo4j node/edge records.

    Returns:
        Tuple of (graph, name_to_idx) or (None, None) if deps missing.
    """
    try:
        import igraph as ig
    except ImportError:
        return None, None

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

    return g, name_to_idx


def _run_leiden_at_resolution(g, resolution: float) -> list[list[int]]:
    """Run Leiden clustering at a given resolution.

    Returns:
        List of member-index lists per community.
    """
    try:
        import leidenalg

        partition = leidenalg.find_partition(
            g,
            leidenalg.RBConfigurationVertexPartition,
            resolution_parameter=resolution,
            n_iterations=10,
        )
        return list(partition)
    except ImportError:
        logger.warning("leidenalg_not_available_using_louvain_fallback")
        # Fallback: networkx Louvain (always available via igraph → networkx)
        try:
            import networkx as nx
            from networkx.algorithms.community import louvain_communities

            # Convert igraph to networkx
            nx_g = nx.Graph()
            for v in g.vs:
                nx_g.add_node(v.index, name=v["name"])
            for e in g.es:
                nx_g.add_edge(e.source, e.target)

            nx_communities = louvain_communities(nx_g, resolution=resolution)
            return [list(c) for c in nx_communities]
        except ImportError:
            logger.warning("networkx_community_fallback_also_missing")
            return []


def _map_children_to_parents(
    fine_partition: list[list[int]],
    coarse_partition: list[list[int]],
) -> dict[int, int]:
    """Map fine-grained community indices to coarse parent indices.

    Uses majority-vote: a fine community belongs to whichever coarse community
    contains the majority of its members.

    Returns:
        Dict of fine_comm_idx -> coarse_comm_idx.
    """
    # Build node -> coarse_comm lookup
    node_to_coarse: dict[int, int] = {}
    for coarse_idx, members in enumerate(coarse_partition):
        for node in members:
            node_to_coarse[node] = coarse_idx

    mapping: dict[int, int] = {}
    for fine_idx, fine_members in enumerate(fine_partition):
        # Count which coarse community has the most overlap
        votes: dict[int, int] = {}
        for node in fine_members:
            coarse_idx = node_to_coarse.get(node)
            if coarse_idx is not None:
                votes[coarse_idx] = votes.get(coarse_idx, 0) + 1
        if votes:
            mapping[fine_idx] = max(votes, key=lambda k: votes[k])

    return mapping


async def community_cluster(
    driver,
    book_id: str,
    batch_id: str = "",
    min_community_size: int = 3,
    resolutions: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Hierarchical community clustering via multi-level Leiden algorithm.

    Runs Leiden at multiple resolution levels (fine -> coarse), generates
    LLM summaries per community, and links communities across levels
    via PARENT_COMMUNITY relationships.

    Levels:
        0 (finest, resolution=1.0): detailed entity clusters
        1 (medium, resolution=0.5): mid-level thematic groups
        2 (coarsest, resolution=0.1): top-level narrative arcs

    Args:
        driver: Neo4j async driver.
        book_id: Book identifier.
        batch_id: Batch ID for rollback.
        min_community_size: Minimum members to keep a community.
        resolutions: Resolution parameters per level (fine -> coarse).
            Defaults to [1.0, 0.5, 0.1].

    Returns:
        List of community dicts with id, level, members, summary.
    """
    if resolutions is None:
        resolutions = [1.0, 0.5, 0.1]

    if not batch_id:
        batch_id = f"community:{book_id}:{int(time.time())}"

    all_communities: list[dict[str, Any]] = []

    # Export graph from Neo4j
    async with driver.session() as session:
        node_result = await session.run(
            """
            MATCH (e)
            WHERE e.book_id = $book_id
              AND e.canonical_name IS NOT NULL
            RETURN e.canonical_name AS name, labels(e)[0] AS label,
                   e.description AS description
            """,
            book_id=book_id,
        )
        nodes = [r async for r in node_result]

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
        return all_communities

    # Build igraph
    g, name_to_idx = _build_igraph(nodes, edges)
    if g is None:
        logger.warning("community_cluster_missing_deps", exc_info=True)
        return all_communities

    # Build name -> description lookup for level-0 summaries
    name_to_desc: dict[str, str] = {}
    for n in nodes:
        name_to_desc[n["name"]] = n.get("description") or ""

    # Get Instructor client for LLM summaries
    try:
        from app.llm.providers import get_instructor_for_task

        client, model = get_instructor_for_task("chat")
    except Exception:
        logger.warning("community_cluster_no_llm_client", exc_info=True)
        client, model = None, ""

    from app.repositories.entity_repo import EntityRepository

    repo = EntityRepository(driver)

    # Clear existing communities for this book before re-clustering
    await repo.delete_communities_for_book(book_id)

    # Run Leiden at each resolution level
    partitions: list[list[list[int]]] = []
    for resolution in resolutions:
        partition = _run_leiden_at_resolution(g, resolution)
        partitions.append(partition)

    # Track community IDs per level for parent linking
    # level_communities[level] = list of (comm_id, member_names, partition_idx)
    level_communities: list[list[tuple[str, list[str], int]]] = []

    sem = asyncio.Semaphore(10)  # limit concurrent LLM calls

    for level, (resolution, partition) in enumerate(zip(resolutions, partitions, strict=True)):
        level_comms: list[tuple[str, list[str], int]] = []

        for comm_idx, members in enumerate(partition):
            member_names = [g.vs[m]["name"] for m in members]
            if len(member_names) < min_community_size:
                continue

            community_id = f"{book_id}:comm:L{level}:{comm_idx}"

            # Generate LLM summary
            summary = f"Community of {len(member_names)} entities (level {level})"
            key_themes: list[str] = []

            if client is not None:
                try:
                    async with sem:
                        if level == 0:
                            # Level 0: summarize from entity names + descriptions
                            member_desc_parts = []
                            for name in member_names[:20]:
                                desc = name_to_desc.get(name, "")
                                if desc:
                                    member_desc_parts.append(f"{name}: {desc}")
                                else:
                                    member_desc_parts.append(name)
                            members_text = "\n".join(member_desc_parts)
                            summary, key_themes = await _generate_community_summary(
                                client,
                                model,
                                members_text,
                                level,
                                is_rollup=False,
                            )
                        else:
                            # Level 1+: rollup from child community summaries
                            child_summaries = _collect_child_summaries(
                                comm_idx,
                                level,
                                partitions,
                                level_communities,
                                all_communities,
                            )
                            if child_summaries:
                                summary, key_themes = await _generate_community_summary(
                                    client,
                                    model,
                                    child_summaries,
                                    level,
                                    is_rollup=True,
                                )
                            else:
                                # Fallback to entity names if no children found
                                members_text = ", ".join(member_names[:20])
                                summary, key_themes = await _generate_community_summary(
                                    client,
                                    model,
                                    members_text,
                                    level,
                                    is_rollup=False,
                                )
                except Exception:
                    logger.warning(
                        "community_summary_failed",
                        community_id=community_id,
                        level=level,
                        exc_info=True,
                    )

            await repo.upsert_community(
                community_id=community_id,
                book_id=book_id,
                summary=summary,
                member_names=member_names,
                batch_id=batch_id,
                level=level,
                resolution=resolution,
                key_themes=key_themes,
            )

            level_comms.append((community_id, member_names, comm_idx))
            all_communities.append(
                {
                    "id": community_id,
                    "level": level,
                    "resolution": resolution,
                    "members": member_names,
                    "summary": summary,
                    "key_themes": key_themes,
                }
            )

        level_communities.append(level_comms)

        # Link to parent communities at previous (coarser) level
        if level > 0:
            child_to_parent = _map_children_to_parents(
                partitions[level - 1],
                partitions[level],
            )
            # Build partition_idx -> community_id for current (parent) level
            parent_idx_to_id: dict[int, str] = {}
            for comm_id, _names, pidx in level_comms:
                parent_idx_to_id[pidx] = comm_id

            for child_comm_id, _child_names, child_pidx in level_communities[level - 1]:
                parent_pidx = child_to_parent.get(child_pidx)
                if parent_pidx is not None and parent_pidx in parent_idx_to_id:
                    await repo.link_parent_community(
                        child_id=child_comm_id,
                        parent_id=parent_idx_to_id[parent_pidx],
                        book_id=book_id,
                    )

    logger.info(
        "community_cluster_done",
        book_id=book_id,
        total_communities=len(all_communities),
        levels=len(resolutions),
        per_level=[
            len([c for c in all_communities if c["level"] == lvl])
            for lvl in range(len(resolutions))
        ],
    )
    return all_communities


def _collect_child_summaries(
    parent_comm_idx: int,
    parent_level: int,
    partitions: list[list[list[int]]],
    level_communities: list[list[tuple[str, list[str], int]]],
    all_communities: list[dict[str, Any]],
) -> str:
    """Collect summaries from child communities for rollup.

    Finds which child communities (from the previous level) have majority
    overlap with this parent community, and concatenates their summaries.
    """
    if parent_level < 1 or parent_level > len(partitions) - 1:
        return ""

    child_partition = partitions[parent_level - 1]
    # Find child communities whose members mostly belong to this parent
    child_to_parent = _map_children_to_parents(child_partition, partitions[parent_level])

    child_summaries = []
    for child_comm_id, _names, child_pidx in level_communities[parent_level - 1]:
        if child_to_parent.get(child_pidx) == parent_comm_idx:
            # Find the summary from all_communities
            for comm in all_communities:
                if comm["id"] == child_comm_id:
                    child_summaries.append(f"- {comm['summary']}")
                    break

    return "\n".join(child_summaries)
