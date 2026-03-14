"""Tests for BookIngestionOrchestrator — Discovery and Guided ingestion modes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingestion.graphiti_ingest import BookIngestionOrchestrator
from app.services.saga_profile.models import (
    InducedEntityType,
    InducedRelationType,
    SagaProfile,
)
from app.services.saga_profile.pydantic_generator import _UNIVERSAL_TYPES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_graphiti():
    """Mocked GraphitiClient with AsyncMock ingest_chapter."""
    client = MagicMock()
    client.ingest_chapter = AsyncMock(return_value=None)
    return client


@pytest.fixture
def orchestrator(mock_graphiti):
    return BookIngestionOrchestrator(graphiti=mock_graphiti)


@pytest.fixture
def sample_chapters():
    return [
        {"number": 1, "text": "Chapter one text."},
        {"number": 2, "text": "Chapter two text."},
        {"number": 3, "text": "Chapter three text."},
    ]


@pytest.fixture
def minimal_profile():
    """SagaProfile with two induced entity types and one relation."""
    return SagaProfile(
        saga_id="saga-001",
        saga_name="The Primal Hunter",
        source_book="book-001",
        entity_types=[
            InducedEntityType(
                type_name="Skill",
                parent_universal="Concept",
                description="A LitRPG skill",
                typical_attributes=["level", "mana_cost"],
                confidence=0.95,
            ),
            InducedEntityType(
                type_name="Class",
                parent_universal="Concept",
                description="A LitRPG class",
                typical_attributes=["tier"],
                confidence=0.90,
            ),
        ],
        relation_types=[
            InducedRelationType(
                relation_name="has_skill",
                source_type="Character",
                target_type="Skill",
                cardinality="1:N",
                temporal=True,
                description="Character possesses a skill",
            )
        ],
        text_patterns=[],
    )


# ---------------------------------------------------------------------------
# Discovery mode tests
# ---------------------------------------------------------------------------


class TestDiscoveryMode:
    async def test_uses_only_universal_types(self, orchestrator, mock_graphiti, sample_chapters):
        """Discovery mode must pass exactly the 6 universal entity types."""
        await orchestrator.ingest_discovery(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
        )

        for call_args in mock_graphiti.ingest_chapter.call_args_list:
            entity_types = call_args.kwargs.get("entity_types", call_args.args[0] if call_args.args else None)
            assert set(entity_types.keys()) == set(_UNIVERSAL_TYPES.keys()), (
                f"Expected universal types only, got: {set(entity_types.keys())}"
            )

    async def test_no_edge_types_in_discovery(self, orchestrator, mock_graphiti, sample_chapters):
        """Discovery mode must not pass any edge_types."""
        await orchestrator.ingest_discovery(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
        )

        for call_args in mock_graphiti.ingest_chapter.call_args_list:
            # edge_types and edge_type_map should not be present or be empty/None
            edge_types = call_args.kwargs.get("edge_types")
            assert not edge_types, f"Discovery mode should have no edge_types, got: {edge_types}"

    async def test_ingests_all_chapters_sequentially(self, orchestrator, mock_graphiti, sample_chapters):
        """Discovery mode must call ingest_chapter once per chapter."""
        await orchestrator.ingest_discovery(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
        )

        assert mock_graphiti.ingest_chapter.await_count == len(sample_chapters)

    async def test_single_chapter(self, orchestrator, mock_graphiti):
        """Discovery mode with a single chapter calls ingest_chapter once."""
        chapters = [{"number": 1, "text": "Only chapter."}]
        await orchestrator.ingest_discovery(
            chapters=chapters,
            book_id="book-x",
            book_num=1,
            saga_id="saga-x",
        )
        assert mock_graphiti.ingest_chapter.await_count == 1

    async def test_empty_chapters(self, orchestrator, mock_graphiti):
        """Discovery mode with no chapters calls ingest_chapter zero times."""
        await orchestrator.ingest_discovery(
            chapters=[],
            book_id="book-x",
            book_num=1,
            saga_id="saga-x",
        )
        assert mock_graphiti.ingest_chapter.await_count == 0


# ---------------------------------------------------------------------------
# Guided mode tests
# ---------------------------------------------------------------------------


class TestGuidedMode:
    async def test_includes_induced_entity_types(
        self, orchestrator, mock_graphiti, sample_chapters, minimal_profile
    ):
        """Guided mode must include induced types on top of universal types."""
        await orchestrator.ingest_guided(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
            profile=minimal_profile,
        )

        induced_names = {e.type_name for e in minimal_profile.entity_types}
        for call_args in mock_graphiti.ingest_chapter.call_args_list:
            entity_types = call_args.kwargs.get("entity_types", call_args.args[0] if call_args.args else None)
            assert induced_names.issubset(set(entity_types.keys())), (
                f"Induced types {induced_names} not found in {set(entity_types.keys())}"
            )

    async def test_includes_universal_types_in_guided(
        self, orchestrator, mock_graphiti, sample_chapters, minimal_profile
    ):
        """Guided mode must still include all universal types."""
        await orchestrator.ingest_guided(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
            profile=minimal_profile,
        )

        for call_args in mock_graphiti.ingest_chapter.call_args_list:
            entity_types = call_args.kwargs.get("entity_types", call_args.args[0] if call_args.args else None)
            assert set(_UNIVERSAL_TYPES.keys()).issubset(set(entity_types.keys()))

    async def test_passes_edge_types(
        self, orchestrator, mock_graphiti, sample_chapters, minimal_profile
    ):
        """Guided mode must pass edge_types derived from relation_types."""
        await orchestrator.ingest_guided(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
            profile=minimal_profile,
        )

        expected_relation = minimal_profile.relation_types[0].relation_name
        for call_args in mock_graphiti.ingest_chapter.call_args_list:
            edge_types = call_args.kwargs.get("edge_types")
            assert edge_types is not None, "edge_types must be passed in guided mode"
            assert expected_relation in edge_types

    async def test_passes_edge_type_map(
        self, orchestrator, mock_graphiti, sample_chapters, minimal_profile
    ):
        """Guided mode must pass edge_type_map."""
        await orchestrator.ingest_guided(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
            profile=minimal_profile,
        )

        for call_args in mock_graphiti.ingest_chapter.call_args_list:
            edge_type_map = call_args.kwargs.get("edge_type_map")
            assert edge_type_map is not None, "edge_type_map must be passed in guided mode"
            # Check that the expected (source, target) pair is present
            assert ("Character", "Skill") in edge_type_map

    async def test_ingests_all_chapters_sequentially(
        self, orchestrator, mock_graphiti, sample_chapters, minimal_profile
    ):
        """Guided mode must call ingest_chapter once per chapter."""
        await orchestrator.ingest_guided(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
            profile=minimal_profile,
        )

        assert mock_graphiti.ingest_chapter.await_count == len(sample_chapters)

    async def test_guided_more_types_than_discovery(
        self, orchestrator, mock_graphiti, sample_chapters, minimal_profile
    ):
        """Guided mode entity_types dict is strictly larger than universal types."""
        await orchestrator.ingest_guided(
            chapters=sample_chapters,
            book_id="book-123",
            book_num=1,
            saga_id="saga-001",
            profile=minimal_profile,
        )

        first_call = mock_graphiti.ingest_chapter.call_args_list[0]
        entity_types = first_call.kwargs.get("entity_types")
        assert len(entity_types) > len(_UNIVERSAL_TYPES)
