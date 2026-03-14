"""Tests for app.api.routes.saga_profiles — Saga Profiles CRUD API."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import saga_profiles
from app.services.saga_profile.models import SagaProfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAGA_ID = "primal-hunter"

PROFILE = SagaProfile(
    saga_id=SAGA_ID,
    saga_name="The Primal Hunter",
    source_book="The Primal Hunter Book 1",
    version=2,
    entity_types=[],
    relation_types=[],
    text_patterns=[],
    narrative_systems=["system: The Path"],
    estimated_complexity="high",
)

PROFILE_JSON = PROFILE.model_dump_json()


def _build_app(mock_redis: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app with the saga_profiles router and a mocked Redis."""
    app = FastAPI()
    app.state.redis = mock_redis
    # Mount router without auth (no require_auth in the test app)
    # We override by including the router's routes directly, bypassing dependencies
    test_router = saga_profiles.router
    app.include_router(test_router)
    return app


async def _async_iter(items):
    """Helper to create an async iterator from a list."""
    for item in items:
        yield item


def _make_redis(*, get_value: str | None = None, keys_value: list[str] | None = None) -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=get_value)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.scan_iter = lambda match=None: _async_iter(keys_value or [])
    return redis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> AsyncMock:
    return _make_redis()


@pytest.fixture
def client(mock_redis: AsyncMock) -> TestClient:
    app = _build_app(mock_redis)
    # Override auth dependency to be a no-op
    from app.api.auth import require_auth

    app.dependency_overrides[require_auth] = lambda: "test"
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetSagaProfile:
    def test_404_for_nonexistent_saga(self, mock_redis: AsyncMock) -> None:
        """GET /{saga_id} returns 404 when key is missing from Redis."""
        mock_redis.get = AsyncMock(return_value=None)
        app = _build_app(mock_redis)
        from app.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test"

        with TestClient(app) as c:
            resp = c.get(f"/saga-profiles/{SAGA_ID}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_200_for_existing_saga(self, mock_redis: AsyncMock) -> None:
        """GET /{saga_id} returns 200 with profile when key exists."""
        mock_redis.get = AsyncMock(return_value=PROFILE_JSON)
        app = _build_app(mock_redis)
        from app.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test"

        with TestClient(app) as c:
            resp = c.get(f"/saga-profiles/{SAGA_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["exists"] is True
        assert data["profile"]["saga_id"] == SAGA_ID
        assert data["profile"]["saga_name"] == "The Primal Hunter"
        assert data["profile"]["version"] == 2


class TestListSagaProfiles:
    def test_empty_list(self, mock_redis: AsyncMock) -> None:
        """GET / returns 200 with total=0 when no saga profiles exist."""
        mock_redis.scan_iter = lambda match=None: _async_iter([])
        app = _build_app(mock_redis)
        from app.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test"

        with TestClient(app) as c:
            resp = c.get("/saga-profiles")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["profiles"] == []

    def test_list_returns_all_profiles(self, mock_redis: AsyncMock) -> None:
        """GET / returns summary items for each key found in Redis."""
        mock_redis.scan_iter = lambda match=None: _async_iter([f"saga_profile:{SAGA_ID}"])
        mock_redis.get = AsyncMock(return_value=PROFILE_JSON)
        app = _build_app(mock_redis)
        from app.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test"

        with TestClient(app) as c:
            resp = c.get("/saga-profiles")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["profiles"][0]["saga_id"] == SAGA_ID
        assert data["profiles"][0]["saga_name"] == "The Primal Hunter"
        assert data["profiles"][0]["version"] == 2


class TestUpsertSagaProfile:
    def test_put_creates_profile(self, mock_redis: AsyncMock) -> None:
        """PUT /{saga_id} stores profile in Redis and returns 200."""
        app = _build_app(mock_redis)
        from app.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test"

        with TestClient(app) as c:
            resp = c.put(
                f"/saga-profiles/{SAGA_ID}",
                content=PROFILE_JSON,
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["exists"] is True
        assert data["profile"]["saga_id"] == SAGA_ID

        # Verify Redis.set was called with the correct key
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == f"saga_profile:{SAGA_ID}"


class TestDeleteSagaProfile:
    def test_delete_existing_returns_200(self, mock_redis: AsyncMock) -> None:
        """DELETE /{saga_id} returns 200 when key exists."""
        mock_redis.delete = AsyncMock(return_value=1)
        app = _build_app(mock_redis)
        from app.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test"

        with TestClient(app) as c:
            resp = c.delete(f"/saga-profiles/{SAGA_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == SAGA_ID
        mock_redis.delete.assert_called_once_with(f"saga_profile:{SAGA_ID}")

    def test_delete_nonexistent_returns_404(self, mock_redis: AsyncMock) -> None:
        """DELETE /{saga_id} returns 404 when key does not exist."""
        mock_redis.delete = AsyncMock(return_value=0)
        app = _build_app(mock_redis)
        from app.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test"

        with TestClient(app) as c:
            resp = c.delete(f"/saga-profiles/nonexistent")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
