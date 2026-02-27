"""Pydantic schemas for LLM extraction passes and reconciliation.

Defines structured output models for each of the 4 extraction passes:
  Pass 1: Characters & Relationships
  Pass 2: Systems & Progression (LitRPG specific)
  Pass 3: Events & Timeline
  Pass 4: Lore & Worldbuilding

Also defines the unified ExtractionResult that combines all passes,
and the reconciliation schemas used by Instructor.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── V3 Base Schema ─────────────────────────────────────────────────────


class BaseExtractedEntity(BaseModel):
    """V3 base for all extraction outputs with confidence and provenance."""

    name: str
    canonical_name: str
    entity_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_text: str
    char_offset_start: int
    char_offset_end: int
    chapter_number: int
    extraction_layer: Literal["narrative", "genre", "series"]
    extraction_phase: int
    ontology_version: str


class ExtractedStatBlock(BaseModel):
    """Snapshot of character stats at a chapter."""

    character_name: str
    stats: dict[str, int]
    total: int | None = None
    source: Literal["blue_box", "narrative", "inferred"] = "blue_box"
    chapter_number: int


# ── Pass 1: Characters & Relationships ──────────────────────────────────


class ExtractedRelationship(BaseModel):
    """A relationship between two characters."""

    source: str = Field(..., description="Name of the source character")
    target: str = Field(..., description="Name of the target character")
    rel_type: str = Field(
        ...,
        description=(
            "Relationship type: ally, enemy, mentor, family, romantic, rival, patron, subordinate"
        ),
    )
    subtype: str = ""
    context: str = Field("", description="Brief context from the text")
    since_chapter: int | None = None


class ExtractedCharacter(BaseModel):
    """A character extracted from text."""

    name: str = Field(..., description="Character's primary name as used in text")
    canonical_name: str = Field("", description="Full canonical name if different from name")
    aliases: list[str] = Field(default_factory=list, description="Known aliases or nicknames")
    description: str = Field("", description="Brief description based on this chapter")
    role: str = Field(
        "minor",
        description=(
            "Narrative role: protagonist, antagonist, mentor, sidekick, ally, minor, neutral"
        ),
    )
    species: str = ""
    first_appearance_chapter: int | None = None
    # V3 fields
    status: Literal["alive", "dead", "unknown", "transformed"] = "alive"
    last_seen_chapter: int | None = None
    evolution_of: str | None = None


class CharacterExtractionResult(BaseModel):
    """Result from Pass 1: Characters & Relationships."""

    characters: list[ExtractedCharacter] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


# ── Pass 2: Systems & Progression ───────────────────────────────────────


class ExtractedSkill(BaseModel):
    """A skill or ability extracted from text."""

    name: str = Field(..., description="Skill name exactly as mentioned")
    description: str = ""
    skill_type: str = Field(
        "active",
        description="Type: active, passive, racial, class, profession, unique",
    )
    rank: str = ""
    owner: str = Field("", description="Character who has this skill")
    acquired_chapter: int | None = None


class ExtractedClass(BaseModel):
    """A class/job extracted from text."""

    name: str = Field(..., description="Class name exactly as mentioned")
    description: str = ""
    tier: int | None = None
    owner: str = Field("", description="Character who has this class")
    acquired_chapter: int | None = None


class ExtractedTitle(BaseModel):
    """A title extracted from text."""

    name: str = Field(..., description="Title name")
    description: str = ""
    effects: list[str] = Field(default_factory=list)
    owner: str = ""
    acquired_chapter: int | None = None


class ExtractedLevelChange(BaseModel):
    """A level up or level change event."""

    character: str = Field(..., description="Character who leveled up")
    old_level: int | None = None
    new_level: int | None = None
    realm: str = ""
    chapter: int | None = None


class ExtractedStatChange(BaseModel):
    """A stat increase or decrease."""

    character: str = ""
    stat_name: str = Field(..., description="Name of the stat")
    value: int = Field(..., description="Amount of change (positive or negative)")


class SystemExtractionResult(BaseModel):
    """Result from Pass 2: Systems & Progression."""

    skills: list[ExtractedSkill] = Field(default_factory=list)
    classes: list[ExtractedClass] = Field(default_factory=list)
    titles: list[ExtractedTitle] = Field(default_factory=list)
    level_changes: list[ExtractedLevelChange] = Field(default_factory=list)
    stat_changes: list[ExtractedStatChange] = Field(default_factory=list)


# ── Pass 3: Events & Timeline ──────────────────────────────────────────


class ExtractedEvent(BaseModel):
    """A narrative event extracted from text."""

    name: str = Field(..., description="Short name for the event")
    description: str = Field("", description="What happened")
    event_type: str = Field(
        "action",
        description="Type: action, state_change, achievement, process, dialogue",
    )
    significance: str = Field(
        "moderate",
        description="Significance: minor, moderate, major, critical, arc_defining",
    )
    participants: list[str] = Field(default_factory=list, description="Character names involved")
    location: str = ""
    chapter: int | None = None
    is_flashback: bool = False
    causes: list[str] = Field(
        default_factory=list,
        description="Names of events this event was caused by",
    )


class EventExtractionResult(BaseModel):
    """Result from Pass 3: Events & Timeline."""

    events: list[ExtractedEvent] = Field(default_factory=list)


# ── Pass 4: Lore & Worldbuilding ───────────────────────────────────────


class ExtractedLocation(BaseModel):
    """A location extracted from text."""

    name: str = Field(..., description="Location name")
    description: str = ""
    location_type: str = Field(
        "region",
        description=(
            "Type: city, dungeon, realm, continent, "
            "pocket_dimension, planet, forest, "
            "mountain, building, region"
        ),
    )
    parent_location: str = ""


class ExtractedItem(BaseModel):
    """An item or artifact extracted from text."""

    name: str = Field(..., description="Item name")
    description: str = ""
    item_type: str = Field(
        "key_item",
        description="Type: weapon, armor, consumable, artifact, key_item, tool, material",
    )
    rarity: str = ""
    owner: str = ""


class ExtractedCreature(BaseModel):
    """A creature or monster extracted from text."""

    name: str = Field(..., description="Creature name or species")
    description: str = ""
    species: str = ""
    threat_level: str = ""
    habitat: str = ""


class ExtractedFaction(BaseModel):
    """A faction or organization extracted from text."""

    name: str = Field(..., description="Faction name")
    description: str = ""
    faction_type: str = ""
    alignment: str = ""


class ExtractedConcept(BaseModel):
    """A world concept or lore element."""

    name: str = Field(..., description="Concept name")
    description: str = Field("", description="Explanation of the concept")
    domain: str = Field("", description="Domain: magic, politics, cosmology, etc.")


class LoreExtractionResult(BaseModel):
    """Result from Pass 4: Lore & Worldbuilding."""

    locations: list[ExtractedLocation] = Field(default_factory=list)
    items: list[ExtractedItem] = Field(default_factory=list)
    creatures: list[ExtractedCreature] = Field(default_factory=list)
    factions: list[ExtractedFaction] = Field(default_factory=list)
    concepts: list[ExtractedConcept] = Field(default_factory=list)


# ── Grounding ───────────────────────────────────────────────────────────


class GroundedEntity(BaseModel):
    """An entity with source grounding from LangExtract."""

    entity_type: str = Field(..., description="Entity type label (Character, Skill, etc.)")
    entity_name: str = Field(..., description="Entity name as extracted")
    extraction_text: str = Field(..., description="Exact text span from source")
    char_offset_start: int = Field(..., description="Start offset in source text")
    char_offset_end: int = Field(..., description="End offset in source text")
    attributes: dict[str, str] = Field(default_factory=dict)
    pass_name: str = Field("", description="Which extraction pass produced this")
    alignment_status: str = Field(
        "exact", description="Alignment quality: exact, fuzzy, or unaligned"
    )
    confidence: float = Field(1.0, description="Grounding confidence: 1.0 for exact, 0.7 for fuzzy")


# ── Unified extraction result ───────────────────────────────────────────


class ChapterExtractionResult(BaseModel):
    """Combined result of all extraction passes for a single chapter."""

    book_id: str
    chapter_number: int
    characters: CharacterExtractionResult = Field(default_factory=CharacterExtractionResult)
    systems: SystemExtractionResult = Field(default_factory=SystemExtractionResult)
    events: EventExtractionResult = Field(default_factory=EventExtractionResult)
    lore: LoreExtractionResult = Field(default_factory=LoreExtractionResult)
    grounded_entities: list[GroundedEntity] = Field(default_factory=list)
    alias_map: dict[str, str] = Field(
        default_factory=dict,
        description="Reconciliation alias map {alias -> canonical_name}",
    )
    total_entities: int = 0
    total_cost_usd: float = 0.0
    passes_completed: list[str] = Field(default_factory=list)

    def count_entities(self) -> int:
        """Count total extracted entities across all passes."""
        count = 0
        count += len(self.characters.characters)
        count += len(self.characters.relationships)
        count += len(self.systems.skills)
        count += len(self.systems.classes)
        count += len(self.systems.titles)
        count += len(self.systems.level_changes)
        count += len(self.systems.stat_changes)
        count += len(self.events.events)
        count += len(self.lore.locations)
        count += len(self.lore.items)
        count += len(self.lore.creatures)
        count += len(self.lore.factions)
        count += len(self.lore.concepts)
        self.total_entities = count
        return count


# ── Reconciliation schemas (used by Instructor) ────────────────────────


class EntityMergeCandidate(BaseModel):
    """A pair of entities that might be duplicates."""

    entity_a_name: str
    entity_b_name: str
    entity_type: str
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence they are the same entity",
    )
    canonical_name: str = Field(..., description="Preferred canonical name if merged")
    reason: str = Field("", description="Why they should or should not be merged")


class ReconciliationResult(BaseModel):
    """Result of cross-pass entity reconciliation."""

    merges: list[EntityMergeCandidate] = Field(default_factory=list)
    alias_map: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of alias → canonical_name",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Unresolved conflicts requiring human review",
    )


# ── Provenance (V3) ──────────────────────────────────────────────────────


class SkillProvenance(BaseModel):
    """Provenance link: which source granted a skill."""

    skill_name: str = Field(..., description="Name of the skill")
    source_type: str = Field(
        "unknown",
        description="Source type: item, class, bloodline, title, unknown",
    )
    source_name: str = Field("", description="Name of the source entity")
    confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Confidence that this source grants the skill",
    )
    context: str = Field("", description="Text evidence for the provenance")


class ProvenanceResult(BaseModel):
    """Result of provenance extraction for a chapter."""

    provenances: list[SkillProvenance] = Field(default_factory=list)


# ── Layer 3: Series-specific entities (V3) ───────────────────────────────


class ExtractedBloodline(BaseModel):
    """A bloodline extracted from text (Primal Hunter specific)."""

    name: str = Field(..., description="Bloodline name")
    description: str = ""
    effects: list[str] = Field(default_factory=list)
    origin: str = ""
    owner: str = ""
    awakened_chapter: int | None = None


class ExtractedProfession(BaseModel):
    """A profession extracted from text."""

    name: str = Field(..., description="Profession name")
    tier: int | None = None
    profession_type: str = ""
    owner: str = ""
    acquired_chapter: int | None = None


class ExtractedChurch(BaseModel):
    """A primordial church/deity relation."""

    deity_name: str = Field(..., description="Deity or Primordial name")
    domain: str = ""
    blessing: str = ""
    worshipper: str = ""
    valid_from_chapter: int | None = None


class Layer3ExtractionResult(BaseModel):
    """Result of Layer 3 series-specific extraction."""

    bloodlines: list[ExtractedBloodline] = Field(default_factory=list)
    professions: list[ExtractedProfession] = Field(default_factory=list)
    churches: list[ExtractedChurch] = Field(default_factory=list)
