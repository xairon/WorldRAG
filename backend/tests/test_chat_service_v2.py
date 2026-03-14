"""Tests for ChatServiceV2 — Graphiti-based chat service.

TDD: tests written before implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import ChatResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_graphiti():
    """Minimal Graphiti client mock."""
    g = MagicMock()
    g.search = AsyncMock(return_value=[])
    return g


@pytest.fixture
def mock_neo4j_driver():
    """Minimal Neo4j driver mock."""
    return MagicMock()


@pytest.fixture
def mock_compiled_graph():
    """Mock compiled LangGraph returned by builder.compile()."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(
        return_value={
            "generation": "Ilea is an Ashen Healer.",
            "retrieved_context": [
                {"fact": "Ilea: Ashen Healer", "source": "Ilea", "target": ""},
                {"fact": "Ilea is level 400", "source": "Ilea", "target": ""},
            ],
            "faithfulness_score": 0.8,
        }
    )
    return graph


@pytest.fixture
def mock_graph_builder(mock_compiled_graph):
    """Mock uncompiled StateGraph builder."""
    builder = MagicMock()
    builder.compile.return_value = mock_compiled_graph
    return builder


# ---------------------------------------------------------------------------
# W4.1 — __init__ builds and compiles the graph
# ---------------------------------------------------------------------------


class TestChatServiceV2Init:
    """test_init builds graph: __init__ calls build_chat_v2_graph and compiles."""

    def test_init_builds_and_compiles_graph(
        self, mock_graphiti, mock_neo4j_driver, mock_graph_builder
    ) -> None:
        """__init__ must call build_chat_v2_graph and compile the builder."""
        with patch(
            "app.services.chat_service_v2.build_chat_v2_graph",
            return_value=mock_graph_builder,
        ) as mock_build:
            from app.services.chat_service_v2 import ChatServiceV2

            service = ChatServiceV2(mock_graphiti, mock_neo4j_driver)

        mock_build.assert_called_once_with(
            graphiti=mock_graphiti, neo4j_driver=mock_neo4j_driver
        )
        mock_graph_builder.compile.assert_called_once()
        assert service._graph is mock_graph_builder.compile.return_value

    def test_init_passes_checkpointer_to_compile(
        self, mock_graphiti, mock_neo4j_driver, mock_graph_builder
    ) -> None:
        """When checkpointer is provided, compile() receives it."""
        checkpointer = MagicMock()
        with patch(
            "app.services.chat_service_v2.build_chat_v2_graph",
            return_value=mock_graph_builder,
        ):
            from app.services.chat_service_v2 import ChatServiceV2

            ChatServiceV2(mock_graphiti, mock_neo4j_driver, checkpointer=checkpointer)

        mock_graph_builder.compile.assert_called_once_with(checkpointer=checkpointer)

    def test_init_without_checkpointer_compiles_with_none(
        self, mock_graphiti, mock_neo4j_driver, mock_graph_builder
    ) -> None:
        """When no checkpointer, compile() is called with checkpointer=None."""
        with patch(
            "app.services.chat_service_v2.build_chat_v2_graph",
            return_value=mock_graph_builder,
        ):
            from app.services.chat_service_v2 import ChatServiceV2

            ChatServiceV2(mock_graphiti, mock_neo4j_driver)

        mock_graph_builder.compile.assert_called_once_with(checkpointer=None)


# ---------------------------------------------------------------------------
# W4.2 — query() returns ChatResponse
# ---------------------------------------------------------------------------


class TestChatServiceV2Query:
    """test_query_returns_chat_response: query() maps graph output to ChatResponse."""

    @pytest.fixture
    def service(self, mock_graphiti, mock_neo4j_driver, mock_graph_builder):
        with patch(
            "app.services.chat_service_v2.build_chat_v2_graph",
            return_value=mock_graph_builder,
        ):
            from app.services.chat_service_v2 import ChatServiceV2

            return ChatServiceV2(mock_graphiti, mock_neo4j_driver)

    @pytest.mark.asyncio
    async def test_query_returns_chat_response(self, service) -> None:
        """query() must return a ChatResponse instance."""
        result = await service.query(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        )
        assert isinstance(result, ChatResponse)

    @pytest.mark.asyncio
    async def test_query_answer_from_generation(self, service) -> None:
        """answer field is taken from state['generation']."""
        result = await service.query(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        )
        assert result.answer == "Ilea is an Ashen Healer."

    @pytest.mark.asyncio
    async def test_query_chunks_retrieved_from_context(self, service) -> None:
        """chunks_retrieved equals len(retrieved_context)."""
        result = await service.query(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        )
        assert result.chunks_retrieved == 2
        assert result.chunks_after_rerank == 2

    @pytest.mark.asyncio
    async def test_query_confidence_from_faithfulness_score(self, service) -> None:
        """confidence maps to faithfulness_score from state."""
        result = await service.query(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        )
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_query_thread_id_propagated(
        self, service, mock_compiled_graph
    ) -> None:
        """thread_id is set in config.configurable and returned in response."""
        result = await service.query(
            "What is Ilea's class?",
            book_id="book-1",
            saga_id="saga-1",
            thread_id="thread-xyz",
        )
        assert result.thread_id == "thread-xyz"

        call_kwargs = mock_compiled_graph.ainvoke.call_args
        config = call_kwargs.kwargs.get("config", call_kwargs[1].get("config", {}))
        assert config.get("configurable", {}).get("thread_id") == "thread-xyz"

    @pytest.mark.asyncio
    async def test_query_no_thread_id_uses_empty_config(
        self, service, mock_compiled_graph
    ) -> None:
        """When no thread_id, config has no configurable key."""
        await service.query("What is Ilea's class?", book_id="book-1", saga_id="saga-1")

        call_kwargs = mock_compiled_graph.ainvoke.call_args
        config = call_kwargs.kwargs.get("config", call_kwargs[1].get("config", {}))
        assert "configurable" not in config

    @pytest.mark.asyncio
    async def test_query_state_includes_saga_id(
        self, service, mock_compiled_graph
    ) -> None:
        """The state_input passed to ainvoke must include saga_id."""
        await service.query(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-42"
        )

        call_args = mock_compiled_graph.ainvoke.call_args
        state_input = call_args.args[0] if call_args.args else call_args[0][0]
        assert state_input["saga_id"] == "saga-42"
        assert state_input["book_id"] == "book-1"

    @pytest.mark.asyncio
    async def test_query_fallback_answer_when_generation_missing(
        self, service, mock_compiled_graph
    ) -> None:
        """When graph returns no generation, a fallback message is used."""
        mock_compiled_graph.ainvoke.return_value = {
            "generation": "",
            "retrieved_context": [],
            "faithfulness_score": 0.0,
        }
        result = await service.query(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        )
        assert isinstance(result, ChatResponse)
        assert "wasn't able" in result.answer.lower() or len(result.answer) > 0

    @pytest.mark.asyncio
    async def test_query_max_chapter_passed_to_state(
        self, service, mock_compiled_graph
    ) -> None:
        """max_chapter is forwarded in state_input."""
        await service.query(
            "What is Ilea's class?",
            book_id="book-1",
            saga_id="saga-1",
            max_chapter=10,
        )
        call_args = mock_compiled_graph.ainvoke.call_args
        state_input = call_args.args[0] if call_args.args else call_args[0][0]
        assert state_input["max_chapter"] == 10


# ---------------------------------------------------------------------------
# W4.3 — query_stream() yields SSE events
# ---------------------------------------------------------------------------


class TestChatServiceV2Stream:
    """query_stream() yields dicts with 'event' and 'data' keys."""

    @pytest.fixture
    def service(self, mock_graphiti, mock_neo4j_driver, mock_graph_builder):
        with patch(
            "app.services.chat_service_v2.build_chat_v2_graph",
            return_value=mock_graph_builder,
        ):
            from app.services.chat_service_v2 import ChatServiceV2

            return ChatServiceV2(mock_graphiti, mock_neo4j_driver)

    @pytest.mark.asyncio
    async def test_stream_yields_done_event(
        self, service, mock_compiled_graph
    ) -> None:
        """query_stream() must yield a 'done' event at the end."""
        # astream yields nothing, then we get done
        async def _empty_astream(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_compiled_graph.astream = _empty_astream

        events = []
        async for event in service.query_stream(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        ):
            events.append(event)

        assert any(e["event"] == "done" for e in events)

    @pytest.mark.asyncio
    async def test_stream_yields_error_event_on_exception(
        self, service, mock_compiled_graph
    ) -> None:
        """query_stream() yields an 'error' event when astream raises."""

        async def _raising_astream(*args, **kwargs):
            raise RuntimeError("test error")
            yield  # make it an async generator

        mock_compiled_graph.astream = _raising_astream

        events = []
        async for event in service.query_stream(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        ):
            events.append(event)

        assert any(e["event"] == "error" for e in events)

    @pytest.mark.asyncio
    async def test_stream_all_events_have_event_and_data_keys(
        self, service, mock_compiled_graph
    ) -> None:
        """Every yielded item must have 'event' and 'data' keys."""
        async def _empty_astream(*args, **kwargs):
            return
            yield

        mock_compiled_graph.astream = _empty_astream

        async for event in service.query_stream(
            "What is Ilea's class?", book_id="book-1", saga_id="saga-1"
        ):
            assert "event" in event
            assert "data" in event
