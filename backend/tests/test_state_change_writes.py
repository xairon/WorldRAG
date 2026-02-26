"""Tests for V3 dual-write StateChange ledger nodes in entity upsert methods.

Verifies that each upsert method in EntityRepository now makes 2 execute_write
calls: the original MERGE operation + the StateChange CREATE operation.
"""

from __future__ import annotations

import pytest

from app.repositories.entity_repo import EntityRepository
from app.schemas.extraction import (
    ExtractedClass,
    ExtractedItem,
    ExtractedLevelChange,
    ExtractedSkill,
    ExtractedStatChange,
    ExtractedTitle,
)

BOOK_ID = "book-uuid-001"
CHAPTER = 14
BATCH_ID = "batch-001"


@pytest.fixture
def repo(mock_neo4j_driver_with_session):
    return EntityRepository(mock_neo4j_driver_with_session)


# ── upsert_stat_changes ─────────────────────────────────────────────────


class TestUpsertStatChangesCreatesStateChange:
    async def test_creates_state_change_nodes(self, repo, mock_neo4j_session):
        stats = [
            ExtractedStatChange(character="Jake Thayne", stat_name="Perception", value=5),
        ]
        await repo.upsert_stat_changes(BOOK_ID, CHAPTER, stats, BATCH_ID)
        # Should have 2 execute_write calls: one for HAS_STAT merge, one for StateChange CREATE
        assert mock_neo4j_session.run.call_count >= 2

    async def test_state_change_action_gain(self, repo, mock_neo4j_session):
        stats = [
            ExtractedStatChange(character="Jake Thayne", stat_name="Agility", value=3),
        ]
        await repo.upsert_stat_changes(BOOK_ID, CHAPTER, stats, BATCH_ID)
        # The second call should be the StateChange creation
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["action"] == "gain"
        assert changes[0]["category"] == "stat"
        assert changes[0]["name"] == "Agility"
        assert changes[0]["value_delta"] == 3

    async def test_state_change_action_lose(self, repo, mock_neo4j_session):
        stats = [
            ExtractedStatChange(character="Jake Thayne", stat_name="Health", value=-10),
        ]
        await repo.upsert_stat_changes(BOOK_ID, CHAPTER, stats, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert changes[0]["action"] == "lose"
        assert changes[0]["value_delta"] == -10

    async def test_empty_list_no_calls(self, repo, mock_neo4j_session):
        await repo.upsert_stat_changes(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert mock_neo4j_session.run.call_count == 0

    async def test_filtered_empty_no_state_change(self, repo, mock_neo4j_session):
        """Stats with empty character/stat_name get filtered out."""
        stats = [
            ExtractedStatChange(character="", stat_name="Perception", value=5),
        ]
        await repo.upsert_stat_changes(BOOK_ID, CHAPTER, stats, BATCH_ID)
        # All filtered out by the `if sc.character and sc.stat_name` check
        assert mock_neo4j_session.run.call_count == 0


# ── upsert_level_changes ────────────────────────────────────────────────


class TestUpsertLevelChangesCreatesStateChange:
    async def test_creates_state_change_nodes(self, repo, mock_neo4j_session):
        levels = [
            ExtractedLevelChange(
                character="Jake Thayne",
                old_level=87,
                new_level=88,
                realm="D-grade",
            ),
        ]
        await repo.upsert_level_changes(BOOK_ID, CHAPTER, levels, BATCH_ID)
        assert mock_neo4j_session.run.call_count >= 2

    async def test_state_change_has_correct_fields(self, repo, mock_neo4j_session):
        levels = [
            ExtractedLevelChange(
                character="Jake Thayne",
                old_level=87,
                new_level=88,
                realm="D-grade",
            ),
        ]
        await repo.upsert_level_changes(BOOK_ID, CHAPTER, levels, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["category"] == "level"
        assert changes[0]["name"] == "level"
        assert changes[0]["action"] == "gain"
        assert changes[0]["value_delta"] == 1
        assert changes[0]["value_after"] == 88
        assert changes[0]["detail"] == "D-grade"

    async def test_missing_old_level_gives_none_delta(self, repo, mock_neo4j_session):
        levels = [
            ExtractedLevelChange(character="Jake Thayne", old_level=None, new_level=88),
        ]
        await repo.upsert_level_changes(BOOK_ID, CHAPTER, levels, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert changes[0]["value_delta"] is None
        assert changes[0]["value_after"] == 88

    async def test_empty_list_no_calls(self, repo, mock_neo4j_session):
        await repo.upsert_level_changes(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert mock_neo4j_session.run.call_count == 0

    async def test_filtered_empty_character(self, repo, mock_neo4j_session):
        """Level changes with empty character get filtered out."""
        levels = [
            ExtractedLevelChange(character="", old_level=1, new_level=2),
        ]
        await repo.upsert_level_changes(BOOK_ID, CHAPTER, levels, BATCH_ID)
        # Filtered by `if lc.character` check in the data comprehension
        assert mock_neo4j_session.run.call_count == 0


# ── upsert_skills ───────────────────────────────────────────────────────


class TestUpsertSkillsCreatesStateChange:
    async def test_creates_state_change_nodes(self, repo, mock_neo4j_session):
        skills = [
            ExtractedSkill(name="Arcane Powershot", owner="Jake Thayne"),
        ]
        await repo.upsert_skills(BOOK_ID, CHAPTER, skills, BATCH_ID)
        assert mock_neo4j_session.run.call_count >= 2

    async def test_state_change_has_correct_fields(self, repo, mock_neo4j_session):
        skills = [
            ExtractedSkill(name="Arcane Powershot", owner="Jake Thayne"),
        ]
        await repo.upsert_skills(BOOK_ID, CHAPTER, skills, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["category"] == "skill"
        assert changes[0]["name"] == "Arcane Powershot"
        assert changes[0]["action"] == "acquire"
        assert changes[0]["character_name"] == "Jake Thayne"

    async def test_empty_owner_filtered_out(self, repo, mock_neo4j_session):
        skills = [
            ExtractedSkill(name="Arcane Powershot", owner=""),
        ]
        await repo.upsert_skills(BOOK_ID, CHAPTER, skills, BATCH_ID)
        # 1 call for the MERGE (skills are still created), but no StateChange call
        assert mock_neo4j_session.run.call_count == 1

    async def test_empty_list_no_calls(self, repo, mock_neo4j_session):
        await repo.upsert_skills(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert mock_neo4j_session.run.call_count == 0

    async def test_mixed_owners_filters_empty(self, repo, mock_neo4j_session):
        skills = [
            ExtractedSkill(name="Arcane Powershot", owner="Jake Thayne"),
            ExtractedSkill(name="Fire Bolt", owner=""),
            ExtractedSkill(name="Shadow Step", owner="Sylphie"),
        ]
        await repo.upsert_skills(BOOK_ID, CHAPTER, skills, BATCH_ID)
        # 1 MERGE + 1 StateChange
        assert mock_neo4j_session.run.call_count == 2
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        # Only 2 with non-empty owners
        assert len(changes) == 2
        names = {c["name"] for c in changes}
        assert names == {"Arcane Powershot", "Shadow Step"}


# ── upsert_classes ──────────────────────────────────────────────────────


class TestUpsertClassesCreatesStateChange:
    async def test_creates_state_change_nodes(self, repo, mock_neo4j_session):
        classes = [
            ExtractedClass(name="Arcane Hunter", owner="Jake Thayne"),
        ]
        await repo.upsert_classes(BOOK_ID, CHAPTER, classes, BATCH_ID)
        assert mock_neo4j_session.run.call_count >= 2

    async def test_state_change_has_correct_fields(self, repo, mock_neo4j_session):
        classes = [
            ExtractedClass(name="Arcane Hunter", owner="Jake Thayne"),
        ]
        await repo.upsert_classes(BOOK_ID, CHAPTER, classes, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["category"] == "class"
        assert changes[0]["name"] == "Arcane Hunter"
        assert changes[0]["action"] == "acquire"

    async def test_empty_owner_filtered_out(self, repo, mock_neo4j_session):
        classes = [
            ExtractedClass(name="Arcane Hunter", owner=""),
        ]
        await repo.upsert_classes(BOOK_ID, CHAPTER, classes, BATCH_ID)
        assert mock_neo4j_session.run.call_count == 1

    async def test_empty_list_no_calls(self, repo, mock_neo4j_session):
        await repo.upsert_classes(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert mock_neo4j_session.run.call_count == 0


# ── upsert_titles ───────────────────────────────────────────────────────


class TestUpsertTitlesCreatesStateChange:
    async def test_creates_state_change_nodes(self, repo, mock_neo4j_session):
        titles = [
            ExtractedTitle(name="Hydra Slayer", owner="Jake Thayne"),
        ]
        await repo.upsert_titles(BOOK_ID, CHAPTER, titles, BATCH_ID)
        assert mock_neo4j_session.run.call_count >= 2

    async def test_state_change_has_correct_fields(self, repo, mock_neo4j_session):
        titles = [
            ExtractedTitle(name="Hydra Slayer", owner="Jake Thayne"),
        ]
        await repo.upsert_titles(BOOK_ID, CHAPTER, titles, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["category"] == "title"
        assert changes[0]["name"] == "Hydra Slayer"
        assert changes[0]["action"] == "acquire"

    async def test_empty_owner_filtered_out(self, repo, mock_neo4j_session):
        titles = [
            ExtractedTitle(name="Hydra Slayer", owner=""),
        ]
        await repo.upsert_titles(BOOK_ID, CHAPTER, titles, BATCH_ID)
        assert mock_neo4j_session.run.call_count == 1

    async def test_empty_list_no_calls(self, repo, mock_neo4j_session):
        await repo.upsert_titles(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert mock_neo4j_session.run.call_count == 0


# ── upsert_items ────────────────────────────────────────────────────────


class TestUpsertItemsCreatesStateChange:
    async def test_creates_state_change_nodes(self, repo, mock_neo4j_session):
        items = [
            ExtractedItem(name="Nanoblade", owner="Jake Thayne"),
        ]
        await repo.upsert_items(BOOK_ID, CHAPTER, items, BATCH_ID)
        assert mock_neo4j_session.run.call_count >= 2

    async def test_state_change_has_correct_fields(self, repo, mock_neo4j_session):
        items = [
            ExtractedItem(name="Nanoblade", owner="Jake Thayne"),
        ]
        await repo.upsert_items(BOOK_ID, CHAPTER, items, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["category"] == "item"
        assert changes[0]["name"] == "Nanoblade"
        assert changes[0]["action"] == "acquire"

    async def test_empty_owner_filtered_out(self, repo, mock_neo4j_session):
        items = [
            ExtractedItem(name="Nanoblade", owner=""),
        ]
        await repo.upsert_items(BOOK_ID, CHAPTER, items, BATCH_ID)
        assert mock_neo4j_session.run.call_count == 1

    async def test_empty_list_no_calls(self, repo, mock_neo4j_session):
        await repo.upsert_items(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert mock_neo4j_session.run.call_count == 0


# ── _create_state_changes helper ────────────────────────────────────────


class TestCreateStateChangesHelper:
    async def test_empty_changes_returns_zero(self, repo, mock_neo4j_session):
        result = await repo._create_state_changes(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_sets_default_optional_fields(self, repo, mock_neo4j_session):
        changes = [
            {
                "character_name": "Jake Thayne",
                "category": "skill",
                "name": "Arcane Powershot",
                "action": "acquire",
            }
        ]
        await repo._create_state_changes(BOOK_ID, CHAPTER, changes, BATCH_ID)
        # Should have set defaults
        assert changes[0]["value_delta"] is None
        assert changes[0]["value_after"] is None
        assert changes[0]["detail"] == ""

    async def test_returns_count(self, repo, mock_neo4j_session):
        changes = [
            {
                "character_name": "Jake Thayne",
                "category": "stat",
                "name": "Perception",
                "action": "gain",
                "value_delta": 5,
            },
            {
                "character_name": "Sylphie",
                "category": "stat",
                "name": "Agility",
                "action": "gain",
                "value_delta": 3,
            },
        ]
        result = await repo._create_state_changes(BOOK_ID, CHAPTER, changes, BATCH_ID)
        assert result == 2

    async def test_passes_correct_params(self, repo, mock_neo4j_session):
        changes = [
            {
                "character_name": "Jake Thayne",
                "category": "level",
                "name": "level",
                "action": "gain",
                "value_delta": 1,
                "value_after": 88,
                "detail": "D-grade",
            }
        ]
        await repo._create_state_changes(BOOK_ID, CHAPTER, changes, BATCH_ID)
        call_args = mock_neo4j_session.run.call_args
        params = call_args[0][1]
        assert params["book_id"] == BOOK_ID
        assert params["chapter"] == CHAPTER
        assert params["batch_id"] == BATCH_ID
        assert len(params["changes"]) == 1
        assert params["changes"][0]["character_name"] == "Jake Thayne"
