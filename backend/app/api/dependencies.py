"""FastAPI dependency injection.

Provides shared resources (Neo4j, Redis, LLM clients, etc.) to route handlers.
All connections are managed via the application lifespan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import Request
    from neo4j import AsyncDriver
    from redis.asyncio import Redis

    from app.core.cost_tracker import CostTracker
    from app.core.dead_letter import DeadLetterQueue


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


async def get_neo4j_session(request: Request) -> AsyncGenerator:
    """Get a Neo4j async session (auto-closed)."""
    driver: AsyncDriver = request.app.state.neo4j_driver
    async with driver.session() as session:
        yield session
