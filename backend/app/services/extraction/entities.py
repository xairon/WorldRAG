"""Step 1: Entity extraction node for the v4 pipeline.

Extracts all entity types (15 types) from chapter text using Instructor.
Post-validates grounding offsets. Returns entities + grounded_entities.
"""
# NO from __future__ import annotations
import json
from typing import Any

import structlog

from app.core.ontology_loader import OntologyLoader
from app.llm.providers import get_instructor_for_extraction
from app.prompts.extraction_unified import build_entity_prompt
from app.schemas.extraction import GroundedEntity
from app.schemas.extraction_v4 import EntityExtractionResult
from app.services.extraction.entity_registry import EntityRegistry
from app.services.extraction.grounding import validate_and_fix_grounding

logger = structlog.get_logger()


async def _call_instructor(
    prompt: str,
    chapter_text: str,
    model_override: str | None,
) -> EntityExtractionResult:
    """Call Instructor to extract entities. Separated for testability."""
    client, model = get_instructor_for_extraction(model_override)
    return await client.chat.completions.create(
        model=model,
        response_model=EntityExtractionResult,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": chapter_text},
        ],
        max_retries=1,
    )


async def extract_entities_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Step 1 entity extraction.

    Reads from state: chapter_text, chapter_number, regex_matches_json, genre,
                      source_language, model_override, entity_registry
    Writes to state: entities, grounded_entities, total_entities
    """
    chapter_text = state["chapter_text"]
    chapter_number = state["chapter_number"]
    ontology: OntologyLoader = state["ontology"]

    # Build registry context
    registry = EntityRegistry.from_dict(state.get("entity_registry", {}))
    registry_context = registry.to_prompt_context()

    # Parse Phase 0 hints — stored or live fallback
    stored_hints = json.loads(state.get("regex_matches_json", "[]"))
    if not stored_hints:
        try:
            from app.services.extraction.regex_extractor import RegexExtractor

            extractor = RegexExtractor.from_ontology(ontology)
            stored_hints = extractor.extract(chapter_text)
        except Exception:
            pass  # regex is optional
    phase0_hints = stored_hints

    # Router hints (import here exists at module level)
    # Use try/except in case router module has issues
    router_hints: list[str] = []
    try:
        from app.services.extraction.router import compute_router_hints
        router_hints = compute_router_hints(chapter_text, state.get("genre", "litrpg"))
    except (ImportError, AttributeError):
        pass  # router hints are optional

    # Build prompt
    prompt = build_entity_prompt(
        ontology=ontology,
        language=state.get("source_language", "en"),
        registry_context=registry_context,
        phase0_hints=phase0_hints,
        router_hints=router_hints,
    )

    # Call LLM
    result = await _call_instructor(prompt, chapter_text, state.get("model_override"))
    result.chapter_number = chapter_number

    # Post-validate grounding
    grounded_entities: list[dict[str, Any]] = []
    entities_serialized: list[dict[str, Any]] = []

    for entity in result.entities:
        status, confidence = validate_and_fix_grounding(entity, chapter_text)

        # Get entity name (different fields per type)
        entity_name = (
            getattr(entity, "name", "")
            or getattr(entity, "character", "")
        )

        ge = GroundedEntity(
            entity_type=entity.entity_type,
            entity_name=entity_name,
            extraction_text=entity.extraction_text,
            char_offset_start=entity.char_offset_start,
            char_offset_end=entity.char_offset_end,
            alignment_status=status,
            confidence=confidence,
            pass_name="entities",
        )
        grounded_entities.append(ge.model_dump())
        entities_serialized.append(entity.model_dump())

    total = len(entities_serialized)
    logger.info("v4_entities_extracted", chapter=chapter_number, count=total)

    return {
        "entities": entities_serialized,
        "grounded_entities": grounded_entities,
        "total_entities": total,
    }
