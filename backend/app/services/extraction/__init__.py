"""Extraction pipeline orchestrator — LangGraph StateGraph.

Builds and compiles the extraction graph that processes each chapter
through 4 parallel extraction passes + mention detection + reconciliation
+ narrative analysis:

  Route → [Pass 1-4 parallel] → Merge → MentionDetect → [Reconcile, Narrative] → END

The router decides which passes to run based on keyword analysis.
Passes run in parallel via LangGraph's Send mechanism.
The merge node combines results, the mention_detect node finds additional
entity mentions by name/alias matching, the reconcile node deduplicates,
and the narrative node detects higher-order narrative structures.

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


# ── Mention detection node ─────────────────────────────────────────────


def _collect_entities_from_state(state: ExtractionPipelineState) -> list[dict]:
    """Collect all extracted entities from the pipeline state into a flat list for mention detection."""
    entities: list[dict] = []

    characters = state.get("characters")
    if characters:
        for c in characters.characters:
            entities.append({
                "canonical_name": c.canonical_name or c.name,
                "name": c.name,
                "entity_type": "character",
                "aliases": c.aliases,
            })

    systems = state.get("systems")
    if systems:
        for s in systems.skills:
            entities.append({
                "canonical_name": s.name,
                "name": s.name,
                "entity_type": "skill",
                "aliases": [],
            })
        for c in systems.classes:
            entities.append({
                "canonical_name": c.name,
                "name": c.name,
                "entity_type": "class",
                "aliases": [],
            })
        for t in systems.titles:
            entities.append({
                "canonical_name": t.name,
                "name": t.name,
                "entity_type": "title",
                "aliases": [],
            })

    lore = state.get("lore")
    if lore:
        for loc in lore.locations:
            entities.append({
                "canonical_name": loc.name,
                "name": loc.name,
                "entity_type": "location",
                "aliases": [],
            })
        for item in lore.items:
            entities.append({
                "canonical_name": item.name,
                "name": item.name,
                "entity_type": "item",
                "aliases": [],
            })
        for cr in lore.creatures:
            entities.append({
                "canonical_name": cr.name,
                "name": cr.name,
                "entity_type": "creature",
                "aliases": [],
            })
        for f in lore.factions:
            entities.append({
                "canonical_name": f.name,
                "name": f.name,
                "entity_type": "faction",
                "aliases": [],
            })
        for co in lore.concepts:
            entities.append({
                "canonical_name": co.name,
                "name": co.name,
                "entity_type": "concept",
                "aliases": [],
            })

    return entities


async def mention_detect_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Run programmatic mention detection + optional coreference.

    After LangExtract passes, find additional entity mentions by name/alias
    matching in chapter text. Optionally resolve pronouns via LLM.
    """
    from app.services.extraction.mention_detector import detect_mentions

    chapter_text = state.get("chapter_text", "")
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    # Collect all extracted entity names from all passes
    entity_list = _collect_entities_from_state(state)

    if not entity_list:
        return {"passes_completed": ["mention_detect"], "errors": []}

    try:
        # Pass 5a: Programmatic mention detection (free)
        mentions = detect_mentions(chapter_text, entity_list)

        logger.info(
            "mention_detect_completed",
            book_id=book_id,
            chapter=chapter_number,
            programmatic_mentions=len(mentions),
        )

        # Pass 5b: LLM-based coreference resolution (optional, non-critical)
        coref_grounded: list = []
        try:
            from app.services.extraction.coreference import resolve_coreferences

            coref_grounded = await resolve_coreferences(chapter_text, entity_list)
            logger.info(
                "coreference_resolved",
                book_id=book_id,
                chapter=chapter_number,
                pronouns_resolved=len(coref_grounded),
            )
        except Exception:
            logger.warning(
                "coreference_skipped",
                book_id=book_id,
                chapter=chapter_number,
                reason="coreference resolution failed (non-critical)",
                exc_info=True,
            )

        all_grounded = mentions + coref_grounded

        return {
            "grounded_entities": all_grounded,
            "passes_completed": ["mention_detect"],
            "errors": [],
        }
    except Exception as e:
        logger.exception(
            "mention_detect_failed",
            book_id=book_id,
            chapter=chapter_number,
        )
        return {
            "grounded_entities": [],
            "passes_completed": [],
            "errors": [{"pass": "mention_detect", "error": str(e)}],
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
    series_entities = state.get("series_entities", [])

    if series_entities:
        logger.info(
            "cross_book_context_available",
            book_id=book_id,
            chapter=chapter_number,
            series_entity_count=len(series_entities),
        )

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


# ── Narrative analysis node ────────────────────────────────────────────


async def narrative_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Run narrative analysis (character arcs, themes, foreshadowing).

    Non-critical pass — failures are logged as warnings and return empty dict.
    Runs in parallel with reconcile after mention_detect.

    Args:
        state: ExtractionPipelineState after mention_detect.

    Returns:
        State update with narrative_analysis dict.
    """
    from app.services.extraction.narrative import analyze_narrative

    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)
    chapter_text = state.get("chapter_text", "")

    try:
        entities = _collect_entities_from_state(state)
        result = await analyze_narrative(chapter_text, entities)

        logger.info(
            "narrative_analysis_completed",
            book_id=book_id,
            chapter=chapter_number,
            character_developments=len(result.character_developments),
            power_changes=len(result.power_changes),
            foreshadowing=len(result.foreshadowing_hints),
            themes=len(result.themes),
        )

        return {
            "narrative_analysis": result.model_dump(),
            "passes_completed": ["narrative"],
        }
    except Exception:
        logger.warning(
            "narrative_analysis_skipped",
            book_id=book_id,
            chapter=chapter_number,
            reason="narrative analysis failed (non-critical)",
            exc_info=True,
        )
        return {
            "narrative_analysis": {},
            "passes_completed": [],
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
        START → route → [characters | systems | events | lore] → merge
          → mention_detect → [reconcile, narrative] → END

    The route node decides which passes to run.
    Selected passes execute in parallel via Send.
    The merge node combines all results.
    The mention_detect node finds additional entity mentions by name/alias matching.
    The reconcile node deduplicates entities (3-tier dedup).
    The narrative node detects higher-order narrative structures (parallel with reconcile).

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
    builder.add_node("mention_detect", mention_detect_node)
    builder.add_node("reconcile", reconcile_in_graph)
    builder.add_node("narrative", narrative_node)

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

    # merge → mention_detect → [reconcile, narrative] → END
    builder.add_edge("merge", "mention_detect")
    builder.add_edge("mention_detect", "reconcile")
    builder.add_edge("mention_detect", "narrative")
    builder.add_edge("reconcile", END)
    builder.add_edge("narrative", END)

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
    series_entities: list[dict] | None = None,
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
        series_entities: Known entities from other books in the same series
            (for cross-book entity resolution). Each dict should have name,
            canonical_name, entity_types, aliases, description.

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
        "series_entities": series_entities or [],
        "grounded_entities": [],
        "passes_to_run": [],
        "passes_completed": [],
        "errors": [],
        "total_cost_usd": 0.0,
        "total_entities": 0,
        "alias_map": {},
        "narrative_analysis": {},
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
