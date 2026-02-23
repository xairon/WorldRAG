"""WorldRAG FastAPI application.

Main entry point with lifespan management for all infrastructure connections.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncGraphDatabase
from redis.asyncio import Redis

from app.api.middleware import RequestContextMiddleware
from app.api.routes import admin, books, health
from app.config import settings
from app.core.cost_tracker import CostTracker
from app.core.dead_letter import DeadLetterQueue
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle: connect/disconnect all services."""
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("worldrag_starting", version="0.1.0")

    # --- Neo4j ---
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        await neo4j_driver.verify_connectivity()
        logger.info("neo4j_connected", uri=settings.neo4j_uri)
    except Exception as e:
        logger.error("neo4j_connection_failed", error=str(e))
    app.state.neo4j_driver = neo4j_driver

    # --- Redis ---
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        logger.info("redis_connected", url=settings.redis_url)
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))
    app.state.redis = redis

    # --- PostgreSQL ---
    pg_pool = None
    try:
        pg_pool = await asyncpg.create_pool(settings.postgres_uri, min_size=2, max_size=10)
        logger.info("postgres_connected", uri=settings.postgres_uri)
    except Exception as e:
        logger.warning("postgres_connection_failed", error=str(e))
    app.state.pg_pool = pg_pool

    # --- LangFuse ---
    langfuse = None
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            from langfuse import Langfuse

            langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            logger.info("langfuse_connected", host=settings.langfuse_host)
        except Exception as e:
            logger.warning("langfuse_connection_failed", error=str(e))
    app.state.langfuse = langfuse

    # --- Cost Tracker ---
    app.state.cost_tracker = CostTracker(
        ceiling_per_chapter=settings.cost_ceiling_per_chapter,
        ceiling_per_book=settings.cost_ceiling_per_book,
    )

    # --- Dead Letter Queue ---
    app.state.dlq = DeadLetterQueue(redis)

    logger.info("worldrag_started")

    yield

    # --- Shutdown ---
    logger.info("worldrag_stopping")
    await neo4j_driver.close()
    await redis.close()
    if pg_pool is not None:
        await pg_pool.close()
    if langfuse is not None:
        langfuse.flush()
    logger.info("worldrag_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="WorldRAG",
        description="Knowledge Graph construction system for fiction novel universes",
        version="0.1.0",
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    # --- Routes ---
    app.include_router(health.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(books.router, prefix="/api")

    return app


app = create_app()
