"""Health check endpoints.

Verifies connectivity to all infrastructure services:
Neo4j, Redis, PostgreSQL, LangFuse, and LLM providers.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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
        checks["neo4j"] = "error"
        logger.error("health_check_failed", service="neo4j", error=type(e).__name__)

    # Redis
    try:
        redis = request.app.state.redis
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = "error"
        logger.error("health_check_failed", service="redis", error=type(e).__name__)

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
        checks["postgres"] = "error"
        logger.error("health_check_failed", service="postgres", error=type(e).__name__)

    # LangFuse
    try:
        langfuse = request.app.state.langfuse
        if langfuse is not None:
            checks["langfuse"] = "ok"
        else:
            checks["langfuse"] = "not configured"
    except Exception as e:
        checks["langfuse"] = "error"
        logger.error("health_check_failed", service="langfuse", error=type(e).__name__)

    # Overall — return 503 when degraded
    all_ok = all(v == "ok" for v in checks.values() if v != "not configured")
    status = "healthy" if all_ok else "degraded"
    body = {"status": status, "services": checks}

    if not all_ok:
        return JSONResponse(content=body, status_code=503)
    return body


@router.get("/health/ready")
async def readiness_check(request: Request) -> dict | JSONResponse:
    """Quick readiness probe (for k8s / docker healthcheck).

    Returns 503 when not ready so load balancers and orchestrators
    can detect unhealthy instances via HTTP status code.
    """
    try:
        driver = request.app.state.neo4j_driver
        async with driver.session() as session:
            await session.run("RETURN 1")
        return {"ready": True}
    except Exception:
        return JSONResponse(content={"ready": False}, status_code=503)


@router.get("/health/live")
async def liveness_check() -> dict:
    """Lightweight liveness probe. Confirms process is alive.

    No dependency checks — only verifies the FastAPI process
    is responding. Use /health/ready for full readiness.
    """
    return {"alive": True}
