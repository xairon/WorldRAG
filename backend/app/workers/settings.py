"""arq worker settings and lifecycle management.

Startup/shutdown mirrors main.py lifespan but is independent of FastAPI.
Each worker process initializes its own connections to Neo4j, Redis, etc.

Launch:
    uv run arq app.workers.settings.WorkerSettings
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from arq.connections import RedisSettings as ArqRedisSettings
from neo4j import AsyncGraphDatabase
from redis.asyncio import Redis

from app.config import settings
from app.core.cost_tracker import CostTracker
from app.core.dead_letter import DeadLetterQueue
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _parse_redis_settings() -> ArqRedisSettings:
    """Parse redis_url into arq RedisSettings.

    settings.redis_url format: redis://:worldrag@localhost:6379
    arq requires host/port/password separately.
    """
    parsed = urlparse(settings.redis_url)
    return ArqRedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
    )


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize all infrastructure for the worker process.

    Populates ctx with shared resources for task functions.
    Note: arq puts its own ArqRedis pool at ctx["redis"] automatically.
    We store our plain Redis for DLQ under a separate key.
    """
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("arq_worker_starting")

    # --- Neo4j ---
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    await neo4j_driver.verify_connectivity()
    ctx["neo4j_driver"] = neo4j_driver
    logger.info("arq_worker_neo4j_connected")

    # --- Redis (for DLQ — separate from arq's own connection) ---
    dlq_redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await dlq_redis.ping()
    ctx["dlq_redis"] = dlq_redis
    logger.info("arq_worker_redis_connected")

    # --- CostTracker ---
    ctx["cost_tracker"] = CostTracker(
        ceiling_per_chapter=settings.cost_ceiling_per_chapter,
        ceiling_per_book=settings.cost_ceiling_per_book,
    )

    # --- DeadLetterQueue ---
    ctx["dlq"] = DeadLetterQueue(dlq_redis)

    logger.info("arq_worker_started")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Cleanly close all infrastructure connections."""
    logger.info("arq_worker_stopping")
    if driver := ctx.get("neo4j_driver"):
        await driver.close()
    if dlq_redis := ctx.get("dlq_redis"):
        await dlq_redis.close()
    logger.info("arq_worker_stopped")


class WorkerSettings:
    """arq WorkerSettings for WorldRAG background tasks.

    Launch with: uv run arq app.workers.settings.WorkerSettings
    """

    # Import functions lazily to avoid circular imports at module load
    from app.workers.tasks import process_book_embeddings, process_book_extraction

    functions = [process_book_extraction, process_book_embeddings]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _parse_redis_settings()
    max_jobs = settings.arq_max_jobs
    job_timeout = settings.arq_job_timeout
    keep_result = settings.arq_keep_result
    queue_name = "worldrag:arq"
