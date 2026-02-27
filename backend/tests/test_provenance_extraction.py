"""Tests for provenance extraction service."""

from __future__ import annotations

from unittest.mock import patch

from app.schemas.extraction import SkillProvenance
from app.services.extraction.provenance import extract_provenance


class TestExtractProvenance:
    async def test_returns_empty_for_no_skills(self):
        result = await extract_provenance("text", [], {})
        assert result.provenances == []

    async def test_returns_provenances_with_mocked_llm(self):
        with patch("app.services.extraction.provenance._call_instructor") as mock:
            mock.return_value = [
                SkillProvenance(
                    skill_name="Shadow Strike",
                    source_type="item",
                    source_name="Nanoblade",
                    confidence=0.9,
                    context="test context",
                ),
            ]
            result = await extract_provenance("text", ["Shadow Strike"], {"items": ["Nanoblade"]})
            assert len(result.provenances) == 1
            assert result.provenances[0].source_name == "Nanoblade"

    async def test_filters_low_confidence(self):
        with patch("app.services.extraction.provenance._call_instructor") as mock:
            mock.return_value = [
                SkillProvenance(
                    skill_name="A",
                    source_type="item",
                    source_name="X",
                    confidence=0.9,
                    context="test context",
                ),
                SkillProvenance(
                    skill_name="B",
                    source_type="unknown",
                    source_name="",
                    confidence=0.3,
                    context="",
                ),
            ]
            result = await extract_provenance("text", ["A", "B"], {})
            assert len(result.provenances) == 1
            assert result.provenances[0].skill_name == "A"

    async def test_handles_llm_failure(self):
        with patch("app.services.extraction.provenance._call_instructor") as mock:
            mock.return_value = []
            result = await extract_provenance("text", ["Skill"], {})
            assert result.provenances == []

    async def test_high_confidence_count_in_logging(self):
        """Verify that provenances at exactly 0.5 are kept (boundary)."""
        with patch("app.services.extraction.provenance._call_instructor") as mock:
            mock.return_value = [
                SkillProvenance(
                    skill_name="Edge",
                    source_type="class",
                    source_name="Warrior",
                    confidence=0.5,
                    context="test context",
                ),
            ]
            result = await extract_provenance("text", ["Edge"], {})
            assert len(result.provenances) == 1

    async def test_multiple_provenances_mixed_confidence(self):
        """Test mix of high, medium, and low confidence provenances."""
        with patch("app.services.extraction.provenance._call_instructor") as mock:
            mock.return_value = [
                SkillProvenance(
                    skill_name="A",
                    source_type="item",
                    source_name="Sword",
                    confidence=0.95,
                    context="test context",
                ),
                SkillProvenance(
                    skill_name="B",
                    source_type="class",
                    source_name="Mage",
                    confidence=0.6,
                    context="test context",
                ),
                SkillProvenance(
                    skill_name="C",
                    source_type="unknown",
                    source_name="",
                    confidence=0.2,
                    context="",
                ),
            ]
            result = await extract_provenance("text", ["A", "B", "C"], {})
            assert len(result.provenances) == 2
            names = [p.skill_name for p in result.provenances]
            assert "A" in names
            assert "B" in names
            assert "C" not in names

    async def test_passes_entities_to_instructor(self):
        """Verify chapter_entities are forwarded to _call_instructor."""
        with patch("app.services.extraction.provenance._call_instructor") as mock:
            mock.return_value = []
            entities = {
                "items": ["Nanoblade", "Amulet"],
                "classes": ["Hunter"],
                "bloodlines": ["Bloodline of the Primal Hunter"],
            }
            await extract_provenance("chapter text here", ["Skill1"], entities)
            mock.assert_called_once_with(
                "chapter text here",
                ["Skill1"],
                entities,
            )
