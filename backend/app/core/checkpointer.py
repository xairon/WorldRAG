"""LangGraph checkpointer factory for PostgreSQL persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_checkpointer(
    pool: AsyncConnectionPool | None,
) -> tuple:
    """Create an AsyncPostgresSaver using an existing psycopg pool.

    Args:
        pool: An open AsyncConnectionPool. If None, returns (None, False).

    Returns:
        Tuple of (saver_or_none, success_bool).
    """
    if pool is None:
        return None, False

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = AsyncPostgresSaver(conn=pool)
        await saver.setup()
        logger.info("checkpointer_ready")
        return saver, True
    except Exception as exc:
        logger.warning("checkpointer_creation_failed", error=type(exc).__name__)
        return None, False
