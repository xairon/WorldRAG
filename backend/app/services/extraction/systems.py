"""Pass 2 — Systems & Progression extraction via LangExtract.

Extracts skills, classes, titles, level changes, and stat changes
from chapter text. Enriches regex pre-extraction (Passe 0) with
narrative context.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Any

import langextract as lx

from app.config import settings
from app.core.logging import get_logger
from app.prompts.extraction_systems import FEW_SHOT_EXAMPLES, PROMPT_DESCRIPTION
from app.schemas.extraction import (
    ExtractedClass,
    ExtractedLevelChange,
    ExtractedSkill,
    ExtractedStatChange,
    ExtractedTitle,
    GroundedEntity,
    SystemExtractionResult,
)

if TYPE_CHECKING:
    from app.agents.state import ExtractionPipelineState

logger = get_logger(__name__)

PASS_NAME = "systems"


def _build_enriched_prompt(state: ExtractionPipelineState) -> str:
    """Build prompt enriched with Passe 0 regex matches.

    Prepends regex extraction results so the LLM can confirm and enrich
    them with additional narrative context.
    """
    base_prompt = PROMPT_DESCRIPTION
    regex_json = state.get("regex_matches_json", "")

    if regex_json and regex_json != "[]":
        return (
            f"{base_prompt}\n\n"
            "CONTEXT: The following entities were already pre-extracted by regex "
            "(Passe 0) from blue box notifications. Confirm these and extract any "
            "additional system entities from the narrative text that regex missed:\n"
            f"```json\n{regex_json}\n```"
        )

    return base_prompt


async def extract_systems(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Extract systems and progression from chapter text.

    Reads chapter_text and regex_matches_json from state, runs LangExtract
    with system-focused prompts, returns SystemExtractionResult.

    Args:
        state: ExtractionPipelineState with chapter_text populated.

    Returns:
        Dict update for the LangGraph state.
    """
    chapter_text = state["chapter_text"]
    book_id = state["book_id"]
    chapter_number = state["chapter_number"]

    logger.info(
        "extraction_pass_started",
        pass_name=PASS_NAME,
        book_id=book_id,
        chapter=chapter_number,
        text_length=len(chapter_text),
    )

    try:
        prompt = _build_enriched_prompt(state)

        result = await asyncio.to_thread(
            partial(
                lx.extract,
                text_or_documents=chapter_text,
                prompt_description=prompt,
                examples=FEW_SHOT_EXAMPLES,
                model_id=settings.langextract_model,
                extraction_passes=settings.langextract_passes,
                max_workers=min(settings.langextract_max_workers, 10),
            )
        )

        # Parse LangExtract output
        skills: list[ExtractedSkill] = []
        classes: list[ExtractedClass] = []
        titles: list[ExtractedTitle] = []
        level_changes: list[ExtractedLevelChange] = []
        stat_changes: list[ExtractedStatChange] = []
        grounded: list[GroundedEntity] = []

        for entity in result.extractions:
            attrs = entity.attributes or {}

            if entity.extraction_class == "skill":
                skills.append(
                    ExtractedSkill(
                        name=entity.extraction_text,
                        description=attrs.get("effects", ""),
                        skill_type=attrs.get("skill_type", "active"),
                        rank=attrs.get("rank", ""),
                        owner=attrs.get("owner", ""),
                        acquired_chapter=chapter_number,
                    )
                )

            elif entity.extraction_class == "class":
                classes.append(
                    ExtractedClass(
                        name=attrs.get("name", entity.extraction_text),
                        description=attrs.get("description", ""),
                        tier=_parse_tier(attrs.get("tier_info", "")),
                        owner=attrs.get("owner", ""),
                        acquired_chapter=chapter_number,
                    )
                )

            elif entity.extraction_class == "title":
                titles.append(
                    ExtractedTitle(
                        name=entity.extraction_text,
                        description=attrs.get("description", ""),
                        effects=[
                            e.strip() for e in attrs.get("effects", "").split(",") if e.strip()
                        ],
                        owner=attrs.get("owner", ""),
                        acquired_chapter=chapter_number,
                    )
                )

            elif entity.extraction_class == "level_change":
                level_changes.append(
                    ExtractedLevelChange(
                        character=attrs.get("character", ""),
                        old_level=_safe_int(attrs.get("old_level")),
                        new_level=_safe_int(attrs.get("new_level")),
                        realm=attrs.get("realm", ""),
                        chapter=chapter_number,
                    )
                )

            elif entity.extraction_class == "stat_change":
                stat_changes.append(
                    ExtractedStatChange(
                        character=attrs.get("character", ""),
                        stat_name=attrs.get("stat_name", entity.extraction_text),
                        value=_safe_int(attrs.get("value")) or 0,
                    )
                )

            # Build grounding
            if entity.char_interval:
                grounded.append(
                    GroundedEntity(
                        entity_type=entity.extraction_class,
                        entity_name=attrs.get("name", entity.extraction_text),
                        extraction_text=entity.extraction_text,
                        char_offset_start=entity.char_interval.start_pos,
                        char_offset_end=entity.char_interval.end_pos,
                        attributes=attrs,
                        pass_name=PASS_NAME,
                    )
                )

        extraction_result = SystemExtractionResult(
            skills=skills,
            classes=classes,
            titles=titles,
            level_changes=level_changes,
            stat_changes=stat_changes,
        )

        logger.info(
            "extraction_pass_completed",
            pass_name=PASS_NAME,
            book_id=book_id,
            chapter=chapter_number,
            skills=len(skills),
            classes=len(classes),
            titles=len(titles),
            levels=len(level_changes),
            stats=len(stat_changes),
            grounded=len(grounded),
        )

        return {
            "systems": extraction_result,
            "grounded_entities": grounded,
            "passes_completed": [PASS_NAME],
            "errors": [],
        }

    except Exception as e:
        logger.exception(
            "extraction_pass_failed",
            pass_name=PASS_NAME,
            book_id=book_id,
            chapter=chapter_number,
        )
        return {
            "systems": SystemExtractionResult(),
            "grounded_entities": [],
            "passes_completed": [],
            "errors": [{"pass": PASS_NAME, "error": str(e)}],
        }


def _safe_int(value: str | None) -> int | None:
    """Safely parse a string to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_tier(tier_info: str) -> int | None:
    """Parse tier from strings like 'D-grade', 'Tier 3', etc."""
    if not tier_info:
        return None

    # Grade-based: F=0, E=1, D=2, C=3, B=4, A=5, S=6
    grade_map = {"F": 0, "E": 1, "D": 2, "C": 3, "B": 4, "A": 5, "S": 6}
    tier_upper = tier_info.upper().strip()

    for grade, value in grade_map.items():
        if tier_upper.startswith(grade):
            return value

    # Numeric: "Tier 3" or just "3"
    return _safe_int(tier_info.split()[-1] if " " in tier_info else tier_info)
