"""Context assembly node: builds LLM context from chunks + KG entities."""

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def assemble_context(
    state: dict[str, Any],
    *,
    repo,
) -> dict[str, Any]:
    """Build context string from reranked chunks and related KG entities."""
    chunks = state.get("reranked_chunks", [])
    book_id = state["book_id"]
    max_chapter = state.get("max_chapter")

    if not chunks:
        return {"context": "", "kg_entities": []}

    # Fetch related entities from chapters in the retrieved chunks
    chapter_numbers = list({c["chapter_number"] for c in chunks if "chapter_number" in c})

    entities: list[dict[str, Any]] = []
    if chapter_numbers:
        entities = await repo.execute_read(
            """
            MATCH (entity)-[:GROUNDED_IN|MENTIONED_IN]->(chunk:Chunk)
                  <-[:HAS_CHUNK]-(chap:Chapter)
            WHERE chap.book_id = $book_id AND chap.number IN $chapters
              AND NOT entity:Chunk AND NOT entity:Book AND NOT entity:Chapter
              AND ($max_chapter IS NULL
                   OR NOT exists(entity.valid_from_chapter)
                   OR entity.valid_from_chapter <= $max_chapter)
            RETURN DISTINCT entity.name AS name,
                   labels(entity)[0] AS label,
                   entity.description AS description
            ORDER BY label, name
            LIMIT 30
            """,
            {"book_id": book_id, "chapters": chapter_numbers, "max_chapter": max_chapter},
        )

    # Use pre-fetched KG entities if available (from kg_query path)
    kg_entities = state.get("kg_entities", []) or [
        {"name": e["name"], "label": e["label"], "description": e.get("description", "")}
        for e in entities
        if e.get("name")
    ]

    # Build context string
    parts: list[str] = []

    parts.append("## Source Passages\n")
    for i, chunk in enumerate(chunks, 1):
        chapter = chunk.get("chapter_number", "?")
        title = chunk.get("chapter_title", "")
        header = f"Chapter {chapter}"
        if title:
            header += f" — {title}"
        score = chunk.get("relevance_score", 0.0)
        parts.append(f"### [{i}] {header} (relevance: {score:.2f})")
        parts.append(chunk.get("text", ""))
        parts.append("")

    if kg_entities:
        parts.append("\n## Related Knowledge Graph Entities\n")
        for e in kg_entities:
            desc = f": {e.get('description', '')}" if e.get("description") else ""
            name = e.get("name", "Unknown")
            label = e.get("label", "Entity")
            rels = e.get("relationships", [])
            parts.append(f"- **{name}** ({label}){desc}")
            for r in rels[:5]:
                rel_type = r.get("rel_type", "?")
                target = r.get("target_name", "?")
                t_label = r.get("target_label", "?")
                parts.append(f"  - {rel_type} → {target} ({t_label})")

    # Community context: thematic summaries from entity communities
    community_context = state.get("community_context", [])
    if community_context:
        parts.append("\n## Community Context\n")
        seen_summaries: set[str] = set()
        for cc in community_context:
            summary = cc.get("community_summary") or ""
            if not summary or summary in seen_summaries:
                continue
            seen_summaries.add(summary)
            entity_name = cc.get("entity_name", "")
            themes = cc.get("key_themes") or []
            theme_str = f" (themes: {', '.join(themes)})" if themes else ""
            parts.append(f"- {entity_name} belongs to a community: {summary}{theme_str}")
            theme_summary = cc.get("theme_summary")
            if theme_summary:
                parts.append(f"  - Broader theme: {theme_summary}")

    # Relationship context: semantically similar relationships from embedding search
    relationship_context = state.get("relationship_context", [])
    if relationship_context:
        parts.append("\n## Related Knowledge\n")
        for rc in relationship_context:
            source = rc.get("source") or "?"
            target = rc.get("target") or "?"
            rel_type = rc.get("rel_type") or "RELATED"
            context_text = rc.get("context") or ""
            score = rc.get("score", 0.0)
            line = f"- {source} {rel_type} {target}"
            if context_text:
                line += f": {context_text}"
            line += f" (relevance: {score:.2f})"
            parts.append(line)

    # GOLEM-specific context (psychological states, social evolution, stoff comparison)
    golem_context = state.get("golem_context", [])
    if golem_context:
        route = state.get("route", "")
        if route == "psychological_qa" or any("state_type" in gc for gc in golem_context):
            parts.append("\n## Psychological States\n")
            for gc in golem_context:
                line = f"- Ch.{gc.get('chapter', '?')}: {gc.get('character', '?')} — {gc.get('state_name', '?')} ({gc.get('state_type', '')})"
                if gc.get("intensity"):
                    line += f" [intensity: {gc['intensity']:.1f}]"
                if gc.get("trigger_event"):
                    line += f" triggered by: {gc['trigger_event']}"
                if gc.get("description"):
                    line += f" — {gc['description']}"
                parts.append(line)
        elif any("relationship_type" in gc for gc in golem_context):
            parts.append("\n## Relationship Evolution\n")
            for gc in golem_context:
                line = f"- {gc.get('relationship_name', '?')} ({gc.get('relationship_type', '')})"
                line += f" ch.{gc.get('from_chapter', '?')}"
                if gc.get("to_chapter"):
                    line += f"–{gc['to_chapter']}"
                if gc.get("description"):
                    line += f": {gc['description']}"
                parts.append(line)
        elif any("features" in gc for gc in golem_context):
            parts.append("\n## Character Across Books\n")
            for gc in golem_context:
                line = f"- Book {gc.get('book_id', '?')}: features={gc.get('features', [])}, roles={gc.get('roles', [])}"
                parts.append(line)

    context = "\n".join(parts)

    # Token budget enforcement (§6sexies.4)
    max_context_chars = 12_000  # ~8000 tokens
    if len(context) > max_context_chars:
        context = context[:max_context_chars]
        logger.warning(
            "context_truncated", original_len=len("\n".join(parts)), max_chars=max_context_chars
        )

    logger.info(
        "context_assembled",
        chunks=len(chunks),
        entities=len(kg_entities),
        communities=len(community_context),
        relationships=len(relationship_context),
        golem_context=len(golem_context),
        context_len=len(context),
    )

    return {"context": context, "kg_entities": kg_entities}
