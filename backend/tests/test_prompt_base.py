"""Tests for V3 prompt base template and all prompt module exports."""

from __future__ import annotations


class TestPromptLanguage:
    def test_french_config(self) -> None:
        from app.prompts.base import get_language_config

        config = get_language_config("fr")
        assert config.role_prefix == "Tu es"
        assert config.constraint_label == "CONTRAINTES"

    def test_english_config(self) -> None:
        from app.prompts.base import get_language_config

        config = get_language_config("en")
        assert config.role_prefix == "You are"

    def test_default_is_french(self) -> None:
        from app.prompts.base import get_language_config

        config = get_language_config()
        assert config.code == "fr"

    def test_unknown_falls_back_to_french(self) -> None:
        from app.prompts.base import get_language_config

        config = get_language_config("de")
        assert config.code == "fr"


class TestBuildExtractionPrompt:
    def test_basic_prompt(self) -> None:
        from app.prompts.base import build_extraction_prompt

        prompt = build_extraction_prompt(
            phase=1,
            role_description="un extracteur expert en entit\u00e9s narratives",
            ontology_schema={"Character": {"properties": {"name": "string"}}},
        )
        assert "CONTRAINTES" in prompt
        assert "Character" in prompt
        assert "Phase d'extraction: 1" in prompt

    def test_with_context(self) -> None:
        from app.prompts.base import build_extraction_prompt

        prompt = build_extraction_prompt(
            phase=1,
            role_description="test",
            ontology_schema={},
            entity_registry_context="- jake thayne (Character)",
            previous_summary="Jake entered the tutorial.",
            phase0_hints=[{"name": "Basic Archery", "type": "Skill"}],
        )
        assert "jake thayne" in prompt
        assert "tutorial" in prompt
        assert "Basic Archery" in prompt

    def test_english_mode(self) -> None:
        from app.prompts.base import build_extraction_prompt

        prompt = build_extraction_prompt(
            phase=1,
            role_description="an expert entity extractor",
            ontology_schema={},
            language="en",
        )
        assert "CONSTRAINTS" in prompt
        assert "You are" in prompt

    def test_with_few_shots(self) -> None:
        from app.prompts.base import build_extraction_prompt

        prompt = build_extraction_prompt(
            phase=1,
            role_description="test",
            ontology_schema={},
            few_shot_examples="Input: 'Jake drew his bow'\nOutput: {name: 'Jake'}",
        )
        assert "EXEMPLES" in prompt
        assert "Jake drew his bow" in prompt

    def test_no_context_section_when_empty(self) -> None:
        from app.prompts.base import build_extraction_prompt

        prompt = build_extraction_prompt(
            phase=1,
            role_description="test",
            ontology_schema={},
        )
        assert "CONTEXTE" not in prompt

    def test_phase_number_in_prompt(self) -> None:
        from app.prompts.base import build_extraction_prompt

        for phase in range(6):
            prompt = build_extraction_prompt(
                phase=phase,
                role_description="test",
                ontology_schema={},
            )
            assert f"Phase d'extraction: {phase}" in prompt

    def test_ontology_schema_json_in_prompt(self) -> None:
        from app.prompts.base import build_extraction_prompt

        schema = {
            "Character": {
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "enum"},
                }
            }
        }
        prompt = build_extraction_prompt(
            phase=1,
            role_description="test",
            ontology_schema=schema,
        )
        assert '"Character"' in prompt
        assert '"name"' in prompt
        assert "```json" in prompt

    def test_phase0_hints_json_serialized(self) -> None:
        from app.prompts.base import build_extraction_prompt

        hints = [
            {"name": "\u0152il de l'Archer", "type": "Skill", "rank": "rare"},
        ]
        prompt = build_extraction_prompt(
            phase=2,
            role_description="test",
            ontology_schema={},
            phase0_hints=hints,
        )
        assert "\u0152il de l'Archer" in prompt
        assert "Indices Phase 0" in prompt


class TestPromptModuleExports:
    """Verify all prompt modules export the expected constants."""

    def test_characters_prompt(self) -> None:
        from app.prompts.extraction_characters import (
            FEW_SHOT_EXAMPLES,
            PROMPT_DESCRIPTION,
        )

        assert (
            "personnage" in PROMPT_DESCRIPTION.lower() or "character" in PROMPT_DESCRIPTION.lower()
        )
        assert len(FEW_SHOT_EXAMPLES) >= 1

    def test_systems_prompt(self) -> None:
        from app.prompts.extraction_systems import (
            FEW_SHOT_EXAMPLES,
            PROMPT_DESCRIPTION,
        )

        assert len(FEW_SHOT_EXAMPLES) >= 1
        assert "competence" in PROMPT_DESCRIPTION.lower() or "skill" in PROMPT_DESCRIPTION.lower()

    def test_events_prompt(self) -> None:
        from app.prompts.extraction_events import (
            FEW_SHOT_EXAMPLES,
            PROMPT_DESCRIPTION,
        )

        assert len(FEW_SHOT_EXAMPLES) >= 1
        assert "evenement" in PROMPT_DESCRIPTION.lower() or "event" in PROMPT_DESCRIPTION.lower()

    def test_lore_prompt(self) -> None:
        from app.prompts.extraction_lore import (
            FEW_SHOT_EXAMPLES,
            PROMPT_DESCRIPTION,
        )

        assert len(FEW_SHOT_EXAMPLES) >= 1
        assert "worldbuilding" in PROMPT_DESCRIPTION.lower() or "lore" in PROMPT_DESCRIPTION.lower()

    def test_creatures_prompt(self) -> None:
        from app.prompts.extraction_creatures import (
            FEW_SHOT_EXAMPLES,
            PROMPT_DESCRIPTION,
        )

        assert len(FEW_SHOT_EXAMPLES) >= 1
        assert "creature" in PROMPT_DESCRIPTION.lower()

    def test_series_prompt(self) -> None:
        from app.prompts.extraction_series import (
            FEW_SHOT_EXAMPLES,
            PROMPT_DESCRIPTION,
            SERIES_FEW_SHOT,
            SERIES_SYSTEM_PROMPT,
        )

        assert len(FEW_SHOT_EXAMPLES) >= 1
        # Legacy aliases work
        assert SERIES_SYSTEM_PROMPT == PROMPT_DESCRIPTION
        assert SERIES_FEW_SHOT == FEW_SHOT_EXAMPLES

    def test_discovery_prompt(self) -> None:
        from app.prompts.extraction_discovery import (
            FEW_SHOT_EXAMPLES,
            PROMPT_DESCRIPTION,
        )

        assert len(FEW_SHOT_EXAMPLES) >= 1
        assert "ontologie" in PROMPT_DESCRIPTION.lower() or "lacune" in PROMPT_DESCRIPTION.lower()

    def test_provenance_prompt(self) -> None:
        from app.prompts.extraction_provenance import (
            FEW_SHOT_EXAMPLES,
            PROVENANCE_FEW_SHOT,
            PROVENANCE_SYSTEM_PROMPT,
        )

        assert len(FEW_SHOT_EXAMPLES) >= 1
        # Legacy aliases work
        assert PROVENANCE_FEW_SHOT == FEW_SHOT_EXAMPLES
        assert isinstance(PROVENANCE_SYSTEM_PROMPT, str)

    def test_coreference_prompt(self) -> None:
        from app.prompts.coreference import (
            COREFERENCE_PROMPT,
            FEW_SHOT_EXAMPLES,
        )

        assert isinstance(COREFERENCE_PROMPT, str)
        assert "{entity_context}" in COREFERENCE_PROMPT
        assert "{text}" in COREFERENCE_PROMPT
        assert len(FEW_SHOT_EXAMPLES) >= 1

    def test_narrative_analysis_prompt(self) -> None:
        from app.prompts.narrative_analysis import (
            FEW_SHOT_EXAMPLES,
            NARRATIVE_ANALYSIS_PROMPT,
        )

        assert isinstance(NARRATIVE_ANALYSIS_PROMPT, str)
        assert "{entity_context}" in NARRATIVE_ANALYSIS_PROMPT
        assert "{chapter_text}" in NARRATIVE_ANALYSIS_PROMPT
        assert len(FEW_SHOT_EXAMPLES) >= 1


class TestPromptLanguageConsistency:
    """Verify all prompts are primarily in French."""

    def test_characters_in_french(self) -> None:
        from app.prompts.extraction_characters import PROMPT_DESCRIPTION

        # Should contain French keywords
        assert "extrais" in PROMPT_DESCRIPTION.lower()

    def test_systems_in_french(self) -> None:
        from app.prompts.extraction_systems import PROMPT_DESCRIPTION

        assert "extrais" in PROMPT_DESCRIPTION.lower()

    def test_events_in_french(self) -> None:
        from app.prompts.extraction_events import PROMPT_DESCRIPTION

        assert "extrais" in PROMPT_DESCRIPTION.lower()

    def test_lore_in_french(self) -> None:
        from app.prompts.extraction_lore import PROMPT_DESCRIPTION

        assert "extrais" in PROMPT_DESCRIPTION.lower()

    def test_coreference_in_french(self) -> None:
        from app.prompts.coreference import COREFERENCE_PROMPT

        assert "resous" in COREFERENCE_PROMPT.lower() or "r\u00e9sous" in COREFERENCE_PROMPT.lower()

    def test_narrative_in_french(self) -> None:
        from app.prompts.narrative_analysis import NARRATIVE_ANALYSIS_PROMPT

        assert "analyse" in NARRATIVE_ANALYSIS_PROMPT.lower()


class TestFewShotExamplesQuality:
    """Verify few-shot examples contain realistic Primal Hunter content."""

    def test_characters_has_jake(self) -> None:
        from app.prompts.extraction_characters import FEW_SHOT_EXAMPLES

        all_text = " ".join(ex.text for ex in FEW_SHOT_EXAMPLES)
        assert "Jake" in all_text or "jake" in all_text

    def test_systems_has_skill_notation(self) -> None:
        from app.prompts.extraction_systems import FEW_SHOT_EXAMPLES

        all_text = " ".join(ex.text for ex in FEW_SHOT_EXAMPLES)
        # Blue box notation
        assert "[" in all_text

    def test_events_has_significance_levels(self) -> None:
        from app.prompts.extraction_events import FEW_SHOT_EXAMPLES

        all_attrs = []
        for ex in FEW_SHOT_EXAMPLES:
            for extraction in ex.extractions:
                if "significance" in extraction.attributes:
                    all_attrs.append(extraction.attributes["significance"])
        assert "major" in all_attrs or "minor" in all_attrs

    def test_lore_has_location(self) -> None:
        from app.prompts.extraction_lore import FEW_SHOT_EXAMPLES

        has_location = False
        for ex in FEW_SHOT_EXAMPLES:
            for extraction in ex.extractions:
                if extraction.extraction_class == "location":
                    has_location = True
        assert has_location

    def test_creatures_has_species(self) -> None:
        from app.prompts.extraction_creatures import FEW_SHOT_EXAMPLES

        has_creature = False
        for ex in FEW_SHOT_EXAMPLES:
            for extraction in ex.extractions:
                if extraction.extraction_class == "creature":
                    has_creature = True
        assert has_creature
