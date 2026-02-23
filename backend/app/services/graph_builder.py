"""Graph builder service — Extract, reconcile, and persist to Neo4j.

Orchestrates the full pipeline for a single chapter:
  1. Run LangGraph extraction (4 passes)
  2. Reconcile entities (dedup + alias resolution)
  3. Persist to Neo4j via EntityRepository
  4. Update chapter status

This is the main entry point called by the book processing pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.repositories.entity_repo import EntityRepository
from app.services.extraction import extract_chapter
from app.services.extraction.reconciler import reconcile_chapter_result

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from app.repositories.book_repo import BookRepository
    from app.schemas.book import ChapterData
    from app.schemas.extraction import ChapterExtractionResult

logger = get_logger(__name__)


async def build_chapter_graph(
    driver: AsyncDriver,
    book_repo: BookRepository,
    book_id: str,
    chapter: ChapterData,
    genre: str = "litrpg",
    series_name: str = "",
    regex_matches_json: str = "[]",
) -> dict[str, Any]:
    """Process a single chapter through the full KG pipeline.

    Pipeline: Extract -> Reconcile -> Persist to Neo4j.

    Args:
        driver: Neo4j async driver.
        book_repo: Book repository for status updates.
        book_id: Book identifier.
        chapter: Chapter data with text.
        genre: Book genre.
        series_name: Series name.
        regex_matches_json: Pre-extracted regex matches.

    Returns:
        Dict with processing stats.
    """
    chapter_number = chapter.number

    logger.info(
        "graph_build_chapter_started",
        book_id=book_id,
        chapter=chapter_number,
        text_length=len(chapter.text),
    )

    # 1. Extract entities via LangGraph
    extraction_result = await extract_chapter(
        chapter_text=chapter.text,
        book_id=book_id,
        chapter_number=chapter_number,
        genre=genre,
        series_name=series_name,
        regex_matches_json=regex_matches_json,
    )

    # 2. Reconcile (dedup + normalize)
    reconciliation = await reconcile_chapter_result(extraction_result)

    # 3. Apply alias map to normalize names
    _apply_alias_map(extraction_result, reconciliation.alias_map)

    # 4. Persist to Neo4j
    entity_repo = EntityRepository(driver)
    counts = await entity_repo.upsert_extraction_result(extraction_result)

    # 5. Update chapter status
    await book_repo.update_chapter_status(
        book_id, chapter_number, "extracted",
    )

    stats = {
        "chapter_number": chapter_number,
        "total_entities": extraction_result.total_entities,
        "passes_completed": extraction_result.passes_completed,
        "aliases_resolved": len(reconciliation.alias_map),
        "neo4j_counts": counts,
    }

    logger.info(
        "graph_build_chapter_completed",
        book_id=book_id,
        **stats,
    )

    return stats


async def build_book_graph(
    driver: AsyncDriver,
    book_repo: BookRepository,
    book_id: str,
    chapters: list[ChapterData],
    genre: str = "litrpg",
    series_name: str = "",
    chapter_regex_matches: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Process all chapters of a book through the KG pipeline.

    Iterates through chapters sequentially (to respect narrative order).

    Args:
        driver: Neo4j async driver.
        book_repo: Book repository.
        book_id: Book identifier.
        chapters: List of chapter data.
        genre: Book genre.
        series_name: Series name.
        chapter_regex_matches: Mapping of chapter_number -> regex JSON.

    Returns:
        Dict with aggregate processing stats.
    """
    if chapter_regex_matches is None:
        chapter_regex_matches = {}

    logger.info(
        "graph_build_book_started",
        book_id=book_id,
        total_chapters=len(chapters),
    )

    await book_repo.update_book_status(book_id, "extracting")

    total_entities = 0
    chapter_stats: list[dict[str, Any]] = []
    failed_chapters: list[int] = []

    for chapter in chapters:
        try:
            regex_json = chapter_regex_matches.get(
                chapter.number, "[]",
            )

            stats = await build_chapter_graph(
                driver=driver,
                book_repo=book_repo,
                book_id=book_id,
                chapter=chapter,
                genre=genre,
                series_name=series_name,
                regex_matches_json=regex_json,
            )

            total_entities += stats["total_entities"]
            chapter_stats.append(stats)

        except Exception as e:
            logger.exception(
                "graph_build_chapter_failed",
                book_id=book_id,
                chapter=chapter.number,
                error=str(e),
            )
            failed_chapters.append(chapter.number)

    # Update final status
    final_status = "extracted" if not failed_chapters else "partial"
    await book_repo.update_book_status(book_id, final_status)

    result = {
        "book_id": book_id,
        "chapters_processed": len(chapter_stats),
        "chapters_failed": len(failed_chapters),
        "failed_chapters": failed_chapters,
        "total_entities": total_entities,
        "status": final_status,
    }

    logger.info("graph_build_book_completed", **result)

    return result


def _apply_alias_map(
    result: ChapterExtractionResult,
    alias_map: dict[str, str],
) -> None:
    """Apply alias map to normalize entity names in-place."""
    if not alias_map:
        return

    # Normalize character names
    for char in result.characters.characters:
        char.name = alias_map.get(char.name, char.name)
        if char.canonical_name:
            char.canonical_name = alias_map.get(
                char.canonical_name, char.canonical_name,
            )

    # Normalize relationship references
    for rel in result.characters.relationships:
        rel.source = alias_map.get(rel.source, rel.source)
        rel.target = alias_map.get(rel.target, rel.target)

    # Normalize system owners
    for skill in result.systems.skills:
        skill.owner = alias_map.get(skill.owner, skill.owner)
    for cls in result.systems.classes:
        cls.owner = alias_map.get(cls.owner, cls.owner)
    for title in result.systems.titles:
        title.owner = alias_map.get(title.owner, title.owner)
    for level in result.systems.level_changes:
        level.character = alias_map.get(
            level.character, level.character,
        )

    # Normalize event participants
    for event in result.events.events:
        event.participants = [
            alias_map.get(p, p) for p in event.participants
        ]

    # Normalize item owners
    for item in result.lore.items:
        item.owner = alias_map.get(item.owner, item.owner)
