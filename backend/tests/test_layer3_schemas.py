"""Tests for V3 Layer 3 series-specific Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.extraction import (
    ExtractedBloodline,
    ExtractedChurch,
    ExtractedProfession,
    Layer3ExtractionResult,
)


class TestExtractedBloodline:
    def test_creates_with_required_fields(self):
        bl = ExtractedBloodline(name="Bloodline of the Primal Hunter")
        assert bl.name == "Bloodline of the Primal Hunter"
        assert bl.description == ""
        assert bl.effects == []
        assert bl.origin == ""
        assert bl.owner == ""
        assert bl.awakened_chapter is None

    def test_creates_with_all_fields(self):
        bl = ExtractedBloodline(
            name="Bloodline of the Primal Hunter",
            description="Grants enhanced perception and hunting instincts",
            effects=["enhanced perception", "hunting instincts"],
            origin="Primordial patron",
            owner="Jake Thayne",
            awakened_chapter=42,
        )
        assert bl.description == "Grants enhanced perception and hunting instincts"
        assert len(bl.effects) == 2
        assert bl.origin == "Primordial patron"
        assert bl.owner == "Jake Thayne"
        assert bl.awakened_chapter == 42

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedBloodline()

    def test_effects_default_independent(self):
        """Verify default_factory creates independent lists per instance."""
        bl1 = ExtractedBloodline(name="A")
        bl2 = ExtractedBloodline(name="B")
        bl1.effects.append("perception boost")
        assert len(bl2.effects) == 0

    def test_serialization_roundtrip(self):
        bl = ExtractedBloodline(
            name="Bloodline of the Malefic Viper",
            effects=["poison resistance", "venom mastery"],
            owner="Villy",
            awakened_chapter=10,
        )
        data = bl.model_dump()
        restored = ExtractedBloodline.model_validate(data)
        assert restored.name == bl.name
        assert restored.effects == bl.effects
        assert restored.awakened_chapter == 10


class TestExtractedProfession:
    def test_creates_with_required_fields(self):
        prof = ExtractedProfession(name="Alchemist of the Malefic Viper")
        assert prof.name == "Alchemist of the Malefic Viper"
        assert prof.tier is None
        assert prof.profession_type == ""
        assert prof.owner == ""
        assert prof.acquired_chapter is None

    def test_creates_with_all_fields(self):
        prof = ExtractedProfession(
            name="Alchemist of the Malefic Viper",
            tier=3,
            profession_type="crafting",
            owner="Jake Thayne",
            acquired_chapter=55,
        )
        assert prof.tier == 3
        assert prof.profession_type == "crafting"
        assert prof.owner == "Jake Thayne"
        assert prof.acquired_chapter == 55

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedProfession()

    def test_serialization_roundtrip(self):
        prof = ExtractedProfession(
            name="Alchemist of the Malefic Viper",
            tier=2,
            owner="Jake Thayne",
        )
        data = prof.model_dump()
        restored = ExtractedProfession.model_validate(data)
        assert restored.name == prof.name
        assert restored.tier == 2


class TestExtractedChurch:
    def test_creates_with_required_fields(self):
        church = ExtractedChurch(deity_name="the Malefic Viper")
        assert church.deity_name == "the Malefic Viper"
        assert church.domain == ""
        assert church.blessing == ""
        assert church.worshipper == ""
        assert church.valid_from_chapter is None

    def test_creates_with_all_fields(self):
        church = ExtractedChurch(
            deity_name="the Malefic Viper",
            domain="Poison and Alchemy",
            blessing="Viper's Blessing",
            worshipper="Jake Thayne",
            valid_from_chapter=30,
        )
        assert church.domain == "Poison and Alchemy"
        assert church.blessing == "Viper's Blessing"
        assert church.worshipper == "Jake Thayne"
        assert church.valid_from_chapter == 30

    def test_missing_deity_name_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedChurch()

    def test_serialization_roundtrip(self):
        church = ExtractedChurch(
            deity_name="the Holy Mother",
            domain="Life and Healing",
            worshipper="Priestess Alma",
            valid_from_chapter=5,
        )
        data = church.model_dump()
        restored = ExtractedChurch.model_validate(data)
        assert restored.deity_name == church.deity_name
        assert restored.valid_from_chapter == 5


class TestLayer3ExtractionResult:
    def test_creates_empty(self):
        result = Layer3ExtractionResult()
        assert result.bloodlines == []
        assert result.professions == []
        assert result.churches == []

    def test_creates_with_all_entity_types(self):
        result = Layer3ExtractionResult(
            bloodlines=[
                ExtractedBloodline(
                    name="Bloodline of the Primal Hunter",
                    effects=["enhanced perception"],
                    owner="Jake Thayne",
                ),
            ],
            professions=[
                ExtractedProfession(
                    name="Alchemist of the Malefic Viper",
                    tier=3,
                    owner="Jake Thayne",
                ),
            ],
            churches=[
                ExtractedChurch(
                    deity_name="the Malefic Viper",
                    domain="Poison and Alchemy",
                    worshipper="Jake Thayne",
                ),
            ],
        )
        assert len(result.bloodlines) == 1
        assert len(result.professions) == 1
        assert len(result.churches) == 1
        assert result.bloodlines[0].name == "Bloodline of the Primal Hunter"

    def test_default_lists_independent(self):
        """Verify default_factory creates independent lists per instance."""
        r1 = Layer3ExtractionResult()
        r2 = Layer3ExtractionResult()
        r1.bloodlines.append(ExtractedBloodline(name="Test"))
        r1.professions.append(ExtractedProfession(name="Test"))
        r1.churches.append(ExtractedChurch(deity_name="Test"))
        assert len(r2.bloodlines) == 0
        assert len(r2.professions) == 0
        assert len(r2.churches) == 0

    def test_serialization_roundtrip(self):
        result = Layer3ExtractionResult(
            bloodlines=[
                ExtractedBloodline(
                    name="Bloodline of the Primal Hunter",
                    effects=["enhanced perception", "hunting instincts"],
                    owner="Jake Thayne",
                    awakened_chapter=42,
                ),
            ],
            professions=[
                ExtractedProfession(
                    name="Alchemist of the Malefic Viper",
                    tier=3,
                    owner="Jake Thayne",
                    acquired_chapter=55,
                ),
            ],
            churches=[
                ExtractedChurch(
                    deity_name="the Malefic Viper",
                    domain="Poison and Alchemy",
                    valid_from_chapter=30,
                ),
            ],
        )
        data = result.model_dump()
        restored = Layer3ExtractionResult.model_validate(data)
        assert len(restored.bloodlines) == 1
        assert restored.bloodlines[0].awakened_chapter == 42
        assert restored.professions[0].tier == 3
        assert restored.churches[0].domain == "Poison and Alchemy"
