"""Reader LangGraph: compiles the StateGraph for chapter-scoped Q&A."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.reader.state import ReaderAgentState
from app.core.logging import get_logger

from .nodes.reader_generate import generate_reader_answer
from .nodes.reader_retrieve import retrieve_chapter_context
from .nodes.reader_router import classify_reader_intent

logger = get_logger(__name__)


def build_reader_graph(*, repo) -> StateGraph:
    """Build the reader agent StateGraph (uncompiled).

    Simple 3-node pipeline: router -> retrieve -> generate.
    All routes go through retrieve since we always need chapter context.
    """

    async def _retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
        return await retrieve_chapter_context(state, repo=repo)

    builder = StateGraph(ReaderAgentState)

    builder.add_node("router", classify_reader_intent)
    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("generate", generate_reader_answer)

    builder.add_edge(START, "router")
    builder.add_edge("router", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)

    return builder
