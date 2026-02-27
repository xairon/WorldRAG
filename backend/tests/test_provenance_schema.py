"""Tests for V3 provenance Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.extraction import (
    ProvenanceResult,
    SkillProvenance,
)


class TestSkillProvenance:
    def test_creates_with_required_fields(self):
        prov = SkillProvenance(
            skill_name="Shadow Strike",
            source_type="unknown",
            source_name="",
            confidence=0.5,
            context="",
        )
        assert prov.skill_name == "Shadow Strike"
        assert prov.source_type == "unknown"
        assert prov.source_name == ""
        assert prov.confidence == 0.5
        assert prov.context == ""

    def test_creates_with_all_fields(self):
        prov = SkillProvenance(
            skill_name="Shadow Strike",
            source_type="item",
            source_name="Nanoblade",
            confidence=0.95,
            context="The blade's enchantment granted him a new combat technique.",
        )
        assert prov.source_type == "item"
        assert prov.source_name == "Nanoblade"
        assert prov.confidence == 0.95
        assert "enchantment" in prov.context

    def test_confidence_min_bound(self):
        prov = SkillProvenance(
            skill_name="Test",
            source_type="unknown",
            source_name="",
            confidence=0.0,
            context="",
        )
        assert prov.confidence == 0.0

    def test_confidence_max_bound(self):
        prov = SkillProvenance(
            skill_name="Test",
            source_type="unknown",
            source_name="",
            confidence=1.0,
            context="",
        )
        assert prov.confidence == 1.0

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            SkillProvenance(
                skill_name="Test",
                source_type="unknown",
                source_name="",
                confidence=-0.1,
                context="",
            )

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            SkillProvenance(
                skill_name="Test",
                source_type="unknown",
                source_name="",
                confidence=1.1,
                context="",
            )

    def test_missing_skill_name_rejected(self):
        with pytest.raises(ValidationError):
            SkillProvenance()  # type: ignore[reportCallIssue]

    def test_default_source_type(self):
        prov = SkillProvenance(
            skill_name="Arcane Powershot",
            source_type="unknown",
            source_name="",
            confidence=0.5,
            context="",
        )
        assert prov.source_type == "unknown"

    def test_serialization_roundtrip(self):
        prov = SkillProvenance(
            skill_name="Arcane Powershot",
            source_type="class",
            source_name="Avaricious Arcane Hunter",
            confidence=0.9,
            context="evolution to Avaricious Arcane Hunter",
        )
        data = prov.model_dump()
        restored = SkillProvenance.model_validate(data)
        assert restored.skill_name == prov.skill_name
        assert restored.confidence == prov.confidence


class TestProvenanceResult:
    def test_creates_empty(self):
        result = ProvenanceResult()
        assert result.provenances == []

    def test_creates_with_provenances(self):
        result = ProvenanceResult(
            provenances=[
                SkillProvenance(
                    skill_name="Shadow Strike",
                    source_type="item",
                    source_name="Nanoblade",
                    confidence=0.95,
                    context="",
                ),
                SkillProvenance(
                    skill_name="Arcane Powershot",
                    source_type="class",
                    source_name="Avaricious Arcane Hunter",
                    confidence=0.9,
                    context="",
                ),
            ]
        )
        assert len(result.provenances) == 2
        assert result.provenances[0].source_type == "item"
        assert result.provenances[1].source_type == "class"

    def test_default_list_independent(self):
        """Verify default_factory creates independent lists per instance."""
        r1 = ProvenanceResult()
        r2 = ProvenanceResult()
        r1.provenances.append(
            SkillProvenance(
                skill_name="Test",
                source_type="unknown",
                source_name="",
                confidence=0.5,
                context="",
            )
        )
        assert len(r2.provenances) == 0

    def test_serialization_roundtrip(self):
        result = ProvenanceResult(
            provenances=[
                SkillProvenance(
                    skill_name="Shadow Strike",
                    source_type="item",
                    source_name="Nanoblade",
                    confidence=0.95,
                    context="",
                ),
            ]
        )
        data = result.model_dump()
        restored = ProvenanceResult.model_validate(data)
        assert len(restored.provenances) == 1
        assert restored.provenances[0].skill_name == "Shadow Strike"
