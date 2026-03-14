"""Tests for GraphitiClient — thin wrapper around graphiti_core.Graphiti."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_graphiti() -> MagicMock:
    """Return a MagicMock shaped like a Graphiti instance."""
    instance = MagicMock()
    instance.build_indices_and_constraints = AsyncMock()
    instance.add_episode = AsyncMock()
    instance.search = AsyncMock(return_value=[])
    instance.close = AsyncMock()
    return instance


# ---------------------------------------------------------------------------
# Test: __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_creates_graphiti_instance(self):
        """GraphitiClient.__init__ instantiates a Graphiti object."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )

        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("uri") == "bolt://localhost:7687"
        assert call_kwargs.kwargs.get("user") == "neo4j"
        assert call_kwargs.kwargs.get("password") == "password"

    def test_init_forwards_optional_llm_and_embedder(self):
        """GraphitiClient passes llm_client and embedder to Graphiti when provided."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)
        fake_llm = MagicMock()
        fake_embedder = MagicMock()

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
                llm_client=fake_llm,
                embedder=fake_embedder,
            )

        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("llm_client") is fake_llm
        assert call_kwargs.kwargs.get("embedder") is fake_embedder

    def test_init_llm_and_embedder_default_to_none(self):
        """GraphitiClient passes None for llm_client and embedder by default."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )

        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("llm_client") is None
        assert call_kwargs.kwargs.get("embedder") is None


# ---------------------------------------------------------------------------
# Test: init_schema
# ---------------------------------------------------------------------------


class TestInitSchema:
    @pytest.mark.asyncio
    async def test_init_schema_calls_build_indices(self):
        """init_schema() delegates to Graphiti.build_indices_and_constraints()."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.init_schema()

        mock_instance.build_indices_and_constraints.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test: close
# ---------------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_delegates_to_graphiti_close(self):
        """close() delegates to the underlying Graphiti.close()."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.close()

        mock_instance.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test: search
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_delegates_with_group_ids_and_num_results(self):
        """search() calls client.search() with saga_id as group_ids filter."""
        mock_instance = _make_mock_graphiti()
        mock_instance.search = AsyncMock(return_value=["result_a", "result_b"])
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            results = await client.search(
                query="who is Jake?",
                saga_id="primal_hunter",
                num_results=10,
            )

        mock_instance.search.assert_awaited_once()
        call_kwargs = mock_instance.search.call_args
        group_ids = call_kwargs.kwargs.get("group_ids")
        assert group_ids == ["primal_hunter"]
        assert call_kwargs.kwargs.get("num_results") == 10
        assert results == ["result_a", "result_b"]

    @pytest.mark.asyncio
    async def test_search_uses_default_num_results(self):
        """search() defaults num_results to 20."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.search(query="test", saga_id="saga_x")

        call_kwargs = mock_instance.search.call_args
        assert call_kwargs.kwargs.get("num_results") == 20


# ---------------------------------------------------------------------------
# Test: ingest_chapter
# ---------------------------------------------------------------------------


class TestIngestChapter:
    @pytest.mark.asyncio
    async def test_ingest_chapter_calls_add_episode(self):
        """ingest_chapter() calls Graphiti.add_episode() once."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.ingest_chapter(
                chapter_text="Jake fought the Hydra.",
                book_id="book-001",
                book_num=1,
                chapter_num=42,
                saga_id="primal_hunter",
            )

        mock_instance.add_episode.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ingest_chapter_uses_narrative_temporal_mapper(self):
        """ingest_chapter() derives reference_time via NarrativeTemporalMapper."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.ingest_chapter(
                chapter_text="Some content.",
                book_id="book-001",
                book_num=2,
                chapter_num=5,
                saga_id="primal_hunter",
            )

        call_kwargs = mock_instance.add_episode.call_args
        reference_time = call_kwargs.kwargs.get("reference_time")
        assert reference_time is not None
        # NarrativeTemporalMapper.to_datetime(2, 5) => EPOCH + timedelta(days=10_005)
        expected = datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=10_005)
        assert reference_time == expected

    @pytest.mark.asyncio
    async def test_ingest_chapter_uses_episode_type_text(self):
        """ingest_chapter() sets source as EpisodeType.text."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient
            from graphiti_core.nodes import EpisodeType

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.ingest_chapter(
                chapter_text="Content here.",
                book_id="book-001",
                book_num=1,
                chapter_num=1,
                saga_id="primal_hunter",
            )

        call_kwargs = mock_instance.add_episode.call_args
        source = call_kwargs.kwargs.get("source")
        assert source == EpisodeType.text

    @pytest.mark.asyncio
    async def test_ingest_chapter_passes_group_id_as_saga_id(self):
        """ingest_chapter() forwards saga_id as group_id to add_episode."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.ingest_chapter(
                chapter_text="Some text.",
                book_id="book-001",
                book_num=1,
                chapter_num=10,
                saga_id="saga_y",
            )

        call_kwargs = mock_instance.add_episode.call_args
        assert call_kwargs.kwargs.get("group_id") == "saga_y"

    @pytest.mark.asyncio
    async def test_ingest_chapter_passes_entity_types_and_edge_types(self):
        """Optional entity_types, edge_types and edge_type_map are forwarded."""
        mock_instance = _make_mock_graphiti()
        mock_cls = MagicMock(return_value=mock_instance)
        entity_types = {"Character": MagicMock()}
        edge_types = {"KNOWS": MagicMock()}
        edge_type_map = {("Character", "Character"): ["KNOWS"]}

        with patch("app.core.graphiti_client.Graphiti", mock_cls):
            from app.core.graphiti_client import GraphitiClient

            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_auth=("neo4j", "password"),
            )
            await client.ingest_chapter(
                chapter_text="Some text.",
                book_id="book-001",
                book_num=1,
                chapter_num=10,
                saga_id="saga_y",
                entity_types=entity_types,
                edge_types=edge_types,
                edge_type_map=edge_type_map,
            )

        call_kwargs = mock_instance.add_episode.call_args
        assert call_kwargs.kwargs.get("entity_types") == entity_types
        assert call_kwargs.kwargs.get("edge_types") == edge_types
        assert call_kwargs.kwargs.get("edge_type_map") == edge_type_map
