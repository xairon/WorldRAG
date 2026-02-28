"""SSE streaming endpoints for real-time progress updates.

Provides Server-Sent Events for extraction pipeline progress
via Redis pub/sub subscription.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.auth import require_auth
from app.api.dependencies import get_redis
from app.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)
router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/extraction/{book_id}", dependencies=[Depends(require_auth)])
async def stream_extraction_progress(
    book_id: str,
    redis: Redis = Depends(get_redis),
) -> EventSourceResponse:
    """Stream extraction progress as SSE events.

    Subscribes to Redis pub/sub channel `worldrag:progress:{book_id}`.

    Events:
      - `progress`: chapter completed/failed with entities count
      - `done`: extraction finished (final aggregated stats)
      - `keepalive`: periodic heartbeat to prevent timeout
    """

    async def event_generator():
        pubsub = redis.pubsub()
        channel = f"worldrag:progress:{book_id}"
        await pubsub.subscribe(channel)

        try:
            chapters_done = 0
            total_chapters = 0

            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=5.0,
                )

                if msg and msg["type"] == "message":
                    data = json.loads(msg["data"])
                    total_chapters = data.get("total", total_chapters)
                    status = data.get("status", "")

                    # "started" event = initial signal, don't count as chapter
                    if status == "started":
                        yield {
                            "event": "started",
                            "data": json.dumps(
                                {
                                    **data,
                                    "chapters_done": 0,
                                }
                            ),
                        }
                        continue

                    chapters_done += 1

                    yield {
                        "event": "progress",
                        "data": json.dumps(
                            {
                                **data,
                                "chapters_done": chapters_done,
                            }
                        ),
                    }

                    # If all chapters are done, send done event
                    if total_chapters > 0 and chapters_done >= total_chapters:
                        yield {
                            "event": "done",
                            "data": json.dumps(
                                {
                                    "chapters_done": chapters_done,
                                    "total": total_chapters,
                                }
                            ),
                        }
                        break
                else:
                    # Keepalive to prevent connection timeout
                    yield {"event": "keepalive", "data": "{}"}
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return EventSourceResponse(event_generator())
