"""Tests for SagaProfile Pydantic data models — TDD, written before implementation."""

import json

import pytest

from app.services.saga_profile.models import (
    InducedEntityType,
    InducedPattern,
    InducedRelationType,
    SagaProfile,
)


# ---------------------------------------------------------------------------
# InducedEntityType
# ---------------------------------------------------------------------------


class TestInducedEntityType:
    def test_minimal(self):
        entity = InducedEntityType(
            type_name="Spell",
            parent_universal="Concept",
            description="A magical incantation.",
            confidence=0.9,
        )
        assert entity.type_name == "Spell"
        assert entity.parent_universal == "Concept"
        assert entity.description == "A magical incantation."
        assert entity.confidence == 0.9
        assert entity.instances_found == []
        assert entity.typical_attributes == []

    def test_with_instances_and_attributes(self):
        entity = InducedEntityType(
            type_name="House",
            parent_universal="Organization",
            description="A noble house.",
            instances_found=["Stark", "Lannister"],
            typical_attributes=["sigil", "words", "seat"],
            confidence=0.85,
        )
        assert entity.instances_found == ["Stark", "Lannister"]
        assert entity.typical_attributes == ["sigil", "words", "seat"]

    def test_confidence_boundaries(self):
        low = InducedEntityType(
            type_name="Faction",
            parent_universal="Organization",
            description="A faction.",
            confidence=0.0,
        )
        high = InducedEntityType(
            type_name="Faction",
            parent_universal="Organization",
            description="A faction.",
            confidence=1.0,
        )
        assert low.confidence == 0.0
        assert high.confidence == 1.0


# ---------------------------------------------------------------------------
# InducedRelationType
# ---------------------------------------------------------------------------


class TestInducedRelationType:
    def test_minimal(self):
        rel = InducedRelationType(
            relation_name="has_skill",
            source_type="Character",
            target_type="Skill",
            cardinality="1:N",
            temporal=False,
            description="A character possesses a skill.",
        )
        assert rel.relation_name == "has_skill"
        assert rel.source_type == "Character"
        assert rel.target_type == "Skill"
        assert rel.cardinality == "1:N"
        assert rel.temporal is False
        assert rel.description == "A character possesses a skill."

    def test_temporal_relation(self):
        rel = InducedRelationType(
            relation_name="rules_over",
            source_type="Character",
            target_type="Location",
            cardinality="N:N",
            temporal=True,
            description="A character rules a location at a given time.",
        )
        assert rel.temporal is True

    def test_cardinality_variants(self):
        for cardinality in ("1:1", "1:N", "N:N"):
            rel = InducedRelationType(
                relation_name="rel",
                source_type="A",
                target_type="B",
                cardinality=cardinality,
                temporal=False,
                description="desc",
            )
            assert rel.cardinality == cardinality


# ---------------------------------------------------------------------------
# InducedPattern
# ---------------------------------------------------------------------------


class TestInducedPattern:
    def test_minimal(self):
        pattern = InducedPattern(
            pattern_regex=r"\[(\w+)\] Level (\d+)",
            extraction_type="level_box",
            example="[Fighter] Level 12",
            confidence=0.95,
        )
        assert pattern.pattern_regex == r"\[(\w+)\] Level (\d+)"
        assert pattern.extraction_type == "level_box"
        assert pattern.example == "[Fighter] Level 12"
        assert pattern.confidence == 0.95

    def test_confidence_zero(self):
        pattern = InducedPattern(
            pattern_regex=r".*",
            extraction_type="wildcard",
            example="anything",
            confidence=0.0,
        )
        assert pattern.confidence == 0.0


# ---------------------------------------------------------------------------
# SagaProfile (minimal)
# ---------------------------------------------------------------------------


class TestSagaProfileMinimal:
    def test_empty_lists(self):
        profile = SagaProfile(
            saga_id="saga-001",
            saga_name="Test Saga",
            source_book="book-001",
            entity_types=[],
            relation_types=[],
            text_patterns=[],
        )
        assert profile.saga_id == "saga-001"
        assert profile.saga_name == "Test Saga"
        assert profile.source_book == "book-001"
        assert profile.version == 1
        assert profile.entity_types == []
        assert profile.relation_types == []
        assert profile.text_patterns == []
        assert profile.narrative_systems == []
        assert profile.estimated_complexity == "medium"

    def test_custom_version_and_complexity(self):
        profile = SagaProfile(
            saga_id="saga-002",
            saga_name="Advanced Saga",
            source_book="book-002",
            version=3,
            entity_types=[],
            relation_types=[],
            text_patterns=[],
            estimated_complexity="high",
        )
        assert profile.version == 3
        assert profile.estimated_complexity == "high"

    def test_complexity_low(self):
        profile = SagaProfile(
            saga_id="saga-003",
            saga_name="Simple Saga",
            source_book="book-003",
            entity_types=[],
            relation_types=[],
            text_patterns=[],
            estimated_complexity="low",
        )
        assert profile.estimated_complexity == "low"


# ---------------------------------------------------------------------------
# Full realistic Primal Hunter profile
# ---------------------------------------------------------------------------


class TestSagaProfilePrimalHunter:
    @pytest.fixture
    def primal_hunter_profile(self) -> SagaProfile:
        return SagaProfile(
            saga_id="primal-hunter",
            saga_name="The Primal Hunter",
            source_book="the-primal-hunter-book-1",
            version=1,
            narrative_systems=["System", "Levels", "Classes", "Skills", "Titles"],
            estimated_complexity="high",
            entity_types=[
                InducedEntityType(
                    type_name="Class",
                    parent_universal="Concept",
                    description="A system-assigned class determining a hunter's combat style.",
                    instances_found=["Archer", "Mage", "Warrior"],
                    typical_attributes=["name", "grade", "requirements"],
                    confidence=0.98,
                ),
                InducedEntityType(
                    type_name="Skill",
                    parent_universal="Concept",
                    description="An ability granted by the system.",
                    instances_found=["Multi-Shoot", "Stealth", "Haste"],
                    typical_attributes=["name", "rank", "mana_cost", "cooldown"],
                    confidence=0.97,
                ),
                InducedEntityType(
                    type_name="Dungeon",
                    parent_universal="Location",
                    description="An instanced area populated with monsters.",
                    instances_found=["Forest Dungeon", "Cave Dungeon"],
                    typical_attributes=["tier", "element", "boss"],
                    confidence=0.92,
                ),
            ],
            relation_types=[
                InducedRelationType(
                    relation_name="has_class",
                    source_type="Character",
                    target_type="Class",
                    cardinality="1:N",
                    temporal=True,
                    description="Character holds a class (can evolve over time).",
                ),
                InducedRelationType(
                    relation_name="has_skill",
                    source_type="Character",
                    target_type="Skill",
                    cardinality="1:N",
                    temporal=True,
                    description="Character possesses a skill.",
                ),
                InducedRelationType(
                    relation_name="enters_dungeon",
                    source_type="Character",
                    target_type="Dungeon",
                    cardinality="N:N",
                    temporal=False,
                    description="Character has entered a dungeon.",
                ),
            ],
            text_patterns=[
                InducedPattern(
                    pattern_regex=r"You have been granted the class \[([^\]]+)\]",
                    extraction_type="class_grant",
                    example="You have been granted the class [Archer]",
                    confidence=0.99,
                ),
                InducedPattern(
                    pattern_regex=r"\[Skill Gained\]: \[([^\]]+)\]",
                    extraction_type="skill_gain",
                    example="[Skill Gained]: [Multi-Shoot]",
                    confidence=0.99,
                ),
                InducedPattern(
                    pattern_regex=r"Level (\d+) -> (\d+)",
                    extraction_type="level_up",
                    example="Level 12 -> 13",
                    confidence=0.95,
                ),
            ],
        )

    def test_profile_structure(self, primal_hunter_profile: SagaProfile):
        p = primal_hunter_profile
        assert p.saga_id == "primal-hunter"
        assert p.saga_name == "The Primal Hunter"
        assert p.estimated_complexity == "high"
        assert len(p.entity_types) == 3
        assert len(p.relation_types) == 3
        assert len(p.text_patterns) == 3
        assert "System" in p.narrative_systems

    def test_entity_types_data(self, primal_hunter_profile: SagaProfile):
        class_entity = primal_hunter_profile.entity_types[0]
        assert class_entity.type_name == "Class"
        assert class_entity.parent_universal == "Concept"
        assert "Archer" in class_entity.instances_found
        assert class_entity.confidence == 0.98

    def test_relation_types_data(self, primal_hunter_profile: SagaProfile):
        has_class = primal_hunter_profile.relation_types[0]
        assert has_class.relation_name == "has_class"
        assert has_class.temporal is True
        assert has_class.cardinality == "1:N"

    def test_text_patterns_data(self, primal_hunter_profile: SagaProfile):
        pattern = primal_hunter_profile.text_patterns[0]
        assert pattern.extraction_type == "class_grant"
        assert pattern.confidence == 0.99


# ---------------------------------------------------------------------------
# JSON serialisation roundtrip
# ---------------------------------------------------------------------------


class TestJsonRoundtrip:
    def _make_profile(self) -> SagaProfile:
        return SagaProfile(
            saga_id="roundtrip-saga",
            saga_name="Roundtrip Saga",
            source_book="book-rt-001",
            version=2,
            narrative_systems=["Magic", "Levels"],
            estimated_complexity="medium",
            entity_types=[
                InducedEntityType(
                    type_name="Spell",
                    parent_universal="Concept",
                    description="A spell.",
                    instances_found=["Fireball"],
                    typical_attributes=["cost"],
                    confidence=0.9,
                )
            ],
            relation_types=[
                InducedRelationType(
                    relation_name="casts",
                    source_type="Character",
                    target_type="Spell",
                    cardinality="N:N",
                    temporal=False,
                    description="Character casts a spell.",
                )
            ],
            text_patterns=[
                InducedPattern(
                    pattern_regex=r"Fireball",
                    extraction_type="spell_mention",
                    example="Fireball engulfed the room.",
                    confidence=0.88,
                )
            ],
        )

    def test_model_dump_json_and_parse(self):
        original = self._make_profile()
        json_str = original.model_dump_json()

        # Verify it is valid JSON
        data = json.loads(json_str)
        assert data["saga_id"] == "roundtrip-saga"

        # Reconstruct from dict
        reconstructed = SagaProfile.model_validate(data)
        assert reconstructed == original

    def test_model_dump_returns_dict(self):
        profile = self._make_profile()
        d = profile.model_dump()
        assert isinstance(d, dict)
        assert d["version"] == 2
        assert d["entity_types"][0]["type_name"] == "Spell"
        assert d["relation_types"][0]["relation_name"] == "casts"
        assert d["text_patterns"][0]["extraction_type"] == "spell_mention"

    def test_parse_from_raw_dict(self):
        raw = {
            "saga_id": "raw-001",
            "saga_name": "Raw Saga",
            "source_book": "book-raw",
            "entity_types": [],
            "relation_types": [],
            "text_patterns": [],
        }
        profile = SagaProfile.model_validate(raw)
        assert profile.saga_id == "raw-001"
        assert profile.version == 1  # default
        assert profile.estimated_complexity == "medium"  # default
