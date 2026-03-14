"""Pydantic data models for SagaProfile — schema-level description of a novel saga's KG ontology."""

from pydantic import BaseModel


class InducedEntityType(BaseModel):
    """An entity type induced from saga text, mapped to a universal parent type."""

    type_name: str  # PascalCase, e.g. "Spell", "House"
    parent_universal: str  # Character, Location, Object, Organization, Event, Concept
    description: str
    instances_found: list[str] = []
    typical_attributes: list[str] = []
    confidence: float  # 0.0–1.0


class InducedRelationType(BaseModel):
    """A relationship type induced from saga text between two entity types."""

    relation_name: str  # snake_case
    source_type: str
    target_type: str
    cardinality: str  # "1:1", "1:N", "N:N"
    temporal: bool
    description: str


class InducedPattern(BaseModel):
    """A regex text pattern induced from saga text for structured extraction."""

    pattern_regex: str
    extraction_type: str
    example: str
    confidence: float  # 0.0–1.0


class SagaProfile(BaseModel):
    """Full ontology profile for a novel saga, capturing induced entity types,
    relation types, text patterns, and narrative systems."""

    saga_id: str
    saga_name: str
    source_book: str
    version: int = 1
    entity_types: list[InducedEntityType]
    relation_types: list[InducedRelationType]
    text_patterns: list[InducedPattern]
    narrative_systems: list[str] = []
    estimated_complexity: str = "medium"  # low, medium, high
