"""Admin endpoints for monitoring, costs, and DLQ management.

Provides operational visibility into the extraction pipeline.
All admin endpoints require the admin API key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.api.auth import require_admin
from app.api.dependencies import get_cost_tracker, get_dlq
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.cost_tracker import CostTracker
    from app.core.dead_letter import DeadLetterQueue

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


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
    dlq: DeadLetterQueue = Depends(get_dlq),
) -> dict:
    """List all entries in the Dead Letter Queue."""
    entries = await dlq.list_all()
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
