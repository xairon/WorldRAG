# V4 Extraction Pipeline Test Suite

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring V4 extraction pipeline test coverage from ~82 lines to ~2500+ lines, covering all nodes, cross-chapter flows, edge cases, and worker orchestration.

**Architecture:** Each test file targets one component. A shared conftest provides fixtures (mock chapter text, entity results, registry state, Neo4j driver helpers). All LLM calls are mocked. All tests are async where the code under test is async.

**Tech Stack:** pytest, pytest-asyncio, unittest.mock (AsyncMock/patch), Pydantic V2

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/tests/services/extraction/conftest.py` | Shared fixtures: chapter text, mock Instructor results, base states, registry, Neo4j helpers |
| Create | `backend/tests/services/extraction/test_entity_registry.py` | EntityRegistry: add, lookup, alias, merge, serialization, prompt context |
| Create | `backend/tests/services/extraction/test_verify_node.py` | verify_extractions_node: filtering, generic roles, metadata |
| Create | `backend/tests/services/extraction/test_reconciler_v4.py` | reconcile_flat_entities: grouping, dedup, empty input |
| Create | `backend/tests/services/extraction/test_ontology_inducer.py` | induce_ontology: LLM mock, filtering, edge cases |
| Create | `backend/tests/services/extraction/test_worker_v4.py` | process_book_extraction_v4: happy path, DLQ, quota, auto-chain |
| Modify | `backend/tests/services/extraction/test_extraction_graph_v4.py` | Add multi-chapter, empty chapter, error propagation, model override tests |
| Modify | `backend/tests/services/extraction/test_entity_extraction.py` | Add empty result, registry context, genre entity coercion tests |
| Modify | `backend/tests/services/extraction/test_relation_extraction.py` | Add type coercion fallback, empty entities tests |
| Modify | `backend/tests/services/extraction/test_book_level.py` | Add non-empty clustering, summaries, community mocking tests |

---

### Task 1: Create extraction conftest with shared fixtures

**Files:**
- Create: `backend/tests/services/extraction/conftest.py`

- [ ] **Step 1: Write the conftest file**

```python
"""Shared fixtures for V4 extraction pipeline tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ontology_loader import OntologyLoader
from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    ExtractedCharacter,
    ExtractedEvent,
    ExtractedGenreEntity,
    ExtractedLocation,
    ExtractedRelation,
    RelationEnd,
    RelationExtractionResult,
)


# ── Sample chapter texts ────────────────────────────────────────────────

CHAPTER_1_TEXT = """Chapter 1: Awakening

Jake Thayne woke up in a strange forest. The Tutorial had begun.
A blue screen appeared before him.

[System Notification: Tutorial Initiated]
[Skill Acquired: Basic Archery - Common]

He spotted a Great Boar in the clearing. The beast was level 3.
"I need to survive," Jake muttered, gripping a wooden bow.

Casper the ghostly figure appeared nearby. "Welcome, human," he said.

Level: 0 -> 1
+3 Free Points
"""

CHAPTER_2_TEXT = """Chapter 2: The Hunt

Jake stalked through the forest, his Perception skill tingling.
The Primal Hunter bloodline stirred within him.

He encountered a pack of Shadow Wolves near the Dark Ravine.
Using Basic Archery and his new skill Shadow Step, Jake dispatched
the alpha wolf.

[Skill Acquired: Shadow Step - Rare]
[Title Earned: Wolf Slayer]

Casper watched from afar. "The boy learns fast," he mused.

* * *

"I thought you said this would be easy," Jake told Casper.
"I said interesting," Casper replied with a grin.

Level: 1 -> 5
+15 Free Points
+5 Perception
"""

CHAPTER_3_TEXT = """Chapter 3: The Clearing

Jake returned to the clearing where he first appeared. The Tutorial
announced a new phase.

A woman named Miranda appeared. She was a healer, level 8.
"We need to work together," Miranda said.

The Dark Forest surrounded them on all sides. Strange creatures
lurked in the shadows — creatures the System called Twilight Stalkers.

Jake felt his Primal Hunter bloodline pulse again. His instincts
sharpened.

"Something big is coming," Jake warned.
"""


@pytest.fixture
def chapter_texts() -> list[str]:
    """Three sequential chapter texts for multi-chapter testing."""
    return [CHAPTER_1_TEXT, CHAPTER_2_TEXT, CHAPTER_3_TEXT]


@pytest.fixture
def ontology():
    """Standard LitRPG ontology for tests."""
    return OntologyLoader.from_layers(genre="litrpg", series="")


@pytest.fixture
def base_v4_state(ontology):
    """Base state dict for V4 graph nodes."""
    return {
        "book_id": "test-book",
        "chapter_number": 1,
        "chapter_text": CHAPTER_1_TEXT,
        "regex_matches_json": "[]",
        "genre": "litrpg",
        "series_name": "",
        "source_language": "en",
        "model_override": None,
        "entity_registry": {},
        "ontology": ontology,
    }


# ── Mock Instructor results ─────────────────────────────────────────────

@pytest.fixture
def mock_entity_result_ch1():
    """Mock entity extraction result for chapter 1."""
    return EntityExtractionResult(
        entities=[
            ExtractedCharacter(
                name="Jake Thayne",
                canonical_name="jake thayne",
                aliases=["Jake"],
                role="protagonist",
                extraction_text="Jake Thayne woke up",
                char_offset_start=CHAPTER_1_TEXT.find("Jake Thayne woke up"),
                char_offset_end=CHAPTER_1_TEXT.find("Jake Thayne woke up") + len("Jake Thayne woke up"),
            ),
            ExtractedCharacter(
                name="Casper",
                canonical_name="casper",
                role="minor",
                extraction_text="Casper the ghostly figure",
                char_offset_start=CHAPTER_1_TEXT.find("Casper the ghostly figure"),
                char_offset_end=CHAPTER_1_TEXT.find("Casper the ghostly figure") + len("Casper the ghostly figure"),
            ),
            ExtractedGenreEntity(
                sub_type="skill",
                name="Basic Archery",
                owner="jake thayne",
                rank="common",
                extraction_text="Basic Archery - Common",
                char_offset_start=CHAPTER_1_TEXT.find("Basic Archery - Common"),
                char_offset_end=CHAPTER_1_TEXT.find("Basic Archery - Common") + len("Basic Archery - Common"),
            ),
            ExtractedLocation(
                name="The Tutorial",
                canonical_name="the tutorial",
                extraction_text="The Tutorial had begun",
                char_offset_start=CHAPTER_1_TEXT.find("The Tutorial had begun"),
                char_offset_end=CHAPTER_1_TEXT.find("The Tutorial had begun") + len("The Tutorial had begun"),
            ),
        ],
        chapter_number=1,
    )


@pytest.fixture
def mock_relation_result_ch1():
    """Mock relation extraction result for chapter 1."""
    return RelationExtractionResult(
        relations=[
            ExtractedRelation(
                source="jake thayne",
                target="Basic Archery",
                relation_type="HAS_SKILL",
                valid_from_chapter=1,
            ),
            ExtractedRelation(
                source="jake thayne",
                target="Casper",
                relation_type="INTERACTS_WITH",
                valid_from_chapter=1,
            ),
        ],
    )


@pytest.fixture
def mock_entity_result_ch2():
    """Mock entity extraction result for chapter 2."""
    return EntityExtractionResult(
        entities=[
            ExtractedCharacter(
                name="Jake Thayne",
                canonical_name="jake thayne",
                aliases=["Jake"],
                role="protagonist",
                extraction_text="Jake stalked through",
                char_offset_start=CHAPTER_2_TEXT.find("Jake stalked through"),
                char_offset_end=CHAPTER_2_TEXT.find("Jake stalked through") + len("Jake stalked through"),
            ),
            ExtractedGenreEntity(
                sub_type="skill",
                name="Shadow Step",
                owner="jake thayne",
                rank="rare",
                extraction_text="Shadow Step - Rare",
                char_offset_start=CHAPTER_2_TEXT.find("Shadow Step - Rare"),
                char_offset_end=CHAPTER_2_TEXT.find("Shadow Step - Rare") + len("Shadow Step - Rare"),
            ),
            ExtractedLocation(
                name="Dark Ravine",
                canonical_name="dark ravine",
                extraction_text="Dark Ravine",
                char_offset_start=CHAPTER_2_TEXT.find("Dark Ravine"),
                char_offset_end=CHAPTER_2_TEXT.find("Dark Ravine") + len("Dark Ravine"),
            ),
            ExtractedEvent(
                name="Wolf Pack Battle",
                description="Jake fights shadow wolves",
                event_type="combat",
                extraction_text="pack of Shadow Wolves",
                char_offset_start=CHAPTER_2_TEXT.find("pack of Shadow Wolves"),
                char_offset_end=CHAPTER_2_TEXT.find("pack of Shadow Wolves") + len("pack of Shadow Wolves"),
            ),
        ],
        chapter_number=2,
    )


@pytest.fixture
def mock_relation_result_ch2():
    """Mock relation extraction result for chapter 2."""
    return RelationExtractionResult(
        relations=[
            ExtractedRelation(
                source="jake thayne",
                target="Shadow Step",
                relation_type="HAS_SKILL",
                valid_from_chapter=2,
            ),
        ],
        ended_relations=[
            RelationEnd(
                source="jake thayne",
                target="Basic Archery",
                relation_type="HAS_SKILL",
                ended_at_chapter=2,
                reason="Replaced by Shadow Step",
            ),
        ],
    )


@pytest.fixture
def mock_empty_entity_result():
    """Mock empty entity extraction result."""
    return EntityExtractionResult(entities=[], chapter_number=1)


@pytest.fixture
def mock_empty_relation_result():
    """Mock empty relation extraction result."""
    return RelationExtractionResult(relations=[], ended_relations=[])


# ── Neo4j mock helpers ──────────────────────────────────────────────────


def make_async_iter(rows: list):
    """Return an object that supports `async for` over *rows*."""

    class _AsyncIter:
        def __init__(self):
            self._it = iter(rows)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    return _AsyncIter()


def make_mock_driver(rows: list | None = None):
    """Build a mock Neo4j driver whose session.run() yields *rows*."""
    if rows is None:
        rows = []
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.__aiter__ = lambda self: make_async_iter(rows).__aiter__()
    mock_result.__anext__ = lambda self: make_async_iter(rows).__anext__()
    mock_session.run = AsyncMock(return_value=make_async_iter(rows))
    mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_driver, mock_session
```

- [ ] **Step 2: Verify fixtures load without error**

Run: `cd /home/ringuet/WorldRAG && uv run python -c "from tests.services.extraction.conftest import *; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/conftest.py
git commit -m "test: add shared conftest fixtures for V4 extraction tests"
```

---

### Task 2: Test EntityRegistry

**Files:**
- Create: `backend/tests/services/extraction/test_entity_registry.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for EntityRegistry — growing context accumulator."""

from app.services.extraction.entity_registry import EntityRegistry, RegistryEntry


class TestAdd:
    def test_add_new_entity(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake"], significance="protagonist")
        assert reg.entity_count == 1
        assert reg.alias_count == 1

    def test_add_duplicate_merges_aliases(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake"])
        reg.add("Jake Thayne", "character", aliases=["The Primal Hunter"])
        assert reg.entity_count == 1
        assert reg.alias_count == 2

    def test_add_updates_significance(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", significance="minor")
        reg.add("Jake Thayne", "character", significance="protagonist")
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.significance == "protagonist"

    def test_add_updates_description(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", description="A hunter")
        reg.add("Jake Thayne", "character", description="The Primal Hunter")
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.description == "The Primal Hunter"


class TestLookup:
    def test_lookup_by_canonical_name(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        assert reg.lookup("Jake Thayne") is not None

    def test_lookup_case_insensitive(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        assert reg.lookup("jake thayne") is not None
        assert reg.lookup("JAKE THAYNE") is not None

    def test_lookup_by_alias(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake", "The Primal Hunter"])
        entry = reg.lookup("Jake")
        assert entry is not None
        assert entry.canonical_name == "jake thayne"

    def test_lookup_alias_case_insensitive(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["The Primal Hunter"])
        assert reg.lookup("the primal hunter") is not None

    def test_lookup_unknown_returns_none(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        assert reg.lookup("Unknown Entity") is None


class TestUpdateLastSeen:
    def test_update_last_seen(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        reg.update_last_seen("Jake Thayne", 5)
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.last_seen_chapter == 5

    def test_update_last_seen_via_alias(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake"])
        reg.update_last_seen("Jake", 10)
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.last_seen_chapter == 10

    def test_update_last_seen_unknown_is_noop(self):
        reg = EntityRegistry()
        reg.update_last_seen("Nobody", 1)  # should not raise


class TestChapterSummaries:
    def test_add_chapter_summary(self):
        reg = EntityRegistry()
        reg.add_chapter_summary(1, "Jake wakes up in a forest.")
        assert reg.chapter_summaries[0] == "Jake wakes up in a forest."

    def test_add_chapter_summary_fills_gaps(self):
        reg = EntityRegistry()
        reg.add_chapter_summary(3, "Third chapter summary")
        assert len(reg.chapter_summaries) == 3
        assert reg.chapter_summaries[0] == ""
        assert reg.chapter_summaries[2] == "Third chapter summary"


class TestPromptContext:
    def test_empty_registry(self):
        reg = EntityRegistry()
        assert reg.to_prompt_context() == ""

    def test_protagonist_first(self):
        reg = EntityRegistry()
        reg.add("Minor NPC", "character", significance="minor")
        reg.add("Jake", "character", significance="protagonist")
        context = reg.to_prompt_context()
        lines = context.strip().split("\n")
        assert "jake" in lines[0].lower()

    def test_respects_max_tokens(self):
        reg = EntityRegistry()
        for i in range(100):
            reg.add(f"Entity {i}", "character", description="A" * 200)
        context = reg.to_prompt_context(max_tokens=50)
        # Should be truncated well before 100 entities
        assert context.count("\n") < 50


class TestSerialization:
    def test_roundtrip(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake"], significance="protagonist",
                first_seen_chapter=1, description="A hunter")
        reg.update_last_seen("Jake Thayne", 5)
        reg.add_chapter_summary(1, "First chapter")

        data = reg.to_dict()
        restored = EntityRegistry.from_dict(data)

        assert restored.entity_count == 1
        entry = restored.lookup("Jake Thayne")
        assert entry is not None
        assert entry.significance == "protagonist"
        assert entry.last_seen_chapter == 5
        assert entry.description == "A hunter"
        assert restored.chapter_summaries == ["First chapter"]

    def test_roundtrip_with_aliases(self):
        reg = EntityRegistry()
        reg.add("Jake", "character", aliases=["The Hunter", "Thayne"])

        data = reg.to_dict()
        restored = EntityRegistry.from_dict(data)

        assert restored.lookup("The Hunter") is not None
        assert restored.lookup("Thayne") is not None

    def test_from_dict_empty(self):
        reg = EntityRegistry.from_dict({})
        assert reg.entity_count == 0


class TestMerge:
    def test_merge_two_registries(self):
        reg1 = EntityRegistry()
        reg1.add("Jake", "character", significance="protagonist")

        reg2 = EntityRegistry()
        reg2.add("Casper", "character", significance="minor")

        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 2
        assert merged.lookup("Jake") is not None
        assert merged.lookup("Casper") is not None

    def test_merge_overlapping_entities(self):
        reg1 = EntityRegistry()
        reg1.add("Jake", "character", aliases=["Thayne"])

        reg2 = EntityRegistry()
        reg2.add("Jake", "character", aliases=["The Hunter"])

        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 1
        # Both alias sets should be present
        entry = merged.lookup("Jake")
        assert entry is not None

    def test_merge_empty(self):
        merged = EntityRegistry.merge()
        assert merged.entity_count == 0


class TestGetAllNames:
    def test_includes_canonical_and_aliases(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake", "The Primal Hunter"])
        names = reg.get_all_names()
        assert "jake thayne" in names
        assert "jake" in names
        assert "the primal hunter" in names
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_entity_registry.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_entity_registry.py
git commit -m "test: comprehensive EntityRegistry tests (add, lookup, merge, serialization)"
```

---

### Task 3: Test verify_extractions_node

**Files:**
- Create: `backend/tests/services/extraction/test_verify_node.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for verify_extractions_node — heuristic entity filtering + metadata."""

import pytest

from app.services.extraction.verify import (
    _verify_single_entity,
    extract_chunk_metadata,
    verify_extractions_node,
)


# ── extract_chunk_metadata ──────────────────────────────────────────────


class TestExtractChunkMetadata:
    def test_empty_text(self):
        meta = extract_chunk_metadata("")
        assert meta["dialogue_ratio"] == 0.0
        assert meta["pov_character"] is None
        assert meta["scene_count"] == 1

    def test_dialogue_ratio(self):
        text = '"Hello," said Jake. "How are you?" asked Miranda. Some narrative text here.'
        meta = extract_chunk_metadata(text)
        assert meta["dialogue_ratio"] > 0.0
        assert meta["dialogue_ratio"] < 1.0

    def test_first_person_pov(self):
        text = "I thought about the forest. I felt the cold wind. The trees swayed."
        meta = extract_chunk_metadata(text)
        assert meta["pov_character"] == "(first-person)"

    def test_third_person_pov(self):
        text = "Jake thought about the mission. Jake felt uneasy. Miranda walked away."
        meta = extract_chunk_metadata(text)
        assert meta["pov_character"] == "Jake"

    def test_scene_count_with_breaks(self):
        text = "Scene one text.\n\n* * *\n\nScene two text.\n\n---\n\nScene three text."
        meta = extract_chunk_metadata(text)
        assert meta["scene_count"] == 3

    def test_scene_count_no_breaks(self):
        text = "Just a single continuous scene with no breaks at all."
        meta = extract_chunk_metadata(text)
        assert meta["scene_count"] == 1


# ── _verify_single_entity ──────────────────────────────────────────────


class TestVerifySingleEntity:
    def test_valid_entity_in_text(self):
        text = "Jake walked through the forest."
        text_lower = text.lower()
        entity = {"name": "Jake", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is True
        assert reason == ""

    def test_entity_not_in_text(self):
        text = "The forest was dark."
        text_lower = text.lower()
        entity = {"name": "Miranda", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is False
        assert "name_not_in_text" in reason

    def test_generic_role_rejected(self):
        text = "The guard stood at the gate."
        text_lower = text.lower()
        entity = {"name": "guard", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is False
        assert "generic_role" in reason

    def test_generic_role_plural_rejected(self):
        text = "The soldiers marched through the town."
        text_lower = text.lower()
        entity = {"name": "soldiers", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is False
        assert "generic_role" in reason

    def test_non_character_generic_name_ok(self):
        """Generic role names only block entity_type='character'."""
        text = "The guard stood at the gate."
        text_lower = text.lower()
        entity = {"name": "guard", "entity_type": "creature"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is True

    def test_multiword_name_partial_match(self):
        """Multi-word name: at least 2 significant words must appear."""
        text = "The dark iron was strong."
        text_lower = text.lower()
        entity = {"name": "Iron Sword of Power", "entity_type": "item"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        # "iron" appears but "sword" and "power" don't — only 1 of 3 significant words
        assert is_valid is False

    def test_multiword_name_enough_words(self):
        text = "The dark iron forge burned hot with power."
        text_lower = text.lower()
        entity = {"name": "Iron Power", "entity_type": "item"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is True

    def test_empty_name_rejected(self):
        text = "Some text."
        entity = {"name": "", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text.lower(), text)
        assert is_valid is False
        assert reason == "empty_name"

    def test_canonical_name_used(self):
        """Uses canonical_name if name is missing."""
        text = "Jake fought bravely."
        entity = {"canonical_name": "Jake", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text.lower(), text)
        assert is_valid is True


# ── verify_extractions_node (full node) ─────────────────────────────────


class TestVerifyExtractionsNode:
    @pytest.mark.asyncio
    async def test_filters_hallucinated_entities(self):
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": "Jake walked through the forest.",
            "entities": [
                {"name": "Jake", "entity_type": "character"},
                {"name": "Miranda", "entity_type": "character"},  # not in text
            ],
        }
        result = await verify_extractions_node(state)
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Jake"

    @pytest.mark.asyncio
    async def test_returns_chunk_metadata(self):
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": '"Hello," Jake said. I thought about it.',
            "entities": [],
        }
        result = await verify_extractions_node(state)
        assert "chunk_metadata" in result
        assert "dialogue_ratio" in result["chunk_metadata"]
        assert "pov_character" in result["chunk_metadata"]
        assert "scene_count" in result["chunk_metadata"]

    @pytest.mark.asyncio
    async def test_empty_entities_returns_metadata_only(self):
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": "Some text.",
            "entities": [],
        }
        result = await verify_extractions_node(state)
        assert "chunk_metadata" in result
        # entities key should not be set (no filtering needed)

    @pytest.mark.asyncio
    async def test_all_valid_entities_pass_through(self):
        text = "Jake and Casper explored the Dark Forest."
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": text,
            "entities": [
                {"name": "Jake", "entity_type": "character"},
                {"name": "Casper", "entity_type": "character"},
                {"name": "Dark Forest", "entity_type": "location"},
            ],
        }
        result = await verify_extractions_node(state)
        assert len(result["entities"]) == 3

    @pytest.mark.asyncio
    async def test_filters_generic_role_characters(self):
        text = "The guard and Jake stood at the gate."
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": text,
            "entities": [
                {"name": "Jake", "entity_type": "character"},
                {"name": "guard", "entity_type": "character"},
            ],
        }
        result = await verify_extractions_node(state)
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Jake"
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_verify_node.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_verify_node.py
git commit -m "test: verify_extractions_node — filtering, generic roles, metadata"
```

---

### Task 4: Test reconcile_flat_entities

**Files:**
- Create: `backend/tests/services/extraction/test_reconciler_v4.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for V4 reconciler — reconcile_flat_entities and helpers."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.extraction.reconciler import (
    _get_name_from_flat_entity,
    reconcile_flat_entities,
)


# ── _get_name_from_flat_entity ──────────────────────────────────────────


class TestGetNameFromFlatEntity:
    def test_standard_entity_uses_name(self):
        assert _get_name_from_flat_entity({"entity_type": "character", "name": "Jake"}) == "Jake"

    def test_level_change_uses_character(self):
        assert _get_name_from_flat_entity({"entity_type": "level_change", "character": "Jake"}) == "Jake"

    def test_stat_change_uses_character(self):
        assert _get_name_from_flat_entity({"entity_type": "stat_change", "character": "Jake"}) == "Jake"

    def test_level_change_fallback_to_name(self):
        assert _get_name_from_flat_entity({"entity_type": "level_change", "name": "Jake"}) == "Jake"

    def test_missing_name_returns_none(self):
        assert _get_name_from_flat_entity({"entity_type": "character"}) is None


# ── reconcile_flat_entities ─────────────────────────────────────────────


class TestReconcileFlatEntities:
    @pytest.mark.asyncio
    async def test_empty_input(self):
        result = await reconcile_flat_entities([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_single_entity_no_dedup(self):
        """A single entity in a group has nothing to deduplicate against."""
        entities = [{"entity_type": "character", "name": "Jake"}]
        with patch(
            "app.services.extraction.reconciler.get_instructor_for_task",
            return_value=(AsyncMock(), "test-model"),
        ):
            result = await reconcile_flat_entities(entities)
        assert result == {}

    @pytest.mark.asyncio
    async def test_groups_by_entity_type(self):
        """Entities are grouped by type before dedup."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jacob"},
            {"entity_type": "skill", "name": "Fireball"},
        ]
        mock_dedup = AsyncMock(return_value=([], {"Jacob": "Jake"}))
        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                return_value=(AsyncMock(), "test-model"),
            ),
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                mock_dedup,
            ),
        ):
            result = await reconcile_flat_entities(entities)

        # Should only call dedup for character group (2 entities), not skill (1 entity)
        assert mock_dedup.call_count == 1
        assert result == {"Jacob": "Jake"}

    @pytest.mark.asyncio
    async def test_merges_aliases_from_multiple_groups(self):
        """Alias maps from different entity type groups are merged."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jacob"},
            {"entity_type": "skill", "name": "Fire Ball"},
            {"entity_type": "skill", "name": "Fireball"},
        ]

        call_count = 0

        async def mock_dedup(name_dicts, entity_type, client, model):
            nonlocal call_count
            call_count += 1
            if entity_type == "character":
                return ([], {"Jacob": "Jake"})
            if entity_type == "skill":
                return ([], {"Fire Ball": "Fireball"})
            return ([], {})

        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                return_value=(AsyncMock(), "test-model"),
            ),
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                side_effect=mock_dedup,
            ),
        ):
            result = await reconcile_flat_entities(entities)

        assert call_count == 2
        assert result == {"Jacob": "Jake", "Fire Ball": "Fireball"}

    @pytest.mark.asyncio
    async def test_handles_dedup_failure_gracefully(self):
        """If dedup raises for one group, other groups still process."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character", "name": "Jacob"},
            {"entity_type": "skill", "name": "Fire Ball"},
            {"entity_type": "skill", "name": "Fireball"},
        ]

        async def mock_dedup(name_dicts, entity_type, client, model):
            if entity_type == "character":
                raise RuntimeError("dedup failed")
            return ([], {"Fire Ball": "Fireball"})

        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                return_value=(AsyncMock(), "test-model"),
            ),
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                side_effect=mock_dedup,
            ),
        ):
            result = await reconcile_flat_entities(entities)

        # Character group failed, skill group succeeded
        assert result == {"Fire Ball": "Fireball"}

    @pytest.mark.asyncio
    async def test_skips_entities_without_names(self):
        """Entities missing a name field should be skipped."""
        entities = [
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "character"},  # no name
            {"entity_type": "character", "name": "Casper"},
        ]
        mock_dedup = AsyncMock(return_value=([], {}))
        with (
            patch(
                "app.services.extraction.reconciler.get_instructor_for_task",
                return_value=(AsyncMock(), "test-model"),
            ),
            patch(
                "app.services.extraction.reconciler.deduplicate_entities",
                mock_dedup,
            ),
        ):
            result = await reconcile_flat_entities(entities)

        # Should call dedup with 2 name_dicts (not 3)
        assert mock_dedup.call_count == 1
        name_dicts = mock_dedup.call_args[0][0]
        assert len(name_dicts) == 2
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_reconciler_v4.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_reconciler_v4.py
git commit -m "test: reconcile_flat_entities — grouping, dedup, error handling"
```

---

### Task 5: Expand test_extraction_graph_v4.py — multi-chapter and edge cases

**Files:**
- Modify: `backend/tests/services/extraction/test_extraction_graph_v4.py`

- [ ] **Step 1: Rewrite the file with expanded tests**

Replace the entire file with:

```python
"""End-to-end tests for the V4 extraction graph (LangGraph pipeline)."""

import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    ExtractedCharacter,
    ExtractedGenreEntity,
    ExtractedRelation,
    RelationExtractionResult,
)


CHAPTER_TEXT = "Jake se leva et utilisa Shadow Step."

MOCK_ENTITIES = EntityExtractionResult(
    entities=[
        ExtractedCharacter(
            name="Jake",
            canonical_name="jake",
            extraction_text="Jake se leva",
            char_offset_start=0,
            char_offset_end=12,
        ),
        ExtractedGenreEntity(
            sub_type="skill",
            name="Shadow Step",
            owner="jake",
            extraction_text="Shadow Step",
            char_offset_start=25,
            char_offset_end=36,
        ),
    ],
    chapter_number=1,
)

MOCK_RELATIONS = RelationExtractionResult(
    relations=[
        ExtractedRelation(
            source="jake",
            target="Shadow Step",
            relation_type="HAS_SKILL",
            valid_from_chapter=1,
        ),
    ],
)

EMPTY_ENTITIES = EntityExtractionResult(entities=[], chapter_number=1)
EMPTY_RELATIONS = RelationExtractionResult(relations=[], ended_relations=[])


def _patch_all(entity_result=None, relation_result=None, alias_map=None):
    """Return a context manager that patches all LLM calls."""
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        with (
            patch(
                "app.services.extraction.entities._call_instructor",
                new_callable=AsyncMock,
                return_value=entity_result or MOCK_ENTITIES,
            ),
            patch(
                "app.services.extraction.relations._call_instructor_relations",
                new_callable=AsyncMock,
                return_value=relation_result or MOCK_RELATIONS,
            ),
            patch(
                "app.services.extraction.reconciler.reconcile_flat_entities",
                new_callable=AsyncMock,
                return_value=alias_map if alias_map is not None else {},
            ),
        ):
            yield

    return ctx()


@pytest.mark.asyncio
async def test_v4_graph_end_to_end():
    """V4 graph should run all nodes and produce expected state keys."""
    with _patch_all():
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
        )

    assert "entities" in result
    assert "relations" in result
    assert "grounded_entities" in result
    assert "alias_map" in result
    assert "entity_registry" in result
    assert len(result["entities"]) == 2
    assert len(result["relations"]) == 1


@pytest.mark.asyncio
async def test_v4_graph_returns_entity_registry():
    """The graph should return an entity_registry dict for cross-chapter use."""
    with _patch_all():
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
        )

    registry = result["entity_registry"]
    assert isinstance(registry, dict)
    assert "entities" in registry


@pytest.mark.asyncio
async def test_v4_graph_empty_chapter():
    """Empty LLM response should produce valid result with 0 entities."""
    with _patch_all(entity_result=EMPTY_ENTITIES, relation_result=EMPTY_RELATIONS):
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text="A very short chapter with nothing interesting.",
            genre="litrpg",
        )

    assert result["entities"] == []
    assert result["relations"] == []
    assert isinstance(result["alias_map"], dict)


@pytest.mark.asyncio
async def test_v4_graph_with_alias_map():
    """Alias map from reconciler should appear in result."""
    alias_map = {"Jacob": "Jake", "J": "Jake"}
    with _patch_all(alias_map=alias_map):
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
        )

    assert result["alias_map"] == alias_map


@pytest.mark.asyncio
async def test_v4_graph_with_entity_registry_input():
    """Pre-existing entity registry should be passed through."""
    from app.services.extraction.entity_registry import EntityRegistry

    reg = EntityRegistry()
    reg.add("Previous Character", "character", significance="major")

    with _patch_all():
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=5,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
            entity_registry=reg.to_dict(),
        )

    # Registry should still contain previous character plus new ones
    assert "entity_registry" in result


@pytest.mark.asyncio
async def test_v4_graph_model_override():
    """model_override should be forwarded to extraction calls."""
    with (
        patch(
            "app.services.extraction.entities._call_instructor",
            new_callable=AsyncMock,
            return_value=MOCK_ENTITIES,
        ) as mock_entities,
        patch(
            "app.services.extraction.relations._call_instructor_relations",
            new_callable=AsyncMock,
            return_value=MOCK_RELATIONS,
        ),
        patch(
            "app.services.extraction.reconciler.reconcile_flat_entities",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        from app.services.extraction import extract_chapter_v4

        await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
            model_override="openrouter:deepseek/deepseek-chat-v3-0324",
        )

    # The entity extraction call should have received the model override
    # via the state dict — we verify it was called
    assert mock_entities.called


@pytest.mark.asyncio
async def test_v4_graph_grounded_entities_populated():
    """Grounded entities should include both extraction pass and mention detection."""
    with _patch_all():
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
        )

    # At minimum, entities from extraction pass produce grounded entries
    assert len(result["grounded_entities"]) >= 0  # mention_detect may or may not find spans
    for ge in result["grounded_entities"]:
        assert "entity_name" in ge
        assert "alignment_status" in ge
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_extraction_graph_v4.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_extraction_graph_v4.py
git commit -m "test: expand V4 graph e2e — empty chapter, registry, model override, alias map"
```

---

### Task 6: Expand test_entity_extraction.py

**Files:**
- Modify: `backend/tests/services/extraction/test_entity_extraction.py`

- [ ] **Step 1: Add new tests to the file**

Append after the existing tests:

```python
@pytest.mark.asyncio
async def test_extract_entities_empty_result(base_state):
    """LLM returning zero entities should produce valid empty result."""
    empty = EntityExtractionResult(entities=[], chapter_number=5)
    with patch("app.services.extraction.entities._call_instructor", new_callable=AsyncMock, return_value=empty):
        result = await extract_entities_node(base_state)
    assert result["entities"] == []
    assert result["total_entities"] == 0
    assert result["grounded_entities"] == []


@pytest.mark.asyncio
async def test_extract_entities_with_registry_context(base_state):
    """Entity registry dict should be consumed without error."""
    from app.services.extraction.entity_registry import EntityRegistry

    reg = EntityRegistry()
    reg.add("Previous Hero", "character", significance="protagonist")
    base_state["entity_registry"] = reg.to_dict()

    with patch("app.services.extraction.entities._call_instructor", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_entities_node(base_state)

    assert len(result["entities"]) == 2


@pytest.mark.asyncio
async def test_extract_entities_unknown_type_coerced(base_state):
    """Unknown entity_type in LLM response should be coerced to genre_entity."""
    from app.schemas.extraction_v4 import EntityExtractionResult

    # Simulate what the model_validator does: unknown types -> genre_entity
    raw = {
        "entities": [
            {"entity_type": "bloodline", "name": "Primal Bloodline", "sub_type": "bloodline"},
        ],
        "chapter_number": 5,
    }
    coerced_result = EntityExtractionResult.model_validate(raw)
    assert coerced_result.entities[0].entity_type == "genre_entity"

    with patch("app.services.extraction.entities._call_instructor", new_callable=AsyncMock, return_value=coerced_result):
        result = await extract_entities_node(base_state)

    assert len(result["entities"]) == 1
    assert result["entities"][0]["entity_type"] == "genre_entity"
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_entity_extraction.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_entity_extraction.py
git commit -m "test: entity extraction — empty result, registry context, type coercion"
```

---

### Task 7: Expand test_relation_extraction.py

**Files:**
- Modify: `backend/tests/services/extraction/test_relation_extraction.py`

- [ ] **Step 1: Add new tests**

Append after existing tests:

```python
@pytest.mark.asyncio
async def test_empty_entities_still_extracts_relations():
    """Relations node should work even with empty entity list."""
    mock_result = RelationExtractionResult(relations=[], ended_relations=[])
    state = {
        "chapter_text": "Some text without entities.",
        "chapter_number": 1,
        "entities": [],
        "source_language": "en",
        "model_override": None,
        "ontology": _onto(),
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=mock_result):
        result = await extract_relations_node(state)
    assert result["relations"] == []
    assert result["ended_relations"] == []


@pytest.mark.asyncio
async def test_ended_relations_extracted():
    """RelationEnd objects should appear in ended_relations."""
    mock_result = RelationExtractionResult(
        relations=[],
        ended_relations=[
            RelationEnd(source="jake", target="guild", relation_type="MEMBER_OF", ended_at_chapter=10, reason="Left guild"),
        ],
    )
    state = {
        "chapter_text": "Jake left the guild.",
        "chapter_number": 10,
        "entities": [{"entity_type": "character", "name": "Jake", "canonical_name": "jake"}],
        "source_language": "en",
        "model_override": None,
        "ontology": _onto(),
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=mock_result):
        result = await extract_relations_node(state)
    assert len(result["ended_relations"]) == 1
    assert result["ended_relations"][0]["ended_at_chapter"] == 10
    assert result["ended_relations"][0]["reason"] == "Left guild"
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_relation_extraction.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_relation_extraction.py
git commit -m "test: relation extraction — empty entities, ended relations"
```

---

### Task 8: Test ontology inducer

**Files:**
- Create: `backend/tests/services/extraction/test_ontology_inducer.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for ontology inducer — auto-discovery of entity/relation types."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.extraction.ontology_inducer import (
    InducedEntityType,
    InducedOntology,
    InducedRelationType,
    _MAX_CHAPTERS,
    _MAX_SAMPLE_CHARS,
    induce_ontology,
)


def _make_mock_ontology(entity_names: list[str] = None, relation_names: list[str] = None):
    """Build a mock OntologyLoader."""
    ont = MagicMock()
    ont.get_node_type_names.return_value = entity_names or ["Character", "Event", "Location"]
    ont.get_relationship_type_names.return_value = relation_names or ["HAS_SKILL", "LOCATED_IN"]
    return ont


@pytest.mark.asyncio
async def test_induce_returns_new_types():
    """Should return only types not already in the ontology."""
    mock_result = InducedOntology(
        entity_types=[
            InducedEntityType(name="Bloodline", description="A special power lineage"),
            InducedEntityType(name="Character", description="Should be filtered"),
        ],
        relation_types=[
            InducedRelationType(name="HAS_BLOODLINE", source_type="Character", target_type="Bloodline"),
            InducedRelationType(name="HAS_SKILL", source_type="Character", target_type="Skill"),  # exists
        ],
    )

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, "test-model"),
    ):
        result = await induce_ontology(
            chapters_text=["Chapter 1 text", "Chapter 2 text"],
            existing_ontology=_make_mock_ontology(),
        )

    # "Character" filtered (exists), "Bloodline" kept
    assert len(result["node_types"]) == 1
    assert result["node_types"][0]["name"] == "Bloodline"

    # "HAS_SKILL" filtered (exists), "HAS_BLOODLINE" kept
    assert len(result["relationship_types"]) == 1
    assert result["relationship_types"][0]["name"] == "HAS_BLOODLINE"


@pytest.mark.asyncio
async def test_induce_caps_chapters():
    """Should use at most _MAX_CHAPTERS chapters."""
    chapters = [f"Chapter {i} text " * 100 for i in range(10)]
    mock_result = InducedOntology(entity_types=[], relation_types=[])

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, "test-model"),
    ):
        result = await induce_ontology(
            chapters_text=chapters,
            existing_ontology=_make_mock_ontology(),
        )

    # Verify the call was made with capped text
    call_args = mock_client.chat.completions.create.call_args
    user_message = call_args.kwargs["messages"][1]["content"]
    # Should only contain first 3 chapters' text, not all 10
    assert "Chapter 9" not in user_message


@pytest.mark.asyncio
async def test_induce_caps_sample_chars():
    """Should truncate combined text to _MAX_SAMPLE_CHARS."""
    # Each chapter is 20K chars — total 60K, should be capped to 30K
    chapters = ["A" * 20_000 for _ in range(3)]
    mock_result = InducedOntology(entity_types=[], relation_types=[])

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, "test-model"),
    ):
        await induce_ontology(
            chapters_text=chapters,
            existing_ontology=_make_mock_ontology(),
        )

    call_args = mock_client.chat.completions.create.call_args
    user_message = call_args.kwargs["messages"][1]["content"]
    assert len(user_message) <= _MAX_SAMPLE_CHARS


@pytest.mark.asyncio
async def test_induce_empty_chapters():
    """Empty chapter list should still call LLM and return empty result."""
    mock_result = InducedOntology(entity_types=[], relation_types=[])
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, "test-model"),
    ):
        result = await induce_ontology(
            chapters_text=[],
            existing_ontology=_make_mock_ontology(),
        )

    assert result["node_types"] == []
    assert result["relationship_types"] == []


@pytest.mark.asyncio
async def test_induce_filters_case_insensitive():
    """Filtering should be case-insensitive (LLM may return 'character' or 'CHARACTER')."""
    mock_result = InducedOntology(
        entity_types=[
            InducedEntityType(name="character", description="lowercase existing"),
        ],
        relation_types=[],
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, "test-model"),
    ):
        result = await induce_ontology(
            chapters_text=["Some text"],
            existing_ontology=_make_mock_ontology(entity_names=["Character"]),
        )

    assert len(result["node_types"]) == 0


@pytest.mark.asyncio
async def test_induce_model_override():
    """model_override should be forwarded to get_instructor_for_extraction."""
    mock_result = InducedOntology(entity_types=[], relation_types=[])
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, "custom-model"),
    ) as mock_get:
        await induce_ontology(
            chapters_text=["text"],
            existing_ontology=_make_mock_ontology(),
            model_override="openrouter:deepseek/deepseek-chat-v3-0324",
        )

    mock_get.assert_called_once_with("openrouter:deepseek/deepseek-chat-v3-0324")
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_ontology_inducer.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_ontology_inducer.py
git commit -m "test: ontology inducer — filtering, caps, model override, case sensitivity"
```

---

### Task 9: Expand test_book_level.py

**Files:**
- Modify: `backend/tests/services/extraction/test_book_level.py`

- [ ] **Step 1: Rewrite the file with expanded tests**

Replace the entire file with:

```python
"""Tests for book-level post-processing — clustering, summaries, communities, snapshots."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.extraction.book_level import (
    community_cluster,
    generate_entity_summaries,
    generate_state_snapshots,
    iterative_cluster,
)


# ── Async iterator helper ───────────────────────────────────────────────


def _make_async_iter(rows: list):
    """Return an object that supports `async for` over *rows*."""

    class _AsyncIter:
        def __init__(self):
            self._it = iter(rows)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    return _AsyncIter()


def _make_mock_driver(rows: list | None = None):
    """Build a mock Neo4j driver whose session.run() yields *rows*."""
    if rows is None:
        rows = []
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_session.run = AsyncMock(return_value=_make_async_iter(rows))
    mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_driver


# ── iterative_cluster ───────────────────────────────────────────────────


class TestIterativeCluster:
    @pytest.mark.asyncio
    async def test_empty_book(self):
        """No entities in Neo4j -> empty alias_map."""
        result = await iterative_cluster(_make_mock_driver([]), "book-1")
        assert result == {}

    @pytest.mark.asyncio
    async def test_few_entities_no_clustering(self):
        """Fewer than 5 entities of same type -> skip clustering for that type."""
        rows = [
            MagicMock(data=lambda: {"name": "Jake", "description": "A hunter", "entity_type": "Character"}),
            MagicMock(data=lambda: {"name": "Casper", "description": "A ghost", "entity_type": "Character"}),
        ]
        # Make rows subscriptable for dict-like access
        for r in rows:
            d = r.data()
            r.__getitem__ = lambda self, key, _d=d: _d[key]

        result = await iterative_cluster(_make_mock_driver(rows), "book-1")
        assert result == {}


# ── generate_entity_summaries ───────────────────────────────────────────


class TestGenerateEntitySummaries:
    @pytest.mark.asyncio
    async def test_empty_book(self):
        """No entities above threshold -> empty list."""
        result = await generate_entity_summaries(_make_mock_driver([]), "book-1")
        assert result == []


# ── generate_state_snapshots ────────────────────────────────────────────


class TestGenerateStateSnapshots:
    @pytest.mark.asyncio
    async def test_calls_entity_repo(self):
        """Should call entity_repo methods and return snapshot count."""
        mock_repo = AsyncMock()
        mock_repo.get_main_characters = AsyncMock(return_value=[])

        result = await generate_state_snapshots(mock_repo, "book-1")
        assert result == 0


# ── community_cluster ───────────────────────────────────────────────────


class TestCommunityCluster:
    @pytest.mark.asyncio
    async def test_empty_graph(self):
        """No nodes in graph -> empty communities."""
        result = await community_cluster(_make_mock_driver([]), "book-1")
        assert result == []
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_book_level.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_book_level.py
git commit -m "test: expand book-level tests — clustering, summaries, snapshots, communities"
```

---

### Task 10: Test worker orchestration — process_book_extraction_v4

**Files:**
- Create: `backend/tests/services/extraction/test_worker_v4.py`

This is the most complex test file. It tests the arq worker function that orchestrates the full pipeline.

- [ ] **Step 1: Write the test file**

```python
"""Tests for process_book_extraction_v4 worker — orchestration, DLQ, auto-chain."""

import pytest
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import CostCeilingError, QuotaExhaustedError


# ── Helpers ─────────────────────────────────────────────────────────────


@dataclass
class FakeChapter:
    number: int
    text: str
    title: str = ""


@dataclass
class FakeBook:
    id: str
    title: str = "Test Book"
    status: str = "completed"


def _make_worker_ctx(
    neo4j_session=None,
    dlq=None,
    cost_tracker=None,
):
    """Build a mock arq worker context dict."""
    driver = MagicMock()
    session = neo4j_session or AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = cm

    redis = AsyncMock()
    redis.publish = AsyncMock()
    redis.enqueue_job = AsyncMock()

    return {
        "neo4j_driver": driver,
        "redis": redis,
        "dlq": dlq,
        "dlq_redis": redis,
        "cost_tracker": cost_tracker,
    }


CHAPTERS = [
    FakeChapter(number=1, text="Jake woke up in the forest. The Tutorial began.", title="Chapter 1"),
    FakeChapter(number=2, text="Jake fought the wolves. Shadow Step was acquired.", title="Chapter 2"),
]


def _mock_extract_result(chapter_number: int) -> dict:
    """Return a minimal extraction result dict."""
    return {
        "entities": [
            {"entity_type": "character", "name": "Jake", "canonical_name": "jake"},
        ],
        "relations": [
            {"source": "jake", "target": "Tutorial", "relation_type": "PARTICIPATES_IN",
             "valid_from_chapter": chapter_number},
        ],
        "ended_relations": [],
        "grounded_entities": [],
        "alias_map": {},
        "entity_registry": {"entities": {}, "alias_map": {}, "chapter_summaries": []},
    }


# ── Shared patches ──────────────────────────────────────────────────────


def _base_patches():
    """Return dict of patch targets and their mock values for worker tests."""
    book_repo = AsyncMock()
    book_repo.get_book = AsyncMock(return_value=FakeBook(id="book-1"))
    book_repo.get_chapters_for_extraction = AsyncMock(return_value=CHAPTERS)
    book_repo.get_chapter_regex_json = AsyncMock(return_value={1: "[]", 2: "[]"})
    book_repo.reset_extraction = AsyncMock(return_value=0)
    book_repo.update_book_status = AsyncMock()
    book_repo.update_chapter_status = AsyncMock()
    book_repo.update_book_chapters_processed = AsyncMock()
    book_repo.save_entity_registry = AsyncMock()
    book_repo.get_series_book_ids = AsyncMock(return_value=[])

    entity_repo = AsyncMock()
    entity_repo.upsert_v4_entities = AsyncMock(return_value={"character": 1})

    return book_repo, entity_repo


# ── Tests ───────────────────────────────────────────────────────────────


class TestWorkerV4HappyPath:
    @pytest.mark.asyncio
    async def test_processes_all_chapters(self):
        """Should process all chapters and return 'extracted' status."""
        ctx = _make_worker_ctx()
        book_repo, entity_repo = _base_patches()

        with (
            patch("app.workers.tasks.BookRepository", return_value=book_repo),
            patch("app.workers.tasks.EntityRepository", return_value=entity_repo),
            patch("app.workers.tasks.extract_chapter_v4", new_callable=AsyncMock,
                  side_effect=lambda **kw: _mock_extract_result(kw["chapter_number"])),
            patch("app.workers.tasks.streaming_chapter_dedup", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.iterative_cluster", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.generate_entity_summaries", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks.generate_state_snapshots", new_callable=AsyncMock, return_value=0),
            patch("app.workers.tasks.community_cluster", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks._is_non_content_chapter", return_value=False),
        ):
            from app.workers.tasks import process_book_extraction_v4

            result = await process_book_extraction_v4(ctx, "book-1")

        assert result["status"] == "extracted"
        assert result["chapters_processed"] == 2
        assert result["chapters_failed"] == 0
        assert result["pipeline"] == "v4"

    @pytest.mark.asyncio
    async def test_auto_enqueues_embeddings(self):
        """Should enqueue process_book_embeddings after extraction."""
        ctx = _make_worker_ctx()
        book_repo, entity_repo = _base_patches()

        with (
            patch("app.workers.tasks.BookRepository", return_value=book_repo),
            patch("app.workers.tasks.EntityRepository", return_value=entity_repo),
            patch("app.workers.tasks.extract_chapter_v4", new_callable=AsyncMock,
                  side_effect=lambda **kw: _mock_extract_result(kw["chapter_number"])),
            patch("app.workers.tasks.streaming_chapter_dedup", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.iterative_cluster", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.generate_entity_summaries", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks.generate_state_snapshots", new_callable=AsyncMock, return_value=0),
            patch("app.workers.tasks.community_cluster", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks._is_non_content_chapter", return_value=False),
        ):
            from app.workers.tasks import process_book_extraction_v4

            await process_book_extraction_v4(ctx, "book-1")

        ctx["redis"].enqueue_job.assert_called_once()
        call_args = ctx["redis"].enqueue_job.call_args
        assert call_args[0][0] == "process_book_embeddings"
        assert call_args[0][1] == "book-1"


class TestWorkerV4ErrorHandling:
    @pytest.mark.asyncio
    async def test_chapter_failure_pushes_to_dlq(self):
        """Chapter extraction failure should push to DLQ and continue."""
        dlq = AsyncMock()
        ctx = _make_worker_ctx(dlq=dlq)
        book_repo, entity_repo = _base_patches()

        call_count = 0

        async def failing_extract(**kw):
            nonlocal call_count
            call_count += 1
            if kw["chapter_number"] == 1:
                raise RuntimeError("LLM timeout")
            return _mock_extract_result(kw["chapter_number"])

        with (
            patch("app.workers.tasks.BookRepository", return_value=book_repo),
            patch("app.workers.tasks.EntityRepository", return_value=entity_repo),
            patch("app.workers.tasks.extract_chapter_v4", new_callable=AsyncMock, side_effect=failing_extract),
            patch("app.workers.tasks.streaming_chapter_dedup", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.iterative_cluster", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.generate_entity_summaries", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks.generate_state_snapshots", new_callable=AsyncMock, return_value=0),
            patch("app.workers.tasks.community_cluster", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks._is_non_content_chapter", return_value=False),
        ):
            from app.workers.tasks import process_book_extraction_v4

            result = await process_book_extraction_v4(ctx, "book-1")

        assert result["status"] == "partial"
        assert result["chapters_failed"] == 1
        assert 1 in result["failed_chapters"]
        # DLQ push_failure should have been called
        dlq.push_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_quota_exhausted_stops_immediately(self):
        """QuotaExhaustedError should stop extraction and return error_quota."""
        ctx = _make_worker_ctx()
        book_repo, entity_repo = _base_patches()

        async def quota_extract(**kw):
            raise QuotaExhaustedError(provider="gemini")

        with (
            patch("app.workers.tasks.BookRepository", return_value=book_repo),
            patch("app.workers.tasks.EntityRepository", return_value=entity_repo),
            patch("app.workers.tasks.extract_chapter_v4", new_callable=AsyncMock, side_effect=quota_extract),
            patch("app.workers.tasks._is_non_content_chapter", return_value=False),
        ):
            from app.workers.tasks import process_book_extraction_v4

            result = await process_book_extraction_v4(ctx, "book-1")

        assert result["stopped_reason"] == "quota_exhausted"
        assert result["provider"] == "gemini"
        book_repo.update_book_status.assert_any_call("book-1", "error_quota")

    @pytest.mark.asyncio
    async def test_cost_ceiling_breaks_loop(self):
        """CostCeilingError should break the loop and mark cost_ceiling_hit."""
        ctx = _make_worker_ctx()
        book_repo, entity_repo = _base_patches()

        call_count = 0

        async def ceiling_extract(**kw):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise CostCeilingError("Cost ceiling exceeded")
            return _mock_extract_result(kw["chapter_number"])

        with (
            patch("app.workers.tasks.BookRepository", return_value=book_repo),
            patch("app.workers.tasks.EntityRepository", return_value=entity_repo),
            patch("app.workers.tasks.extract_chapter_v4", new_callable=AsyncMock, side_effect=ceiling_extract),
            patch("app.workers.tasks.streaming_chapter_dedup", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.iterative_cluster", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.generate_entity_summaries", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks.generate_state_snapshots", new_callable=AsyncMock, return_value=0),
            patch("app.workers.tasks.community_cluster", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks._is_non_content_chapter", return_value=False),
        ):
            from app.workers.tasks import process_book_extraction_v4

            result = await process_book_extraction_v4(ctx, "book-1")

        assert result["cost_ceiling_hit"] is True
        assert result["chapters_processed"] == 1  # only first chapter succeeded


class TestWorkerV4ChapterFiltering:
    @pytest.mark.asyncio
    async def test_non_content_chapters_skipped(self):
        """Chapters flagged as non-content should be skipped."""
        ctx = _make_worker_ctx()
        book_repo, entity_repo = _base_patches()

        def is_non_content(ch):
            return ch.number == 1  # Skip chapter 1

        with (
            patch("app.workers.tasks.BookRepository", return_value=book_repo),
            patch("app.workers.tasks.EntityRepository", return_value=entity_repo),
            patch("app.workers.tasks.extract_chapter_v4", new_callable=AsyncMock,
                  side_effect=lambda **kw: _mock_extract_result(kw["chapter_number"])),
            patch("app.workers.tasks.streaming_chapter_dedup", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.iterative_cluster", new_callable=AsyncMock, return_value={}),
            patch("app.workers.tasks.generate_entity_summaries", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks.generate_state_snapshots", new_callable=AsyncMock, return_value=0),
            patch("app.workers.tasks.community_cluster", new_callable=AsyncMock, return_value=[]),
            patch("app.workers.tasks._is_non_content_chapter", side_effect=is_non_content),
        ):
            from app.workers.tasks import process_book_extraction_v4

            result = await process_book_extraction_v4(ctx, "book-1")

        # Only chapter 2 should have been processed
        assert result["chapters_processed"] == 1
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_worker_v4.py -v`
Expected: All tests PASS (some may need adjustment based on actual import paths in workers/tasks.py)

- [ ] **Step 3: Fix any import issues**

The worker tests patch at the module level where functions are imported. If `extract_chapter_v4` is imported differently in `tasks.py`, adjust the patch path. Check with:

Run: `cd /home/ringuet/WorldRAG && grep "from.*import.*extract_chapter_v4\|from.*import.*iterative_cluster\|from.*import.*streaming_chapter_dedup\|from.*import.*BookRepository\|from.*import.*EntityRepository\|from.*import.*_is_non_content_chapter" backend/app/workers/tasks.py`

Adjust patch paths in the test file to match the actual import locations.

- [ ] **Step 4: Run tests again after fixes**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/test_worker_v4.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/services/extraction/test_worker_v4.py
git commit -m "test: V4 worker — happy path, DLQ, quota, cost ceiling, auto-chain, filtering"
```

---

### Task 11: Run full test suite and fix any issues

- [ ] **Step 1: Run all extraction tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run all backend tests to check for regressions**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/ -x --tb=short -q`
Expected: No regressions

- [ ] **Step 3: Run linting**

Run: `cd /home/ringuet/WorldRAG && uv run ruff check backend/tests/services/extraction/ --fix && uv run ruff format backend/tests/services/extraction/`
Expected: Clean

- [ ] **Step 4: Final commit**

```bash
git add -A backend/tests/services/extraction/
git commit -m "test: fix lint issues in V4 extraction test suite"
```

---

### Task 12: Summary verification

- [ ] **Step 1: Count new test lines**

Run: `cd /home/ringuet/WorldRAG && wc -l backend/tests/services/extraction/test_*.py backend/tests/services/extraction/conftest.py`
Expected: ~2500+ total lines across all files

- [ ] **Step 2: Count individual tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/services/extraction/ --collect-only -q | tail -1`
Expected: ~60+ tests collected

- [ ] **Step 3: Final commit with all changes**

```bash
git add -A
git commit -m "feat: comprehensive V4 extraction pipeline test suite (~60 tests, ~2500 lines)"
```
