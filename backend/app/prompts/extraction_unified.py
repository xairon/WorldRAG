"""Dynamic ontology-driven extraction prompts for WorldRAG v4 pipeline.

Prompts are generated from:
1. OntologyLoader — entity types + relation types active for the genre/series
2. templates/entity_descriptions.yaml — bilingual field descriptions per type
3. templates/few_shots.yaml — few-shot examples per genre + language
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from app.prompts.base import build_extraction_prompt

if TYPE_CHECKING:
    from app.core.ontology_loader import OntologyLoader

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_entity_descriptions: dict | None = None
_few_shots: dict | None = None


def _load_entity_descriptions() -> dict:
    global _entity_descriptions  # noqa: PLW0603
    if _entity_descriptions is None:
        with open(_TEMPLATES_DIR / "entity_descriptions.yaml", encoding="utf-8") as f:
            _entity_descriptions = yaml.safe_load(f) or {}
    return _entity_descriptions


def _load_few_shots() -> dict:
    global _few_shots  # noqa: PLW0603
    if _few_shots is None:
        with open(_TEMPLATES_DIR / "few_shots.yaml", encoding="utf-8") as f:
            _few_shots = yaml.safe_load(f) or {}
    return _few_shots


def _build_type_descriptions(ontology: OntologyLoader, language: str) -> str:
    """Build the [TASK] section listing active entity types with descriptions."""
    descs = _load_entity_descriptions()
    sections: list[str] = []

    # Preamble
    if language == "en":
        sections.append("Extract ALL narrative entities from this chapter in a single pass.")
    else:
        sections.append("Extrais TOUTES les entités narratives de ce chapitre en une seule passe.")

    # Core types (always active)
    core_descs = descs.get("core", {})
    if core_descs:
        header = "=== CORE ENTITY TYPES ===" if language == "en" else "=== TYPES D'ENTITÉS CORE ==="
        sections.append(header)
        for _type_name, lang_map in core_descs.items():
            text = lang_map.get(language, lang_map.get("en", ""))
            if text:
                sections.append(text.strip())

    # Genre types (only if a real genre layer loaded — not "core" loaded twice)
    genre_descs = descs.get("genre", {})
    has_genre = len(ontology.layers_loaded) > 1 and ontology.layers_loaded[1] != "core"
    if genre_descs and has_genre:
        genre_label = ontology.layers_loaded[1]
        header = (
            f"=== GENRE-SPECIFIC ENTITY TYPES ({genre_label.upper()}) ==="
            if language == "en"
            else f"=== TYPES D'ENTITÉS GENRE ({genre_label.upper()}) ==="
        )
        sections.append(header)
        # Check which types exist in the ontology (case-insensitive match)
        onto_types_lower = {k.lower() for k in ontology.node_types}
        for _type_name, lang_map in genre_descs.items():
            # Match "skill" to "Skill", "class_" to "Class", etc.
            clean_name = _type_name.rstrip("_")
            if (
                clean_name.lower() in onto_types_lower
                or clean_name.capitalize() in ontology.node_types
            ):
                text = lang_map.get(language, lang_map.get("en", ""))
                if text:
                    sections.append(text.strip())

    # Series types (only if series layer loaded)
    series_descs = descs.get("series", {})
    has_series = len(ontology.layers_loaded) > 2
    if series_descs and has_series:
        series_label = ontology.layers_loaded[2]
        header = (
            f"=== SERIES-SPECIFIC ({series_label.upper()}) ==="
            if language == "en"
            else f"=== SPÉCIFIQUE À LA SÉRIE ({series_label.upper()}) ==="
        )
        sections.append(header)
        onto_types_lower = {k.lower() for k in ontology.node_types}
        for _type_name, lang_map in series_descs.items():
            clean_name = _type_name.rstrip("_")
            if (
                clean_name.lower() in onto_types_lower
                or clean_name.capitalize() in ontology.node_types
            ):
                text = lang_map.get(language, lang_map.get("en", ""))
                if text:
                    sections.append(text.strip())

    return "\n\n".join(sections)


def _build_relation_descriptions(
    ontology: OntologyLoader,
    language: str,
) -> str:
    """Build relation type descriptions from ontology."""
    # Skip bibliographic/grounding relations
    skip = {
        "CONTAINS_WORK",
        "HAS_CHAPTER",
        "HAS_CHUNK",
        "GROUNDED_IN",
        "MENTIONED_IN",
        "STRUCTURED_BY",
        "FULFILLS",
    }

    if language == "en":
        lines = [
            "Extract ALL narrative relations between the entities already identified.",
            "",
            "=== RELATION TYPES ===",
            "",
        ]
    else:
        lines = [
            "Extrais TOUTES les relations narratives entre les entités déjà identifiées.",
            "",
            "=== TYPES DE RELATIONS ===",
            "",
        ]

    for rel_name, rel_type in ontology.relationship_types.items():
        if rel_name in skip:
            continue
        line = f"{rel_name} ({rel_type.from_type} → {rel_type.to_type})"
        if rel_type.properties:
            props = ", ".join(rel_type.properties.keys())
            line += f" — properties: {props}"
        lines.append(line)

    # Add temporal invalidation note
    if language == "en":
        lines.extend(
            [
                "",
                "=== TEMPORAL INVALIDATION ===",
                "",
                "If the text indicates a relation ENDS in this chapter "
                "(death, betrayal, skill lost, etc.),",
                "add a RelationEnd object with: relation_type, source, target, "
                "reason, ended_at_chapter.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "=== INVALIDATION TEMPORELLE ===",
                "",
                "Si le texte indique qu'une relation PREND FIN dans ce chapitre "
                "(mort, trahison, perte de skill, etc.),",
                "ajouter un objet RelationEnd avec : relation_type, source, target, "
                "reason, ended_at_chapter.",
            ]
        )

    return "\n".join(lines)


def _get_few_shots(genre: str, phase: str, language: str) -> str:
    """Load few-shot examples for genre + phase + language."""
    shots = _load_few_shots()
    genre_shots = shots.get(genre, shots.get("core", {}))
    phase_shots = genre_shots.get(phase, {})
    return phase_shots.get(language, phase_shots.get("en", ""))


def build_entity_prompt(
    ontology: OntologyLoader,
    language: str = "en",
    registry_context: str = "",
    phase0_hints: list[dict[str, Any]] | None = None,
    router_hints: list[str] | None = None,
) -> str:
    """Build Step 1 entity extraction prompt from ontology."""
    active_genre = (
        ontology.layers_loaded[1]
        if len(ontology.layers_loaded) > 1 and ontology.layers_loaded[1] != "core"
        else "core"
    )

    role = (
        "an expert in Knowledge Graph extraction for narrative fiction"
        if language == "en"
        else "un expert en extraction de Knowledge Graphs pour la fiction narrative"
    )

    type_descriptions = _build_type_descriptions(ontology, language)
    few_shots = _get_few_shots(active_genre, "entities", language)

    # Filter ontology schema to extractable types (exclude bibliographic)
    extractable = {
        k: v
        for k, v in ontology.to_json_schema().items()
        if k
        not in (
            "Series",
            "Book",
            "Chapter",
            "Chunk",
            "NarrativeFunction",
        )
    }

    return build_extraction_prompt(
        phase="entities",
        role_description=role,
        ontology_schema=extractable,
        task_instructions=type_descriptions,
        entity_registry_context=registry_context,
        phase0_hints=phase0_hints,
        router_hints=router_hints,
        few_shot_examples=few_shots,
        language=language,
    )


def build_relation_prompt(
    ontology: OntologyLoader,
    entities_json: str = "",
    language: str = "en",
) -> str:
    """Build Step 2 relation extraction prompt from ontology."""
    active_genre = (
        ontology.layers_loaded[1]
        if len(ontology.layers_loaded) > 1 and ontology.layers_loaded[1] != "core"
        else "core"
    )

    role = (
        "an expert in narrative relation analysis for Knowledge Graphs"
        if language == "en"
        else "un expert en analyse de relations narratives pour Knowledge Graphs"
    )

    relation_descriptions = _build_relation_descriptions(ontology, language)
    few_shots = _get_few_shots(active_genre, "relations", language)

    return build_extraction_prompt(
        phase="relations",
        role_description=role,
        ontology_schema={},
        task_instructions=relation_descriptions,
        extracted_entities_json=entities_json,
        few_shot_examples=few_shots,
        language=language,
    )
