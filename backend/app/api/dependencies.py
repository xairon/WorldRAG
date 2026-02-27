"""FastAPI dependency injection.

Provides shared resources (Neo4j, Redis, LLM clients, etc.) to route handlers.
All connections are managed via the application lifespan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request  # noqa: TC002 (needed at runtime for FastAPI DI)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from arq.connections import ArqRedis
    from neo4j import AsyncDriver
    from redis.asyncio import Redis

    from app.core.cost_tracker import CostTracker
    from app.core.dead_letter import DeadLetterQueue
    from app.core.ontology_loader import OntologyLoader


async def get_neo4j(request: Request) -> AsyncDriver:
    """Get Neo4j async driver from app state."""
    return request.app.state.neo4j_driver


async def get_redis(request: Request) -> Redis:
    """Get Redis async client from app state."""
    return request.app.state.redis


async def get_cost_tracker(request: Request) -> CostTracker:
    """Get cost tracker from app state."""
    return request.app.state.cost_tracker


async def get_dlq(request: Request) -> DeadLetterQueue:
    """Get dead letter queue from app state."""
    return request.app.state.dlq


async def get_arq_pool(request: Request) -> ArqRedis:
    """Get arq Redis pool from app state for job enqueueing."""
    pool = request.app.state.arq_pool
    if pool is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Task queue not available (Redis down?)")
    return pool


async def get_ontology(request: Request) -> OntologyLoader:
    """Get the loaded ontology from app state."""
    return request.app.state.ontology


async def get_neo4j_session(request: Request) -> AsyncGenerator:
    """Get a Neo4j async session (auto-closed)."""
    driver: AsyncDriver = request.app.state.neo4j_driver
    async with driver.session() as session:
        yield session
