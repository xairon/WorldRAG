"""Tests for relation type constraint validation."""

from app.services.extraction.validation import validate_relations


class TestValidateRelations:
    def test_valid_relation_passes(self):
        relations = [{"source": "jake", "target": "fireball", "relation_type": "HAS_SKILL"}]
        entity_map = {
            "jake": {"entity_type": "character"},
            "fireball": {"entity_type": "genre_entity"},
        }
        result = validate_relations(relations, entity_map)
        assert len(result) == 1

    def test_invalid_source_type_removed(self):
        relations = [{"source": "fireball", "target": "ice bolt", "relation_type": "HAS_SKILL"}]
        entity_map = {
            "fireball": {"entity_type": "skill"},
            "ice bolt": {"entity_type": "skill"},
        }
        result = validate_relations(relations, entity_map)
        assert len(result) == 0

    def test_unknown_relation_type_passes(self):
        relations = [{"source": "a", "target": "b", "relation_type": "CUSTOM_REL"}]
        entity_map = {"a": {"entity_type": "character"}, "b": {"entity_type": "item"}}
        result = validate_relations(relations, entity_map)
        assert len(result) == 1

    def test_missing_entity_in_map_passes(self):
        """If an entity isn't in the map, we can't validate — allow through."""
        relations = [{"source": "jake", "target": "unknown", "relation_type": "HAS_SKILL"}]
        entity_map = {"jake": {"entity_type": "character"}}
        result = validate_relations(relations, entity_map)
        assert len(result) == 1

    def test_empty_relations(self):
        result = validate_relations([], {})
        assert result == []

    def test_mixed_valid_invalid(self):
        relations = [
            {"source": "jake", "target": "fireball", "relation_type": "HAS_SKILL"},
            {"source": "fireball", "target": "jake", "relation_type": "HAS_SKILL"},  # invalid
            {"source": "jake", "target": "dark forest", "relation_type": "LOCATED_AT"},
        ]
        entity_map = {
            "jake": {"entity_type": "character"},
            "fireball": {"entity_type": "genre_entity"},
            "dark forest": {"entity_type": "location"},
        }
        result = validate_relations(relations, entity_map)
        assert len(result) == 2
