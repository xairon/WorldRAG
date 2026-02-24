"""LangGraph state definitions for the extraction pipeline.

Defines the TypedDict state schema used by the extraction StateGraph.
Each pass reads from and writes to a shared state that flows through
the graph nodes.

NOTE: This file intentionally does NOT use `from __future__ import annotations`
because LangGraph's StateGraph uses get_type_hints() at runtime to resolve
the state schema. Deferred annotations break this resolution.
"""

import operator
from typing import Annotated, Any

from typing_extensions import TypedDict

from app.schemas.extraction import (
    CharacterExtractionResult,
    EventExtractionResult,
    GroundedEntity,
    LoreExtractionResult,
    SystemExtractionResult,
)


class ExtractionPipelineState(TypedDict, total=False):
    """Shared state for the extraction pipeline LangGraph.

    Flows through: route -> [passes 1-4 parallel] -> merge -> reconcile.

    Attributes:
        book_id: Book identifier.
        chapter_number: Chapter number being processed.
        chapter_text: Full chapter text.
        chunk_texts: Chunked text segments (if chapter is long).
        regex_matches_json: Pre-extracted regex matches (Passe 0) as JSON.
        genre: Book genre for ontology selection.
        series_name: Series name for series-specific ontology.

        characters: Result from Pass 1.
        systems: Result from Pass 2.
        events: Result from Pass 3.
        lore: Result from Pass 4.

        grounded_entities: All entities with source grounding offsets.
        passes_to_run: Which passes to execute (from router).
        passes_completed: Names of completed passes.
        errors: Errors from each pass.

        total_cost_usd: Accumulated cost across all passes.
        total_entities: Count of all extracted entities.
    """

    # -- Input fields (set before graph invocation) --
    book_id: str
    chapter_number: int
    chapter_text: str
    chunk_texts: list[str]
    regex_matches_json: str
    genre: str
    series_name: str

    # -- Pass results (set by each extraction node) --
    characters: CharacterExtractionResult
    systems: SystemExtractionResult
    events: EventExtractionResult
    lore: LoreExtractionResult

    # -- Grounding (appended by each pass) --
    grounded_entities: Annotated[list[GroundedEntity], operator.add]

    # -- Control flow --
    passes_to_run: list[str]
    passes_completed: Annotated[list[str], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]

    # -- Reconciliation --
    alias_map: dict[str, str]

    # -- Metrics --
    total_cost_usd: float
    total_entities: int
