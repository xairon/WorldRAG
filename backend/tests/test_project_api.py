"""Tests for app.api.routes.projects — Project CRUD API.

Uses TestClient with mock ProjectService. No real database connections.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)

PROJECT_ROW = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "slug": "primal-hunter",
    "name": "The Primal Hunter",
    "description": "A LitRPG saga",
    "cover_image": None,
    "created_at": NOW,
    "updated_at": NOW,
    "books_count": 0,
    "has_profile": False,
    "entity_count": 0,
}

STATS_ROW = {
    "slug": "primal-hunter",
    "books_count": 0,
    "chapters_total": 0,
    "entities_total": 0,
    "community_count": 0,
    "has_profile": False,
    "profile_types_count": 0,
}


def _make_service(
    *,
    create_return=None,
    get_return=None,
    list_return=None,
    update_return=None,
    stats_return=None,
) -> AsyncMock:
    """Return a mock ProjectService with sensible defaults."""
    svc = AsyncMock()
    svc.create_project = AsyncMock(return_value=create_return or PROJECT_ROW)
    svc.get_project = AsyncMock(return_value=get_return)
    svc.list_projects = AsyncMock(return_value=list_return or [])
    svc.update_project = AsyncMock(return_value=update_return or PROJECT_ROW)
    svc.delete_project = AsyncMock(return_value=None)
    svc.get_stats = AsyncMock(return_value=stats_return or STATS_ROW)
    svc.store_book_file = AsyncMock(return_value=None)
    return svc


def _build_app(mock_service: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app with the projects router, using a patched ProjectService."""
    from app.api.routes import projects
    from app.api.auth import require_auth

    app = FastAPI()
    # Provide state so _get_service can read it (values are not used since
    # ProjectService is patched, but FastAPI resolves state attributes at setup)
    app.state.pg_pool = MagicMock()
    app.state.redis = AsyncMock()
    app.state.neo4j_driver = MagicMock()
    app.state.arq_pool = AsyncMock()

    # Override auth to skip token checks
    app.dependency_overrides[require_auth] = lambda: "test"
    app.include_router(projects.router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateProject:
    def test_create_returns_201(self) -> None:
        """POST /projects returns 201 with the created project."""
        svc = _make_service(get_return=None, create_return=PROJECT_ROW)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.post(
                    "/projects",
                    json={"slug": "primal-hunter", "name": "The Primal Hunter", "description": "A LitRPG saga"},
                )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "primal-hunter"
        assert data["name"] == "The Primal Hunter"

    def test_create_duplicate_slug_returns_409(self) -> None:
        """POST /projects returns 409 when slug already exists."""
        svc = _make_service(get_return=PROJECT_ROW)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.post(
                    "/projects",
                    json={"slug": "primal-hunter", "name": "Duplicate"},
                )
        assert resp.status_code == 409
        body = resp.json()
        assert "primal-hunter" in body["detail"] or "exists" in body["detail"].lower()


class TestListProjects:
    def test_list_returns_200_empty(self) -> None:
        """GET /projects returns 200 with empty list."""
        svc = _make_service(list_return=[])
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.get("/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []
        assert data["total"] == 0

    def test_list_returns_all_projects(self) -> None:
        """GET /projects returns all projects with total count."""
        svc = _make_service(list_return=[PROJECT_ROW])
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.get("/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["projects"][0]["slug"] == "primal-hunter"


class TestGetProject:
    def test_get_nonexistent_returns_404(self) -> None:
        """GET /projects/{slug} returns 404 when slug is unknown."""
        svc = _make_service(get_return=None)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.get("/projects/does-not-exist")
        assert resp.status_code == 404

    def test_get_existing_returns_200(self) -> None:
        """GET /projects/{slug} returns 200 with project data."""
        svc = _make_service(get_return=PROJECT_ROW)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.get("/projects/primal-hunter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "primal-hunter"


class TestUpdateProject:
    def test_update_returns_200(self) -> None:
        """PUT /projects/{slug} returns 200 with updated project."""
        updated = {**PROJECT_ROW, "name": "Updated Name"}
        svc = _make_service(get_return=PROJECT_ROW, update_return=updated)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.put("/projects/primal-hunter", json={"name": "Updated Name"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"

    def test_update_nonexistent_returns_404(self) -> None:
        """PUT /projects/{slug} returns 404 when project not found."""
        svc = _make_service(get_return=None, update_return=None)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.put("/projects/ghost", json={"name": "Ghost"})
        assert resp.status_code == 404


class TestDeleteProject:
    def test_delete_existing_returns_200(self) -> None:
        """DELETE /projects/{slug} returns 200 with deleted slug."""
        svc = _make_service(get_return=PROJECT_ROW)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.delete("/projects/primal-hunter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == "primal-hunter"

    def test_delete_nonexistent_returns_404(self) -> None:
        """DELETE /projects/{slug} returns 404 when project not found."""
        svc = _make_service(get_return=None)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.delete("/projects/ghost")
        assert resp.status_code == 404


class TestGetStats:
    def test_stats_returns_200(self) -> None:
        """GET /projects/{slug}/stats returns 200 with stats."""
        svc = _make_service(get_return=PROJECT_ROW)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.get("/projects/primal-hunter/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "primal-hunter"
        assert "books_count" in data

    def test_stats_nonexistent_returns_404(self) -> None:
        """GET /projects/{slug}/stats returns 404 when project not found."""
        svc = _make_service(get_return=None)
        with patch("app.api.routes.projects.ProjectService", return_value=svc):
            app = _build_app(svc)
            with TestClient(app, raise_server_exceptions=True) as c:
                resp = c.get("/projects/ghost/stats")
        assert resp.status_code == 404
