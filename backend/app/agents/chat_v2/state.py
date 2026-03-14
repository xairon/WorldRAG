"""LangGraph state definition for the chat v2 / Graphiti-based pipeline.

NOTE: This file intentionally does NOT use `from __future__ import annotations`
because LangGraph's StateGraph uses get_type_hints() at runtime to resolve
the state schema. Deferred annotations break this resolution.
"""

from typing import Any

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class ChatV2State(TypedDict, total=False):
    """Shared state for the chat v2 LangGraph pipeline (Graphiti-based).

    Flows through:
      router → [graphiti_search | cypher_lookup | direct]
             → context_assembly → generate → faithfulness → [END | graphiti_search]
    """

    # -- Conversation --
    messages: list[BaseMessage]

    # -- Query processing --
    query: str
    original_query: str

    # -- Scope --
    book_id: str
    saga_id: str
    max_chapter: int | None

    # -- Routing --
    route: str  # "graphiti_search" | "cypher_lookup" | "direct"

    # -- Retrieval --
    retrieved_context: list[dict[str, Any]]
    entity_summaries: list[dict[str, Any]]
    community_summaries: list[str]

    # -- Generation --
    generation: str
    generation_output: dict[str, Any]
    reasoning: str

    # -- Quality control --
    faithfulness_score: float
    retries: int
