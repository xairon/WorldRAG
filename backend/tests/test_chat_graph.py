"""Tests for the chat LangGraph agent graph structure."""

from unittest.mock import MagicMock


def test_graph_has_all_nodes():
    """Chat graph contains all expected nodes."""
    from app.agents.chat.graph import build_chat_graph

    mock_repo = MagicMock()
    mock_embedder = MagicMock()
    graph = build_chat_graph(repo=mock_repo, embedder=mock_embedder)

    node_names = set(graph.nodes.keys())
    expected = {
        "router",
        "query_transform",
        "retrieve",
        "rerank",
        "context_assembly",
        "generate",
        "faithfulness_check",
        "rewrite_query",
        "kg_query",
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


# ---------------------------------------------------------------------------
# N1 regression: _route_after_generate skips faithfulness for direct route
# ---------------------------------------------------------------------------


def test_route_after_generate_direct_skips_faithfulness():
    """N1 fix: direct route goes straight to END, skipping faithfulness."""
    from app.agents.chat.graph import _route_after_generate

    assert _route_after_generate({"route": "direct"}) == "end"


def test_route_after_generate_hybrid_goes_to_faithfulness():
    """N1 fix: non-direct routes still pass through faithfulness check."""
    from app.agents.chat.graph import _route_after_generate

    assert _route_after_generate({"route": "hybrid_rag"}) == "faithfulness_check"
    assert _route_after_generate({"route": "kg_query"}) == "faithfulness_check"
    assert _route_after_generate({}) == "faithfulness_check"


# ---------------------------------------------------------------------------
# N3 regression: missing faithfulness_score defaults to 0.0 → rewrite
# ---------------------------------------------------------------------------


def test_route_faithfulness_missing_score_defaults_to_rewrite():
    """N3 fix: empty state (no score) defaults to 0.0 → triggers rewrite, not pass."""
    from app.agents.chat.graph import _route_after_faithfulness

    # No faithfulness_score key at all → default 0.0 < threshold → rewrite
    assert _route_after_faithfulness({}) == "rewrite_query"
    assert _route_after_faithfulness({"retries": 0}) == "rewrite_query"


def test_route_faithfulness_missing_score_with_max_retries_ends():
    """N3 fix: missing score + max retries → end (give up)."""
    from app.agents.chat.graph import _route_after_faithfulness

    assert _route_after_faithfulness({"retries": 2}) == "end"
