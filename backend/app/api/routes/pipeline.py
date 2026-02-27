"""Pipeline configuration API — exposes extraction pipeline metadata.

Returns prompts, regex patterns, ontology definitions, extraction graph
topology, Neo4j schema, and Pydantic model introspection for the
frontend Pipeline Dashboard.

All data is static (loaded from source files at startup) and cached.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.logging import get_logger
from app.core.ontology_loader import OntologyLoader
from app.schemas.pipeline import (
    ConstraintInfo,
    ExtractionGraphEdge,
    ExtractionGraphInfo,
    ExtractionGraphNode,
    ExtractionModelInfo,
    FieldInfo,
    IndexInfo,
    Neo4jSchemaInfo,
    OntologyNodeTypeInfo,
    OntologyRelTypeInfo,
    PipelineConfig,
    PromptInfo,
    PropertyInfo,
    RegexPatternInfo,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# ── Module-level cache ───────────────────────────────────────────────────

_cached_config: PipelineConfig | None = None

# ── Prompt metadata ──────────────────────────────────────────────────────

_PROMPT_MODULES: dict[str, dict[str, str | None]] = {
    "extraction_characters": {
        "var": "PROMPT_DESCRIPTION",
        "few_shot_var": "FEW_SHOT_EXAMPLES",
        "pass": "Pass 1: Characters & Relationships",
    },
    "extraction_systems": {
        "var": "PROMPT_DESCRIPTION",
        "few_shot_var": "FEW_SHOT_EXAMPLES",
        "pass": "Pass 2: Systems & Progression",
    },
    "extraction_events": {
        "var": "PROMPT_DESCRIPTION",
        "few_shot_var": "FEW_SHOT_EXAMPLES",
        "pass": "Pass 3: Events & Timeline",
    },
    "extraction_lore": {
        "var": "PROMPT_DESCRIPTION",
        "few_shot_var": "FEW_SHOT_EXAMPLES",
        "pass": "Pass 4: Lore & Worldbuilding",
    },
    "extraction_provenance": {
        "var": "PROVENANCE_SYSTEM_PROMPT",
        "few_shot_var": None,
        "pass": "Pass 2b: Skill Provenance",
    },
    "extraction_series": {
        "var": "SERIES_SYSTEM_PROMPT",
        "few_shot_var": None,
        "pass": "Pass 4b: Series-Specific (Layer 3)",
    },
    "coreference": {
        "var": "COREFERENCE_PROMPT",
        "few_shot_var": None,
        "pass": "Pass 5b: Coreference Resolution",
    },
    "narrative_analysis": {
        "var": "NARRATIVE_ANALYSIS_PROMPT",
        "few_shot_var": None,
        "pass": "Pass 6: Narrative Analysis",
    },
}

# ── Extraction graph topology (hardcoded from LangGraph definition) ──────

_GRAPH_NODES = [
    ExtractionGraphNode(
        name="route",
        description="Keyword-based routing to select passes",
        node_type="route",
    ),
    ExtractionGraphNode(
        name="characters",
        description="Pass 1: Character & Relationship extraction",
        node_type="pass",
    ),
    ExtractionGraphNode(
        name="systems",
        description="Pass 2: System & Progression extraction",
        node_type="pass",
    ),
    ExtractionGraphNode(
        name="events",
        description="Pass 3: Event & Timeline extraction",
        node_type="pass",
    ),
    ExtractionGraphNode(
        name="lore",
        description="Pass 4: Lore & Worldbuilding extraction",
        node_type="pass",
    ),
    ExtractionGraphNode(
        name="merge",
        description="Combine results from all passes",
        node_type="merge",
    ),
    ExtractionGraphNode(
        name="mention_detect",
        description="Pass 5: Programmatic mention detection",
        node_type="postprocess",
    ),
    ExtractionGraphNode(
        name="reconcile",
        description="3-tier entity deduplication",
        node_type="postprocess",
    ),
    ExtractionGraphNode(
        name="narrative",
        description="Pass 6: Narrative structure analysis",
        node_type="postprocess",
    ),
]

_GRAPH_EDGES = [
    ExtractionGraphEdge(
        source="START",
        target="route",
        edge_type="normal",
    ),
    ExtractionGraphEdge(
        source="route",
        target="characters",
        edge_type="fan_out",
        label="conditional",
    ),
    ExtractionGraphEdge(
        source="route",
        target="systems",
        edge_type="fan_out",
        label="conditional",
    ),
    ExtractionGraphEdge(
        source="route",
        target="events",
        edge_type="fan_out",
        label="conditional",
    ),
    ExtractionGraphEdge(
        source="route",
        target="lore",
        edge_type="fan_out",
        label="conditional",
    ),
    ExtractionGraphEdge(
        source="characters",
        target="merge",
        edge_type="normal",
    ),
    ExtractionGraphEdge(
        source="systems",
        target="merge",
        edge_type="normal",
    ),
    ExtractionGraphEdge(
        source="events",
        target="merge",
        edge_type="normal",
    ),
    ExtractionGraphEdge(
        source="lore",
        target="merge",
        edge_type="normal",
    ),
    ExtractionGraphEdge(
        source="merge",
        target="mention_detect",
        edge_type="normal",
    ),
    ExtractionGraphEdge(
        source="mention_detect",
        target="reconcile",
        edge_type="normal",
        label="parallel",
    ),
    ExtractionGraphEdge(
        source="mention_detect",
        target="narrative",
        edge_type="normal",
        label="parallel",
    ),
    ExtractionGraphEdge(
        source="reconcile",
        target="END",
        edge_type="normal",
    ),
    ExtractionGraphEdge(
        source="narrative",
        target="END",
        edge_type="normal",
    ),
]

# ── Extraction model → pass mapping ──────────────────────────────────────

_MODEL_PASS_MAP: dict[str, str] = {
    "ExtractedCharacter": "Pass 1",
    "ExtractedRelationship": "Pass 1",
    "ExtractedSkill": "Pass 2",
    "ExtractedClass": "Pass 2",
    "ExtractedTitle": "Pass 2",
    "ExtractedLevelChange": "Pass 2",
    "ExtractedStatChange": "Pass 2",
    "ExtractedEvent": "Pass 3",
    "ExtractedLocation": "Pass 4",
    "ExtractedItem": "Pass 4",
    "ExtractedCreature": "Pass 4",
    "ExtractedFaction": "Pass 4",
    "ExtractedConcept": "Pass 4",
    "ExtractedBloodline": "Layer 3",
    "ExtractedProfession": "Layer 3",
    "ExtractedChurch": "Layer 3",
}


# ── Config builder functions ─────────────────────────────────────────────


def _build_prompts() -> list[PromptInfo]:
    """Load prompt descriptions from prompt modules."""
    prompts: list[PromptInfo] = []
    for module_name, meta in _PROMPT_MODULES.items():
        try:
            mod = importlib.import_module(f"app.prompts.{module_name}")
            var_name = meta["var"] or ""
            description = getattr(mod, var_name, "")
            few_shot_var = meta["few_shot_var"]
            few_shot = getattr(mod, few_shot_var, None) if isinstance(few_shot_var, str) else None
            prompts.append(
                PromptInfo(
                    name=module_name,
                    pass_number=str(meta["pass"]),
                    description=str(description),
                    has_few_shot=few_shot is not None,
                    few_shot_count=len(few_shot) if few_shot else 0,
                )
            )
        except Exception:
            logger.warning("pipeline_prompt_load_failed", module=module_name, exc_info=True)
    return prompts


def _build_regex_patterns() -> list[RegexPatternInfo]:
    """Load regex patterns from the extractor."""
    from app.services.extraction.regex_extractor import RegexExtractor

    extractor = RegexExtractor.default()
    return [
        RegexPatternInfo(
            name=p.name,
            entity_type=p.entity_type,
            pattern=p.pattern.pattern,
            captures=p.captures,
            source="hardcoded",
        )
        for p in extractor.patterns
    ]


def _build_ontology() -> tuple[list[OntologyNodeTypeInfo], list[OntologyRelTypeInfo]]:
    """Load ontology from YAML layers and serialize."""
    # Load each layer separately to track origin
    layer_node_keys: dict[str, set[str]] = {}

    for layer_name, (genre, series) in {
        "core": ("litrpg", ""),
        "litrpg": ("litrpg", ""),
        "primal_hunter": ("litrpg", "primal_hunter"),
    }.items():
        loader = OntologyLoader.from_layers(genre, series)
        layer_node_keys[layer_name] = set(loader.node_types.keys())

    # Determine which layer introduced each type
    core_keys = layer_node_keys.get("core", set())
    litrpg_only = layer_node_keys.get("litrpg", set()) - core_keys
    ph_only = layer_node_keys.get("primal_hunter", set()) - layer_node_keys.get("litrpg", set())

    def _get_layer(name: str) -> str:
        if name in ph_only:
            return "primal_hunter"
        if name in litrpg_only:
            return "litrpg"
        return "core"

    # Full ontology with all layers
    full = OntologyLoader.from_layers("litrpg", "primal_hunter")

    node_types = [
        OntologyNodeTypeInfo(
            name=nt.name,
            layer=_get_layer(nt.name),
            properties=[
                PropertyInfo(
                    name=p.name,
                    type=p.type,
                    required=p.required,
                    unique=p.unique,
                    values=p.values,
                )
                for p in nt.properties.values()
            ],
        )
        for nt in full.node_types.values()
    ]

    # Same approach for relationship types
    rel_types = [
        OntologyRelTypeInfo(
            name=rt.name,
            from_type=rt.from_type,
            to_type=rt.to_type,
            layer=_get_layer(rt.name),
            properties=[
                PropertyInfo(
                    name=p.name,
                    type=p.type,
                    required=p.required,
                    values=p.values,
                )
                for p in rt.properties.values()
            ],
        )
        for rt in full.relationship_types.values()
    ]

    return node_types, rel_types


def _build_neo4j_schema() -> Neo4jSchemaInfo:
    """Parse init_neo4j.cypher to extract constraints and indexes."""
    cypher_path = Path(__file__).resolve().parents[4] / "scripts" / "init_neo4j.cypher"
    if not cypher_path.exists():
        return Neo4jSchemaInfo()

    text = cypher_path.read_text(encoding="utf-8")

    constraints: list[ConstraintInfo] = []
    indexes: list[IndexInfo] = []

    # Parse: CREATE CONSTRAINT name IF NOT EXISTS FOR (x:Label) REQUIRE ...
    for m in re.finditer(
        r"CREATE CONSTRAINT (\w+) IF NOT EXISTS\s+FOR \(\w+:(\w+)\)\s+REQUIRE\s+(.+?);",
        text,
        re.DOTALL,
    ):
        name, label, require_clause = m.group(1), m.group(2), m.group(3)
        props = re.findall(r"\w+\.(\w+)", require_clause)
        constraints.append(ConstraintInfo(name=name, label=label, properties=props))

    # Parse: CREATE INDEX name IF NOT EXISTS FOR (x:Label) ON (x.prop)
    for m in re.finditer(
        r"CREATE (?:INDEX|FULLTEXT INDEX|VECTOR INDEX) (\w+) IF NOT EXISTS\s+"
        r"FOR \(\w+:([A-Za-z|]+)\)\s+ON\s+(?:EACH\s+)?\((.+?)\)",
        text,
    ):
        name, label, on_clause = m.group(1), m.group(2), m.group(3)
        props = re.findall(r"\w+\.(\w+)", on_clause)
        idx_type = "fulltext" if "FULLTEXT" in text[m.start() : m.end()] else "property"
        indexes.append(
            IndexInfo(
                name=name,
                index_type=idx_type,
                label=label,
                properties=props,
            )
        )

    # Parse vector index
    for m in re.finditer(
        r"CREATE VECTOR INDEX (\w+) IF NOT EXISTS\s+"
        r"FOR \(\w+:(\w+)\)\s+ON\s+\((\w+\.\w+)\)",
        text,
    ):
        name, label, prop = m.group(1), m.group(2), m.group(3)
        indexes.append(
            IndexInfo(
                name=name,
                index_type="vector",
                label=label,
                properties=[prop.split(".")[-1]],
            )
        )

    # Parse relationship indexes
    for m in re.finditer(
        r"CREATE INDEX (\w+) IF NOT EXISTS\s+"
        r"FOR \(\)-\[r:(\w+)\]-\(\)\s+ON\s+\((.+?)\)",
        text,
    ):
        name, rel_type, on_clause = m.group(1), m.group(2), m.group(3)
        props = re.findall(r"r\.(\w+)", on_clause)
        indexes.append(
            IndexInfo(
                name=name,
                index_type="relationship",
                label=rel_type,
                properties=props,
            )
        )

    return Neo4jSchemaInfo(constraints=constraints, indexes=indexes)


def _build_extraction_models() -> list[ExtractionModelInfo]:
    """Introspect Pydantic extraction models."""
    from app.schemas import extraction as ext_mod

    models: list[ExtractionModelInfo] = []
    for class_name, pass_name in _MODEL_PASS_MAP.items():
        cls = getattr(ext_mod, class_name, None)
        if cls is None:
            continue

        fields: list[FieldInfo] = []
        for fname, finfo in cls.model_fields.items():
            ftype = str(finfo.annotation) if finfo.annotation else "Any"
            # Clean up type repr
            ftype = ftype.replace("typing.", "").replace("<class '", "").replace("'>", "")
            fields.append(
                FieldInfo(
                    name=fname,
                    type=ftype,
                    required=finfo.is_required(),
                    default=str(finfo.default) if finfo.default is not None else None,
                    description=finfo.description or "",
                )
            )

        models.append(
            ExtractionModelInfo(
                name=class_name,
                pass_name=pass_name,
                fields=fields,
            )
        )

    return models


def _build_pipeline_config() -> PipelineConfig:
    """Build the complete pipeline config (called once, cached)."""
    node_types, rel_types = _build_ontology()

    return PipelineConfig(
        prompts=_build_prompts(),
        regex_patterns=_build_regex_patterns(),
        ontology_node_types=node_types,
        ontology_rel_types=rel_types,
        extraction_graph=ExtractionGraphInfo(
            nodes=_GRAPH_NODES,
            edges=_GRAPH_EDGES,
        ),
        neo4j_schema=_build_neo4j_schema(),
        extraction_models=_build_extraction_models(),
    )


# ── Endpoint ─────────────────────────────────────────────────────────────


@router.get("/config", response_model=PipelineConfig)
async def get_pipeline_config() -> PipelineConfig:
    """Return all pipeline configuration metadata (cached)."""
    global _cached_config  # noqa: PLW0603
    if _cached_config is None:
        _cached_config = _build_pipeline_config()
    return _cached_config


def _extract_model_field_info(field_info: Any) -> dict[str, Any]:
    """Extract serializable field info from a Pydantic FieldInfo."""
    return {
        "name": field_info.name if hasattr(field_info, "name") else "",
        "type": str(field_info.annotation) if field_info.annotation else "Any",
        "required": field_info.is_required(),
        "default": str(field_info.default) if field_info.default is not None else None,
    }
