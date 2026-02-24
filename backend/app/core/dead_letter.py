"""Dead Letter Queue (DLQ) for failed pipeline operations.

Failed chapters are stored in Redis for inspection and manual retry.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)

DLQ_KEY = "worldrag:dlq:extraction"


@dataclass
class DLQEntry:
    """A failed operation stored in the DLQ."""

    book_id: str
    chapter: int
    error_type: str
    error_message: str
    timestamp: float
    attempt_count: int = 1
    metadata: dict | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> DLQEntry:
        return cls(**json.loads(data))


class DeadLetterQueue:
    """Redis-backed dead letter queue for failed pipeline operations."""

    def __init__(self, redis: Redis, key: str = DLQ_KEY) -> None:
        self.redis = redis
        self.key = key

    async def push(self, entry: DLQEntry) -> None:
        """Add a failed operation to the DLQ."""
        await self.redis.rpush(self.key, entry.to_json())
        logger.error(
            "dlq_push",
            book_id=entry.book_id,
            chapter=entry.chapter,
            error_type=entry.error_type,
            error_message=entry.error_message,
        )

    async def push_failure(
        self,
        book_id: str,
        chapter: int,
        error: Exception,
        attempt_count: int = 1,
        metadata: dict | None = None,
    ) -> None:
        """Convenience method to push a failure from an exception."""
        entry = DLQEntry(
            book_id=book_id,
            chapter=chapter,
            error_type=type(error).__name__,
            error_message=str(error),
            timestamp=time.time(),
            attempt_count=attempt_count,
            metadata=metadata,
        )
        await self.push(entry)

    async def list_all(self) -> list[DLQEntry]:
        """List all entries in the DLQ."""
        raw_entries = await self.redis.lrange(self.key, 0, -1)
        return [DLQEntry.from_json(entry) for entry in raw_entries]

    async def pop(self) -> DLQEntry | None:
        """Remove and return the oldest entry."""
        raw = await self.redis.lpop(self.key)
        if raw is None:
            return None
        return DLQEntry.from_json(raw)

    async def size(self) -> int:
        """Return the number of entries in the DLQ."""
        return await self.redis.llen(self.key)

    async def remove_by_book_chapter(self, book_id: str, chapter: int) -> int:
        """Remove all entries for a specific book/chapter. Returns count removed."""
        entries = await self.redis.lrange(self.key, 0, -1)
        removed = 0
        for raw in entries:
            entry = DLQEntry.from_json(raw)
            if entry.book_id == book_id and entry.chapter == chapter:
                await self.redis.lrem(self.key, 1, raw)
                removed += 1
        if removed:
            logger.info(
                "dlq_removed_entries",
                book_id=book_id,
                chapter=chapter,
                removed=removed,
            )
        return removed

    async def clear(self) -> int:
        """Clear all entries from the DLQ. Returns count of removed entries."""
        count = await self.redis.llen(self.key)
        await self.redis.delete(self.key)
        logger.info("dlq_cleared", count=count)
        return count
