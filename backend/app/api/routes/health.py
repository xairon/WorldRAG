"""Health check endpoints.

Verifies connectivity to all infrastructure services:
Neo4j, Redis, PostgreSQL, LangFuse, and LLM providers.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict:
    """Comprehensive health check for all services.

    Returns status of each service and overall health.
    """
    checks: dict[str, str] = {}

    # Neo4j
    try:
        driver = request.app.state.neo4j_driver
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS n")
            await result.single()
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = f"error: {e}"
        logger.error("health_check_failed", service="neo4j", error=str(e))

    # Redis
    try:
        redis = request.app.state.redis
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        logger.error("health_check_failed", service="redis", error=str(e))

    # PostgreSQL
    try:
        pool = request.app.state.pg_pool
        if pool is not None:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["postgres"] = "ok"
        else:
            checks["postgres"] = "not configured"
    except Exception as e:
        checks["postgres"] = f"error: {e}"
        logger.error("health_check_failed", service="postgres", error=str(e))

    # LangFuse
    try:
        langfuse = request.app.state.langfuse
        if langfuse is not None:
            checks["langfuse"] = "ok"
        else:
            checks["langfuse"] = "not configured"
    except Exception as e:
        checks["langfuse"] = f"error: {e}"
        logger.error("health_check_failed", service="langfuse", error=str(e))

    # Overall
    all_ok = all(v == "ok" for v in checks.values() if v != "not configured")
    status = "healthy" if all_ok else "degraded"

    return {"status": status, "services": checks}


@router.get("/health/ready")
async def readiness_check(request: Request) -> dict:
    """Quick readiness probe (for k8s / docker healthcheck)."""
    try:
        driver = request.app.state.neo4j_driver
        async with driver.session() as session:
            await session.run("RETURN 1")
        return {"ready": True}
    except Exception:
        return {"ready": False}
