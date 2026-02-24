"""Extraction pipeline orchestrator — LangGraph StateGraph.

Builds and compiles the extraction graph that processes each chapter
through 4 parallel extraction passes + reconciliation:

  Route → [Pass 1-4 parallel] → Merge → Reconcile → END

The router decides which passes to run based on keyword analysis.
Passes run in parallel via LangGraph's Send mechanism.
The merge node combines results and the reconcile node deduplicates.

Usage:
    graph = build_extraction_graph()
    result = await graph.ainvoke({
        "book_id": "abc123",
        "chapter_number": 42,
        "chapter_text": "...",
        "genre": "litrpg",
    })
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.state import ExtractionPipelineState
from app.core.logging import get_logger
from app.schemas.extraction import (
    ChapterExtractionResult,
    CharacterExtractionResult,
    EventExtractionResult,
    LoreExtractionResult,
    SystemExtractionResult,
)
from app.services.extraction.characters import extract_characters
from app.services.extraction.events import extract_events
from app.services.extraction.lore import extract_lore
from app.services.extraction.router import route_extraction_passes
from app.services.extraction.systems import extract_systems

logger = get_logger(__name__)


# ── Merge node ──────────────────────────────────────────────────────────


async def merge_results(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Merge all pass results and compute final metrics.

    Counts total entities, accumulates costs, and logs the final summary.

    Args:
        state: ExtractionPipelineState with all passes completed.

    Returns:
        State update with total_entities and total_cost_usd.
    """
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    # Count all extracted entities
    total = 0

    characters = state.get("characters")
    if characters:
        total += len(characters.characters) + len(characters.relationships)

    systems = state.get("systems")
    if systems:
        total += (
            len(systems.skills)
            + len(systems.classes)
            + len(systems.titles)
            + len(systems.level_changes)
            + len(systems.stat_changes)
        )

    events = state.get("events")
    if events:
        total += len(events.events)

    lore = state.get("lore")
    if lore:
        total += (
            len(lore.locations)
            + len(lore.items)
            + len(lore.creatures)
            + len(lore.factions)
            + len(lore.concepts)
        )

    grounded = state.get("grounded_entities", [])
    passes_completed = state.get("passes_completed", [])
    errors = state.get("errors", [])

    logger.info(
        "extraction_merge_completed",
        book_id=book_id,
        chapter=chapter_number,
        total_entities=total,
        grounded_entities=len(grounded),
        passes_completed=passes_completed,
        errors_count=len(errors),
    )

    return {
        "total_entities": total,
    }


# ── Reconcile node ─────────────────────────────────────────────────────


async def reconcile_in_graph(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Run 3-tier dedup on all extracted entities.

    Builds a temporary ChapterExtractionResult from state, runs the
    reconciler, and returns the alias_map for downstream use.

    Args:
        state: ExtractionPipelineState after merge.

    Returns:
        State update with alias_map.
    """
    from app.services.extraction.reconciler import reconcile_chapter_result

    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    # Build temporary result from state for reconciliation
    temp_result = ChapterExtractionResult(
        book_id=book_id,
        chapter_number=chapter_number,
        characters=state.get("characters", CharacterExtractionResult()),
        systems=state.get("systems", SystemExtractionResult()),
        events=state.get("events", EventExtractionResult()),
        lore=state.get("lore", LoreExtractionResult()),
    )

    try:
        reconciliation = await reconcile_chapter_result(temp_result)
        alias_map = reconciliation.alias_map

        logger.info(
            "extraction_reconcile_completed",
            book_id=book_id,
            chapter=chapter_number,
            aliases_resolved=len(alias_map),
        )
    except Exception:
        logger.exception(
            "extraction_reconcile_failed",
            book_id=book_id,
            chapter=chapter_number,
        )
        alias_map = {}

    return {
        "alias_map": alias_map,
        "passes_completed": ["reconcile"],
    }


# ── Fan-out routing ─────────────────────────────────────────────────────


def fan_out_to_passes(state: ExtractionPipelineState) -> list[Send]:
    """LangGraph conditional edge: Fan out to selected extraction passes.

    Uses the passes_to_run list from the router to create parallel
    Send operations to each pass node.

    Args:
        state: State with passes_to_run populated by router.

    Returns:
        List of Send objects for parallel execution.
    """
    passes_to_run = state.get("passes_to_run", ["characters"])
    sends: list[Send] = []

    for pass_name in passes_to_run:
        sends.append(Send(pass_name, state))

    return sends


# ── Graph builder ───────────────────────────────────────────────────────


def build_extraction_graph() -> StateGraph:
    """Build and compile the extraction pipeline LangGraph.

    Graph structure:
        START → route → [characters | systems | events | lore] → merge → reconcile → END

    The route node decides which passes to run.
    Selected passes execute in parallel via Send.
    The merge node combines all results.
    The reconcile node deduplicates entities (3-tier dedup).

    Returns:
        Compiled LangGraph StateGraph.
    """
    builder = StateGraph(ExtractionPipelineState)

    # ── Add nodes ──
    builder.add_node("route", route_extraction_passes)
    builder.add_node("characters", extract_characters)
    builder.add_node("systems", extract_systems)
    builder.add_node("events", extract_events)
    builder.add_node("lore", extract_lore)
    builder.add_node("merge", merge_results)
    builder.add_node("reconcile", reconcile_in_graph)

    # ── Edges ──
    # START → route
    builder.add_edge(START, "route")

    # route → fan-out to selected passes
    builder.add_conditional_edges("route", fan_out_to_passes)

    # All passes → merge
    builder.add_edge("characters", "merge")
    builder.add_edge("systems", "merge")
    builder.add_edge("events", "merge")
    builder.add_edge("lore", "merge")

    # merge → reconcile → END
    builder.add_edge("merge", "reconcile")
    builder.add_edge("reconcile", END)

    graph = builder.compile()

    logger.info("extraction_graph_built")
    return graph


# Pre-build and cache the extraction graph at module level
_extraction_graph = build_extraction_graph()


# ── High-level extraction function ──────────────────────────────────────


async def extract_chapter(
    chapter_text: str,
    book_id: str,
    chapter_number: int,
    genre: str = "litrpg",
    series_name: str = "",
    regex_matches_json: str = "[]",
) -> ChapterExtractionResult:
    """Extract all entities from a single chapter.

    High-level entry point that invokes the LangGraph extraction pipeline
    and returns a structured ChapterExtractionResult.

    Args:
        chapter_text: Full text of the chapter.
        book_id: Book identifier.
        chapter_number: Chapter number.
        genre: Book genre for ontology selection.
        series_name: Series name for series-specific patterns.
        regex_matches_json: Pre-extracted regex matches JSON (Passe 0).

    Returns:
        ChapterExtractionResult with all extracted entities.
    """
    initial_state: dict[str, Any] = {
        "book_id": book_id,
        "chapter_number": chapter_number,
        "chapter_text": chapter_text,
        "chunk_texts": [],
        "regex_matches_json": regex_matches_json,
        "genre": genre,
        "series_name": series_name,
        "grounded_entities": [],
        "passes_to_run": [],
        "passes_completed": [],
        "errors": [],
        "total_cost_usd": 0.0,
        "total_entities": 0,
        "alias_map": {},
    }

    logger.info(
        "chapter_extraction_started",
        book_id=book_id,
        chapter=chapter_number,
        text_length=len(chapter_text),
    )

    final_state = await _extraction_graph.ainvoke(initial_state)

    # Build result from final state
    result = ChapterExtractionResult(
        book_id=book_id,
        chapter_number=chapter_number,
        characters=final_state.get("characters", CharacterExtractionResult()),
        systems=final_state.get("systems", SystemExtractionResult()),
        events=final_state.get("events", EventExtractionResult()),
        lore=final_state.get("lore", LoreExtractionResult()),
        grounded_entities=final_state.get("grounded_entities", []),
        alias_map=final_state.get("alias_map", {}),
        total_entities=final_state.get("total_entities", 0),
        total_cost_usd=final_state.get("total_cost_usd", 0.0),
        passes_completed=final_state.get("passes_completed", []),
    )

    result.count_entities()

    logger.info(
        "chapter_extraction_completed",
        book_id=book_id,
        chapter=chapter_number,
        total_entities=result.total_entities,
        passes=result.passes_completed,
        grounded=len(result.grounded_entities),
        aliases=len(final_state.get("alias_map", {})),
    )

    return result
