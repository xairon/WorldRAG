"""Tests for multi-turn thread_id support in chat routes.

Verifies that POST /chat/query and GET /chat/stream correctly
propagate thread_id to the ChatService layer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.chat import router
from app.config import settings
from app.schemas.chat import ChatResponse


def _create_app() -> FastAPI:
    # Ensure v1 chat service is used (not v2 which needs Graphiti)
    settings.graphiti_enabled = False
    """Build a minimal FastAPI app with the chat router and mocked state."""
    app = FastAPI()
    app.include_router(router)

    # Provide a mock Neo4j driver via app.state so get_neo4j works.
    driver = MagicMock()
    app.state.neo4j_driver = driver
    return app


_DUMMY_RESPONSE = ChatResponse(
    answer="Test answer",
    sources=[],
    related_entities=[],
    chunks_retrieved=5,
    chunks_after_rerank=3,
    thread_id="thread-abc-123",
    citations=[],
)


@pytest.mark.asyncio
@patch("app.api.routes.chat.ChatService")
async def test_post_query_passes_thread_id(mock_service_cls: MagicMock) -> None:
    """POST /chat/query should forward thread_id from the request body to ChatService.query()."""
    mock_instance = AsyncMock()
    mock_instance.query = AsyncMock(return_value=_DUMMY_RESPONSE)
    mock_service_cls.return_value = mock_instance

    app = _create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/chat/query",
            json={
                "query": "Who is the main character?",
                "book_id": "book-1",
                "thread_id": "thread-abc-123",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["thread_id"] == "thread-abc-123"

    # Verify thread_id was passed through to the service call.
    mock_instance.query.assert_awaited_once()
    call_kwargs = mock_instance.query.call_args
    assert call_kwargs.kwargs.get("thread_id") == "thread-abc-123"


@pytest.mark.asyncio
@patch("app.api.routes.chat.ChatService")
async def test_post_query_thread_id_defaults_to_none(mock_service_cls: MagicMock) -> None:
    """POST /chat/query without thread_id should pass None to the service."""
    mock_instance = AsyncMock()
    mock_instance.query = AsyncMock(return_value=_DUMMY_RESPONSE)
    mock_service_cls.return_value = mock_instance

    app = _create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/chat/query",
            json={
                "query": "What is the system?",
                "book_id": "book-2",
            },
        )

    assert resp.status_code == 200
    mock_instance.query.assert_awaited_once()
    call_kwargs = mock_instance.query.call_args
    assert call_kwargs.kwargs.get("thread_id") is None


@pytest.mark.asyncio
@patch("app.api.routes.chat.ChatService")
async def test_get_stream_accepts_thread_id(mock_service_cls: MagicMock) -> None:
    """GET /chat/stream should accept thread_id as a query param and pass it to query_stream()."""
    mock_instance = AsyncMock()

    async def _fake_stream(**kwargs):
        yield {"event": "token", "data": "Hello"}
        yield {"event": "done", "data": ""}

    mock_instance.query_stream = MagicMock(return_value=_fake_stream())
    mock_service_cls.return_value = mock_instance

    app = _create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/chat/stream",
            params={
                "q": "Tell me about the dungeon",
                "book_id": "book-1",
                "thread_id": "thread-xyz-789",
            },
        )

    assert resp.status_code == 200
    mock_instance.query_stream.assert_called_once()
    call_kwargs = mock_instance.query_stream.call_args
    assert call_kwargs.kwargs.get("thread_id") == "thread-xyz-789"


@pytest.mark.asyncio
@patch("app.api.routes.chat.ChatService")
async def test_get_stream_thread_id_defaults_to_none(mock_service_cls: MagicMock) -> None:
    """GET /chat/stream without thread_id should pass None to query_stream()."""
    mock_instance = AsyncMock()

    async def _fake_stream(**kwargs):
        yield {"event": "token", "data": "World"}
        yield {"event": "done", "data": ""}

    mock_instance.query_stream = MagicMock(return_value=_fake_stream())
    mock_service_cls.return_value = mock_instance

    app = _create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/chat/stream",
            params={
                "q": "What happened in chapter 5?",
                "book_id": "book-3",
            },
        )

    assert resp.status_code == 200
    mock_instance.query_stream.assert_called_once()
    call_kwargs = mock_instance.query_stream.call_args
    assert call_kwargs.kwargs.get("thread_id") is None
