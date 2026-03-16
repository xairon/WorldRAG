"""Tests for v4 extraction schemas (15-type discriminated union)."""

import pytest
from pydantic import ValidationError

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    EntityUnion,
    ExtractedBloodline,
    ExtractedCharacter,
    ExtractedChurch,
    ExtractedClass,
    ExtractedConcept,
    ExtractedCreature,
    ExtractedEvent,
    ExtractedFaction,
    ExtractedItem,
    ExtractedLevelChange,
    ExtractedLocation,
    ExtractedProfession,
    ExtractedRelation,
    ExtractedSkill,
    ExtractedStatChange,
    ExtractedTitle,
    RelationEnd,
    RelationExtractionResult,
)


# ── 1. Character roundtrip ────────────────────────────────────────────────


def test_character_roundtrip():
    char = ExtractedCharacter(
        name="Jake Thayne",
        canonical_name="Jake Thayne",
        aliases=["Jake", "The Primal Hunter"],
        role="protagonist",
        species="Human",
        description="A hunter awakened in the tutorial.",
        status="alive",
        extraction_text="Jake Thayne stepped forward.",
        char_offset_start=0,
        char_offset_end=26,
    )
    dumped = char.model_dump()
    assert dumped["entity_type"] == "character"
    assert dumped["name"] == "Jake Thayne"
    assert dumped["aliases"] == ["Jake", "The Primal Hunter"]

    reloaded = ExtractedCharacter.model_validate(dumped)
    assert reloaded.name == char.name
    assert reloaded.status == "alive"


# ── 2. Literal["class"] is valid Python ───────────────────────────────────


def test_class_literal_is_valid():
    cls = ExtractedClass(
        name="Sword Saint",
        tier=3,
        owner="Jake Thayne",
        description="An advanced swordsman class.",
        extraction_text="Jake gained the Sword Saint class.",
    )
    assert cls.entity_type == "class"
    dumped = cls.model_dump()
    assert dumped["entity_type"] == "class"
    reloaded = ExtractedClass.model_validate(dumped)
    assert reloaded.entity_type == "class"


# ── 3. Discriminated union deserialization ────────────────────────────────


def test_discriminated_union_deserialization():
    raw_entities = [
        {
            "entity_type": "character",
            "name": "Alice",
            "extraction_text": "Alice ran.",
        },
        {
            "entity_type": "skill",
            "name": "Fireball",
            "skill_type": "active",
            "extraction_text": "He cast Fireball.",
        },
        {
            "entity_type": "location",
            "name": "Dark Forest",
            "extraction_text": "They entered the Dark Forest.",
        },
    ]

    result = EntityExtractionResult(entities=raw_entities, chapter_number=5)
    assert len(result.entities) == 3
    assert isinstance(result.entities[0], ExtractedCharacter)
    assert isinstance(result.entities[1], ExtractedSkill)
    assert isinstance(result.entities[2], ExtractedLocation)
    assert result.chapter_number == 5


# ── 4. All 15 entity types have correct discriminators ────────────────────


def test_all_15_entity_types():
    entities = [
        ExtractedCharacter(name="A", extraction_text="A"),
        ExtractedSkill(name="B", extraction_text="B"),
        ExtractedClass(name="C", extraction_text="C"),
        ExtractedTitle(name="D", extraction_text="D"),
        ExtractedEvent(name="E", extraction_text="E"),
        ExtractedLocation(name="F", extraction_text="F"),
        ExtractedItem(name="G", extraction_text="G"),
        ExtractedCreature(name="H", extraction_text="H"),
        ExtractedFaction(name="I", extraction_text="I"),
        ExtractedConcept(name="J", extraction_text="J"),
        ExtractedLevelChange(character="K", extraction_text="K"),
        ExtractedStatChange(character="L", stat_name="Strength", value=5, extraction_text="L"),
        ExtractedBloodline(name="M", extraction_text="M"),
        ExtractedProfession(name="N", extraction_text="N"),
        ExtractedChurch(deity_name="O", extraction_text="O"),
    ]

    expected_types = [
        "character",
        "skill",
        "class",
        "title",
        "event",
        "location",
        "item",
        "creature",
        "faction",
        "concept",
        "level_change",
        "stat_change",
        "bloodline",
        "profession",
        "church",
    ]

    assert len(entities) == 15
    for entity, expected_type in zip(entities, expected_types):
        assert entity.entity_type == expected_type, (
            f"Expected {expected_type}, got {entity.entity_type}"
        )


# ── 5. Default offsets are -1 ─────────────────────────────────────────────


def test_default_offsets_are_minus_one():
    char = ExtractedCharacter(name="Zack", extraction_text="Zack appeared.")
    assert char.char_offset_start == -1
    assert char.char_offset_end == -1

    skill = ExtractedSkill(name="Slash", extraction_text="He used Slash.")
    assert skill.char_offset_start == -1
    assert skill.char_offset_end == -1

    event = ExtractedEvent(name="Battle", extraction_text="A battle began.")
    assert event.char_offset_start == -1
    assert event.char_offset_end == -1


# ── 6. Relation roundtrip ─────────────────────────────────────────────────


def test_relation_roundtrip():
    relation = ExtractedRelation(
        source="Jake Thayne",
        target="Miranda",
        relation_type="ALLIED_WITH",
        subtype="combat_partner",
        sentiment=0.8,
        valid_from_chapter=3,
        context="They fought side by side against the beast.",
    )
    dumped = relation.model_dump()
    assert dumped["source"] == "Jake Thayne"
    assert dumped["relation_type"] == "ALLIED_WITH"
    assert dumped["sentiment"] == 0.8

    reloaded = ExtractedRelation.model_validate(dumped)
    assert reloaded.source == relation.source
    assert reloaded.valid_from_chapter == 3


# ── 7. RelationEnd roundtrip ──────────────────────────────────────────────


def test_relation_end():
    ended = RelationEnd(
        source="Jake Thayne",
        target="The Order",
        relation_type="MEMBER_OF",
        ended_at_chapter=12,
        reason="Jake left the Order after the betrayal.",
    )
    assert ended.ended_at_chapter == 12
    dumped = ended.model_dump()
    reloaded = RelationEnd.model_validate(dumped)
    assert reloaded.reason == ended.reason


# ── 8. RelationExtractionResult with ended relations ─────────────────────


def test_relation_result_with_ended():
    result = RelationExtractionResult(
        relations=[
            ExtractedRelation(
                source="A",
                target="B",
                relation_type="ALLIED_WITH",
                context="Together.",
            )
        ],
        ended_relations=[
            RelationEnd(
                source="C",
                target="D",
                relation_type="MEMBER_OF",
                ended_at_chapter=7,
                reason="Conflict.",
            )
        ],
    )
    assert len(result.relations) == 1
    assert len(result.ended_relations) == 1
    assert result.ended_relations[0].ended_at_chapter == 7


# ── 9. Sentiment bounds validation ───────────────────────────────────────


def test_sentiment_bounds():
    # Valid boundary values
    r_low = ExtractedRelation(
        source="A", target="B", relation_type="ENEMY_OF", sentiment=-1.0, context=""
    )
    assert r_low.sentiment == -1.0

    r_high = ExtractedRelation(
        source="A", target="B", relation_type="ALLIED_WITH", sentiment=1.0, context=""
    )
    assert r_high.sentiment == 1.0

    # None is valid
    r_none = ExtractedRelation(
        source="A", target="B", relation_type="KNOWS", sentiment=None, context=""
    )
    assert r_none.sentiment is None

    # Out-of-bounds should raise
    with pytest.raises(ValidationError):
        ExtractedRelation(
            source="A", target="B", relation_type="ALLIED_WITH", sentiment=1.5, context=""
        )

    with pytest.raises(ValidationError):
        ExtractedRelation(
            source="A", target="B", relation_type="ALLIED_WITH", sentiment=-2.0, context=""
        )
