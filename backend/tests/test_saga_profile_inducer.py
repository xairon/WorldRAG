"""Tests for SagaProfileInducer — 5 tests covering the induction algorithm."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.saga_profile.inducer import (
    MIN_CLUSTER_SIZE,
    MIN_CONFIDENCE,
    SagaProfileInducer,
    _cluster_entities,
    _detect_patterns,
    _induce_relations_llm,
)
from app.services.saga_profile.models import (
    InducedEntityType,
    InducedPattern,
    InducedRelationType,
    SagaProfile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(name: str, summary: str, labels: list[str]) -> dict:
    return {"name": name, "summary": summary, "labels": labels}


def _mock_neo4j_driver(entities: list[dict]) -> AsyncMock:
    """Build a mock Neo4j AsyncDriver that returns *entities* from session.run().data()."""
    result_mock = AsyncMock()
    result_mock.data = MagicMock(return_value=entities)

    session_mock = AsyncMock()
    session_mock.run = AsyncMock(return_value=result_mock)
    session_mock.__aenter__ = AsyncMock(return_value=session_mock)
    session_mock.__aexit__ = AsyncMock(return_value=False)

    driver = AsyncMock()
    driver.session = MagicMock(return_value=session_mock)

    return driver


# ---------------------------------------------------------------------------
# 1. test_inducer_returns_saga_profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inducer_returns_saga_profile():
    """Full pipeline: mock Neo4j + LLM, verify SagaProfile output."""
    entities = [
        _make_entity("Fireball", "A fire spell", ["Entity", "Concept"]),
        _make_entity("Ice Shard", "An ice spell", ["Entity", "Concept"]),
        _make_entity("Lightning Bolt", "An electric spell", ["Entity", "Concept"]),
        _make_entity("Aldric", "A warrior", ["Entity", "Character"]),
        _make_entity("Dungeon of Doom", "A dark dungeon", ["Entity", "Location"]),
    ]
    driver = _mock_neo4j_driver(entities)

    formalized = [
        {
            "type_name": "Spell",
            "parent_universal": "Concept",
            "description": "A magical ability",
            "typical_attributes": ["element", "mana_cost"],
            "instances_found": ["Fireball", "Ice Shard", "Lightning Bolt"],
            "confidence": 0.9,
        }
    ]

    with patch(
        "app.services.saga_profile.inducer._formalize_clusters_llm",
        new_callable=AsyncMock,
        return_value=formalized,
    ), patch(
        "app.services.saga_profile.inducer._induce_relations_llm",
        new_callable=AsyncMock,
        return_value=[],
    ):
        inducer = SagaProfileInducer(driver)
        profile = await inducer.induce(
            saga_id="saga-1",
            saga_name="Test Saga",
            source_book="book-1",
            raw_text="Some text with no patterns.",
        )

    assert isinstance(profile, SagaProfile)
    assert profile.saga_id == "saga-1"
    assert profile.saga_name == "Test Saga"
    assert len(profile.entity_types) == 1
    assert profile.entity_types[0].type_name == "Spell"
    assert profile.entity_types[0].confidence == 0.9


# ---------------------------------------------------------------------------
# 2. test_low_confidence_types_filtered
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_confidence_types_filtered():
    """Types with confidence < MIN_CONFIDENCE are excluded from the profile."""
    entities = [
        _make_entity("A", "desc", ["Entity", "Concept"]),
        _make_entity("B", "desc", ["Entity", "Concept"]),
        _make_entity("C", "desc", ["Entity", "Concept"]),
    ]
    driver = _mock_neo4j_driver(entities)

    formalized = [
        {
            "type_name": "WeakType",
            "parent_universal": "Concept",
            "description": "Low confidence type",
            "typical_attributes": [],
            "instances_found": ["A", "B", "C"],
            "confidence": 0.3,  # Below MIN_CONFIDENCE
        }
    ]

    with patch(
        "app.services.saga_profile.inducer._formalize_clusters_llm",
        new_callable=AsyncMock,
        return_value=formalized,
    ), patch(
        "app.services.saga_profile.inducer._induce_relations_llm",
        new_callable=AsyncMock,
        return_value=[],
    ):
        inducer = SagaProfileInducer(driver)
        profile = await inducer.induce(
            saga_id="saga-2",
            saga_name="Filtered Saga",
            source_book="book-2",
            raw_text="",
        )

    assert len(profile.entity_types) == 0


# ---------------------------------------------------------------------------
# 3. test_detect_patterns_litrpg
# ---------------------------------------------------------------------------

def test_detect_patterns_litrpg():
    """LitRPG patterns like [Skill Acquired: X] are detected with ≥2 matches."""
    text = (
        "You focus your mind.\n"
        "[Skill Acquired: Fireball]\n"
        "The heat courses through your veins.\n"
        "[Skill Acquired: Ice Shield]\n"
        "A cold barrier forms around you.\n"
        "[Skill Acquired: Lightning Strike]\n"
    )
    patterns = _detect_patterns(text)
    assert len(patterns) >= 1

    skill_pattern = next(
        (p for p in patterns if "skill" in p.extraction_type.lower()),
        None,
    )
    assert skill_pattern is not None
    assert isinstance(skill_pattern, InducedPattern)
    assert skill_pattern.confidence > 0


# ---------------------------------------------------------------------------
# 4. test_detect_patterns_no_matches
# ---------------------------------------------------------------------------

def test_detect_patterns_no_matches():
    """Plain prose with no structured patterns returns an empty list."""
    text = (
        "The old man walked slowly through the village. "
        "He stopped to pet a dog. The sun was setting."
    )
    patterns = _detect_patterns(text)
    assert patterns == []


# ---------------------------------------------------------------------------
# 5. test_cluster_entities_min_size
# ---------------------------------------------------------------------------

def test_cluster_entities_min_size():
    """Only clusters with ≥ MIN_CLUSTER_SIZE members are kept."""
    entities = [
        _make_entity("A", "desc", ["Entity", "Concept"]),
        _make_entity("B", "desc", ["Entity", "Concept"]),
        _make_entity("C", "desc", ["Entity", "Concept"]),
        # Character has only 1 member → excluded
        _make_entity("Hero", "desc", ["Entity", "Character"]),
        # Location has only 2 members → excluded
        _make_entity("Town", "desc", ["Entity", "Location"]),
        _make_entity("Forest", "desc", ["Entity", "Location"]),
    ]
    clusters = _cluster_entities(entities)

    assert len(clusters) == 1
    assert clusters[0]["label"] == "Concept"
    assert len(clusters[0]["members"]) == 3


# ---------------------------------------------------------------------------
# 6. test_induce_relations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_induce_relations():
    """_induce_relations_llm returns parsed InducedRelationType dicts from LLM JSON."""
    entity_types = [
        InducedEntityType(
            type_name="Spell",
            parent_universal="Concept",
            description="A magical ability",
            instances_found=["Fireball", "Ice Shard"],
            typical_attributes=["element", "mana_cost"],
            confidence=0.9,
        ),
        InducedEntityType(
            type_name="Guild",
            parent_universal="Organization",
            description="A group of adventurers",
            instances_found=["Mage's Circle", "Warrior Brotherhood"],
            typical_attributes=["rank", "territory"],
            confidence=0.85,
        ),
    ]
    entities = [
        _make_entity("Fireball", "A fire spell", ["Entity", "Concept"]),
        _make_entity("Aldric", "A warrior", ["Entity", "Character"]),
        _make_entity("Mage's Circle", "A guild of mages", ["Entity", "Organization"]),
    ]

    # LLM returns a JSON array with one valid and one invalid (unknown type) relation
    llm_response_json = (
        "[\n"
        '  {"relation_name": "has_spell", "source_type": "Character", "target_type": "Spell", '
        '"cardinality": "N:N", "temporal": true, "description": "Character can cast a spell"},\n'
        '  {"relation_name": "member_of", "source_type": "Character", "target_type": "Guild", '
        '"cardinality": "N:N", "temporal": true, "description": "Character belongs to a guild"},\n'
        '  {"relation_name": "invalid_relation", "source_type": "UnknownType", "target_type": "Spell", '
        '"cardinality": "1:1", "temporal": false, "description": "Should be filtered out"}\n'
        "]"
    )

    llm_mock = AsyncMock()
    llm_response_mock = MagicMock()
    llm_response_mock.content = llm_response_json
    llm_mock.ainvoke = AsyncMock(return_value=llm_response_mock)

    with patch("app.llm.providers.get_langchain_llm", return_value=llm_mock):
        result = await _induce_relations_llm(entity_types, entities)

    # Two valid relations (UnknownType is filtered out)
    assert len(result) == 2
    relation_names = {r["relation_name"] for r in result}
    assert "has_spell" in relation_names
    assert "member_of" in relation_names
    assert "invalid_relation" not in relation_names

    # Verify the dicts can be parsed into InducedRelationType models
    for r in result:
        model = InducedRelationType(**r)
        assert model.relation_name
        assert model.source_type
        assert model.target_type


@pytest.mark.asyncio
async def test_induce_full_pipeline_produces_relations():
    """Full induce() pipeline wires relation types from _induce_relations_llm into SagaProfile."""
    entities = [
        _make_entity("Fireball", "A fire spell", ["Entity", "Concept"]),
        _make_entity("Ice Shard", "An ice spell", ["Entity", "Concept"]),
        _make_entity("Lightning Bolt", "An electric spell", ["Entity", "Concept"]),
    ]
    driver = _mock_neo4j_driver(entities)

    formalized = [
        {
            "type_name": "Spell",
            "parent_universal": "Concept",
            "description": "A magical ability",
            "typical_attributes": ["element"],
            "instances_found": ["Fireball", "Ice Shard", "Lightning Bolt"],
            "confidence": 0.9,
        }
    ]
    relations = [
        {
            "relation_name": "has_spell",
            "source_type": "Character",
            "target_type": "Spell",
            "cardinality": "N:N",
            "temporal": True,
            "description": "Character can cast a spell",
        }
    ]

    with patch(
        "app.services.saga_profile.inducer._formalize_clusters_llm",
        new_callable=AsyncMock,
        return_value=formalized,
    ), patch(
        "app.services.saga_profile.inducer._induce_relations_llm",
        new_callable=AsyncMock,
        return_value=relations,
    ):
        inducer = SagaProfileInducer(driver)
        profile = await inducer.induce(
            saga_id="saga-3",
            saga_name="Relations Saga",
            source_book="book-3",
            raw_text="",
        )

    assert len(profile.relation_types) == 1
    rel = profile.relation_types[0]
    assert isinstance(rel, InducedRelationType)
    assert rel.relation_name == "has_spell"
    assert rel.source_type == "Character"
    assert rel.target_type == "Spell"
    assert rel.cardinality == "N:N"
    assert rel.temporal is True
