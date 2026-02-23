"""Shared test fixtures for WorldRAG backend tests.

Provides mocked infrastructure services (Neo4j, Redis, LLM) for unit tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.book import ChapterData

# -- Infrastructure mocks -------------------------------------------------


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j async driver."""
    driver = AsyncMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
    driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return driver


@pytest.fixture
def mock_neo4j_session():
    """Pre-configured Neo4j session with run().data()/.consume() chain."""
    session = AsyncMock()

    result = AsyncMock()
    result.data = AsyncMock(return_value=[])

    summary = MagicMock()
    summary.counters.nodes_created = 0
    summary.counters.relationships_created = 0
    summary.counters.properties_set = 0
    result.consume = AsyncMock(return_value=summary)

    session.run = AsyncMock(return_value=result)

    # Transaction mock for execute_batch
    tx = AsyncMock()
    tx.run = AsyncMock()
    tx.commit = AsyncMock()
    session.begin_transaction = MagicMock()
    session.begin_transaction.return_value.__aenter__ = AsyncMock(return_value=tx)
    session.begin_transaction.return_value.__aexit__ = AsyncMock(return_value=False)

    return session


@pytest.fixture
def mock_neo4j_driver_with_session(mock_neo4j_session):
    """Neo4j driver that yields the pre-configured session.

    driver.session() is synchronous (returns an async context manager),
    so we use MagicMock for the driver and wire __aenter__/__aexit__
    on the returned object.
    """
    driver = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_neo4j_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = cm
    return driver


@pytest.fixture
def mock_redis():
    """Mock Redis async client."""
    redis = AsyncMock()
    redis.ping.return_value = True
    redis.get.return_value = None
    redis.set.return_value = True
    return redis


@pytest.fixture
def mock_langfuse():
    """Mock LangFuse client."""
    langfuse = MagicMock()
    trace = MagicMock()
    langfuse.trace.return_value = trace
    trace.span.return_value = MagicMock()
    return langfuse


@pytest.fixture
def mock_instructor_client():
    """AsyncMock for instructor.AsyncInstructor."""
    client = AsyncMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()
    return client


# -- Factory fixtures -----------------------------------------------------


@pytest.fixture
def make_chapter():
    """Factory for ChapterData with sensible defaults."""

    def _factory(
        number: int = 1,
        title: str = "Test Chapter",
        text: str = "Default paragraph one.\n\nDefault paragraph two.",
    ) -> ChapterData:
        return ChapterData(number=number, title=title, text=text)

    return _factory


# -- Sample data ----------------------------------------------------------


@pytest.fixture
def sample_chapter_text():
    """Sample LitRPG chapter text for extraction tests."""
    return """Chapter 42: The Trial Begins

Jake drew his bow, the familiar weight reassuring in his hands. The Arcane Hunter
class pulsed with power as he channeled Arcane Powershot. Across the arena, the
C-grade beast roared — a Scalding Hydra with five regenerating heads.

[Skill Acquired: Mark of the Ambitious Hunter - Legendary]
+5 Perception, +3 Agility

"Focus, Thayne," Villy's voice echoed in his mind. The Primordial of the Malefic
Viper rarely offered direct guidance, but the trial demanded it.

Sylphie chirped from above, her emerald feathers catching the light of Nevermore's
eternal twilight. The little hawk had grown considerably since their arrival on
the 78th floor.

Jake released the arrow. It screamed through the air, trailing purple and green
arcane energy. Level 87 to 88 — the beast's death triggered an immediate level-up.

Level: 87 -> 88
+5 Free Points

The Monarch of the arena fell, and with it, Jake earned a new title.

Title earned: Hydra Slayer
"""
