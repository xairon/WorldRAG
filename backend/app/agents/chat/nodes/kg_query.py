"""KG query node: entity-centric Cypher queries bypassing vector search."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import KG_QUERY_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def kg_search(
    state: dict[str, Any],
    *,
    repo,
) -> dict[str, Any]:
    """Search the Knowledge Graph for entity-centric queries.

    If no results found, sets route to 'hybrid_rag' for fallback.
    """
    llm = get_langchain_llm(settings.llm_chat)
    query = state["query"]
    book_id = state["book_id"]
    max_chapter = state.get("max_chapter")

    # Step 1: Extract entity names from query
    response = await llm.ainvoke([
        SystemMessage(content=KG_QUERY_SYSTEM),
        HumanMessage(content=query),
    ])

    try:
        parsed = json.loads(response.content)
        entity_names = parsed.get("entities", [])
        query_type = parsed.get("query_type", "entity_lookup")
    except (json.JSONDecodeError, KeyError):
        logger.warning("kg_query_parse_failed", raw=response.content[:200])
        return {"route": "hybrid_rag", "kg_cypher_result": [], "kg_entities": []}

    if not entity_names:
        return {"route": "hybrid_rag", "kg_cypher_result": [], "kg_entities": []}

    # Step 2: Search entities via fulltext index
    entity_query = " OR ".join(entity_names)
    entities = await repo.execute_read(
        """
        CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
        YIELD node AS entity, score
        WHERE score > 0.5
          AND ($max_chapter IS NULL
               OR NOT exists(entity.valid_from_chapter)
               OR entity.valid_from_chapter <= $max_chapter)
        RETURN entity.name AS name,
               labels(entity)[0] AS label,
               entity.description AS description,
               score
        ORDER BY score DESC
        LIMIT 10
        """,
        {"query": entity_query, "max_chapter": max_chapter},
    )

    if not entities:
        logger.info("kg_query_no_entities_found", query=query)
        return {"route": "hybrid_rag", "kg_cypher_result": [], "kg_entities": []}

    # Step 3: Expand relationships for found entities
    entity_names_found = [e["name"] for e in entities]
    relationships = await repo.execute_read(
        """
        UNWIND $names AS ename
        MATCH (entity {name: ename})-[r]->(related)
        WHERE NOT related:Chunk AND NOT related:Chapter AND NOT related:Book
          AND type(r) <> 'MENTIONED_IN' AND type(r) <> 'GROUNDED_IN'
          AND ($max_chapter IS NULL
               OR NOT exists(r.valid_from_chapter)
               OR r.valid_from_chapter <= $max_chapter)
        RETURN entity.name AS source,
               type(r) AS rel_type,
               related.name AS target_name,
               labels(related)[0] AS target_label
        LIMIT 30
        """,
        {"names": entity_names_found, "max_chapter": max_chapter},
    )

    # Step 4: Fetch grounded chunks
    chunks = await repo.execute_read(
        """
        UNWIND $names AS ename
        MATCH (entity {name: ename})-[:GROUNDED_IN|MENTIONED_IN]->(chunk:Chunk)
              <-[:HAS_CHUNK]-(chap:Chapter)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN DISTINCT elementId(chunk) AS node_id,
               chunk.text AS text,
               chap.number AS chapter_number,
               chap.title AS chapter_title
        ORDER BY chap.number
        LIMIT 10
        """,
        {"names": entity_names_found, "book_id": book_id, "max_chapter": max_chapter},
    )

    logger.info(
        "kg_query_completed",
        entities_found=len(entities),
        relationships_found=len(relationships),
        chunks_found=len(chunks),
        query_type=query_type,
    )

    return {
        "kg_cypher_result": chunks,
        "kg_entities": [
            {**e, "relationships": [r for r in relationships if r["source"] == e["name"]]}
            for e in entities
        ],
        "reranked_chunks": chunks,
    }
