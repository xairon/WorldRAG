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
)
from app.services.saga_profile.models import InducedPattern, SagaProfile


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
