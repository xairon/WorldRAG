"""Tests for POST /books/{book_id}/extract-graphiti endpoint.

Covers discovery mode (no existing saga profile), guided mode (existing
profile in Redis), and validation errors.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.books import router


def _make_job_mock(job_id: str = "graphiti:book-123") -> MagicMock:
    """Return a mock arq Job with a .job_id attribute."""
    job = MagicMock()
    job.job_id = job_id
    return job


def _create_app(
    *,
    redis_get_return=None,
    arq_job_id: str = "graphiti:book-123",
) -> FastAPI:
    """Build a minimal FastAPI app with the books router and mocked state."""
    app = FastAPI()
    app.include_router(router)

    # Neo4j driver mock (required by other routes imported at module level)
    app.state.neo4j_driver = AsyncMock()

    # arq pool mock
    arq_pool = AsyncMock()
    arq_pool.enqueue_job = AsyncMock(return_value=_make_job_mock(arq_job_id))
    app.state.arq_pool = arq_pool

    # Redis mock
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=redis_get_return)
    app.state.redis = redis

    return app


# ---------------------------------------------------------------------------
# Test: discovery mode (no saga profile in Redis)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_graphiti_discovery_mode() -> None:
    """When no saga profile exists in Redis, mode should be 'discovery'."""
    app = _create_app(redis_get_return=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/books/book-123/extract-graphiti",
            json={"saga_id": "cradle", "saga_name": "Cradle", "book_num": 1},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["mode"] == "discovery"
    assert data["book_id"] == "book-123"
    assert data["job_id"] == "graphiti:book-123"


@pytest.mark.asyncio
async def test_extract_graphiti_discovery_mode_enqueue_args() -> None:
    """In discovery mode, enqueue_job should be called with saga_profile_json=None."""
    app = _create_app(redis_get_return=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/books/book-42/extract-graphiti",
            json={"saga_id": "litrpg-saga", "saga_name": "LitRPG Saga", "book_num": 2},
        )

    arq_pool = app.state.arq_pool
    arq_pool.enqueue_job.assert_awaited_once()
    call_args = arq_pool.enqueue_job.call_args

    # First positional arg is the task name
    assert call_args.args[0] == "process_book_graphiti"
    # saga_profile_json (5th positional arg after task name) should be None
    positional = call_args.args
    assert positional[5] is None  # existing_profile = None in discovery mode


# ---------------------------------------------------------------------------
# Test: guided mode (saga profile found in Redis)
# ---------------------------------------------------------------------------

_FAKE_PROFILE_JSON = json.dumps({"saga_id": "cradle", "entity_types": []})


@pytest.mark.asyncio
async def test_extract_graphiti_guided_mode() -> None:
    """When a saga profile exists in Redis, mode should be 'guided'."""
    app = _create_app(redis_get_return=_FAKE_PROFILE_JSON)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/books/book-99/extract-graphiti",
            json={"saga_id": "cradle", "saga_name": "Cradle", "book_num": 3},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["mode"] == "guided"
    assert data["book_id"] == "book-99"


@pytest.mark.asyncio
async def test_extract_graphiti_guided_mode_passes_profile_json() -> None:
    """In guided mode, enqueue_job should receive the profile JSON string."""
    app = _create_app(redis_get_return=_FAKE_PROFILE_JSON)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/books/book-99/extract-graphiti",
            json={"saga_id": "cradle", "saga_name": "Cradle", "book_num": 1},
        )

    arq_pool = app.state.arq_pool
    arq_pool.enqueue_job.assert_awaited_once()
    call_args = arq_pool.enqueue_job.call_args
    positional = call_args.args

    # existing_profile should be the JSON string, not None
    assert positional[5] == _FAKE_PROFILE_JSON


@pytest.mark.asyncio
async def test_extract_graphiti_redis_get_key() -> None:
    """Redis.get should be called with the correct key pattern."""
    app = _create_app(redis_get_return=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/books/book-1/extract-graphiti",
            json={"saga_id": "my-saga", "saga_name": "My Saga", "book_num": 1},
        )

    app.state.redis.get.assert_awaited_once_with("saga_profile:my-saga")


# ---------------------------------------------------------------------------
# Test: validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_graphiti_empty_saga_id_returns_422() -> None:
    """Empty saga_id should fail Pydantic validation with 422."""
    app = _create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/books/book-1/extract-graphiti",
            json={"saga_id": "", "saga_name": "Test", "book_num": 1},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_extract_graphiti_missing_saga_name_returns_422() -> None:
    """Missing saga_name should fail Pydantic validation with 422."""
    app = _create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/books/book-1/extract-graphiti",
            json={"saga_id": "valid-id", "book_num": 1},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_extract_graphiti_invalid_saga_id_pattern_returns_422() -> None:
    """saga_id with invalid characters (spaces) should fail with 422."""
    app = _create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/books/book-1/extract-graphiti",
            json={"saga_id": "invalid id with spaces", "saga_name": "Test", "book_num": 1},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_extract_graphiti_job_id_format() -> None:
    """The job should be enqueued with _job_id=graphiti:{book_id}."""
    app = _create_app(redis_get_return=None, arq_job_id="graphiti:custom-book")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/books/custom-book/extract-graphiti",
            json={"saga_id": "saga-x", "saga_name": "Saga X", "book_num": 1},
        )

    arq_pool = app.state.arq_pool
    call_kwargs = arq_pool.enqueue_job.call_args.kwargs
    assert call_kwargs.get("_job_id") == "graphiti:custom-book"
    assert call_kwargs.get("_queue_name") == "worldrag:arq"
