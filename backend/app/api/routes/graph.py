"""Graph Explorer API routes.

Provides KG browsing, entity search, neighborhood expansion, and
subgraph retrieval for the frontend Graph Explorer component.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_auth
from app.api.dependencies import get_neo4j
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])

# Allowed node labels for parameterised queries (whitelist, no injection)
ALLOWED_LABELS = frozenset(
    {
        "Character",
        "Skill",
        "Class",
        "Title",
        "Event",
        "Location",
        "Item",
        "Creature",
        "Faction",
        "Concept",
    }
)


# ── Graph statistics ────────────────────────────────────────────────────────


@router.get("/stats", dependencies=[Depends(require_auth)])
async def graph_stats(
    book_id: str | None = None,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Return global graph statistics (or scoped to a book).

    Counts nodes and relationships by label/type.
    """
    repo = Neo4jRepository(driver)

    if book_id:
        nodes, rels = await asyncio.gather(
            repo.execute_read(
                """
                MATCH (n)
                WHERE n.book_id = $book_id OR (n:Book AND n.id = $book_id)
                WITH labels(n)[0] AS label, count(n) AS cnt
                RETURN label, cnt ORDER BY cnt DESC
                """,
                {"book_id": book_id},
            ),
            repo.execute_read(
                """
                MATCH ()-[r]->()
                WHERE r.book_id = $book_id
                WITH type(r) AS rel_type, count(r) AS cnt
                RETURN rel_type, cnt ORDER BY cnt DESC
                """,
                {"book_id": book_id},
            ),
        )
    else:
        nodes, rels = await asyncio.gather(
            repo.execute_read(
                """
                MATCH (n)
                WITH labels(n)[0] AS label, count(n) AS cnt
                RETURN label, cnt ORDER BY cnt DESC
                """
            ),
            repo.execute_read(
                """
                MATCH ()-[r]->()
                WITH type(r) AS rel_type, count(r) AS cnt
                RETURN rel_type, cnt ORDER BY cnt DESC
                """
            ),
        )

    return {
        "nodes": {r["label"]: r["cnt"] for r in nodes},
        "relationships": {r["rel_type"]: r["cnt"] for r in rels},
        "total_nodes": sum(r["cnt"] for r in nodes),
        "total_relationships": sum(r["cnt"] for r in rels),
    }


# ── Entity search ──────────────────────────────────────────────────────────


@router.get("/search", dependencies=[Depends(require_auth)])
async def search_entities(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    label: str | None = Query(None, description="Filter by node label"),
    book_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    driver: AsyncDriver = Depends(get_neo4j),
) -> list[dict]:
    """Full-text search across all entity types.

    Uses the `entity_fulltext` Neo4j index when available (O(1) lookup),
    with automatic fallback to CONTAINS scan if the index doesn't exist.
    Returns matching nodes with label, name, description, and score.
    """
    repo = Neo4jRepository(driver)

    # Escape Lucene special characters for fulltext query
    lucene_query = _escape_lucene(q)

    # Try fulltext index first, fall back to CONTAINS if index is missing
    try:
        results = await _search_fulltext(
            repo,
            lucene_query,
            label,
            book_id,
            limit,
        )
    except Exception:
        logger.debug("fulltext_index_unavailable, falling back to CONTAINS")
        results = await _search_contains(repo, q, label, book_id, limit)

    return results


# ── Entity detail ───────────────────────────────────────────────────────────


@router.get("/entity/{entity_id}", dependencies=[Depends(require_auth)])
async def get_entity(
    entity_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get full entity details by element ID."""
    repo = Neo4jRepository(driver)

    results = await repo.execute_read(
        """
        MATCH (n) WHERE elementId(n) = $id
        RETURN labels(n) AS labels, properties(n) AS props, elementId(n) AS id
        """,
        {"id": entity_id},
    )

    if not results:
        raise NotFoundError("Entity not found")

    row = results[0]
    return {
        "id": row["id"],
        "labels": row["labels"],
        "properties": row["props"],
    }


# ── Entity wiki page ──────────────────────────────────────────────────────


@router.get("/wiki/{entity_type}/{entity_name}", dependencies=[Depends(require_auth)])
async def get_entity_wiki(
    entity_type: str,
    entity_name: str,
    book_id: str | None = None,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get full entity wiki page data: properties, connections, appearances."""
    if entity_type not in ALLOWED_LABELS:
        raise NotFoundError(f"Unknown entity type: {entity_type}")

    repo = Neo4jRepository(driver)

    # Find entity by name and type
    entities = await repo.execute_read(
        f"""
        MATCH (n:{entity_type})
        WHERE (n.name = $name OR n.canonical_name = $name)
              AND (CASE WHEN $has_book THEN n.book_id = $book_id ELSE true END)
        RETURN properties(n) AS props, elementId(n) AS id, labels(n) AS labels
        LIMIT 1
        """,
        {"name": entity_name, "book_id": book_id, "has_book": book_id is not None},
    )

    if not entities:
        raise NotFoundError(f"{entity_type} '{entity_name}' not found")

    entity = entities[0]
    entity_id = entity["id"]

    # Fetch connections and appearances in parallel
    connections, appearances = await asyncio.gather(
        repo.execute_read(
            """
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $id
              AND NOT m:Chunk AND NOT m:Book
            RETURN type(r) AS rel_type,
                   CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END AS direction,
                   labels(m)[0] AS target_label,
                   m.name AS target_name,
                   properties(r) AS rel_props,
                   elementId(m) AS target_id
            ORDER BY rel_type, target_name
            LIMIT 100
            """,
            {"id": entity_id},
        ),
        repo.execute_read(
            """
            MATCH (n)-[:GROUNDED_IN|MENTIONED_IN]->(chap:Chapter)
            WHERE elementId(n) = $id
            RETURN chap.number AS chapter, chap.title AS title
            ORDER BY chap.number
            """,
            {"id": entity_id},
        ),
    )

    # Group connections by relationship type
    grouped: dict[str, list[dict]] = {}
    for conn in connections:
        rel = conn["rel_type"]
        if rel not in grouped:
            grouped[rel] = []
        grouped[rel].append(
            {
                "target_name": conn["target_name"],
                "target_label": conn["target_label"],
                "target_id": conn["target_id"],
                "direction": conn["direction"],
                "properties": conn["rel_props"],
            }
        )

    return {
        "id": entity_id,
        "labels": entity["labels"],
        "properties": entity["props"],
        "connections": grouped,
        "appearances": appearances,
    }


# ── Neighborhood (expand node) ──────────────────────────────────────────────


@router.get("/neighbors/{entity_id}", dependencies=[Depends(require_auth)])
async def get_neighbors(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(50, ge=1, le=200),
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get the neighborhood of a node (ego graph).

    Returns nodes and edges within `depth` hops. Useful for expanding
    a character to see related skills, events, relationships, etc.
    """
    repo = Neo4jRepository(driver)

    results = await repo.execute_read(
        """
        MATCH (start) WHERE elementId(start) = $id
        CALL apoc.path.subgraphAll(start, {maxLevel: $depth, limit: $limit})
        YIELD nodes, relationships
        RETURN nodes, relationships
        """,
        {"id": entity_id, "depth": depth, "limit": limit},
    )

    if not results:
        # Fallback without APOC
        results = await repo.execute_read(
            """
            MATCH (start) WHERE elementId(start) = $id
            OPTIONAL MATCH path = (start)-[*1..2]-(neighbor)
            WHERE NOT neighbor:Chunk AND NOT neighbor:Book
            WITH start, collect(DISTINCT neighbor)[..$limit] AS neighbors,
                 collect(DISTINCT relationships(path)) AS all_rels
            RETURN start, neighbors, all_rels
            """,
            {"id": entity_id, "limit": limit},
        )

    return _format_subgraph(results)


# ── Subgraph for a book ────────────────────────────────────────────────────


@router.get("/subgraph/{book_id}", dependencies=[Depends(require_auth)])
async def get_book_subgraph(
    book_id: str,
    label: str | None = Query(None, description="Filter by node label"),
    chapter: int | None = Query(None, description="Filter by chapter"),
    limit: int = Query(100, ge=1, le=500),
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get the full entity subgraph for a book.

    Returns nodes and edges for visualization. Optionally filter
    by entity label or chapter scope.
    """
    repo = Neo4jRepository(driver)

    # Fully parameterized — no f-string interpolation of labels
    results = await repo.execute_read(
        """
        MATCH (n)-[r]-(m)
        WHERE (n.book_id = $book_id OR m.book_id = $book_id)
          AND NOT n:Chunk AND NOT n:Book AND NOT n:Chapter
          AND NOT m:Chunk AND NOT m:Book AND NOT m:Chapter
          AND (CASE WHEN $has_label THEN ($label IN labels(n) OR $label IN labels(m)) ELSE true END)
          AND (CASE WHEN $has_chapter
               THEN (r.valid_from_chapter IS NULL OR r.valid_from_chapter <= $chapter)
                    AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter >= $chapter)
               ELSE true END)
        WITH n, r, m
        LIMIT $limit
        RETURN collect(DISTINCT {
            id: elementId(n),
            labels: labels(n),
            name: n.name,
            description: n.description
        }) + collect(DISTINCT {
            id: elementId(m),
            labels: labels(m),
            name: m.name,
            description: m.description
        }) AS nodes,
        collect(DISTINCT {
            id: elementId(r),
            type: type(r),
            source: elementId(startNode(r)),
            target: elementId(endNode(r)),
            properties: properties(r)
        }) AS edges
        """,
        {
            "book_id": book_id,
            "chapter": chapter,
            "limit": limit,
            "label": label if label and label in ALLOWED_LABELS else "",
            "has_label": label is not None and label in ALLOWED_LABELS,
            "has_chapter": chapter is not None,
        },
    )

    if not results:
        return {"nodes": [], "edges": []}

    row = results[0]
    # Deduplicate nodes by id
    seen_ids: set[str] = set()
    unique_nodes = []
    for n in row.get("nodes", []):
        nid = n.get("id")
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            unique_nodes.append(n)

    return {"nodes": unique_nodes, "edges": row.get("edges", [])}


# ── Entity listing (paginated) ─────────────────────────────────────────────


@router.get("/entities", dependencies=[Depends(require_auth)])
async def list_entities(
    book_id: str = Query(..., description="Book ID"),
    label: str = Query(..., description="Entity label (Character, Skill, etc.)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """List entities of a specific type for a book, with pagination."""
    if label not in ALLOWED_LABELS:
        raise HTTPException(status_code=400, detail=f"Invalid label: {label}")

    repo = Neo4jRepository(driver)

    # Count total
    count_result = await repo.execute_read(
        """
        MATCH (n)
        WHERE n.book_id = $book_id AND $label IN labels(n)
        RETURN count(n) AS total
        """,
        {"book_id": book_id, "label": label},
    )
    total = count_result[0]["total"] if count_result else 0

    # Fetch page
    results = await repo.execute_read(
        """
        MATCH (n)
        WHERE n.book_id = $book_id AND $label IN labels(n)
        RETURN elementId(n) AS id,
               labels(n) AS labels,
               n.name AS name,
               n.canonical_name AS canonical_name,
               n.description AS description
        ORDER BY n.name
        SKIP $offset LIMIT $limit
        """,
        {"book_id": book_id, "label": label, "offset": offset, "limit": limit},
    )

    return {
        "entities": [dict(r) for r in results],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ── Character detail (profile) ─────────────────────────────────────────────


@router.get("/characters/{name}", dependencies=[Depends(require_auth)])
async def get_character_profile(
    name: str,
    book_id: str | None = None,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get a rich character profile from the KG.

    Returns the character's properties, skills, classes, titles,
    relationships, events, and progression timeline.
    """
    repo = Neo4jRepository(driver)

    # Main character data (parameterized book filter)
    chars = await repo.execute_read(
        """
        MATCH (ch:Character)
        WHERE (ch.canonical_name = $name OR ch.name = $name
              OR $name IN ch.aliases)
              AND (CASE WHEN $has_book THEN ch.book_id = $book_id ELSE true END)
        RETURN properties(ch) AS props, elementId(ch) AS id
        LIMIT 1
        """,
        {"name": name, "book_id": book_id, "has_book": book_id is not None},
    )

    if not chars:
        raise NotFoundError("Character not found")

    char = chars[0]

    # Related entities — fetch all in parallel
    char_id = char["id"]
    skills, classes, titles, relationships, events = await asyncio.gather(
        repo.execute_read(
            """
            MATCH (ch:Character)-[r:HAS_SKILL]->(s:Skill)
            WHERE elementId(ch) = $id
            RETURN s.name AS name, s.rank AS rank, s.skill_type AS type,
                   s.description AS description,
                   r.valid_from_chapter AS since_chapter
            ORDER BY r.valid_from_chapter
            """,
            {"id": char_id},
        ),
        repo.execute_read(
            """
            MATCH (ch:Character)-[r:HAS_CLASS]->(c:Class)
            WHERE elementId(ch) = $id
            RETURN c.name AS name, c.tier AS tier, c.description AS description,
                   r.valid_from_chapter AS since_chapter
            ORDER BY r.valid_from_chapter
            """,
            {"id": char_id},
        ),
        repo.execute_read(
            """
            MATCH (ch:Character)-[r:HAS_TITLE]->(t:Title)
            WHERE elementId(ch) = $id
            RETURN t.name AS name, t.description AS description,
                   r.acquired_chapter AS acquired_chapter
            ORDER BY r.acquired_chapter
            """,
            {"id": char_id},
        ),
        repo.execute_read(
            """
            MATCH (ch:Character)-[r:RELATES_TO]-(other:Character)
            WHERE elementId(ch) = $id
            RETURN other.name AS name, r.type AS rel_type,
                   r.subtype AS subtype, r.context AS context,
                   r.valid_from_chapter AS since_chapter
            ORDER BY r.valid_from_chapter
            """,
            {"id": char_id},
        ),
        repo.execute_read(
            """
            MATCH (ch:Character)-[:PARTICIPATES_IN]->(ev:Event)
            WHERE elementId(ch) = $id
            RETURN ev.name AS name, ev.description AS description,
                   ev.event_type AS type, ev.significance AS significance,
                   ev.chapter_start AS chapter
            ORDER BY ev.chapter_start
            """,
            {"id": char_id},
        ),
    )

    return {
        "id": char_id,
        "properties": char["props"],
        "skills": skills,
        "classes": classes,
        "titles": titles,
        "relationships": relationships,
        "events": events,
    }


# ── Timeline ────────────────────────────────────────────────────────────────


@router.get("/timeline/{book_id}", dependencies=[Depends(require_auth)])
async def get_timeline(
    book_id: str,
    significance: str | None = Query(
        None, description="Min significance: minor, moderate, major, critical"
    ),
    character: str | None = Query(None, description="Filter events by character name"),
    limit: int = Query(100, ge=1, le=500),
    driver: AsyncDriver = Depends(get_neo4j),
) -> list[dict]:
    """Get event timeline for a book, ordered by chapter."""
    repo = Neo4jRepository(driver)

    sig_levels_map = {
        "critical": ["critical", "arc_defining"],
        "major": ["major", "critical", "arc_defining"],
        "moderate": ["moderate", "major", "critical", "arc_defining"],
        "minor": ["minor", "moderate", "major", "critical", "arc_defining"],
    }

    allowed: list[str] = []
    if significance:
        allowed = sig_levels_map.get(significance, [])

    results = await repo.execute_read(
        """
        MATCH (ev:Event)
        WHERE ev.book_id = $book_id
          AND (CASE WHEN $has_sig THEN ev.significance IN $allowed ELSE true END)
          AND (CASE WHEN $has_character THEN EXISTS {
                MATCH (ev)<-[:PARTICIPATES_IN]-(filter_ch:Character)
                WHERE filter_ch.canonical_name = $character OR filter_ch.name = $character
              } ELSE true END)
        OPTIONAL MATCH (ev)<-[:PARTICIPATES_IN]-(ch:Character)
        OPTIONAL MATCH (ev)-[:OCCURS_AT]->(loc:Location)
        RETURN ev.name AS name, ev.description AS description,
               ev.event_type AS type, ev.significance AS significance,
               ev.chapter_start AS chapter,
               collect(DISTINCT ch.name) AS participants,
               collect(DISTINCT loc.name) AS locations
        ORDER BY ev.chapter_start
        LIMIT $limit
        """,
        {
            "book_id": book_id,
            "character": character,
            "has_character": character is not None,
            "allowed": allowed,
            "has_sig": len(allowed) > 0,
            "limit": limit,
        },
    )

    return results


# ── Helpers ─────────────────────────────────────────────────────────────────


_LUCENE_SPECIAL = frozenset('+-&|!(){}[]^"~*?:\\/')


def _escape_lucene(text: str) -> str:
    """Escape Lucene special characters for fulltext queries."""
    return "".join(f"\\{ch}" if ch in _LUCENE_SPECIAL else ch for ch in text)


async def _search_fulltext(
    repo: Neo4jRepository,
    lucene_query: str,
    label: str | None,
    book_id: str | None,
    limit: int,
) -> list[dict]:
    """Search using the entity_fulltext index (fast, indexed)."""
    # Append wildcard for prefix matching
    ft_query = f"{lucene_query}*" if lucene_query else "*"

    return await repo.execute_read(
        """
        CALL db.index.fulltext.queryNodes('entity_fulltext', $ft_query)
        YIELD node AS n, score
        WHERE (CASE WHEN $has_label THEN $label IN labels(n) ELSE true END)
          AND (CASE WHEN $has_book THEN n.book_id = $book_id ELSE true END)
        RETURN labels(n) AS labels, n.name AS name,
               n.description AS description,
               n.canonical_name AS canonical_name,
               elementId(n) AS id, score
        ORDER BY score DESC
        LIMIT $limit
        """,
        {
            "ft_query": ft_query,
            "label": label if label and label in ALLOWED_LABELS else "",
            "has_label": label is not None and label in ALLOWED_LABELS,
            "book_id": book_id,
            "has_book": book_id is not None,
            "limit": limit,
        },
    )


async def _search_contains(
    repo: Neo4jRepository,
    q: str,
    label: str | None,
    book_id: str | None,
    limit: int,
) -> list[dict]:
    """Fallback CONTAINS scan when fulltext index is unavailable."""
    if label and label in ALLOWED_LABELS:
        return await repo.execute_read(
            """
            MATCH (n)
            WHERE $label IN labels(n)
              AND toLower(n.name) CONTAINS toLower($q)
              AND (CASE WHEN $has_book THEN n.book_id = $book_id ELSE true END)
            RETURN labels(n) AS labels, n.name AS name,
                   n.description AS description,
                   n.canonical_name AS canonical_name,
                   elementId(n) AS id
            LIMIT $limit
            """,
            {
                "q": q,
                "label": label,
                "book_id": book_id,
                "has_book": book_id is not None,
                "limit": limit,
            },
        )

    return await repo.execute_read(
        """
        MATCH (n)
        WHERE n.name IS NOT NULL
          AND toLower(n.name) CONTAINS toLower($q)
          AND NOT n:Book AND NOT n:Chapter AND NOT n:Chunk
          AND (CASE WHEN $has_book THEN n.book_id = $book_id ELSE true END)
        RETURN labels(n) AS labels, n.name AS name,
               n.description AS description,
               n.canonical_name AS canonical_name,
               elementId(n) AS id
        ORDER BY size(n.name)
        LIMIT $limit
        """,
        {"q": q, "book_id": book_id, "has_book": book_id is not None, "limit": limit},
    )


def _format_subgraph(results: list[dict]) -> dict:
    """Format APOC subgraph results into nodes + edges."""
    if not results:
        return {"nodes": [], "edges": []}

    nodes = []
    edges = []

    for row in results:
        for node in row.get("nodes", []):
            if hasattr(node, "labels"):
                nodes.append(
                    {
                        "id": node.element_id,
                        "labels": list(node.labels),
                        "name": node.get("name", ""),
                        "description": node.get("description", ""),
                    }
                )

        for rel in row.get("relationships", []):
            if hasattr(rel, "type"):
                edges.append(
                    {
                        "id": rel.element_id,
                        "type": rel.type,
                        "source": rel.start_node.element_id,
                        "target": rel.end_node.element_id,
                    }
                )

    return {"nodes": nodes, "edges": edges}
