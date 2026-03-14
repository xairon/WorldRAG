"""LangGraph state definition for the reader agent.

NOTE: No `from __future__ import annotations` — LangGraph requires
runtime type hints resolution via get_type_hints().
"""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ReaderAgentState(TypedDict, total=False):
    """Shared state for the reader LangGraph pipeline.

    The reader agent is scoped to a single chapter. It answers questions
    about the current reading position using paragraph text and entity
    annotations as grounding context.
    """

    # -- Conversation --
    messages: Annotated[list[BaseMessage], add_messages]

    # -- Query --
    query: str
    route: str  # context_qa | entity_lookup | summarize

    # -- Chapter scope --
    book_id: str
    chapter_number: int
    max_chapter: int | None  # spoiler guard

    # -- Retrieved context --
    paragraph_context: list[dict[str, Any]]
    entity_annotations: list[dict[str, Any]]
    kg_context: str

    # -- Generation --
    generation: str
    citations: list[dict[str, Any]]
