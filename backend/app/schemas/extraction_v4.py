"""Pydantic schemas for the v4 extraction pipeline (KGGen-style, 2-step).

Step 1: Entity extraction — 12-type discriminated union
Step 2: Relation extraction — Neo4j relation types

Design choices:
- entity_type: Literal[...] discriminator on every model (required for Annotated union)
- Sub-type fields use `str` with `BeforeValidator` to coerce LLM outputs to known values
- All str fields default to "" (no Field(...)) unless semantically required
- All offset fields default to -1 (unknown / not grounded yet)
- All list fields use Field(default_factory=list)
- NO `from __future__ import annotations` — LangGraph needs runtime type resolution
"""

import operator
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field
from typing_extensions import TypedDict

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


_ROLES = {"protagonist", "antagonist", "mentor", "sidekick", "ally", "minor", "neutral"}
_coerce_role = _make_coercer(_ROLES, "minor")

_STATUSES = {"alive", "dead", "unknown", "transformed"}
_coerce_status = _make_coercer(_STATUSES, "unknown")

_SKILL_TYPES = {"active", "passive", "racial", "class", "profession", "unique"}
_coerce_skill_type = _make_coercer(_SKILL_TYPES, "active")

_EVENT_TYPES = {"action", "state_change", "achievement", "process", "dialogue",
                "encounter", "discovery", "revelation", "transition", "combat"}
_coerce_event_type = _make_coercer(_EVENT_TYPES, "action")

_SIGNIFICANCES = {"minor", "moderate", "major", "critical", "arc_defining"}
_coerce_significance = _make_coercer(_SIGNIFICANCES, "moderate")


# Type aliases with coercion
CoercedRole = Annotated[str, BeforeValidator(_coerce_role)]
CoercedStatus = Annotated[str, BeforeValidator(_coerce_status)]
CoercedSkillType = Annotated[str, BeforeValidator(_coerce_skill_type)]
CoercedEventType = Annotated[str, BeforeValidator(_coerce_event_type)]
CoercedSignificance = Annotated[str, BeforeValidator(_coerce_significance)]


# ── 1. Character ──────────────────────────────────────────────────────────


class ExtractedCharacter(BaseModel):
    entity_type: Literal["character"] = "character"
    name: str = Field(..., description="Character name as used in text")
    canonical_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    role: CoercedRole = "minor"
    species: str = ""
    description: str = ""
    status: CoercedStatus = "alive"
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 2. Event ─────────────────────────────────────────────────────────────


class ExtractedEvent(BaseModel):
    entity_type: Literal["event"] = "event"
    name: str = Field(..., description="Short name for the event")
    description: str = ""
    event_type: CoercedEventType = "action"
    significance: CoercedSignificance = "moderate"
    participants: list[str] = Field(default_factory=list)
    location: str = ""
    is_flashback: bool = False
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 3. Location ──────────────────────────────────────────────────────────


class ExtractedLocation(BaseModel):
    entity_type: Literal["location"] = "location"
    name: str = Field(..., description="Location name")
    location_type: str = ""
    parent_location: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 4. Item ──────────────────────────────────────────────────────────────


class ExtractedItem(BaseModel):
    entity_type: Literal["item"] = "item"
    name: str = Field(..., description="Item name")
    item_type: str = ""
    rarity: str = ""
    effects: list[str] = Field(default_factory=list)
    owner: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 5. Creature ──────────────────────────────────────────────────────────


class ExtractedCreature(BaseModel):
    entity_type: Literal["creature"] = "creature"
    name: str = Field(..., description="Creature name or species")
    species: str = ""
    threat_level: str = ""
    habitat: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 6. Faction ───────────────────────────────────────────────────────────


class ExtractedFaction(BaseModel):
    entity_type: Literal["faction"] = "faction"
    name: str = Field(..., description="Faction name")
    faction_type: str = ""
    alignment: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 7. Concept ───────────────────────────────────────────────────────────


class ExtractedConcept(BaseModel):
    entity_type: Literal["concept"] = "concept"
    name: str = Field(..., description="Concept name")
    domain: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 8. Arc ───────────────────────────────────────────────────────────────


class ExtractedArc(BaseModel):
    entity_type: Literal["arc"] = "arc"
    name: str = Field(..., description="Narrative arc name")
    canonical_name: str = ""
    arc_type: str = ""  # main_plot, subplot, character_arc, world_arc
    status: str = ""  # active, completed, abandoned
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 9. Prophecy ──────────────────────────────────────────────────────────


class ExtractedProphecy(BaseModel):
    entity_type: Literal["prophecy"] = "prophecy"
    name: str = Field(..., description="Prophecy name or title")
    canonical_name: str = ""
    status: str = ""  # unfulfilled, fulfilled, subverted
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 10. LevelChange ─────────────────────────────────────────────────────


class ExtractedLevelChange(BaseModel):
    entity_type: Literal["level_change"] = "level_change"
    character: str = Field(..., description="Character who leveled up")
    old_level: int | None = None
    new_level: int | None = None
    realm: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 11. StatChange ──────────────────────────────────────────────────────


class ExtractedStatChange(BaseModel):
    entity_type: Literal["stat_change"] = "stat_change"
    character: str = ""
    stat_name: str = Field(..., description="Name of the stat")
    value: int = Field(..., description="Amount of change (positive or negative)")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 12. GenreEntity (catch-all) ──────────────────────────────────────────


class ExtractedGenreEntity(BaseModel):
    """Catch-all for genre/series-specific entity types.

    The sub_type field maps to ontology-defined types:
    LitRPG: skill, class, title, system, race, quest, achievement, realm,
            bloodline, profession, church, alchemy_recipe, floor
    Fantasy: spell, magic_system, kingdom, house, bond
    """

    entity_type: Literal["genre_entity"] = "genre_entity"
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
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── Discriminated Union ───────────────────────────────────────────────────

EntityUnion = Annotated[
    ExtractedCharacter
    | ExtractedEvent
    | ExtractedLocation
    | ExtractedItem
    | ExtractedCreature
    | ExtractedFaction
    | ExtractedConcept
    | ExtractedArc
    | ExtractedProphecy
    | ExtractedLevelChange
    | ExtractedStatChange
    | ExtractedGenreEntity,
    Field(discriminator="entity_type"),
]


# ── Result types ─────────────────────────────────────────────────────────


class EntityExtractionResult(BaseModel):
    """Step 1 output: flat list of all extracted entities for a chapter."""

    entities: list[EntityUnion] = Field(default_factory=list)
    chapter_number: int = 0


class ExtractedRelation(BaseModel):
    """A directed relationship between two named entities."""

    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    relation_type: str = Field(
        ..., description="Neo4j relation type — post-validated by extraction node"
    )
    subtype: str = ""
    sentiment: float | None = Field(None, ge=-1.0, le=1.0)
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

    # Post-processing
    alias_map: dict[str, str]

    # Telemetry
    total_cost_usd: float
    total_entities: int

    # Error accumulation (reducer)
    errors: Annotated[list[dict], operator.add]
