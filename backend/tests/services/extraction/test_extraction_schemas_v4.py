"""Tests for v4 extraction schemas (12-type discriminated union)."""

import pytest
from pydantic import ValidationError

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    EntityUnion,
    ExtractedArc,
    ExtractedCharacter,
    ExtractedConcept,
    ExtractedCreature,
    ExtractedEvent,
    ExtractedFaction,
    ExtractedGenreEntity,
    ExtractedItem,
    ExtractedLevelChange,
    ExtractedLocation,
    ExtractedProphecy,
    ExtractedRelation,
    ExtractedStatChange,
    RelationEnd,
    RelationExtractionResult,
)


# ── 1. ExtractedArc roundtrip ────────────────────────────────────────────


def test_arc_roundtrip():
    arc = ExtractedArc(
        name="The Tutorial",
        canonical_name="The Tutorial",
        arc_type="main_plot",
        status="completed",
        description="The initial tutorial arc.",
        extraction_text="The tutorial began.",
        char_offset_start=0,
        char_offset_end=20,
    )
    dumped = arc.model_dump()
    assert dumped["entity_type"] == "arc"
    assert dumped["name"] == "The Tutorial"
    assert dumped["arc_type"] == "main_plot"

    reloaded = ExtractedArc.model_validate(dumped)
    assert reloaded.name == arc.name
    assert reloaded.status == "completed"


# ── 2. ExtractedProphecy roundtrip ───────────────────────────────────────


def test_prophecy_roundtrip():
    prophecy = ExtractedProphecy(
        name="The Chosen One Prophecy",
        canonical_name="The Chosen One Prophecy",
        status="unfulfilled",
        description="A prophecy about the one who will restore balance.",
        extraction_text="It was foretold that the chosen one would come.",
        char_offset_start=100,
        char_offset_end=148,
    )
    dumped = prophecy.model_dump()
    assert dumped["entity_type"] == "prophecy"
    assert dumped["name"] == "The Chosen One Prophecy"

    reloaded = ExtractedProphecy.model_validate(dumped)
    assert reloaded.name == prophecy.name
    assert reloaded.status == "unfulfilled"


# ── 3. ExtractedGenreEntity with various sub_types ──────────────────────


def test_genre_entity_skill():
    ge = ExtractedGenreEntity(
        sub_type="skill",
        name="Fireball",
        description="A fire-based attack skill.",
        owner="Jake",
        effects=["deals fire damage"],
        properties={"skill_type": "active", "mana_cost": 15},
    )
    assert ge.entity_type == "genre_entity"
    assert ge.sub_type == "skill"
    dumped = ge.model_dump()
    assert dumped["properties"]["mana_cost"] == 15
    reloaded = ExtractedGenreEntity.model_validate(dumped)
    assert reloaded.sub_type == "skill"


def test_genre_entity_bloodline():
    ge = ExtractedGenreEntity(
        sub_type="bloodline",
        name="Bloodline of the Primal Hunter",
        description="An ancient bloodline.",
        owner="Jake Thayne",
        tier="S",
        effects=["enhanced perception", "predator instinct"],
    )
    assert ge.entity_type == "genre_entity"
    assert ge.sub_type == "bloodline"
    assert len(ge.effects) == 2


def test_genre_entity_spell():
    ge = ExtractedGenreEntity(
        sub_type="spell",
        name="Arcane Shield",
        description="A defensive spell.",
        properties={"element": "arcane", "level_required": 5},
    )
    assert ge.entity_type == "genre_entity"
    assert ge.sub_type == "spell"
    assert ge.properties["element"] == "arcane"


# ── 4. Discriminated union resolves all 12 types ────────────────────────


def test_all_12_entity_types():
    entities = [
        ExtractedCharacter(name="A", extraction_text="A"),
        ExtractedEvent(name="B", extraction_text="B"),
        ExtractedLocation(name="C", extraction_text="C"),
        ExtractedItem(name="D", extraction_text="D"),
        ExtractedCreature(name="E", extraction_text="E"),
        ExtractedFaction(name="F", extraction_text="F"),
        ExtractedConcept(name="G", extraction_text="G"),
        ExtractedArc(name="H"),
        ExtractedProphecy(name="I"),
        ExtractedLevelChange(character="J", extraction_text="J"),
        ExtractedStatChange(character="K", stat_name="Str", value=5, extraction_text="K"),
        ExtractedGenreEntity(sub_type="skill", name="L"),
    ]

    expected_types = [
        "character", "event", "location", "item", "creature",
        "faction", "concept", "arc", "prophecy",
        "level_change", "stat_change", "genre_entity",
    ]

    assert len(entities) == 12
    for entity, expected_type in zip(entities, expected_types):
        assert entity.entity_type == expected_type, (
            f"Expected {expected_type}, got {entity.entity_type}"
        )


def test_discriminated_union_deserialization_all_12():
    """All 12 types deserialize correctly via EntityExtractionResult."""
    raw_entities = [
        {"entity_type": "character", "name": "Alice", "extraction_text": "Alice ran."},
        {"entity_type": "event", "name": "Battle", "extraction_text": "A battle."},
        {"entity_type": "location", "name": "Forest", "extraction_text": "The forest."},
        {"entity_type": "item", "name": "Sword", "extraction_text": "A sword."},
        {"entity_type": "creature", "name": "Wolf", "extraction_text": "A wolf."},
        {"entity_type": "faction", "name": "Guild", "extraction_text": "The guild."},
        {"entity_type": "concept", "name": "Mana", "extraction_text": "Mana flows."},
        {"entity_type": "arc", "name": "Tutorial Arc"},
        {"entity_type": "prophecy", "name": "Dark Prophecy"},
        {"entity_type": "level_change", "character": "Jake", "extraction_text": "Level up."},
        {"entity_type": "stat_change", "character": "Jake", "stat_name": "STR", "value": 3, "extraction_text": "STR+3."},
        {"entity_type": "genre_entity", "sub_type": "class", "name": "Sword Saint"},
    ]

    result = EntityExtractionResult(entities=raw_entities, chapter_number=1)
    assert len(result.entities) == 12
    assert isinstance(result.entities[0], ExtractedCharacter)
    assert isinstance(result.entities[7], ExtractedArc)
    assert isinstance(result.entities[8], ExtractedProphecy)
    assert isinstance(result.entities[11], ExtractedGenreEntity)


# ── 5. relation_type is plain str (no coercion) ─────────────────────────


def test_relation_type_is_plain_str():
    """relation_type accepts any string, no coercion."""
    r1 = ExtractedRelation(
        source="A", target="B", relation_type="CUSTOM_REL", context="test"
    )
    assert r1.relation_type == "CUSTOM_REL"

    r2 = ExtractedRelation(
        source="A", target="B", relation_type="whatever_string", context="test"
    )
    assert r2.relation_type == "whatever_string"

    r3 = ExtractedRelation(
        source="A", target="B", relation_type="RELATES_TO", context="test"
    )
    assert r3.relation_type == "RELATES_TO"


# ── 6. Mixed-type EntityExtractionResult ────────────────────────────────


def test_mixed_type_entity_extraction_result():
    raw = [
        {"entity_type": "character", "name": "Jake", "role": "protagonist", "extraction_text": "Jake."},
        {"entity_type": "genre_entity", "sub_type": "skill", "name": "Fireball"},
        {"entity_type": "arc", "name": "The Hunt"},
        {"entity_type": "location", "name": "Dark Forest", "extraction_text": "Forest."},
    ]
    result = EntityExtractionResult(entities=raw, chapter_number=5)
    assert len(result.entities) == 4
    assert isinstance(result.entities[0], ExtractedCharacter)
    assert isinstance(result.entities[1], ExtractedGenreEntity)
    assert isinstance(result.entities[2], ExtractedArc)
    assert isinstance(result.entities[3], ExtractedLocation)


# ── 7. Core enum coercion still works ───────────────────────────────────


def test_role_coercion():
    char = ExtractedCharacter(name="Test", role="PROTAGONIST", extraction_text="Test.")
    assert char.role == "protagonist"

    char2 = ExtractedCharacter(name="Test", role="unknown_role", extraction_text="Test.")
    assert char2.role == "minor"  # default fallback


def test_status_coercion():
    char = ExtractedCharacter(name="Test", status="DEAD", extraction_text="Test.")
    assert char.status == "dead"


def test_event_type_coercion():
    event = ExtractedEvent(name="Battle", event_type="COMBAT", extraction_text="Battle.")
    assert event.event_type == "combat"

    event2 = ExtractedEvent(name="Battle", event_type="nonsense", extraction_text="Battle.")
    assert event2.event_type == "action"  # default fallback


# ── 8. Character roundtrip (kept from original) ─────────────────────────


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
    assert dumped["aliases"] == ["Jake", "The Primal Hunter"]

    reloaded = ExtractedCharacter.model_validate(dumped)
    assert reloaded.name == char.name
    assert reloaded.status == "alive"


# ── 9. Sentiment bounds ────────────────────────────────────────────────


def test_sentiment_bounds():
    r_low = ExtractedRelation(
        source="A", target="B", relation_type="RELATES_TO", sentiment=-1.0, context=""
    )
    assert r_low.sentiment == -1.0

    r_high = ExtractedRelation(
        source="A", target="B", relation_type="RELATES_TO", sentiment=1.0, context=""
    )
    assert r_high.sentiment == 1.0

    with pytest.raises(ValidationError):
        ExtractedRelation(
            source="A", target="B", relation_type="RELATES_TO", sentiment=1.5, context=""
        )


# ── 10. RelationEnd and RelationExtractionResult ────────────────────────


def test_relation_end():
    ended = RelationEnd(
        source="Jake",
        target="The Order",
        relation_type="MEMBER_OF",
        ended_at_chapter=12,
        reason="Jake left.",
    )
    assert ended.ended_at_chapter == 12
    dumped = ended.model_dump()
    reloaded = RelationEnd.model_validate(dumped)
    assert reloaded.reason == ended.reason


def test_relation_result_with_ended():
    result = RelationExtractionResult(
        relations=[
            ExtractedRelation(source="A", target="B", relation_type="ALLIES_WITH", context="Together.")
        ],
        ended_relations=[
            RelationEnd(source="C", target="D", relation_type="MEMBER_OF", ended_at_chapter=7, reason="Conflict.")
        ],
    )
    assert len(result.relations) == 1
    assert len(result.ended_relations) == 1


# ── 11. Default offsets ────────────────────────────────────────────────


def test_default_offsets():
    arc = ExtractedArc(name="Test Arc")
    assert arc.char_offset_start == -1
    assert arc.char_offset_end == -1

    prophecy = ExtractedProphecy(name="Test Prophecy")
    assert prophecy.char_offset_start == -1
    assert prophecy.char_offset_end == -1

    ge = ExtractedGenreEntity(sub_type="skill", name="Test")
    assert ge.char_offset_start == -1
    assert ge.char_offset_end == -1
