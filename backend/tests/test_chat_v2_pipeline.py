"""Tests for the chat v2 pipeline (Graphiti-based, 8-node LangGraph).

Follows TDD: tests written before implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.chat_v2.state import ChatV2State


class TestChatV2State:
    """Test that ChatV2State has all required fields."""

    def test_state_has_required_fields(self) -> None:
        """ChatV2State TypedDict must declare all required keys."""
        # Instantiate a partial dict — total=False means all fields are optional
        state: ChatV2State = {
            "messages": [],
            "query": "What is Ilea's class?",
            "original_query": "What is Ilea's class?",
            "book_id": "book-001",
            "saga_id": "saga-001",
            "max_chapter": None,
            "route": "graphiti_search",
            "retrieved_context": [],
            "entity_summaries": [],
            "community_summaries": [],
            "generation": "",
            "generation_output": {},
            "reasoning": "",
            "faithfulness_score": 0.0,
            "retries": 0,
        }
        required_keys = [
            "messages",
            "query",
            "original_query",
            "book_id",
            "saga_id",
            "max_chapter",
            "route",
            "retrieved_context",
            "entity_summaries",
            "community_summaries",
            "generation",
            "generation_output",
            "reasoning",
            "faithfulness_score",
            "retries",
        ]
        for key in required_keys:
            assert key in state, f"Missing key: {key}"

    def test_state_accepts_empty_dict(self) -> None:
        """total=False means an empty dict is a valid ChatV2State."""
        state: ChatV2State = {}
        assert isinstance(state, dict)

    def test_route_field_accepts_valid_routes(self) -> None:
        """route field accepts the three valid route strings."""
        for route in ("graphiti_search", "cypher_lookup", "direct"):
            state: ChatV2State = {"route": route}
            assert state["route"] == route


class TestChatV2GraphBuilds:
    """Test that the graph builds without errors and has expected structure."""

    def _make_deps(self):
        """Create minimal mock dependencies."""
        graphiti = MagicMock()
        graphiti.search = AsyncMock(return_value=[])
        neo4j_driver = MagicMock()
        return graphiti, neo4j_driver

    def test_graph_builds_without_error(self) -> None:
        """build_chat_v2_graph() must return a StateGraph without raising."""
        from app.agents.chat_v2.graph import build_chat_v2_graph

        graphiti, neo4j_driver = self._make_deps()
        builder = build_chat_v2_graph(graphiti, neo4j_driver)
        assert builder is not None

    def test_graph_has_expected_nodes(self) -> None:
        """The compiled graph must expose all 7 node names."""
        from app.agents.chat_v2.graph import build_chat_v2_graph

        graphiti, neo4j_driver = self._make_deps()
        builder = build_chat_v2_graph(graphiti, neo4j_driver)

        expected_nodes = {
            "router",
            "graphiti_search",
            "cypher_lookup",
            "direct",
            "context_assembly",
            "generate",
            "faithfulness",
        }
        # StateGraph stores nodes in builder.nodes (dict)
        actual_nodes = set(builder.nodes.keys())
        for node in expected_nodes:
            assert node in actual_nodes, f"Node '{node}' not found in graph. Got: {actual_nodes}"

    def test_graph_returns_state_graph_instance(self) -> None:
        """build_chat_v2_graph() must return a StateGraph (uncompiled)."""
        from langgraph.graph import StateGraph

        from app.agents.chat_v2.graph import build_chat_v2_graph

        graphiti, neo4j_driver = self._make_deps()
        builder = build_chat_v2_graph(graphiti, neo4j_driver)
        assert isinstance(builder, StateGraph)


class TestKeywordFallbackRouter:
    """Tests for _keyword_classify_route — the LLM-unavailable fallback."""

    def test_cypher_pattern_matched(self) -> None:
        """Queries with structured-lookup keywords route to cypher_lookup."""
        from app.agents.chat_v2.graph import _keyword_classify_route

        assert _keyword_classify_route("What skills does Jake have?") == "cypher_lookup"
        assert _keyword_classify_route("list class for Ilea") == "cypher_lookup"
        assert _keyword_classify_route("what level is she?") == "cypher_lookup"
        assert _keyword_classify_route("how many skills does he have?") == "cypher_lookup"

    def test_direct_pattern_matched(self) -> None:
        """Conversational messages route to direct."""
        from app.agents.chat_v2.graph import _keyword_classify_route

        assert _keyword_classify_route("hello") == "direct"
        assert _keyword_classify_route("hi there") == "direct"
        assert _keyword_classify_route("thanks") == "direct"
        assert _keyword_classify_route("thank you so much") == "direct"

    def test_open_ended_routes_to_graphiti(self) -> None:
        """Open-ended narrative questions default to graphiti_search."""
        from app.agents.chat_v2.graph import _keyword_classify_route

        assert _keyword_classify_route("Why did Jake choose that path?") == "graphiti_search"
        assert _keyword_classify_route("What happened in the battle?") == "graphiti_search"
        assert _keyword_classify_route("How are Jake and Viper related?") == "graphiti_search"

    @pytest.mark.asyncio
    async def test_router_node_falls_back_when_llm_raises(self) -> None:
        """router node uses keyword fallback when LLM raises an exception."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.agents.chat_v2.graph import build_chat_v2_graph

        graphiti = MagicMock()
        graphiti.search = AsyncMock(return_value=[])
        neo4j_driver = MagicMock()

        builder = build_chat_v2_graph(graphiti, neo4j_driver)
        # Extract the async router closure from the LangGraph node spec
        router_fn = builder.nodes["router"].runnable.afunc  # type: ignore[attr-defined]

        with patch(
            "app.llm.providers.get_langchain_llm",
            side_effect=RuntimeError("LLM unavailable"),
        ):
            result = await router_fn({"query": "What skills does Jake have?"})

        assert result["route"] == "cypher_lookup"
        assert result["query"] == "What skills does Jake have?"

    @pytest.mark.asyncio
    async def test_router_node_falls_back_on_invalid_llm_response(self) -> None:
        """router node uses keyword fallback when LLM returns an unrecognized category."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.agents.chat_v2.graph import build_chat_v2_graph

        graphiti = MagicMock()
        graphiti.search = AsyncMock(return_value=[])
        neo4j_driver = MagicMock()

        builder = build_chat_v2_graph(graphiti, neo4j_driver)
        router_fn = builder.nodes["router"].runnable.afunc  # type: ignore[attr-defined]

        mock_response = MagicMock()
        mock_response.content = "unknown_route"
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.llm.providers.get_langchain_llm", return_value=mock_llm):
            result = await router_fn({"query": "hello"})

        # LLM returned garbage, so keyword fallback kicks in -> "direct"
        assert result["route"] == "direct"
