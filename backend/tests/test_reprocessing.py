"""Tests for the selective reprocessing pipeline."""

from app.schemas.ontology import OntologyChange
from app.services.reprocessing import ImpactScope, compute_impact_scope


class TestComputeImpactScope:
    def test_add_entity_type_core(self):
        changes = [
            OntologyChange(
                change_type="add_entity_type",
                layer="core",
                target="NewEntity",
                proposed_by="system",
                confidence=0.9,
                evidence=["Found in text"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert "NewEntity" in scope.affected_entity_types
        assert 1 in scope.affected_phases

    def test_add_entity_type_genre(self):
        changes = [
            OntologyChange(
                change_type="add_entity_type",
                layer="genre",
                target="QuestLog",
                proposed_by="system",
                confidence=0.8,
                evidence=["Found pattern"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert 2 in scope.affected_phases

    def test_add_entity_type_series(self):
        changes = [
            OntologyChange(
                change_type="add_entity_type",
                layer="series",
                target="PrimordialChurch",
                proposed_by="system",
                confidence=0.95,
                evidence=["Mentioned in text"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert "PrimordialChurch" in scope.affected_entity_types
        assert 3 in scope.affected_phases

    def test_add_regex_pattern(self):
        changes = [
            OntologyChange(
                change_type="add_regex",
                layer="genre",
                target="bloodline_pattern",
                proposed_by="system",
                confidence=0.9,
                evidence=["Regex proposal"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert 0 in scope.affected_phases
        assert len(scope.new_regex_patterns) == 1

    def test_modify_property(self):
        changes = [
            OntologyChange(
                change_type="modify_property",
                layer="core",
                target="Character",
                proposed_by="admin",
                confidence=1.0,
                evidence=["Schema update"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert "Character" in scope.affected_entity_types
        assert 4 in scope.affected_phases

    def test_multiple_changes_deduplicate(self):
        changes = [
            OntologyChange(
                change_type="add_entity_type",
                layer="genre",
                target="A",
                proposed_by="system",
                confidence=1.0,
                evidence=["e"],
            ),
            OntologyChange(
                change_type="add_entity_type",
                layer="genre",
                target="B",
                proposed_by="system",
                confidence=1.0,
                evidence=["e"],
            ),
            OntologyChange(
                change_type="modify_property",
                layer="core",
                target="Character",
                proposed_by="system",
                confidence=1.0,
                evidence=["e"],
            ),
        ]
        scope = compute_impact_scope(changes)
        # Phase 2 should appear once, not twice
        assert scope.affected_phases.count(2) == 1

    def test_empty_changes(self):
        scope = compute_impact_scope([])
        assert scope.affected_entity_types == []
        assert scope.affected_phases == []
        assert not scope.requires_full_reextract

    def test_add_relationship_type(self):
        changes = [
            OntologyChange(
                change_type="add_relationship_type",
                layer="series",
                target="HAS_BLOODLINE",
                proposed_by="system",
                confidence=0.9,
                evidence=["New relation"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert 4 in scope.affected_phases

    def test_add_property(self):
        changes = [
            OntologyChange(
                change_type="add_property",
                layer="genre",
                target="Skill",
                proposed_by="admin",
                confidence=1.0,
                evidence=["New property needed"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert "Skill" in scope.affected_entity_types
        assert 4 in scope.affected_phases

    def test_extend_enum(self):
        changes = [
            OntologyChange(
                change_type="extend_enum",
                layer="core",
                target="Character",
                proposed_by="auto_discovery",
                confidence=0.85,
                evidence=["New enum value found"],
            )
        ]
        scope = compute_impact_scope(changes)
        assert "Character" in scope.affected_entity_types
        assert 4 in scope.affected_phases

    def test_mixed_changes_phases_sorted(self):
        changes = [
            OntologyChange(
                change_type="add_regex",
                layer="genre",
                target="pattern1",
                proposed_by="system",
                confidence=0.9,
                evidence=["e"],
            ),
            OntologyChange(
                change_type="add_entity_type",
                layer="series",
                target="NewType",
                proposed_by="system",
                confidence=0.9,
                evidence=["e"],
            ),
            OntologyChange(
                change_type="add_entity_type",
                layer="core",
                target="AnotherType",
                proposed_by="system",
                confidence=0.9,
                evidence=["e"],
            ),
        ]
        scope = compute_impact_scope(changes)
        # Phases should be sorted
        assert scope.affected_phases == sorted(scope.affected_phases)
        assert 0 in scope.affected_phases  # regex
        assert 1 in scope.affected_phases  # core
        assert 3 in scope.affected_phases  # series

    def test_impact_scope_defaults(self):
        scope = ImpactScope()
        assert scope.affected_entity_types == []
        assert scope.affected_phases == []
        assert scope.new_regex_patterns == []
        assert scope.requires_full_reextract is False
