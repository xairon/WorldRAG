"""arq task functions for WorldRAG background processing.

Each task receives a `ctx` dict populated by worker startup with:
  - ctx["neo4j_driver"]: AsyncDriver
  - ctx["cost_tracker"]: CostTracker
  - ctx["dlq"]: DeadLetterQueue
  - ctx["dlq_redis"]: Redis (plain, for DLQ)
  - ctx["redis"]: ArqRedis (arq's own pool, for enqueuing)

Tasks use arq's built-in job chaining via ctx["redis"].enqueue_job().
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.repositories.book_repo import BookRepository

logger = get_logger(__name__)

ARQ_QUEUE = "worldrag:arq"


async def process_book_extraction(
    ctx: dict[str, Any],
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    chapters: list[int] | None = None,
) -> dict[str, Any]:
    """Run the full KG extraction pipeline for a book.

    Called by the arq worker after a job is enqueued from
    POST /books/{book_id}/extract.

    If *chapters* is provided, only those chapter numbers are processed.
    Pass ``None`` to extract all chapters.

    On success: enqueues process_book_embeddings automatically.
    On chapter failure: pushes to DLQ (individual chapters).
    On total failure: raises to let arq mark job as failed.
    """
    from app.config import settings

    if settings.use_v3_pipeline:
        # Delegate to V3 pipeline
        return await process_book_extraction_v3(
            ctx,
            book_id,
            genre,
            series_name,
            chapters,
            settings.extraction_language,
        )

    driver = ctx["neo4j_driver"]
    dlq = ctx["dlq"]
    cost_tracker = ctx.get("cost_tracker")

    logger.info(
        "task_book_extraction_started",
        book_id=book_id,
        genre=genre,
        chapters=chapters,
    )

    book_repo = BookRepository(driver)
    book = await book_repo.get_book(book_id)
    if not book:
        msg = f"Book {book_id!r} not found"
        raise ValueError(msg)

    chapter_data = await book_repo.get_chapters_for_extraction(
        book_id,
        chapters=chapters,
    )
    if not chapter_data:
        msg = f"No chapters found for book {book_id!r}"
        raise ValueError(msg)

    chapter_regex = await book_repo.get_chapter_regex_json(book_id)
    # Filter regex matches to requested chapters
    if chapters is not None:
        chapter_set = set(chapters)
        chapter_regex = {k: v for k, v in chapter_regex.items() if k in chapter_set}

    # Import here to avoid circular import at module load
    from app.services.graph_builder import build_book_graph

    # Progress callback: publish to Redis pub/sub for SSE consumers
    dlq_redis = ctx.get("dlq_redis")

    async def _publish_progress(chapter: int, total: int, status: str, entities: int) -> None:
        if dlq_redis is not None:
            import json

            await dlq_redis.publish(
                f"worldrag:progress:{book_id}",
                json.dumps(
                    {
                        "chapter": chapter,
                        "total": total,
                        "status": status,
                        "entities_found": entities,
                    }
                ),
            )

    result = await build_book_graph(
        driver=driver,
        book_repo=book_repo,
        book_id=book_id,
        chapters=chapter_data,
        genre=genre,
        series_name=series_name,
        chapter_regex_matches=chapter_regex,
        dlq=dlq,
        cost_tracker=cost_tracker,
        on_chapter_done=_publish_progress,
    )

    logger.info(
        "task_book_extraction_completed",
        book_id=book_id,
        chapters_processed=result["chapters_processed"],
        chapters_failed=result["chapters_failed"],
        total_entities=result["total_entities"],
    )

    # Auto-enqueue embedding job after extraction
    # ctx["redis"] is arq's ArqRedis pool (set by arq automatically)
    await ctx["redis"].enqueue_job(
        "process_book_embeddings",
        book_id,
        _queue_name=ARQ_QUEUE,
        _job_id=f"embed:{book_id}",
    )
    logger.info("task_embeddings_enqueued", book_id=book_id)

    return result


async def process_book_extraction_v3(
    ctx: dict[str, Any],
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    chapters: list[int] | None = None,
    language: str = "fr",
) -> dict[str, Any]:
    """Run the V3 6-phase extraction pipeline for a book.

    Unlike process_book_extraction, this:
    - Uses build_chapter_graph_v3 per chapter (sequential, not parallel)
    - Maintains an EntityRegistry that grows across chapters
    - Loads cross-book registries from previous books in the series
    - Saves the registry to Neo4j after each chapter
    - Logs with ontology_version

    On success: enqueues process_book_embeddings automatically.
    On chapter failure: pushes to DLQ (individual chapters).
    """
    driver = ctx["neo4j_driver"]
    dlq = ctx["dlq"]
    cost_tracker = ctx.get("cost_tracker")

    from app.config import settings

    ontology_version = settings.ontology_version
    if not language:
        language = settings.extraction_language

    logger.info(
        "task_book_extraction_v3_started",
        book_id=book_id,
        genre=genre,
        series_name=series_name,
        chapters=chapters,
        language=language,
        ontology_version=ontology_version,
    )

    book_repo = BookRepository(driver)
    book = await book_repo.get_book(book_id)
    if not book:
        msg = f"Book {book_id!r} not found"
        raise ValueError(msg)

    chapter_data = await book_repo.get_chapters_for_extraction(
        book_id,
        chapters=chapters,
    )
    if not chapter_data:
        msg = f"No chapters found for book {book_id!r}"
        raise ValueError(msg)

    chapter_regex = await book_repo.get_chapter_regex_json(book_id)
    if chapters is not None:
        chapter_set = set(chapters)
        chapter_regex = {k: v for k, v in chapter_regex.items() if k in chapter_set}

    # Import here to avoid circular import at module load
    from app.services.graph_builder import build_chapter_graph_v3, _is_non_content_chapter
    from app.services.extraction.entity_registry import EntityRegistry
    from app.core.exceptions import CostCeilingError

    # Initialize entity registry
    entity_registry = EntityRegistry()

    # Load entity registries from other books in same series
    if series_name:
        try:
            series_books = await book_repo.get_series_book_ids(series_name, exclude=book_id)
            for prev_book_id in series_books:
                prev_data = await book_repo.load_entity_registry(prev_book_id)
                if prev_data:
                    prev_reg = EntityRegistry.from_dict(prev_data)
                    entity_registry = EntityRegistry.merge(entity_registry, prev_reg)
            if series_books:
                logger.info(
                    "v3_cross_book_registry_loaded",
                    book_id=book_id,
                    series_name=series_name,
                    series_books_count=len(series_books),
                    registry_entity_count=entity_registry.entity_count,
                )
        except Exception:
            logger.warning(
                "v3_cross_book_registry_load_failed",
                book_id=book_id,
                series_name=series_name,
                exc_info=True,
            )

    # Filter non-content chapters
    content_chapters = [ch for ch in chapter_data if not _is_non_content_chapter(ch)]
    skipped = len(chapter_data) - len(content_chapters)
    if skipped:
        logger.info(
            "v3_chapters_skipped",
            book_id=book_id,
            skipped=skipped,
            reason="non-content (Sommaire/TOC/copyright)",
        )

    # Progress callback: publish to Redis pub/sub for SSE consumers
    dlq_redis = ctx.get("dlq_redis")

    async def _publish_progress(chapter: int, total: int, status: str, entities: int) -> None:
        if dlq_redis is not None:
            import json

            await dlq_redis.publish(
                f"worldrag:progress:{book_id}",
                json.dumps(
                    {
                        "chapter": chapter,
                        "total": total,
                        "status": status,
                        "entities_found": entities,
                        "pipeline": "v3",
                    }
                ),
            )

    await book_repo.update_book_status(book_id, "extracting")

    total_entities = 0
    failed_chapters: list[int] = []
    chapter_stats: list[dict[str, Any]] = []
    cost_ceiling_hit = False

    # Process chapters SEQUENTIALLY (narrative order matters for EntityRegistry)
    for idx, chapter in enumerate(content_chapters):
        regex_json = chapter_regex.get(chapter.number, "[]")
        try:
            stats = await build_chapter_graph_v3(
                driver=driver,
                book_repo=book_repo,
                book_id=book_id,
                chapter=chapter,
                genre=genre,
                series_name=series_name,
                regex_matches_json=regex_json,
                cost_tracker=cost_tracker,
                entity_registry=entity_registry.to_dict(),
                ontology_version=ontology_version,
                source_language=language,
            )
            total_entities += stats.get("total_entities", 0)
            chapter_stats.append(stats)

            # Update registry with new entities from this chapter's alias_map
            for old_name, new_name in (stats.get("alias_map") or {}).items():
                entity_registry.add(new_name, "Unknown")

            # Save registry after each chapter
            await book_repo.save_entity_registry(
                book_id, entity_registry.to_dict(), ontology_version,
            )

            await _publish_progress(
                chapter.number, len(content_chapters), "extracted", stats.get("total_entities", 0),
            )

        except CostCeilingError:
            logger.warning(
                "v3_cost_ceiling_hit",
                book_id=book_id,
                chapter=chapter.number,
                chapters_processed=len(chapter_stats),
            )
            cost_ceiling_hit = True
            break
        except Exception as exc:
            logger.exception(
                "v3_chapter_failed",
                book_id=book_id,
                chapter=chapter.number,
            )
            failed_chapters.append(chapter.number)
            if dlq:
                await dlq.push_failure(
                    book_id=book_id,
                    chapter=chapter.number,
                    error=exc,
                    metadata={"genre": genre, "pipeline": "v3"},
                )
            await _publish_progress(chapter.number, len(content_chapters), "failed", 0)

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
        "ontology_version": ontology_version,
        "pipeline": "v3",
    }

    logger.info("task_book_extraction_v3_completed", **result)

    # Auto-enqueue embedding job after extraction
    await ctx["redis"].enqueue_job(
        "process_book_embeddings",
        book_id,
        _queue_name=ARQ_QUEUE,
        _job_id=f"embed:{book_id}",
    )
    logger.info("task_embeddings_enqueued", book_id=book_id, pipeline="v3")

    return result


async def process_book_reprocessing(
    ctx: dict[str, Any],
    book_id: str,
    chapter_range: list[int] | None = None,
    changes_raw: list[dict] | None = None,
    genre: str = "litrpg",
    series_name: str = "",
) -> dict[str, Any]:
    """Selective reprocessing after ontology evolution.

    Analyzes ontology changes to determine which chapters and phases
    need re-extraction, then runs only those.

    If chapter_range is provided, only those chapters are reprocessed.
    If changes_raw is provided, auto-detects affected chapters.
    If neither, reprocesses all chapters.
    """
    driver = ctx["neo4j_driver"]

    from app.schemas.ontology import OntologyChange
    from app.services.reprocessing import (
        compute_impact_scope,
        reextract_chapters,
        scan_chapters_for_impact,
    )

    # Parse changes if provided
    changes: list[OntologyChange] = []
    if changes_raw:
        for c in changes_raw:
            changes.append(OntologyChange(**c))

    # Compute impact scope
    scope = compute_impact_scope(changes)

    # Determine chapters to reprocess
    if chapter_range:
        chapters_to_process = chapter_range
    elif changes:
        chapters_to_process = await scan_chapters_for_impact(book_id, scope, driver)
    else:
        # No specific guidance -> reprocess all
        book_repo = BookRepository(driver)
        all_chapters = await book_repo.get_chapters_for_extraction(book_id)
        chapters_to_process = [ch.number for ch in all_chapters]

    logger.info(
        "reprocessing_started",
        book_id=book_id,
        chapters=chapters_to_process,
        affected_phases=scope.affected_phases,
    )

    result = await reextract_chapters(
        book_id=book_id,
        chapter_numbers=chapters_to_process,
        scope=scope,
        driver=driver,
        genre=genre,
        series_name=series_name,
    )

    logger.info("reprocessing_completed", **result)
    return result


async def process_book_embeddings(
    ctx: dict[str, Any],
    book_id: str,
) -> dict[str, Any]:
    """Run the embedding pipeline for all chunks of a book.

    Fetches chunks without embeddings, calls VoyageEmbedder,
    writes vectors back to Neo4j. Handles partial failures gracefully.
    """
    driver = ctx["neo4j_driver"]
    cost_tracker = ctx["cost_tracker"]

    logger.info("task_book_embeddings_started", book_id=book_id)

    book_repo = BookRepository(driver)
    chunks = await book_repo.get_chunks_for_embedding(book_id)

    if not chunks:
        logger.info("task_book_embeddings_no_chunks", book_id=book_id)
        return {"book_id": book_id, "embedded": 0, "failed": 0}

    # Update status to embedding
    await book_repo.update_book_status(book_id, "embedding")

    from app.services.embedding_pipeline import embed_book_chunks

    result = await embed_book_chunks(
        driver=driver,
        book_id=book_id,
        chunks=chunks,
        cost_tracker=cost_tracker,
    )

    if result.failed_keys:
        logger.warning(
            "task_book_embeddings_partial_failure",
            book_id=book_id,
            failed=result.failed,
            failed_keys=result.failed_keys[:10],
        )

    # Update book status
    if result.failed == 0:
        await book_repo.update_book_status(book_id, "embedded")
    # else: keep current status (extracted/partial)

    logger.info(
        "task_book_embeddings_completed",
        book_id=book_id,
        embedded=result.embedded,
        failed=result.failed,
        total_tokens=result.total_tokens,
        cost_usd=round(result.cost_usd, 6),
    )

    return {
        "book_id": book_id,
        "embedded": result.embedded,
        "failed": result.failed,
        "total_tokens": result.total_tokens,
        "cost_usd": result.cost_usd,
    }
