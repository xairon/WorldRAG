"""Tests for relation type constraint validation."""

from unittest.mock import MagicMock

from app.services.extraction.validation import validate_relations


class TestValidateRelations:
    def test_valid_relation_passes(self):
        relations = [{"source": "jake", "target": "fireball", "relation_type": "HAS_SKILL"}]
        entity_map = {
            "jake": {"entity_type": "character"},
            "fireball": {"entity_type": "genre_entity"},
        }
        result = validate_relations(relations, entity_map, ontology=None)
        assert len(result) == 1

    def test_no_ontology_allows_all(self):
        """When ontology=None, all relations pass through regardless of types."""
        relations = [{"source": "fireball", "target": "ice bolt", "relation_type": "HAS_SKILL"}]
        entity_map = {
            "fireball": {"entity_type": "skill"},
            "ice bolt": {"entity_type": "skill"},
        }
        result = validate_relations(relations, entity_map, ontology=None)
        assert len(result) == 1

    def test_unknown_relation_type_passes(self):
        relations = [{"source": "a", "target": "b", "relation_type": "CUSTOM_REL"}]
        entity_map = {"a": {"entity_type": "character"}, "b": {"entity_type": "item"}}
        result = validate_relations(relations, entity_map, ontology=None)
        assert len(result) == 1

    def test_missing_entity_in_map_passes(self):
        """If an entity isn't in the map, we can't validate — allow through."""
        relations = [{"source": "jake", "target": "unknown", "relation_type": "HAS_SKILL"}]
        entity_map = {"jake": {"entity_type": "character"}}
        result = validate_relations(relations, entity_map, ontology=None)
        assert len(result) == 1

    def test_empty_relations(self):
        result = validate_relations([], {}, ontology=None)
        assert result == []

    def test_ontology_enforces_constraints(self):
        """With an ontology, invalid source/target types are removed."""
        mock_ontology = MagicMock()
        mock_ontology.get_domain_range.side_effect = lambda rel_type: (
            ({"character"}, {"genre_entity", "skill"}) if rel_type == "HAS_SKILL" else None
        )

        relations = [
            {"source": "jake", "target": "fireball", "relation_type": "HAS_SKILL"},  # valid
            {"source": "fireball", "target": "jake", "relation_type": "HAS_SKILL"},  # invalid src
        ]
        entity_map = {
            "jake": {"entity_type": "character"},
            "fireball": {"entity_type": "genre_entity"},
        }
        result = validate_relations(relations, entity_map, ontology=mock_ontology)
        assert len(result) == 1
        assert result[0]["source"] == "jake"

    def test_ontology_unknown_relation_passes(self):
        """With ontology, a relation type not in domain_range is allowed through."""
        mock_ontology = MagicMock()
        mock_ontology.get_domain_range.return_value = None

        relations = [{"source": "a", "target": "b", "relation_type": "CUSTOM_REL"}]
        entity_map = {"a": {"entity_type": "character"}, "b": {"entity_type": "item"}}
        result = validate_relations(relations, entity_map, ontology=mock_ontology)
        assert len(result) == 1

    def test_ontology_located_at_valid(self):
        """LOCATED_AT with character→location is valid."""
        mock_ontology = MagicMock()
        mock_ontology.get_domain_range.side_effect = lambda rel_type: (
            (
                {"character", "item", "event", "creature", "faction"},
                {"location"},
            )
            if rel_type == "LOCATED_AT"
            else None
        )

        relations = [
            {"source": "jake", "target": "dark forest", "relation_type": "LOCATED_AT"},
        ]
        entity_map = {
            "jake": {"entity_type": "character"},
            "dark forest": {"entity_type": "location"},
        }
        result = validate_relations(relations, entity_map, ontology=mock_ontology)
        assert len(result) == 1
