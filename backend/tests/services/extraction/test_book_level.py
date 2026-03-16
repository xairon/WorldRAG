import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.extraction.book_level import (
    iterative_cluster,
    generate_entity_summaries,
    community_cluster,
)


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


def _make_mock_driver(rows: list):
    """Build a mock Neo4j driver whose session.run() yields *rows*."""
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_session.run = AsyncMock(return_value=_make_async_iter(rows))
    mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_driver


@pytest.mark.asyncio
async def test_iterative_cluster_empty_book():
    """No entities → empty alias_map."""
    result = await iterative_cluster(_make_mock_driver([]), "book-1")
    assert result == {}


@pytest.mark.asyncio
async def test_generate_entity_summaries_empty():
    """No entities above threshold → empty list."""
    result = await generate_entity_summaries(_make_mock_driver([]), "book-1")
    assert result == []
