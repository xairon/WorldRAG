"""Tests for the Chat/RAG query service.

Tests the hybrid retrieval pipeline: vector search → rerank → LLM generation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import ChatResponse, RelatedEntity, SourceChunk
from app.services.chat_service import ChatService


@pytest.fixture
def chat_service(mock_neo4j_driver_with_session):
    """ChatService with mocked Neo4j driver."""
    return ChatService(mock_neo4j_driver_with_session)


@pytest.fixture
def mock_embedder():
    """Mock VoyageEmbedder."""
    embedder = AsyncMock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return embedder


@pytest.fixture
def mock_reranker():
    """Mock CohereReranker."""
    reranker = AsyncMock()
    return reranker


# -- Vector search returns empty --


@pytest.mark.asyncio
async def test_query_no_chunks_returns_helpful_message(
    chat_service, mock_embedder, mock_reranker, mock_neo4j_session
):
    """When no chunks match, return a helpful message."""
    chat_service.embedder = mock_embedder
    chat_service.reranker = mock_reranker
    mock_neo4j_session.run.return_value.data = AsyncMock(return_value=[])

    result = await chat_service.query("Who is Jake?", book_id="book-1")

    assert isinstance(result, ChatResponse)
    assert result.chunks_retrieved == 0
    assert result.chunks_after_rerank == 0
    assert "couldn't find" in result.answer.lower()


# -- Rerank returns empty --


@pytest.mark.asyncio
async def test_query_rerank_filters_all(
    chat_service, mock_embedder, mock_reranker, mock_neo4j_session
):
    """When reranker filters everything out, return appropriate message."""
    chat_service.embedder = mock_embedder
    chat_service.reranker = mock_reranker

    # Vector search returns chunks
    chunks = [
        {
            "text": "Jake drew his bow.",
            "chapter_number": 1,
            "chapter_title": "Ch 1",
            "position": 0,
            "score": 0.9,
        },
    ]
    mock_neo4j_session.run.return_value.data = AsyncMock(return_value=chunks)

    # Reranker filters everything
    mock_reranker.rerank = AsyncMock(return_value=[])

    result = await chat_service.query("Who is Jake?", book_id="book-1")

    assert result.chunks_retrieved == 1
    assert result.chunks_after_rerank == 0
    assert "relevant enough" in result.answer.lower()


# -- Full pipeline success --


@pytest.mark.asyncio
async def test_query_full_pipeline(chat_service, mock_embedder, mock_reranker, mock_neo4j_session):
    """Full pipeline: vector search → rerank → entities → LLM generates answer."""
    chat_service.embedder = mock_embedder
    chat_service.reranker = mock_reranker

    chunks = [
        {
            "text": "Jake is a hunter.",
            "chapter_number": 1,
            "chapter_title": "The Hunt",
            "position": 0,
            "score": 0.95,
        },
        {
            "text": "He used Arcane Powershot.",
            "chapter_number": 1,
            "chapter_title": "The Hunt",
            "position": 1,
            "score": 0.8,
        },
        {
            "text": "Sylphie flew overhead.",
            "chapter_number": 2,
            "chapter_title": "The Hawk",
            "position": 0,
            "score": 0.7,
        },
    ]

    entities = [
        {"name": "Jake", "label": "Character", "description": "The protagonist"},
        {"name": "Arcane Powershot", "label": "Skill", "description": "A powerful skill"},
    ]

    # First call: vector search returns chunks; Second call: entity fetch
    call_count = 0

    async def mock_data():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return chunks
        return entities

    mock_neo4j_session.run.return_value.data = mock_data

    # Reranker keeps top 2
    from app.llm.reranker import RerankResult

    mock_reranker.rerank = AsyncMock(
        return_value=[
            RerankResult(index=0, text=chunks[0]["text"], relevance_score=0.95),
            RerankResult(index=1, text=chunks[1]["text"], relevance_score=0.80),
        ]
    )

    # Mock LLM generation
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[
        0
    ].message.content = "Jake is a skilled hunter who uses Arcane Powershot."

    with patch("app.services.chat_service.get_openai_client") as mock_client_fn:
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_client_fn.return_value = client

        result = await chat_service.query(
            "Who is Jake?",
            book_id="book-1",
            top_k=10,
            rerank_top_n=2,
        )

    assert isinstance(result, ChatResponse)
    assert result.chunks_retrieved == 3
    assert result.chunks_after_rerank == 2
    assert "Jake" in result.answer
    assert len(result.sources) == 2
    assert result.sources[0].relevance_score == 0.95
    assert result.sources[0].chapter_number == 1
    assert len(result.related_entities) == 2


# -- Sources excluded when include_sources=False --


@pytest.mark.asyncio
async def test_query_no_sources_when_disabled(
    chat_service, mock_embedder, mock_reranker, mock_neo4j_session
):
    """When include_sources=False, response has no source chunks."""
    chat_service.embedder = mock_embedder
    chat_service.reranker = mock_reranker

    chunks = [
        {
            "text": "Jake is a hunter.",
            "chapter_number": 1,
            "chapter_title": "Ch 1",
            "position": 0,
            "score": 0.9,
        },
    ]

    call_count = 0

    async def mock_data():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return chunks
        return []

    mock_neo4j_session.run.return_value.data = mock_data

    from app.llm.reranker import RerankResult

    mock_reranker.rerank = AsyncMock(
        return_value=[
            RerankResult(index=0, text=chunks[0]["text"], relevance_score=0.9),
        ]
    )

    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = "Jake is a hunter."

    with patch("app.services.chat_service.get_openai_client") as mock_client_fn:
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_client_fn.return_value = client

        result = await chat_service.query(
            "Who is Jake?",
            book_id="book-1",
            include_sources=False,
        )

    assert result.sources == []
    assert result.chunks_after_rerank == 1


# -- Context building --


def test_build_context_with_entities(chat_service):
    """_build_context includes chunk text and entity info."""
    chunks = [
        {"text": "Jake is a hunter.", "chapter_number": 1, "chapter_title": "The Hunt"},
    ]
    scores = [0.95]
    entities = [RelatedEntity(name="Jake", label="Character", description="The protagonist")]

    context = chat_service._build_context(chunks, scores, entities)

    assert "Chapter 1" in context
    assert "The Hunt" in context
    assert "Jake is a hunter." in context
    assert "0.95" in context
    assert "**Jake**" in context
    assert "(Character)" in context


def test_build_context_without_entities(chat_service):
    """_build_context works without entities."""
    chunks = [
        {"text": "Some text.", "chapter_number": 5},
    ]
    context = chat_service._build_context(chunks, [0.8], [])

    assert "Chapter 5" in context
    assert "Some text." in context
    assert "Related Knowledge Graph" not in context


# -- Schema tests --


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
