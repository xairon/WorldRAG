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

from app.core.logging import get_logger
from app.llm.providers import get_instructor_for_task
from app.schemas.extraction import (
    ChapterExtractionResult,
    ReconciliationResult,
)
from app.services.deduplication import deduplicate_entities

logger = get_logger(__name__)


async def _dedup_group(
    entities: list,
    entity_type: str,
    name_attr: str,
    client,
    model: str,
) -> dict[str, str]:
    """Deduplicate a group of entities by name and return the alias map.

    Skips dedup if there are fewer than 2 entities (nothing to compare).

    Args:
        entities: List of Pydantic models with the name attribute.
        entity_type: Entity type label for logging/context.
        name_attr: Attribute name to extract (e.g. "name", "character").
        client: Instructor async client (or None to skip LLM tier).
        model: Model name for LLM tier.

    Returns:
        Alias map {alias -> canonical_name}.
    """
    if len(entities) < 2:
        return {}

    entity_dicts = [{"name": getattr(e, name_attr)} for e in entities]
    _, aliases = await deduplicate_entities(
        entity_dicts,
        entity_type,
        client,
        model,
    )
    return aliases


async def reconcile_chapter_result(
    result: ChapterExtractionResult,
) -> ReconciliationResult:
    """Reconcile a standalone ChapterExtractionResult.

    Runs 3-tier deduplication (exact → fuzzy → LLM) across all entity
    types extracted from a single chapter.

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

    # ── Pass 1 entities ────────────────────────────────────────────
    # Characters
    aliases = await _dedup_group(
        result.characters.characters,
        "Character",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # ── Pass 2 entities ────────────────────────────────────────────
    # Skills
    aliases = await _dedup_group(
        result.systems.skills,
        "Skill",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # Classes
    aliases = await _dedup_group(
        result.systems.classes,
        "Class",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # Titles
    aliases = await _dedup_group(
        result.systems.titles,
        "Title",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # ── Pass 3 entities ────────────────────────────────────────────
    # Events
    aliases = await _dedup_group(
        result.events.events,
        "Event",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # ── Pass 4 entities ────────────────────────────────────────────
    # Locations
    aliases = await _dedup_group(
        result.lore.locations,
        "Location",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # Items
    aliases = await _dedup_group(
        result.lore.items,
        "Item",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # Creatures
    aliases = await _dedup_group(
        result.lore.creatures,
        "Creature",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # Factions
    aliases = await _dedup_group(
        result.lore.factions,
        "Faction",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    # Concepts
    aliases = await _dedup_group(
        result.lore.concepts,
        "Concept",
        "name",
        client,
        model,
    )
    full_alias_map.update(aliases)

    logger.info(
        "reconciliation_completed",
        total_aliases=len(full_alias_map),
        conflicts=len(conflicts),
        entity_types_processed=10,
    )

    return ReconciliationResult(
        merges=[],
        alias_map=full_alias_map,
        conflicts=conflicts,
    )


async def reconcile_with_cross_book(
    result: ChapterExtractionResult,
    series_registry: dict | None = None,
) -> ReconciliationResult:
    """V3 reconciliation with cross-book entity matching.

    If series_registry is provided, attempts to match new entities
    against entities from previous books in the series.

    Args:
        result: Completed extraction result to reconcile.
        series_registry: Serialized EntityRegistry from previous books.

    Returns:
        ReconciliationResult with cross-book aliases merged in.
    """
    # First, run the existing reconciliation
    base_result = await reconcile_chapter_result(result)

    if not series_registry:
        return base_result

    # Cross-book matching: check new entities against series registry
    from app.services.extraction.entity_registry import EntityRegistry

    registry = EntityRegistry.from_dict(series_registry)

    additional_aliases: dict[str, str] = {}
    entity_lists: list[list] = [
        result.characters.characters,
        result.systems.skills,
        result.systems.classes,
        result.systems.titles,
        result.events.events,
        result.lore.locations,
        result.lore.items,
        result.lore.creatures,
        result.lore.factions,
        result.lore.concepts,
    ]
    for entity_type_entities in entity_lists:
        if not entity_type_entities:
            continue
        for entity in entity_type_entities:
            name = getattr(entity, "name", None) or getattr(entity, "canonical_name", None)
            if not name:
                continue
            match = registry.lookup(name)
            if match and match.canonical_name != name.lower().strip():
                additional_aliases[name] = match.canonical_name

    # Merge additional aliases into the result
    merged_aliases = {**base_result.alias_map, **additional_aliases}

    logger.info(
        "cross_book_reconciliation_completed",
        base_aliases=len(base_result.alias_map),
        cross_book_aliases=len(additional_aliases),
        total_aliases=len(merged_aliases),
    )

    return ReconciliationResult(
        merges=base_result.merges,
        alias_map=merged_aliases,
        conflicts=base_result.conflicts,
    )
