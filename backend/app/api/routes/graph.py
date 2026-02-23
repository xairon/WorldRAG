"""Graph Explorer API routes.

Provides KG browsing, entity search, neighborhood expansion, and
subgraph retrieval for the frontend Graph Explorer component.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_neo4j
from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])

# Allowed node labels for parameterised queries (whitelist, no injection)
ALLOWED_LABELS = frozenset({
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
})


# ── Graph statistics ────────────────────────────────────────────────────────


@router.get("/stats")
async def graph_stats(
    book_id: str | None = None,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Return global graph statistics (or scoped to a book).

    Counts nodes and relationships by label/type.
    """
    repo = Neo4jRepository(driver)

    if book_id:
        nodes = await repo.execute_read(
            """
            MATCH (n)
            WHERE n.book_id = $book_id OR (n:Book AND n.id = $book_id)
            WITH labels(n)[0] AS label, count(n) AS cnt
            RETURN label, cnt ORDER BY cnt DESC
            """,
            {"book_id": book_id},
        )
        rels = await repo.execute_read(
            """
            MATCH ()-[r]->()
            WHERE r.book_id = $book_id
            WITH type(r) AS rel_type, count(r) AS cnt
            RETURN rel_type, cnt ORDER BY cnt DESC
            """,
            {"book_id": book_id},
        )
    else:
        nodes = await repo.execute_read(
            """
            MATCH (n)
            WITH labels(n)[0] AS label, count(n) AS cnt
            RETURN label, cnt ORDER BY cnt DESC
            """
        )
        rels = await repo.execute_read(
            """
            MATCH ()-[r]->()
            WITH type(r) AS rel_type, count(r) AS cnt
            RETURN rel_type, cnt ORDER BY cnt DESC
            """
        )

    return {
        "nodes": {r["label"]: r["cnt"] for r in nodes},
        "relationships": {r["rel_type"]: r["cnt"] for r in rels},
        "total_nodes": sum(r["cnt"] for r in nodes),
        "total_relationships": sum(r["cnt"] for r in rels),
    }


# ── Entity search ──────────────────────────────────────────────────────────


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    label: str | None = Query(None, description="Filter by node label"),
    book_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    driver: AsyncDriver = Depends(get_neo4j),
) -> list[dict]:
    """Full-text search across all entity types.

    Returns matching nodes with label, name, description, and score.
    """
    repo = Neo4jRepository(driver)

    # Use CONTAINS for simple search (fulltext index requires separate setup)
    if label and label in ALLOWED_LABELS:
        results = await repo.execute_read(
            f"""
            MATCH (n:{label})
            WHERE toLower(n.name) CONTAINS toLower($q)
                  {"AND n.book_id = $book_id" if book_id else ""}
            RETURN labels(n)[0] AS label, n.name AS name,
                   n.description AS description,
                   n.canonical_name AS canonical_name,
                   elementId(n) AS id
            LIMIT $limit
            """,
            {"q": q, "book_id": book_id, "limit": limit},
        )
    else:
        results = await repo.execute_read(
            """
            MATCH (n)
            WHERE n.name IS NOT NULL
              AND toLower(n.name) CONTAINS toLower($q)
              AND NOT n:Book AND NOT n:Chapter AND NOT n:Chunk
              $book_filter
            RETURN labels(n)[0] AS label, n.name AS name,
                   n.description AS description,
                   n.canonical_name AS canonical_name,
                   elementId(n) AS id
            ORDER BY size(n.name)
            LIMIT $limit
            """.replace(
                "$book_filter",
                "AND n.book_id = $book_id" if book_id else "",
            ),
            {"q": q, "book_id": book_id, "limit": limit},
        )

    return results


# ── Entity detail ───────────────────────────────────────────────────────────


@router.get("/entity/{entity_id}")
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
        raise HTTPException(status_code=404, detail="Entity not found")

    row = results[0]
    return {
        "id": row["id"],
        "labels": row["labels"],
        "properties": row["props"],
    }


# ── Neighborhood (expand node) ──────────────────────────────────────────────


@router.get("/neighbors/{entity_id}")
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


@router.get("/subgraph/{book_id}")
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

    # Build label filter
    label_clause = ""
    if label and label in ALLOWED_LABELS:
        label_clause = f"AND (n:{label} OR m:{label})"

    chapter_clause = ""
    if chapter is not None:
        chapter_clause = """
            AND (r.valid_from_chapter IS NULL
                 OR r.valid_from_chapter <= $chapter)
            AND (r.valid_to_chapter IS NULL
                 OR r.valid_to_chapter >= $chapter)
        """

    results = await repo.execute_read(
        f"""
        MATCH (n)-[r]-(m)
        WHERE (n.book_id = $book_id OR m.book_id = $book_id)
          AND NOT n:Chunk AND NOT n:Book AND NOT n:Chapter
          AND NOT m:Chunk AND NOT m:Book AND NOT m:Chapter
          {label_clause}
          {chapter_clause}
        WITH n, r, m
        LIMIT $limit
        RETURN collect(DISTINCT {{
            id: elementId(n),
            labels: labels(n),
            name: n.name,
            description: n.description
        }}) + collect(DISTINCT {{
            id: elementId(m),
            labels: labels(m),
            name: m.name,
            description: m.description
        }}) AS nodes,
        collect(DISTINCT {{
            id: elementId(r),
            type: type(r),
            source: elementId(startNode(r)),
            target: elementId(endNode(r)),
            properties: properties(r)
        }}) AS edges
        """,
        {"book_id": book_id, "chapter": chapter, "limit": limit},
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


# ── Character detail (profile) ─────────────────────────────────────────────


@router.get("/characters/{name}")
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

    book_filter = "AND ch.book_id = $book_id" if book_id else ""

    # Main character data
    chars = await repo.execute_read(
        f"""
        MATCH (ch:Character)
        WHERE ch.canonical_name = $name OR ch.name = $name
              OR $name IN ch.aliases
              {book_filter}
        RETURN properties(ch) AS props, elementId(ch) AS id
        LIMIT 1
        """,
        {"name": name, "book_id": book_id},
    )

    if not chars:
        raise HTTPException(status_code=404, detail="Character not found")

    char = chars[0]

    # Related entities
    skills = await repo.execute_read(
        """
        MATCH (ch:Character)-[r:HAS_SKILL]->(s:Skill)
        WHERE elementId(ch) = $id
        RETURN s.name AS name, s.rank AS rank, s.skill_type AS type,
               s.description AS description,
               r.valid_from_chapter AS since_chapter
        ORDER BY r.valid_from_chapter
        """,
        {"id": char["id"]},
    )

    classes = await repo.execute_read(
        """
        MATCH (ch:Character)-[r:HAS_CLASS]->(c:Class)
        WHERE elementId(ch) = $id
        RETURN c.name AS name, c.tier AS tier, c.description AS description,
               r.valid_from_chapter AS since_chapter
        ORDER BY r.valid_from_chapter
        """,
        {"id": char["id"]},
    )

    titles = await repo.execute_read(
        """
        MATCH (ch:Character)-[r:HAS_TITLE]->(t:Title)
        WHERE elementId(ch) = $id
        RETURN t.name AS name, t.description AS description,
               r.acquired_chapter AS acquired_chapter
        ORDER BY r.acquired_chapter
        """,
        {"id": char["id"]},
    )

    relationships = await repo.execute_read(
        """
        MATCH (ch:Character)-[r:RELATES_TO]-(other:Character)
        WHERE elementId(ch) = $id
        RETURN other.name AS name, r.type AS rel_type,
               r.subtype AS subtype, r.context AS context,
               r.valid_from_chapter AS since_chapter
        ORDER BY r.valid_from_chapter
        """,
        {"id": char["id"]},
    )

    events = await repo.execute_read(
        """
        MATCH (ch:Character)-[:PARTICIPATES_IN]->(ev:Event)
        WHERE elementId(ch) = $id
        RETURN ev.name AS name, ev.description AS description,
               ev.event_type AS type, ev.significance AS significance,
               ev.chapter_start AS chapter
        ORDER BY ev.chapter_start
        """,
        {"id": char["id"]},
    )

    return {
        "id": char["id"],
        "properties": char["props"],
        "skills": skills,
        "classes": classes,
        "titles": titles,
        "relationships": relationships,
        "events": events,
    }


# ── Timeline ────────────────────────────────────────────────────────────────


@router.get("/timeline/{book_id}")
async def get_timeline(
    book_id: str,
    significance: str | None = Query(
        None, description="Min significance: minor, moderate, major, critical"
    ),
    limit: int = Query(100, ge=1, le=500),
    driver: AsyncDriver = Depends(get_neo4j),
) -> list[dict]:
    """Get event timeline for a book, ordered by chapter."""
    repo = Neo4jRepository(driver)

    sig_clause = ""
    if significance:
        sig_levels = {
            "critical": ["critical", "arc_defining"],
            "major": ["major", "critical", "arc_defining"],
            "moderate": ["moderate", "major", "critical", "arc_defining"],
            "minor": ["minor", "moderate", "major", "critical", "arc_defining"],
        }
        allowed = sig_levels.get(significance, [])
        if allowed:
            sig_clause = "AND ev.significance IN $allowed"

    results = await repo.execute_read(
        f"""
        MATCH (ev:Event)
        WHERE ev.book_id = $book_id
              {sig_clause}
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
        {"book_id": book_id, "allowed": sig_levels.get(significance, []), "limit": limit},
    )

    return results


# ── Helpers ─────────────────────────────────────────────────────────────────


def _format_subgraph(results: list[dict]) -> dict:
    """Format APOC subgraph results into nodes + edges."""
    if not results:
        return {"nodes": [], "edges": []}

    nodes = []
    edges = []

    for row in results:
        for node in row.get("nodes", []):
            if hasattr(node, "labels"):
                nodes.append({
                    "id": node.element_id,
                    "labels": list(node.labels),
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                })

        for rel in row.get("relationships", []):
            if hasattr(rel, "type"):
                edges.append({
                    "id": rel.element_id,
                    "type": rel.type,
                    "source": rel.start_node.element_id,
                    "target": rel.end_node.element_id,
                })

    return {"nodes": nodes, "edges": edges}
