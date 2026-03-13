"""Tests for the chat LangGraph agent graph structure."""
import pytest
from unittest.mock import MagicMock


def test_graph_has_all_nodes():
    """Chat graph contains all expected nodes."""
    from app.agents.chat.graph import build_chat_graph

    mock_repo = MagicMock()
    mock_embedder = MagicMock()
    graph = build_chat_graph(repo=mock_repo, embedder=mock_embedder)

    node_names = set(graph.nodes.keys())
    expected = {
        "router", "query_transform", "retrieve",
        "rerank", "context_assembly", "generate",
        "faithfulness_check", "rewrite_query", "kg_query",
    }
    assert expected <= node_names


def test_graph_compiles():
    """Chat graph compiles without errors."""
    from app.agents.chat.graph import build_chat_graph

    mock_repo = MagicMock()
    mock_embedder = MagicMock()
    graph = build_chat_graph(repo=mock_repo, embedder=mock_embedder)
    compiled = graph.compile()
    assert compiled is not None


def test_route_after_router_kg():
    from app.agents.chat.graph import _route_after_router
    assert _route_after_router({"route": "kg_query"}) == "kg_query"


def test_route_after_router_direct():
    from app.agents.chat.graph import _route_after_router
    assert _route_after_router({"route": "direct"}) == "generate"


def test_route_after_router_hybrid():
    from app.agents.chat.graph import _route_after_router
    assert _route_after_router({"route": "hybrid_rag"}) == "query_transform"


def test_route_after_router_default():
    from app.agents.chat.graph import _route_after_router
    assert _route_after_router({}) == "query_transform"


def test_route_after_kg_fallback():
    from app.agents.chat.graph import _route_after_kg_query
    assert _route_after_kg_query({"route": "hybrid_rag"}) == "query_transform"


def test_route_after_kg_success():
    from app.agents.chat.graph import _route_after_kg_query
    assert _route_after_kg_query({"route": "kg_query"}) == "context_assembly"


def test_route_faithfulness_pass():
    from app.agents.chat.graph import _route_after_faithfulness
    assert _route_after_faithfulness({"faithfulness_score": 0.9, "retries": 0}) == "end"


def test_route_faithfulness_fail_retry():
    from app.agents.chat.graph import _route_after_faithfulness
    assert _route_after_faithfulness({"faithfulness_score": 0.3, "retries": 0}) == "rewrite_query"


def test_route_faithfulness_max_retries():
    from app.agents.chat.graph import _route_after_faithfulness
    assert _route_after_faithfulness({"faithfulness_score": 0.3, "retries": 2}) == "end"
