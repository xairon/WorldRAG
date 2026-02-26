"""Pass 5b -- LLM-based coreference resolution.

Resolves pronouns (il/elle/ils/elles/he/she/they) to known entity names
using Instructor + Gemini Flash.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.llm.providers import get_instructor_for_task
from app.prompts.coreference import COREFERENCE_PROMPT
from app.schemas.extraction import GroundedEntity

logger = get_logger(__name__)


# -- Response models for Instructor structured output --------------------


class PronounResolution(BaseModel):
    """A resolved pronoun reference."""

    pronoun: str = Field(..., description="The pronoun text (e.g., 'il', 'elle')")
    referent: str = Field(..., description="The entity name it refers to")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Resolution confidence")


class CoreferenceResult(BaseModel):
    """Result of coreference resolution for a text segment."""

    resolutions: list[PronounResolution] = Field(default_factory=list)


# -- Public API ----------------------------------------------------------


async def resolve_coreferences(
    chapter_text: str,
    entities: list[dict],
    max_segment_chars: int = 3000,
) -> list[GroundedEntity]:
    """Resolve pronouns to entity names using LLM.

    Args:
        chapter_text: Full chapter text.
        entities: Known entities with ``canonical_name``/``name`` and
            ``entity_type`` keys.
        max_segment_chars: Max chars per LLM call (for batching).

    Returns:
        GroundedEntity list with ``mention_type="pronoun"`` in attributes.
    """
    if not chapter_text or not entities:
        return []

    # Build entity context string (cap at 30 to stay within context budget)
    entity_lines: list[str] = []
    for e in entities:
        name = e.get("canonical_name") or e.get("name", "")
        entity_type = e.get("entity_type", "")
        if name:
            entity_lines.append(f"- {name} ({entity_type})")

    if not entity_lines:
        return []

    entity_context = "\n".join(entity_lines[:30])

    # Split chapter into segments for batched processing
    segments = _split_into_segments(chapter_text, max_segment_chars)

    client, model = get_instructor_for_task("classification")

    all_grounded: list[GroundedEntity] = []

    for segment_text, segment_offset in segments:
        try:
            prompt = COREFERENCE_PROMPT.format(
                entity_context=entity_context,
                text=segment_text,
            )

            result = await client.chat.completions.create(
                model=model,
                response_model=CoreferenceResult,
                messages=[{"role": "user", "content": prompt}],
            )

            # Find pronoun positions in text and create grounded entities
            for resolution in result.resolutions:
                if resolution.confidence < 0.8:
                    continue

                # Locate ALL occurrences of the pronoun in the segment text
                pattern = re.compile(
                    r"\b" + re.escape(resolution.pronoun) + r"\b",
                    re.IGNORECASE,
                )
                for match in pattern.finditer(segment_text):
                    all_grounded.append(
                        GroundedEntity(
                            entity_type="character",
                            entity_name=resolution.referent,
                            extraction_text=match.group(),
                            char_offset_start=segment_offset + match.start(),
                            char_offset_end=segment_offset + match.end(),
                            pass_name="coreference",
                            alignment_status="fuzzy",
                            confidence=resolution.confidence * 0.8,
                            attributes={"mention_type": "pronoun"},
                        )
                    )

        except Exception:
            logger.exception(
                "coreference_segment_failed",
                segment_offset=segment_offset,
            )
            continue

    logger.info(
        "coreference_complete",
        segments_processed=len(segments),
        pronouns_resolved=len(all_grounded),
    )

    return all_grounded


# -- Internal helpers ----------------------------------------------------


def _split_into_segments(
    text: str,
    max_chars: int,
) -> list[tuple[str, int]]:
    """Split text into segments for batched coreference resolution.

    Returns list of ``(segment_text, char_offset)`` tuples.
    Splits on paragraph boundaries when possible.
    """
    if len(text) <= max_chars:
        return [(text, 0)]

    segments: list[tuple[str, int]] = []
    current_start = 0

    while current_start < len(text):
        end = min(current_start + max_chars, len(text))

        # Try to break at a paragraph boundary
        if end < len(text):
            newline_pos = text.rfind("\n", current_start, end)
            if newline_pos > current_start + max_chars // 2:
                end = newline_pos + 1

        segments.append((text[current_start:end], current_start))
        current_start = end

    return segments
