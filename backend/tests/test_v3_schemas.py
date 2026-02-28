"""Tests for V3 extraction schemas."""

from typing import Literal

import pytest
from pydantic import ValidationError


class TestBaseExtractedEntity:
    def test_required_fields(self):
        from app.schemas.extraction import BaseExtractedEntity

        entity = BaseExtractedEntity(
            name="Jake Thayne",
            canonical_name="jake thayne",
            entity_type="Character",
            confidence=0.95,
            extraction_text="Jake drew his bow",
            char_offset_start=0,
            char_offset_end=17,
            chapter_number=1,
            extraction_layer="narrative",
            extraction_phase=1,
            ontology_version="3.0.0",
        )
        assert entity.name == "Jake Thayne"
        assert entity.confidence == 0.95
        assert entity.extraction_layer == "narrative"

    def test_confidence_bounds_high(self):
        from app.schemas.extraction import BaseExtractedEntity

        with pytest.raises(ValidationError):
            BaseExtractedEntity(
                name="X",
                canonical_name="x",
                entity_type="Character",
                confidence=1.5,
                extraction_text="X",
                char_offset_start=0,
                char_offset_end=1,
                chapter_number=1,
                extraction_layer="narrative",
                extraction_phase=1,
                ontology_version="3.0.0",
            )

    def test_confidence_bounds_low(self):
        from app.schemas.extraction import BaseExtractedEntity

        with pytest.raises(ValidationError):
            BaseExtractedEntity(
                name="X",
                canonical_name="x",
                entity_type="Character",
                confidence=-0.1,
                extraction_text="X",
                char_offset_start=0,
                char_offset_end=1,
                chapter_number=1,
                extraction_layer="narrative",
                extraction_phase=1,
                ontology_version="3.0.0",
            )

    def test_extraction_layer_literal(self):
        from app.schemas.extraction import BaseExtractedEntity

        with pytest.raises(ValidationError):
            BaseExtractedEntity(
                name="X",
                canonical_name="x",
                entity_type="Character",
                confidence=0.9,
                extraction_text="X",
                char_offset_start=0,
                char_offset_end=1,
                chapter_number=1,
                extraction_layer="invalid",  # type: ignore[arg-type]
                extraction_phase=1,
                ontology_version="3.0.0",
            )


class TestExtractedStatBlock:
    def test_create(self):
        from app.schemas.extraction import ExtractedStatBlock

        sb = ExtractedStatBlock(
            character_name="Jake Thayne",
            stats={"Strength": 42, "Agility": 38},
            total=80,
            source="blue_box",
            chapter_number=5,
        )
        assert sb.stats["Strength"] == 42
        assert sb.source == "blue_box"

    def test_source_default(self):
        from app.schemas.extraction import ExtractedStatBlock

        sb = ExtractedStatBlock(
            character_name="Jake",
            stats={"Strength": 10},
            chapter_number=1,
        )
        assert sb.source == "blue_box"


class TestExtractedCharacterV3:
    def test_new_fields_defaults(self):
        from app.schemas.extraction import ExtractedCharacter

        char = ExtractedCharacter(
            name="Jake",
            canonical_name="jake thayne",
            aliases=["the hunter"],
            role="protagonist",
            description="An archer",
        )
        assert char.status == "alive"
        assert char.last_seen_chapter is None
        assert char.evolution_of is None

    def test_status_values(self):
        from app.schemas.extraction import ExtractedCharacter

        statuses: list[Literal["alive", "dead", "unknown", "transformed"]] = [
            "alive", "dead", "unknown", "transformed",
        ]
        for status in statuses:
            char = ExtractedCharacter(
                name="Test",
                canonical_name="test",
                role="minor",
                description="Test character",
                status=status,
            )
            assert char.status == status


class TestExtractionPipelineStateV3:
    def test_new_state_fields(self):
        from app.agents.state import ExtractionPipelineState

        annotations = ExtractionPipelineState.__annotations__
        assert "entity_registry" in annotations
        assert "ontology_version" in annotations
        assert "extraction_run_id" in annotations
        assert "phase0_regex" in annotations
        assert "phase1_narrative" in annotations
        assert "phase2_genre" in annotations
        assert "phase3_series" in annotations
        assert "source_language" in annotations
