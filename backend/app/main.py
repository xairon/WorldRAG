"""WorldRAG FastAPI application.

Main entry point with lifespan management for all infrastructure connections.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j import AsyncGraphDatabase
from redis.asyncio import Redis

from app.api.middleware import RequestContextMiddleware
from app.api.routes import admin, books, graph, health
from app.config import settings
from app.core.cost_tracker import CostTracker
from app.core.dead_letter import DeadLetterQueue
from app.core.exceptions import WorldRAGError
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _safe_host(uri: str) -> str:
    """Extract host from a connection URI without leaking credentials.

    'bolt://neo4j:pass@localhost:7687' -> 'localhost:7687'
    'redis://:pass@localhost:6379'     -> 'localhost:6379'
    'postgresql://u:p@host:5432/db'    -> 'host:5432'
    """
    try:
        # Strip scheme
        rest = uri.split("://", 1)[-1]
        # Strip auth
        if "@" in rest:
            rest = rest.split("@", 1)[-1]
        # Strip path/query
        return rest.split("/")[0].split("?")[0]
    except Exception:
        return "<redacted>"


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
        logger.info("neo4j_connected", host=_safe_host(settings.neo4j_uri))
    except ConnectionError as e:
        logger.error("neo4j_connection_failed", host=_safe_host(settings.neo4j_uri), error=str(e))
    except Exception as e:
        logger.error("neo4j_connection_failed", error=type(e).__name__)
    app.state.neo4j_driver = neo4j_driver

    # --- Redis ---
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        logger.info("redis_connected", host=_safe_host(settings.redis_url))
    except ConnectionError as e:
        logger.error("redis_connection_failed", host=_safe_host(settings.redis_url), error=str(e))
    except Exception as e:
        logger.error("redis_connection_failed", error=type(e).__name__)
    app.state.redis = redis

    # --- PostgreSQL ---
    pg_pool = None
    try:
        pg_pool = await asyncpg.create_pool(settings.postgres_uri, min_size=2, max_size=10)
        logger.info("postgres_connected", host=_safe_host(settings.postgres_uri))
    except (ConnectionError, OSError) as e:
        logger.warning(
            "postgres_connection_failed", host=_safe_host(settings.postgres_uri), error=str(e)
        )
    except Exception as e:
        logger.warning("postgres_connection_failed", error=type(e).__name__)
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
            logger.info("langfuse_connected", host=_safe_host(settings.langfuse_host))
        except Exception as e:
            logger.warning("langfuse_connection_failed", error=type(e).__name__)
    app.state.langfuse = langfuse

    # --- Cost Tracker ---
    app.state.cost_tracker = CostTracker(
        ceiling_per_chapter=settings.cost_ceiling_per_chapter,
        ceiling_per_book=settings.cost_ceiling_per_book,
    )

    # --- Dead Letter Queue ---
    app.state.dlq = DeadLetterQueue(redis)

    # --- arq Pool (for enqueueing background jobs from API) ---
    arq_pool = None
    try:
        from arq.connections import create_pool

        from app.workers.settings import _parse_redis_settings

        arq_pool = await create_pool(
            _parse_redis_settings(),
            default_queue_name="worldrag:arq",
        )
        logger.info("arq_pool_connected")
    except Exception as e:
        logger.warning("arq_pool_connection_failed", error=type(e).__name__)
    app.state.arq_pool = arq_pool

    # --- Ontology ---
    from app.core.ontology_loader import get_ontology

    ontology = get_ontology(genre="litrpg", series="primal_hunter")
    app.state.ontology = ontology

    # --- Auth mode ---
    auth_mode = "api_key" if settings.api_key else "dev (no auth)"
    logger.info("worldrag_started", auth_mode=auth_mode)

    yield

    # --- Shutdown ---
    logger.info("worldrag_stopping")
    if arq_pool is not None:
        await arq_pool.close()
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

    # --- Global exception handler for WorldRAGError hierarchy ---
    @app.exception_handler(WorldRAGError)
    async def worldrag_error_handler(request: Request, exc: WorldRAGError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": type(exc).__name__,
                "detail": exc.detail,
                "context": exc.context if settings.debug else {},
            },
        )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    # --- Routes ---
    app.include_router(health.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(books.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")

    return app


app = create_app()
