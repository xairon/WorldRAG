"""Tests for entity/relationship mutation endpoints on /graph.

Covers:
  PATCH  /graph/entity/{entity_id}
  DELETE /graph/entity/{entity_id}
  POST   /graph/entities/merge
  DELETE /graph/relationship/{relationship_id}
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.api.routes.graph import router
from app.core.exceptions import WorldRAGError

if TYPE_CHECKING:
    from starlette.requests import Request

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENTITY_ID = "4:abc:1"
_REL_ID = "5:def:2"
_SOURCE_ID = "4:src:1"
_TARGET_ID = "4:tgt:2"


def _make_summary(*, nodes_deleted: int = 0, relationships_deleted: int = 0) -> MagicMock:
    summary = MagicMock()
    summary.counters.nodes_deleted = nodes_deleted
    summary.counters.relationships_deleted = relationships_deleted
    summary.counters.nodes_created = 0
    summary.counters.relationships_created = 0
    summary.counters.properties_set = 0
    return summary


def _make_repo(
    *,
    read_results: list | None = None,
    write_results: list | None = None,
    write_summary: MagicMock | None = None,
) -> MagicMock:
    """Return a patched Neo4jRepository with controllable return values."""
    repo = MagicMock()
    repo.execute_read = AsyncMock(return_value=read_results or [])
    repo.execute_write = AsyncMock(return_value=write_results or [])
    repo.execute_write_with_summary = AsyncMock(
        return_value=(write_results or [], write_summary or _make_summary())
    )
    return repo


def _make_app(repo: MagicMock) -> FastAPI:
    from app.api.auth import require_auth
    from app.api.dependencies import get_neo4j

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_auth] = lambda: None
    app.dependency_overrides[get_neo4j] = lambda: AsyncMock()  # driver (unused — repo patched)

    @app.exception_handler(WorldRAGError)
    async def worldrag_error_handler(request: Request, exc: WorldRAGError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": type(exc).__name__, "detail": exc.detail},
        )

    return app


# ---------------------------------------------------------------------------
# PATCH /graph/entity/{entity_id}
# ---------------------------------------------------------------------------


class TestUpdateEntity:
    async def _call(self, repo: MagicMock, body: dict) -> tuple:
        app = _make_app(repo)
        with patch("app.api.routes.graph.Neo4jRepository", return_value=repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.patch(f"/api/graph/entity/{_ENTITY_ID}", json=body)
        return resp, resp.json()

    @pytest.mark.asyncio
    async def test_update_name_returns_200(self):
        repo = _make_repo(read_results=[{"labels": ["Character", "Entity"]}])
        resp, body = await self._call(repo, {"name": "Jake Thayne"})
        assert resp.status_code == 200
        assert body["id"] == _ENTITY_ID
        assert "name" in body["updated_properties"]
        assert body["labels"] == ["Character", "Entity"]

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self):
        repo = _make_repo(read_results=[{"labels": ["Character"]}])
        resp, body = await self._call(
            repo, {"name": "Jake", "canonical_name": "Jake Thayne", "description": "An archer"}
        )
        assert resp.status_code == 200
        assert set(body["updated_properties"]) == {"name", "canonical_name", "description"}

    @pytest.mark.asyncio
    async def test_400_when_no_valid_fields(self):
        repo = _make_repo()
        resp, body = await self._call(repo, {"unknown_field": "value"})
        assert resp.status_code == 400
        assert "name" in body["detail"] or "canonical_name" in body["detail"]

    @pytest.mark.asyncio
    async def test_400_when_all_none(self):
        repo = _make_repo()
        resp, body = await self._call(repo, {"name": None, "description": None})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_404_when_entity_not_found(self):
        # execute_read returns [] → entity not found
        repo = _make_repo(read_results=[])
        resp, body = await self._call(repo, {"name": "Jake"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_write_called_with_set_clause(self):
        repo = _make_repo(read_results=[{"labels": ["Character"]}])
        await self._call(repo, {"name": "Jake"})
        # execute_write must have been called once (for the SET)
        repo.execute_write.assert_called_once()
        call_query = repo.execute_write.call_args[0][0]
        assert "SET" in call_query
        assert "n.name" in call_query


# ---------------------------------------------------------------------------
# DELETE /graph/entity/{entity_id}
# ---------------------------------------------------------------------------


class TestDeleteEntity:
    async def _call(self, repo: MagicMock) -> tuple:
        app = _make_app(repo)
        with patch("app.api.routes.graph.Neo4jRepository", return_value=repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.delete(f"/api/graph/entity/{_ENTITY_ID}")
        return resp, resp.json()

    @pytest.mark.asyncio
    async def test_delete_returns_200_with_counts(self):
        repo = _make_repo(
            read_results=[{"cnt": 3}],
            write_summary=_make_summary(nodes_deleted=1),
        )
        resp, body = await self._call(repo)
        assert resp.status_code == 200
        assert body["deleted"] is True
        assert body["relationships_removed"] == 3

    @pytest.mark.asyncio
    async def test_delete_zero_relationships(self):
        repo = _make_repo(
            read_results=[{"cnt": 0}],
            write_summary=_make_summary(nodes_deleted=1),
        )
        resp, body = await self._call(repo)
        assert resp.status_code == 200
        assert body["relationships_removed"] == 0

    @pytest.mark.asyncio
    async def test_404_when_entity_not_found(self):
        repo = _make_repo(
            read_results=[{"cnt": 0}],
            write_summary=_make_summary(nodes_deleted=0),
        )
        resp, body = await self._call(repo)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_detach_delete_cypher_used(self):
        repo = _make_repo(
            read_results=[{"cnt": 1}],
            write_summary=_make_summary(nodes_deleted=1),
        )
        await self._call(repo)
        call_query = repo.execute_write_with_summary.call_args[0][0]
        assert "DETACH DELETE" in call_query


# ---------------------------------------------------------------------------
# POST /graph/entities/merge
# ---------------------------------------------------------------------------


class TestMergeEntities:
    def _repo_for_merge(
        self,
        *,
        source_props: dict | None = None,
        target_props: dict | None = None,
        out_rels: list | None = None,
        in_rels: list | None = None,
    ) -> MagicMock:
        """Build a repo mock that returns different values per call sequence."""
        source_props = source_props or {
            "name": "Jake",
            "canonical_name": "Jake Thayne",
            "aliases": [],
        }
        target_props = target_props or {
            "name": "Thayne",
            "canonical_name": "Thayne",
            "aliases": ["Chosen"],
        }

        # execute_read call sequence:
        #  0 → source entity fetch
        #  1 → target entity fetch
        #  2 → outgoing rels
        #  3 → incoming rels
        side_effects = [
            [{"props": source_props, "labels": ["Character"]}],
            [{"props": target_props, "labels": ["Character"]}],
            out_rels or [],
            in_rels or [],
        ]
        repo = MagicMock()
        repo.execute_read = AsyncMock(side_effect=side_effects)
        repo.execute_write = AsyncMock(return_value=[])
        repo.execute_write_with_summary = AsyncMock(
            return_value=([], _make_summary(nodes_deleted=1))
        )
        return repo

    async def _call(self, repo: MagicMock, body: dict) -> tuple:
        app = _make_app(repo)
        with patch("app.api.routes.graph.Neo4jRepository", return_value=repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/graph/entities/merge", json=body)
        return resp, resp.json()

    @pytest.mark.asyncio
    async def test_merge_happy_path(self):
        repo = self._repo_for_merge()
        resp, body = await self._call(repo, {"source_id": _SOURCE_ID, "target_id": _TARGET_ID})
        assert resp.status_code == 200
        assert body["merged_into"] == _TARGET_ID
        assert isinstance(body["aliases_added"], list)
        assert isinstance(body["relationships_transferred"], int)

    @pytest.mark.asyncio
    async def test_merge_transfers_relationships(self):
        out_rels = [{"rel_type": "KNOWS", "other_id": "4:x:1", "props": {"weight": 1}}]
        in_rels = [{"rel_type": "MEMBER_OF", "other_id": "4:y:1", "props": {}}]
        repo = self._repo_for_merge(out_rels=out_rels, in_rels=in_rels)
        resp, body = await self._call(repo, {"source_id": _SOURCE_ID, "target_id": _TARGET_ID})
        assert resp.status_code == 200
        assert body["relationships_transferred"] == 2

    @pytest.mark.asyncio
    async def test_merge_adds_source_names_as_aliases(self):
        source_props = {"name": "Jake", "canonical_name": "Jake Thayne", "aliases": ["Jake-o"]}
        target_props = {"name": "Thayne", "canonical_name": "Thayne", "aliases": []}
        repo = self._repo_for_merge(source_props=source_props, target_props=target_props)
        resp, body = await self._call(repo, {"source_id": _SOURCE_ID, "target_id": _TARGET_ID})
        assert resp.status_code == 200
        # "Jake", "Jake Thayne", "Jake-o" should all be added (they differ from target name)
        assert "Jake" in body["aliases_added"]

    @pytest.mark.asyncio
    async def test_400_same_id(self):
        repo = _make_repo()
        resp, body = await self._call(repo, {"source_id": _SOURCE_ID, "target_id": _SOURCE_ID})
        assert resp.status_code == 400
        assert "different" in body["detail"]

    @pytest.mark.asyncio
    async def test_400_missing_source_id(self):
        repo = _make_repo()
        resp, body = await self._call(repo, {"target_id": _TARGET_ID})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_400_missing_target_id(self):
        repo = _make_repo()
        resp, body = await self._call(repo, {"source_id": _SOURCE_ID})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_404_source_not_found(self):
        repo = MagicMock()
        # Both calls in asyncio.gather return [] — source check fires first
        repo.execute_read = AsyncMock(return_value=[])
        repo.execute_write = AsyncMock(return_value=[])
        repo.execute_write_with_summary = AsyncMock(return_value=([], _make_summary()))
        app = _make_app(repo)
        with patch("app.api.routes.graph.Neo4jRepository", return_value=repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/graph/entities/merge",
                    json={"source_id": _SOURCE_ID, "target_id": _TARGET_ID},
                )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_404_target_not_found(self):
        repo = MagicMock()
        source_row = [{"props": {"name": "Jake", "aliases": []}, "labels": ["Character"]}]
        empty_row: list = []

        call_count = 0

        async def read_side_effect(query: str, params: dict) -> list:
            nonlocal call_count
            # Identify target query by param value
            if params.get("id") == _TARGET_ID:
                return empty_row
            return source_row

        repo.execute_read = AsyncMock(side_effect=read_side_effect)
        repo.execute_write = AsyncMock(return_value=[])
        repo.execute_write_with_summary = AsyncMock(return_value=([], _make_summary()))
        app = _make_app(repo)
        with patch("app.api.routes.graph.Neo4jRepository", return_value=repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/graph/entities/merge",
                    json={"source_id": _SOURCE_ID, "target_id": _TARGET_ID},
                )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_duplicate_aliases_added(self):
        source_props = {"name": "Thayne", "canonical_name": "Thayne", "aliases": []}
        target_props = {"name": "Thayne", "canonical_name": "Thayne", "aliases": []}
        repo = self._repo_for_merge(source_props=source_props, target_props=target_props)
        resp, body = await self._call(repo, {"source_id": _SOURCE_ID, "target_id": _TARGET_ID})
        assert resp.status_code == 200
        # "Thayne" is already the target name — should NOT be added
        assert "Thayne" not in body["aliases_added"]


# ---------------------------------------------------------------------------
# DELETE /graph/relationship/{relationship_id}
# ---------------------------------------------------------------------------


class TestDeleteRelationship:
    async def _call(self, repo: MagicMock) -> tuple:
        app = _make_app(repo)
        with patch("app.api.routes.graph.Neo4jRepository", return_value=repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.delete(f"/api/graph/relationship/{_REL_ID}")
        return resp, resp.json()

    @pytest.mark.asyncio
    async def test_delete_returns_200(self):
        repo = _make_repo(write_summary=_make_summary(relationships_deleted=1))
        resp, body = await self._call(repo)
        assert resp.status_code == 200
        assert body["deleted"] is True

    @pytest.mark.asyncio
    async def test_404_when_relationship_not_found(self):
        repo = _make_repo(write_summary=_make_summary(relationships_deleted=0))
        resp, body = await self._call(repo)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_cypher_uses_element_id(self):
        repo = _make_repo(write_summary=_make_summary(relationships_deleted=1))
        await self._call(repo)
        call_query = repo.execute_write_with_summary.call_args[0][0]
        assert "elementId(r)" in call_query
        assert "DELETE r" in call_query
