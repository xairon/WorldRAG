"""Tests for unified entity + relation extraction prompts (v4)."""

from __future__ import annotations

from app.prompts.extraction_unified import build_entity_prompt, build_relation_prompt


def test_entity_prompt_contains_all_sections() -> None:
    prompt = build_entity_prompt(
        registry_context="jake: Character",
        phase0_hints=[{"type": "skill_acquired"}],
        router_hints=["Éléments de système (skills, classes, levels)"],
        language="fr",
    )
    assert "CHARACTER" in prompt
    assert "SKILL" in prompt
    assert "BLOODLINE" in prompt  # Layer 3
    assert "[FOCUS]" in prompt
    assert "jake" in prompt  # registry injected


def test_relation_prompt_contains_entities() -> None:
    prompt = build_relation_prompt(
        entities_json='[{"entity_type": "character", "name": "Jake"}]',
        language="fr",
    )
    assert "RELATES_TO" in prompt
    assert "HAS_SKILL" in prompt
    assert "Jake" in prompt
    assert "invalidation" in prompt.lower()


def test_entity_prompt_without_hints() -> None:
    prompt = build_entity_prompt(language="fr")
    assert "CHARACTER" in prompt
    # No FOCUS section when no hints
    assert "[FOCUS]" not in prompt


def test_entity_prompt_phase_label() -> None:
    prompt = build_entity_prompt(language="fr")
    assert "entities" in prompt


def test_entity_prompt_few_shot_included() -> None:
    prompt = build_entity_prompt(language="fr")
    # Few-shot examples are injected for French
    assert "Frappe Foudroyante" in prompt


def test_relation_prompt_few_shot_included() -> None:
    prompt = build_relation_prompt(language="fr")
    assert "ended_relations" in prompt
    assert "RelationEnd" in prompt or "ended_relation" in prompt.lower() or "ended_relations" in prompt


def test_entity_prompt_no_focus_without_router_hints() -> None:
    prompt = build_entity_prompt(
        registry_context="aria: Character",
        phase0_hints=[{"type": "level_up"}],
        language="fr",
    )
    # router_hints=None → no [FOCUS]
    assert "[FOCUS]" not in prompt
    # but registry and phase0 are present
    assert "aria" in prompt
    assert "level_up" in prompt


def test_relation_prompt_extracted_entities_section() -> None:
    entities = '[{"entity_type": "character", "canonical_name": "jake"}]'
    prompt = build_relation_prompt(entities_json=entities, language="fr")
    assert "ENTITÉS EXTRAITES" in prompt
    assert "jake" in prompt


def test_entity_prompt_all_15_types() -> None:
    prompt = build_entity_prompt(language="fr")
    for entity_type in [
        "CHARACTER", "EVENT", "LOCATION", "ITEM", "ARC",
        "CLASS", "SKILL", "STAT", "TITLE", "LEVEL", "SYSTEM", "FACTION",
        "BLOODLINE", "PROFESSION", "QUEST",
    ]:
        assert entity_type in prompt, f"Missing entity type: {entity_type}"


def test_relation_prompt_all_16_relation_types() -> None:
    prompt = build_relation_prompt(language="fr")
    for rel_type in [
        "RELATES_TO", "MEMBER_OF", "HAS_SKILL", "HAS_CLASS", "HAS_TITLE",
        "PARTICIPATES_IN", "OCCURS_AT", "LOCATED_AT", "POSSESSES",
        "CAUSES", "ENABLES", "PART_OF", "EVOLVES_INTO", "IS_RACE",
        "INHABITS", "BELONGS_TO",
    ]:
        assert rel_type in prompt, f"Missing relation type: {rel_type}"
