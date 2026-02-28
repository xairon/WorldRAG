"""Admin endpoints for monitoring, costs, and DLQ management.

Provides operational visibility into the extraction pipeline.
All admin endpoints require the admin API key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_admin
from app.api.dependencies import get_arq_pool, get_cost_tracker, get_dlq
from app.core.logging import get_logger

if TYPE_CHECKING:
    from arq.connections import ArqRedis

    from app.core.cost_tracker import CostTracker
    from app.core.dead_letter import DeadLetterQueue

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

ARQ_QUEUE = "worldrag:arq"


@router.get("/costs", dependencies=[Depends(require_admin)])
async def get_costs(
    cost_tracker: CostTracker = Depends(get_cost_tracker),
) -> dict:
    """Get aggregated LLM cost summary by provider, model, and operation."""
    return cost_tracker.summary()


@router.get("/costs/{book_id}", dependencies=[Depends(require_admin)])
async def get_book_costs(
    book_id: str,
    cost_tracker: CostTracker = Depends(get_cost_tracker),
) -> dict:
    """Get cost breakdown for a specific book."""
    book_entries = [e for e in cost_tracker.entries if e.book_id == book_id]
    by_chapter: dict[int, float] = {}
    for entry in book_entries:
        if entry.chapter is not None:
            by_chapter[entry.chapter] = by_chapter.get(entry.chapter, 0) + entry.cost_usd

    return {
        "book_id": book_id,
        "total_cost_usd": round(sum(e.cost_usd for e in book_entries), 4),
        "chapter_count": len(by_chapter),
        "by_chapter": {str(k): round(v, 4) for k, v in sorted(by_chapter.items())},
    }


@router.get("/dlq", dependencies=[Depends(require_admin)])
async def list_dlq(
    book_id: str | None = Query(None, description="Filter by book ID"),
    dlq: DeadLetterQueue = Depends(get_dlq),
) -> dict:
    """List all entries in the Dead Letter Queue, optionally filtered by book."""
    entries = await dlq.list_all()
    if book_id:
        entries = [e for e in entries if e.book_id == book_id]
    return {
        "count": len(entries),
        "entries": [
            {
                "book_id": e.book_id,
                "chapter": e.chapter,
                "error_type": e.error_type,
                "error_message": e.error_message,
                "timestamp": e.timestamp,
                "attempt_count": e.attempt_count,
            }
            for e in entries
        ],
    }


@router.get("/dlq/size", dependencies=[Depends(require_admin)])
async def dlq_size(
    dlq: DeadLetterQueue = Depends(get_dlq),
) -> dict:
    """Get the number of entries in the DLQ."""
    size = await dlq.size()
    return {"size": size}


@router.post("/dlq/clear", dependencies=[Depends(require_admin)])
async def clear_dlq(
    dlq: DeadLetterQueue = Depends(get_dlq),
) -> dict:
    """Clear all entries from the DLQ."""
    count = await dlq.clear()
    return {"cleared": count}


@router.post(
    "/dlq/retry/{book_id}/{chapter}",
    dependencies=[Depends(require_admin)],
)
async def retry_dlq_chapter(
    book_id: str,
    chapter: int,
    dlq: DeadLetterQueue = Depends(get_dlq),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> dict:
    """Re-enqueue a single failed chapter for extraction.

    Removes matching DLQ entries and enqueues a new extraction job
    for the specific book. The extraction worker will process all
    chapters that haven't been extracted yet.
    """
    removed = await dlq.remove_by_book_chapter(book_id, chapter)
    if removed == 0:
        return {
            "retried": False,
            "reason": f"No DLQ entry found for book={book_id!r} chapter={chapter}",
        }

    job = await arq_pool.enqueue_job(
        "process_book_extraction",
        book_id,
        _queue_name=ARQ_QUEUE,
        _job_id=f"retry:{book_id}:{chapter}",
    )
    logger.info(
        "dlq_retry_enqueued",
        book_id=book_id,
        chapter=chapter,
        job_id=job.job_id if job else None,
        removed=removed,
    )
    return {
        "retried": True,
        "book_id": book_id,
        "chapter": chapter,
        "entries_removed": removed,
        "job_id": job.job_id if job else None,
    }


@router.post("/dlq/retry-all", dependencies=[Depends(require_admin)])
async def retry_all_dlq(
    dlq: DeadLetterQueue = Depends(get_dlq),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> dict:
    """Re-enqueue all failed chapters from the DLQ.

    Groups entries by book_id and enqueues one extraction job per book.
    Clears the entire DLQ after enqueuing.
    """
    entries = await dlq.list_all()
    if not entries:
        return {"retried": 0, "jobs_enqueued": 0}

    # Group by book_id (one job per book)
    book_ids: set[str] = {e.book_id for e in entries}
    jobs_enqueued = 0

    for bid in book_ids:
        job = await arq_pool.enqueue_job(
            "process_book_extraction",
            bid,
            _queue_name=ARQ_QUEUE,
            _job_id=f"retry-all:{bid}",
        )
        if job:
            jobs_enqueued += 1

    cleared = await dlq.clear()

    logger.info(
        "dlq_retry_all_enqueued",
        entries=len(entries),
        books=len(book_ids),
        jobs_enqueued=jobs_enqueued,
    )

    return {
        "retried": len(entries),
        "books": list(book_ids),
        "jobs_enqueued": jobs_enqueued,
        "entries_cleared": cleared,
    }
