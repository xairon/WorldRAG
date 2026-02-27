"""Tests for the V3 6-phase LangGraph pipeline.

Validates graph structure, conditional routing, node functions,
and backward compatibility with the legacy extraction graph.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


class TestV3GraphStructure:
    """Verify the V3 graph has the correct topology."""

    def test_graph_has_all_nodes(self) -> None:
        from app.services.extraction import build_extraction_graph_v3

        graph = build_extraction_graph_v3()
        node_names = set(graph.get_graph().nodes.keys())

        # Phase 0
        assert "regex_extract" in node_names
        # Phase 1
        assert "narrative_characters" in node_names
        assert "narrative_events" in node_names
        assert "narrative_world" in node_names
        assert "merge_phase1" in node_names
        # Phase 2
        assert "genre_progression" in node_names
        assert "genre_creatures" in node_names
        assert "merge_phase2" in node_names
        # Phase 3
        assert "series_extract" in node_names
        # Phase 4
        assert "reconcile" in node_names
        # Phase 5
        assert "ground_mentions" in node_names
        assert "update_registry" in node_names

    def test_graph_compiles(self) -> None:
        from app.services.extraction import build_extraction_graph_v3

        graph = build_extraction_graph_v3()
        assert graph is not None

    def test_legacy_graph_still_works(self) -> None:
        from app.services.extraction import build_extraction_graph

        graph = build_extraction_graph()
        assert graph is not None


class TestPhaseRouting:
    """Test conditional routing logic for Phase 2 and Phase 3."""

    def test_genre_phase_skipped_when_no_genre(self) -> None:
        from app.services.extraction import should_run_genre_phase

        state: dict[str, Any] = {"genre": ""}
        assert should_run_genre_phase(state) is False  # type: ignore[arg-type]

    def test_genre_phase_runs_for_litrpg(self) -> None:
        from app.services.extraction import should_run_genre_phase

        state: dict[str, Any] = {"genre": "litrpg"}
        assert should_run_genre_phase(state) is True  # type: ignore[arg-type]

    def test_genre_phase_runs_for_cultivation(self) -> None:
        from app.services.extraction import should_run_genre_phase

        state: dict[str, Any] = {"genre": "cultivation"}
        assert should_run_genre_phase(state) is True  # type: ignore[arg-type]

    def test_series_phase_skipped_when_no_series(self) -> None:
        from app.services.extraction import should_run_series_phase

        state: dict[str, Any] = {"series_name": ""}
        assert should_run_series_phase(state) is False  # type: ignore[arg-type]

    def test_series_phase_runs_when_series_set(self) -> None:
        from app.services.extraction import should_run_series_phase

        state: dict[str, Any] = {"series_name": "primal_hunter"}
        assert should_run_series_phase(state) is True  # type: ignore[arg-type]

    def test_genre_phase_skipped_when_genre_none(self) -> None:
        from app.services.extraction import should_run_genre_phase

        state: dict[str, Any] = {}
        assert should_run_genre_phase(state) is False  # type: ignore[arg-type]

    def test_series_phase_skipped_when_series_none(self) -> None:
        from app.services.extraction import should_run_series_phase

        state: dict[str, Any] = {}
        assert should_run_series_phase(state) is False  # type: ignore[arg-type]


class TestFanOutRouting:
    """Test fan-out functions for parallel execution."""

    def test_fan_out_phase1_returns_three_sends(self) -> None:
        from app.services.extraction import fan_out_phase1

        state: dict[str, Any] = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": "test text",
        }
        sends = fan_out_phase1(state)  # type: ignore[arg-type]
        assert len(sends) == 3

        node_names = [s.node for s in sends]
        assert "narrative_characters" in node_names
        assert "narrative_events" in node_names
        assert "narrative_world" in node_names

    def test_route_phase1_to_phase2_with_genre(self) -> None:
        from app.services.extraction import _route_phase1_to_phase2

        state: dict[str, Any] = {"genre": "litrpg"}
        sends = _route_phase1_to_phase2(state)  # type: ignore[arg-type]
        assert len(sends) == 2

        node_names = [s.node for s in sends]
        assert "genre_progression" in node_names
        assert "genre_creatures" in node_names

    def test_route_phase1_to_phase2_without_genre(self) -> None:
        from app.services.extraction import _route_phase1_to_phase2

        state: dict[str, Any] = {"genre": ""}
        sends = _route_phase1_to_phase2(state)  # type: ignore[arg-type]
        assert len(sends) == 1
        assert sends[0].node == "reconcile"

    def test_route_phase2_to_phase3_with_series(self) -> None:
        from app.services.extraction import _route_phase2_to_phase3

        state: dict[str, Any] = {"series_name": "primal_hunter"}
        sends = _route_phase2_to_phase3(state)  # type: ignore[arg-type]
        assert len(sends) == 1
        assert sends[0].node == "series_extract"

    def test_route_phase2_to_phase3_without_series(self) -> None:
        from app.services.extraction import _route_phase2_to_phase3

        state: dict[str, Any] = {"series_name": ""}
        sends = _route_phase2_to_phase3(state)  # type: ignore[arg-type]
        assert len(sends) == 1
        assert sends[0].node == "reconcile"


class TestNodeFunctions:
    """Test individual V3 node functions."""

    def test_regex_extract_node_parses_json(self) -> None:
        from app.services.extraction import regex_extract_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "regex_matches_json": '[{"type": "skill", "name": "Stealth"}]',
            "extraction_run_id": "",
        }
        result = regex_extract_node(state)  # type: ignore[arg-type]

        assert len(result["phase0_regex"]) == 1
        assert result["phase0_regex"][0]["name"] == "Stealth"
        assert result["extraction_run_id"] != ""
        assert "phase0_regex" in result["passes_completed"]

    def test_regex_extract_node_handles_empty_json(self) -> None:
        from app.services.extraction import regex_extract_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "regex_matches_json": "[]",
            "extraction_run_id": "",
        }
        result = regex_extract_node(state)  # type: ignore[arg-type]

        assert result["phase0_regex"] == []
        assert result["extraction_run_id"] != ""

    def test_regex_extract_node_handles_invalid_json(self) -> None:
        from app.services.extraction import regex_extract_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "regex_matches_json": "not valid json",
            "extraction_run_id": "",
        }
        result = regex_extract_node(state)  # type: ignore[arg-type]

        assert result["phase0_regex"] == []

    def test_regex_extract_node_preserves_existing_run_id(self) -> None:
        from app.services.extraction import regex_extract_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "regex_matches_json": "[]",
            "extraction_run_id": "existing-run-id-123",
        }
        result = regex_extract_node(state)  # type: ignore[arg-type]

        assert result["extraction_run_id"] == "existing-run-id-123"

    def test_merge_phase1_node(self) -> None:
        from app.services.extraction import merge_phase1_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "phase1_narrative": [
                {"entity_type": "character", "name": "Jake", "source_pass": "narrative_characters"},
                {"entity_type": "event", "name": "Tutorial Start", "source_pass": "narrative_events"},
            ],
        }
        result = merge_phase1_node(state)  # type: ignore[arg-type]

        assert "phase1_merge" in result["passes_completed"]

    def test_merge_phase2_node(self) -> None:
        from app.services.extraction import merge_phase2_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "phase2_genre": [
                {"entity_type": "skill", "name": "Stealth", "source_pass": "genre_progression"},
            ],
        }
        result = merge_phase2_node(state)  # type: ignore[arg-type]

        assert "phase2_merge" in result["passes_completed"]

    def test_update_registry_node(self) -> None:
        from app.services.extraction import update_registry_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 5,
            "entity_registry": {},
            "phase1_narrative": [
                {"entity_type": "character", "name": "Jake"},
                {"entity_type": "event", "name": "Tutorial Start"},
            ],
            "phase2_genre": [
                {"entity_type": "skill", "name": "Stealth"},
            ],
            "phase3_series": [],
        }
        result = update_registry_node(state)  # type: ignore[arg-type]

        registry = result["entity_registry"]
        assert registry["last_chapter"] == 5
        assert registry["entity_count"] == 3
        assert len(registry["entities"]) == 3
        assert "update_registry" in result["passes_completed"]

    def test_update_registry_node_handles_empty_phases(self) -> None:
        from app.services.extraction import update_registry_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "entity_registry": None,
            "phase1_narrative": [],
            "phase2_genre": [],
            "phase3_series": [],
        }
        result = update_registry_node(state)  # type: ignore[arg-type]

        registry = result["entity_registry"]
        assert registry["entity_count"] == 0
        assert registry["entities"] == []

    @pytest.mark.asyncio
    async def test_genre_creatures_node_returns_placeholder(self) -> None:
        from app.services.extraction import genre_creatures_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
        }
        result = await genre_creatures_node(state)  # type: ignore[arg-type]

        assert result["phase2_genre"] == []
        assert "genre_creatures" in result["passes_completed"]

    @pytest.mark.asyncio
    async def test_series_extract_node_returns_placeholder(self) -> None:
        from app.services.extraction import series_extract_node

        state: dict[str, Any] = {
            "book_id": "test-book",
            "chapter_number": 1,
            "series_name": "primal_hunter",
        }
        result = await series_extract_node(state)  # type: ignore[arg-type]

        assert result["phase3_series"] == []
        assert "series_extract" in result["passes_completed"]


class TestV3DelegateNodes:
    """Test that V3 nodes properly delegate to existing extraction functions."""

    @pytest.mark.asyncio
    async def test_narrative_characters_delegates(self) -> None:
        """narrative_characters_node should delegate to extract_characters."""
        from app.schemas.extraction import CharacterExtractionResult, ExtractedCharacter

        mock_result = {
            "characters": CharacterExtractionResult(
                characters=[
                    ExtractedCharacter(
                        name="Jake Thayne",
                        canonical_name="Jake Thayne",
                        aliases=["Jake"],
                        description="Main character",
                        role="protagonist",
                    )
                ],
                relationships=[],
            ),
            "grounded_entities": [],
            "passes_completed": ["characters"],
            "errors": [],
        }

        with patch(
            "app.services.extraction.extract_characters",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from app.services.extraction import narrative_characters_node

            state: dict[str, Any] = {
                "book_id": "test-book",
                "chapter_number": 1,
                "chapter_text": "Jake Thayne walked into the forest.",
            }
            result = await narrative_characters_node(state)  # type: ignore[arg-type]

            assert "characters" in result
            assert len(result["phase1_narrative"]) == 1
            assert result["phase1_narrative"][0]["entity_type"] == "character"
            assert result["phase1_narrative"][0]["name"] == "Jake Thayne"

    @pytest.mark.asyncio
    async def test_narrative_events_delegates(self) -> None:
        """narrative_events_node should delegate to extract_events."""
        from app.schemas.extraction import EventExtractionResult, ExtractedEvent

        mock_result = {
            "events": EventExtractionResult(
                events=[
                    ExtractedEvent(
                        name="Tutorial Begins",
                        description="The tutorial starts",
                        event_type="system",
                        significance="major",
                        participants=["Jake"],
                        chapter=1,
                    )
                ]
            ),
            "grounded_entities": [],
            "passes_completed": ["events"],
            "errors": [],
        }

        with patch(
            "app.services.extraction.extract_events",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from app.services.extraction import narrative_events_node

            state: dict[str, Any] = {
                "book_id": "test-book",
                "chapter_number": 1,
                "chapter_text": "The tutorial began with a flash of light.",
            }
            result = await narrative_events_node(state)  # type: ignore[arg-type]

            assert "events" in result
            assert len(result["phase1_narrative"]) == 1
            assert result["phase1_narrative"][0]["entity_type"] == "event"
            assert result["phase1_narrative"][0]["name"] == "Tutorial Begins"

    @pytest.mark.asyncio
    async def test_narrative_world_delegates(self) -> None:
        """narrative_world_node should delegate to extract_lore."""
        from app.schemas.extraction import ExtractedLocation, LoreExtractionResult

        mock_result = {
            "lore": LoreExtractionResult(
                locations=[
                    ExtractedLocation(
                        name="Tutorial Zone",
                        description="The starting area",
                        location_type="dungeon",
                    )
                ],
                items=[],
                creatures=[],
                factions=[],
                concepts=[],
            ),
            "grounded_entities": [],
            "passes_completed": ["lore"],
            "errors": [],
        }

        with patch(
            "app.services.extraction.extract_lore",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from app.services.extraction import narrative_world_node

            state: dict[str, Any] = {
                "book_id": "test-book",
                "chapter_number": 1,
                "chapter_text": "They entered the Tutorial Zone.",
            }
            result = await narrative_world_node(state)  # type: ignore[arg-type]

            assert "lore" in result
            assert len(result["phase1_narrative"]) == 1
            assert result["phase1_narrative"][0]["entity_type"] == "location"
            assert result["phase1_narrative"][0]["name"] == "Tutorial Zone"

    @pytest.mark.asyncio
    async def test_genre_progression_delegates(self) -> None:
        """genre_progression_node should delegate to extract_systems."""
        from app.schemas.extraction import ExtractedSkill, SystemExtractionResult

        mock_result = {
            "systems": SystemExtractionResult(
                skills=[
                    ExtractedSkill(
                        name="Stealth",
                        description="Move unseen",
                        skill_type="active",
                        owner="Jake",
                    )
                ],
                classes=[],
                titles=[],
                level_changes=[],
                stat_changes=[],
            ),
            "grounded_entities": [],
            "passes_completed": ["systems"],
            "errors": [],
        }

        with patch(
            "app.services.extraction.extract_systems",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from app.services.extraction import genre_progression_node

            state: dict[str, Any] = {
                "book_id": "test-book",
                "chapter_number": 1,
                "chapter_text": "[Skill Acquired: Stealth]",
            }
            result = await genre_progression_node(state)  # type: ignore[arg-type]

            assert "systems" in result
            assert len(result["phase2_genre"]) == 1
            assert result["phase2_genre"][0]["entity_type"] == "skill"
            assert result["phase2_genre"][0]["name"] == "Stealth"

    @pytest.mark.asyncio
    async def test_reconcile_v3_delegates(self) -> None:
        """reconcile_v3_node should delegate to reconcile_in_graph."""
        mock_result = {
            "alias_map": {"Jake": "Jake Thayne"},
            "passes_completed": ["reconcile"],
        }

        with patch(
            "app.services.extraction.reconcile_in_graph",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from app.services.extraction import reconcile_v3_node

            state: dict[str, Any] = {}
            result = await reconcile_v3_node(state)  # type: ignore[arg-type]

            assert result["alias_map"] == {"Jake": "Jake Thayne"}

    @pytest.mark.asyncio
    async def test_ground_mentions_v3_delegates(self) -> None:
        """ground_mentions_v3_node should delegate to mention_detect_node."""
        mock_result = {
            "grounded_entities": [],
            "passes_completed": ["mention_detect"],
            "errors": [],
        }

        with patch(
            "app.services.extraction.mention_detect_node",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from app.services.extraction import ground_mentions_v3_node

            state: dict[str, Any] = {}
            result = await ground_mentions_v3_node(state)  # type: ignore[arg-type]

            assert "mention_detect" in result["passes_completed"]
