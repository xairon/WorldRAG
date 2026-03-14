"""KG export service — export knowledge graph data in various formats."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)


async def export_cypher(driver: AsyncDriver, saga_id: str) -> str:
    """Export all entities and relationships as Cypher CREATE statements."""
    lines: list[str] = []

    async with driver.session() as session:
        # Export nodes
        result = await session.run(
            """
            MATCH (n:Entity {group_id: $saga_id})
            RETURN n.name AS name, n.summary AS summary, labels(n) AS labels,
                   properties(n) AS props
            """,
            saga_id=saga_id,
        )
        records = await result.data()
        for r in records:
            labels_str = ":".join(r["labels"])
            props = {k: v for k, v in r["props"].items() if v is not None}
            props_str = json.dumps(props, ensure_ascii=False)
            lines.append(f"CREATE (:{labels_str} {props_str});")

        # Export relationships
        result = await session.run(
            """
            MATCH (a:Entity {group_id: $saga_id})-[r]->(b:Entity {group_id: $saga_id})
            RETURN a.name AS source, type(r) AS rel_type, b.name AS target,
                   properties(r) AS props
            """,
            saga_id=saga_id,
        )
        rels = await result.data()
        for r in rels:
            props = {k: v for k, v in r["props"].items() if v is not None}
            props_str = f" {json.dumps(props, ensure_ascii=False)}" if props else ""
            lines.append(
                f"MATCH (a {{name: {json.dumps(r['source'])}}}), "
                f"(b {{name: {json.dumps(r['target'])}}}) "
                f"CREATE (a)-[:{r['rel_type']}{props_str}]->(b);"
            )

    logger.info("kg_exported_cypher", saga_id=saga_id, nodes=len(records), rels=len(rels))
    return "\n".join(lines)


async def export_json_ld(driver: AsyncDriver, saga_id: str) -> dict[str, Any]:
    """Export as JSON-LD format."""
    graph: list[dict[str, Any]] = []

    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (n:Entity {group_id: $saga_id})
            RETURN n.name AS name, n.summary AS summary, labels(n) AS labels
            """,
            saga_id=saga_id,
        )
        entities = await result.data()
        for e in entities:
            node: dict[str, Any] = {
                "@type": e["labels"][0] if e["labels"] else "Entity",
                "name": e["name"],
            }
            if e.get("summary"):
                node["description"] = e["summary"]
            graph.append(node)

        result = await session.run(
            """
            MATCH (a:Entity {group_id: $saga_id})-[r]->(b:Entity {group_id: $saga_id})
            RETURN a.name AS source, type(r) AS rel_type, b.name AS target
            """,
            saga_id=saga_id,
        )
        rels = await result.data()
        for r in rels:
            graph.append({
                "@type": "Relationship",
                "source": r["source"],
                "predicate": r["rel_type"],
                "target": r["target"],
            })

    logger.info("kg_exported_jsonld", saga_id=saga_id, items=len(graph))
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "worldrag": "https://worldrag.dev/ontology/",
        },
        "@graph": graph,
    }


async def export_csv(driver: AsyncDriver, saga_id: str) -> dict[str, str]:
    """Export as CSV (entities.csv + relationships.csv)."""
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (n:Entity {group_id: $saga_id})
            RETURN n.name AS name, n.summary AS summary, labels(n) AS labels
            """,
            saga_id=saga_id,
        )
        entities = await result.data()

        result = await session.run(
            """
            MATCH (a:Entity {group_id: $saga_id})-[r]->(b:Entity {group_id: $saga_id})
            RETURN a.name AS source, type(r) AS rel_type, b.name AS target
            """,
            saga_id=saga_id,
        )
        rels = await result.data()

    # Build CSVs
    entity_lines = ["name,type,summary"]
    for e in entities:
        name = e["name"].replace('"', '""')
        label = e["labels"][0] if e["labels"] else "Entity"
        summary = (e.get("summary") or "").replace('"', '""')
        entity_lines.append(f'"{name}","{label}","{summary}"')

    rel_lines = ["source,relationship,target"]
    for r in rels:
        source = r["source"].replace('"', '""')
        target = r["target"].replace('"', '""')
        rel_lines.append(f'"{source}","{r["rel_type"]}","{target}"')

    logger.info("kg_exported_csv", saga_id=saga_id, entities=len(entities), rels=len(rels))
    return {
        "entities": "\n".join(entity_lines),
        "relationships": "\n".join(rel_lines),
    }
