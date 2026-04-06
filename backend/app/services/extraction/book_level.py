"""Book-level post-processing for v4 extraction pipeline.

Runs after all chapters are extracted. Three operations:
1. Iterative clustering (KGGen-style global dedup)
2. Entity summaries (LLM-generated per significant entity)
3. Community clustering (Leiden + LLM summaries)
"""

import asyncio
import json
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
                    # Collect outgoing rels from alias, recreate on canonical, delete alias
                    # No APOC — read rel types, then use f-string Cypher per type
                    out_rels = await session.run(
                        """
                        MATCH (alias)-[r]->(target)
                        WHERE id(alias) = $alias_id AND id(target) <> $canonical_id
                        RETURN type(r) AS rel_type, properties(r) AS props, id(target) AS tid
                        """,
                        alias_id=alias_id,
                        canonical_id=canonical_id,
                    )
                    for rec in await out_rels.data():
                        rt = (
                            "".join(c for c in rec["rel_type"] if c.isalnum() or c == "_")
                            or "RELATED"
                        )
                        await session.run(
                            f"""
                            MATCH (canon) WHERE id(canon) = $cid
                            MATCH (target) WHERE id(target) = $tid
                            MERGE (canon)-[nr:{rt}]->(target)
                            SET nr += $props
                            """,
                            cid=canonical_id,
                            tid=rec["tid"],
                            props=rec["props"],
                        )

                    # Transfer incoming rels
                    in_rels = await session.run(
                        """
                        MATCH (source)-[r]->(alias)
                        WHERE id(alias) = $alias_id AND id(source) <> $canonical_id
                        RETURN type(r) AS rel_type, properties(r) AS props, id(source) AS sid
                        """,
                        alias_id=alias_id,
                        canonical_id=canonical_id,
                    )
                    for rec in await in_rels.data():
                        rt = (
                            "".join(c for c in rec["rel_type"] if c.isalnum() or c == "_")
                            or "RELATED"
                        )
                        await session.run(
                            f"""
                            MATCH (source) WHERE id(source) = $sid
                            MATCH (canon) WHERE id(canon) = $cid
                            MERGE (source)-[nr:{rt}]->(canon)
                            SET nr += $props
                            """,
                            sid=rec["sid"],
                            cid=canonical_id,
                            props=rec["props"],
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


async def generate_state_snapshots(
    entity_repo,
    book_id: str,
    snapshot_interval: int = 10,
) -> int:
    """Generate state snapshots for main characters every N chapters.

    A snapshot aggregates: current level, active skills, current class,
    active titles, and active relationships at a specific chapter.
    """
    # Get total chapters
    chapters = await entity_repo.execute_read(
        "MATCH (c:Chapter {book_id: $book_id}) RETURN max(c.number) AS max_ch",
        {"book_id": book_id},
    )
    max_chapter = chapters[0]["max_ch"] if chapters else 0
    if not max_chapter:
        return 0

    # Get main characters (top 5 by relationship count)
    main_chars = await entity_repo.execute_read(
        """
        MATCH (c:Character {book_id: $book_id})-[r]-()
        WITH c, count(r) AS rel_count
        ORDER BY rel_count DESC LIMIT 5
        RETURN c.canonical_name AS name
        """,
        {"book_id": book_id},
    )

    if not main_chars:
        return 0

    snapshot_count = 0
    for chapter_num in range(snapshot_interval, max_chapter + 1, snapshot_interval):
        for char in main_chars:
            char_name = char["name"]
            # Build snapshot at this chapter
            snapshot = await entity_repo.execute_read(
                """
                MATCH (c:Character {canonical_name: $name, book_id: $book_id})
                OPTIONAL MATCH (c)-[lvl:AT_LEVEL]->(b)
                WHERE lvl.valid_from_chapter <= $chapter
                  AND (lvl.valid_to_chapter IS NULL OR lvl.valid_to_chapter >= $chapter)
                OPTIONAL MATCH (c)-[sk:HAS_SKILL]->(skill:Skill)
                WHERE sk.valid_from_chapter <= $chapter
                  AND (sk.valid_to_chapter IS NULL OR sk.valid_to_chapter >= $chapter)
                OPTIONAL MATCH (c)-[cl:HAS_CLASS]->(cls:Class)
                WHERE cl.valid_from_chapter <= $chapter
                  AND (cl.valid_to_chapter IS NULL OR cl.valid_to_chapter >= $chapter)
                OPTIONAL MATCH (c)-[tl:HAS_TITLE]->(title:Title)
                RETURN c.canonical_name AS name,
                       collect(DISTINCT {level: lvl.level, realm: lvl.realm}) AS levels,
                       collect(DISTINCT skill.name) AS skills,
                       collect(DISTINCT cls.name) AS classes,
                       collect(DISTINCT title.name) AS titles
                """,
                {"name": char_name, "book_id": book_id, "chapter": chapter_num},
            )

            if snapshot:
                snap = snapshot[0]
                await entity_repo.execute_write(
                    """
                    MATCH (c:Character {canonical_name: $name, book_id: $book_id})
                    MERGE (s:StateSnapshot {character: $name, chapter: $chapter, book_id: $book_id})
                    ON CREATE SET
                        s.levels = $levels,
                        s.skills = $skills,
                        s.classes = $classes,
                        s.titles = $titles,
                        s.created_at = timestamp()
                    MERGE (c)-[:HAS_SNAPSHOT]->(s)
                    """,
                    {
                        "name": char_name,
                        "book_id": book_id,
                        "chapter": chapter_num,
                        "levels": json.dumps(snap.get("levels", [])),
                        "skills": snap.get("skills", []),
                        "classes": snap.get("classes", []),
                        "titles": snap.get("titles", []),
                    },
                )
                snapshot_count += 1

    logger.info(
        "state_snapshots_done",
        book_id=book_id,
        snapshot_count=snapshot_count,
        interval=snapshot_interval,
    )
    return snapshot_count


async def run_consistency_checks(
    driver,
    book_id: str,
) -> list[dict[str, Any]]:
    """Run graph-level quality checks and return issues found.

    Checks:
    1. Orphan entities (no meaningful relations)
    2. Cross-type duplicate names (same canonical_name, different labels)
    3. Relation type violations (source/target types don't match constraints)

    Returns:
        List of issue dicts with type, count, and example details.
    """
    checks: list[dict[str, Any]] = []

    async with driver.session() as session:
        # 1. Orphan entities — no relations except MENTIONED_IN / structural
        result = await session.run(
            """
            MATCH (e {book_id: $book_id})
            WHERE NOT 'Chapter' IN labels(e) AND NOT 'Book' IN labels(e)
              AND NOT 'Chunk' IN labels(e) AND NOT 'Paragraph' IN labels(e)
              AND NOT 'Community' IN labels(e) AND NOT 'StateChange' IN labels(e)
              AND e.canonical_name IS NOT NULL
            OPTIONAL MATCH (e)-[r]-()
            WHERE NOT type(r) IN [
                'MENTIONED_IN', 'FIRST_MENTIONED_IN',
                'BELONGS_TO_COMMUNITY', 'HAS_PARAGRAPH',
                'HAS_CHUNK', 'CONTAINS', 'IN_BOOK', 'NEXT'
            ]
            WITH e, count(r) AS rel_count
            WHERE rel_count = 0
            RETURN e.canonical_name AS name, labels(e)[0] AS label
            ORDER BY label, name
            LIMIT 50
            """,
            {"book_id": book_id},
        )
        orphans = [{"name": r["name"], "label": r["label"]} async for r in result]
        if orphans:
            checks.append(
                {
                    "type": "orphan_entities",
                    "severity": "warning",
                    "count": len(orphans),
                    "message": f"{len(orphans)} entities have no meaningful relations",
                    "entities": orphans,
                }
            )

        # 2. Cross-type duplicates — same canonical_name, different labels
        result = await session.run(
            """
            MATCH (e {book_id: $book_id})
            WHERE e.canonical_name IS NOT NULL
              AND NOT 'Chapter' IN labels(e) AND NOT 'Book' IN labels(e)
              AND NOT 'Chunk' IN labels(e) AND NOT 'Paragraph' IN labels(e)
              AND NOT 'Community' IN labels(e) AND NOT 'StateChange' IN labels(e)
            WITH e.canonical_name AS name,
                 collect(DISTINCT labels(e)[0]) AS types,
                 count(e) AS node_count
            WHERE size(types) > 1
            RETURN name, types, node_count
            ORDER BY node_count DESC
            LIMIT 30
            """,
            {"book_id": book_id},
        )
        dupes = [
            {"name": r["name"], "types": r["types"], "count": r["node_count"]} async for r in result
        ]
        if dupes:
            checks.append(
                {
                    "type": "cross_type_duplicates",
                    "severity": "error",
                    "count": len(dupes),
                    "message": f"{len(dupes)} entity names appear with multiple types",
                    "entities": dupes,
                }
            )

        # 3. Relation type violations (HAS_SKILL on non-character source, etc.)
        result = await session.run(
            """
            MATCH (a {book_id: $book_id})-[r:HAS_SKILL]->(b)
            WHERE NOT 'Character' IN labels(a)
            RETURN a.canonical_name AS source, labels(a)[0] AS source_label,
                   type(r) AS rel, b.canonical_name AS target, labels(b)[0] AS target_label
            UNION ALL
            MATCH (a {book_id: $book_id})-[r:HAS_CLASS]->(b)
            WHERE NOT 'Character' IN labels(a)
            RETURN a.canonical_name AS source, labels(a)[0] AS source_label,
                   type(r) AS rel, b.canonical_name AS target, labels(b)[0] AS target_label
            UNION ALL
            MATCH (a {book_id: $book_id})-[r:LOCATED_AT]->(b)
            WHERE NOT 'Location' IN labels(b)
            RETURN a.canonical_name AS source, labels(a)[0] AS source_label,
                   type(r) AS rel, b.canonical_name AS target, labels(b)[0] AS target_label
            """,
            {"book_id": book_id},
        )
        violations = [
            {
                "source": r["source"],
                "source_label": r["source_label"],
                "relation": r["rel"],
                "target": r["target"],
                "target_label": r["target_label"],
            }
            async for r in result
        ]
        if violations:
            checks.append(
                {
                    "type": "relation_type_violations",
                    "severity": "error",
                    "count": len(violations),
                    "message": f"{len(violations)} relations have invalid source/target types",
                    "examples": violations[:20],
                }
            )

    logger.info(
        "consistency_checks_completed",
        book_id=book_id,
        issues_found=len(checks),
        total_problems=sum(c["count"] for c in checks),
    )

    return checks


# ── KG Quality: Orphan GOLEM entity resolution ────────────────────────


async def resolve_orphan_golem_entities(driver, book_id: str) -> dict[str, int]:
    """Fix orphan PsychologicalState/CharacterFeature nodes by fuzzy-matching character_name.

    Runs after iterative_cluster to leverage merged aliases. Uses multiple
    strategies: exact match, article stripping, fuzzy matching, and
    MENTIONED_IN co-occurrence.

    Returns: dict of fix counts per type.
    """
    fixes: dict[str, int] = {"psychological_state": 0, "character_feature": 0}

    async with driver.session() as session:
        # Strategy 1: Article stripping ("the X" → "X")
        for label, edge_type, fix_key in [
            ("PsychologicalState", "HAS_STATE", "psychological_state"),
            ("CharacterFeature", "HAS_FEATURE", "character_feature"),
        ]:
            result = await session.run(
                f"""
                MATCH (ps:{label} {{book_id: $book_id}})
                WHERE NOT (:Character)-[:{edge_type}]->(ps)
                  AND ps.character_name IS NOT NULL
                WITH ps, CASE
                    WHEN ps.character_name STARTS WITH 'the ' THEN substring(ps.character_name, 4)
                    WHEN ps.character_name STARTS WITH 'a ' THEN substring(ps.character_name, 2)
                    ELSE ps.character_name
                END AS stripped
                MATCH (c:Character {{book_id: $book_id}})
                WHERE c.canonical_name = stripped
                   OR stripped IN c.aliases
                MERGE (c)-[:{edge_type}]->(ps)
                RETURN count(ps) AS fixed
                """,
                {"book_id": book_id},
            )
            record = await result.single()
            if record:
                fixes[fix_key] += record["fixed"]

        # Strategy 2: Substring containment match (no APOC dependency)
        for label, edge_type, fix_key in [
            ("PsychologicalState", "HAS_STATE", "psychological_state"),
            ("CharacterFeature", "HAS_FEATURE", "character_feature"),
        ]:
            result = await session.run(
                f"""
                MATCH (ps:{label} {{book_id: $book_id}})
                WHERE NOT (:Character)-[:{edge_type}]->(ps)
                  AND ps.character_name IS NOT NULL
                  AND size(ps.character_name) > 2
                WITH ps
                MATCH (c:Character {{book_id: $book_id}})
                WHERE c.canonical_name CONTAINS ps.character_name
                   OR ps.character_name CONTAINS c.canonical_name
                   OR ANY(alias IN coalesce(c.aliases, []) WHERE alias CONTAINS ps.character_name)
                WITH ps, c,
                     toFloat(size(ps.character_name)) /
                     toFloat(CASE WHEN size(c.canonical_name) > size(ps.character_name)
                                  THEN size(c.canonical_name) ELSE size(ps.character_name) END) AS overlap
                WHERE overlap > 0.5
                WITH ps, c ORDER BY overlap DESC
                WITH ps, head(collect(c)) AS best_char
                WHERE best_char IS NOT NULL
                MERGE (best_char)-[:{edge_type}]->(ps)
                RETURN count(ps) AS fixed
                """,
                {"book_id": book_id},
            )
            record = await result.single()
            if record:
                fixes[fix_key] += record["fixed"]

    logger.info("orphan_golem_resolution", book_id=book_id, fixes=fixes)
    return fixes


async def enrich_entity_descriptions(
    driver,
    book_id: str,
    batch_id: str = "",
) -> int:
    """Generate descriptions for entities that have empty descriptions.

    For each entity without description:
    1. Fetch chunks where entity is MENTIONED_IN
    2. LLM generates 1-3 sentence description
    3. Write back to Neo4j

    Returns: number of entities enriched.
    """
    from app.llm.providers import get_instructor_for_task

    if not batch_id:
        batch_id = f"enrich:{book_id}:{int(time.time())}"

    # Fetch entities without descriptions (focus on Object, Profession, Creature)
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (e {book_id: $book_id})
            WHERE (e:Object OR e:Creature OR e:Faction OR e:Location OR e:Concept)
              AND (e.description IS NULL OR e.description = '')
              AND e.name IS NOT NULL
            OPTIONAL MATCH (e)-[:MENTIONED_IN|GROUNDED_IN]->(chunk:Chunk)
            WITH e, labels(e)[0] AS label,
                 collect(DISTINCT left(chunk.text, 300))[..3] AS passages
            WHERE size(passages) > 0
            RETURN elementId(e) AS eid, e.name AS name, label,
                   reduce(s = '', p IN passages | s + p + ' ') AS context
            LIMIT 200
            """,
            {"book_id": book_id},
        )
        entities_to_enrich = [r async for r in result]

    if not entities_to_enrich:
        logger.info("enrich_descriptions_nothing_to_do", book_id=book_id)
        return 0

    try:
        client, model = get_instructor_for_task("summary")
    except Exception:
        logger.warning("enrich_descriptions_no_llm", exc_info=True)
        return 0

    sem = asyncio.Semaphore(5)  # max 5 concurrent LLM calls
    enriched = 0

    async def _enrich_one(entity: dict) -> bool:
        async with sem:
            try:
                response = await client.chat.completions.create(
                    model=model,
                    response_model=None,
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate a brief 1-2 sentence description for a fiction entity based on context passages. Return ONLY the description text.",
                        },
                        {
                            "role": "user",
                            "content": f"Entity: {entity['name']} (type: {entity['label']})\nContext: {entity['context'][:1000]}",
                        },
                    ],
                    max_tokens=100,
                )
                desc = response.choices[0].message.content.strip() if response.choices else ""
                if desc and len(desc) > 10:
                    async with driver.session() as session:
                        await session.run(
                            """
                            MATCH (e) WHERE elementId(e) = $eid
                            SET e.description = $desc
                            """,
                            {"eid": entity["eid"], "desc": desc},
                        )
                    return True
            except Exception:
                logger.debug("enrich_description_failed", entity=entity["name"], exc_info=True)
            return False

    results = await asyncio.gather(*[_enrich_one(e) for e in entities_to_enrich])
    enriched = sum(1 for r in results if r)

    logger.info(
        "enrich_descriptions_completed",
        book_id=book_id,
        enriched=enriched,
        total=len(entities_to_enrich),
    )
    return enriched


async def infer_golem_edges(driver, book_id: str) -> dict[str, int]:
    """Topology-enhanced inference: generate missing GOLEM edges from graph structure.

    Inspired by LightKGG (2025). Uses temporal proximity and structural patterns.

    Returns: dict of edge counts created per type.
    """
    counts: dict[str, int] = {}

    async with driver.session() as session:
        # 1. FOLLOWS_STATE: consecutive PsychologicalStates for same character
        result = await session.run(
            """
            MATCH (c:Character {book_id: $book_id})-[:HAS_STATE]->(ps:PsychologicalState)
            WITH c, ps ORDER BY ps.chapter_start
            WITH c, collect(ps) AS states
            WHERE size(states) > 1
            UNWIND range(0, size(states)-2) AS i
            WITH states[i] AS prev, states[i+1] AS next
            WHERE NOT (prev)-[:FOLLOWS_STATE]->(next)
            MERGE (prev)-[:FOLLOWS_STATE]->(next)
            RETURN count(*) AS created
            """,
            {"book_id": book_id},
        )
        record = await result.single()
        counts["FOLLOWS_STATE"] = record["created"] if record else 0

        # 2. TRIGGERS_EVENT: link PsychologicalState to Event in same chapter
        result = await session.run(
            """
            MATCH (ps:PsychologicalState {book_id: $book_id})
            WHERE NOT (ps)-[:STATE_TRIGGERED_BY]->(:Event)
            MATCH (c:Character {book_id: $book_id})-[:HAS_STATE]->(ps)
            MATCH (c)-[:PARTICIPATES_IN]->(ev:Event {book_id: $book_id})
            WHERE ev.chapter_start = ps.chapter_start
            WITH ps, ev, rand() AS r ORDER BY r
            WITH ps, head(collect(ev)) AS nearest_event
            WHERE nearest_event IS NOT NULL
            MERGE (ps)-[:STATE_TRIGGERED_BY {inferred: true}]->(nearest_event)
            RETURN count(*) AS created
            """,
            {"book_id": book_id},
        )
        record = await result.single()
        counts["STATE_TRIGGERED_BY"] = record["created"] if record else 0

        # 3. SEQUENCED_IN: link Events to NarrativeSequences by chapter overlap
        result = await session.run(
            """
            MATCH (ns:NarrativeSequence {book_id: $book_id})
            WHERE ns.valid_from_chapter IS NOT NULL
            MATCH (ev:Event {book_id: $book_id})
            WHERE ev.chapter_start >= ns.valid_from_chapter
              AND (ns.chapter_end IS NULL OR ev.chapter_start <= ns.chapter_end)
              AND NOT (ev)-[:SEQUENCED_IN]->(ns)
            MERGE (ev)-[:SEQUENCED_IN {inferred: true}]->(ns)
            RETURN count(*) AS created
            """,
            {"book_id": book_id},
        )
        record = await result.single()
        counts["SEQUENCED_IN"] = record["created"] if record else 0

        # 4. RELATIONSHIP_CAUSED_BY: link SocialRelationship to Event via trigger
        result = await session.run(
            """
            MATCH (sr:SocialRelationship {book_id: $book_id})
            WHERE NOT (sr)-[:RELATIONSHIP_CAUSED_BY]->(:Event)
              AND sr.valid_from_chapter IS NOT NULL
            MATCH (ev:Event {book_id: $book_id})
            WHERE ev.chapter_start = sr.valid_from_chapter
            WITH sr, ev, rand() AS r ORDER BY r
            WITH sr, head(collect(ev)) AS trigger_ev
            WHERE trigger_ev IS NOT NULL
            MERGE (sr)-[:RELATIONSHIP_CAUSED_BY {inferred: true}]->(trigger_ev)
            RETURN count(*) AS created
            """,
            {"book_id": book_id},
        )
        record = await result.single()
        counts["RELATIONSHIP_CAUSED_BY"] = record["created"] if record else 0

        # 5. ROLE_IN_SEQUENCE: link NarrativeRoles to NarrativeSequences
        # If a NarrativeRole's character participates in events of a sequence,
        # the role applies to that sequence
        result = await session.run(
            """
            MATCH (nr:NarrativeRole {book_id: $book_id})
            WHERE NOT (nr)-[:ROLE_IN_SEQUENCE]->(:NarrativeSequence)
            MATCH (c:Character {book_id: $book_id, canonical_name: nr.character_name})
            MATCH (c)-[:PARTICIPATES_IN]->(ev:Event)-[:SEQUENCED_IN]->(ns:NarrativeSequence)
            WITH nr, ns, count(ev) AS ev_count
            WHERE ev_count >= 1
            WITH nr, ns ORDER BY ev_count DESC
            WITH nr, head(collect(ns)) AS best_seq
            WHERE best_seq IS NOT NULL
            MERGE (nr)-[:ROLE_IN_SEQUENCE {inferred: true}]->(best_seq)
            RETURN count(*) AS created
            """,
            {"book_id": book_id},
        )
        record = await result.single()
        counts["ROLE_IN_SEQUENCE"] = record["created"] if record else 0

    logger.info("infer_golem_edges_completed", book_id=book_id, counts=counts)
    return counts


# ── KG Quality: Relation reclassification ─────────────────────────────


async def reclassify_untyped_relations(driver, book_id: str) -> dict[str, int]:
    """Reclassify RELATES_TO edges into proper typed edges.

    Strategy 1: Character-Character RELATES_TO → SocialRelationship + INVOLVED_IN
    Strategy 2: Delete hallucinated edge types (count=1, long names)

    Returns: dict of action counts.
    """
    counts: dict[str, int] = {"char_char_reified": 0, "hallucinated_deleted": 0}

    async with driver.session() as session:
        # Strategy 1: Character-Character RELATES_TO → SocialRelationship
        result = await session.run(
            """
            MATCH (a:Character {book_id: $book_id})-[r:RELATES_TO]->(b:Character {book_id: $book_id})
            WITH a, b, r,
                 a.canonical_name + ' — ' + b.canonical_name AS sr_name,
                 CASE
                     WHEN r.type IS NOT NULL THEN r.type
                     WHEN r.subtype IS NOT NULL THEN r.subtype
                     ELSE 'professional'
                 END AS rel_type,
                 coalesce(r.valid_from_chapter, 1) AS vfc
            MERGE (sr:SocialRelationship {name: sr_name, book_id: $book_id})
            ON CREATE SET
                sr.relationship_type = rel_type,
                sr.valid_from_chapter = vfc,
                sr.valid_to_chapter = r.valid_to_chapter,
                sr.description = coalesce(r.context, ''),
                sr.batch_id = 'reclassify_post_extraction',
                sr.created_at = timestamp()
            MERGE (a)-[:INVOLVED_IN {role: 'participant', valid_from_chapter: vfc}]->(sr)
            MERGE (b)-[:INVOLVED_IN {role: 'participant', valid_from_chapter: vfc}]->(sr)
            DELETE r
            RETURN count(sr) AS reified
            """,
            {"book_id": book_id},
        )
        record = await result.single()
        counts["char_char_reified"] = record["reified"] if record else 0

        # Strategy 2: Delete hallucinated edge types (count=1, >25 chars or >3 underscores)
        result = await session.run(
            """
            MATCH (a {book_id: $book_id})-[r]->(b)
            WITH type(r) AS rt, collect(r) AS rels, count(r) AS cnt
            WHERE cnt = 1 AND (size(rt) > 25 OR size(rt) - size(replace(rt, '_', '')) > 3)
            UNWIND rels AS r
            DELETE r
            RETURN count(*) AS deleted
            """,
            {"book_id": book_id},
        )
        record = await result.single()
        counts["hallucinated_deleted"] = record["deleted"] if record else 0

    logger.info("reclassify_relations_completed", book_id=book_id, counts=counts)
    return counts


# ── KG Quality: AutoSchemaKG-style conceptualization ──────────────────


async def conceptualize_genre_entities(driver, book_id: str) -> dict[str, int]:
    """Conceptualize GenreEntity catch-all into proper typed nodes.

    Groups GenreEntity nodes by sub_type and promotes frequent sub_types
    (≥3 instances) to proper Neo4j labels. Less frequent ones are kept
    as GenreEntity.

    Returns: dict of sub_type → count promoted.
    """
    counts: dict[str, int] = {}

    async with driver.session() as session:
        # Find sub_types with enough instances to promote
        result = await session.run(
            """
            MATCH (ge:GenreEntity {book_id: $book_id})
            WHERE ge.sub_type IS NOT NULL AND ge.sub_type <> ''
            RETURN ge.sub_type AS sub_type, count(ge) AS cnt
            ORDER BY cnt DESC
            """,
            {"book_id": book_id},
        )
        sub_types = [r async for r in result]

    # Known promotable sub_types → Neo4j label mapping
    _PROMOTABLE = {
        "stat": "StatBlock",
        "spell": "Skill",
        "ability": "Skill",
        "potion": "Object",
        "enchantment": "Skill",
        "material": "Object",
        "rank": "Title",
        "skill_upgrade": "Skill",
        "skill_improvement": "Skill",
    }

    async with driver.session() as session:
        for row in sub_types:
            sub_type = row["sub_type"]
            count = row["cnt"]

            target_label = _PROMOTABLE.get(sub_type.lower())
            if not target_label:
                continue

            # Add the target label to matching GenreEntity nodes
            result = await session.run(
                f"""
                MATCH (ge:GenreEntity {{book_id: $book_id, sub_type: $sub_type}})
                SET ge:{target_label}
                RETURN count(ge) AS promoted
                """,
                {"book_id": book_id, "sub_type": sub_type},
            )
            record = await result.single()
            promoted = record["promoted"] if record else 0
            if promoted:
                counts[sub_type] = promoted

    logger.info("conceptualize_genre_entities_completed", book_id=book_id, counts=counts)
    return counts
