"""Tests for the Chat/RAG query service (LangGraph-based).

Tests the ChatService wrapper that delegates to the LangGraph chat agent graph.
The graph itself is mocked — node-level logic is tested in dedicated test files.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import ChatResponse, RelatedEntity, SourceChunk

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_graph():
    """Mock compiled LangGraph."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(
        return_value={
            "generation": "Jake is a skilled hunter.",
            "reranked_chunks": [
                {
                    "text": "Jake is a hunter.",
                    "chapter_number": 1,
                    "chapter_title": "The Hunt",
                    "position": 0,
                    "relevance_score": 0.95,
                },
            ],
            "kg_entities": [
                {"name": "Jake", "label": "Character", "description": "The protagonist"},
            ],
            "citations": [{"chapter": 1, "position": 0}],
            "fused_results": [{"node_id": "c1"}, {"node_id": "c2"}, {"node_id": "c3"}],
            "faithfulness_score": 0.9,
        }
    )
    return graph


@pytest.fixture
def mock_graph_builder(mock_graph):
    """Mock uncompiled StateGraph builder."""
    builder = MagicMock()
    builder.compile.return_value = mock_graph
    return builder


@pytest.fixture
def chat_service(mock_neo4j_driver_with_session, mock_graph_builder):
    """ChatService with mocked graph builder."""
    from app.services.chat_service import ChatService

    # Reset singleton so each test gets a fresh compiled graph
    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None
    ChatService._shared_driver = None

    with patch(
        "app.services.chat_service.build_chat_graph",
        return_value=mock_graph_builder,
    ):
        service = ChatService(mock_neo4j_driver_with_session)
    return service


# ---------------------------------------------------------------------------
# query() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_returns_chat_response(chat_service):
    """query() invokes graph and maps output to ChatResponse."""
    result = await chat_service.query("Who is Jake?", book_id="book-1")

    assert isinstance(result, ChatResponse)
    assert "Jake" in result.answer
    assert result.chunks_retrieved == 3
    assert result.chunks_after_rerank == 1
    assert len(result.sources) == 1
    assert result.sources[0].chapter_number == 1
    assert result.sources[0].relevance_score == 0.95
    assert len(result.related_entities) == 1
    assert result.related_entities[0].name == "Jake"
    assert len(result.citations) == 1
    assert result.citations[0].chapter == 1


@pytest.mark.asyncio
async def test_query_no_chunks_returns_fallback(chat_service, mock_graph):
    """When graph returns empty generation, return fallback message."""
    mock_graph.ainvoke.return_value = {
        "generation": "",
        "reranked_chunks": [],
        "kg_entities": [],
        "citations": [],
        "fused_results": [],
        "faithfulness_score": 0.0,
    }

    result = await chat_service.query("Who is Jake?", book_id="book-1")
    assert isinstance(result, ChatResponse)
    assert result.chunks_retrieved == 0
    assert result.chunks_after_rerank == 0
    assert "wasn't able" in result.answer.lower()


@pytest.mark.asyncio
async def test_query_no_sources_when_disabled(chat_service):
    """When include_sources=False, response has no source chunks."""
    result = await chat_service.query("Who is Jake?", book_id="book-1", include_sources=False)
    assert result.sources == []
    assert result.chunks_after_rerank == 1


@pytest.mark.asyncio
async def test_query_with_thread_id(chat_service, mock_graph):
    """thread_id is passed via config and returned in response."""
    result = await chat_service.query("Who is Jake?", book_id="book-1", thread_id="thread-abc")

    assert result.thread_id == "thread-abc"
    call_kwargs = mock_graph.ainvoke.call_args
    config = call_kwargs.kwargs.get("config", call_kwargs[1].get("config", {}))
    assert config.get("configurable", {}).get("thread_id") == "thread-abc"


# ---------------------------------------------------------------------------
# N5 regression: driver change invalidates singleton
# ---------------------------------------------------------------------------


def test_driver_change_recompiles_graph(mock_neo4j_driver_with_session):
    """N5 fix: ChatService recompiles graph when a different driver is passed."""
    from app.services.chat_service import ChatService

    # Reset singleton
    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None
    ChatService._shared_driver = None

    mock_builder_1 = MagicMock()
    mock_graph_1 = MagicMock()
    mock_builder_1.compile.return_value = mock_graph_1

    mock_builder_2 = MagicMock()
    mock_graph_2 = MagicMock()
    mock_builder_2.compile.return_value = mock_graph_2

    # First init with driver_1
    driver_1 = mock_neo4j_driver_with_session
    with patch("app.services.chat_service.build_chat_graph", return_value=mock_builder_1):
        service_1 = ChatService(driver_1)
    assert service_1._graph is mock_graph_1

    # Second init with SAME driver → reuses cached graph
    with patch("app.services.chat_service.build_chat_graph", return_value=mock_builder_2):
        service_2 = ChatService(driver_1)
    assert service_2._graph is mock_graph_1  # Still the old one

    # Third init with DIFFERENT driver → recompiles
    driver_2 = MagicMock()
    with patch("app.services.chat_service.build_chat_graph", return_value=mock_builder_2):
        service_3 = ChatService(driver_2)
    assert service_3._graph is mock_graph_2  # New graph!

    # Clean up singleton
    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None
    ChatService._shared_driver = None


# ---------------------------------------------------------------------------
# Checkpointer tests
# ---------------------------------------------------------------------------


def test_graph_compiled_with_checkpointer(mock_neo4j_driver_with_session):
    """When checkpointer is provided, graph.compile() receives it."""
    from app.services.chat_service import ChatService

    # Reset singleton
    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None
    ChatService._shared_driver = None
    ChatService._shared_checkpointer = None

    mock_checkpointer = MagicMock()
    mock_builder = MagicMock()
    mock_graph = MagicMock()
    mock_builder.compile.return_value = mock_graph

    with patch("app.services.chat_service.build_chat_graph", return_value=mock_builder):
        ChatService(mock_neo4j_driver_with_session, checkpointer=mock_checkpointer)

    mock_builder.compile.assert_called_once_with(checkpointer=mock_checkpointer)

    # Clean up singleton
    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None
    ChatService._shared_driver = None
    ChatService._shared_checkpointer = None


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_chat_response_serialization():
    """ChatResponse serializes correctly."""
    resp = ChatResponse(
        answer="Test answer",
        sources=[
            SourceChunk(
                text="chunk text",
                chapter_number=1,
                chapter_title="Ch 1",
                position=0,
                relevance_score=0.95,
            )
        ],
        related_entities=[
            RelatedEntity(name="Jake", label="Character", description="Hero"),
        ],
        chunks_retrieved=10,
        chunks_after_rerank=3,
    )

    data = resp.model_dump()
    assert data["answer"] == "Test answer"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["chapter_number"] == 1
    assert len(data["related_entities"]) == 1
    assert data["chunks_retrieved"] == 10
