"""Pass 3 — Events & Timeline extraction via LangExtract.

Extracts narrative events with temporal anchoring, causal links,
participant tracking, and significance assessment.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Any

import langextract as lx

from app.config import settings
from app.core.logging import get_logger
from app.prompts.extraction_events import FEW_SHOT_EXAMPLES, PROMPT_DESCRIPTION
from app.schemas.extraction import (
    EventExtractionResult,
    ExtractedEvent,
    GroundedEntity,
)

if TYPE_CHECKING:
    from app.agents.state import ExtractionPipelineState

logger = get_logger(__name__)

PASS_NAME = "events"


async def extract_events(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Extract narrative events from chapter text.

    Reads chapter_text from state, runs LangExtract with event-focused
    prompts, returns EventExtractionResult.

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
        result = await asyncio.to_thread(
            partial(
                lx.extract,
                text_or_documents=chapter_text,
                prompt_description=PROMPT_DESCRIPTION,
                examples=FEW_SHOT_EXAMPLES,
                model_id=settings.langextract_model,
                api_key=settings.gemini_api_key or None,
                extraction_passes=settings.langextract_passes,
                max_workers=min(settings.langextract_max_workers, 10),
                show_progress=False,
            )
        )

        # Parse LangExtract output
        events: list[ExtractedEvent] = []
        grounded: list[GroundedEntity] = []

        for entity in result.extractions:
            attrs = entity.attributes or {}

            if entity.extraction_class == "event":
                participants = [
                    p.strip() for p in attrs.get("participants", "").split(",") if p.strip()
                ]
                causes = [c.strip() for c in attrs.get("causes", "").split(",") if c.strip()]

                events.append(
                    ExtractedEvent(
                        name=attrs.get("name", entity.extraction_text[:60]),
                        description=attrs.get("description", entity.extraction_text),
                        event_type=attrs.get("event_type", "action"),
                        significance=attrs.get("significance", "moderate"),
                        participants=participants,
                        location=attrs.get("location", ""),
                        chapter=chapter_number,
                        is_flashback=attrs.get("is_flashback", "false").lower() == "true",
                        causes=causes,
                    )
                )

            # Build grounding
            if entity.char_interval:
                grounded.append(
                    GroundedEntity(
                        entity_type=entity.extraction_class,
                        entity_name=attrs.get("name", entity.extraction_text[:60]),
                        extraction_text=entity.extraction_text,
                        char_offset_start=entity.char_interval.start_pos,
                        char_offset_end=entity.char_interval.end_pos,
                        attributes=attrs,
                        pass_name=PASS_NAME,
                    )
                )

        extraction_result = EventExtractionResult(events=events)

        logger.info(
            "extraction_pass_completed",
            pass_name=PASS_NAME,
            book_id=book_id,
            chapter=chapter_number,
            events=len(events),
            by_significance={
                sig: sum(1 for e in events if e.significance == sig)
                for sig in {e.significance for e in events}
            },
            grounded=len(grounded),
        )

        return {
            "events": extraction_result,
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
            "events": EventExtractionResult(),
            "grounded_entities": [],
            "passes_completed": [],
            "errors": [{"pass": PASS_NAME, "error": str(e)}],
        }
