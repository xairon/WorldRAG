"""Tests for v4 extraction schemas (18-type discriminated union, GOLEM v1.1)."""

import pytest
from pydantic import ValidationError

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    ExtractedCharacter,
    ExtractedCharacterFeature,
    ExtractedConcept,
    ExtractedCreature,
    ExtractedEvent,
    ExtractedFaction,
    ExtractedGenreEntity,
    ExtractedLevelChange,
    ExtractedLocation,
    ExtractedNarrativeRole,
    ExtractedNarrativeSequence,
    ExtractedObject,
    ExtractedProphecy,
    ExtractedPsychologicalState,
    ExtractedRelation,
    ExtractedSetting,
    ExtractedSocialRelationship,
    ExtractedStatChange,
    ExtractedTextualFeature,
    RelationEnd,
    RelationExtractionResult,
)

# ── 1. ExtractedNarrativeSequence roundtrip ─────────────────────────────


def test_narrative_sequence_roundtrip():
    seq = ExtractedNarrativeSequence(
        name="The Tutorial",
        canonical_name="The Tutorial",
        sequence_type="main_plot",
        status="completed",
        description="The initial tutorial arc.",
        extraction_text="The tutorial began.",
        char_offset_start=0,
        char_offset_end=20,
    )
    dumped = seq.model_dump()
    assert dumped["entity_type"] == "narrative_sequence"
    assert dumped["name"] == "The Tutorial"
    assert dumped["sequence_type"] == "main_plot"

    reloaded = ExtractedNarrativeSequence.model_validate(dumped)
    assert reloaded.name == seq.name
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


# ── 4. Discriminated union resolves all 18 types ────────────────────────


def test_all_18_entity_types():
    entities = [
        ExtractedCharacter(name="A", extraction_text="A"),
        ExtractedEvent(name="B", extraction_text="B"),
        ExtractedLocation(name="C", extraction_text="C"),
        ExtractedObject(name="D", extraction_text="D"),
        ExtractedCreature(name="E", extraction_text="E"),
        ExtractedFaction(name="F", extraction_text="F"),
        ExtractedConcept(name="G", extraction_text="G"),
        ExtractedNarrativeSequence(name="H"),
        ExtractedProphecy(name="I"),
        ExtractedLevelChange(character="J", extraction_text="J"),
        ExtractedStatChange(character="K", stat_name="Str", value=5, extraction_text="K"),
        ExtractedPsychologicalState(character="L", name="fear", extraction_text="L"),
        ExtractedSetting(name="M", extraction_text="M"),
        ExtractedCharacterFeature(character="N", name="green eyes", extraction_text="N"),
        ExtractedNarrativeRole(character="O", extraction_text="O"),
        ExtractedSocialRelationship(participants=["P", "Q"], extraction_text="P-Q"),
        ExtractedTextualFeature(name="first_person"),
        ExtractedGenreEntity(sub_type="skill", name="R"),
    ]

    expected_types = [
        "character",
        "event",
        "location",
        "object",
        "creature",
        "faction",
        "concept",
        "narrative_sequence",
        "prophecy",
        "level_change",
        "stat_change",
        "psychological_state",
        "setting",
        "character_feature",
        "narrative_role",
        "social_relationship",
        "textual_feature",
        "genre_entity",
    ]

    assert len(entities) == 18
    for entity, expected_type in zip(entities, expected_types, strict=False):
        assert entity.entity_type == expected_type, (
            f"Expected {expected_type}, got {entity.entity_type}"
        )


def test_discriminated_union_deserialization_all_types():
    """All 18 types deserialize correctly via EntityExtractionResult."""
    raw_entities = [
        {"entity_type": "character", "name": "Alice", "extraction_text": "Alice ran."},
        {"entity_type": "event", "name": "Battle", "extraction_text": "A battle."},
        {"entity_type": "location", "name": "Forest", "extraction_text": "The forest."},
        {"entity_type": "object", "name": "Sword", "extraction_text": "A sword."},
        {"entity_type": "creature", "name": "Wolf", "extraction_text": "A wolf."},
        {"entity_type": "faction", "name": "Guild", "extraction_text": "The guild."},
        {"entity_type": "concept", "name": "Mana", "extraction_text": "Mana flows."},
        {"entity_type": "narrative_sequence", "name": "Tutorial Arc"},
        {"entity_type": "prophecy", "name": "Dark Prophecy"},
        {"entity_type": "level_change", "character": "Jake", "extraction_text": "Level up."},
        {
            "entity_type": "stat_change",
            "character": "Jake",
            "stat_name": "STR",
            "value": 3,
            "extraction_text": "STR+3.",
        },
        {
            "entity_type": "psychological_state",
            "character": "Jake",
            "name": "determination",
            "extraction_text": "Jake felt determined.",
        },
        {
            "entity_type": "setting",
            "name": "The Tutorial",
            "extraction_text": "Welcome to the Tutorial.",
        },
        {
            "entity_type": "character_feature",
            "character": "Jake",
            "name": "green eyes",
            "extraction_text": "Jake's green eyes.",
        },
        {
            "entity_type": "narrative_role",
            "character": "Jake",
            "extraction_text": "Jake as protagonist.",
        },
        {
            "entity_type": "social_relationship",
            "participants": ["Jake", "Casper"],
            "extraction_text": "Friendship.",
        },
        {"entity_type": "textual_feature", "name": "first_person_pov"},
        {"entity_type": "genre_entity", "sub_type": "class", "name": "Sword Saint"},
    ]

    result = EntityExtractionResult(entities=raw_entities, chapter_number=1)
    assert len(result.entities) == 18
    assert isinstance(result.entities[0], ExtractedCharacter)
    assert isinstance(result.entities[7], ExtractedNarrativeSequence)
    assert isinstance(result.entities[8], ExtractedProphecy)
    assert isinstance(result.entities[11], ExtractedPsychologicalState)
    assert isinstance(result.entities[12], ExtractedSetting)
    assert isinstance(result.entities[17], ExtractedGenreEntity)


# ── 5. relation_type is plain str (no coercion) ─────────────────────────


def test_relation_type_is_plain_str():
    """relation_type accepts any string, no coercion."""
    r1 = ExtractedRelation(source="A", target="B", relation_type="CUSTOM_REL", context="test")
    assert r1.relation_type == "CUSTOM_REL"

    r2 = ExtractedRelation(source="A", target="B", relation_type="whatever_string", context="test")
    assert r2.relation_type == "whatever_string"

    r3 = ExtractedRelation(source="A", target="B", relation_type="RELATES_TO", context="test")
    assert r3.relation_type == "RELATES_TO"


# ── 6. Mixed-type EntityExtractionResult ────────────────────────────────


def test_mixed_type_entity_extraction_result():
    raw = [
        {
            "entity_type": "character",
            "name": "Jake",
            "agency": "active",
            "extraction_text": "Jake.",
        },
        {"entity_type": "genre_entity", "sub_type": "skill", "name": "Fireball"},
        {"entity_type": "narrative_sequence", "name": "The Hunt"},
        {"entity_type": "location", "name": "Dark Forest", "extraction_text": "Forest."},
    ]
    result = EntityExtractionResult(entities=raw, chapter_number=5)
    assert len(result.entities) == 4
    assert isinstance(result.entities[0], ExtractedCharacter)
    assert isinstance(result.entities[1], ExtractedGenreEntity)
    assert isinstance(result.entities[2], ExtractedNarrativeSequence)
    assert isinstance(result.entities[3], ExtractedLocation)


# ── 7. Core enum coercion still works ───────────────────────────────────


def test_agency_coercion():
    char = ExtractedCharacter(name="Test", agency="ACTIVE", extraction_text="Test.")
    assert char.agency == "active"

    char2 = ExtractedCharacter(name="Test", agency="unknown_agency", extraction_text="Test.")
    assert char2.agency == "active"  # default fallback


def test_status_coercion():
    char = ExtractedCharacter(name="Test", status="DEAD", extraction_text="Test.")
    assert char.status == "dead"


def test_event_category_coercion():
    event = ExtractedEvent(name="Battle", event_category="COMBAT", extraction_text="Battle.")
    assert event.event_category == "combat"

    event2 = ExtractedEvent(name="Battle", event_category="nonsense", extraction_text="Battle.")
    assert event2.event_category == "action"  # default fallback


# ── 8. Character roundtrip (kept from original) ─────────────────────────


def test_character_roundtrip():
    char = ExtractedCharacter(
        name="Jake Thayne",
        canonical_name="Jake Thayne",
        aliases=["Jake", "The Primal Hunter"],
        agency="active",
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
            ExtractedRelation(
                source="A", target="B", relation_type="ALLIES_WITH", context="Together."
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


# ── 11. Default offsets ────────────────────────────────────────────────


def test_default_offsets():
    seq = ExtractedNarrativeSequence(name="Test Arc")
    assert seq.char_offset_start == -1
    assert seq.char_offset_end == -1

    prophecy = ExtractedProphecy(name="Test Prophecy")
    assert prophecy.char_offset_start == -1
    assert prophecy.char_offset_end == -1

    ge = ExtractedGenreEntity(sub_type="skill", name="Test")
    assert ge.char_offset_start == -1
    assert ge.char_offset_end == -1


# ── 12. New GOLEM types roundtrip ──────────────────────────────────────


def test_psychological_state_roundtrip():
    state = ExtractedPsychologicalState(
        character="jake",
        state_type="emotion",
        name="determination",
        description="Jake felt a surge of determination.",
        trigger_event="Battle of the Clearing",
        intensity=0.9,
        extraction_text="Jake felt a surge of determination.",
    )
    dumped = state.model_dump()
    assert dumped["entity_type"] == "psychological_state"
    assert dumped["intensity"] == 0.9
    reloaded = ExtractedPsychologicalState.model_validate(dumped)
    assert reloaded.character == "jake"


def test_setting_roundtrip():
    setting = ExtractedSetting(
        name="The Tutorial",
        setting_type="instance",
        description="A deadly trial for newcomers.",
        extraction_text="Welcome to the Tutorial.",
    )
    dumped = setting.model_dump()
    assert dumped["entity_type"] == "setting"
    assert dumped["setting_type"] == "instance"
    reloaded = ExtractedSetting.model_validate(dumped)
    assert reloaded.name == "The Tutorial"


def test_character_feature_roundtrip():
    feature = ExtractedCharacterFeature(
        character="jake",
        feature_type="physical",
        name="green eyes",
        description="Jake has striking green eyes.",
        extraction_text="his green eyes",
    )
    dumped = feature.model_dump()
    assert dumped["entity_type"] == "character_feature"
    reloaded = ExtractedCharacterFeature.model_validate(dumped)
    assert reloaded.feature_type == "physical"


def test_narrative_role_roundtrip():
    role = ExtractedNarrativeRole(
        character="jake",
        role_type="protagonist",
        context="Main arc",
        extraction_text="Jake, the protagonist.",
    )
    dumped = role.model_dump()
    assert dumped["entity_type"] == "narrative_role"
    assert dumped["role_type"] == "protagonist"
    reloaded = ExtractedNarrativeRole.model_validate(dumped)
    assert reloaded.character == "jake"


def test_social_relationship_roundtrip():
    rel = ExtractedSocialRelationship(
        participants=["jake", "casper"],
        relationship_type="friendship",
        name="Jake-Casper bond",
        description="A deep friendship forged in the Tutorial.",
        trigger_event="Battle of the Clearing",
        extraction_text="The friendship between Jake and Casper deepened.",
    )
    dumped = rel.model_dump()
    assert dumped["entity_type"] == "social_relationship"
    assert len(dumped["participants"]) == 2
    reloaded = ExtractedSocialRelationship.model_validate(dumped)
    assert reloaded.relationship_type == "friendship"


def test_textual_feature_roundtrip():
    feat = ExtractedTextualFeature(
        feature_type="pov",
        name="third_person_limited",
        value="Jake",
    )
    dumped = feat.model_dump()
    assert dumped["entity_type"] == "textual_feature"
    reloaded = ExtractedTextualFeature.model_validate(dumped)
    assert reloaded.feature_type == "pov"


# ── 13. GOLEM type coercion ────────────────────────────────────────────


def test_state_type_coercion():
    state = ExtractedPsychologicalState(
        character="jake", name="fear", state_type="EMOTION", extraction_text="fear."
    )
    assert state.state_type == "emotion"

    state2 = ExtractedPsychologicalState(
        character="jake", name="fear", state_type="nonsense", extraction_text="fear."
    )
    assert state2.state_type == "emotion"  # default fallback


def test_setting_type_coercion():
    setting = ExtractedSetting(
        name="Tutorial", setting_type="WORLD", extraction_text="Tutorial."
    )
    assert setting.setting_type == "world"


def test_role_type_coercion():
    role = ExtractedNarrativeRole(
        character="jake", role_type="PROTAGONIST", extraction_text="jake."
    )
    assert role.role_type == "protagonist"


def test_relationship_type_coercion():
    rel = ExtractedSocialRelationship(
        participants=["a", "b"],
        relationship_type="FRIENDSHIP",
        extraction_text="friends.",
    )
    assert rel.relationship_type == "friendship"


def test_social_relationship_accepts_one_participant_for_llm_robustness():
    """min_length removed from Pydantic to avoid rejecting entire JSON.

    Validation of ≥2 participants is now done by verify node Check 8.
    """
    sr = ExtractedSocialRelationship(
        participants=["jake"],
        extraction_text="alone.",
    )
    assert len(sr.participants) == 1  # accepted at schema level, filtered by verify


# ── 14. Unknown entity types are dropped ─────────────────────────────


def test_unknown_entity_type_dropped():
    raw = [
        {"entity_type": "character", "name": "Jake", "extraction_text": "Jake."},
        {"entity_type": "invented_type", "name": "Foo"},
        {"entity_type": "event", "name": "Battle", "extraction_text": "Battle."},
    ]
    result = EntityExtractionResult(entities=raw, chapter_number=1)
    assert len(result.entities) == 2
    assert result.entities[0].entity_type == "character"
    assert result.entities[1].entity_type == "event"
