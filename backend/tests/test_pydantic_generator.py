"""Tests for saga_profile.pydantic_generator — TDD, written before implementation."""

import pytest
from pydantic import BaseModel

from app.services.saga_profile.models import InducedEntityType, InducedRelationType, SagaProfile
from app.services.saga_profile.pydantic_generator import (
    saga_profile_to_graphiti_edges,
    saga_profile_to_graphiti_types,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity_type(type_name: str, typical_attributes: list[str] | None = None) -> InducedEntityType:
    return InducedEntityType(
        type_name=type_name,
        parent_universal="Object",
        description=f"A {type_name} entity",
        typical_attributes=typical_attributes or [],
        confidence=0.9,
    )


def _make_relation_type(
    relation_name: str,
    source_type: str = "Character",
    target_type: str = "Location",
    temporal: bool = False,
) -> InducedRelationType:
    return InducedRelationType(
        relation_name=relation_name,
        source_type=source_type,
        target_type=target_type,
        cardinality="N:N",
        temporal=temporal,
        description=f"Relation {relation_name}",
    )


def _make_profile(
    *entity_types: InducedEntityType,
    relation_types: list[InducedRelationType] | None = None,
) -> SagaProfile:
    return SagaProfile(
        saga_id="test",
        saga_name="Test",
        source_book="b1",
        entity_types=list(entity_types),
        relation_types=relation_types or [],
        text_patterns=[],
        narrative_systems=[],
        estimated_complexity="low",
    )


# ---------------------------------------------------------------------------
# Tests: saga_profile_to_graphiti_types
# ---------------------------------------------------------------------------

class TestSagaProfileToGraphitiTypes:
    def test_universal_types_always_present(self) -> None:
        """An empty profile still returns the 6 universal entity types."""
        profile = _make_profile()
        types = saga_profile_to_graphiti_types(profile)

        assert set(types.keys()) == {"Character", "Location", "Object", "Organization", "Event", "Concept"}

    def test_all_universal_types_are_pydantic_models(self) -> None:
        profile = _make_profile()
        types = saga_profile_to_graphiti_types(profile)

        for name, model in types.items():
            assert issubclass(model, BaseModel), f"{name} is not a Pydantic BaseModel"

    def test_induced_type_added(self) -> None:
        """One induced entity type yields 7 types total."""
        profile = _make_profile(_make_entity_type("Spell"))
        types = saga_profile_to_graphiti_types(profile)

        assert len(types) == 7
        assert "Spell" in types

    def test_induced_type_is_valid_pydantic(self) -> None:
        """Induced type can be instantiated with no arguments (all fields optional)."""
        profile = _make_profile(_make_entity_type("Spell", ["element", "cost"]))
        types = saga_profile_to_graphiti_types(profile)

        SpellModel = types["Spell"]
        instance = SpellModel()  # no args — all fields optional
        assert isinstance(instance, BaseModel)

    def test_induced_type_has_correct_fields(self) -> None:
        """Induced type fields match typical_attributes."""
        attrs = ["element", "cost", "rank"]
        profile = _make_profile(_make_entity_type("Spell", attrs))
        types = saga_profile_to_graphiti_types(profile)

        SpellModel = types["Spell"]
        model_fields = set(SpellModel.model_fields.keys())
        assert set(attrs).issubset(model_fields)

    def test_induced_type_fields_are_optional_strings(self) -> None:
        """Each induced field accepts None and a string value."""
        profile = _make_profile(_make_entity_type("Spell", ["element"]))
        types = saga_profile_to_graphiti_types(profile)
        SpellModel = types["Spell"]

        instance_none = SpellModel(element=None)
        instance_str = SpellModel(element="fire")
        assert instance_none.element is None
        assert instance_str.element == "fire"

    def test_multiple_induced_types(self) -> None:
        """Multiple induced types are all added correctly."""
        profile = _make_profile(
            _make_entity_type("Spell"),
            _make_entity_type("House"),
            _make_entity_type("Class"),
        )
        types = saga_profile_to_graphiti_types(profile)

        assert len(types) == 9  # 6 universal + 3 induced
        assert "Spell" in types
        assert "House" in types
        assert "Class" in types

    def test_induced_type_does_not_override_universal(self) -> None:
        """An induced type named like a universal type should still be returned — the
        caller is responsible for not shadowing, but we verify no crash occurs."""
        profile = _make_profile(_make_entity_type("Character", ["level"]))
        types = saga_profile_to_graphiti_types(profile)

        # Character was induced — universal + induced both exist in result
        # (induced overrides or is merged — either way, Character is in dict)
        assert "Character" in types

    def test_induced_type_no_attributes(self) -> None:
        """An induced type with no typical_attributes is still a valid model."""
        profile = _make_profile(_make_entity_type("Wisp", []))
        types = saga_profile_to_graphiti_types(profile)
        WispModel = types["Wisp"]
        instance = WispModel()
        assert isinstance(instance, BaseModel)


# ---------------------------------------------------------------------------
# Tests: saga_profile_to_graphiti_edges
# ---------------------------------------------------------------------------

class TestSagaProfileToGraphitiEdges:
    def test_empty_profile_returns_empty_dicts(self) -> None:
        profile = _make_profile()
        edge_types, edge_type_map = saga_profile_to_graphiti_edges(profile)

        assert edge_types == {}
        assert edge_type_map == {}

    def test_single_relation_type(self) -> None:
        rel = _make_relation_type("lives_in", "Character", "Location")
        profile = _make_profile(relation_types=[rel])
        edge_types, edge_type_map = saga_profile_to_graphiti_edges(profile)

        assert "lives_in" in edge_types
        assert ("Character", "Location") in edge_type_map
        assert "lives_in" in edge_type_map[("Character", "Location")]

    def test_edge_model_is_valid_pydantic(self) -> None:
        rel = _make_relation_type("lives_in")
        profile = _make_profile(relation_types=[rel])
        edge_types, _ = saga_profile_to_graphiti_edges(profile)

        EdgeModel = edge_types["lives_in"]
        assert issubclass(EdgeModel, BaseModel)
        instance = EdgeModel()
        assert isinstance(instance, BaseModel)

    def test_edge_temporal_field_default_false(self) -> None:
        rel = _make_relation_type("knows", temporal=False)
        profile = _make_profile(relation_types=[rel])
        edge_types, _ = saga_profile_to_graphiti_edges(profile)

        instance = edge_types["knows"]()
        assert instance.temporal is False

    def test_edge_temporal_field_default_true(self) -> None:
        rel = _make_relation_type("ruled", temporal=True)
        profile = _make_profile(relation_types=[rel])
        edge_types, _ = saga_profile_to_graphiti_edges(profile)

        instance = edge_types["ruled"]()
        assert instance.temporal is True

    def test_multiple_edges_same_source_target(self) -> None:
        """Two relations sharing the same (source, target) pair are both registered."""
        rel1 = _make_relation_type("lives_in", "Character", "Location")
        rel2 = _make_relation_type("born_in", "Character", "Location")
        profile = _make_profile(relation_types=[rel1, rel2])
        edge_types, edge_type_map = saga_profile_to_graphiti_edges(profile)

        assert "lives_in" in edge_types
        assert "born_in" in edge_types

        edge_list = edge_type_map[("Character", "Location")]
        assert "lives_in" in edge_list
        assert "born_in" in edge_list
        assert len(edge_list) == 2

    def test_multiple_distinct_source_target_pairs(self) -> None:
        rel1 = _make_relation_type("lives_in", "Character", "Location")
        rel2 = _make_relation_type("owns", "Character", "Object")
        profile = _make_profile(relation_types=[rel1, rel2])
        _, edge_type_map = saga_profile_to_graphiti_edges(profile)

        assert ("Character", "Location") in edge_type_map
        assert ("Character", "Object") in edge_type_map

    def test_edge_type_map_values_are_lists(self) -> None:
        rel = _make_relation_type("lives_in")
        profile = _make_profile(relation_types=[rel])
        _, edge_type_map = saga_profile_to_graphiti_edges(profile)

        for value in edge_type_map.values():
            assert isinstance(value, list)
