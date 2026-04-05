"""Batch faithfulness verification for extracted entities.

Asks the LLM to verify which entities are actually grounded in the source
text, filtering out hallucinated entities in a single batch call.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.llm.providers import get_instructor_for_task

logger = get_logger(__name__)


class FaithfulnessResult(BaseModel):
    """Result of batch faithfulness check."""

    ungrounded_indices: list[int] = Field(
        default_factory=list,
        description="0-based indices of entities NOT supported by the source text",
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of which entities were flagged and why",
    )


async def batch_verify_faithfulness(
    entities: list[dict[str, Any]],
    chapter_text: str,
    max_entities: int = 40,
) -> list[dict[str, Any]]:
    """Verify entities are grounded in source text via batch LLM check.

    Args:
        entities: Extracted entity dicts.
        chapter_text: Source chapter text.
        max_entities: Max entities to check per call (cost control).

    Returns:
        Filtered list with hallucinated entities removed.
    """
    if not entities or not chapter_text:
        return entities

    # Limit to first N entities for cost control
    to_check = entities[:max_entities]

    entity_list = "\n".join(
        f'{i}. "{e.get("name", "?")}" (type: {e.get("entity_type", "?")})'
        for i, e in enumerate(to_check)
    )

    # Truncate chapter text to fit context
    text_preview = chapter_text[:4000]

    try:
        client, model = get_instructor_for_task("verification")
    except Exception:
        logger.warning("faithfulness_check_skipped", reason="no_instructor_client")
        return entities

    try:
        result = await client.chat.completions.create(
            model=model,
            response_model=FaithfulnessResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a fact-checker for entity extraction. "
                        "Given source text and a numbered list of extracted entities, "
                        "identify which entities are NOT actually mentioned or clearly "
                        "implied in the source text. These are hallucinated."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'Source text:\n"""\n{text_preview}\n"""\n\n'
                        f"Extracted entities:\n{entity_list}\n\n"
                        "Return the indices (0-based) of entities that are NOT grounded "
                        "in the source text. If all are grounded, return an empty list."
                    ),
                },
            ],
            max_retries=1,
        )

        hallucinated = set(result.ungrounded_indices)
        if hallucinated:
            removed_names = [
                to_check[i].get("name", "?") for i in hallucinated if i < len(to_check)
            ]
            logger.info(
                "faithfulness_check_completed",
                total_checked=len(to_check),
                hallucinated=len(hallucinated),
                removed_names=removed_names,
                reasoning=result.reasoning[:200],
            )
        else:
            logger.info(
                "faithfulness_check_completed",
                total_checked=len(to_check),
                hallucinated=0,
            )

        # Remove hallucinated entities
        verified = [e for i, e in enumerate(entities) if i >= max_entities or i not in hallucinated]
        return verified

    except Exception:
        logger.warning("faithfulness_check_failed", exc_info=True)
        return entities  # fail open — don't block extraction
