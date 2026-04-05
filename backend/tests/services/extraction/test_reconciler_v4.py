"""Unit tests for reconcile_flat_entities and _get_name_from_flat_entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.services.extraction.reconciler import (
    _get_name_from_flat_entity,
    reconcile_flat_entities,
)

# ── _get_name_from_flat_entity ──────────────────────────────────────────────


class TestGetNameFromFlatEntity:
    def test_standard_entity_uses_name_field(self):
        entity = {"entity_type": "character", "name": "Jake Thayne"}
        assert _get_name_from_flat_entity(entity) == "Jake Thayne"

    def test_location_uses_name_field(self):
        entity = {"entity_type": "location", "name": "Dark Forest"}
        assert _get_name_from_flat_entity(entity) == "Dark Forest"

    def test_skill_uses_name_field(self):
        entity = {"entity_type": "skill", "name": "Basic Archery"}
        assert _get_name_from_flat_entity(entity) == "Basic Archery"

    def test_level_change_uses_character_field(self):
        entity = {
            "entity_type": "level_change",
            "character": "Jake",
            "old_level": 1,
            "new_level": 5,
        }
        assert _get_name_from_flat_entity(entity) == "Jake"

    def test_stat_change_uses_character_field(self):
        entity = {
            "entity_type": "stat_change",
            "character": "Miranda",
            "stat": "Perception",
            "delta": 5,
        }
        assert _get_name_from_flat_entity(entity) == "Miranda"

    def test_level_change_falls_back_to_name_if_no_character(self):
        entity = {"entity_type": "level_change", "name": "Jake"}
        assert _get_name_from_flat_entity(entity) == "Jake"

    def test_stat_change_falls_back_to_name_if_no_character(self):
        entity = {"entity_type": "stat_change", "name": "SomeChar"}
        assert _get_name_from_flat_entity(entity) == "SomeChar"

    def test_missing_name_returns_none(self):
        entity = {"entity_type": "character", "description": "No name here"}
        assert _get_name_from_flat_entity(entity) is None

    def test_missing_entity_type_uses_name_field(self):
        entity = {"name": "Unknown Entity"}
        assert _get_name_from_flat_entity(entity) == "Unknown Entity"

    def test_empty_dict_returns_none(self):
        assert _get_name_from_flat_entity({}) is None

    def test_level_change_with_empty_character_falls_back_to_name(self):
        # empty string is falsy, should fall back to name
        entity = {"entity_type": "level_change", "character": "", "name": "Jake"}
        assert _get_name_from_flat_entity(entity) == "Jake"


# ── reconcile_flat_entities ─────────────────────────────────────────────────


class TestReconcileFlatEntities:
    async def test_empty_input_returns_empty_map(self):
        result = await reconcile_flat_entities([])
        assert result == {}

    async def test_single_entity_returns_empty_map(self):
        """Single entity per group — nothing to deduplicate."""
        entities = [{"entity_type": "character", "name": "Jake"}]
        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            new_callable=AsyncMock,
        ) as mock_dedup:
            result = await reconcile_flat_entities(entities, client=None, model="")
        # dedup should never be called for a group of 1
        mock_dedup.assert_not_called()
        assert result == {}

    async def test_two_entities_same_type_calls_dedup(self):
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jake Thayne"},
        ]
        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            new_callable=AsyncMock,
            return_value=([], {"Jake": "Jake Thayne"}),
        ) as mock_dedup:
            result = await reconcile_flat_entities(entities, client=object(), model="test-model")

        mock_dedup.assert_awaited_once()
        assert result == {"Jake": "Jake Thayne"}

    async def test_groups_by_entity_type(self):
        """Entities of different types are grouped separately; dedup called per group."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jake Thayne"},
            {"entity_type": "location", "name": "Dark Forest"},
            {"entity_type": "location", "name": "The Dark Forest"},
        ]

        call_count = 0

        async def fake_dedup(name_dicts, entity_type, client, model):
            nonlocal call_count
            call_count += 1
            if entity_type == "character":
                return [], {"Jake": "Jake Thayne"}
            if entity_type == "location":
                return [], {"Dark Forest": "The Dark Forest"}
            return [], {}

        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            side_effect=fake_dedup,
        ):
            result = await reconcile_flat_entities(entities, client=object(), model="test-model")

        assert call_count == 2
        assert result == {"Jake": "Jake Thayne", "Dark Forest": "The Dark Forest"}

    async def test_merges_alias_maps_from_multiple_groups(self):
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jake Thayne"},
            {"entity_type": "skill", "name": "Archery"},
            {"entity_type": "skill", "name": "Basic Archery"},
        ]

        async def fake_dedup(name_dicts, entity_type, client, model):
            if entity_type == "character":
                return [], {"Jake": "Jake Thayne"}
            return [], {"Archery": "Basic Archery"}

        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            side_effect=fake_dedup,
        ):
            result = await reconcile_flat_entities(entities, client=object(), model="m")

        assert result == {"Jake": "Jake Thayne", "Archery": "Basic Archery"}

    async def test_dedup_failure_is_handled_gracefully(self):
        """If dedup raises for one group, the whole call still succeeds."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jake Thayne"},
        ]

        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            new_callable=AsyncMock,
            side_effect=RuntimeError("dedup exploded"),
        ):
            result = await reconcile_flat_entities(entities, client=object(), model="m")

        # Should swallow the error and return an empty alias map
        assert result == {}

    async def test_entities_without_names_are_skipped(self):
        """Entities with no resolvable name must not reach dedup."""
        entities = [
            {"entity_type": "character", "description": "no name"},
            {"entity_type": "character", "description": "also no name"},
        ]

        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            new_callable=AsyncMock,
        ) as mock_dedup:
            result = await reconcile_flat_entities(entities, client=object(), model="m")

        # Both entities have no name — after filtering name_dicts has <2 entries, skip dedup
        mock_dedup.assert_not_called()
        assert result == {}

    async def test_mixed_named_and_unnamed_entities(self):
        """Only named entities reach dedup; unnamed ones are silently dropped."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character"},  # no name
            {"entity_type": "character", "name": "Jake Thayne"},
        ]

        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            new_callable=AsyncMock,
            return_value=([], {"Jake": "Jake Thayne"}),
        ) as mock_dedup:
            result = await reconcile_flat_entities(entities, client=object(), model="m")

        # dedup should be called with only the two named entities
        mock_dedup.assert_awaited_once()
        call_args = mock_dedup.call_args[0]
        assert call_args[0] == [{"name": "Jake"}, {"name": "Jake Thayne"}]
        assert result == {"Jake": "Jake Thayne"}

    async def test_level_change_entities_use_character_field_for_dedup(self):
        entities = [
            {
                "entity_type": "level_change",
                "character": "Jake",
                "old_level": 1,
                "new_level": 2,
            },
            {
                "entity_type": "level_change",
                "character": "Jake Thayne",
                "old_level": 2,
                "new_level": 5,
            },
        ]

        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            new_callable=AsyncMock,
            return_value=([], {"Jake": "Jake Thayne"}),
        ) as mock_dedup:
            result = await reconcile_flat_entities(entities, client=object(), model="m")

        call_args = mock_dedup.call_args[0]
        assert call_args[0] == [{"name": "Jake"}, {"name": "Jake Thayne"}]
        assert result == {"Jake": "Jake Thayne"}

    async def test_client_model_fetched_when_not_provided(self):
        """When client/model are omitted, get_instructor_for_task is called."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Casper"},
        ]
        mock_client = object()

        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                return_value=(mock_client, "auto-model"),
            ) as mock_get,
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                new_callable=AsyncMock,
                return_value=([], {}),
            ),
        ):
            await reconcile_flat_entities(entities)

        mock_get.assert_called_once_with("dedup")

    async def test_instructor_fetch_failure_falls_back_to_none(self):
        """If get_instructor_for_task raises, client/model default to None/''."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Casper"},
        ]

        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                side_effect=RuntimeError("no provider"),
            ),
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                new_callable=AsyncMock,
                return_value=([], {"Jake": "Casper"}),
            ) as mock_dedup,
        ):
            result = await reconcile_flat_entities(entities)

        # dedup was still called (with client=None, model="")
        mock_dedup.assert_awaited_once()
        call_args = mock_dedup.call_args[0]
        assert call_args[2] is None  # client
        assert call_args[3] == ""  # model
        assert result == {"Jake": "Casper"}

    async def test_dedup_partial_failure_keeps_successful_groups(self):
        """If one group fails dedup but another succeeds, partial results are returned."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jake Thayne"},
            {"entity_type": "location", "name": "Forest"},
            {"entity_type": "location", "name": "Dark Forest"},
        ]
        call_count = 0

        async def fake_dedup(name_dicts, entity_type, client, model):
            nonlocal call_count
            call_count += 1
            if entity_type == "character":
                raise RuntimeError("character dedup failed")
            return [], {"Forest": "Dark Forest"}

        with patch(
            "app.services.extraction.reconciler.deduplicate_entities",
            side_effect=fake_dedup,
        ):
            result = await reconcile_flat_entities(entities, client=object(), model="m")

        assert call_count == 2
        # character group failed silently; location group succeeded
        assert result == {"Forest": "Dark Forest"}


class TestCrossTypeDedup:
    async def test_same_name_different_types_keeps_highest_priority(self):
        """Same name as Character and Event → keeps Character (higher priority)."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "event", "name": "Jake"},
            {"entity_type": "concept", "name": "Jake"},
        ]
        mock_dedup = AsyncMock(return_value=([], {}))
        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                return_value=(AsyncMock(), "test-model"),
            ),
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                mock_dedup,
            ),
        ):
            await reconcile_flat_entities(entities)
        # Only character "Jake" should survive (dedup called with 1 entity → skipped)
        assert mock_dedup.call_count == 0  # 1 character entity → < 2, skip dedup

    async def test_different_names_not_affected(self):
        """Different names should not trigger cross-type dedup."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "event", "name": "Battle of Ironhold"},
        ]
        mock_dedup = AsyncMock(return_value=([], {}))
        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                return_value=(AsyncMock(), "test-model"),
            ),
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                mock_dedup,
            ),
        ):
            await reconcile_flat_entities(entities)
        # Both should survive — different names
        assert mock_dedup.call_count == 0  # each type has only 1 entity
