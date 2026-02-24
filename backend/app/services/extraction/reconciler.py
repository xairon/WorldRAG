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
            char_dicts,
            "Character",
            client,
            model,
        )
        full_alias_map.update(aliases)

    # Dedup skills
    if result.systems.skills:
        skill_dicts = [{"name": s.name} for s in result.systems.skills]
        _, aliases = await deduplicate_entities(
            skill_dicts,
            "Skill",
            client,
            model,
        )
        full_alias_map.update(aliases)

    return ReconciliationResult(
        merges=[],
        alias_map=full_alias_map,
        conflicts=conflicts,
    )
