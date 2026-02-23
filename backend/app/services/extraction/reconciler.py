"""Cross-pass entity reconciliation via Instructor.

After the 4 extraction passes complete, entities may be duplicated
or referenced differently across passes. The reconciler:

1. Collects all entity names from all passes
2. Groups by entity type
3. Runs 3-tier deduplication (exact -> fuzzy -> LLM)
4. Builds a unified alias map
5. Applies the alias map to normalize all entity references

This is the bridge between raw extraction and KG ingestion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.llm.providers import get_instructor_for_task
from app.schemas.extraction import (
    ChapterExtractionResult,
    ReconciliationResult,
)
from app.services.deduplication import deduplicate_entities

if TYPE_CHECKING:
    from app.agents.state import ExtractionPipelineState

logger = get_logger(__name__)


async def reconcile_entities(
    state: ExtractionPipelineState,
) -> dict[str, Any]:
    """LangGraph node: Reconcile entities across all extraction passes.

    Deduplicates entity names within each type, builds an alias map,
    and normalizes all references.

    Args:
        state: ExtractionPipelineState with all passes completed.

    Returns:
        State update with reconciled results.
    """
    book_id = state.get("book_id", "")
    chapter_number = state.get("chapter_number", 0)

    logger.info(
        "reconciliation_started",
        book_id=book_id,
        chapter=chapter_number,
    )

    # Get Instructor client for LLM dedup (Tier 3)
    try:
        client, model = get_instructor_for_task("dedup")
    except Exception:
        client, model = None, ""

    full_alias_map: dict[str, str] = {}

    # ── Collect character names ──
    characters = state.get("characters")
    if characters and characters.characters:
        char_dicts = [
            {"name": c.name, "canonical": c.canonical_name}
            for c in characters.characters
        ]
        _, char_aliases = await deduplicate_entities(
            char_dicts, "Character", client, model,
        )
        full_alias_map.update(char_aliases)

        # Also dedup from aliases
        all_aliases: list[dict[str, str]] = []
        for c in characters.characters:
            for alias in c.aliases:
                if alias and alias != c.name:
                    all_aliases.append({"name": alias, "canonical": c.canonical_name or c.name})
        if all_aliases:
            for a in all_aliases:
                full_alias_map[a["name"]] = a.get("canonical", a["name"])

    # ── Collect skill names ──
    systems = state.get("systems")
    if systems and systems.skills:
        skill_dicts = [{"name": s.name} for s in systems.skills]
        _, skill_aliases = await deduplicate_entities(
            skill_dicts, "Skill", client, model,
        )
        full_alias_map.update(skill_aliases)

    # ── Collect class names ──
    if systems and systems.classes:
        class_dicts = [{"name": c.name} for c in systems.classes]
        _, class_aliases = await deduplicate_entities(
            class_dicts, "Class", client, model,
        )
        full_alias_map.update(class_aliases)

    # ── Collect location names ──
    lore = state.get("lore")
    if lore and lore.locations:
        loc_dicts = [{"name": loc.name} for loc in lore.locations]
        _, loc_aliases = await deduplicate_entities(
            loc_dicts, "Location", client, model,
        )
        full_alias_map.update(loc_aliases)

    # ── Collect item names ──
    if lore and lore.items:
        item_dicts = [{"name": i.name} for i in lore.items]
        _, item_aliases = await deduplicate_entities(
            item_dicts, "Item", client, model,
        )
        full_alias_map.update(item_aliases)

    # ── Collect faction names ──
    if lore and lore.factions:
        faction_dicts = [{"name": f.name} for f in lore.factions]
        _, faction_aliases = await deduplicate_entities(
            faction_dicts, "Faction", client, model,
        )
        full_alias_map.update(faction_aliases)

    # ── Cross-pass character reference normalization ──
    # Characters may be referenced differently in events/systems/lore
    _normalize_event_participants(state, full_alias_map)
    _normalize_system_owners(state, full_alias_map)
    _normalize_item_owners(state, full_alias_map)

    logger.info(
        "reconciliation_completed",
        book_id=book_id,
        chapter=chapter_number,
        total_aliases=len(full_alias_map),
    )

    return {
        "errors": [],
    }


def _normalize_event_participants(
    state: ExtractionPipelineState,
    alias_map: dict[str, str],
) -> None:
    """Normalize character names in event participants."""
    events = state.get("events")
    if not events:
        return

    for event in events.events:
        event.participants = [
            alias_map.get(p, p) for p in event.participants
        ]


def _normalize_system_owners(
    state: ExtractionPipelineState,
    alias_map: dict[str, str],
) -> None:
    """Normalize character names in system entity owners."""
    systems = state.get("systems")
    if not systems:
        return

    for skill in systems.skills:
        skill.owner = alias_map.get(skill.owner, skill.owner)
    for cls in systems.classes:
        cls.owner = alias_map.get(cls.owner, cls.owner)
    for title in systems.titles:
        title.owner = alias_map.get(title.owner, title.owner)
    for level in systems.level_changes:
        level.character = alias_map.get(level.character, level.character)


def _normalize_item_owners(
    state: ExtractionPipelineState,
    alias_map: dict[str, str],
) -> None:
    """Normalize character names in item owners."""
    lore = state.get("lore")
    if not lore:
        return

    for item in lore.items:
        item.owner = alias_map.get(item.owner, item.owner)


async def reconcile_chapter_result(
    result: ChapterExtractionResult,
) -> ReconciliationResult:
    """Reconcile a standalone ChapterExtractionResult.

    Convenience function for use outside the LangGraph pipeline.

    Args:
        result: Completed extraction result to reconcile.

    Returns:
        ReconciliationResult with merges and alias map.
    """
    try:
        client, model = get_instructor_for_task("dedup")
    except Exception:
        client, model = None, ""

    full_alias_map: dict[str, str] = {}
    conflicts: list[str] = []

    # Dedup characters
    if result.characters.characters:
        char_dicts = [{"name": c.name} for c in result.characters.characters]
        _, aliases = await deduplicate_entities(
            char_dicts, "Character", client, model,
        )
        full_alias_map.update(aliases)

    # Dedup skills
    if result.systems.skills:
        skill_dicts = [{"name": s.name} for s in result.systems.skills]
        _, aliases = await deduplicate_entities(
            skill_dicts, "Skill", client, model,
        )
        full_alias_map.update(aliases)

    return ReconciliationResult(
        merges=[],
        alias_map=full_alias_map,
        conflicts=conflicts,
    )
