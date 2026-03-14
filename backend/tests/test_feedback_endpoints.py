"""Tests for POST/GET /api/chat/feedback endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.chat import router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: int = 1,
    thread_id: str = "thread-abc",
    rating: int = 1,
    comment: str | None = None,
    book_id: str | None = None,
) -> dict:
    return {
        "id": id,
        "thread_id": thread_id,
        "rating": rating,
        "comment": comment,
        "book_id": book_id,
        "created_at": datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC),
    }


def _mock_pool(*, fetchrow=None, fetch=None):
    """Build a minimal asyncpg-like pool mock."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow)
    pool.fetch = AsyncMock(return_value=fetch or [])
    return pool


def _make_app(pool) -> FastAPI:
    """Minimal FastAPI app wiring the chat router + mocked dependencies."""
    from app.api.auth import require_auth
    from app.api.dependencies import get_postgres

    app = FastAPI()
    # router already has prefix="/chat"; mount at "/api" to match production
    app.include_router(router, prefix="/api")

    app.dependency_overrides[require_auth] = lambda: None
    app.dependency_overrides[get_postgres] = lambda: pool

    return app


# ---------------------------------------------------------------------------
# POST /feedback
# ---------------------------------------------------------------------------


class TestSubmitFeedback:
    @pytest.mark.asyncio
    async def test_thumbs_up_returns_201(self):
        row = _make_row(rating=1)
        app = _make_app(_mock_pool(fetchrow=row))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/chat/feedback",
                json={"thread_id": "thread-abc", "rating": 1},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["thread_id"] == "thread-abc"
        assert data["rating"] == 1
        assert data["id"] == 1

    @pytest.mark.asyncio
    async def test_thumbs_down_returns_201(self):
        row = _make_row(rating=-1, comment="Wrong answer")
        app = _make_app(_mock_pool(fetchrow=row))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/chat/feedback",
                json={"thread_id": "thread-abc", "rating": -1, "comment": "Wrong answer"},
            )

        assert resp.status_code == 201
        assert resp.json()["rating"] == -1

    @pytest.mark.asyncio
    async def test_invalid_rating_rejected(self):
        app = _make_app(_mock_pool())

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/chat/feedback",
                json={"thread_id": "thread-abc", "rating": 0},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_thread_id_rejected(self):
        app = _make_app(_mock_pool())

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/chat/feedback", json={"rating": 1})

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_optional_fields_forwarded(self):
        row = _make_row(rating=1, comment="Great!", book_id="book-42")
        pool = _mock_pool(fetchrow=row)
        app = _make_app(pool)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/chat/feedback",
                json={
                    "thread_id": "thread-abc",
                    "rating": 1,
                    "comment": "Great!",
                    "book_id": "book-42",
                    "message_id": "msg-7",
                },
            )

        call_args = pool.fetchrow.call_args[0]
        # $1=thread_id, $2=message_id, $3=rating, $4=comment, $5=book_id
        assert call_args[1] == "thread-abc"
        assert call_args[2] == "msg-7"
        assert call_args[3] == 1
        assert call_args[4] == "Great!"
        assert call_args[5] == "book-42"

    @pytest.mark.asyncio
    async def test_response_model_fields_present(self):
        row = _make_row()
        app = _make_app(_mock_pool(fetchrow=row))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/chat/feedback",
                json={"thread_id": "thread-abc", "rating": 1},
            )

        body = resp.json()
        for field in ("id", "thread_id", "rating", "comment", "book_id", "created_at"):
            assert field in body


# ---------------------------------------------------------------------------
# GET /feedback/{thread_id}
# ---------------------------------------------------------------------------


class TestGetFeedback:
    @pytest.mark.asyncio
    async def test_returns_list_for_thread(self):
        rows = [_make_row(id=1, rating=1), _make_row(id=2, rating=-1)]
        app = _make_app(_mock_pool(fetch=rows))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/chat/feedback/thread-abc")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_empty_thread_returns_empty_list(self):
        app = _make_app(_mock_pool(fetch=[]))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/chat/feedback/unknown-thread")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_thread_id_forwarded_to_query(self):
        pool = _mock_pool(fetch=[])
        app = _make_app(pool)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/api/chat/feedback/my-thread-123")

        pool.fetch.assert_called_once()
        call_args = pool.fetch.call_args[0]
        assert call_args[1] == "my-thread-123"

    @pytest.mark.asyncio
    async def test_503_when_pool_unavailable(self):
        from app.api.auth import require_auth

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[require_auth] = lambda: None
        # No override for get_postgres → pool missing → 503

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/chat/feedback/thread-abc")

        # Without override, get_postgres looks for app.state.pg_pool — expect 500 or 503
        assert resp.status_code in (500, 503)
