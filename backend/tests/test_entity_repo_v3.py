"""Tests for V3 entity_repo methods: BlueBox, GRANTS, and Layer 3 persistence.

Covers:
- upsert_blue_boxes (Task 2.2)
- upsert_grants_relations (Task 2.5)
- upsert_bloodlines, upsert_professions, upsert_churches (Task 3.3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.repositories.entity_repo import EntityRepository
from app.schemas.extraction import (
    ExtractedBloodline,
    ExtractedChurch,
    ExtractedProfession,
    SkillProvenance,
)

BOOK_ID = "book-uuid-001"
CHAPTER = 14
BATCH_ID = "batch-001"


@pytest.fixture
def repo(mock_neo4j_driver_with_session):
    return EntityRepository(mock_neo4j_driver_with_session)


# ── Fake BlueBoxGroup (from dataclass in bluebox.py) ───────────────────────


@dataclass
class FakeBlueBoxGroup:
    paragraph_start: int
    paragraph_end: int
    raw_text: str
    box_type: str = "mixed"
    paragraph_indexes: list[int] = field(default_factory=list)


# ── upsert_blue_boxes ─────────────────────────────────────────────────────


class TestUpsertBlueBoxes:
    async def test_empty_boxes_returns_zero(self, repo, mock_neo4j_session):
        result = await repo.upsert_blue_boxes(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_normal_boxes_returns_count(self, repo, mock_neo4j_session):
        boxes = [
            FakeBlueBoxGroup(
                paragraph_start=5,
                paragraph_end=7,
                raw_text="[Skill Acquired: Arcane Powershot]\n+5 Perception",
                box_type="skill_notification",
            ),
            FakeBlueBoxGroup(
                paragraph_start=12,
                paragraph_end=13,
                raw_text="Level: 87 -> 88",
                box_type="level_up",
            ),
        ]
        result = await repo.upsert_blue_boxes(BOOK_ID, CHAPTER, boxes, BATCH_ID)
        assert result == 2
        assert mock_neo4j_session.run.call_count == 1

    async def test_passes_correct_params(self, repo, mock_neo4j_session):
        boxes = [
            FakeBlueBoxGroup(
                paragraph_start=5,
                paragraph_end=7,
                raw_text="[Skill Acquired: Shadow Strike]",
                box_type="skill_notification",
            ),
        ]
        await repo.upsert_blue_boxes(BOOK_ID, CHAPTER, boxes, BATCH_ID)
        call_args = mock_neo4j_session.run.call_args
        params = call_args[0][1]
        assert params["book_id"] == BOOK_ID
        assert params["chapter"] == CHAPTER
        assert params["batch_id"] == BATCH_ID
        assert len(params["boxes"]) == 1
        assert params["boxes"][0]["index"] == 0
        assert params["boxes"][0]["raw_text"] == "[Skill Acquired: Shadow Strike]"
        assert params["boxes"][0]["box_type"] == "skill_notification"
        assert params["boxes"][0]["paragraph_start"] == 5
        assert params["boxes"][0]["paragraph_end"] == 7

    async def test_indexes_are_sequential(self, repo, mock_neo4j_session):
        boxes = [
            FakeBlueBoxGroup(paragraph_start=1, paragraph_end=2, raw_text="Box A"),
            FakeBlueBoxGroup(paragraph_start=5, paragraph_end=6, raw_text="Box B"),
            FakeBlueBoxGroup(paragraph_start=10, paragraph_end=11, raw_text="Box C"),
        ]
        await repo.upsert_blue_boxes(BOOK_ID, CHAPTER, boxes, BATCH_ID)
        params = mock_neo4j_session.run.call_args[0][1]
        indexes = [b["index"] for b in params["boxes"]]
        assert indexes == [0, 1, 2]


# ── upsert_grants_relations ──────────────────────────────────────────────


class TestUpsertGrantsRelations:
    async def test_empty_provenances_returns_zero(self, repo, mock_neo4j_session):
        result = await repo.upsert_grants_relations([], BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_low_confidence_filtered_out(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Shadow Strike",
                source_type="item",
                source_name="Nanoblade",
                confidence=0.3,  # below 0.7 threshold
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_unknown_source_type_filtered_out(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Shadow Strike",
                source_type="unknown",  # not in (item, class, bloodline)
                source_name="Some Source",
                confidence=0.9,
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_empty_source_name_filtered_out(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Shadow Strike",
                source_type="item",
                source_name="",  # empty source name
                confidence=0.9,
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_valid_item_provenance_creates_relation(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Shadow Strike",
                source_type="item",
                source_name="Nanoblade",
                confidence=0.95,
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 1
        assert mock_neo4j_session.run.call_count == 1

    async def test_valid_class_provenance(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Arcane Powershot",
                source_type="class",
                source_name="Avaricious Arcane Hunter",
                confidence=0.9,
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 1
        assert mock_neo4j_session.run.call_count == 1

    async def test_valid_bloodline_provenance(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Primal Instinct",
                source_type="bloodline",
                source_name="Bloodline of the Primal Hunter",
                confidence=0.85,
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 1
        assert mock_neo4j_session.run.call_count == 1

    async def test_mixed_provenances_multiple_types(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Shadow Strike",
                source_type="item",
                source_name="Nanoblade",
                confidence=0.95,
            ),
            SkillProvenance(
                skill_name="Arcane Powershot",
                source_type="class",
                source_name="Avaricious Arcane Hunter",
                confidence=0.9,
            ),
            SkillProvenance(
                skill_name="Low Confidence Skill",
                source_type="item",
                source_name="Some Item",
                confidence=0.3,  # filtered
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 2
        # One call for item type, one call for class type
        assert mock_neo4j_session.run.call_count == 2

    async def test_boundary_confidence_0_7_included(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Boundary Skill",
                source_type="item",
                source_name="Boundary Item",
                confidence=0.7,  # exactly at threshold
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 1

    async def test_boundary_confidence_below_excluded(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Boundary Skill",
                source_type="item",
                source_name="Boundary Item",
                confidence=0.69,  # just below threshold
            ),
        ]
        result = await repo.upsert_grants_relations(provenances, BATCH_ID)
        assert result == 0


# ── upsert_bloodlines ────────────────────────────────────────────────────


class TestUpsertBloodlines:
    async def test_empty_bloodlines_returns_zero(self, repo, mock_neo4j_session):
        result = await repo.upsert_bloodlines(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_normal_bloodlines_returns_count(self, repo, mock_neo4j_session):
        bloodlines = [
            ExtractedBloodline(
                name="Bloodline of the Primal Hunter",
                description="Grants enhanced perception and hunting instincts",
                effects=["enhanced perception", "hunting instincts"],
                origin="Primordial patron",
                owner="Jake Thayne",
                awakened_chapter=42,
            ),
        ]
        result = await repo.upsert_bloodlines(BOOK_ID, CHAPTER, bloodlines, BATCH_ID)
        assert result == 1
        # 1 call for MERGE + 1 call for StateChange
        assert mock_neo4j_session.run.call_count == 2

    async def test_bloodline_without_owner_no_state_change(self, repo, mock_neo4j_session):
        bloodlines = [
            ExtractedBloodline(
                name="Bloodline of the Malefic Viper",
                description="Viper bloodline",
                owner="",
            ),
        ]
        result = await repo.upsert_bloodlines(BOOK_ID, CHAPTER, bloodlines, BATCH_ID)
        assert result == 1
        # Only 1 MERGE call, no StateChange (owner is empty)
        assert mock_neo4j_session.run.call_count == 1

    async def test_state_change_fields_correct(self, repo, mock_neo4j_session):
        bloodlines = [
            ExtractedBloodline(
                name="Bloodline of the Primal Hunter",
                owner="Jake Thayne",
                awakened_chapter=42,
            ),
        ]
        await repo.upsert_bloodlines(BOOK_ID, CHAPTER, bloodlines, BATCH_ID)
        # Second call is the StateChange
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["category"] == "bloodline"
        assert changes[0]["name"] == "Bloodline of the Primal Hunter"
        assert changes[0]["action"] == "awaken"
        assert changes[0]["character_name"] == "Jake Thayne"

    async def test_awakened_chapter_defaults_to_current(self, repo, mock_neo4j_session):
        bloodlines = [
            ExtractedBloodline(
                name="Bloodline of the Primal Hunter",
                owner="Jake Thayne",
                awakened_chapter=None,  # should default to CHAPTER
            ),
        ]
        await repo.upsert_bloodlines(BOOK_ID, CHAPTER, bloodlines, BATCH_ID)
        params = mock_neo4j_session.run.call_args_list[0][0][1]
        assert params["bloodlines"][0]["awakened_chapter"] == CHAPTER


# ── upsert_professions ──────────────────────────────────────────────────


class TestUpsertProfessions:
    async def test_empty_professions_returns_zero(self, repo, mock_neo4j_session):
        result = await repo.upsert_professions(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_normal_professions_returns_count(self, repo, mock_neo4j_session):
        professions = [
            ExtractedProfession(
                name="Alchemist of the Malefic Viper",
                tier=3,
                profession_type="crafting",
                owner="Jake Thayne",
                acquired_chapter=55,
            ),
        ]
        result = await repo.upsert_professions(BOOK_ID, CHAPTER, professions, BATCH_ID)
        assert result == 1
        # 1 call for MERGE + 1 call for StateChange
        assert mock_neo4j_session.run.call_count == 2

    async def test_profession_without_owner_no_state_change(self, repo, mock_neo4j_session):
        professions = [
            ExtractedProfession(
                name="Blacksmith",
                tier=1,
                owner="",
            ),
        ]
        result = await repo.upsert_professions(BOOK_ID, CHAPTER, professions, BATCH_ID)
        assert result == 1
        # Only 1 MERGE call, no StateChange
        assert mock_neo4j_session.run.call_count == 1

    async def test_state_change_fields_correct(self, repo, mock_neo4j_session):
        professions = [
            ExtractedProfession(
                name="Alchemist of the Malefic Viper",
                owner="Jake Thayne",
            ),
        ]
        await repo.upsert_professions(BOOK_ID, CHAPTER, professions, BATCH_ID)
        state_call = mock_neo4j_session.run.call_args_list[1]
        params = state_call[0][1]
        changes = params["changes"]
        assert len(changes) == 1
        assert changes[0]["category"] == "profession"
        assert changes[0]["name"] == "Alchemist of the Malefic Viper"
        assert changes[0]["action"] == "acquire"
        assert changes[0]["character_name"] == "Jake Thayne"

    async def test_acquired_chapter_defaults_to_current(self, repo, mock_neo4j_session):
        professions = [
            ExtractedProfession(
                name="Alchemist of the Malefic Viper",
                owner="Jake Thayne",
                acquired_chapter=None,
            ),
        ]
        await repo.upsert_professions(BOOK_ID, CHAPTER, professions, BATCH_ID)
        params = mock_neo4j_session.run.call_args_list[0][0][1]
        assert params["professions"][0]["chapter"] == CHAPTER


# ── upsert_churches ──────────────────────────────────────────────────────


class TestUpsertChurches:
    async def test_empty_churches_returns_zero(self, repo, mock_neo4j_session):
        result = await repo.upsert_churches(BOOK_ID, CHAPTER, [], BATCH_ID)
        assert result == 0
        assert mock_neo4j_session.run.call_count == 0

    async def test_normal_churches_returns_count(self, repo, mock_neo4j_session):
        churches = [
            ExtractedChurch(
                deity_name="the Malefic Viper",
                domain="Poison and Alchemy",
                blessing="Viper's Blessing",
                worshipper="Jake Thayne",
                valid_from_chapter=30,
            ),
        ]
        result = await repo.upsert_churches(BOOK_ID, CHAPTER, churches, BATCH_ID)
        assert result == 1
        assert mock_neo4j_session.run.call_count == 1

    async def test_church_without_worshipper(self, repo, mock_neo4j_session):
        churches = [
            ExtractedChurch(
                deity_name="the Holy Mother",
                domain="Life and Healing",
                worshipper="",
            ),
        ]
        result = await repo.upsert_churches(BOOK_ID, CHAPTER, churches, BATCH_ID)
        assert result == 1
        assert mock_neo4j_session.run.call_count == 1

    async def test_passes_correct_params(self, repo, mock_neo4j_session):
        churches = [
            ExtractedChurch(
                deity_name="the Malefic Viper",
                domain="Poison and Alchemy",
                blessing="Viper's Blessing",
                worshipper="Jake Thayne",
                valid_from_chapter=30,
            ),
        ]
        await repo.upsert_churches(BOOK_ID, CHAPTER, churches, BATCH_ID)
        params = mock_neo4j_session.run.call_args[0][1]
        assert params["book_id"] == BOOK_ID
        assert params["batch_id"] == BATCH_ID
        assert len(params["churches"]) == 1
        assert params["churches"][0]["deity_name"] == "the Malefic Viper"
        assert params["churches"][0]["domain"] == "Poison and Alchemy"
        assert params["churches"][0]["blessing"] == "Viper's Blessing"
        assert params["churches"][0]["worshipper"] == "Jake Thayne"
        assert params["churches"][0]["chapter"] == 30

    async def test_valid_from_chapter_defaults_to_current(self, repo, mock_neo4j_session):
        churches = [
            ExtractedChurch(
                deity_name="the Malefic Viper",
                worshipper="Jake Thayne",
                valid_from_chapter=None,
            ),
        ]
        await repo.upsert_churches(BOOK_ID, CHAPTER, churches, BATCH_ID)
        params = mock_neo4j_session.run.call_args[0][1]
        assert params["churches"][0]["chapter"] == CHAPTER
