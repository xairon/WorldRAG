"""Chat/RAG LangGraph: compiles the StateGraph with all nodes and edges."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.chat.state import ChatAgentState
from app.core.logging import get_logger
from app.llm.embeddings import LocalEmbedder

from .nodes.context_assembly import assemble_context
from .nodes.faithfulness import check_faithfulness
from .nodes.generate import generate_answer
from .nodes.kg_query import kg_search
from .nodes.query_transform import transform_query
from .nodes.rerank import rerank_results
from .nodes.retrieve import hybrid_retrieve
from .nodes.rewrite import rewrite_query
from .nodes.router import classify_intent

logger = get_logger(__name__)

FAITHFULNESS_THRESHOLD = 0.6
MAX_RETRIES = 2


def _route_after_router(state: dict[str, Any]) -> str:
    """Conditional edge after router: dispatch to the right path."""
    route = state.get("route", "hybrid_rag")
    if route == "kg_query":
        return "kg_query"
    if route == "direct":
        return "generate"
    return "query_transform"


def _route_after_kg_query(state: dict[str, Any]) -> str:
    """After KG query: if empty results, fallback to hybrid RAG."""
    if state.get("route") == "hybrid_rag":
        return "query_transform"
    return "context_assembly"


def _route_after_generate(state: dict[str, Any]) -> str:
    """After generate: skip faithfulness for direct route (N1 fix)."""
    if state.get("route") == "direct":
        return "end"
    return "faithfulness_check"


def _route_after_faithfulness(state: dict[str, Any]) -> str:
    """After faithfulness check: pass, retry, or give up."""
    score = state.get("faithfulness_score", 0.0)
    retries = state.get("retries", 0)

    if score >= FAITHFULNESS_THRESHOLD:
        return "end"
    if retries >= MAX_RETRIES:
        logger.warning("faithfulness_max_retries", score=score, retries=retries)
        return "end"
    return "rewrite_query"


def build_chat_graph(
    *,
    repo,
    embedder: LocalEmbedder | None = None,
) -> StateGraph:
    """Build the chat agent StateGraph (uncompiled).

    Args:
        repo: Neo4j repository for DB access.
        embedder: Embedding model. If None, creates a default LocalEmbedder.
    """
    if embedder is None:
        embedder = LocalEmbedder()

    # Create node functions that close over repo/embedder
    async def _retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
        queries = state.get("transformed_queries", [state["query"]])
        query_embedding = await embedder.embed_query(queries[0])
        # Pass multi-query variants as extra BM25 arms (C2 audit fix)
        extra_bm25 = queries[1:] if len(queries) > 1 else None
        return {
            "fused_results": await hybrid_retrieve(
                repo,
                query_text=queries[0],
                query_embedding=query_embedding,
                book_id=state["book_id"],
                max_chapter=state.get("max_chapter"),
                extra_bm25_queries=extra_bm25,
            ),
        }

    async def _kg_query_node(state: dict[str, Any]) -> dict[str, Any]:
        return await kg_search(state, repo=repo)

    async def _context_assembly_node(state: dict[str, Any]) -> dict[str, Any]:
        return await assemble_context(state, repo=repo)

    # Build graph
    builder = StateGraph(ChatAgentState)

    # Add nodes
    builder.add_node("router", classify_intent)
    builder.add_node("query_transform", transform_query)
    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("rerank", rerank_results)
    builder.add_node("context_assembly", _context_assembly_node)
    builder.add_node("generate", generate_answer)
    builder.add_node("faithfulness_check", check_faithfulness)
    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("kg_query", _kg_query_node)

    # Edges: START → router
    builder.add_edge(START, "router")

    # Router dispatches to 3 paths
    builder.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "kg_query": "kg_query",
            "query_transform": "query_transform",
            "generate": "generate",
        },
    )

    # KG query path: may fallback to hybrid
    builder.add_conditional_edges(
        "kg_query",
        _route_after_kg_query,
        {
            "context_assembly": "context_assembly",
            "query_transform": "query_transform",
        },
    )

    # Hybrid RAG path
    builder.add_edge("query_transform", "retrieve")
    builder.add_edge("retrieve", "rerank")
    builder.add_edge("rerank", "context_assembly")
    builder.add_edge("context_assembly", "generate")

    # Generation → faithfulness check (or END for direct route — N1 fix)
    builder.add_conditional_edges(
        "generate",
        _route_after_generate,
        {
            "faithfulness_check": "faithfulness_check",
            "end": END,
        },
    )

    # Faithfulness: pass → END, fail → rewrite → retrieve
    builder.add_conditional_edges(
        "faithfulness_check",
        _route_after_faithfulness,
        {
            "end": END,
            "rewrite_query": "rewrite_query",
        },
    )

    # Rewrite loops back to retrieve
    builder.add_edge("rewrite_query", "retrieve")

    return builder
