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

import time
from typing import Any

from app.core.exceptions import QuotaExhaustedError
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
    provider: str | None = None,
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
        return await process_book_extraction_v3(
            ctx,
            book_id,
            genre,
            series_name,
            chapters,
            settings.extraction_language,
        )

    # Delegate to V4 pipeline (was incorrectly calling build_book_graph before)
    return await process_book_extraction_v4(
        ctx,
        book_id,
        genre,
        series_name,
        chapters,
        settings.extraction_language,
        provider,
    )


async def process_book_extraction_v3(
    ctx: dict[str, Any],
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    chapters: list[int] | None = None,
    language: str = "fr",
    provider: str | None = None,
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
    logger.info("v3_task_args", book_id=book_id, genre=genre, provider=provider, language=language)

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
    from app.core.exceptions import CostCeilingError
    from app.services.extraction.entity_registry import EntityRegistry
    from app.services.graph_builder import _is_non_content_chapter, build_chapter_graph_v3

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
    for _idx, chapter in enumerate(content_chapters):
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
                provider=provider,
            )
            total_entities += stats.get("total_entities", 0)
            chapter_stats.append(stats)

            # Update registry with all extracted entities (rich data)
            for ent in stats.get("extracted_entities") or []:
                entity_registry.add(
                    name=ent["name"],
                    entity_type=ent["type"],
                    aliases=ent.get("aliases", []),
                    significance=ent.get("significance", ""),
                    first_seen_chapter=chapter.number,
                    description=ent.get("description", ""),
                )
                entity_registry.update_last_seen(ent["name"], chapter.number)

            # Also record alias_map canonical names
            for _old_name, new_name in (stats.get("alias_map") or {}).items():
                if not entity_registry.lookup(new_name):
                    entity_registry.add(new_name, "Unknown")

            # Save registry after each chapter
            await book_repo.save_entity_registry(
                book_id,
                entity_registry.to_dict(),
                ontology_version,
            )

            await _publish_progress(
                chapter.number,
                len(content_chapters),
                "extracted",
                stats.get("total_entities", 0),
            )

        except QuotaExhaustedError as qe:
            logger.warning(
                "v3_quota_exhausted",
                book_id=book_id,
                chapter=chapter.number,
                provider=qe.provider,
                chapters_processed=len(chapter_stats),
            )
            failed_chapters.append(chapter.number)
            await _publish_progress(
                chapter.number,
                len(content_chapters),
                "error_quota",
                total_entities,
            )
            await book_repo.update_book_status(book_id, "error_quota")
            return {
                "book_id": book_id,
                "chapters_processed": len(chapter_stats),
                "chapters_failed": len(failed_chapters),
                "failed_chapters": failed_chapters,
                "total_entities": total_entities,
                "stopped_reason": "quota_exhausted",
                "stopped_at_chapter": chapter.number,
                "provider": qe.provider,
            }
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

    # Update final status + chapters_processed
    if cost_ceiling_hit:
        final_status = "cost_ceiling_hit"
    elif failed_chapters:
        final_status = "partial"
    else:
        final_status = "extracted"
    await book_repo.update_book_status(book_id, final_status)
    await book_repo.update_book_chapters_processed(book_id, len(chapter_stats))

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


async def process_book_extraction_v4(
    ctx: dict[str, Any],
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    chapters: list[int] | None = None,
    language: str = "fr",
    provider: str | None = None,
) -> dict[str, Any]:
    """Run the V4 single-pass extraction pipeline for a book.

    Like process_book_extraction_v3, processes chapters sequentially to maintain
    EntityRegistry context across chapters.  Uses the v4 4-node LangGraph
    (extract_entities → extract_relations → mention_detect → reconcile_persist).

    On success: enqueues process_book_embeddings automatically.
    On chapter failure: pushes to DLQ (individual chapters).
    On QuotaExhaustedError: stops immediately, marks book "error_quota".
    On CostCeilingError: stops, marks book "cost_ceiling_hit".
    """
    logger.info("v4_task_args", book_id=book_id, genre=genre, provider=provider, language=language)

    driver = ctx["neo4j_driver"]
    dlq = ctx["dlq"]
    cost_tracker = ctx.get("cost_tracker")

    from app.config import settings

    ontology_version = settings.ontology_version
    if not language:
        language = settings.extraction_language

    logger.info(
        "task_book_extraction_v4_started",
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

    from app.core.exceptions import CostCeilingError
    from app.repositories.entity_repo import EntityRepository
    from app.services.extraction import extract_chapter_v4
    from app.services.extraction.entity_registry import EntityRegistry
    from app.services.graph_builder import _is_non_content_chapter

    entity_repo = EntityRepository(driver)

    # Initialize entity registry
    entity_registry = EntityRegistry()

    from app.core.ontology_loader import OntologyLoader

    ontology = OntologyLoader.from_layers(genre=genre, series=series_name)
    logger.info(
        "v4_ontology_loaded",
        layers=ontology.layers_loaded,
        node_types=len(ontology.node_types),
        relationship_types=len(ontology.relationship_types),
    )

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
                    "v4_cross_book_registry_loaded",
                    book_id=book_id,
                    series_name=series_name,
                    series_books_count=len(series_books),
                    registry_entity_count=entity_registry.entity_count,
                )
        except Exception:
            logger.warning(
                "v4_cross_book_registry_load_failed",
                book_id=book_id,
                series_name=series_name,
                exc_info=True,
            )

    # Filter non-content chapters
    content_chapters = [ch for ch in chapter_data if not _is_non_content_chapter(ch)]
    skipped = len(chapter_data) - len(content_chapters)
    if skipped:
        logger.info(
            "v4_chapters_skipped",
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
                        "pipeline": "v4",
                    }
                ),
            )

    # Reset previous extraction data before starting fresh
    deleted = await book_repo.reset_extraction(book_id)
    if deleted:
        logger.info("v4_previous_extraction_cleared", book_id=book_id, entities_deleted=deleted)

    await book_repo.update_book_status(book_id, "extracting")

    total_entities = 0
    failed_chapters: list[int] = []
    chapter_stats: list[dict[str, Any]] = []
    cost_ceiling_hit = False

    # Process chapters SEQUENTIALLY (narrative order matters for EntityRegistry)
    for chapter in content_chapters:
        import uuid

        batch_id = str(uuid.uuid4())
        regex_json = chapter_regex.get(chapter.number, "[]")
        try:
            result = await extract_chapter_v4(
                book_id=book_id,
                chapter_number=chapter.number,
                chapter_text=chapter.text,
                regex_matches_json=regex_json,
                genre=genre,
                series_name=series_name,
                source_language=language,
                model_override=provider,
                entity_registry=entity_registry.to_dict(),
                ontology=ontology,
            )

            entities = result.get("entities") or []
            relations = result.get("relations") or []
            ended_relations = result.get("ended_relations") or []

            # Persist to Neo4j
            counts = await entity_repo.upsert_v4_entities(
                entities=entities,
                relations=relations,
                ended_relations=ended_relations,
                book_id=book_id,
                chapter_number=chapter.number,
                batch_id=batch_id,
            )
            chapter_entity_count = sum(counts.values())
            total_entities += chapter_entity_count

            # Apply ended relations
            for ended in ended_relations:
                try:
                    await entity_repo.apply_relation_end(
                        source=ended.get("source", ""),
                        target=ended.get("target", ""),
                        relation_type=ended.get("relation_type", ""),
                        ended_at_chapter=chapter.number,
                        reason=ended.get("reason", ""),
                        book_id=book_id,
                    )
                except Exception:
                    logger.warning(
                        "v4_relation_end_failed",
                        book_id=book_id,
                        chapter=chapter.number,
                        ended=ended,
                        exc_info=True,
                    )

            # Update entity_registry from result (already updated inside reconcile_persist node)
            updated_registry = result.get("entity_registry")
            if updated_registry:
                entity_registry = EntityRegistry.from_dict(updated_registry)

            # Save registry after each chapter
            await book_repo.save_entity_registry(
                book_id,
                entity_registry.to_dict(),
                ontology_version,
            )

            # Update chapter status in Neo4j (Bug 3 fix)
            await book_repo.update_chapter_status(
                book_id, chapter.number, "extracted", chapter_entity_count
            )

            chapter_stats.append(
                {
                    "chapter": chapter.number,
                    "entities": chapter_entity_count,
                    "relations": len(relations),
                }
            )

            await _publish_progress(
                chapter.number,
                len(content_chapters),
                "extracted",
                chapter_entity_count,
            )

        except QuotaExhaustedError as qe:
            logger.warning(
                "v4_quota_exhausted",
                book_id=book_id,
                chapter=chapter.number,
                provider=qe.provider,
                chapters_processed=len(chapter_stats),
            )
            failed_chapters.append(chapter.number)
            await _publish_progress(
                chapter.number,
                len(content_chapters),
                "error_quota",
                total_entities,
            )
            await book_repo.update_book_status(book_id, "error_quota")
            return {
                "book_id": book_id,
                "chapters_processed": len(chapter_stats),
                "chapters_failed": len(failed_chapters),
                "failed_chapters": failed_chapters,
                "total_entities": total_entities,
                "stopped_reason": "quota_exhausted",
                "stopped_at_chapter": chapter.number,
                "provider": qe.provider,
            }
        except CostCeilingError:
            logger.warning(
                "v4_cost_ceiling_hit",
                book_id=book_id,
                chapter=chapter.number,
                chapters_processed=len(chapter_stats),
            )
            cost_ceiling_hit = True
            break
        except Exception as exc:
            logger.exception(
                "v4_chapter_failed",
                book_id=book_id,
                chapter=chapter.number,
            )
            failed_chapters.append(chapter.number)
            if dlq:
                await dlq.push_failure(
                    book_id=book_id,
                    chapter=chapter.number,
                    error=exc,
                    metadata={"genre": genre, "pipeline": "v4"},
                )
            await _publish_progress(chapter.number, len(content_chapters), "failed", 0)

    # Update final status + chapters_processed
    if cost_ceiling_hit:
        final_status = "cost_ceiling_hit"
    elif failed_chapters:
        final_status = "partial"
    else:
        final_status = "extracted"
    await book_repo.update_book_status(book_id, final_status)
    await book_repo.update_book_chapters_processed(book_id, len(chapter_stats))

    result_summary = {
        "book_id": book_id,
        "chapters_processed": len(chapter_stats),
        "chapters_failed": len(failed_chapters),
        "failed_chapters": failed_chapters,
        "total_entities": total_entities,
        "status": final_status,
        "cost_ceiling_hit": cost_ceiling_hit,
        "ontology_version": ontology_version,
        "pipeline": "v4",
    }

    logger.info("task_book_extraction_v4_completed", **result_summary)

    # Book-level post-processing
    try:
        from app.services.extraction.book_level import (
            community_cluster,
            generate_entity_summaries,
            iterative_cluster,
        )

        book_batch_id = f"book-level:{book_id}:{int(time.time())}"

        # 1. Iterative clustering
        cluster_aliases = await iterative_cluster(driver, book_id)
        logger.info("v4_book_clustering_done", merges=len(cluster_aliases))

        # 2. Entity summaries
        summaries = await generate_entity_summaries(driver, book_id, batch_id=book_batch_id)
        logger.info("v4_book_summaries_done", count=len(summaries))

        # 3. Community clustering
        communities = await community_cluster(driver, book_id, batch_id=book_batch_id)
        logger.info("v4_book_communities_done", count=len(communities))
    except Exception:
        logger.warning("v4_book_level_failed", book_id=book_id, exc_info=True)

    # Auto-enqueue embedding job after extraction
    await ctx["redis"].enqueue_job(
        "process_book_embeddings",
        book_id,
        _queue_name=ARQ_QUEUE,
        _job_id=f"embed:{book_id}",
    )
    logger.info("task_embeddings_enqueued", book_id=book_id, pipeline="v4")

    return result_summary


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


async def process_book_graphiti(
    ctx: dict[str, Any],
    book_id: str,
    saga_id: str,
    saga_name: str,
    book_num: int = 1,
    saga_profile_json: str | None = None,
) -> dict[str, Any]:
    """Ingest a book via Graphiti (KG v2 pipeline).

    Discovery Mode if saga_profile_json is None, Guided Mode otherwise.
    After Discovery Mode, auto-runs SagaProfileInducer and stores result in Redis.
    """
    # C4: Graceful error when Graphiti is not in worker context
    graphiti = ctx.get("graphiti")
    if graphiti is None:
        raise ValueError("Graphiti is not enabled. Set GRAPHITI_ENABLED=true.")
    neo4j_driver = ctx["neo4j_driver"]
    dlq = ctx.get("dlq")

    book_repo = BookRepository(neo4j_driver)
    chapter_data = await book_repo.get_chapters_for_extraction(book_id)
    chapters = [{"number": ch.number, "text": ch.text} for ch in chapter_data]

    logger.info(
        "task_graphiti_ingestion_started",
        book_id=book_id,
        saga_id=saga_id,
        chapters=len(chapters),
        mode="guided" if saga_profile_json else "discovery",
    )

    # Progress callback: publish to Redis pub/sub for SSE consumers
    dlq_redis = ctx.get("dlq_redis")
    chapters_done = 0

    async def _publish_progress(status: str, entities: int = 0) -> None:
        if dlq_redis is not None:
            import json

            await dlq_redis.publish(
                f"worldrag:progress:{book_id}",
                json.dumps(
                    {
                        "chapter": chapters_done,
                        "total": len(chapters),
                        "status": status,
                        "entities_found": entities,
                        "chapters_done": chapters_done,
                    }
                ),
            )

    await _publish_progress("started")

    from app.services.ingestion.graphiti_ingest import BookIngestionOrchestrator

    orchestrator = BookIngestionOrchestrator(graphiti=graphiti)

    failed_chapters: list[int] = []
    if saga_profile_json:
        from app.services.saga_profile.models import SagaProfile

        profile = SagaProfile.model_validate_json(saga_profile_json)
        for ch in chapters:
            try:
                await orchestrator.ingest_guided(
                    chapters=[ch],
                    book_id=book_id,
                    book_num=book_num,
                    saga_id=saga_id,
                    profile=profile,
                )
                chapters_done += 1
                await _publish_progress("progress", chapters_done)
            except Exception as exc:
                logger.exception("graphiti_chapter_failed", chapter=ch["number"])
                failed_chapters.append(ch["number"])
                chapters_done += 1
                await _publish_progress("progress", chapters_done)
                if dlq:
                    await dlq.push_failure(
                        book_id=book_id,
                        chapter=ch["number"],
                        error=exc,
                        metadata={"saga_id": saga_id, "pipeline": "graphiti-guided"},
                    )
    else:
        for ch in chapters:
            try:
                await orchestrator.ingest_discovery(
                    chapters=[ch],
                    book_id=book_id,
                    book_num=book_num,
                    saga_id=saga_id,
                )
                chapters_done += 1
                await _publish_progress("progress", chapters_done)
            except Exception as exc:
                logger.exception("graphiti_chapter_failed", chapter=ch["number"])
                failed_chapters.append(ch["number"])
                chapters_done += 1
                await _publish_progress("progress", chapters_done)
                if dlq:
                    await dlq.push_failure(
                        book_id=book_id,
                        chapter=ch["number"],
                        error=exc,
                        metadata={"saga_id": saga_id, "pipeline": "graphiti-discovery"},
                    )

        # Auto-run SagaProfileInducer after Discovery
        from app.services.saga_profile.inducer import SagaProfileInducer

        full_text = "\n".join(ch["text"] for ch in chapters)
        inducer = SagaProfileInducer(driver=neo4j_driver)
        profile = await inducer.induce(
            saga_id=saga_id,
            saga_name=saga_name,
            source_book=book_id,
            raw_text=full_text,
        )
        # Store profile in Redis for reuse in Guided Mode
        dlq_redis = ctx.get("dlq_redis")
        if dlq_redis:
            await dlq_redis.set(f"saga_profile:{saga_id}", profile.model_dump_json())
        logger.info(
            "saga_profile_induced",
            saga_id=saga_id,
            entity_types=len(profile.entity_types),
            patterns=len(profile.text_patterns),
        )

        # Run community clustering
        from app.services.community_clustering import run_community_clustering

        clustering_result = await run_community_clustering(neo4j_driver, saga_id=saga_id)
        logger.info("community_clustering_done", **clustering_result)

    await _publish_progress("done", chapters_done)

    result = {
        "book_id": book_id,
        "saga_id": saga_id,
        "chapters_processed": len(chapters) - len(failed_chapters),
        "chapters_failed": len(failed_chapters),
        "pipeline": "graphiti",
        "mode": "guided" if saga_profile_json else "discovery",
    }
    logger.info("task_graphiti_ingestion_completed", **result)
    return result
