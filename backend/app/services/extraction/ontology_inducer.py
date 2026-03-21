"""Automatic ontology induction — discover entity/relation types from text.

Reads the first N chapters and asks the LLM to identify entity types and
relationship types that are NOT already covered by the loaded ontology layers.

This replaces the need for manually authoring Layer 2 (genre) and Layer 3
(series) YAML files for every new genre or series.

Usage:
    induced = await induce_ontology(chapters_text, ontology)
    ontology.extend_with_induced(induced)
"""

# NO from __future__ import annotations — Instructor needs runtime types
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.core.ontology_loader import OntologyLoader
from app.llm.providers import get_instructor_for_extraction

logger = structlog.get_logger()

# ── Pydantic response models for Instructor ────────────────────────────


class InducedEntityType(BaseModel):
    """A single entity type discovered from text."""

    name: str = Field(..., description="PascalCase entity type name (e.g. 'Bloodline', 'Profession')")
    description: str = Field("", description="What this entity type represents in the story")
    example_instances: list[str] = Field(
        default_factory=list,
        description="2-4 concrete examples found in the text",
    )
    properties: list[str] = Field(
        default_factory=list,
        description="Suggested property names for this type (e.g. 'tier', 'rank', 'effects')",
    )


class InducedRelationType(BaseModel):
    """A relationship type discovered from text."""

    name: str = Field(
        ...,
        description="UPPER_SNAKE_CASE relationship name (e.g. 'HAS_BLOODLINE')",
    )
    source_type: str = Field(..., description="Source entity type (PascalCase)")
    target_type: str = Field(..., description="Target entity type (PascalCase)")
    description: str = Field("", description="What this relationship represents")


class InducedOntology(BaseModel):
    """LLM-discovered entity types and relation types for a story."""

    entity_types: list[InducedEntityType] = Field(default_factory=list)
    relation_types: list[InducedRelationType] = Field(default_factory=list)


# ── Constants ──────────────────────────────────────────────────────────

_MAX_SAMPLE_CHARS = 30_000  # ~10K tokens at 3 chars/token
_MAX_CHAPTERS = 3

_SYSTEM_PROMPT = """\
You are an ontology engineer for a knowledge graph system that models fiction novels.

You will be given sample text from the first chapters of a novel. Your job is to \
identify **entity types** and **relationship types** that are important in this story \
but are NOT already defined in the existing ontology.

## Existing ontology types (DO NOT rediscover these)

### Entity types already defined:
{existing_entity_types}

### Relationship types already defined:
{existing_relation_types}

## Instructions

1. Read the sample text carefully.
2. Identify domain-specific entity types that appear repeatedly and are NOT in the \
existing list above. Focus on types that are **structurally important** to the story's \
world-building (e.g. game systems, magic types, social structures, progression mechanics).
3. For each new entity type, provide 2-4 concrete examples from the text and suggest \
useful properties.
4. Identify relationship types that connect these new types to each other or to \
existing types.
5. Use PascalCase for entity type names and UPPER_SNAKE_CASE for relationship names.
6. Be conservative — only propose types that appear multiple times and are clearly \
distinct from existing types. Prefer fewer, high-quality types over many speculative ones.
7. Do NOT propose types for individual characters, locations, or events — those are \
instances, not types.
"""


# ── Public API ─────────────────────────────────────────────────────────


async def induce_ontology(
    chapters_text: list[str],
    existing_ontology: OntologyLoader,
    model_override: str | None = None,
) -> dict[str, Any]:
    """Discover entity types and relation types from sample chapters.

    Reads the first N chapters and asks the LLM:
    "What entity types and relationship types are important in this story
    that are NOT already in the core ontology?"

    Args:
        chapters_text: List of chapter text strings (first few chapters).
        existing_ontology: Currently loaded ontology (to avoid rediscovery).
        model_override: Optional 'provider:model' override.

    Returns:
        A dict compatible with OntologyLoader.extend_with_induced():
        {
            "node_types": [{"name": "Bloodline", "properties": [...], "description": "..."}],
            "relationship_types": [{"name": "HAS_BLOODLINE", ...}],
        }
    """
    # 1. Build sample text from first N chapters, capped at token budget
    sample_chapters = chapters_text[:_MAX_CHAPTERS]
    sample_text = "\n\n---\n\n".join(sample_chapters)
    if len(sample_text) > _MAX_SAMPLE_CHARS:
        sample_text = sample_text[:_MAX_SAMPLE_CHARS]

    # 2. Build existing ontology context
    existing_entity_names = sorted(existing_ontology.get_node_type_names())
    existing_relation_names = sorted(existing_ontology.get_relationship_type_names())

    system_prompt = _SYSTEM_PROMPT.format(
        existing_entity_types=", ".join(existing_entity_names) if existing_entity_names else "(none)",
        existing_relation_types=", ".join(existing_relation_names) if existing_relation_names else "(none)",
    )

    # 3. Call Instructor
    client, model = get_instructor_for_extraction(model_override)

    logger.info(
        "ontology_induction_started",
        sample_chapters=len(sample_chapters),
        sample_chars=len(sample_text),
        existing_entity_types=len(existing_entity_names),
        existing_relation_types=len(existing_relation_names),
        model=model,
    )

    result: InducedOntology = await client.chat.completions.create(
        model=model,
        response_model=InducedOntology,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sample_text},
        ],
        max_retries=2,
    )

    # 4. Filter out any types that already exist (LLM sometimes rediscovers)
    existing_entity_set = {n.lower() for n in existing_entity_names}
    existing_relation_set = {n.lower() for n in existing_relation_names}

    new_entity_types = [
        et for et in result.entity_types if et.name.lower() not in existing_entity_set
    ]
    new_relation_types = [
        rt for rt in result.relation_types if rt.name.lower() not in existing_relation_set
    ]

    logger.info(
        "ontology_induction_completed",
        induced_entity_types=[et.name for et in new_entity_types],
        induced_relation_types=[rt.name for rt in new_relation_types],
        filtered_entity_types=len(result.entity_types) - len(new_entity_types),
        filtered_relation_types=len(result.relation_types) - len(new_relation_types),
    )

    return {
        "node_types": [
            {
                "name": et.name,
                "description": et.description,
                "example_instances": et.example_instances,
                "properties": et.properties,
            }
            for et in new_entity_types
        ],
        "relationship_types": [
            {
                "name": rt.name,
                "source_type": rt.source_type,
                "target_type": rt.target_type,
                "description": rt.description,
            }
            for rt in new_relation_types
        ],
    }
