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
                char_offset_end=CHAPTER_1_TEXT.find("Jake Thayne woke up")
                + len("Jake Thayne woke up"),
            ),
            ExtractedCharacter(
                name="Casper",
                canonical_name="casper",
                role="minor",
                extraction_text="Casper the ghostly figure",
                char_offset_start=CHAPTER_1_TEXT.find("Casper the ghostly figure"),
                char_offset_end=CHAPTER_1_TEXT.find("Casper the ghostly figure")
                + len("Casper the ghostly figure"),
            ),
            ExtractedGenreEntity(
                sub_type="skill",
                name="Basic Archery",
                owner="jake thayne",
                rank="common",
                extraction_text="Basic Archery - Common",
                char_offset_start=CHAPTER_1_TEXT.find("Basic Archery - Common"),
                char_offset_end=CHAPTER_1_TEXT.find("Basic Archery - Common")
                + len("Basic Archery - Common"),
            ),
            ExtractedLocation(
                name="The Tutorial",
                canonical_name="the tutorial",
                extraction_text="The Tutorial had begun",
                char_offset_start=CHAPTER_1_TEXT.find("The Tutorial had begun"),
                char_offset_end=CHAPTER_1_TEXT.find("The Tutorial had begun")
                + len("The Tutorial had begun"),
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
                char_offset_end=CHAPTER_2_TEXT.find("Jake stalked through")
                + len("Jake stalked through"),
            ),
            ExtractedGenreEntity(
                sub_type="skill",
                name="Shadow Step",
                owner="jake thayne",
                rank="rare",
                extraction_text="Shadow Step - Rare",
                char_offset_start=CHAPTER_2_TEXT.find("Shadow Step - Rare"),
                char_offset_end=CHAPTER_2_TEXT.find("Shadow Step - Rare")
                + len("Shadow Step - Rare"),
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
                char_offset_end=CHAPTER_2_TEXT.find("pack of Shadow Wolves")
                + len("pack of Shadow Wolves"),
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
                raise StopAsyncIteration from None

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
