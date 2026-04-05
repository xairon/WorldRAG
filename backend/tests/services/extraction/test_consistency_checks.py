"""Tests for graph-level consistency checks."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_async_iter(rows):
    class _Iter:
        def __init__(self):
            self._it = iter(rows)
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration from None
    return _Iter()


def _make_driver(query_results: list):
    """Mock driver returning different results for sequential queries."""
    driver = MagicMock()
    session = AsyncMock()
    call_idx = [0]

    async def mock_run(query, params=None):
        idx = call_idx[0]
        call_idx[0] += 1
        rows = query_results[idx] if idx < len(query_results) else []
        return _make_async_iter(rows)

    session.run = mock_run
    driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
    driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return driver


class TestRunConsistencyChecks:
    @pytest.mark.asyncio
    async def test_clean_graph_returns_empty(self):
        from app.services.extraction.book_level import run_consistency_checks
        driver = _make_driver([[], [], []])
        result = await run_consistency_checks(driver, "book-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_detects_orphans(self):
        from app.services.extraction.book_level import run_consistency_checks
        orphan_rows = [
            {"name": "lonely entity", "label": "Concept"},
        ]
        driver = _make_driver([orphan_rows, [], []])
        result = await run_consistency_checks(driver, "book-1")
        assert len(result) == 1
        assert result[0]["type"] == "orphan_entities"
        assert result[0]["count"] == 1

    @pytest.mark.asyncio
    async def test_detects_cross_type_duplicates(self):
        from app.services.extraction.book_level import run_consistency_checks
        dupe_rows = [
            {"name": "jake", "types": ["Character", "Event"], "node_count": 2},
        ]
        driver = _make_driver([[], dupe_rows, []])
        result = await run_consistency_checks(driver, "book-1")
        assert len(result) == 1
        assert result[0]["type"] == "cross_type_duplicates"

    @pytest.mark.asyncio
    async def test_detects_relation_violations(self):
        from app.services.extraction.book_level import run_consistency_checks
        violation_rows = [
            {"source": "fireball", "source_label": "Skill",
             "rel": "HAS_SKILL", "target": "ice", "target_label": "Concept"},
        ]
        driver = _make_driver([[], [], violation_rows])
        result = await run_consistency_checks(driver, "book-1")
        assert len(result) == 1
        assert result[0]["type"] == "relation_type_violations"
