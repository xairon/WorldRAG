"""Tests for apply_alias_map_v4() in graph_builder service."""

from app.services.graph_builder import apply_alias_map_v4


def test_apply_alias_map_v4_normalizes_entities():
    entities = [
        {"entity_type": "character", "name": "Jon", "canonical_name": "jon"},
        {"entity_type": "skill", "name": "Strike", "owner": "Jon"},
    ]
    relations = [{"source": "Jon", "target": "Strike", "relation_type": "HAS_SKILL"}]
    alias_map = {"jon": "jake"}

    apply_alias_map_v4(entities, relations, alias_map)
    assert entities[0]["canonical_name"] == "jake"
    assert entities[1]["owner"] == "jake"
    assert relations[0]["source"] == "jake"


def test_apply_alias_map_v4_case_insensitive():
    entities = [{"entity_type": "character", "name": "JAKE", "canonical_name": "JAKE"}]
    alias_map = {"jake": "jacob"}
    apply_alias_map_v4(entities, [], alias_map)
    assert entities[0]["canonical_name"] == "jacob"


def test_apply_alias_map_v4_no_alias_map():
    entities = [{"entity_type": "character", "name": "Alice", "canonical_name": "alice"}]
    relations = [{"source": "Alice", "target": "Bob"}]
    apply_alias_map_v4(entities, relations, {})
    # No changes when alias_map is empty
    assert entities[0]["name"] == "Alice"
    assert relations[0]["source"] == "Alice"


def test_apply_alias_map_v4_character_field():
    entities = [
        {"entity_type": "level_change", "character": "Jon", "new_level": 10},
        {"entity_type": "stat_change", "character": "Jon", "stat_name": "STR", "value": 5},
    ]
    alias_map = {"jon": "jake"}
    apply_alias_map_v4(entities, [], alias_map)
    assert entities[0]["character"] == "jake"
    assert entities[1]["character"] == "jake"


def test_apply_alias_map_v4_no_mutation_for_unknown_names():
    entities = [{"entity_type": "character", "name": "Unknown", "canonical_name": "unknown"}]
    alias_map = {"jake": "jacob"}
    apply_alias_map_v4(entities, [], alias_map)
    assert entities[0]["name"] == "Unknown"
    assert entities[0]["canonical_name"] == "unknown"
