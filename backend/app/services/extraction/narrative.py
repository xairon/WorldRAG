"""Pass 6 — Narrative analysis via Instructor + Gemini.

Detects higher-order narrative structures: character arcs, power progression,
foreshadowing, and themes. Results are stored as Events with subtypes.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.prompts.narrative_analysis import NARRATIVE_ANALYSIS_PROMPT
from app.schemas.narrative import NarrativeAnalysisResult

logger = get_logger(__name__)


async def analyze_narrative(
    chapter_text: str,
    entities: list[dict],
) -> NarrativeAnalysisResult:
    """Run narrative analysis on a chapter using Instructor + Gemini.

    Args:
        chapter_text: Full chapter text.
        entities: Known entities with names and types.

    Returns:
        NarrativeAnalysisResult with all detected narrative elements.
    """
    from app.llm.providers import get_instructor_for_task

    if not chapter_text:
        return NarrativeAnalysisResult()

    # Build entity context
    entity_lines: list[str] = []
    for e in entities[:30]:  # Cap to avoid token overflow
        name = e.get("canonical_name", e.get("name", ""))
        etype = e.get("entity_type", "")
        if name:
            entity_lines.append(f"- {name} ({etype})")

    entity_context = "\n".join(entity_lines) if entity_lines else "(aucun personnage connu)"

    # Truncate chapter text if very long
    text_for_analysis = chapter_text[:15000] if len(chapter_text) > 15000 else chapter_text

    prompt = NARRATIVE_ANALYSIS_PROMPT.format(
        entity_context=entity_context,
        chapter_text=text_for_analysis,
    )

    try:
        client, model = get_instructor_for_task("classification")

        result = await client.chat.completions.create(
            model=model,
            response_model=NarrativeAnalysisResult,
            messages=[{"role": "user", "content": prompt}],
        )

        logger.info(
            "narrative_analysis_complete",
            character_developments=len(result.character_developments),
            power_changes=len(result.power_changes),
            foreshadowing=len(result.foreshadowing_hints),
            themes=len(result.themes),
        )

        return result

    except Exception:
        logger.exception("narrative_analysis_failed")
        return NarrativeAnalysisResult()
