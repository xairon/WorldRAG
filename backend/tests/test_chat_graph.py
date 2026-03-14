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
        "load_memory",
        "summarize_memory",
        "router",
        "query_transform",
        "hyde_expand",
        "retrieve",
        "rerank",
        "dedup_chunks",
        "temporal_sort",
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


# ---------------------------------------------------------------------------
# _route_after_router: 6-route → 3-path mapping
# ---------------------------------------------------------------------------


def test_route_after_router_factual_lookup():
    from app.agents.chat.graph import _route_after_router

    assert _route_after_router({"route": "factual_lookup"}) == "kg_query"


def test_route_after_router_conversational():
    from app.agents.chat.graph import _route_after_router

    assert _route_after_router({"route": "conversational"}) == "generate"


def test_route_after_router_hybrid_routes():
    from app.agents.chat.graph import _route_after_router

    for route in ("entity_qa", "relationship_qa", "timeline_qa", "analytical"):
        assert _route_after_router({"route": route}) == "query_transform", route


def test_route_after_router_default():
    from app.agents.chat.graph import _route_after_router

    assert _route_after_router({}) == "query_transform"


# ---------------------------------------------------------------------------
# _route_after_kg_query: fallback on empty results
# ---------------------------------------------------------------------------


def test_route_after_kg_fallback_on_empty_entities():
    from app.agents.chat.graph import _route_after_kg_query

    assert _route_after_kg_query({"kg_entities": []}) == "query_transform"
    assert _route_after_kg_query({}) == "query_transform"


def test_route_after_kg_success():
    from app.agents.chat.graph import _route_after_kg_query

    assert _route_after_kg_query({"kg_entities": [{"name": "Jake"}]}) == "context_assembly"


# ---------------------------------------------------------------------------
# _route_after_faithfulness: now routes to summarize_memory (not END)
# ---------------------------------------------------------------------------


def test_route_faithfulness_pass():
    from app.agents.chat.graph import _route_after_faithfulness

    assert _route_after_faithfulness({"faithfulness_score": 0.9, "retries": 0}) == "summarize_memory"


def test_route_faithfulness_fail_retry():
    from app.agents.chat.graph import _route_after_faithfulness

    assert _route_after_faithfulness({"faithfulness_score": 0.3, "retries": 0}) == "rewrite_query"


def test_route_faithfulness_max_retries():
    from app.agents.chat.graph import _route_after_faithfulness

    assert _route_after_faithfulness({"faithfulness_score": 0.3, "retries": 2}) == "summarize_memory"


# ---------------------------------------------------------------------------
# _route_after_generate: conversational skips faithfulness
# ---------------------------------------------------------------------------


def test_route_after_generate_conversational_skips_faithfulness():
    """conversational route goes straight to summarize_memory, skipping faithfulness."""
    from app.agents.chat.graph import _route_after_generate

    assert _route_after_generate({"route": "conversational"}) == "summarize_memory"


def test_route_after_generate_other_routes_go_to_faithfulness():
    from app.agents.chat.graph import _route_after_generate

    for route in ("factual_lookup", "entity_qa", "relationship_qa", "timeline_qa", "analytical", ""):
        assert _route_after_generate({"route": route}) == "faithfulness_check", route

    assert _route_after_generate({}) == "faithfulness_check"


# ---------------------------------------------------------------------------
# N3 regression: missing faithfulness_score defaults to 0.0 → rewrite
# ---------------------------------------------------------------------------


def test_route_faithfulness_missing_score_defaults_to_rewrite():
    """N3 fix: empty state (no score) defaults to 0.0 → triggers rewrite, not pass."""
    from app.agents.chat.graph import _route_after_faithfulness

    assert _route_after_faithfulness({}) == "rewrite_query"
    assert _route_after_faithfulness({"retries": 0}) == "rewrite_query"


def test_route_faithfulness_missing_score_with_max_retries_ends():
    """N3 fix: missing score + max retries → summarize_memory (give up)."""
    from app.agents.chat.graph import _route_after_faithfulness

    assert _route_after_faithfulness({"retries": 2}) == "summarize_memory"
