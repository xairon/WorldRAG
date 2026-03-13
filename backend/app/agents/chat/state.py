"""LangGraph state definition for the chat/RAG pipeline.

NOTE: This file intentionally does NOT use `from __future__ import annotations`
because LangGraph's StateGraph uses get_type_hints() at runtime to resolve
the state schema. Deferred annotations break this resolution.
"""

import operator
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ChatAgentState(TypedDict, total=False):
    """Shared state for the chat/RAG LangGraph pipeline.

    Flows through: router → [kg_query | query_transform → retrieve →
    rerank → context_assembly] → generate → faithfulness_check →
    [END | rewrite → retrieve].
    """

    # -- Conversation (managed by add_messages reducer) --
    messages: Annotated[list[BaseMessage], add_messages]

    # -- Query processing --
    original_query: str
    query: str
    route: str  # kg_query | hybrid_rag | direct
    transformed_queries: list[str]

    # -- Retrieval --
    dense_results: list[dict[str, Any]]
    sparse_results: list[dict[str, Any]]
    graph_results: list[dict[str, Any]]
    fused_results: list[dict[str, Any]]
    reranked_chunks: list[dict[str, Any]]

    # -- KG context --
    kg_entities: list[dict[str, Any]]
    kg_cypher_result: list[dict[str, Any]]

    # -- Generation --
    context: str
    generation: str
    citations: list[dict[str, Any]]

    # -- Quality control --
    faithfulness_score: float
    faithfulness_reason: str
    retries: Annotated[int, operator.add]

    # -- Scope --
    book_id: str
    max_chapter: int | None
