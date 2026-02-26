# V3 Character State Tracking — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an immutable StateChange ledger so character state (stats, skills, classes, titles, items, level) can be reconstructed at any chapter, with provenance tracking, blue box grouping, and Layer 3 extraction.

**Architecture:** Append-only StateChange nodes in Neo4j, reconstructed via Cypher aggregation (`sum(value_delta) WHERE chapter <= N`). Dual-write in existing upsert methods: keep current HAS_STAT/HAS_SKILL relationships (backward compat) AND create immutable StateChange nodes. New API endpoints serve character sheets at any chapter. Frontend renders interactive character sheets with chapter slider.

**Tech Stack:** Python 3.12 / FastAPI / Neo4j 5 Cypher / Pydantic v2 / Next.js 16 / React 19 / TypeScript / shadcn/ui / SWR / recharts

**Design doc:** `docs/plans/2026-02-26-v3-character-state-tracking-design.md`

---

## Phase 1: Neo4j Schema + StateChange Ledger

### Task 1.1: Neo4j Schema — Add StateChange + BlueBox + Layer 3 Constraints

**Files:**
- Modify: `scripts/init_neo4j.cypher` (after line 59, existing constraints section)

**Step 1: Add new constraints and indexes to init script**

Append after the existing `paragraph_unique` constraint (around line 59):

```cypher
// ── V3: Character State Tracking ──────────────────────────────────────

// StateChange ledger
CREATE CONSTRAINT state_change_unique IF NOT EXISTS
  FOR (sc:StateChange)
  REQUIRE (sc.character_name, sc.book_id, sc.chapter, sc.category, sc.name, sc.action) IS UNIQUE;

CREATE INDEX state_change_character IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.character_name, sc.book_id);

CREATE INDEX state_change_chapter IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.book_id, sc.chapter);

CREATE INDEX state_change_category IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.category);

// BlueBox grouping
CREATE CONSTRAINT bluebox_unique IF NOT EXISTS
  FOR (bb:BlueBox) REQUIRE (bb.book_id, bb.chapter, bb.index) IS UNIQUE;

// Layer 3: Bloodline
CREATE CONSTRAINT bloodline_unique IF NOT EXISTS
  FOR (b:Bloodline) REQUIRE b.name IS UNIQUE;

// Layer 3: Profession
CREATE CONSTRAINT profession_unique IF NOT EXISTS
  FOR (p:Profession) REQUIRE (p.name, p.book_id) IS UNIQUE;

// Layer 3: PrimordialChurch
CREATE CONSTRAINT church_unique IF NOT EXISTS
  FOR (pc:PrimordialChurch) REQUIRE pc.deity_name IS UNIQUE;

// Batch ID indexes for new types
CREATE INDEX state_change_batch IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.batch_id);

CREATE INDEX bluebox_batch IF NOT EXISTS
  FOR (bb:BlueBox) ON (bb.batch_id);
```

Also add `"StateChange"`, `"BlueBox"`, `"Bloodline"`, `"Profession"`, `"PrimordialChurch"` to the `_VALID_LABELS` set in `backend/app/repositories/base.py:23-40`.

**Step 2: Apply schema to running Neo4j**

Run:
```bash
docker exec -i rag-neo4j-1 cypher-shell -u neo4j -p worldrag < scripts/init_neo4j.cypher
```

Expected: All constraints created (or "already exists" for existing ones), no errors.

**Step 3: Commit**

```bash
git add scripts/init_neo4j.cypher backend/app/repositories/base.py
git commit -m "feat(v3): add StateChange, BlueBox, Layer 3 Neo4j constraints and indexes"
```

---

### Task 1.2: Pydantic Schemas — character_state.py

**Files:**
- Create: `backend/app/schemas/character_state.py`
- Test: `backend/tests/test_character_state_schemas.py`

**Step 1: Write the test**

```python
"""Tests for V3 character state Pydantic schemas."""
from app.schemas.character_state import (
    StatEntry,
    SkillSnapshot,
    ClassSnapshot,
    TitleSnapshot,
    ItemSnapshot,
    LevelSnapshot,
    StateChangeRecord,
    CharacterStateSnapshot,
    ProgressionMilestone,
    ProgressionTimeline,
    StatDiff,
    CategoryDiff,
    CharacterComparison,
    CharacterSummary,
)


class TestStatEntry:
    def test_creates_with_required_fields(self):
        entry = StatEntry(name="Perception", value=37, last_changed_chapter=14)
        assert entry.name == "Perception"
        assert entry.value == 37

    def test_defaults(self):
        entry = StatEntry(name="Strength", value=10, last_changed_chapter=1)
        assert entry.last_changed_chapter == 1


class TestCharacterStateSnapshot:
    def test_creates_minimal(self):
        snap = CharacterStateSnapshot(
            character_name="Jake Thayne",
            canonical_name="Jake Thayne",
            book_id="abc",
            as_of_chapter=14,
            total_chapters_in_book=100,
        )
        assert snap.stats == []
        assert snap.skills == []
        assert snap.level.level is None

    def test_full_snapshot(self):
        snap = CharacterStateSnapshot(
            character_name="Jake Thayne",
            canonical_name="Jake Thayne",
            book_id="abc",
            as_of_chapter=14,
            total_chapters_in_book=100,
            role="protagonist",
            species="Human",
            description="A hunter",
            aliases=["Jake", "Thayne"],
            level=LevelSnapshot(level=88, realm="D-grade", since_chapter=42),
            stats=[StatEntry(name="Perception", value=37, last_changed_chapter=14)],
            skills=[SkillSnapshot(name="Archer's Eye", rank="rare", skill_type="active", acquired_chapter=1)],
            classes=[ClassSnapshot(name="Avaricious Arcane Hunter", tier=3, acquired_chapter=30, is_active=True)],
            titles=[TitleSnapshot(name="Hydra Slayer", effects=["fear_aura"], acquired_chapter=42)],
            items=[ItemSnapshot(name="Nanoblade", item_type="weapon", rarity="legendary", acquired_chapter=20, grants=["Shadow Strike"])],
            chapter_changes=[StateChangeRecord(chapter=14, category="stat", name="Perception", action="gain", value_delta=5)],
            total_changes_to_date=45,
        )
        assert snap.level.level == 88
        assert len(snap.stats) == 1
        assert snap.items[0].grants == ["Shadow Strike"]


class TestCharacterComparison:
    def test_creates_diff(self):
        comp = CharacterComparison(
            character_name="Jake Thayne",
            book_id="abc",
            from_chapter=10,
            to_chapter=20,
            stat_diffs=[StatDiff(name="Perception", value_at_from=20, value_at_to=37, delta=17)],
            skills=CategoryDiff(gained=["Mark of the Ambitious Hunter"], lost=[]),
            classes=CategoryDiff(),
            titles=CategoryDiff(),
            items=CategoryDiff(),
            total_changes=12,
        )
        assert comp.stat_diffs[0].delta == 17


class TestCharacterSummary:
    def test_creates_summary(self):
        summary = CharacterSummary(
            name="Jake Thayne",
            canonical_name="Jake Thayne",
            role="protagonist",
            species="Human",
        )
        assert summary.top_skills == []
        assert summary.level is None
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_character_state_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas.character_state'`

**Step 3: Write the schemas**

```python
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
```

**Step 4: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_character_state_schemas.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/schemas/character_state.py backend/tests/test_character_state_schemas.py
git commit -m "feat(v3): add Pydantic schemas for character state tracking"
```

---

### Task 1.3: CharacterStateRepository — Cypher Aggregation Queries

**Files:**
- Create: `backend/app/repositories/character_state_repo.py`
- Test: `backend/tests/test_character_state_repo.py`

**Step 1: Write the test**

These tests mock `execute_read` since they don't need a live Neo4j. We verify the repo calls the right queries and transforms results correctly.

```python
"""Tests for CharacterStateRepository."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.character_state_repo import CharacterStateRepository


@pytest.fixture
def repo(mock_neo4j_driver_with_session, mock_neo4j_session):
    """CharacterStateRepository with mocked driver."""
    # Pre-configure session.run to return empty results by default
    return CharacterStateRepository(mock_neo4j_driver_with_session)


class TestGetStatsAtChapter:
    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_character(self, repo):
        result = await repo.get_stats_at_chapter("Unknown", "book1", 10)
        assert result == []

    @pytest.mark.asyncio
    async def test_calls_cypher_with_correct_params(self, repo):
        """Verify the query uses sum(sc.value_delta) aggregation pattern."""
        await repo.get_stats_at_chapter("Jake Thayne", "book1", 14)
        # The driver.session().run() should have been called
        # We just verify no exception is raised


class TestGetLevelAtChapter:
    @pytest.mark.asyncio
    async def test_returns_none_level_when_no_data(self, repo):
        result = await repo.get_level_at_chapter("Unknown", "book1", 10)
        assert result["level"] is None


class TestGetSkillsAtChapter:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_skills(self, repo):
        result = await repo.get_skills_at_chapter("Unknown", "book1", 10)
        assert result == []


class TestGetChapterChanges:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_changes(self, repo):
        result = await repo.get_chapter_changes("Unknown", "book1", 10)
        assert result == []


class TestGetCharacterInfo:
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown(self, repo):
        result = await repo.get_character_info("Unknown", "book1")
        assert result is None


class TestGetTotalChapters:
    @pytest.mark.asyncio
    async def test_returns_zero_for_unknown_book(self, repo):
        result = await repo.get_total_chapters("book1")
        assert result == 0


class TestGetProgressionMilestones:
    @pytest.mark.asyncio
    async def test_returns_empty_timeline(self, repo):
        milestones, total = await repo.get_progression_milestones("Unknown", "book1")
        assert milestones == []
        assert total == 0
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_character_state_repo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repositories.character_state_repo'`

**Step 3: Write the repository**

```python
"""Repository for character state reconstruction queries.

Implements the Stat Ledger pattern: aggregates immutable StateChange
nodes to reconstruct character state at any chapter.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

logger = get_logger(__name__)


class CharacterStateRepository(Neo4jRepository):
    """Read-only queries for reconstructing character state at any chapter."""

    async def get_stats_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Aggregate stat deltas up to a chapter.

        Returns list of {stat_name, value, last_changed_chapter}.
        """
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id
              AND sc.chapter <= $chapter
              AND sc.category = 'stat'
            WITH sc.name AS stat_name,
                 sum(sc.value_delta) AS value,
                 max(sc.chapter) AS last_changed_chapter
            RETURN stat_name, value, last_changed_chapter
            ORDER BY stat_name
            """,
            {"name": character_name, "book_id": book_id, "chapter": chapter},
        )

    async def get_level_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> dict[str, Any]:
        """Get latest level change at or before chapter.

        Returns {level, realm, since_chapter}.
        """
        rows = await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id
              AND sc.chapter <= $chapter
              AND sc.category = 'level'
            ORDER BY sc.chapter DESC
            LIMIT 1
            RETURN sc.value_after AS level, sc.detail AS realm, sc.chapter AS since_chapter
            """,
            {"name": character_name, "book_id": book_id, "chapter": chapter},
        )
        if rows:
            return rows[0]
        return {"level": None, "realm": "", "since_chapter": None}

    async def get_skills_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get skills the character has at a chapter (temporal filtering)."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:HAS_SKILL]->(sk:Skill)
            WHERE r.valid_from_chapter <= $chapter
              AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter > $chapter)
            RETURN sk.name AS name, sk.rank AS rank, sk.skill_type AS skill_type,
                   sk.description AS description, r.valid_from_chapter AS acquired_chapter
            ORDER BY r.valid_from_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_classes_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get classes the character has at a chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:HAS_CLASS]->(cls:Class)
            WHERE r.valid_from_chapter <= $chapter
              AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter > $chapter)
            RETURN cls.name AS name, cls.tier AS tier, cls.description AS description,
                   r.valid_from_chapter AS acquired_chapter
            ORDER BY r.valid_from_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_titles_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get titles the character holds at a chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:HAS_TITLE]->(ti:Title)
            WHERE (r.acquired_chapter IS NULL OR r.acquired_chapter <= $chapter)
            RETURN ti.name AS name, ti.description AS description,
                   ti.effects AS effects, r.acquired_chapter AS acquired_chapter
            ORDER BY r.acquired_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_items_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get items the character possesses at a chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:POSSESSES]->(it:Item)
            WHERE r.valid_from_chapter <= $chapter
              AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter > $chapter)
            OPTIONAL MATCH (it)-[:GRANTS_SKILL]->(sk:Skill)
            WITH it, r, collect(sk.name) AS grants
            RETURN it.name AS name, it.item_type AS item_type, it.rarity AS rarity,
                   it.description AS description, r.valid_from_chapter AS acquired_chapter,
                   grants
            ORDER BY r.valid_from_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_chapter_changes(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get all StateChange records for a specific chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id AND sc.chapter = $chapter
            RETURN sc.category AS category, sc.name AS name, sc.action AS action,
                   sc.value_delta AS value_delta, sc.value_after AS value_after,
                   sc.detail AS detail, sc.chapter AS chapter
            ORDER BY sc.category, sc.name
            """,
            {"name": character_name, "book_id": book_id, "chapter": chapter},
        )

    async def get_character_info(
        self, character_name: str, book_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get basic character info (role, species, description, aliases)."""
        rows = await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})
            RETURN ch.canonical_name AS canonical_name,
                   ch.name AS name,
                   ch.role AS role,
                   ch.species AS species,
                   ch.description AS description,
                   ch.aliases AS aliases
            LIMIT 1
            """,
            {"name": character_name},
        )
        return rows[0] if rows else None

    async def get_total_chapters(self, book_id: str) -> int:
        """Get total chapter count for a book."""
        rows = await self.execute_read(
            """
            MATCH (c:Chapter {book_id: $book_id})
            RETURN count(c) AS total
            """,
            {"book_id": book_id},
        )
        return rows[0]["total"] if rows else 0

    async def get_progression_milestones(
        self,
        character_name: str,
        book_id: str,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated progression milestones.

        Returns (milestones, total_count).
        """
        category_filter = "AND sc.category = $category" if category else ""

        # Count query
        count_rows = await self.execute_read(
            f"""
            MATCH (ch:Character {{canonical_name: $name}})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id {category_filter}
            RETURN count(sc) AS total
            """,
            {"name": character_name, "book_id": book_id, "category": category},
        )
        total = count_rows[0]["total"] if count_rows else 0

        # Data query
        rows = await self.execute_read(
            f"""
            MATCH (ch:Character {{canonical_name: $name}})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id {category_filter}
            RETURN sc.chapter AS chapter, sc.category AS category,
                   sc.name AS name, sc.action AS action,
                   sc.value_delta AS value_delta, sc.value_after AS value_after,
                   sc.detail AS detail
            ORDER BY sc.chapter, sc.category, sc.name
            SKIP $offset LIMIT $limit
            """,
            {
                "name": character_name,
                "book_id": book_id,
                "category": category,
                "offset": offset,
                "limit": limit,
            },
        )

        return rows, total

    async def get_changes_between_chapters(
        self,
        character_name: str,
        book_id: str,
        from_chapter: int,
        to_chapter: int,
    ) -> list[dict[str, Any]]:
        """Get all StateChanges between two chapters (exclusive from, inclusive to)."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id
              AND sc.chapter > $from_chapter
              AND sc.chapter <= $to_chapter
            RETURN sc.chapter AS chapter, sc.category AS category,
                   sc.name AS name, sc.action AS action,
                   sc.value_delta AS value_delta, sc.value_after AS value_after,
                   sc.detail AS detail
            ORDER BY sc.chapter, sc.category
            """,
            {
                "name": character_name,
                "book_id": book_id,
                "from_chapter": from_chapter,
                "to_chapter": to_chapter,
            },
        )
```

**Step 4: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_character_state_repo.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/repositories/character_state_repo.py backend/tests/test_character_state_repo.py
git commit -m "feat(v3): add CharacterStateRepository with ledger aggregation queries"
```

---

### Task 1.4: Dual-Write — StateChange Creation in entity_repo Upserts

**Files:**
- Modify: `backend/app/repositories/entity_repo.py` (lines 717-769 for stat_changes, 652-713 for level_changes, 164-220 for skills, 224-271 for classes, 275-316 for titles, 476-523 for items)
- Test: `backend/tests/test_state_change_writes.py`

**Step 1: Write the test**

```python
"""Tests for StateChange dual-write in entity_repo upsert methods."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call
import pytest

from app.repositories.entity_repo import EntityRepository
from app.schemas.extraction import (
    ExtractedStatChange,
    ExtractedLevelChange,
    ExtractedSkill,
    ExtractedClass,
    ExtractedTitle,
    ExtractedItem,
)


@pytest.fixture
def repo(mock_neo4j_driver_with_session):
    return EntityRepository(mock_neo4j_driver_with_session)


class TestUpsertStatChangesCreatesStateChange:
    @pytest.mark.asyncio
    async def test_creates_state_change_nodes(self, repo, mock_neo4j_session):
        stats = [
            ExtractedStatChange(character="Jake Thayne", stat_name="Perception", value=5),
            ExtractedStatChange(character="Jake Thayne", stat_name="Agility", value=3),
        ]
        await repo.upsert_stat_changes("book1", 14, stats, "batch1")
        # Should have 2 execute_write calls: one for HAS_STAT merge, one for StateChange CREATE
        assert mock_neo4j_session.run.call_count >= 2


class TestUpsertLevelChangesCreatesStateChange:
    @pytest.mark.asyncio
    async def test_creates_level_state_change(self, repo, mock_neo4j_session):
        levels = [
            ExtractedLevelChange(character="Jake Thayne", old_level=87, new_level=88, realm="D-grade"),
        ]
        await repo.upsert_level_changes("book1", 42, levels, "batch1")
        assert mock_neo4j_session.run.call_count >= 2


class TestUpsertSkillsCreatesStateChange:
    @pytest.mark.asyncio
    async def test_creates_skill_acquire_state_change(self, repo, mock_neo4j_session):
        skills = [
            ExtractedSkill(name="Mark of the Hunter", owner="Jake Thayne", acquired_chapter=14),
        ]
        await repo.upsert_skills("book1", 14, skills, "batch1")
        assert mock_neo4j_session.run.call_count >= 2


class TestUpsertClassesCreatesStateChange:
    @pytest.mark.asyncio
    async def test_creates_class_acquire_state_change(self, repo, mock_neo4j_session):
        classes = [
            ExtractedClass(name="Arcane Hunter", owner="Jake Thayne", acquired_chapter=30),
        ]
        await repo.upsert_classes("book1", 30, classes, "batch1")
        assert mock_neo4j_session.run.call_count >= 2


class TestUpsertTitlesCreatesStateChange:
    @pytest.mark.asyncio
    async def test_creates_title_acquire_state_change(self, repo, mock_neo4j_session):
        titles = [
            ExtractedTitle(name="Hydra Slayer", owner="Jake Thayne", acquired_chapter=42),
        ]
        await repo.upsert_titles("book1", 42, titles, "batch1")
        assert mock_neo4j_session.run.call_count >= 2


class TestUpsertItemsCreatesStateChange:
    @pytest.mark.asyncio
    async def test_creates_item_acquire_state_change(self, repo, mock_neo4j_session):
        items = [
            ExtractedItem(name="Nanoblade", owner="Jake Thayne", item_type="weapon", rarity="legendary"),
        ]
        await repo.upsert_items("book1", 20, items, "batch1")
        assert mock_neo4j_session.run.call_count >= 2
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_state_change_writes.py -v`
Expected: FAIL — `assert mock_neo4j_session.run.call_count >= 2` fails (currently only 1 call per method)

**Step 3: Implement dual-write**

For each upsert method in `entity_repo.py`, add a second `execute_write` call AFTER the existing one to create StateChange nodes. The pattern for each:

**upsert_stat_changes** (after the existing UNWIND at line 741-761, add):

```python
        # Dual-write: Create immutable StateChange ledger nodes
        state_change_data = [
            {
                "character_name": sc.character,
                "category": "stat",
                "name": sc.stat_name,
                "action": "gain" if sc.value > 0 else "lose",
                "value_delta": sc.value,
            }
            for sc in stat_changes
            if sc.character and sc.stat_name
        ]
        if state_change_data:
            await self._create_state_changes(
                book_id, chapter_number, state_change_data, batch_id
            )
```

**upsert_level_changes** (after the existing UNWIND at line 678-704, add):

```python
        state_change_data = [
            {
                "character_name": lc.character,
                "category": "level",
                "name": "level",
                "action": "gain",
                "value_delta": (lc.new_level - lc.old_level) if lc.old_level and lc.new_level else None,
                "value_after": lc.new_level,
                "detail": lc.realm or "",
            }
            for lc in level_changes
            if lc.character
        ]
        if state_change_data:
            await self._create_state_changes(
                book_id, chapter_number, state_change_data, batch_id
            )
```

**upsert_skills** (after the existing UNWIND at line 187-212, add):

```python
        state_change_data = [
            {
                "character_name": s.owner,
                "category": "skill",
                "name": s.name,
                "action": "acquire",
            }
            for s in skills
            if s.owner
        ]
        if state_change_data:
            await self._create_state_changes(
                book_id, chapter_number, state_change_data, batch_id
            )
```

Same pattern for classes (`category="class"`), titles (`category="title"`), items (`category="item"`).

**Add shared helper method** to `EntityRepository` (before `upsert_extraction_result`):

```python
    async def _create_state_changes(
        self,
        book_id: str,
        chapter: int,
        changes: list[dict[str, Any]],
        batch_id: str,
    ) -> int:
        """Create immutable StateChange ledger nodes.

        Each change dict must have: character_name, category, name, action.
        Optional: value_delta, value_after, detail.
        """
        if not changes:
            return 0

        for sc in changes:
            sc.setdefault("value_delta", None)
            sc.setdefault("value_after", None)
            sc.setdefault("detail", "")

        await self.execute_write(
            """
            UNWIND $changes AS sc
            MATCH (ch:Character {canonical_name: sc.character_name})
            CREATE (ch)-[:STATE_CHANGED]->(s:StateChange {
                character_name: sc.character_name,
                book_id: $book_id,
                chapter: $chapter,
                category: sc.category,
                name: sc.name,
                action: sc.action,
                value_delta: sc.value_delta,
                value_after: sc.value_after,
                detail: sc.detail,
                batch_id: $batch_id,
                created_at: timestamp()
            })
            """,
            {
                "changes": changes,
                "book_id": book_id,
                "chapter": chapter,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "state_changes_created",
            book_id=book_id,
            chapter=chapter,
            count=len(changes),
        )
        return len(changes)
```

**Step 4: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_state_change_writes.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/ -v --ignore=backend/tests/test_embedding_pipeline.py --ignore=backend/tests/test_chat_service.py`
Expected: All existing tests still PASS (no regressions)

**Step 6: Commit**

```bash
git add backend/app/repositories/entity_repo.py backend/tests/test_state_change_writes.py
git commit -m "feat(v3): dual-write StateChange ledger nodes in all entity upsert methods"
```

---

### Task 1.5: Character State API Endpoints

**Files:**
- Create: `backend/app/api/routes/characters.py`
- Modify: `backend/app/main.py` (line 22, import; line 201, include_router)
- Test: `backend/tests/test_character_state_api.py`

**Step 1: Write the test**

```python
"""Tests for character state API endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestGetCharacterStateAt:
    def test_returns_404_for_unknown_character(self, client):
        with patch("app.api.routes.characters.get_neo4j_driver") as mock_driver:
            mock_driver.return_value = AsyncMock()
            # Mock repo to return None for character info
            with patch("app.api.routes.characters.CharacterStateRepository") as MockRepo:
                instance = MockRepo.return_value
                instance.get_character_info = AsyncMock(return_value=None)
                response = client.get("/api/characters/Unknown/at/10?book_id=abc")
                assert response.status_code == 404

    def test_returns_200_with_snapshot(self, client):
        with patch("app.api.routes.characters.get_neo4j_driver") as mock_driver:
            mock_driver.return_value = AsyncMock()
            with patch("app.api.routes.characters.CharacterStateRepository") as MockRepo:
                instance = MockRepo.return_value
                instance.get_character_info = AsyncMock(return_value={
                    "canonical_name": "Jake Thayne",
                    "name": "Jake",
                    "role": "protagonist",
                    "species": "Human",
                    "description": "A hunter",
                    "aliases": ["Jake", "Thayne"],
                })
                instance.get_total_chapters = AsyncMock(return_value=100)
                instance.get_stats_at_chapter = AsyncMock(return_value=[
                    {"stat_name": "Perception", "value": 37, "last_changed_chapter": 14}
                ])
                instance.get_level_at_chapter = AsyncMock(return_value={
                    "level": 88, "realm": "D-grade", "since_chapter": 42
                })
                instance.get_skills_at_chapter = AsyncMock(return_value=[])
                instance.get_classes_at_chapter = AsyncMock(return_value=[])
                instance.get_titles_at_chapter = AsyncMock(return_value=[])
                instance.get_items_at_chapter = AsyncMock(return_value=[])
                instance.get_chapter_changes = AsyncMock(return_value=[])
                instance.get_progression_milestones = AsyncMock(return_value=([], 0))

                response = client.get("/api/characters/Jake%20Thayne/at/14?book_id=abc")
                assert response.status_code == 200
                data = response.json()
                assert data["character_name"] == "Jake Thayne"
                assert data["as_of_chapter"] == 14
                assert data["stats"][0]["name"] == "Perception"
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_character_state_api.py -v`
Expected: FAIL — route not registered

**Step 3: Write the API router**

Create `backend/app/api/routes/characters.py`:

```python
"""Character state tracking API endpoints.

Provides endpoints for:
- Character sheet at any chapter (snapshot)
- Progression timeline
- Chapter comparison
- Lightweight summary (for hover tooltips)
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import get_neo4j_driver
from app.repositories.character_state_repo import CharacterStateRepository
from app.schemas.character_state import (
    CategoryDiff,
    CharacterComparison,
    CharacterStateSnapshot,
    CharacterSummary,
    ClassSnapshot,
    ItemSnapshot,
    LevelSnapshot,
    ProgressionMilestone,
    ProgressionTimeline,
    SkillSnapshot,
    StatDiff,
    StatEntry,
    StateChangeRecord,
    TitleSnapshot,
)

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("/{name}/at/{chapter}", response_model=CharacterStateSnapshot)
async def get_character_state_at(
    name: str,
    chapter: int,
    book_id: str = Query(..., description="Book identifier"),
) -> CharacterStateSnapshot:
    """Get full character sheet reconstructed at a specific chapter."""
    driver = get_neo4j_driver()
    repo = CharacterStateRepository(driver)

    # Verify character exists
    char_info = await repo.get_character_info(name, book_id)
    if not char_info:
        raise HTTPException(status_code=404, detail=f"Character {name!r} not found")

    total_chapters = await repo.get_total_chapters(book_id)

    # Run all aggregation queries in parallel
    stats_raw, level_raw, skills_raw, classes_raw, titles_raw, items_raw, changes_raw, (_, total_changes) = (
        await asyncio.gather(
            repo.get_stats_at_chapter(name, book_id, chapter),
            repo.get_level_at_chapter(name, book_id, chapter),
            repo.get_skills_at_chapter(name, book_id, chapter),
            repo.get_classes_at_chapter(name, book_id, chapter),
            repo.get_titles_at_chapter(name, book_id, chapter),
            repo.get_items_at_chapter(name, book_id, chapter),
            repo.get_chapter_changes(name, book_id, chapter),
            repo.get_progression_milestones(name, book_id, limit=0),
        )
    )

    return CharacterStateSnapshot(
        character_name=char_info.get("name", name),
        canonical_name=char_info.get("canonical_name", name),
        book_id=book_id,
        as_of_chapter=chapter,
        total_chapters_in_book=total_chapters,
        role=char_info.get("role", ""),
        species=char_info.get("species", ""),
        description=char_info.get("description", ""),
        aliases=char_info.get("aliases") or [],
        level=LevelSnapshot(
            level=level_raw.get("level"),
            realm=level_raw.get("realm", ""),
            since_chapter=level_raw.get("since_chapter"),
        ),
        stats=[
            StatEntry(
                name=s["stat_name"],
                value=s["value"],
                last_changed_chapter=s["last_changed_chapter"],
            )
            for s in stats_raw
        ],
        skills=[
            SkillSnapshot(
                name=s["name"],
                rank=s.get("rank", ""),
                skill_type=s.get("skill_type", ""),
                description=s.get("description", ""),
                acquired_chapter=s.get("acquired_chapter"),
            )
            for s in skills_raw
        ],
        classes=[
            ClassSnapshot(
                name=c["name"],
                tier=c.get("tier"),
                description=c.get("description", ""),
                acquired_chapter=c.get("acquired_chapter"),
                is_active=True,  # All returned classes are active at this chapter
            )
            for c in classes_raw
        ],
        titles=[
            TitleSnapshot(
                name=t["name"],
                description=t.get("description", ""),
                effects=t.get("effects") or [],
                acquired_chapter=t.get("acquired_chapter"),
            )
            for t in titles_raw
        ],
        items=[
            ItemSnapshot(
                name=i["name"],
                item_type=i.get("item_type", ""),
                rarity=i.get("rarity", ""),
                description=i.get("description", ""),
                acquired_chapter=i.get("acquired_chapter"),
                grants=i.get("grants") or [],
            )
            for i in items_raw
        ],
        chapter_changes=[
            StateChangeRecord(
                chapter=ch["chapter"],
                category=ch["category"],
                name=ch["name"],
                action=ch["action"],
                value_delta=ch.get("value_delta"),
                value_after=ch.get("value_after"),
                detail=ch.get("detail", ""),
            )
            for ch in changes_raw
        ],
        total_changes_to_date=total_changes,
    )


@router.get("/{name}/progression", response_model=ProgressionTimeline)
async def get_character_progression(
    name: str,
    book_id: str = Query(..., description="Book identifier"),
    category: str | None = Query(None, description="Filter by category"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> ProgressionTimeline:
    """Get paginated progression timeline for a character."""
    driver = get_neo4j_driver()
    repo = CharacterStateRepository(driver)

    milestones_raw, total = await repo.get_progression_milestones(
        name, book_id, category=category, offset=offset, limit=limit
    )

    return ProgressionTimeline(
        character_name=name,
        book_id=book_id,
        milestones=[
            ProgressionMilestone(
                chapter=m["chapter"],
                category=m["category"],
                name=m["name"],
                action=m["action"],
                value_delta=m.get("value_delta"),
                value_after=m.get("value_after"),
                detail=m.get("detail", ""),
            )
            for m in milestones_raw
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{name}/compare", response_model=CharacterComparison)
async def compare_character_state(
    name: str,
    book_id: str = Query(...),
    from_chapter: int = Query(..., alias="from"),
    to_chapter: int = Query(..., alias="to"),
) -> CharacterComparison:
    """Compare character state between two chapters."""
    driver = get_neo4j_driver()
    repo = CharacterStateRepository(driver)

    # Get stats at both chapters in parallel
    stats_from, stats_to, changes = await asyncio.gather(
        repo.get_stats_at_chapter(name, book_id, from_chapter),
        repo.get_stats_at_chapter(name, book_id, to_chapter),
        repo.get_changes_between_chapters(name, book_id, from_chapter, to_chapter),
    )

    # Build stat diffs
    from_map = {s["stat_name"]: s["value"] for s in stats_from}
    to_map = {s["stat_name"]: s["value"] for s in stats_to}
    all_stats = sorted(set(from_map) | set(to_map))
    stat_diffs = [
        StatDiff(
            name=s,
            value_at_from=from_map.get(s, 0),
            value_at_to=to_map.get(s, 0),
            delta=to_map.get(s, 0) - from_map.get(s, 0),
        )
        for s in all_stats
        if from_map.get(s, 0) != to_map.get(s, 0)
    ]

    # Build category diffs from changes
    def _category_diff(cat: str) -> CategoryDiff:
        gained = [c["name"] for c in changes if c["category"] == cat and c["action"] in ("acquire", "gain")]
        lost = [c["name"] for c in changes if c["category"] == cat and c["action"] in ("lose", "drop")]
        return CategoryDiff(gained=gained, lost=lost)

    # Get level at both points
    level_from_raw, level_to_raw = await asyncio.gather(
        repo.get_level_at_chapter(name, book_id, from_chapter),
        repo.get_level_at_chapter(name, book_id, to_chapter),
    )

    return CharacterComparison(
        character_name=name,
        book_id=book_id,
        from_chapter=from_chapter,
        to_chapter=to_chapter,
        level_from=level_from_raw.get("level"),
        level_to=level_to_raw.get("level"),
        stat_diffs=stat_diffs,
        skills=_category_diff("skill"),
        classes=_category_diff("class"),
        titles=_category_diff("title"),
        items=_category_diff("item"),
        total_changes=len(changes),
    )


@router.get("/{name}/summary", response_model=CharacterSummary)
async def get_character_summary(
    name: str,
    chapter: int | None = Query(None),
    book_id: str | None = Query(None),
) -> CharacterSummary:
    """Lightweight character summary for hover tooltips."""
    driver = get_neo4j_driver()
    repo = CharacterStateRepository(driver)

    char_info = await repo.get_character_info(name, book_id)
    if not char_info:
        raise HTTPException(status_code=404, detail=f"Character {name!r} not found")

    level = None
    realm = ""
    active_class = None
    top_skills: list[str] = []

    if book_id and chapter:
        level_raw, skills_raw, classes_raw = await asyncio.gather(
            repo.get_level_at_chapter(name, book_id, chapter),
            repo.get_skills_at_chapter(name, book_id, chapter),
            repo.get_classes_at_chapter(name, book_id, chapter),
        )
        level = level_raw.get("level")
        realm = level_raw.get("realm", "")
        top_skills = [s["name"] for s in skills_raw[:3]]
        if classes_raw:
            active_class = classes_raw[-1]["name"]  # Most recently acquired
    else:
        level = getattr(char_info, "level", None) if hasattr(char_info, "level") else char_info.get("level")

    return CharacterSummary(
        name=char_info.get("name", name),
        canonical_name=char_info.get("canonical_name", name),
        role=char_info.get("role", ""),
        species=char_info.get("species", ""),
        level=level,
        realm=realm,
        active_class=active_class,
        top_skills=top_skills,
        description=char_info.get("description", ""),
    )
```

Register in `main.py`:
- Add to import (line 22): `from app.api.routes import admin, books, characters, chat, graph, health, reader, stream`
- Add router (after line 201): `app.include_router(characters.router, prefix="/api")`

**Step 4: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_character_state_api.py -v`
Expected: All PASS

**Step 5: Run full suite**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/ -v --ignore=backend/tests/test_embedding_pipeline.py --ignore=backend/tests/test_chat_service.py`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/api/routes/characters.py backend/app/main.py backend/tests/test_character_state_api.py
git commit -m "feat(v3): add character state API endpoints (snapshot, progression, compare, summary)"
```

---

## Phase 2: BlueBox Grouping + Provenance

### Task 2.1: BlueBox Grouping Service

**Files:**
- Create: `backend/app/services/extraction/bluebox.py`
- Test: `backend/tests/test_bluebox.py`

**Step 1: Write the test**

```python
"""Tests for BlueBox grouping service."""
from __future__ import annotations

import pytest

from app.services.extraction.bluebox import group_blue_boxes, BlueBoxGroup


class TestGroupBlueBoxes:
    def test_empty_paragraphs(self):
        result = group_blue_boxes([])
        assert result == []

    def test_no_blue_boxes(self):
        paragraphs = [
            {"index": 0, "type": "narration", "text": "Jake walked."},
            {"index": 1, "type": "dialogue", "text": '"Hello," said Jake.'},
        ]
        result = group_blue_boxes(paragraphs)
        assert result == []

    def test_single_blue_box(self):
        paragraphs = [
            {"index": 0, "type": "narration", "text": "Jake fought."},
            {"index": 1, "type": "blue_box", "text": "[Skill Acquired: Mark of the Hunter - Legendary]"},
            {"index": 2, "type": "narration", "text": "He felt stronger."},
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1
        assert result[0].paragraph_start == 1
        assert result[0].paragraph_end == 1
        assert "Mark of the Hunter" in result[0].raw_text

    def test_consecutive_blue_boxes_grouped(self):
        paragraphs = [
            {"index": 0, "type": "blue_box", "text": "[Skill Acquired: Mark of the Hunter]"},
            {"index": 1, "type": "blue_box", "text": "+5 Perception"},
            {"index": 2, "type": "blue_box", "text": "+3 Agility"},
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1
        assert result[0].paragraph_start == 0
        assert result[0].paragraph_end == 2
        assert "+5 Perception" in result[0].raw_text
        assert "+3 Agility" in result[0].raw_text

    def test_gap_of_one_narration_still_groups(self):
        """Blue boxes with 1 narration paragraph between them should still group."""
        paragraphs = [
            {"index": 0, "type": "blue_box", "text": "[Skill Acquired: Mark]"},
            {"index": 1, "type": "narration", "text": "He felt a surge."},
            {"index": 2, "type": "blue_box", "text": "+5 Perception"},
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1

    def test_gap_of_two_creates_separate_groups(self):
        """Blue boxes with 2+ narration between them are separate groups."""
        paragraphs = [
            {"index": 0, "type": "blue_box", "text": "[Skill Acquired: Mark]"},
            {"index": 1, "type": "narration", "text": "He walked."},
            {"index": 2, "type": "narration", "text": "He ran."},
            {"index": 3, "type": "blue_box", "text": "Level: 87 -> 88"},
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 2

    def test_box_type_classification(self):
        paragraphs = [
            {"index": 0, "type": "blue_box", "text": "Level: 87 -> 88"},
        ]
        result = group_blue_boxes(paragraphs)
        assert result[0].box_type == "level_up"

        paragraphs2 = [
            {"index": 0, "type": "blue_box", "text": "[Skill Acquired: Something]"},
        ]
        result2 = group_blue_boxes(paragraphs2)
        assert result2[0].box_type == "skill_acquisition"
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_bluebox.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
"""BlueBox grouping service — Passe 0.5.

Groups consecutive blue_box paragraphs into coherent BlueBox units.
V2 already tags paragraphs with type="blue_box" during ingestion;
this service groups adjacent ones into logical system notification blocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Gap tolerance: blue boxes separated by at most 1 non-blue-box paragraph
# are considered part of the same notification block
_MAX_GAP = 1

# Classification patterns
_LEVEL_PATTERN = re.compile(r"Level.*?(?:→|->|\d+\s*to\s*\d+)", re.IGNORECASE)
_SKILL_PATTERN = re.compile(r"(?:Skill|Ability)\s+(?:Acquired|Learned|Obtained)", re.IGNORECASE)
_TITLE_PATTERN = re.compile(r"Title\s+(?:earned|obtained|acquired)", re.IGNORECASE)
_STAT_PATTERN = re.compile(r"[+-]\d+\s+(?:Strength|Agility|Perception|Endurance|Vitality|Toughness|Wisdom|Intelligence|Willpower|Free\s+Points)", re.IGNORECASE)


@dataclass
class BlueBoxGroup:
    """A grouped blue box from consecutive blue_box paragraphs."""

    paragraph_start: int
    paragraph_end: int
    raw_text: str
    box_type: str = "mixed"
    paragraph_indexes: list[int] = field(default_factory=list)


def _classify_box(text: str) -> str:
    """Classify a blue box by its content."""
    has_level = bool(_LEVEL_PATTERN.search(text))
    has_skill = bool(_SKILL_PATTERN.search(text))
    has_title = bool(_TITLE_PATTERN.search(text))
    has_stat = bool(_STAT_PATTERN.search(text))

    flags = sum([has_level, has_skill, has_title])
    if flags > 1:
        return "mixed"
    if has_level:
        return "level_up"
    if has_skill:
        return "skill_acquisition"
    if has_title:
        return "title"
    if has_stat:
        return "stat_block"
    return "mixed"


def group_blue_boxes(paragraphs: list[dict[str, Any]]) -> list[BlueBoxGroup]:
    """Group consecutive blue_box paragraphs into BlueBox units.

    Args:
        paragraphs: List of paragraph dicts with keys: index, type, text.

    Returns:
        List of BlueBoxGroup with merged text and classification.
    """
    if not paragraphs:
        return []

    # Find blue_box paragraph indexes
    blue_indexes = [p["index"] for p in paragraphs if p.get("type") == "blue_box"]
    if not blue_indexes:
        return []

    # Build index -> paragraph map
    para_map = {p["index"]: p for p in paragraphs}

    # Group with gap tolerance
    groups: list[list[int]] = []
    current_group: list[int] = [blue_indexes[0]]

    for i in range(1, len(blue_indexes)):
        gap = blue_indexes[i] - blue_indexes[i - 1] - 1
        if gap <= _MAX_GAP:
            current_group.append(blue_indexes[i])
        else:
            groups.append(current_group)
            current_group = [blue_indexes[i]]
    groups.append(current_group)

    # Build BlueBoxGroup objects
    result: list[BlueBoxGroup] = []
    for group_indexes in groups:
        texts = [para_map[idx]["text"] for idx in group_indexes if idx in para_map]
        raw_text = "\n".join(texts)
        box = BlueBoxGroup(
            paragraph_start=group_indexes[0],
            paragraph_end=group_indexes[-1],
            raw_text=raw_text,
            box_type=_classify_box(raw_text),
            paragraph_indexes=group_indexes,
        )
        result.append(box)

    logger.info("blue_boxes_grouped", count=len(result))
    return result
```

**Step 4: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_bluebox.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/services/extraction/bluebox.py backend/tests/test_bluebox.py
git commit -m "feat(v3): add BlueBox grouping service (Passe 0.5)"
```

---

### Task 2.2: BlueBox Persistence in entity_repo

**Files:**
- Modify: `backend/app/repositories/entity_repo.py` (add `upsert_blue_boxes` method)
- Test: `backend/tests/test_bluebox_persistence.py`

**Step 1: Write the test**

```python
"""Tests for BlueBox persistence."""
from __future__ import annotations

import pytest

from app.repositories.entity_repo import EntityRepository
from app.services.extraction.bluebox import BlueBoxGroup


@pytest.fixture
def repo(mock_neo4j_driver_with_session):
    return EntityRepository(mock_neo4j_driver_with_session)


class TestUpsertBlueBoxes:
    @pytest.mark.asyncio
    async def test_creates_bluebox_nodes(self, repo, mock_neo4j_session):
        boxes = [
            BlueBoxGroup(
                paragraph_start=1,
                paragraph_end=3,
                raw_text="[Skill Acquired: Mark]\n+5 Perception\n+3 Agility",
                box_type="skill_acquisition",
                paragraph_indexes=[1, 2, 3],
            ),
        ]
        count = await repo.upsert_blue_boxes("book1", 14, boxes, "batch1")
        assert count == 1
        assert mock_neo4j_session.run.call_count >= 1

    @pytest.mark.asyncio
    async def test_empty_list(self, repo):
        count = await repo.upsert_blue_boxes("book1", 14, [], "batch1")
        assert count == 0
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_bluebox_persistence.py -v`
Expected: FAIL — `AttributeError: 'EntityRepository' object has no attribute 'upsert_blue_boxes'`

**Step 3: Implement upsert_blue_boxes**

Add to `entity_repo.py` (before the `_create_state_changes` helper):

```python
    async def upsert_blue_boxes(
        self,
        book_id: str,
        chapter_number: int,
        boxes: list,  # list[BlueBoxGroup]
        batch_id: str = "",
    ) -> int:
        """Persist BlueBox grouping nodes to Neo4j."""
        if not boxes:
            return 0

        data = [
            {
                "index": idx,
                "raw_text": box.raw_text,
                "box_type": box.box_type,
                "paragraph_start": box.paragraph_start,
                "paragraph_end": box.paragraph_end,
            }
            for idx, box in enumerate(boxes)
        ]

        await self.execute_write(
            """
            UNWIND $boxes AS bb
            MERGE (b:BlueBox {book_id: $book_id, chapter: $chapter, index: bb.index})
            ON CREATE SET
                b.raw_text = bb.raw_text,
                b.box_type = bb.box_type,
                b.paragraph_start = bb.paragraph_start,
                b.paragraph_end = bb.paragraph_end,
                b.batch_id = $batch_id,
                b.created_at = timestamp()
            ON MATCH SET
                b.raw_text = bb.raw_text,
                b.box_type = bb.box_type,
                b.batch_id = $batch_id
            """,
            {
                "boxes": data,
                "book_id": book_id,
                "chapter": chapter_number,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "blue_boxes_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(boxes),
        )
        return len(boxes)
```

**Step 4: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_bluebox_persistence.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/repositories/entity_repo.py backend/tests/test_bluebox_persistence.py
git commit -m "feat(v3): add BlueBox persistence to entity_repo"
```

---

### Task 2.3: Provenance Extraction Schemas + Prompt

**Files:**
- Modify: `backend/app/schemas/extraction.py` (add `ProvenanceResult` model)
- Create: `backend/app/prompts/extraction_provenance.py`
- Test: `backend/tests/test_provenance_schema.py`

**Step 1: Write the test**

```python
"""Tests for provenance extraction schemas."""
from __future__ import annotations

from app.schemas.extraction import SkillProvenance, ProvenanceResult


class TestSkillProvenance:
    def test_creates_with_required(self):
        p = SkillProvenance(
            skill_name="Shadow Strike",
            source_type="item",
            source_name="Nanoblade",
            confidence=0.9,
        )
        assert p.source_type == "item"

    def test_rejects_low_confidence(self):
        p = SkillProvenance(
            skill_name="Unknown",
            source_type="unknown",
            source_name="",
            confidence=0.3,
        )
        assert p.confidence == 0.3  # We store it; filtering is at persistence time


class TestProvenanceResult:
    def test_creates_empty(self):
        r = ProvenanceResult()
        assert r.provenances == []

    def test_filters_high_confidence(self):
        r = ProvenanceResult(provenances=[
            SkillProvenance(skill_name="A", source_type="item", source_name="X", confidence=0.9),
            SkillProvenance(skill_name="B", source_type="unknown", source_name="", confidence=0.3),
        ])
        high = [p for p in r.provenances if p.confidence >= 0.7]
        assert len(high) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_provenance_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'SkillProvenance'`

**Step 3: Add schemas to extraction.py**

Append to `backend/app/schemas/extraction.py` (before the reconciliation section, around line 283):

```python
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
```

**Step 4: Create prompt file**

Create `backend/app/prompts/extraction_provenance.py`:

```python
"""Prompt templates for skill provenance extraction (Pass 2b).

Identifies which items, classes, bloodlines, or titles grant specific skills.
"""

PROVENANCE_SYSTEM_PROMPT = """\
You are a LitRPG system analyst. Given a chapter excerpt and a list of skills
acquired in this chapter, identify the SOURCE of each skill.

Sources can be:
- item: An equipment or artifact grants the skill
- class: A class or job provides the skill
- bloodline: A bloodline ability manifests as the skill
- title: A title confers the skill
- unknown: Source is not mentioned or unclear

For each skill, return the source_type, source_name, and your confidence (0.0-1.0).
Only report confidence >= 0.5. If no source is evident, use "unknown".
"""

PROVENANCE_FEW_SHOT = [
    {
        "chapter_text": (
            "Jake equipped the Nanoblade, feeling its power flow through him.\n"
            "[Skill Acquired: Shadow Strike - Rare]\n"
            "The blade's enchantment granted him a new combat technique."
        ),
        "skills": ["Shadow Strike"],
        "result": [
            {
                "skill_name": "Shadow Strike",
                "source_type": "item",
                "source_name": "Nanoblade",
                "confidence": 0.95,
                "context": "The blade's enchantment granted him a new combat technique.",
            }
        ],
    },
    {
        "chapter_text": (
            "With his evolution to Avaricious Arcane Hunter, Jake gained access to "
            "a whole new set of abilities.\n"
            "[Skill Acquired: Arcane Powershot - Epic]"
        ),
        "skills": ["Arcane Powershot"],
        "result": [
            {
                "skill_name": "Arcane Powershot",
                "source_type": "class",
                "source_name": "Avaricious Arcane Hunter",
                "confidence": 0.9,
                "context": "evolution to Avaricious Arcane Hunter, Jake gained access to a whole new set of abilities",
            }
        ],
    },
]
```

**Step 5: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_provenance_schema.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/schemas/extraction.py backend/app/prompts/extraction_provenance.py backend/tests/test_provenance_schema.py
git commit -m "feat(v3): add provenance schemas and prompt templates"
```

---

### Task 2.4: Provenance Extraction Service

**Files:**
- Create: `backend/app/services/extraction/provenance.py`
- Test: `backend/tests/test_provenance_extraction.py`

**Step 1: Write the test**

```python
"""Tests for provenance extraction service."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.extraction import SkillProvenance
from app.services.extraction.provenance import extract_provenance


class TestExtractProvenance:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_skills(self):
        result = await extract_provenance(
            chapter_text="Jake walked around.",
            skills_acquired=[],
            chapter_entities={"items": [], "classes": [], "bloodlines": []},
        )
        assert result.provenances == []

    @pytest.mark.asyncio
    async def test_returns_provenances_with_mocked_llm(self):
        with patch("app.services.extraction.provenance._call_instructor") as mock_call:
            mock_call.return_value = [
                SkillProvenance(
                    skill_name="Shadow Strike",
                    source_type="item",
                    source_name="Nanoblade",
                    confidence=0.9,
                ),
            ]
            result = await extract_provenance(
                chapter_text="Jake equipped Nanoblade. [Skill Acquired: Shadow Strike]",
                skills_acquired=["Shadow Strike"],
                chapter_entities={"items": ["Nanoblade"], "classes": [], "bloodlines": []},
            )
            assert len(result.provenances) == 1
            assert result.provenances[0].source_name == "Nanoblade"
```

**Step 2: Run test to verify it fails**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_provenance_extraction.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
"""Provenance extraction service — Pass 2b.

After systems extraction identifies skills acquired in a chapter,
this pass determines the SOURCE of each skill (item, class, bloodline, etc.)
using an LLM with structured output.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.prompts.extraction_provenance import PROVENANCE_FEW_SHOT, PROVENANCE_SYSTEM_PROMPT
from app.schemas.extraction import ProvenanceResult, SkillProvenance

logger = get_logger(__name__)


async def _call_instructor(
    chapter_text: str,
    skills: list[str],
    entities: dict[str, list[str]],
) -> list[SkillProvenance]:
    """Call Instructor with Gemini Flash for provenance extraction.

    Isolated for easy mocking in tests.
    """
    from app.core.config import settings
    from app.llm.providers import get_instructor_client

    client = get_instructor_client()
    if client is None:
        logger.warning("instructor_client_unavailable")
        return []

    prompt = (
        f"{PROVENANCE_SYSTEM_PROMPT}\n\n"
        f"## Skills acquired this chapter:\n"
        f"{', '.join(skills)}\n\n"
        f"## Known entities in context:\n"
        f"Items: {', '.join(entities.get('items', []))}\n"
        f"Classes: {', '.join(entities.get('classes', []))}\n"
        f"Bloodlines: {', '.join(entities.get('bloodlines', []))}\n\n"
        f"## Chapter text:\n{chapter_text[:4000]}\n\n"
        f"Return a list of SkillProvenance for each skill."
    )

    try:
        result = await client.chat.completions.create(
            model=settings.reconciliation_model or "gpt-4o-mini",
            response_model=list[SkillProvenance],
            messages=[{"role": "user", "content": prompt}],
            max_retries=2,
        )
        return result
    except Exception:
        logger.warning("provenance_extraction_failed", exc_info=True)
        return []


async def extract_provenance(
    chapter_text: str,
    skills_acquired: list[str],
    chapter_entities: dict[str, list[str]],
) -> ProvenanceResult:
    """Extract provenance for skills acquired in a chapter.

    Args:
        chapter_text: Full chapter text.
        skills_acquired: List of skill names acquired this chapter.
        chapter_entities: Dict of entity types to names present in chapter.

    Returns:
        ProvenanceResult with confidence-scored provenance links.
    """
    if not skills_acquired:
        return ProvenanceResult()

    provenances = await _call_instructor(chapter_text, skills_acquired, chapter_entities)

    # Filter to only high-confidence results
    filtered = [p for p in provenances if p.confidence >= 0.5]

    logger.info(
        "provenance_extracted",
        total=len(provenances),
        high_confidence=len([p for p in filtered if p.confidence >= 0.7]),
        filtered=len(filtered),
    )

    return ProvenanceResult(provenances=filtered)
```

**Step 4: Run tests**

Run: `cd E:/RAG && python -m uv run pytest backend/tests/test_provenance_extraction.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/services/extraction/provenance.py backend/tests/test_provenance_extraction.py
git commit -m "feat(v3): add provenance extraction service (Pass 2b)"
```

---

### Task 2.5: GRANTS Relation Persistence

**Files:**
- Modify: `backend/app/repositories/entity_repo.py` (add `upsert_grants_relations`)
- Test: `backend/tests/test_grants_persistence.py`

**Step 1: Write the test**

```python
"""Tests for GRANTS relation persistence."""
from __future__ import annotations

import pytest

from app.repositories.entity_repo import EntityRepository
from app.schemas.extraction import SkillProvenance


@pytest.fixture
def repo(mock_neo4j_driver_with_session):
    return EntityRepository(mock_neo4j_driver_with_session)


class TestUpsertGrantsRelations:
    @pytest.mark.asyncio
    async def test_creates_grants_skill_from_item(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Shadow Strike",
                source_type="item",
                source_name="Nanoblade",
                confidence=0.9,
            ),
        ]
        count = await repo.upsert_grants_relations(provenances, "batch1")
        assert count == 1
        assert mock_neo4j_session.run.call_count >= 1

    @pytest.mark.asyncio
    async def test_skips_low_confidence(self, repo, mock_neo4j_session):
        provenances = [
            SkillProvenance(
                skill_name="Unknown",
                source_type="unknown",
                source_name="",
                confidence=0.3,
            ),
        ]
        count = await repo.upsert_grants_relations(provenances, "batch1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_empty_list(self, repo):
        count = await repo.upsert_grants_relations([], "batch1")
        assert count == 0
```

**Step 2: Run to verify fails, Step 3: Implement**

Add to `entity_repo.py`:

```python
    async def upsert_grants_relations(
        self,
        provenances: list,  # list[SkillProvenance]
        batch_id: str = "",
    ) -> int:
        """Create GRANTS_SKILL relationships from provenance data.

        Only creates relations for high-confidence (>= 0.7) provenances
        with known source types (item, class, bloodline).
        """
        # Filter to actionable provenances
        valid = [
            p for p in provenances
            if p.confidence >= 0.7
            and p.source_type in ("item", "class", "bloodline")
            and p.source_name
        ]
        if not valid:
            return 0

        # Group by source type for label-aware queries
        label_map = {"item": "Item", "class": "Class", "bloodline": "Bloodline"}

        created = 0
        for source_type, label in label_map.items():
            type_provenances = [p for p in valid if p.source_type == source_type]
            if not type_provenances:
                continue

            data = [
                {"source_name": p.source_name, "skill_name": p.skill_name}
                for p in type_provenances
            ]

            await self.execute_write(
                f"""
                UNWIND $data AS d
                MATCH (src:{label} {{name: d.source_name}})
                MATCH (sk:Skill {{name: d.skill_name}})
                MERGE (src)-[r:GRANTS_SKILL]->(sk)
                ON CREATE SET r.batch_id = $batch_id, r.created_at = timestamp()
                """,
                {"data": data, "batch_id": batch_id},
            )
            created += len(type_provenances)

        logger.info("grants_relations_upserted", count=created)
        return created
```

**Step 4-6: Run tests, verify, commit**

```bash
git add backend/app/repositories/entity_repo.py backend/tests/test_grants_persistence.py
git commit -m "feat(v3): add GRANTS_SKILL relation persistence for provenance"
```

---

## Phase 3: Layer 3 Extraction

### Task 3.1: Layer 3 Schemas

**Files:**
- Modify: `backend/app/schemas/extraction.py`
- Test: `backend/tests/test_layer3_schemas.py`

**Step 1: Write the test**

```python
"""Tests for Layer 3 extraction schemas."""
from app.schemas.extraction import (
    ExtractedBloodline,
    ExtractedProfession,
    ExtractedChurch,
    Layer3ExtractionResult,
)


class TestExtractedBloodline:
    def test_creates_with_required(self):
        b = ExtractedBloodline(name="Bloodline of the Primal Hunter")
        assert b.name == "Bloodline of the Primal Hunter"
        assert b.effects == []


class TestLayer3ExtractionResult:
    def test_creates_empty(self):
        r = Layer3ExtractionResult()
        assert r.bloodlines == []
        assert r.professions == []
        assert r.churches == []
```

**Step 2-3: Fail → Implement**

Add to `extraction.py`:

```python
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
```

**Step 4-5: Run tests, commit**

```bash
git add backend/app/schemas/extraction.py backend/tests/test_layer3_schemas.py
git commit -m "feat(v3): add Layer 3 extraction schemas (Bloodline, Profession, Church)"
```

---

### Task 3.2: Layer 3 Regex Patterns

**Files:**
- Modify: `backend/app/services/extraction/regex_extractor.py` (add Layer 3 patterns to `default()`)
- Test: `backend/tests/test_regex_extractor.py` (add Layer 3 test cases)

**Step 1: Write the test**

Add to `test_regex_extractor.py`:

```python
class TestLayer3Patterns:
    @pytest.fixture
    def extractor(self) -> RegexExtractor:
        return RegexExtractor.default()

    def test_bloodline_notification(self, extractor):
        text = "[Bloodline Awakened: Bloodline of the Primal Hunter]"
        matches = extractor.extract(text, chapter_number=1)
        names = [m.captures.get("name", "") for m in matches if m.pattern_name == "bloodline_notification"]
        assert "Bloodline of the Primal Hunter" in names

    def test_profession_obtained(self, extractor):
        text = "Profession Obtained: Alchemist of the Malefic Viper (Legendary)"
        matches = extractor.extract(text, chapter_number=1)
        names = [m.captures.get("name", "") for m in matches if m.pattern_name == "profession_obtained"]
        assert "Alchemist of the Malefic Viper" in names

    def test_blessing_received(self, extractor):
        text = "[Blessing of the Malefic Viper received]"
        matches = extractor.extract(text, chapter_number=1)
        names = [m.captures.get("name", "") for m in matches if m.pattern_name == "blessing_received"]
        assert "the Malefic Viper" in names
```

**Step 2-3: Fail → Add patterns to `default()` method**

Add 3 new patterns to the `default()` method in `regex_extractor.py`:

```python
            RegexPattern(
                name="bloodline_notification",
                pattern=re.compile(
                    r"\[Bloodline\s+(?:Awakened|Evolved|Activated):\s*(.+?)\]",
                    re.IGNORECASE,
                ),
                entity_type="Bloodline",
                capture_names=["name"],
            ),
            RegexPattern(
                name="profession_obtained",
                pattern=re.compile(
                    r"Profession\s+(?:Obtained|Acquired|Gained):\s*(.+?)\s*(?:\((.+?)\))?$",
                    re.IGNORECASE | re.MULTILINE,
                ),
                entity_type="Profession",
                capture_names=["name", "tier_info"],
            ),
            RegexPattern(
                name="blessing_received",
                pattern=re.compile(
                    r"\[Blessing\s+(?:of|from)\s+(.+?)(?:\s+received|\])",
                    re.IGNORECASE,
                ),
                entity_type="Church",
                capture_names=["name"],
            ),
```

**Step 4-5: Run tests, commit**

```bash
git add backend/app/services/extraction/regex_extractor.py backend/tests/test_regex_extractor.py
git commit -m "feat(v3): add Layer 3 regex patterns (bloodline, profession, blessing)"
```

---

### Task 3.3: Layer 3 Entity Persistence

**Files:**
- Modify: `backend/app/repositories/entity_repo.py` (add `upsert_bloodlines`, `upsert_professions`, `upsert_churches`)
- Test: `backend/tests/test_layer3_persistence.py`

Follow the exact same TDD pattern as Tasks 1.4 and 2.2:
- Write tests that verify upsert methods can be called with schema objects
- Implement MERGE-based Cypher queries for each entity type
- Create appropriate STATE_CHANGED records for each
- Run full test suite to verify no regressions

**Commit:**
```bash
git commit -m "feat(v3): add Layer 3 entity persistence (Bloodline, Profession, Church)"
```

---

### Task 3.4: Wire New Passes into LangGraph

**Files:**
- Modify: `backend/app/services/extraction/__init__.py` (lines 437-489)
- Modify: `backend/app/agents/state.py` (add Layer 3 state fields)
- Modify: `backend/app/services/graph_builder.py` (call BlueBox + provenance + Layer 3 after extraction)

**Changes to state.py:**

Add after line 73:
```python
    # -- Layer 3 results (V3) --
    layer3: Layer3ExtractionResult
    provenance: ProvenanceResult
```

**Changes to graph_builder.py (`build_chapter_graph`):**

After `entity_repo.upsert_extraction_result(extraction_result)` (line 128), add:

```python
    # 5b. BlueBox grouping (V3 — Passe 0.5)
    paragraphs = await book_repo.get_paragraphs(book_id, chapter_number)
    if paragraphs:
        from app.services.extraction.bluebox import group_blue_boxes
        blue_boxes = group_blue_boxes(paragraphs)
        if blue_boxes:
            await entity_repo.upsert_blue_boxes(book_id, chapter_number, blue_boxes, batch_id)

    # 5c. Provenance extraction (V3 — Pass 2b)
    if extraction_result.systems.skills:
        from app.services.extraction.provenance import extract_provenance
        skills_acquired = [s.name for s in extraction_result.systems.skills]
        chapter_entities = {
            "items": [i.name for i in extraction_result.lore.items],
            "classes": [c.name for c in extraction_result.systems.classes],
            "bloodlines": [],  # Layer 3 TODO
        }
        prov_result = await extract_provenance(chapter.text, skills_acquired, chapter_entities)
        if prov_result.provenances:
            await entity_repo.upsert_grants_relations(prov_result.provenances, batch_id)
```

**Commit:**
```bash
git commit -m "feat(v3): wire BlueBox grouping and provenance into extraction pipeline"
```

---

## Phase 4: Frontend — Character Sheet

### Task 4.1: TypeScript API Client + Types

**Files:**
- Create: `frontend/lib/api/characters.ts`
- Modify: `frontend/lib/api/index.ts` (add re-exports)

Create `characters.ts` following the exact pattern from `graph.ts`:

```typescript
import { apiFetch } from "./client"

// ── Types ──────────────────────────────────────────────────────────────

export interface StatEntry {
  name: string
  value: number
  last_changed_chapter: number
}

export interface SkillSnapshot {
  name: string
  rank: string
  skill_type: string
  description: string
  acquired_chapter: number | null
}

// ... (all types from design doc Section 5.2)

// ── API Functions ──────────────────────────────────────────────────────

export function getCharacterStateAt(
  name: string,
  chapter: number,
  bookId?: string,
): Promise<CharacterStateSnapshot> {
  const params = new URLSearchParams()
  if (bookId) params.set("book_id", bookId)
  const q = params.toString() ? `?${params}` : ""
  return apiFetch(`/characters/${encodeURIComponent(name)}/at/${chapter}${q}`)
}

// ... (all 4 API functions)
```

Add to `index.ts`:
```typescript
export { getCharacterStateAt, getCharacterProgression, compareCharacterState, getCharacterSummary } from "./characters"
export type { CharacterStateSnapshot, CharacterSummary, CharacterComparison, ProgressionTimeline } from "./characters"
```

**Commit:**
```bash
git commit -m "feat(v3): add TypeScript API client for character state endpoints"
```

---

### Task 4.2: Character Sheet Page + Components

**Files:**
- Create: `frontend/app/(explorer)/characters/[name]/page.tsx`
- Create: `frontend/components/characters/chapter-slider.tsx`
- Create: `frontend/components/characters/character-header.tsx`
- Create: `frontend/components/characters/stat-grid.tsx`
- Create: `frontend/components/characters/skill-list.tsx`
- Create: `frontend/components/characters/changelog-tab.tsx`
- Modify: `frontend/components/shared/sidebar.tsx` (add Characters nav item)

> **IMPORTANT:** Use the `superpowers:frontend-design` skill when implementing this task.
> The design should follow the dark theme established in the existing codebase (slate-900 backgrounds, indigo/emerald/amber accents, monospace numbers).

The Character Sheet page follows the design from Section 6 of the design doc:
- ChapterSlider at top with debounced 300ms SWR fetch
- CharacterHeader with name, role, species, level badge
- 6-tab layout (Stats, Skills, Classes, Equipment, Titles, Changelog)
- CSR with SWR + `keepPreviousData: true`
- URL synced chapter param via `router.replace`

Sidebar change — add to Explorer section (in `sidebar.tsx` NAV_SECTIONS):
```typescript
{ href: "/characters", label: "Characters", icon: Users },
```

**Commit:**
```bash
git commit -m "feat(v3): add character sheet page with chapter slider and stat/skill tabs"
```

---

### Task 4.3: Reader Integration — Enhanced Character HoverCard

**Files:**
- Create: `frontend/components/reader/character-hover-content.tsx`
- Modify: `frontend/components/reader/annotated-text.tsx` (line 131-179, modify AnnotatedSpan)

When `annotation.entity_type === "Character"`, render `CharacterHoverContent` instead of the generic hover content. This component:
1. Calls `/characters/{name}/summary?chapter=N`
2. Shows: name, level badge, active class, top 3 skills, description (2 lines)
3. "Full Character Sheet" link at bottom

Pass `currentChapter` from the reader page context through to `AnnotatedSpan`.

**Commit:**
```bash
git commit -m "feat(v3): enhanced character hover cards in reader with live state"
```

---

## Phase 5: Polish + Re-extraction

### Task 5.1: Re-extraction Migration Script

**Files:**
- Modify: `backend/scripts/migrate_v2.py` → rename/extend to `migrate_v3.py`

Add V3-specific migration:
1. Delete all existing StateChange nodes (they'll be recreated)
2. Delete all BlueBox nodes
3. Delete all GRANTS_SKILL relationships
4. Re-run extraction for all books
5. `--dry-run` mode shows counts without deleting

**Commit:**
```bash
git commit -m "feat(v3): add V3 migration script for re-extraction"
```

---

### Task 5.2: Full Test Suite + Type Check

**Step 1: Run full backend tests**

```bash
cd E:/RAG && python -m uv run pytest backend/tests/ -v --ignore=backend/tests/test_embedding_pipeline.py --ignore=backend/tests/test_chat_service.py
```
Expected: All PASS

**Step 2: Run pyright**

```bash
cd E:/RAG && python -m uv run pyright backend/
```
Expected: 0 errors

**Step 3: Run ruff**

```bash
cd E:/RAG && python -m uv run ruff check backend/ --fix && python -m uv run ruff format backend/
```

**Step 4: Build frontend**

```bash
cd E:/RAG/frontend && npm run build
```
Expected: Build succeeds

**Step 5: Commit any fixes**

```bash
git commit -m "fix(v3): address lint, type, and test issues"
```

---

### Task 5.3: Code Review

> **IMPORTANT:** Use `superpowers:requesting-code-review` skill.

Review all V3 changes against the design doc. Verify:
- StateChange dual-write in all 6 upsert methods
- BlueBox grouping correctness
- Provenance confidence filtering
- API endpoint response schemas match frontend types
- No regressions in existing tests
- CLAUDE.md updated with V3 status

---

## Summary: 17 Tasks across 5 Phases

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1.1–1.5 | Neo4j schema, Pydantic schemas, CharacterStateRepo, dual-write, API endpoints |
| 2 | 2.1–2.5 | BlueBox grouping, BlueBox persistence, provenance schemas/prompt, provenance service, GRANTS persistence |
| 3 | 3.1–3.4 | Layer 3 schemas, Layer 3 regex, Layer 3 persistence, LangGraph wiring |
| 4 | 4.1–4.3 | TS API client, character sheet page + components, reader hover cards |
| 5 | 5.1–5.3 | Migration script, full test suite, code review |

Each task follows TDD: failing test → minimal implementation → verify pass → commit.
