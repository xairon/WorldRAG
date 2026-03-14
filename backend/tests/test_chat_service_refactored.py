"""Tests for the refactored ChatService that wraps the LangGraph chat agent."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import ChatResponse

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_chat_service_singleton():
    """Reset the ChatService singleton before each test."""
    from app.services.chat_service import ChatService

    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None
    yield
    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None


@pytest.fixture()
def mock_driver():
    """Fake Neo4j AsyncDriver."""
    return AsyncMock()


@pytest.fixture()
def fake_graph_result() -> dict[str, Any]:
    """A realistic graph output state dict."""
    return {
        "generation": "Erin Solstice is an innkeeper in Liscor.",
        "reranked_chunks": [
            {
                "text": "Erin opened The Wandering Inn on a hill outside Liscor.",
                "chapter_number": 1,
                "chapter_title": "The Innkeeper",
                "position": 0,
                "relevance_score": 0.95,
            },
            {
                "text": "She served pasta to the Antinium.",
                "chapter_number": 3,
                "chapter_title": "Guests",
                "position": 12,
                "relevance_score": 0.82,
            },
        ],
        "kg_entities": [
            {"name": "Erin Solstice", "label": "Character", "description": "The innkeeper"},
            {"name": "Liscor", "label": "Location", "description": "A walled city"},
        ],
        "citations": [
            {"chapter": 1, "position": 0},
            {"chapter": 3},
        ],
        "fused_results": [{"id": 1}, {"id": 2}, {"id": 3}],
        "faithfulness_score": 0.9,
    }


# ---------------------------------------------------------------------------
# Test 1: __init__ builds the graph
# ---------------------------------------------------------------------------


@patch("app.services.chat_service.build_chat_graph")
@patch("app.services.chat_service.LocalEmbedder")
@patch("app.services.chat_service.Neo4jRepository")
def test_init_builds_graph(mock_repo_cls, mock_embedder_cls, mock_build_graph, mock_driver):
    """ChatService.__init__ should construct the graph builder and compile it."""
    mock_builder = MagicMock()
    mock_compiled = MagicMock()
    mock_builder.compile.return_value = mock_compiled
    mock_build_graph.return_value = mock_builder

    from app.services.chat_service import ChatService

    svc = ChatService(mock_driver)

    mock_repo_cls.assert_called_once_with(mock_driver)
    mock_embedder_cls.assert_called_once()
    mock_build_graph.assert_called_once_with(
        repo=svc.repo,
        embedder=svc.embedder,
    )
    mock_builder.compile.assert_called_once_with(checkpointer=None)
    assert svc._graph is mock_compiled


# ---------------------------------------------------------------------------
# Test 2: query() invokes the graph and returns ChatResponse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.services.chat_service.build_chat_graph")
@patch("app.services.chat_service.LocalEmbedder")
@patch("app.services.chat_service.Neo4jRepository")
async def test_query_invokes_graph(
    mock_repo_cls, mock_embedder_cls, mock_build_graph, mock_driver, fake_graph_result
):
    """query() should ainvoke the compiled graph and map the result to ChatResponse."""
    mock_builder = MagicMock()
    mock_compiled = MagicMock()
    mock_compiled.ainvoke = AsyncMock(return_value=fake_graph_result)
    mock_builder.compile.return_value = mock_compiled
    mock_build_graph.return_value = mock_builder

    from app.services.chat_service import ChatService

    svc = ChatService(mock_driver)

    resp = await svc.query("Who is Erin?", "book-123", thread_id="thread-1")

    # Verify ainvoke was called with correct state
    call_args = mock_compiled.ainvoke.call_args
    state_input = call_args[0][0]
    config = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("config", {})

    assert state_input["query"] == "Who is Erin?"
    assert state_input["book_id"] == "book-123"
    assert state_input["retries"] == 0
    assert config == {"configurable": {"thread_id": "thread-1"}}

    # Verify response mapping
    assert isinstance(resp, ChatResponse)
    assert resp.answer == "Erin Solstice is an innkeeper in Liscor."
    assert resp.thread_id == "thread-1"
    assert resp.chunks_retrieved == 3
    assert resp.chunks_after_rerank == 2
    assert len(resp.sources) == 2
    assert resp.sources[0].chapter_number == 1
    assert resp.sources[0].relevance_score == 0.95
    assert len(resp.related_entities) == 2
    assert resp.related_entities[0].name == "Erin Solstice"
    assert len(resp.citations) == 2
    assert resp.citations[0].chapter == 1
    assert resp.citations[1].position is None


@pytest.mark.asyncio
@patch("app.services.chat_service.build_chat_graph")
@patch("app.services.chat_service.LocalEmbedder")
@patch("app.services.chat_service.Neo4jRepository")
async def test_query_no_thread_id(mock_repo_cls, mock_embedder_cls, mock_build_graph, mock_driver):
    """query() without thread_id should pass empty config."""
    mock_builder = MagicMock()
    mock_compiled = MagicMock()
    mock_compiled.ainvoke = AsyncMock(return_value={"generation": "An answer."})
    mock_builder.compile.return_value = mock_compiled
    mock_build_graph.return_value = mock_builder

    from app.services.chat_service import ChatService

    svc = ChatService(mock_driver)
    resp = await svc.query("test?", "book-1")

    call_args = mock_compiled.ainvoke.call_args
    config = call_args[1].get("config", call_args[0][1] if len(call_args[0]) > 1 else {})
    assert config == {}
    assert resp.thread_id is None
    assert resp.answer == "An answer."


# ---------------------------------------------------------------------------
# Test 3: query_stream() yields SSE events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.services.chat_service.build_chat_graph")
@patch("app.services.chat_service.LocalEmbedder")
@patch("app.services.chat_service.Neo4jRepository")
async def test_query_stream_yields_sse_events(
    mock_repo_cls, mock_embedder_cls, mock_build_graph, mock_driver
):
    """query_stream() should yield step, token, and done SSE events."""
    import json

    from langchain_core.messages import AIMessageChunk

    # Simulate astream yielding (stream_type, data) tuples
    stream_events = [
        ("custom", {"node": "router", "route": "hybrid_rag"}),
        ("messages", (AIMessageChunk(content="Hello"), {"langgraph_node": "generate"})),
        ("messages", (AIMessageChunk(content=" world"), {"langgraph_node": "generate"})),
    ]

    async def fake_astream(*args, **kwargs):
        for event in stream_events:
            yield event

    mock_builder = MagicMock()
    mock_compiled = MagicMock()
    mock_compiled.astream = fake_astream
    mock_builder.compile.return_value = mock_compiled
    mock_build_graph.return_value = mock_builder

    from app.services.chat_service import ChatService

    svc = ChatService(mock_driver)

    events: list[dict[str, str]] = []
    async for event in svc.query_stream("Who is Erin?", "book-1", thread_id="t-1"):
        events.append(event)

    # Expect: step, token, token, done
    assert len(events) == 4

    assert events[0]["event"] == "step"
    step_data = json.loads(events[0]["data"])
    assert step_data["node"] == "router"

    assert events[1]["event"] == "token"
    assert json.loads(events[1]["data"])["token"] == "Hello"

    assert events[2]["event"] == "token"
    assert json.loads(events[2]["data"])["token"] == " world"

    assert events[3]["event"] == "done"


@pytest.mark.asyncio
@patch("app.services.chat_service.build_chat_graph")
@patch("app.services.chat_service.LocalEmbedder")
@patch("app.services.chat_service.Neo4jRepository")
async def test_query_stream_handles_errors(
    mock_repo_cls, mock_embedder_cls, mock_build_graph, mock_driver
):
    """query_stream() should yield an error event if the graph raises."""
    import json

    async def failing_astream(*args, **kwargs):
        raise ValueError("Graph exploded")
        yield  # noqa: B901 — make this an async generator

    mock_builder = MagicMock()
    mock_compiled = MagicMock()
    mock_compiled.astream = failing_astream
    mock_builder.compile.return_value = mock_compiled
    mock_build_graph.return_value = mock_builder

    from app.services.chat_service import ChatService

    svc = ChatService(mock_driver)

    events: list[dict[str, str]] = []
    async for event in svc.query_stream("test?", "book-1"):
        events.append(event)

    # Should get an error event (no done)
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert "ValueError" in json.loads(events[0]["data"])["message"]
