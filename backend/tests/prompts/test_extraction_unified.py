"""Tests for dynamic ontology-driven prompt builders (v4)."""

from __future__ import annotations

from app.core.ontology_loader import OntologyLoader
from app.prompts.extraction_unified import build_entity_prompt, build_relation_prompt


def _get_ontology(genre: str = "litrpg", series: str = "") -> OntologyLoader:
    return OntologyLoader.from_layers(genre=genre, series=series)


def test_entity_prompt_en_contains_core_types():
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "CHARACTER" in prompt
    assert "EVENT" in prompt
    assert "LOCATION" in prompt
    assert "ARC" in prompt
    assert "PROPHECY" in prompt


def test_entity_prompt_en_contains_genre_types():
    onto = _get_ontology(genre="litrpg")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "SKILL" in prompt
    assert "genre_entity" in prompt


def test_entity_prompt_en_contains_series_types():
    onto = _get_ontology(genre="litrpg", series="primal_hunter")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "BLOODLINE" in prompt


def test_entity_prompt_fr_works():
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="fr")
    assert "CHARACTER" in prompt or "character" in prompt.lower()
    assert len(prompt) > 500


def test_entity_prompt_en_is_not_empty():
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert len(prompt) > 500


def test_entity_prompt_core_only_no_genre_types():
    # genre="" loads only core.yaml (logs a warning, that's OK)
    onto = OntologyLoader.from_layers(genre="", series="")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "CHARACTER" in prompt
    assert "SKILL" not in prompt
    assert "BLOODLINE" not in prompt


def test_entity_prompt_injects_ontology_schema():
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "ontology" in prompt.lower() or "Target" in prompt


def test_entity_prompt_with_registry_and_hints():
    onto = _get_ontology()
    prompt = build_entity_prompt(
        ontology=onto,
        language="en",
        registry_context="jake thayne: character, protagonist",
        phase0_hints=[{"type": "skill_acquired", "name": "Shadow Step"}],
    )
    assert "jake thayne" in prompt
    assert "Shadow Step" in prompt


def test_relation_prompt_en_contains_relation_types():
    onto = _get_ontology()
    prompt = build_relation_prompt(
        ontology=onto,
        entities_json='[{"entity_type": "character", "name": "Jake"}]',
        language="en",
    )
    assert "RELATES_TO" in prompt
    assert "Jake" in prompt


def test_relation_prompt_includes_layer3_relations():
    onto = _get_ontology(genre="litrpg", series="primal_hunter")
    prompt = build_relation_prompt(
        ontology=onto,
        entities_json="[]",
        language="en",
    )
    assert "HAS_BLOODLINE" in prompt
    assert "WORSHIPS" in prompt


def test_few_shots_included_for_litrpg_en():
    onto = _get_ontology(genre="litrpg")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "Example" in prompt or "example" in prompt


def test_few_shots_included_for_fr():
    onto = _get_ontology(genre="litrpg")
    prompt = build_entity_prompt(ontology=onto, language="fr")
    assert "Exemple" in prompt or "exemple" in prompt
