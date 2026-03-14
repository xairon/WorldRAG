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
    generation_output: dict[str, Any]  # structured output (answer, citations, entities, confidence)
    citations: list[dict[str, Any]]

    # -- Quality control --
    faithfulness_score: float
    faithfulness_reason: str
    faithfulness_grounded: bool
    faithfulness_relevant: bool
    faithfulness_passed: bool
    retries: Annotated[int, operator.add]

    # -- Multi-turn memory --
    conversation_summary: str  # LLM-compressed history (updated every 5 turns)
    entity_memory: list[dict[str, Any]]  # entities tracked across turns
    turn_count: int  # number of human turns in this conversation

    # -- Query expansion --
    hyde_document: str  # hypothetical document for HyDE
    sub_questions: list[str]  # decomposed sub-questions for analytical route

    # -- Retrieval --
    deduplicated_chunks: list[dict[str, Any]]  # chunks after cosine dedup

    # -- Scope --
    book_id: str
    max_chapter: int | None
