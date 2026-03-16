"""Pydantic schemas for the v4 extraction pipeline (KGGen-style, 2-step).

Step 1: Entity extraction — 15-type discriminated union
Step 2: Relation extraction — Neo4j relation types

Design choices:
- entity_type: Literal[...] discriminator on every model (required for Annotated union)
- All str fields default to "" (no Field(...)) unless semantically required
- All offset fields default to -1 (unknown / not grounded yet)
- All list fields use Field(default_factory=list)
- NO `from __future__ import annotations` — LangGraph needs runtime type resolution
"""

import operator
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# ── 1. Character ──────────────────────────────────────────────────────────


class ExtractedCharacter(BaseModel):
    entity_type: Literal["character"] = "character"
    name: str = Field(..., description="Character name as used in text")
    canonical_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    role: Literal[
        "protagonist", "antagonist", "mentor", "sidekick", "ally", "minor", "neutral"
    ] = "minor"
    species: str = ""
    description: str = ""
    status: Literal["alive", "dead", "unknown", "transformed"] = "alive"
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 2. Skill ──────────────────────────────────────────────────────────────


class ExtractedSkill(BaseModel):
    entity_type: Literal["skill"] = "skill"
    name: str = Field(..., description="Skill name exactly as mentioned")
    description: str = ""
    skill_type: Literal["active", "passive", "racial", "class", "profession", "unique"] = "active"
    rank: str = ""
    owner: str = ""
    effects: list[str] = Field(default_factory=list)
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 3. Class ──────────────────────────────────────────────────────────────


class ExtractedClass(BaseModel):
    # NOTE: Literal["class"] is valid Python — "class" is only reserved as an
    # identifier, not as a string value.
    entity_type: Literal["class"] = "class"
    name: str = Field(..., description="Class name exactly as mentioned")
    tier: int | None = None
    owner: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 4. Title ──────────────────────────────────────────────────────────────


class ExtractedTitle(BaseModel):
    entity_type: Literal["title"] = "title"
    name: str = Field(..., description="Title name")
    effects: list[str] = Field(default_factory=list)
    owner: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 5. Event ──────────────────────────────────────────────────────────────


class ExtractedEvent(BaseModel):
    entity_type: Literal["event"] = "event"
    name: str = Field(..., description="Short name for the event")
    description: str = ""
    event_type: Literal["action", "state_change", "achievement", "process", "dialogue"] = "action"
    significance: Literal["minor", "moderate", "major", "critical", "arc_defining"] = "moderate"
    participants: list[str] = Field(default_factory=list)
    location: str = ""
    is_flashback: bool = False
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 6. Location ───────────────────────────────────────────────────────────


class ExtractedLocation(BaseModel):
    entity_type: Literal["location"] = "location"
    name: str = Field(..., description="Location name")
    location_type: str = ""
    parent_location: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 7. Item ───────────────────────────────────────────────────────────────


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


# ── 8. Creature ───────────────────────────────────────────────────────────


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


# ── 9. Faction ────────────────────────────────────────────────────────────


class ExtractedFaction(BaseModel):
    entity_type: Literal["faction"] = "faction"
    name: str = Field(..., description="Faction name")
    faction_type: str = ""
    alignment: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 10. Concept ───────────────────────────────────────────────────────────


class ExtractedConcept(BaseModel):
    entity_type: Literal["concept"] = "concept"
    name: str = Field(..., description="Concept name")
    domain: str = ""
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 11. LevelChange ───────────────────────────────────────────────────────


class ExtractedLevelChange(BaseModel):
    entity_type: Literal["level_change"] = "level_change"
    character: str = Field(..., description="Character who leveled up")
    old_level: int | None = None
    new_level: int | None = None
    realm: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 12. StatChange ────────────────────────────────────────────────────────


class ExtractedStatChange(BaseModel):
    entity_type: Literal["stat_change"] = "stat_change"
    character: str = ""
    stat_name: str = Field(..., description="Name of the stat")
    value: int = Field(..., description="Amount of change (positive or negative)")
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 13. Bloodline (Layer 3 — series-specific) ─────────────────────────────


class ExtractedBloodline(BaseModel):
    entity_type: Literal["bloodline"] = "bloodline"
    name: str = Field(..., description="Bloodline name")
    description: str = ""
    effects: list[str] = Field(default_factory=list)
    origin: str = ""
    owner: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 14. Profession (Layer 3 — series-specific) ────────────────────────────


class ExtractedProfession(BaseModel):
    entity_type: Literal["profession"] = "profession"
    name: str = Field(..., description="Profession name")
    tier: int | None = None
    profession_type: str = ""
    owner: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── 15. Church (Layer 3 — series-specific) ────────────────────────────────


class ExtractedChurch(BaseModel):
    entity_type: Literal["church"] = "church"
    deity_name: str = Field(..., description="Deity or Primordial name")
    domain: str = ""
    blessing: str = ""
    worshipper: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── Discriminated Union ───────────────────────────────────────────────────

EntityUnion = Annotated[
    Union[
        ExtractedCharacter,
        ExtractedSkill,
        ExtractedClass,
        ExtractedTitle,
        ExtractedEvent,
        ExtractedLocation,
        ExtractedItem,
        ExtractedCreature,
        ExtractedFaction,
        ExtractedConcept,
        ExtractedLevelChange,
        ExtractedStatChange,
        ExtractedBloodline,
        ExtractedProfession,
        ExtractedChurch,
    ],
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
    relation_type: Literal[
        "ALLIED_WITH",
        "ENEMY_OF",
        "KNOWS",
        "MENTOR_OF",
        "FAMILY_OF",
        "ROMANTIC_WITH",
        "RIVAL_OF",
        "PATRON_OF",
        "SUBORDINATE_OF",
        "MEMBER_OF",
        "OWNS",
        "LOCATED_IN",
        "PARTICIPATES_IN",
        "GRANTS",
        "CAUSED_BY",
        "PART_OF",
    ] = Field(..., description="Neo4j relation type")
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
