"""Temporal sort node: sort chunks by (chapter_number, position) for timeline Q&A.

Ensures that when answering timeline questions, chunks are presented to the
generator in chronological order so events flow naturally in the context window.

This node is a no-op for non-temporal routes — it returns the unchanged list
when the route is not 'timeline_qa'.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def temporal_sort(state: dict[str, Any]) -> dict[str, Any]:
    """Sort reranked chunks chronologically for timeline Q&A.

    For timeline_qa route: sorts by (chapter_number ASC, position ASC).
    For all other routes: returns chunks in reranker order (no-op).

    The sorted list is stored back in reranked_chunks so context_assembly
    picks them up in the right order.
    """
    route = state.get("route", "")
    chunks = state.get("reranked_chunks", [])

    if route != "timeline_qa" or not chunks:
        return {}  # no-op

    sorted_chunks = sorted(
        chunks,
        key=lambda c: (c.get("chapter_number", 0), c.get("position", 0)),
    )

    logger.info(
        "temporal_sort_completed",
        route=route,
        chunk_count=len(sorted_chunks),
        chapter_range=(
            sorted_chunks[0].get("chapter_number", 0),
            sorted_chunks[-1].get("chapter_number", 0),
        ) if sorted_chunks else (0, 0),
    )
    return {"reranked_chunks": sorted_chunks}
