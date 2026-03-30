import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.extraction.book_level import (
    iterative_cluster,
    generate_entity_summaries,
    community_cluster,
    generate_state_snapshots,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_mock_driver(rows: list, extra_call_rows: list | None = None):
    """Build a mock Neo4j driver whose session.run() yields *rows*.

    If *extra_call_rows* is provided, subsequent calls to session.run()
    return those rows instead (useful when multiple queries run in sequence).
    """
    mock_driver = MagicMock()
    mock_session = AsyncMock()

    call_count = 0
    all_row_sets = [rows] + (extra_call_rows or [])

    async def _run(*args, **kwargs):
        nonlocal call_count
        idx = min(call_count, len(all_row_sets) - 1)
        call_count += 1
        return _make_async_iter(all_row_sets[idx])

    mock_session.run = _run
    mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_driver


def _make_row(data: dict):
    """Return a dict-like object (used as a Neo4j record stand-in)."""
    return data


# ---------------------------------------------------------------------------
# TestIterativeCluster
# ---------------------------------------------------------------------------

class TestIterativeCluster:

    @pytest.mark.asyncio
    async def test_empty_book(self):
        """No entities in Neo4j → empty alias_map returned immediately."""
        result = await iterative_cluster(_make_mock_driver([]), "book-1")
        assert result == {}

    @pytest.mark.asyncio
    async def test_few_entities_no_clustering(self):
        """Fewer than 5 entities per type → clustering loop is skipped entirely."""
        # 4 Character entities — below the `len(entities) < 5` threshold
        records = [
            {"name": "Alice", "entity_type": "Character", "description": "hero"},
            {"name": "Bob", "entity_type": "Character", "description": "sidekick"},
            {"name": "Eve", "entity_type": "Character", "description": "villain"},
            {"name": "Dave", "entity_type": "Character", "description": "merchant"},
        ]
        result = await iterative_cluster(_make_mock_driver(records), "book-2")
        # No dedup calls → alias_map must be empty
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        """Return type is always a dict (even when only 1 entity type present)."""
        records = [
            {"name": "X", "entity_type": "Location", "description": "a place"},
        ]
        result = await iterative_cluster(_make_mock_driver(records), "book-3")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TestGenerateEntitySummaries
# ---------------------------------------------------------------------------

class TestGenerateEntitySummaries:

    @pytest.mark.asyncio
    async def test_empty_book(self):
        """No entities above mention threshold → returns empty list."""
        result = await generate_entity_summaries(_make_mock_driver([]), "book-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_book_returns_list(self):
        """Return type is always a list, never None."""
        result = await generate_entity_summaries(_make_mock_driver([]), "book-99")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_below_min_mentions_skipped(self):
        """Entities that don't reach min_mentions are filtered out in the query.

        The mock returns no rows (simulating the DB WHERE clause filtering them),
        so the function must return an empty list without calling any LLM.
        """
        # min_mentions default is 3 — driver returns nothing (filtered by Neo4j)
        result = await generate_entity_summaries(
            _make_mock_driver([]), "book-2", min_mentions=5
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_with_entities_no_llm_client_returns_empty(self):
        """When entities are present but LLM client unavailable → returns []."""
        records = [
            {
                "name": "Aria",
                "entity_type": "Character",
                "mention_count": 10,
                "texts": ["Aria is the protagonist.", "Aria fights the dragon."],
                "first_ch": 1,
                "last_ch": 5,
            }
        ]

        mock_driver = _make_mock_driver(records)

        # Patch get_instructor_for_task where it is imported inside book_level
        with patch(
            "app.llm.providers.get_instructor_for_task",
            side_effect=RuntimeError("no provider"),
        ):
            result = await generate_entity_summaries(mock_driver, "book-3")
        # Should return [] gracefully when LLM client is unavailable
        assert result == []


# ---------------------------------------------------------------------------
# TestGenerateStateSnapshots
# ---------------------------------------------------------------------------

class TestGenerateStateSnapshots:

    @pytest.mark.asyncio
    async def test_calls_entity_repo_no_chapters(self):
        """When max_chapter is None / 0, returns 0 immediately."""
        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[{"max_ch": None}])

        result = await generate_state_snapshots(mock_repo, "book-1")

        assert result == 0
        mock_repo.execute_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_entity_repo_no_characters(self):
        """When chapters exist but no main characters, returns 0."""
        mock_repo = AsyncMock()
        # First call: max chapter query → returns chapter 20
        # Second call: main chars query → returns []
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                [{"max_ch": 20}],
                [],  # no main characters
            ]
        )

        result = await generate_state_snapshots(mock_repo, "book-2")

        assert result == 0
        assert mock_repo.execute_read.call_count == 2

    @pytest.mark.asyncio
    async def test_snapshot_count_one_char_two_intervals(self):
        """One character over 20 chapters with interval=10 → 2 snapshots."""
        mock_repo = AsyncMock()

        # execute_read call sequence:
        # 1. max_chapter → 20
        # 2. main_chars → [{"name": "Alice"}]
        # 3+. snapshot queries (one per chapter-interval per char) → each returns data
        snapshot_data = {
            "name": "Alice",
            "levels": [{"level": 5, "realm": None}],
            "skills": ["Fireball"],
            "classes": ["Mage"],
            "titles": [],
        }
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                [{"max_ch": 20}],
                [{"name": "Alice"}],
                [snapshot_data],  # chapter 10
                [snapshot_data],  # chapter 20
            ]
        )
        mock_repo.execute_write = AsyncMock(return_value=None)

        result = await generate_state_snapshots(
            mock_repo, "book-3", snapshot_interval=10
        )

        assert result == 2
        assert mock_repo.execute_write.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_int(self):
        """Return type is always int."""
        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[{"max_ch": 0}])

        result = await generate_state_snapshots(mock_repo, "book-4")

        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# TestCommunityCluster
# ---------------------------------------------------------------------------

class TestCommunityCluster:

    @pytest.mark.asyncio
    async def test_empty_graph_no_nodes(self):
        """No nodes in graph → returns empty community list immediately."""

        def _session_factory():
            mock_session = AsyncMock()
            call_idx = [0]

            async def _run(*args, **kwargs):
                idx = call_idx[0]
                call_idx[0] += 1
                # First call: node query → []
                # Second call: edge query → []
                return _make_async_iter([])

            mock_session.run = _run
            return mock_session

        mock_driver = MagicMock()
        mock_session = AsyncMock()
        call_idx = [0]

        async def _run(*args, **kwargs):
            call_idx[0] += 1
            return _make_async_iter([])

        mock_session.run = _run
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await community_cluster(mock_driver, "book-1", min_community_size=3)

        assert result == []

    @pytest.mark.asyncio
    async def test_fewer_nodes_than_min_community_size(self):
        """Graph with 2 nodes but min_community_size=3 → empty list."""
        nodes = [
            {"name": "Alice", "label": "Character", "description": "hero"},
            {"name": "Bob", "label": "Character", "description": "sidekick"},
        ]
        edges: list = []

        mock_driver = MagicMock()
        mock_session = AsyncMock()
        call_idx = [0]
        row_sets = [nodes, edges]

        async def _run(*args, **kwargs):
            idx = min(call_idx[0], len(row_sets) - 1)
            call_idx[0] += 1
            return _make_async_iter(row_sets[idx])

        mock_session.run = _run
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await community_cluster(mock_driver, "book-2", min_community_size=3)

        # 2 nodes < min_community_size=3 → immediate return
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_list(self):
        """Return type is always a list."""
        mock_driver = MagicMock()
        mock_session = AsyncMock()

        async def _run(*args, **kwargs):
            return _make_async_iter([])

        mock_session.run = _run
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await community_cluster(mock_driver, "book-3")

        assert isinstance(result, list)
