"""Provenance extraction service — Pass 2b.

After systems extraction identifies skills acquired in a chapter,
this pass determines the SOURCE of each skill (item, class, bloodline, etc.)
using an LLM with structured output.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.prompts.extraction_provenance import PROVENANCE_SYSTEM_PROMPT
from app.schemas.extraction import ProvenanceResult, SkillProvenance

logger = get_logger(__name__)


async def _call_instructor(
    chapter_text: str,
    skills: list[str],
    entities: dict[str, list[str]],
) -> list[SkillProvenance]:
    """Call Instructor with Gemini Flash for provenance extraction."""
    from app.llm.providers import get_instructor_for_task

    client, model = get_instructor_for_task("reconciliation")

    prompt = (
        f"{PROVENANCE_SYSTEM_PROMPT}\n\n"
        f"## Skills acquired this chapter:\n"
        f"{', '.join(skills)}\n\n"
        f"## Known entities in context:\n"
        f"Items: {', '.join(entities.get('items', []))}\n"
        f"Classes: {', '.join(entities.get('classes', []))}\n"
        f"Bloodlines: {', '.join(entities.get('bloodlines', []))}\n\n"
        f"## Chapter text:\n{chapter_text[:4000]}\n\n"
        f"Return a list of SkillProvenance for each skill."
    )

    try:
        result = await client.chat.completions.create(
            model=model,
            response_model=list[SkillProvenance],
            messages=[{"role": "user", "content": prompt}],
            max_retries=2,
        )
        return result
    except Exception:
        logger.warning("provenance_extraction_failed", exc_info=True)
        return []


async def extract_provenance(
    chapter_text: str,
    skills_acquired: list[str],
    chapter_entities: dict[str, list[str]],
) -> ProvenanceResult:
    """Extract provenance for skills acquired in a chapter.

    Args:
        chapter_text: Full chapter text.
        skills_acquired: List of skill names acquired this chapter.
        chapter_entities: Dict of entity types to names present in chapter.

    Returns:
        ProvenanceResult with confidence-scored provenance links.
    """
    if not skills_acquired:
        return ProvenanceResult()

    provenances = await _call_instructor(chapter_text, skills_acquired, chapter_entities)

    filtered = [p for p in provenances if p.confidence >= 0.5]

    logger.info(
        "provenance_extracted",
        total=len(provenances),
        high_confidence=len([p for p in filtered if p.confidence >= 0.7]),
        filtered=len(filtered),
    )

    return ProvenanceResult(provenances=filtered)
