"""Pydantic schemas for V3 character state tracking.

Used by the character state API endpoints to return
reconstructed character sheets, progression timelines,
comparisons, and lightweight summaries.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Building blocks ──────────────────────────────────────────────────────


class StatEntry(BaseModel):
    """A single stat with its current aggregated value."""

    name: str
    value: int
    last_changed_chapter: int


class SkillSnapshot(BaseModel):
    """A skill the character has at a given chapter."""

    name: str
    rank: str = ""
    skill_type: str = ""
    description: str = ""
    acquired_chapter: int | None = None


class ClassSnapshot(BaseModel):
    """A class the character has at a given chapter."""

    name: str
    tier: int | None = None
    description: str = ""
    acquired_chapter: int | None = None
    is_active: bool = False


class TitleSnapshot(BaseModel):
    """A title the character holds at a given chapter."""

    name: str
    description: str = ""
    effects: list[str] = Field(default_factory=list)
    acquired_chapter: int | None = None


class ItemSnapshot(BaseModel):
    """An item the character possesses at a given chapter."""

    name: str
    item_type: str = ""
    rarity: str = ""
    description: str = ""
    acquired_chapter: int | None = None
    grants: list[str] = Field(default_factory=list)


class LevelSnapshot(BaseModel):
    """Character level at a given chapter."""

    level: int | None = None
    realm: str = ""
    since_chapter: int | None = None


class StateChangeRecord(BaseModel):
    """A single immutable state change event."""

    chapter: int
    category: str  # stat, skill, class, title, item, level
    name: str
    action: str  # gain, lose, upgrade, evolve, acquire, drop
    value_delta: int | None = None
    value_after: int | None = None
    detail: str = ""


# ── API response models ──────────────────────────────────────────────────


class CharacterStateSnapshot(BaseModel):
    """Full character sheet reconstructed at a specific chapter."""

    character_name: str
    canonical_name: str
    book_id: str
    as_of_chapter: int
    total_chapters_in_book: int
    role: str = ""
    species: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    level: LevelSnapshot = Field(default_factory=LevelSnapshot)
    stats: list[StatEntry] = Field(default_factory=list)
    skills: list[SkillSnapshot] = Field(default_factory=list)
    classes: list[ClassSnapshot] = Field(default_factory=list)
    titles: list[TitleSnapshot] = Field(default_factory=list)
    items: list[ItemSnapshot] = Field(default_factory=list)
    chapter_changes: list[StateChangeRecord] = Field(default_factory=list)
    total_changes_to_date: int = 0


class ProgressionMilestone(BaseModel):
    """A single progression event in the timeline."""

    chapter: int
    category: str
    name: str
    action: str
    value_delta: int | None = None
    value_after: int | None = None
    detail: str = ""


class ProgressionTimeline(BaseModel):
    """Paginated progression timeline for a character."""

    character_name: str
    book_id: str
    milestones: list[ProgressionMilestone] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50


class StatDiff(BaseModel):
    """Difference in a single stat between two chapters."""

    name: str
    value_at_from: int
    value_at_to: int
    delta: int


class CategoryDiff(BaseModel):
    """Gained/lost items in a category between two chapters."""

    gained: list[str] = Field(default_factory=list)
    lost: list[str] = Field(default_factory=list)


class CharacterComparison(BaseModel):
    """Comparison of character state between two chapters."""

    character_name: str
    book_id: str
    from_chapter: int
    to_chapter: int
    level_from: int | None = None
    level_to: int | None = None
    stat_diffs: list[StatDiff] = Field(default_factory=list)
    skills: CategoryDiff = Field(default_factory=CategoryDiff)
    classes: CategoryDiff = Field(default_factory=CategoryDiff)
    titles: CategoryDiff = Field(default_factory=CategoryDiff)
    items: CategoryDiff = Field(default_factory=CategoryDiff)
    total_changes: int = 0


class CharacterSummary(BaseModel):
    """Lightweight character summary for hover tooltips."""

    name: str
    canonical_name: str
    role: str = ""
    species: str = ""
    level: int | None = None
    realm: str = ""
    active_class: str | None = None
    top_skills: list[str] = Field(default_factory=list)
    description: str = ""
