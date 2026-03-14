"""Tests for Leiden community clustering module.

All tests use mocked Neo4j driver and LLM calls — no external services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.community_clustering import run_community_clustering


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_driver(communities_data: list[dict] | None = None, raise_on_run: bool = False):
    """Build a mock AsyncDriver whose session.run() behaves as specified."""
    session = AsyncMock()

    if raise_on_run:
        session.run = AsyncMock(side_effect=Exception("GDS unavailable"))
    else:
        # session.run() returns a result object; only the MATCH query needs .data()
        async def _run(query, **kwargs):
            result = AsyncMock()
            result.data = AsyncMock(return_value=communities_data or [])
            return result

        session.run = AsyncMock(side_effect=_run)

    # Support `async with driver.session() as session`
    driver = MagicMock()
    ctx_manager = AsyncMock()
    ctx_manager.__aenter__ = AsyncMock(return_value=session)
    ctx_manager.__aexit__ = AsyncMock(return_value=False)
    driver.session = MagicMock(return_value=ctx_manager)
    return driver, session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClusteringRunsGdsPipeline:
    """Verifies happy-path GDS pipeline execution and community creation."""

    @pytest.mark.asyncio
    async def test_clustering_runs_gds_pipeline(self):
        """Mock driver/session, verify returns communities_found."""
        communities_data = [
            {
                "community_id": 1,
                "names": ["Arthur", "Merlin"],
                "summaries": ["Hero", "Wizard"],
            },
            {
                "community_id": 2,
                "names": ["Mordred", "Morgan"],
                "summaries": ["Villain", "Sorceress"],
            },
        ]
        driver, session = _make_mock_driver(communities_data=communities_data)

        with patch(
            "app.services.community_clustering._summarize_community",
            new=AsyncMock(return_value="A group of interlinked fiction entities."),
        ):
            result = await run_community_clustering(driver, saga_id="saga-001")

        assert result["communities_found"] == 2
        assert result["saga_id"] == "saga-001"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_clustering_returns_zero_when_no_communities(self):
        """Returns communities_found=0 when the graph has no qualifying communities."""
        driver, _ = _make_mock_driver(communities_data=[])

        with patch(
            "app.services.community_clustering._summarize_community",
            new=AsyncMock(return_value="summary"),
        ):
            result = await run_community_clustering(driver, saga_id="saga-empty")

        assert result["communities_found"] == 0
        assert result["saga_id"] == "saga-empty"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_clustering_writes_community_nodes(self):
        """Community MERGE Cypher is called once per detected community."""
        communities_data = [
            {
                "community_id": 42,
                "names": ["Alpha", "Beta", "Gamma"],
                "summaries": ["s1", "s2", "s3"],
            },
        ]
        driver, session = _make_mock_driver(communities_data=communities_data)

        with patch(
            "app.services.community_clustering._summarize_community",
            new=AsyncMock(return_value="Three entities form a tight cluster."),
        ):
            await run_community_clustering(driver, saga_id="saga-write")

        # session.run must have been called at least for: project, leiden, match, merge, drop
        assert session.run.call_count >= 5


class TestClusteringHandlesGdsUnavailable:
    """Verifies graceful fallback when GDS is not available."""

    @pytest.mark.asyncio
    async def test_clustering_handles_gds_unavailable(self):
        """session.run raises Exception → graceful fallback with error in result."""
        driver, _ = _make_mock_driver(raise_on_run=True)

        result = await run_community_clustering(driver, saga_id="saga-fail")

        assert result["communities_found"] == 0
        assert result["saga_id"] == "saga-fail"
        assert "error" in result
        assert len(result["error"]) > 0

    @pytest.mark.asyncio
    async def test_clustering_error_does_not_raise(self):
        """Any GDS exception is swallowed — run_community_clustering never raises."""
        driver, _ = _make_mock_driver(raise_on_run=True)

        # Must not raise
        result = await run_community_clustering(driver, saga_id="saga-no-raise")
        assert isinstance(result, dict)
