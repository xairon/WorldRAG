"""Pydantic schemas for the pipeline configuration dashboard.

Defines response models for GET /pipeline/config which exposes
prompts, regex patterns, ontology, extraction graph topology,
Neo4j schema, and Pydantic extraction models — all read-only
metadata used by the frontend Pipeline Dashboard.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Prompts ──────────────────────────────────────────────────────────────


class PromptInfo(BaseModel):
    """Metadata about an extraction prompt template."""

    name: str
    pass_number: str
    description: str
    has_few_shot: bool = False
    few_shot_count: int = 0


# ── Regex Patterns ───────────────────────────────────────────────────────


class RegexPatternInfo(BaseModel):
    """A regex pattern used in Passe 0."""

    name: str
    entity_type: str
    pattern: str
    captures: dict[str, int] = Field(default_factory=dict)
    source: str = "hardcoded"


# ── Ontology ─────────────────────────────────────────────────────────────


class PropertyInfo(BaseModel):
    """A single property definition from the ontology."""

    name: str
    type: str = "string"
    required: bool = False
    unique: bool = False
    values: list[str] | None = None


class OntologyNodeTypeInfo(BaseModel):
    """A node type from the ontology."""

    name: str
    layer: str
    properties: list[PropertyInfo] = Field(default_factory=list)


class OntologyRelTypeInfo(BaseModel):
    """A relationship type from the ontology."""

    name: str
    from_type: str = ""
    to_type: str = ""
    layer: str = ""
    properties: list[PropertyInfo] = Field(default_factory=list)


# ── Extraction Graph ─────────────────────────────────────────────────────


class ExtractionGraphNode(BaseModel):
    """A node in the LangGraph extraction pipeline."""

    name: str
    description: str = ""
    node_type: str = "pass"


class ExtractionGraphEdge(BaseModel):
    """An edge in the LangGraph extraction pipeline."""

    source: str
    target: str
    edge_type: str = "normal"
    label: str = ""


class ExtractionGraphInfo(BaseModel):
    """LangGraph extraction pipeline topology."""

    nodes: list[ExtractionGraphNode] = Field(default_factory=list)
    edges: list[ExtractionGraphEdge] = Field(default_factory=list)


# ── Neo4j Schema ─────────────────────────────────────────────────────────


class ConstraintInfo(BaseModel):
    """A Neo4j uniqueness constraint."""

    name: str
    label: str
    properties: list[str] = Field(default_factory=list)


class IndexInfo(BaseModel):
    """A Neo4j index."""

    name: str
    index_type: str = "property"
    label: str = ""
    properties: list[str] = Field(default_factory=list)


class Neo4jSchemaInfo(BaseModel):
    """Summary of Neo4j schema (constraints + indexes)."""

    constraints: list[ConstraintInfo] = Field(default_factory=list)
    indexes: list[IndexInfo] = Field(default_factory=list)


# ── Extraction Models ────────────────────────────────────────────────────


class FieldInfo(BaseModel):
    """A field in a Pydantic extraction model."""

    name: str
    type: str
    required: bool = False
    default: str | None = None
    description: str = ""


class ExtractionModelInfo(BaseModel):
    """A Pydantic extraction model with its fields."""

    name: str
    pass_name: str = ""
    fields: list[FieldInfo] = Field(default_factory=list)


# ── Top-level response ───────────────────────────────────────────────────


class PipelineConfig(BaseModel):
    """Complete pipeline configuration for the dashboard."""

    prompts: list[PromptInfo] = Field(default_factory=list)
    regex_patterns: list[RegexPatternInfo] = Field(default_factory=list)
    ontology_node_types: list[OntologyNodeTypeInfo] = Field(
        default_factory=list,
    )
    ontology_rel_types: list[OntologyRelTypeInfo] = Field(
        default_factory=list,
    )
    extraction_graph: ExtractionGraphInfo = Field(
        default_factory=ExtractionGraphInfo,
    )
    neo4j_schema: Neo4jSchemaInfo = Field(
        default_factory=Neo4jSchemaInfo,
    )
    extraction_models: list[ExtractionModelInfo] = Field(
        default_factory=list,
    )


# ── Extraction request body ──────────────────────────────────────────────


class ExtractionRequest(BaseModel):
    """Request body for POST /books/{id}/extract."""

    chapters: list[int] | None = Field(
        None,
        description="Chapter numbers to extract. null = all chapters.",
    )


class ExtractionRequestV3(BaseModel):
    """Request body for POST /books/{id}/extract/v3."""

    chapters: list[int] | None = Field(
        None,
        description="Chapter numbers to extract. null = all chapters.",
    )
    language: str = Field(
        "fr",
        description="Source language of the book text.",
    )
    series_name: str | None = Field(
        None,
        description="Override series name for this extraction.",
    )
    genre: str | None = Field(
        None,
        description="Override genre for this extraction.",
    )


class ReprocessRequest(BaseModel):
    """Request body for POST /books/{id}/reprocess."""

    chapter_range: list[int] | None = Field(
        None,
        description="Specific chapters to reprocess. null = auto-detect.",
    )
    changes: list[dict] | None = Field(
        None,
        description="Ontology changes that triggered reprocessing.",
    )
