"""Reader agent retrieve: fetch chapter paragraphs and entity annotations."""

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def retrieve_chapter_context(
    state: dict[str, Any],
    *,
    repo,
) -> dict[str, Any]:
    """Retrieve paragraphs and entity annotations for the current chapter."""
    book_id = state["book_id"]
    chapter_number = state["chapter_number"]
    max_chapter = state.get("max_chapter")

    # Fetch paragraphs for the chapter
    paragraphs = await repo.execute_read(
        """
        MATCH (c:Chapter {book_id: $book_id, number: $chapter_number})
              -[:HAS_PARAGRAPH]->(p:Paragraph)
        RETURN p.index AS index, p.type AS type, p.text AS text,
               p.char_start AS char_start, p.char_end AS char_end,
               p.speaker AS speaker
        ORDER BY p.index
        """,
        {"book_id": book_id, "chapter_number": chapter_number},
    )

    # Fetch entity annotations grounded in this chapter
    entities = await repo.execute_read(
        """
        MATCH (entity)-[m:MENTIONED_IN]->(c:Chapter {book_id: $book_id, number: $chapter_number})
        WHERE $max_chapter IS NULL
              OR NOT exists(entity.valid_from_chapter)
              OR entity.valid_from_chapter <= $max_chapter
        RETURN DISTINCT entity.name AS name,
               labels(entity) AS labels,
               entity.description AS description,
               m.char_start AS char_start,
               m.char_end AS char_end,
               m.mention_text AS mention_text
        ORDER BY m.char_start
        """,
        {"book_id": book_id, "chapter_number": chapter_number, "max_chapter": max_chapter},
    )

    # Build KG context string for entity_lookup route
    kg_lines = []
    for e in entities:
        label = next(
            (lbl for lbl in e.get("labels", []) if lbl not in ("Entity", "Node", "_Entity")),
            "Entity",
        )
        desc = e.get("description", "")
        kg_lines.append(f"{e['name']} ({label}): {desc}")

    logger.info(
        "reader_context_retrieved",
        chapter=chapter_number,
        paragraphs=len(paragraphs),
        entities=len(entities),
    )

    return {
        "paragraph_context": paragraphs,
        "entity_annotations": entities,
        "kg_context": "\n".join(kg_lines),
    }
