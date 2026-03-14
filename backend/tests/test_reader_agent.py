"""Tests for the Reader LangGraph agent (nodes, graph, service)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

ROUTER_PATCH = "app.agents.reader.nodes.reader_router.get_langchain_llm"
GENERATE_PATCH = "app.agents.reader.nodes.reader_generate.get_langchain_llm"


# ── Reader Router ──────────────────────────────────────────────────


class TestClassifyReaderIntent:
    """Tests for classify_reader_intent node."""

    @pytest.mark.asyncio
    async def test_routes_context_qa(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"route": "context_qa"}',
        )
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_router import (
                classify_reader_intent,
            )

            state: dict[str, Any] = {
                "query": "What happened?",
                "messages": [],
                "chapter_number": 3,
            }
            result = await classify_reader_intent(state)
            assert result["route"] == "context_qa"
            assert result["query"] == "What happened?"

    @pytest.mark.asyncio
    async def test_routes_entity_lookup(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"route": "entity_lookup"}',
        )
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_router import (
                classify_reader_intent,
            )

            state: dict[str, Any] = {
                "query": "Who is Jake?",
                "messages": [],
                "chapter_number": 1,
            }
            result = await classify_reader_intent(state)
            assert result["route"] == "entity_lookup"

    @pytest.mark.asyncio
    async def test_routes_summarize(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"route": "summarize"}',
        )
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_router import (
                classify_reader_intent,
            )

            state: dict[str, Any] = {
                "query": "Summarize this chapter",
                "messages": [],
                "chapter_number": 5,
            }
            result = await classify_reader_intent(state)
            assert result["route"] == "summarize"

    @pytest.mark.asyncio
    async def test_defaults_to_context_qa_on_invalid_json(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="not json")

        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_router import (
                classify_reader_intent,
            )

            state: dict[str, Any] = {
                "query": "Hello",
                "messages": [],
                "chapter_number": 1,
            }
            result = await classify_reader_intent(state)
            assert result["route"] == "context_qa"

    @pytest.mark.asyncio
    async def test_defaults_to_context_qa_on_unknown_route(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"route": "unknown_type"}',
        )
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_router import (
                classify_reader_intent,
            )

            state: dict[str, Any] = {
                "query": "Test",
                "messages": [],
                "chapter_number": 1,
            }
            result = await classify_reader_intent(state)
            assert result["route"] == "context_qa"


# ── Reader Retrieve ────────────────────────────────────────────────


class TestRetrieveChapterContext:
    """Tests for retrieve_chapter_context node."""

    @pytest.mark.asyncio
    async def test_retrieves_paragraphs_and_entities(self):
        from app.agents.reader.nodes.reader_retrieve import (
            retrieve_chapter_context,
        )

        paragraphs = [
            {
                "index": 0,
                "type": "narration",
                "text": "The sun rose.",
                "char_start": 0,
                "char_end": 13,
            },
            {
                "index": 1,
                "type": "dialogue",
                "text": "Hello!",
                "char_start": 14,
                "char_end": 20,
                "speaker": "Jake",
            },
        ]
        entities = [
            {
                "name": "Jake",
                "labels": ["Character"],
                "description": "A warrior",
                "char_start": 14,
                "char_end": 18,
                "mention_text": "Jake",
            },
        ]

        repo = AsyncMock()
        repo.execute_read = AsyncMock(
            side_effect=[paragraphs, entities],
        )

        state: dict[str, Any] = {
            "book_id": "book-1",
            "chapter_number": 3,
            "max_chapter": 5,
        }
        result = await retrieve_chapter_context(state, repo=repo)

        assert len(result["paragraph_context"]) == 2
        assert len(result["entity_annotations"]) == 1
        assert "Jake (Character)" in result["kg_context"]
        assert repo.execute_read.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_chapter_returns_empty(self):
        from app.agents.reader.nodes.reader_retrieve import (
            retrieve_chapter_context,
        )

        repo = AsyncMock()
        repo.execute_read = AsyncMock(side_effect=[[], []])

        state: dict[str, Any] = {
            "book_id": "book-1",
            "chapter_number": 1,
        }
        result = await retrieve_chapter_context(state, repo=repo)

        assert result["paragraph_context"] == []
        assert result["entity_annotations"] == []
        assert result["kg_context"] == ""


# ── Reader Generate ────────────────────────────────────────────────


class TestGenerateReaderAnswer:
    """Tests for generate_reader_answer node."""

    @pytest.mark.asyncio
    async def test_generates_context_qa_answer(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="The sun rose over the mountains.",
        )
        with patch(GENERATE_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_generate import (
                generate_reader_answer,
            )

            state: dict[str, Any] = {
                "query": "What happened?",
                "route": "context_qa",
                "paragraph_context": [
                    {"index": 0, "type": "narration", "text": "The sun rose."},
                ],
                "kg_context": "",
                "chapter_number": 3,
                "max_chapter": 5,
            }
            result = await generate_reader_answer(state)
            assert result["generation"] == "The sun rose over the mountains."
            mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_entity_lookup_answer(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="Jake is a warrior.",
        )
        with patch(GENERATE_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_generate import (
                generate_reader_answer,
            )

            state: dict[str, Any] = {
                "query": "Who is Jake?",
                "route": "entity_lookup",
                "paragraph_context": [],
                "kg_context": "Jake (Character): A warrior",
                "chapter_number": 3,
            }
            result = await generate_reader_answer(state)
            assert result["generation"] == "Jake is a warrior."

    @pytest.mark.asyncio
    async def test_spoiler_guard_in_prompt(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Answer")

        with patch(GENERATE_PATCH, return_value=mock_llm):
            from app.agents.reader.nodes.reader_generate import (
                generate_reader_answer,
            )

            state: dict[str, Any] = {
                "query": "What happens next?",
                "route": "context_qa",
                "paragraph_context": [],
                "kg_context": "",
                "chapter_number": 3,
                "max_chapter": 5,
            }
            await generate_reader_answer(state)
            call_args = mock_llm.ainvoke.call_args[0][0]
            system_msg = call_args[0].content
            assert "chapter 5" in system_msg
            assert "SPOILER" in system_msg


# ── Reader Graph ───────────────────────────────────────────────────


class TestBuildReaderGraph:
    """Tests for build_reader_graph."""

    def test_graph_has_three_nodes(self):
        from app.agents.reader.graph import build_reader_graph

        repo = MagicMock()
        builder = build_reader_graph(repo=repo)
        assert "router" in builder.nodes
        assert "retrieve" in builder.nodes
        assert "generate" in builder.nodes

    def test_graph_compiles(self):
        from app.agents.reader.graph import build_reader_graph

        repo = MagicMock()
        builder = build_reader_graph(repo=repo)
        compiled = builder.compile()
        assert compiled is not None


# ── Reader Service ─────────────────────────────────────────────────


class TestReaderService:
    """Tests for ReaderService."""

    @pytest.mark.asyncio
    async def test_query_returns_expected_keys(self):
        from app.services.reader_service import ReaderService

        ReaderService._compiled_graph = None
        ReaderService._shared_driver = None
        ReaderService._shared_repo = None

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "generation": "Answer text",
            "route": "context_qa",
            "paragraph_context": [{"text": "p1"}, {"text": "p2"}],
            "entity_annotations": [{"name": "Jake"}],
        }

        mock_driver = MagicMock()

        with patch(
            "app.services.reader_service.build_reader_graph",
        ) as mock_build:
            mock_builder = MagicMock()
            mock_builder.compile.return_value = mock_graph
            mock_build.return_value = mock_builder

            service = ReaderService(mock_driver)
            result = await service.query("What happened?", "book-1", 3)

        assert result["answer"] == "Answer text"
        assert result["route"] == "context_qa"
        assert result["paragraphs_used"] == 2
        assert result["entities_found"] == 1

    @pytest.mark.asyncio
    async def test_service_passes_thread_id(self):
        from app.services.reader_service import ReaderService

        ReaderService._compiled_graph = None
        ReaderService._shared_driver = None
        ReaderService._shared_repo = None

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "generation": "Answer",
            "route": "context_qa",
            "paragraph_context": [],
            "entity_annotations": [],
        }

        mock_driver = MagicMock()

        with patch(
            "app.services.reader_service.build_reader_graph",
        ) as mock_build:
            mock_builder = MagicMock()
            mock_builder.compile.return_value = mock_graph
            mock_build.return_value = mock_builder

            service = ReaderService(mock_driver)
            await service.query(
                "Q?",
                "book-1",
                1,
                thread_id="thread-123",
            )

        call_kwargs = mock_graph.ainvoke.call_args
        config = call_kwargs[1]["config"]
        assert config["configurable"]["thread_id"] == "thread-123"


# ── Reader Schemas ─────────────────────────────────────────────────


class TestReaderSchemas:
    """Tests for reader Pydantic schemas."""

    def test_request_valid(self):
        from app.schemas.reader import ReaderQueryRequest

        req = ReaderQueryRequest(
            query="What happened?",
            book_id="book-1",
            chapter_number=3,
        )
        assert req.query == "What happened?"
        assert req.chapter_number == 3
        assert req.thread_id is None

    def test_request_with_thread_id(self):
        from app.schemas.reader import ReaderQueryRequest

        req = ReaderQueryRequest(
            query="Who is Jake?",
            book_id="book-1",
            chapter_number=1,
            thread_id="abc-123",
        )
        assert req.thread_id == "abc-123"

    def test_request_rejects_empty_query(self):
        from app.schemas.reader import ReaderQueryRequest

        with pytest.raises(ValidationError):
            ReaderQueryRequest(
                query="",
                book_id="book-1",
                chapter_number=1,
            )

    def test_request_rejects_invalid_chapter(self):
        from app.schemas.reader import ReaderQueryRequest

        with pytest.raises(ValidationError):
            ReaderQueryRequest(
                query="Hi",
                book_id="book-1",
                chapter_number=0,
            )

    def test_response_defaults(self):
        from app.schemas.reader import ReaderQueryResponse

        resp = ReaderQueryResponse(answer="Yes", route="context_qa")
        assert resp.paragraphs_used == 0
        assert resp.entities_found == 0
        assert resp.thread_id is None
