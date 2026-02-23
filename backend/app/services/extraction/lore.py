"""Pass 4 — Lore & Worldbuilding extraction via LangExtract.

Extracts locations, items, creatures, factions, and world concepts
from chapter text with source grounding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import langextract as lx

from app.config import settings
from app.core.logging import get_logger
from app.prompts.extraction_lore import FEW_SHOT_EXAMPLES, PROMPT_DESCRIPTION
from app.schemas.extraction import (
    ExtractedConcept,
    ExtractedCreature,
    ExtractedFaction,
    ExtractedItem,
    ExtractedLocation,
    GroundedEntity,
    LoreExtractionResult,
)

if TYPE_CHECKING:
    from app.agents.state import ExtractionPipelineState

logger = get_logger(__name__)

PASS_NAME = "lore"


async def extract_lore(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Extract lore and worldbuilding from chapter text.

    Reads chapter_text from state, runs LangExtract with lore-focused
    prompts, returns LoreExtractionResult.

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
        result = lx.extract(
            text_or_documents=chapter_text,
            prompt_description=PROMPT_DESCRIPTION,
            examples=FEW_SHOT_EXAMPLES,
            model_id=settings.langextract_model,
            extraction_passes=settings.langextract_passes,
            max_workers=min(settings.langextract_max_workers, 10),
        )

        # Parse LangExtract output
        locations: list[ExtractedLocation] = []
        items: list[ExtractedItem] = []
        creatures: list[ExtractedCreature] = []
        factions: list[ExtractedFaction] = []
        concepts: list[ExtractedConcept] = []
        grounded: list[GroundedEntity] = []

        for entity in result.extractions:
            attrs = entity.attributes or {}

            if entity.extraction_class == "location":
                locations.append(
                    ExtractedLocation(
                        name=attrs.get("name", entity.extraction_text),
                        description=attrs.get("description", ""),
                        location_type=attrs.get("location_type", "region"),
                        parent_location=attrs.get("parent_location", ""),
                    )
                )

            elif entity.extraction_class == "item":
                items.append(
                    ExtractedItem(
                        name=attrs.get("name", entity.extraction_text),
                        description=attrs.get("description", ""),
                        item_type=attrs.get("item_type", "key_item"),
                        rarity=attrs.get("rarity", ""),
                        owner=attrs.get("owner", ""),
                    )
                )

            elif entity.extraction_class == "creature":
                creatures.append(
                    ExtractedCreature(
                        name=entity.extraction_text,
                        description=attrs.get("description", ""),
                        species=attrs.get("species", ""),
                        threat_level=attrs.get("threat_level", ""),
                        habitat=attrs.get("habitat", ""),
                    )
                )

            elif entity.extraction_class == "faction":
                factions.append(
                    ExtractedFaction(
                        name=entity.extraction_text,
                        description=attrs.get("description", ""),
                        faction_type=attrs.get("faction_type", ""),
                        alignment=attrs.get("alignment", ""),
                    )
                )

            elif entity.extraction_class == "concept":
                concepts.append(
                    ExtractedConcept(
                        name=attrs.get("name", entity.extraction_text),
                        description=attrs.get("description", ""),
                        domain=attrs.get("domain", ""),
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

        extraction_result = LoreExtractionResult(
            locations=locations,
            items=items,
            creatures=creatures,
            factions=factions,
            concepts=concepts,
        )

        logger.info(
            "extraction_pass_completed",
            pass_name=PASS_NAME,
            book_id=book_id,
            chapter=chapter_number,
            locations=len(locations),
            items=len(items),
            creatures=len(creatures),
            factions=len(factions),
            concepts=len(concepts),
            grounded=len(grounded),
        )

        return {
            "lore": extraction_result,
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
            error=str(e),
        )
        return {
            "lore": LoreExtractionResult(),
            "grounded_entities": [],
            "passes_completed": [],
            "errors": [{"pass": PASS_NAME, "error": str(e)}],
        }
