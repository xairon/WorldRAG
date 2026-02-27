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

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.core.exceptions import CostCeilingError
from app.core.logging import get_logger
from app.repositories.entity_repo import EntityRepository
from app.services.entity_filter import filter_extraction_result
from app.services.extraction import extract_chapter

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from app.core.cost_tracker import CostTracker
    from app.core.dead_letter import DeadLetterQueue
    from app.repositories.book_repo import BookRepository
    from app.schemas.book import ChapterData
    from app.schemas.extraction import ChapterExtractionResult

# Progress callback: (chapter_number, total, status, entities) -> None
ProgressCallback = Callable[[int, int, str, int], Awaitable[None]]

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
    series_entities: list[dict[str, Any]] | None = None,
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
        series_entities: Known entities from other books in the same series
            (for cross-book entity resolution).

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
        series_entities=series_entities,
    )

    # 2. Log extraction warnings
    if extraction_result.total_entities == 0 and extraction_result.passes_completed:
        logger.warning(
            "graph_build_chapter_zero_entities",
            book_id=book_id,
            chapter=chapter_number,
            passes_completed=extraction_result.passes_completed,
        )

    # 3. Apply alias map to normalize names (alias_map from graph reconcile step)
    _apply_alias_map(extraction_result, extraction_result.alias_map)

    # 4. Apply entity quality filters (reject pronouns, generics, noise)
    filter_extraction_result(extraction_result)

    # 5. Persist to Neo4j
    entity_repo = EntityRepository(driver)
    counts = await entity_repo.upsert_extraction_result(extraction_result)

    # 5b. V3: BlueBox grouping
    try:
        from app.services.extraction.bluebox import group_blue_boxes

        paragraphs = await book_repo.get_paragraphs(book_id, chapter_number)
        if paragraphs:
            blue_boxes = group_blue_boxes(paragraphs)
            if blue_boxes:
                bb_count = await entity_repo.upsert_blue_boxes(
                    book_id, chapter_number, blue_boxes, str(uuid.uuid4())
                )
                counts["blue_boxes"] = bb_count
    except Exception:
        logger.warning(
            "bluebox_grouping_failed",
            book_id=book_id,
            chapter=chapter_number,
            exc_info=True,
        )

    # 5c. V3: Provenance extraction (only if skills were found)
    if extraction_result.systems.skills:
        try:
            from app.services.extraction.provenance import extract_provenance

            skills_acquired = [s.name for s in extraction_result.systems.skills]
            chapter_entities = {
                "items": [i.name for i in extraction_result.lore.items],
                "classes": [c.name for c in extraction_result.systems.classes],
                "bloodlines": [],
            }
            prov_result = await extract_provenance(chapter.text, skills_acquired, chapter_entities)
            if prov_result.provenances:
                grants_count = await entity_repo.upsert_grants_relations(
                    prov_result.provenances, str(uuid.uuid4())
                )
                counts["grants"] = grants_count
        except Exception:
            logger.warning(
                "provenance_extraction_failed",
                book_id=book_id,
                chapter=chapter_number,
                exc_info=True,
            )

    # 6. Update chapter status
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
    on_chapter_done: ProgressCallback | None = None,
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

    # ── Filter out non-content chapters (Sommaire, TOC, copyright) ───
    content_chapters = [ch for ch in chapters if not _is_non_content_chapter(ch)]
    skipped = len(chapters) - len(content_chapters)
    if skipped:
        logger.info(
            "graph_build_chapters_skipped",
            book_id=book_id,
            skipped=skipped,
            reason="non-content (Sommaire/TOC/copyright)",
        )

    # ── Load cross-book series entities for dedup ──────────────────
    series_entities: list[dict[str, Any]] = []
    if series_name:
        try:
            entity_repo = EntityRepository(driver)
            series_entities = await entity_repo.get_series_entities(
                series_name,
                exclude_book_id=book_id,
            )
            logger.info(
                "series_entities_loaded_for_book",
                book_id=book_id,
                series_name=series_name,
                series_entity_count=len(series_entities),
            )
        except Exception:
            logger.warning(
                "series_entities_load_failed",
                book_id=book_id,
                series_name=series_name,
                exc_info=True,
            )

    logger.info(
        "graph_build_book_started",
        book_id=book_id,
        total_chapters=len(content_chapters),
        skipped_chapters=skipped,
    )

    await book_repo.update_book_status(book_id, "extracting")

    total_entities = 0
    chapter_stats: list[dict[str, Any]] = []
    failed_chapters: list[int] = []
    cost_ceiling_hit = False

    # ── Parallel chapter processing with semaphore ─────────────────
    # Process up to 3 chapters concurrently to balance throughput
    # with LLM rate limits. Results are collected per-chapter.
    sem = asyncio.Semaphore(3)

    total_chapters = len(content_chapters)

    async def _process_one(
        chapter: ChapterData,
    ) -> tuple[int, dict[str, Any] | None, Exception | None]:
        """Process a single chapter under semaphore control."""
        async with sem:
            regex_json = chapter_regex_matches.get(chapter.number, "[]")
            try:
                stats = await build_chapter_graph(
                    driver=driver,
                    book_repo=book_repo,
                    book_id=book_id,
                    chapter=chapter,
                    genre=genre,
                    series_name=series_name,
                    regex_matches_json=regex_json,
                    cost_tracker=cost_tracker,
                    series_entities=series_entities,
                )
                if on_chapter_done:
                    await on_chapter_done(
                        chapter.number,
                        total_chapters,
                        "extracted",
                        stats["total_entities"],
                    )
                return (chapter.number, stats, None)
            except Exception as exc:
                if on_chapter_done:
                    await on_chapter_done(chapter.number, total_chapters, "failed", 0)
                return (chapter.number, None, exc)

    tasks = [_process_one(ch) for ch in content_chapters]
    results_raw = await asyncio.gather(*tasks)

    # Collect results in chapter order
    for chapter_number, stats, exc in sorted(results_raw, key=lambda r: r[0]):
        if stats is not None:
            total_entities += stats["total_entities"]
            chapter_stats.append(stats)
        elif isinstance(exc, CostCeilingError):
            logger.warning(
                "graph_build_book_ceiling_hit",
                book_id=book_id,
                chapter=chapter_number,
                chapters_processed=len(chapter_stats),
            )
            cost_ceiling_hit = True
        elif exc is not None:
            logger.exception(
                "graph_build_chapter_failed",
                book_id=book_id,
                chapter=chapter_number,
            )
            failed_chapters.append(chapter_number)
            if dlq is not None:
                await dlq.push_failure(
                    book_id=book_id,
                    chapter=chapter_number,
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


_NON_CONTENT_TITLES = {
    "sommaire",
    "table des matières",
    "table of contents",
    "couverture",
    "cover",
    "copyright",
    "mentions légales",
    "colophon",
    "dédicace",
    "dedication",
    "remerciements",
    "acknowledgements",
    "préface",
    "preface",
    "avant-propos",
}


def _is_non_content_chapter(chapter: ChapterData) -> bool:
    """Detect non-content chapters (TOC, copyright, etc.) to skip extraction.

    Heuristics:
    1. Title matches known non-content titles (Sommaire, Copyright, etc.)
    2. Text is mostly a list of chapter titles (TOC pattern)
    """
    title_lower = (chapter.title or "").strip().lower()

    # Check title against known non-content titles
    if title_lower in _NON_CONTENT_TITLES:
        return True

    # Check if text is mostly chapter listing (TOC heuristic):
    # If > 40% of lines start with "Chapitre" or "Chapter", it's a TOC
    lines = [ln.strip() for ln in chapter.text.split("\n") if ln.strip()]
    if len(lines) > 5:
        chapter_lines = sum(1 for ln in lines if ln.lower().startswith(("chapitre", "chapter")))
        if chapter_lines / len(lines) > 0.4:
            return True

    return False


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


async def _persist_extraction_result(
    entity_repo: EntityRepository,
    book_id: str,
    chapter_number: int,
    result: ChapterExtractionResult,
    batch_id: str,
) -> dict[str, int]:
    """Persist all entity types from extraction result to Neo4j.

    Mirrors the persistence pattern from upsert_extraction_result but
    called from build_chapter_graph_v3 with an explicit batch_id.
    """
    counts: dict[str, int] = {}

    # Phase 1: Characters + relationships (sequential — rels reference chars)
    counts["characters"] = await entity_repo.upsert_characters(
        book_id, chapter_number, result.characters.characters, batch_id,
    )
    counts["relationships"] = await entity_repo.upsert_relationships(
        book_id, chapter_number, result.characters.relationships, batch_id,
    )

    # Phase 2: All independent entity types in parallel
    (
        counts["skills"],
        counts["classes"],
        counts["titles"],
        counts["level_changes"],
        counts["stat_changes"],
        counts["events"],
        counts["locations"],
        counts["items"],
        counts["creatures"],
        counts["factions"],
        counts["concepts"],
    ) = await asyncio.gather(
        entity_repo.upsert_skills(
            book_id, chapter_number, result.systems.skills, batch_id,
        ),
        entity_repo.upsert_classes(
            book_id, chapter_number, result.systems.classes, batch_id,
        ),
        entity_repo.upsert_titles(
            book_id, chapter_number, result.systems.titles, batch_id,
        ),
        entity_repo.upsert_level_changes(
            book_id, chapter_number, result.systems.level_changes, batch_id,
        ),
        entity_repo.upsert_stat_changes(
            book_id, chapter_number, result.systems.stat_changes, batch_id,
        ),
        entity_repo.upsert_events(
            book_id, chapter_number, result.events.events, batch_id,
        ),
        entity_repo.upsert_locations(
            book_id, chapter_number, result.lore.locations, batch_id,
        ),
        entity_repo.upsert_items(
            book_id, chapter_number, result.lore.items, batch_id,
        ),
        entity_repo.upsert_creatures(
            book_id, chapter_number, result.lore.creatures, batch_id,
        ),
        entity_repo.upsert_factions(
            book_id, chapter_number, result.lore.factions, batch_id,
        ),
        entity_repo.upsert_concepts(
            book_id, chapter_number, result.lore.concepts, batch_id,
        ),
    )

    # Phase 3: Mentions (depends on entities existing)
    counts["mentions"] = await entity_repo.store_mentions(
        book_id, chapter_number, result.grounded_entities,
    )

    return counts


async def build_chapter_graph_v3(
    driver: AsyncDriver,
    book_repo: BookRepository,
    book_id: str,
    chapter: ChapterData,
    genre: str = "litrpg",
    series_name: str = "",
    regex_matches_json: str = "[]",
    cost_tracker: CostTracker | None = None,
    series_entities: list[dict[str, Any]] | None = None,
    entity_registry: dict | None = None,
    ontology_version: str = "3.0.0",
    source_language: str = "fr",
) -> dict[str, Any]:
    """V3: Extract and persist entities using the 6-phase pipeline.

    Like build_chapter_graph but with EntityRegistry lifecycle and
    ontology versioning.

    Args:
        driver: Neo4j async driver.
        book_repo: Book repository for status updates.
        book_id: Book identifier.
        chapter: Chapter data with text.
        genre: Book genre.
        series_name: Series name.
        regex_matches_json: Pre-extracted regex matches.
        cost_tracker: Optional cost tracker for ceiling enforcement.
        series_entities: Known entities from other books in the same series.
        entity_registry: Serialized EntityRegistry from previous chapters.
        ontology_version: Ontology version string for this extraction run.
        source_language: Source language of the text.

    Returns:
        Dict with processing stats.

    Raises:
        CostCeilingError: If chapter or book cost ceiling is exceeded.
    """
    from app.services.extraction import extract_chapter_v3

    chapter_number = chapter.number

    # 0. Check cost ceilings before spending LLM tokens
    if cost_tracker is not None:
        if not cost_tracker.check_book_ceiling(book_id):
            raise CostCeilingError(
                f"Book cost ceiling exceeded for {book_id!r}",
                context={"book_id": book_id, "chapter": chapter_number},
            )
        if not cost_tracker.check_chapter_ceiling(book_id, chapter_number):
            raise CostCeilingError(
                f"Chapter cost ceiling exceeded for {book_id!r} ch.{chapter_number}",
                context={"book_id": book_id, "chapter": chapter_number},
            )

    logger.info(
        "graph_build_chapter_v3_started",
        book_id=book_id,
        chapter=chapter_number,
        text_length=len(chapter.text),
        ontology_version=ontology_version,
    )

    # 1. Extract via V3 pipeline
    result = await extract_chapter_v3(
        chapter_text=chapter.text,
        chapter_number=chapter_number,
        book_id=book_id,
        genre=genre,
        series_name=series_name,
        regex_matches_json=regex_matches_json,
        entity_registry=entity_registry,
        ontology_version=ontology_version,
        source_language=source_language,
        series_entities=series_entities,
    )

    # 2. Apply alias map to normalize names
    if result.alias_map:
        _apply_alias_map(result, result.alias_map)

    # 3. Apply entity quality filters
    filter_extraction_result(result)

    # 4. Persist all entity types
    entity_repo = EntityRepository(driver)
    batch_id = str(uuid.uuid4())

    counts = await _persist_extraction_result(
        entity_repo, book_id, chapter_number, result, batch_id,
    )

    # 5. Update chapter status
    await book_repo.update_chapter_status(book_id, chapter_number, "extracted")

    stats: dict[str, Any] = {
        "chapter_number": chapter_number,
        "total_entities": result.count_entities(),
        "alias_map": result.alias_map,
        "batch_id": batch_id,
        "ontology_version": ontology_version,
        "neo4j_counts": counts,
    }

    logger.info(
        "graph_build_chapter_v3_completed",
        book_id=book_id,
        **{k: v for k, v in stats.items() if k != "alias_map"},
    )

    return stats
