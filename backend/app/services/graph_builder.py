"""Graph builder service — Extract, reconcile, and persist to Neo4j.

Orchestrates the full pipeline for a single chapter:
  1. Check cost ceiling
  2. Run LangGraph extraction (4 passes + reconcile)
  3. Apply alias map to normalize entity names
  4. Persist to Neo4j via EntityRepository
  5. Update chapter status

This is the main entry point called by the book processing pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.exceptions import CostCeilingError
from app.core.logging import get_logger
from app.repositories.entity_repo import EntityRepository
from app.services.extraction import extract_chapter

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from app.core.cost_tracker import CostTracker
    from app.core.dead_letter import DeadLetterQueue
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
    cost_tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """Process a single chapter through the full KG pipeline.

    Pipeline: Check cost ceiling -> Extract -> Reconcile -> Persist to Neo4j.

    Args:
        driver: Neo4j async driver.
        book_repo: Book repository for status updates.
        book_id: Book identifier.
        chapter: Chapter data with text.
        genre: Book genre.
        series_name: Series name.
        regex_matches_json: Pre-extracted regex matches.
        cost_tracker: Optional cost tracker for ceiling enforcement.

    Returns:
        Dict with processing stats.

    Raises:
        CostCeilingError: If chapter or book cost ceiling is exceeded.
    """
    chapter_number = chapter.number

    # 0. Check cost ceilings before spending LLM tokens
    if cost_tracker is not None:
        if not cost_tracker.check_book_ceiling(book_id):
            raise CostCeilingError(
                f"Book cost ceiling exceeded for {book_id!r} "
                f"(${cost_tracker.cost_for_book(book_id):.2f} >= "
                f"${cost_tracker.ceiling_per_book:.2f})",
                context={"book_id": book_id, "chapter": chapter_number},
            )
        if not cost_tracker.check_chapter_ceiling(book_id, chapter_number):
            raise CostCeilingError(
                f"Chapter cost ceiling exceeded for {book_id!r} ch.{chapter_number} "
                f"(${cost_tracker.cost_for_chapter(book_id, chapter_number):.2f} >= "
                f"${cost_tracker.ceiling_per_chapter:.2f})",
                context={"book_id": book_id, "chapter": chapter_number},
            )

    logger.info(
        "graph_build_chapter_started",
        book_id=book_id,
        chapter=chapter_number,
        text_length=len(chapter.text),
    )

    # 1. Extract + reconcile entities via LangGraph
    #    (graph includes: route → [passes 1-4] → merge → reconcile)
    extraction_result = await extract_chapter(
        chapter_text=chapter.text,
        book_id=book_id,
        chapter_number=chapter_number,
        genre=genre,
        series_name=series_name,
        regex_matches_json=regex_matches_json,
    )

    # 2. Apply alias map to normalize names (alias_map from graph reconcile step)
    _apply_alias_map(extraction_result, extraction_result.alias_map)

    # 3. Persist to Neo4j
    entity_repo = EntityRepository(driver)
    counts = await entity_repo.upsert_extraction_result(extraction_result)

    # 4. Update chapter status
    await book_repo.update_chapter_status(
        book_id,
        chapter_number,
        "extracted",
    )

    stats = {
        "chapter_number": chapter_number,
        "total_entities": extraction_result.total_entities,
        "passes_completed": extraction_result.passes_completed,
        "aliases_resolved": len(extraction_result.alias_map),
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
    dlq: DeadLetterQueue | None = None,
    cost_tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """Process all chapters of a book through the KG pipeline.

    Iterates through chapters sequentially (to respect narrative order).
    Checks cost ceilings before each chapter and aborts the book if
    the book-level ceiling is exceeded.

    Args:
        driver: Neo4j async driver.
        book_repo: Book repository.
        book_id: Book identifier.
        chapters: List of chapter data.
        genre: Book genre.
        series_name: Series name.
        chapter_regex_matches: Mapping of chapter_number -> regex JSON.
        dlq: Optional dead letter queue for failed chapters.
        cost_tracker: Optional cost tracker for ceiling enforcement.

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

    cost_ceiling_hit = False

    for chapter in chapters:
        try:
            regex_json = chapter_regex_matches.get(
                chapter.number,
                "[]",
            )

            stats = await build_chapter_graph(
                driver=driver,
                book_repo=book_repo,
                book_id=book_id,
                chapter=chapter,
                genre=genre,
                series_name=series_name,
                regex_matches_json=regex_json,
                cost_tracker=cost_tracker,
            )

            total_entities += stats["total_entities"]
            chapter_stats.append(stats)

        except CostCeilingError:
            # Book-level ceiling hit — stop processing remaining chapters
            logger.warning(
                "graph_build_book_ceiling_hit",
                book_id=book_id,
                chapter=chapter.number,
                chapters_processed=len(chapter_stats),
                chapters_remaining=len(chapters) - len(chapter_stats) - len(failed_chapters),
            )
            cost_ceiling_hit = True
            break

        except Exception as exc:
            logger.exception(
                "graph_build_chapter_failed",
                book_id=book_id,
                chapter=chapter.number,
            )
            failed_chapters.append(chapter.number)
            if dlq is not None:
                await dlq.push_failure(
                    book_id=book_id,
                    chapter=chapter.number,
                    error=exc,
                    metadata={"genre": genre, "series_name": series_name},
                )

    # Update final status
    if cost_ceiling_hit:
        final_status = "cost_ceiling_hit"
    elif failed_chapters:
        final_status = "partial"
    else:
        final_status = "extracted"
    await book_repo.update_book_status(book_id, final_status)

    result = {
        "book_id": book_id,
        "chapters_processed": len(chapter_stats),
        "chapters_failed": len(failed_chapters),
        "failed_chapters": failed_chapters,
        "total_entities": total_entities,
        "status": final_status,
        "cost_ceiling_hit": cost_ceiling_hit,
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
                char.canonical_name,
                char.canonical_name,
            )

    # Normalize relationship references
    for rel in result.characters.relationships:
        rel.source = alias_map.get(rel.source, rel.source)
        rel.target = alias_map.get(rel.target, rel.target)

    # Normalize system entity names and owners
    for skill in result.systems.skills:
        skill.name = alias_map.get(skill.name, skill.name)
        skill.owner = alias_map.get(skill.owner, skill.owner)
    for cls in result.systems.classes:
        cls.name = alias_map.get(cls.name, cls.name)
        cls.owner = alias_map.get(cls.owner, cls.owner)
    for title in result.systems.titles:
        title.name = alias_map.get(title.name, title.name)
        title.owner = alias_map.get(title.owner, title.owner)
    for level in result.systems.level_changes:
        level.character = alias_map.get(
            level.character,
            level.character,
        )
    for stat in result.systems.stat_changes:
        stat.character = alias_map.get(stat.character, stat.character)

    # Normalize event participants and names
    for event in result.events.events:
        event.name = alias_map.get(event.name, event.name)
        event.participants = [alias_map.get(p, p) for p in event.participants]
        event.location = alias_map.get(event.location, event.location)

    # Normalize lore entity names
    for location in result.lore.locations:
        location.name = alias_map.get(location.name, location.name)
        location.parent_location = alias_map.get(
            location.parent_location,
            location.parent_location,
        )

    for item in result.lore.items:
        item.name = alias_map.get(item.name, item.name)
        item.owner = alias_map.get(item.owner, item.owner)

    for creature in result.lore.creatures:
        creature.name = alias_map.get(creature.name, creature.name)

    for faction in result.lore.factions:
        faction.name = alias_map.get(faction.name, faction.name)

    for concept in result.lore.concepts:
        concept.name = alias_map.get(concept.name, concept.name)
