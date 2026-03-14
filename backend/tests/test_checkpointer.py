"""Tests for the LangGraph checkpointer factory."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_checkpointer_returns_saver():
    """Factory returns an AsyncPostgresSaver when given a valid pool."""
    mock_pool = MagicMock()
    mock_saver = MagicMock()
    mock_saver.setup = AsyncMock()

    mock_module = MagicMock()
    mock_module.AsyncPostgresSaver = MagicMock(return_value=mock_saver)

    with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_module}):
        from app.core.checkpointer import create_checkpointer

        saver, success = await create_checkpointer(mock_pool)
        assert saver is mock_saver
        assert success is True
        mock_saver.setup.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_checkpointer_returns_none_on_none_pool():
    """Factory returns None when pool is None."""
    from app.core.checkpointer import create_checkpointer

    saver, success = await create_checkpointer(None)
    assert saver is None
    assert success is False


@pytest.mark.asyncio
async def test_create_checkpointer_returns_none_on_failure():
    """Factory returns None and logs warning on setup error."""
    mock_pool = MagicMock()

    mock_module = MagicMock()
    mock_module.AsyncPostgresSaver = MagicMock(side_effect=ConnectionError("refused"))

    with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_module}):
        from app.core.checkpointer import create_checkpointer

        saver, success = await create_checkpointer(mock_pool)
        assert saver is None
        assert success is False
