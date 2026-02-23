"""Pass 1 — Character & Relationship extraction via LangExtract.

Extracts characters (names, roles, species) and their relationships
from chapter text using LangExtract with source grounding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import langextract as lx

from app.config import settings
from app.core.logging import get_logger
from app.prompts.extraction_characters import FEW_SHOT_EXAMPLES, PROMPT_DESCRIPTION
from app.schemas.extraction import (
    CharacterExtractionResult,
    ExtractedCharacter,
    ExtractedRelationship,
    GroundedEntity,
)

if TYPE_CHECKING:
    from app.agents.state import ExtractionPipelineState

logger = get_logger(__name__)

PASS_NAME = "characters"


async def extract_characters(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Extract characters and relationships from chapter text.

    Reads chapter_text from state, runs LangExtract with character-focused
    prompts, and returns structured CharacterExtractionResult.

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

        # Parse LangExtract output into structured schemas
        characters: list[ExtractedCharacter] = []
        relationships: list[ExtractedRelationship] = []
        grounded: list[GroundedEntity] = []

        for entity in result.extractions:
            attrs = entity.attributes or {}

            if entity.extraction_class == "character":
                characters.append(
                    ExtractedCharacter(
                        name=entity.extraction_text,
                        canonical_name=attrs.get("canonical_name", entity.extraction_text),
                        aliases=[a.strip() for a in attrs.get("alias", "").split(",") if a.strip()],
                        description=attrs.get("description", ""),
                        role=attrs.get("role", "minor"),
                        species=attrs.get("species", ""),
                        first_appearance_chapter=chapter_number,
                    )
                )

            elif entity.extraction_class == "relationship":
                relationships.append(
                    ExtractedRelationship(
                        source=attrs.get("source", ""),
                        target=attrs.get("target", ""),
                        rel_type=attrs.get("type", "ally"),
                        subtype=attrs.get("subtype", ""),
                        context=attrs.get("context", entity.extraction_text),
                        since_chapter=chapter_number,
                    )
                )

            elif entity.extraction_class == "faction_membership":
                # Faction memberships are stored as relationships too
                relationships.append(
                    ExtractedRelationship(
                        source=attrs.get("character", ""),
                        target=attrs.get("faction", ""),
                        rel_type="member",
                        subtype=attrs.get("role", "member"),
                        context=entity.extraction_text,
                        since_chapter=chapter_number,
                    )
                )

            # Build grounding for every entity
            if entity.char_interval:
                grounded.append(
                    GroundedEntity(
                        entity_type=entity.extraction_class,
                        entity_name=attrs.get("canonical_name", entity.extraction_text),
                        extraction_text=entity.extraction_text,
                        char_offset_start=entity.char_interval.start_pos,
                        char_offset_end=entity.char_interval.end_pos,
                        attributes=attrs,
                        pass_name=PASS_NAME,
                    )
                )

        extraction_result = CharacterExtractionResult(
            characters=characters,
            relationships=relationships,
        )

        logger.info(
            "extraction_pass_completed",
            pass_name=PASS_NAME,
            book_id=book_id,
            chapter=chapter_number,
            characters=len(characters),
            relationships=len(relationships),
            grounded=len(grounded),
        )

        return {
            "characters": extraction_result,
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
            "characters": CharacterExtractionResult(),
            "grounded_entities": [],
            "passes_completed": [],
            "errors": [{"pass": PASS_NAME, "error": str(e)}],
        }
