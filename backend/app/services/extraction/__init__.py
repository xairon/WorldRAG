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

import json
import uuid
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph  # noqa: TC002
from langgraph.types import Send

from app.agents.state import ExtractionPipelineState
from app.core.logging import get_logger
from app.schemas.extraction import (
    ChapterExtractionResult,
    CharacterExtractionResult,
    EventExtractionResult,
    Layer3ExtractionResult,
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
    """Collect all extracted entities from the pipeline state.

    Returns a flat list for mention detection.
    """
    entities: list[dict] = []

    characters = state.get("characters")
    if characters:
        for c in characters.characters:
            entities.append(
                {
                    "canonical_name": c.canonical_name or c.name,
                    "name": c.name,
                    "entity_type": "character",
                    "aliases": c.aliases,
                }
            )

    systems = state.get("systems")
    if systems:
        for s in systems.skills:
            entities.append(
                {
                    "canonical_name": s.name,
                    "name": s.name,
                    "entity_type": "skill",
                    "aliases": [],
                }
            )
        for c in systems.classes:
            entities.append(
                {
                    "canonical_name": c.name,
                    "name": c.name,
                    "entity_type": "class",
                    "aliases": [],
                }
            )
        for t in systems.titles:
            entities.append(
                {
                    "canonical_name": t.name,
                    "name": t.name,
                    "entity_type": "title",
                    "aliases": [],
                }
            )

    lore = state.get("lore")
    if lore:
        for loc in lore.locations:
            entities.append(
                {
                    "canonical_name": loc.name,
                    "name": loc.name,
                    "entity_type": "location",
                    "aliases": [],
                }
            )
        for item in lore.items:
            entities.append(
                {
                    "canonical_name": item.name,
                    "name": item.name,
                    "entity_type": "item",
                    "aliases": [],
                }
            )
        for cr in lore.creatures:
            entities.append(
                {
                    "canonical_name": cr.name,
                    "name": cr.name,
                    "entity_type": "creature",
                    "aliases": [],
                }
            )
        for f in lore.factions:
            entities.append(
                {
                    "canonical_name": f.name,
                    "name": f.name,
                    "entity_type": "faction",
                    "aliases": [],
                }
            )
        for co in lore.concepts:
            entities.append(
                {
                    "canonical_name": co.name,
                    "name": co.name,
                    "entity_type": "concept",
                    "aliases": [],
                }
            )

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
            "errors": [{"pass": "mention_detect", "error": type(e).__name__}],
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

        # Cross-book entity resolution: match chapter entities to known series entities
        if series_entities:
            series_name_map: dict[str, str] = {}
            for se in series_entities:
                canonical = se.get("canonical_name") or se.get("name", "")
                name = se.get("name", "")
                if canonical:
                    series_name_map[name.lower()] = canonical
                    series_name_map[canonical.lower()] = canonical

            cross_book_aliases = 0
            for char in temp_result.characters.characters:
                lower_name = char.name.lower()
                if lower_name in series_name_map and series_name_map[lower_name] != char.name:
                    alias_map[char.name] = series_name_map[lower_name]
                    cross_book_aliases += 1

            if cross_book_aliases:
                logger.info(
                    "cross_book_aliases_resolved",
                    book_id=book_id,
                    chapter=chapter_number,
                    count=cross_book_aliases,
                )

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


def build_extraction_graph() -> CompiledStateGraph:
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


# ════════════════════════════════════════════════════════════════════════
# V3 — 6-Phase Extraction Pipeline
# ════════════════════════════════════════════════════════════════════════
#
# Phase 0: regex_extract ($0, deterministic)
# Phase 1: narrative extraction (characters, events, world) — Layer 1 ontology
# Phase 2: genre extraction (progression, creatures) — Layer 2 ontology, conditional
# Phase 3: series extraction — Layer 3 ontology, conditional
# Phase 4: reconciliation (3-tier dedup + cross-book)
# Phase 5: grounding + mention detection + registry update
# ════════════════════════════════════════════════════════════════════════

# ── Phase 0: Regex extraction node ────────────────────────────────────


def regex_extract_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 0: Run regex patterns from ontology ($0).

    Currently a pass-through — regex extraction is performed before graph
    invocation and passed in as regex_matches_json. This node normalizes
    the JSON string into the structured phase0_regex state field.

    Args:
        state: ExtractionPipelineState with regex_matches_json populated.

    Returns:
        State update with phase0_regex list[dict] and extraction_run_id.
    """
    regex_json = state.get("regex_matches_json", "[]")
    try:
        phase0 = json.loads(regex_json) if regex_json else []
    except (json.JSONDecodeError, TypeError):
        phase0 = []

    run_id = state.get("extraction_run_id", "") or str(uuid.uuid4())

    logger.info(
        "v3_phase0_regex_completed",
        book_id=state.get("book_id", ""),
        chapter=state.get("chapter_number", 0),
        regex_matches=len(phase0),
        run_id=run_id,
    )

    return {
        "phase0_regex": phase0,
        "extraction_run_id": run_id,
        "passes_completed": ["phase0_regex"],
    }


# ── Phase 1: Narrative extraction nodes (parallel) ────────────────────


async def narrative_characters_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 1a: Extract characters and factions.

    Delegates to the existing extract_characters function and populates
    both the legacy state keys and V3 phase1_narrative.

    Args:
        state: ExtractionPipelineState with chapter_text populated.

    Returns:
        State update with characters result and phase1_narrative entries.
    """
    result = await extract_characters(state)

    # Build V3 phase1_narrative entries from the characters result
    phase1_entries: list[dict] = []
    characters_result = result.get("characters")
    if characters_result:
        for char in characters_result.characters:
            phase1_entries.append(
                {
                    "entity_type": "character",
                    "name": char.canonical_name or char.name,
                    "source_pass": "narrative_characters",
                }
            )
        for rel in characters_result.relationships:
            phase1_entries.append(
                {
                    "entity_type": "relationship",
                    "name": f"{rel.source}->{rel.target}",
                    "source_pass": "narrative_characters",
                }
            )

    result["phase1_narrative"] = phase1_entries
    return result


async def narrative_events_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 1b: Extract events and arcs.

    Delegates to the existing extract_events function and populates
    both the legacy state keys and V3 phase1_narrative.

    Args:
        state: ExtractionPipelineState with chapter_text populated.

    Returns:
        State update with events result and phase1_narrative entries.
    """
    result = await extract_events(state)

    # Build V3 phase1_narrative entries from the events result
    phase1_entries: list[dict] = []
    events_result = result.get("events")
    if events_result:
        for event in events_result.events:
            phase1_entries.append(
                {
                    "entity_type": "event",
                    "name": event.name,
                    "source_pass": "narrative_events",
                }
            )

    result["phase1_narrative"] = phase1_entries
    return result


async def narrative_world_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 1c: Extract locations, items, concepts (worldbuilding lore).

    Delegates to the existing extract_lore function and populates
    both the legacy state keys and V3 phase1_narrative.

    Args:
        state: ExtractionPipelineState with chapter_text populated.

    Returns:
        State update with lore result and phase1_narrative entries.
    """
    result = await extract_lore(state)

    # Build V3 phase1_narrative entries from the lore result
    phase1_entries: list[dict] = []
    lore_result = result.get("lore")
    if lore_result:
        for loc in lore_result.locations:
            phase1_entries.append(
                {
                    "entity_type": "location",
                    "name": loc.name,
                    "source_pass": "narrative_world",
                }
            )
        for item in lore_result.items:
            phase1_entries.append(
                {
                    "entity_type": "item",
                    "name": item.name,
                    "source_pass": "narrative_world",
                }
            )
        for cr in lore_result.creatures:
            phase1_entries.append(
                {
                    "entity_type": "creature",
                    "name": cr.name,
                    "source_pass": "narrative_world",
                }
            )
        for faction in lore_result.factions:
            phase1_entries.append(
                {
                    "entity_type": "faction",
                    "name": faction.name,
                    "source_pass": "narrative_world",
                }
            )
        for concept in lore_result.concepts:
            phase1_entries.append(
                {
                    "entity_type": "concept",
                    "name": concept.name,
                    "source_pass": "narrative_world",
                }
            )

    result["phase1_narrative"] = phase1_entries
    return result


def merge_phase1_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Merge Phase 1 results and build entity list for Phase 2 context.

    Counts all Phase 1 entities extracted by the 3 parallel sub-passes
    and logs a summary. The phase1_narrative list is already accumulated
    by LangGraph's operator.add annotation.

    Args:
        state: ExtractionPipelineState with all Phase 1 results merged.

    Returns:
        State update with passes_completed marker.
    """
    phase1 = state.get("phase1_narrative", [])
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    logger.info(
        "v3_phase1_merge_completed",
        book_id=book_id,
        chapter=chapter_number,
        phase1_entity_count=len(phase1),
    )

    return {
        "passes_completed": ["phase1_merge"],
    }


# ── Phase 2: Genre extraction nodes (conditional, parallel) ──────────


async def genre_progression_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 2a: Extract skills, classes, titles, levels (progression systems).

    Delegates to the existing extract_systems function and populates
    both the legacy state keys and V3 phase2_genre.

    Args:
        state: ExtractionPipelineState with chapter_text populated.

    Returns:
        State update with systems result and phase2_genre entries.
    """
    result = await extract_systems(state)

    # Build V3 phase2_genre entries from the systems result
    phase2_entries: list[dict] = []
    systems_result = result.get("systems")
    if systems_result:
        for skill in systems_result.skills:
            phase2_entries.append(
                {
                    "entity_type": "skill",
                    "name": skill.name,
                    "source_pass": "genre_progression",
                }
            )
        for cls in systems_result.classes:
            phase2_entries.append(
                {
                    "entity_type": "class",
                    "name": cls.name,
                    "source_pass": "genre_progression",
                }
            )
        for title in systems_result.titles:
            phase2_entries.append(
                {
                    "entity_type": "title",
                    "name": title.name,
                    "source_pass": "genre_progression",
                }
            )

    result["phase2_genre"] = phase2_entries
    return result


async def genre_creatures_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 2b: Extract creatures and races from genre-specific context.

    For now, this is a lightweight pass that returns empty results since
    creature extraction is already handled by the narrative_world node
    (extract_lore). This node will be enhanced in future V3 iterations
    to extract genre-specific creature attributes (threat_level, loot_table,
    xp_value, etc.) that the generic lore pass does not cover.

    Args:
        state: ExtractionPipelineState with chapter_text populated.

    Returns:
        State update with phase2_genre entries.
    """
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    logger.info(
        "v3_genre_creatures_pass",
        book_id=book_id,
        chapter=chapter_number,
        note="placeholder — creature extraction handled by narrative_world",
    )

    return {
        "phase2_genre": [],
        "passes_completed": ["genre_creatures"],
        "errors": [],
    }


def merge_phase2_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Merge Phase 2 results.

    Counts all Phase 2 genre-specific entities extracted by the parallel
    sub-passes and logs a summary.

    Args:
        state: ExtractionPipelineState with all Phase 2 results merged.

    Returns:
        State update with passes_completed marker.
    """
    phase2 = state.get("phase2_genre", [])
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    logger.info(
        "v3_phase2_merge_completed",
        book_id=book_id,
        chapter=chapter_number,
        phase2_entity_count=len(phase2),
    )

    return {
        "passes_completed": ["phase2_merge"],
    }


# ── Phase 3: Series-specific extraction node (conditional) ───────────


async def series_extract_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 3: Extract series-specific entities using Layer 3 ontology.

    For now, this is a placeholder that returns empty results. Future V3
    iterations will load series-specific YAML ontology definitions and
    extract entities unique to a particular series (e.g., Bloodlines,
    Professions for Primal Hunter).

    Args:
        state: ExtractionPipelineState with chapter_text populated.

    Returns:
        State update with phase3_series entries.
    """
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)
    series_name = state.get("series_name", "")

    logger.info(
        "v3_series_extract_pass",
        book_id=book_id,
        chapter=chapter_number,
        series_name=series_name,
        note="placeholder — series-specific extraction not yet implemented",
    )

    return {
        "phase3_series": [],
        "passes_completed": ["series_extract"],
        "errors": [],
    }


# ── Phase routing functions ───────────────────────────────────────────


def should_run_genre_phase(state: ExtractionPipelineState) -> bool:
    """Decide if Phase 2 (genre) should run.

    Phase 2 runs when a genre is specified (e.g., 'litrpg', 'cultivation').
    Without a genre, skip straight to reconciliation.

    Args:
        state: ExtractionPipelineState with genre field.

    Returns:
        True if genre extraction should run.
    """
    return bool(state.get("genre", ""))


def should_run_series_phase(state: ExtractionPipelineState) -> bool:
    """Decide if Phase 3 (series) should run.

    Phase 3 runs only when a series_name is specified, indicating
    that series-specific Layer 3 ontology is available.

    Args:
        state: ExtractionPipelineState with series_name field.

    Returns:
        True if series extraction should run.
    """
    return bool(state.get("series_name", ""))


# ── Phase 4: Reconciliation V3 node ──────────────────────────────────


async def reconcile_v3_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 4: Reconcile and deduplicate across all phases.

    Delegates to the existing reconcile_in_graph function which runs
    3-tier dedup (exact -> fuzzy -> LLM-as-Judge) and cross-book
    entity resolution.

    Args:
        state: ExtractionPipelineState after all extraction phases.

    Returns:
        State update with alias_map from reconciliation.
    """
    return await reconcile_in_graph(state)


# ── Phase 5: Grounding + Registry nodes ──────────────────────────────


async def ground_mentions_v3_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 5a: Source grounding + mention detection.

    Delegates to the existing mention_detect_node which performs
    programmatic mention detection and optional coreference resolution.

    Args:
        state: ExtractionPipelineState after reconciliation.

    Returns:
        State update with grounded_entities.
    """
    return await mention_detect_node(state)


def update_registry_node(state: ExtractionPipelineState) -> dict[str, Any]:
    """Phase 5b: Update EntityRegistry with newly extracted entities.

    Collects all entities from all phases (narrative, genre, series) and
    serializes them into the entity_registry state field. This registry
    carries forward between chapters for cross-chapter dedup context.

    Args:
        state: ExtractionPipelineState after grounding.

    Returns:
        State update with entity_registry.
    """
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    # Collect all entities from all V3 phases
    all_entities: list[dict] = []

    phase1 = state.get("phase1_narrative", [])
    phase2 = state.get("phase2_genre", [])
    phase3 = state.get("phase3_series", [])

    all_entities.extend(phase1)
    all_entities.extend(phase2)
    all_entities.extend(phase3)

    # Build registry from accumulated entities
    registry: dict[str, Any] = state.get("entity_registry", {}) or {}
    registry["last_chapter"] = chapter_number
    registry["entity_count"] = len(all_entities)
    registry["entities"] = all_entities

    logger.info(
        "v3_registry_updated",
        book_id=book_id,
        chapter=chapter_number,
        total_registry_entities=len(all_entities),
    )

    return {
        "entity_registry": registry,
        "passes_completed": ["update_registry"],
    }


# ── Fan-out routing for Phase 1 ──────────────────────────────────────


def fan_out_phase1(state: ExtractionPipelineState) -> list[Send]:
    """Fan out to Phase 1 parallel sub-passes.

    Always sends to all 3 narrative extraction nodes: characters,
    events, and world (locations/items/concepts).

    Args:
        state: ExtractionPipelineState after Phase 0 regex.

    Returns:
        List of Send objects for parallel execution.
    """
    return [
        Send("narrative_characters", state),
        Send("narrative_events", state),
        Send("narrative_world", state),
    ]


def _route_phase1_to_phase2(state: ExtractionPipelineState) -> list[Send]:
    """Route from Phase 1 merge to Phase 2 genre (fan-out) or reconcile.

    When genre is set, fan out to both genre sub-passes in parallel.
    When no genre is specified, skip directly to reconcile.

    Args:
        state: ExtractionPipelineState after Phase 1 merge.

    Returns:
        List of Send objects — either genre fan-out or single reconcile.
    """
    if should_run_genre_phase(state):
        return [
            Send("genre_progression", state),
            Send("genre_creatures", state),
        ]
    return [Send("reconcile", state)]


def _route_phase2_to_phase3(state: ExtractionPipelineState) -> list[Send]:
    """Route from Phase 2 merge to Phase 3 series or reconcile.

    When series_name is set, route to series extraction.
    Otherwise, skip directly to reconcile.

    Args:
        state: ExtractionPipelineState after Phase 2 merge.

    Returns:
        List of Send objects — either series_extract or reconcile.
    """
    if should_run_series_phase(state):
        return [Send("series_extract", state)]
    return [Send("reconcile", state)]


# ── V3 Graph builder ─────────────────────────────────────────────────


def build_extraction_graph_v3() -> CompiledStateGraph:
    """Build and compile the V3 6-phase extraction pipeline.

    Graph structure:
        Phase 0: regex_extract (always, $0 cost)
        Phase 1: narrative (characters, events, world) — parallel fan-out
        Phase 2: genre (progression, creatures) — conditional, parallel
        Phase 3: series — conditional
        Phase 4: reconcile (3-tier dedup)
        Phase 5: ground_mentions + update_registry

    Conditional routing:
        - Phase 2 runs only if genre is set
        - Phase 3 runs only if series_name is set
        - If either is skipped, control flows directly to reconcile

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(ExtractionPipelineState)

    # ── Phase 0 ──
    graph.add_node("regex_extract", regex_extract_node)

    # ── Phase 1 — Narrative (always runs, 3 parallel sub-passes) ──
    graph.add_node("narrative_characters", narrative_characters_node)
    graph.add_node("narrative_events", narrative_events_node)
    graph.add_node("narrative_world", narrative_world_node)
    graph.add_node("merge_phase1", merge_phase1_node)

    # ── Phase 2 — Genre (conditional) ──
    graph.add_node("genre_progression", genre_progression_node)
    graph.add_node("genre_creatures", genre_creatures_node)
    graph.add_node("merge_phase2", merge_phase2_node)

    # ── Phase 3 — Series (conditional) ──
    graph.add_node("series_extract", series_extract_node)

    # ── Phase 4 — Reconciliation ──
    graph.add_node("reconcile", reconcile_v3_node)

    # ── Phase 5 — Grounding + Registry ──
    graph.add_node("ground_mentions", ground_mentions_v3_node)
    graph.add_node("update_registry", update_registry_node)

    # ═══════════════════════════════════════════════════════════════════
    # Edges
    # ═══════════════════════════════════════════════════════════════════

    # START → Phase 0
    graph.add_edge(START, "regex_extract")

    # Phase 0 → Phase 1 (parallel fan-out to 3 narrative passes)
    graph.add_conditional_edges(
        "regex_extract",
        fan_out_phase1,
        ["narrative_characters", "narrative_events", "narrative_world"],
    )

    # Phase 1 passes → merge_phase1
    graph.add_edge("narrative_characters", "merge_phase1")
    graph.add_edge("narrative_events", "merge_phase1")
    graph.add_edge("narrative_world", "merge_phase1")

    # Phase 1 → Phase 2 (conditional fan-out on genre)
    # When genre is set, fan out to both genre sub-passes in parallel.
    # When no genre, skip directly to reconcile.
    graph.add_conditional_edges(
        "merge_phase1",
        _route_phase1_to_phase2,
        ["genre_progression", "genre_creatures", "reconcile"],
    )

    # Phase 2 passes → merge_phase2
    graph.add_edge("genre_progression", "merge_phase2")
    graph.add_edge("genre_creatures", "merge_phase2")

    # Phase 2 → Phase 3 (conditional on series_name)
    graph.add_conditional_edges(
        "merge_phase2", _route_phase2_to_phase3, ["series_extract", "reconcile"]
    )

    # Phase 3 → Phase 4
    graph.add_edge("series_extract", "reconcile")

    # Phase 4 → Phase 5
    graph.add_edge("reconcile", "ground_mentions")
    graph.add_edge("ground_mentions", "update_registry")
    graph.add_edge("update_registry", END)

    compiled = graph.compile()
    logger.info("v3_extraction_graph_built")
    return compiled


# ── V3 Entry point ───────────────────────────────────────────────────


async def extract_chapter_v3(
    chapter_text: str,
    chapter_number: int,
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    regex_matches_json: str = "[]",
    entity_registry: dict | None = None,
    ontology_version: str = "3.0.0",
    source_language: str = "fr",
    series_entities: list[dict] | None = None,
) -> ChapterExtractionResult:
    """V3 entry point: extract entities from a chapter using 6-phase pipeline.

    Invokes the V3 LangGraph extraction pipeline which runs 6 phases:
    regex, narrative, genre (conditional), series (conditional),
    reconciliation, and grounding.

    Args:
        chapter_text: Full text of the chapter.
        chapter_number: Chapter number.
        book_id: Book identifier.
        genre: Book genre for ontology selection and Phase 2 routing.
        series_name: Series name for Phase 3 series-specific extraction.
        regex_matches_json: Pre-extracted regex matches JSON (Phase 0).
        entity_registry: Serialized EntityRegistry from previous chapters.
        ontology_version: Ontology version string for this extraction run.
        source_language: Source language of the text.
        series_entities: Known entities from other books in the same series.

    Returns:
        ChapterExtractionResult with all extracted entities.
    """
    v3_graph = build_extraction_graph_v3()

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
        # V3 fields
        "entity_registry": entity_registry or {},
        "ontology_version": ontology_version,
        "extraction_run_id": "",
        "source_language": source_language,
        "phase0_regex": [],
        "phase1_narrative": [],
        "phase2_genre": [],
        "phase3_series": [],
    }

    logger.info(
        "v3_chapter_extraction_started",
        book_id=book_id,
        chapter=chapter_number,
        text_length=len(chapter_text),
        genre=genre,
        series_name=series_name,
        ontology_version=ontology_version,
    )

    final_state = await v3_graph.ainvoke(initial_state)

    # Build result from final state (same schema as V1 for compatibility)
    result = ChapterExtractionResult(
        book_id=book_id,
        chapter_number=chapter_number,
        characters=final_state.get("characters", CharacterExtractionResult()),
        systems=final_state.get("systems", SystemExtractionResult()),
        events=final_state.get("events", EventExtractionResult()),
        lore=final_state.get("lore", LoreExtractionResult()),
        layer3=final_state.get("layer3", Layer3ExtractionResult()),
        grounded_entities=final_state.get("grounded_entities", []),
        alias_map=final_state.get("alias_map", {}),
        total_entities=final_state.get("total_entities", 0),
        total_cost_usd=final_state.get("total_cost_usd", 0.0),
        passes_completed=final_state.get("passes_completed", []),
        ontology_version=ontology_version,
    )

    result.count_entities()

    logger.info(
        "v3_chapter_extraction_completed",
        book_id=book_id,
        chapter=chapter_number,
        total_entities=result.total_entities,
        passes=result.passes_completed,
        grounded=len(result.grounded_entities),
        aliases=len(final_state.get("alias_map", {})),
        run_id=final_state.get("extraction_run_id", ""),
    )

    return result
