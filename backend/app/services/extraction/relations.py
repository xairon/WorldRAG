"""Step 2: Relation extraction node for the v4 pipeline.

Receives entities from Step 1 + chapter text. Extracts relations between
entities and detects temporal invalidations (RelationEnd).
"""

import json
from typing import Any

import structlog

from app.core.ontology_loader import OntologyLoader
from app.llm.providers import get_instructor_for_extraction
from app.prompts.extraction_unified import build_relation_prompt
from app.schemas.extraction_v4 import RelationExtractionResult, _make_coercer

logger = structlog.get_logger()


async def _call_instructor_relations(
    prompt: str,
    chapter_text: str,
    model_override: str | None,
    dynamic_context: str = "",
) -> RelationExtractionResult:
    """Call Instructor for relation extraction. Separated for testability.

    When dynamic_context is provided (split prompt mode for Gemini caching),
    the static system prompt stays identical across chapters (cacheable),
    and the dynamic context + chapter text go in the user message.
    """
    client, model = get_instructor_for_extraction(model_override)
    if dynamic_context:
        user_content = f"{dynamic_context}\n\n[TEXT]\n{chapter_text}"
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]
    else:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": chapter_text},
        ]
    return await client.chat.completions.create(
        model=model,
        response_model=RelationExtractionResult,
        messages=messages,
        max_retries=2,
    )


async def extract_relations_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Step 2 relation extraction.

    Reads: chapter_text, chapter_number, entities, source_language, model_override
    Writes: relations, ended_relations
    """
    chapter_text = state["chapter_text"]
    chapter_number = state["chapter_number"]
    ontology: OntologyLoader = state["ontology"]
    entities = state.get("entities", [])

    # Serialize entities for prompt injection
    entities_json = json.dumps(entities, ensure_ascii=False, indent=2)

    # Build prompt — split mode for Gemini prefix caching
    prompt_result = build_relation_prompt(
        ontology=ontology,
        entities_json=entities_json,
        language=state.get("source_language", "en"),
        split_for_caching=True,
    )
    static_prompt, dynamic_context = prompt_result  # type: ignore[misc]

    # Call LLM — static system prompt is cacheable across chapters
    result = await _call_instructor_relations(
        static_prompt, chapter_text, state.get("model_override"), dynamic_context
    )

    # Post-coerce relation types from ontology
    allowed = set(ontology.get_relationship_type_names())
    coerce = _make_coercer(allowed, default="RELATES_TO")

    relations_serialized = []
    for rel in result.relations:
        d = rel.model_dump()
        d["relation_type"] = coerce(d["relation_type"])
        if d.get("valid_from_chapter") is None:
            d["valid_from_chapter"] = chapter_number
        relations_serialized.append(d)

    ended_serialized = [e.model_dump() for e in result.ended_relations]

    logger.info(
        "v4_relations_extracted",
        chapter=chapter_number,
        relations=len(relations_serialized),
        ended=len(ended_serialized),
    )

    return {
        "relations": relations_serialized,
        "ended_relations": ended_serialized,
    }
