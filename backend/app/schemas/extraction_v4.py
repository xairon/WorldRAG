"""Pydantic schemas for the v4 extraction pipeline (KGGen-style, 2-step).

Step 1: Entity extraction — 18-type discriminated union (GOLEM v1.1 aligned)
Step 2: Relation extraction — Neo4j relation types

Design choices:
- entity_type: Literal[...] discriminator on every model (required for Annotated union)
- Sub-type fields use `str` with `BeforeValidator` to coerce LLM outputs to known values
- All str fields default to "" (no Field(...)) unless semantically required
- All offset fields default to -1 (unknown / not grounded yet)
- All list fields use Field(default_factory=list)
- NO `from __future__ import annotations` — LangGraph needs runtime type resolution
"""

import logging
import operator
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator
from typing_extensions import TypedDict

_coercer_logger = logging.getLogger("app.schemas.extraction_v4")

# ── Coercion helpers ─────────────────────────────────────────────────────
# LLMs generate close-but-not-exact values.  Instead of rejecting with a
# ValidationError we map them to the closest canonical value.


def _make_coercer(allowed: set[str], default: str):
    """Return a BeforeValidator function that coerces unknown strings."""
    _lower_map = {v.lower().replace("_", "").replace("-", ""): v for v in allowed}

    def _coerce(v: str) -> str:
        if v in allowed:
            return v
        normalised = v.lower().replace("_", "").replace("-", "").replace(" ", "")
        if normalised in _lower_map:
            return _lower_map[normalised]
        return default

    return _coerce


_AGENCIES = {"active", "passive", "ambiguous"}
_coerce_agency = _make_coercer(_AGENCIES, "active")

_STATUSES = {"alive", "dead", "unknown", "transformed"}
_coerce_status = _make_coercer(_STATUSES, "unknown")

_SKILL_TYPES = {"active", "passive", "racial", "class", "profession", "unique"}
_coerce_skill_type = _make_coercer(_SKILL_TYPES, "active")

_EVENT_TYPES = {
    "action",
    "state_change",
    "achievement",
    "process",
    "dialogue",
    "encounter",
    "discovery",
    "revelation",
    "transition",
    "combat",
}
_coerce_event_category = _make_coercer(_EVENT_TYPES, "action")

_SIGNIFICANCES = {"minor", "moderate", "major", "critical", "arc_defining"}
_coerce_significance = _make_coercer(_SIGNIFICANCES, "moderate")


# Type aliases with coercion
CoercedAgency = Annotated[str, BeforeValidator(_coerce_agency)]
CoercedStatus = Annotated[str, BeforeValidator(_coerce_status)]
CoercedSkillType = Annotated[str, BeforeValidator(_coerce_skill_type)]
CoercedEventCategory = Annotated[str, BeforeValidator(_coerce_event_category)]
CoercedSignificance = Annotated[str, BeforeValidator(_coerce_significance)]


# ── 1. Character ──────────────────────────────────────────────────────────


class ExtractedCharacter(BaseModel):
    entity_type: Literal["character"] = "character"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Character name as used in text")
    canonical_name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    agency: CoercedAgency = "active"
    species: str = ""
    status: CoercedStatus = "alive"
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 2. Event ─────────────────────────────────────────────────────────────


class ExtractedEvent(BaseModel):
    entity_type: Literal["event"] = "event"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Short name for the event")
    description: str = ""
    event_category: CoercedEventCategory = "action"
    significance: CoercedSignificance = "moderate"
    participants: list[str] = Field(default_factory=list)
    location: str | None = ""
    is_flashback: bool = False
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 3. Location ──────────────────────────────────────────────────────────


class ExtractedLocation(BaseModel):
    entity_type: Literal["location"] = "location"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Location name")
    canonical_name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    location_type: str = ""
    parent_location: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 4. Object (ex-Item, GOLEM G16) ──────────────────────────────────────


class ExtractedObject(BaseModel):
    entity_type: Literal["object"] = "object"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Object name")
    canonical_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    object_type: str = ""
    rarity: str = ""
    effects: list[str] = Field(default_factory=list)
    owner: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 5. Creature ──────────────────────────────────────────────────────────


class ExtractedCreature(BaseModel):
    entity_type: Literal["creature"] = "creature"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Creature name or species")
    canonical_name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    species: str = ""
    threat_level: str = ""
    habitat: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 6. Faction ───────────────────────────────────────────────────────────


class ExtractedFaction(BaseModel):
    entity_type: Literal["faction"] = "faction"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Faction name")
    canonical_name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    faction_type: str = ""
    alignment: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 7. Concept ───────────────────────────────────────────────────────────


class ExtractedConcept(BaseModel):
    entity_type: Literal["concept"] = "concept"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Concept name")
    canonical_name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    domain: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 8. NarrativeSequence (ex-Arc, GOLEM G7) ─────────────────────────────


class ExtractedNarrativeSequence(BaseModel):
    entity_type: Literal["narrative_sequence"] = "narrative_sequence"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Narrative sequence/arc name")
    canonical_name: str = ""
    description: str = ""
    sequence_type: str = ""  # main_plot, subplot, character_arc, world_arc
    status: str = ""  # active, completed, abandoned
    sequence_order: int = 0
    related_events: list[str] = Field(
        default_factory=list,
        description="Names of events that belong to this sequence",
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 9. Prophecy ──────────────────────────────────────────────────────────


class ExtractedProphecy(BaseModel):
    entity_type: Literal["prophecy"] = "prophecy"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Prophecy name or title")
    canonical_name: str = ""
    description: str = ""
    status: str = ""  # unfulfilled, fulfilled, subverted
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 10. LevelChange ─────────────────────────────────────────────────────


class ExtractedLevelChange(BaseModel):
    entity_type: Literal["level_change"] = "level_change"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    character: str = Field(..., description="Character who leveled up")
    old_level: int | None = None
    new_level: int | None = None
    realm: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 11. StatChange ──────────────────────────────────────────────────────


class ExtractedStatChange(BaseModel):
    entity_type: Literal["stat_change"] = "stat_change"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    character: str = ""
    stat_name: str = Field(..., description="Name of the stat")
    value: int = Field(..., description="Amount of change (positive or negative)")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 12. PsychologicalState (GOLEM G3) ───────────────────────────────────

_STATE_TYPES = {"emotion", "motivation", "belief", "goal", "fear"}
_coerce_state_type = _make_coercer(_STATE_TYPES, "emotion")
CoercedStateType = Annotated[str, BeforeValidator(_coerce_state_type)]


class ExtractedPsychologicalState(BaseModel):
    entity_type: Literal["psychological_state"] = "psychological_state"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    character: str = Field(..., description="Character experiencing this state")
    state_type: CoercedStateType = "emotion"
    name: str = Field(..., description="State name (e.g. 'determination', 'fear of failure')")
    description: str = ""
    trigger_event: str = ""
    intensity: float = Field(0.5, ge=0.0, le=1.0)
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 13. Setting (GOLEM G12) ─────────────────────────────────────────────

_SETTING_TYPES = {"world", "era", "dimension", "realm", "zone", "instance"}
_coerce_setting_type = _make_coercer(_SETTING_TYPES, "world")
CoercedSettingType = Annotated[str, BeforeValidator(_coerce_setting_type)]


class ExtractedSetting(BaseModel):
    entity_type: Literal["setting"] = "setting"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    name: str = Field(..., description="Setting name (e.g. 'The Tutorial', 'Nevermore')")
    setting_type: CoercedSettingType = "world"
    description: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 14. CharacterFeature (GOLEM G17) ────────────────────────────────────

_FEATURE_TYPES = {"biographical", "physical", "psychological"}
_coerce_feature_type = _make_coercer(_FEATURE_TYPES, "biographical")
CoercedFeatureType = Annotated[str, BeforeValidator(_coerce_feature_type)]


class ExtractedCharacterFeature(BaseModel):
    entity_type: Literal["character_feature"] = "character_feature"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    character: str = Field(..., description="Character this feature belongs to")
    feature_type: CoercedFeatureType = "biographical"
    name: str = Field(..., description="Feature name (e.g. 'green eyes', 'human', 'loner')")
    description: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 15. NarrativeRole (GOLEM G11) ───────────────────────────────────────

_ROLE_TYPES = {
    "protagonist",
    "antagonist",
    "mentor",
    "trickster",
    "herald",
    "guardian",
    "shadow",
    "shapeshifter",
    "narrator",
    "deuteragonist",
    "foil",
}
_coerce_role_type = _make_coercer(_ROLE_TYPES, "protagonist")
CoercedRoleType = Annotated[str, BeforeValidator(_coerce_role_type)]


class ExtractedNarrativeRole(BaseModel):
    entity_type: Literal["narrative_role"] = "narrative_role"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    character: str = Field(..., description="Character playing this role")
    role_type: CoercedRoleType = "protagonist"
    context: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 16. SocialRelationship (GOLEM G4) ───────────────────────────────────

_RELATIONSHIP_TYPES = {
    "friendship",
    "rivalry",
    "romance",
    "family",
    "mentorship",
    "patron",
    "alliance",
    "enmity",
    "professional",
    "worship",
}
_coerce_relationship_type = _make_coercer(_RELATIONSHIP_TYPES, "friendship")
CoercedRelationshipType = Annotated[str, BeforeValidator(_coerce_relationship_type)]


class ExtractedSocialRelationship(BaseModel):
    entity_type: Literal["social_relationship"] = "social_relationship"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    participants: list[str] = Field(
        default_factory=list,
        description="2+ characters involved in this relationship (validated by verify node)",
    )
    relationship_type: CoercedRelationshipType = "friendship"
    name: str = ""
    description: str = ""
    trigger_event: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 17. TextualFeature (GOLEM G18 — programmatic, not LLM-extracted) ────


class ExtractedTextualFeature(BaseModel):
    entity_type: Literal["textual_feature"] = "textual_feature"
    feature_type: str = ""  # pov, narrative_voice, dialogue_density, pacing, tone
    name: str = Field(..., description="Feature name (e.g. 'first_person_pov')")
    value: str = ""


# ── 18. GenreEntity (catch-all) ──────────────────────────────────────────


class ExtractedGenreEntity(BaseModel):
    """Catch-all for genre/series-specific entity types.

    The sub_type field maps to ontology-defined types:
    LitRPG: skill, class, title, system, race, quest, achievement, realm,
            bloodline, profession, church, alchemy_recipe, floor
    Fantasy: spell, magic_system, kingdom, house, bond
    """

    entity_type: Literal["genre_entity"] = "genre_entity"
    type_rationale: str = Field(
        default="",
        description="One sentence: why is this entity this type and not another?",
    )
    sub_type: str = Field(..., description="Ontology-defined sub-type (e.g. skill, class, spell)")
    name: str = Field(..., description="Entity name as in text")
    canonical_name: str = ""
    description: str = ""
    owner: str = ""
    tier: str = ""
    rank: str = ""
    effects: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Flexible key-value for ontology-defined fields"
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── Discriminated Union ───────────────────────────────────────────────────

EntityUnion = Annotated[
    ExtractedCharacter
    | ExtractedEvent
    | ExtractedLocation
    | ExtractedObject
    | ExtractedCreature
    | ExtractedFaction
    | ExtractedConcept
    | ExtractedNarrativeSequence
    | ExtractedProphecy
    | ExtractedLevelChange
    | ExtractedStatChange
    | ExtractedPsychologicalState
    | ExtractedSetting
    | ExtractedCharacterFeature
    | ExtractedNarrativeRole
    | ExtractedSocialRelationship
    | ExtractedTextualFeature
    | ExtractedGenreEntity,
    Field(discriminator="entity_type"),
]


# ── Result types ─────────────────────────────────────────────────────────


_VALID_ENTITY_TYPES = {
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
}


class EntityExtractionResult(BaseModel):
    """Step 1 output: flat list of all extracted entities for a chapter."""

    reasoning: str = Field(
        default="",
        description=(
            "Brief step-by-step reasoning about what key entities, events, "
            "and relationships are present in the text before listing them"
        ),
    )
    entities: list[EntityUnion] = Field(default_factory=list)
    chapter_number: int = 0

    @model_validator(mode="before")
    @classmethod
    def coerce_unknown_entity_types(cls, data: Any) -> Any:
        """Drop entities with unknown entity_type values (silently)."""
        if isinstance(data, dict) and "entities" in data:
            valid = []
            for entity in data.get("entities", []):
                if isinstance(entity, dict):
                    et = entity.get("entity_type", "")
                    if not et or et in _VALID_ENTITY_TYPES:
                        valid.append(entity)
                    else:
                        _coercer_logger.warning(
                            "entity_dropped_invalid_type: name=%s type=%s",
                            entity.get("name", "?"),
                            et,
                        )
                else:
                    # Already a Pydantic model instance — pass through as-is
                    valid.append(entity)
            data["entities"] = valid
        return data


def _coerce_to_str(v: object) -> str:
    """Coerce LLM outputs (ints, floats) to str for entity name fields."""
    return str(v) if not isinstance(v, str) else v


class ExtractedRelation(BaseModel):
    """A directed relationship between two named entities."""

    source: Annotated[str, BeforeValidator(_coerce_to_str)] = Field(
        ..., description="Source entity name"
    )
    target: Annotated[str, BeforeValidator(_coerce_to_str)] = Field(
        ..., description="Target entity name"
    )
    relation_type: str = Field(
        ..., description="Neo4j relation type — post-validated by extraction node"
    )
    subtype: str = ""
    sentiment: float | None = Field(None, ge=-1.0, le=1.0)
    temporal_order: str | None = Field(
        default=None,
        description="For event-event relations: 'precedes', 'causes', 'during', 'simultaneous'",
    )
    valid_from_chapter: int | None = None
    context: str = ""


class RelationEnd(BaseModel):
    """A relation that ended at a specific chapter."""

    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    relation_type: str = Field(..., description="Neo4j relation type that ended")
    ended_at_chapter: int = Field(..., description="Chapter where the relation ended")
    reason: str = ""


class RelationExtractionResult(BaseModel):
    """Step 2 output: new and ended relations for a chapter."""

    reasoning: str = Field(
        default="",
        description=("Brief reasoning about relationships between entities before listing them"),
    )
    relations: list[ExtractedRelation] = Field(default_factory=list)
    ended_relations: list[RelationEnd] = Field(default_factory=list)


class EntitySummary(BaseModel):
    """Aggregated summary of an entity across chapters."""

    entity_name: str = Field(..., description="Canonical entity name")
    entity_type: str = Field(..., description="Entity type label")
    summary: str = ""
    key_facts: list[str] = Field(default_factory=list)
    first_chapter: int | None = None
    last_chapter: int | None = None
    mention_count: int = 0


class CommunitySummary(BaseModel):
    """LLM-generated summary for a community of entities."""

    summary: str = Field(..., description="1-3 sentence summary of the community")
    key_themes: list[str] = Field(
        default_factory=list, description="Key themes or roles of this community"
    )


# ── LangGraph State ───────────────────────────────────────────────────────


class ExtractionStateV4(TypedDict, total=False):
    """Simplified LangGraph state for the v4 extraction pipeline."""

    # Input
    book_id: str
    chapter_number: int
    chapter_text: str
    chunk_texts: list[str]
    regex_matches_json: str

    # Config
    genre: str
    series_name: str
    source_language: str
    model_override: str | None

    # Ontology
    ontology: Any  # OntologyLoader instance, passed from worker

    # Accumulated knowledge
    entity_registry: dict  # canonical_name -> entity dict
    series_entities: dict  # series-specific entity registry

    # Step 1 outputs
    entities: list[dict]

    # Step 2 outputs
    relations: list[dict]
    ended_relations: list[dict]

    # Reducer fields (accumulated across parallel nodes / map-reduce)
    grounded_entities: Annotated[list[dict], operator.add]

    # Chunk-level narrative metadata (set by verify node)
    chunk_metadata: dict[str, Any]

    # Coverage verification control
    skip_coverage_pass: bool

    # Post-processing
    alias_map: dict[str, str]

    # Telemetry
    total_cost_usd: float
    total_entities: int

    # Error accumulation (reducer)
    errors: Annotated[list[dict], operator.add]
