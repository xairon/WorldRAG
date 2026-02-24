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
) -> dict[str, Any]:
    """Run the full KG extraction pipeline for a book.

    Called by the arq worker after a job is enqueued from
    POST /books/{book_id}/extract.

    On success: enqueues process_book_embeddings automatically.
    On chapter failure: pushes to DLQ (individual chapters).
    On total failure: raises to let arq mark job as failed.
    """
    driver = ctx["neo4j_driver"]
    dlq = ctx["dlq"]
    cost_tracker = ctx.get("cost_tracker")

    logger.info("task_book_extraction_started", book_id=book_id, genre=genre)

    book_repo = BookRepository(driver)
    book = await book_repo.get_book(book_id)
    if not book:
        msg = f"Book {book_id!r} not found"
        raise ValueError(msg)

    chapters = await book_repo.get_chapters_for_extraction(book_id)
    if not chapters:
        msg = f"No chapters found for book {book_id!r}"
        raise ValueError(msg)

    chapter_regex = await book_repo.get_chapter_regex_json(book_id)

    # Import here to avoid circular import at module load
    from app.services.graph_builder import build_book_graph

    result = await build_book_graph(
        driver=driver,
        book_repo=book_repo,
        book_id=book_id,
        chapters=chapters,
        genre=genre,
        series_name=series_name,
        chapter_regex_matches=chapter_regex,
        dlq=dlq,
        cost_tracker=cost_tracker,
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
