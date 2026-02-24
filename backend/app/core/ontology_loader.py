"""Runtime ontology loader — reads YAML ontology layers and provides validation.

Loads the 3-layer ontology (core → genre → series) with inheritance,
extracts enum constraints, and provides validation functions for
extraction results.

Usage:
    ontology = OntologyLoader.from_layers("litrpg", "primal_hunter")
    errors = ontology.validate_character_role("wizard")  # -> ["Invalid role..."]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default ontology directory relative to project root
_ONTOLOGY_DIR = Path(__file__).resolve().parents[3] / "ontology"


@dataclass
class OntologyProperty:
    """A single property definition from the ontology."""

    name: str
    type: str
    required: bool = False
    unique: bool = False
    values: list[str] | None = None  # For enum types
    default: Any = None


@dataclass
class OntologyNodeType:
    """A node type definition with its properties."""

    name: str
    properties: dict[str, OntologyProperty] = field(default_factory=dict)
    constraints: list[dict] = field(default_factory=list)
    indexes: list[dict] = field(default_factory=list)


@dataclass
class OntologyRelationType:
    """A relationship type definition."""

    name: str
    from_type: str
    to_type: str
    properties: dict[str, OntologyProperty] = field(default_factory=dict)


@dataclass
class OntologyLoader:
    """Loaded ontology with layered inheritance and enum validation.

    The ontology is composed of up to 3 layers:
      - Layer 1 (core): Universal narrative entities
      - Layer 2 (genre): LitRPG / cultivation / sci-fi specific
      - Layer 3 (series): Per-series config (e.g., Primal Hunter)
    """

    node_types: dict[str, OntologyNodeType] = field(default_factory=dict)
    relationship_types: dict[str, OntologyRelationType] = field(default_factory=dict)
    enum_constraints: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    series_info: dict[str, Any] = field(default_factory=dict)
    regex_patterns: dict[str, dict] = field(default_factory=dict)
    few_shot_examples: dict[str, list] = field(default_factory=dict)
    layers_loaded: list[str] = field(default_factory=list)

    @classmethod
    def from_layers(
        cls,
        genre: str = "litrpg",
        series: str = "",
        ontology_dir: Path | str | None = None,
    ) -> OntologyLoader:
        """Load ontology by composing layers.

        Args:
            genre: Genre layer name (maps to {genre}.yaml).
            series: Series layer name (maps to {series}.yaml). Empty to skip.
            ontology_dir: Override ontology directory.

        Returns:
            OntologyLoader with all layers merged.
        """
        base_dir = Path(ontology_dir) if ontology_dir else _ONTOLOGY_DIR
        loader = cls()

        # Layer 1: Core (always loaded)
        core_path = base_dir / "core.yaml"
        if core_path.exists():
            loader._load_layer(core_path, "core")

        # Layer 2: Genre
        genre_path = base_dir / f"{genre}.yaml"
        if genre_path.exists():
            loader._load_layer(genre_path, genre)
        else:
            logger.warning("ontology_genre_not_found", genre=genre, path=str(genre_path))

        # Layer 3: Series (optional)
        if series:
            series_path = base_dir / f"{series}.yaml"
            if series_path.exists():
                loader._load_layer(series_path, series)
            else:
                logger.warning(
                    "ontology_series_not_found",
                    series=series,
                    path=str(series_path),
                )

        # Build enum constraints index
        loader._build_enum_index()

        logger.info(
            "ontology_loaded",
            layers=loader.layers_loaded,
            node_types=len(loader.node_types),
            relationship_types=len(loader.relationship_types),
            enum_constraints=sum(len(v) for v in loader.enum_constraints.values()),
        )

        return loader

    def _load_layer(self, path: Path, layer_name: str) -> None:
        """Load a single YAML layer and merge into current state."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return

        # Merge node types
        for type_name, type_def in (data.get("node_types") or {}).items():
            props = {}
            for prop_name, prop_def in (type_def.get("properties") or {}).items():
                if isinstance(prop_def, dict):
                    props[prop_name] = OntologyProperty(
                        name=prop_name,
                        type=prop_def.get("type", "string"),
                        required=prop_def.get("required", False),
                        unique=prop_def.get("unique", False),
                        values=prop_def.get("values"),
                        default=prop_def.get("default"),
                    )

            node_type = OntologyNodeType(
                name=type_name,
                properties=props,
                constraints=type_def.get("constraints", []),
                indexes=type_def.get("indexes", []),
            )

            if type_name in self.node_types:
                # Merge: later layers extend earlier ones
                self.node_types[type_name].properties.update(props)
                self.node_types[type_name].constraints.extend(node_type.constraints)
                self.node_types[type_name].indexes.extend(node_type.indexes)
            else:
                self.node_types[type_name] = node_type

        # Merge relationship types
        for rel_name, rel_def in (data.get("relationship_types") or {}).items():
            props = {}
            for prop_name, prop_def in (rel_def.get("properties") or {}).items():
                if isinstance(prop_def, dict):
                    props[prop_name] = OntologyProperty(
                        name=prop_name,
                        type=prop_def.get("type", "string"),
                        required=prop_def.get("required", False),
                        values=prop_def.get("values"),
                    )

            self.relationship_types[rel_name] = OntologyRelationType(
                name=rel_name,
                from_type=rel_def.get("from", ""),
                to_type=rel_def.get("to", ""),
                properties=props,
            )

        # Series info (Layer 3)
        if "series_info" in data:
            self.series_info.update(data["series_info"])

        # Regex patterns
        if "regex_patterns" in data:
            self.regex_patterns.update(data["regex_patterns"])

        # Few-shot examples
        if "few_shot_examples" in data:
            self.few_shot_examples.update(data["few_shot_examples"])

        self.layers_loaded.append(layer_name)

    def _build_enum_index(self) -> None:
        """Build a fast lookup of enum constraints per node type."""
        for type_name, node_type in self.node_types.items():
            enums: dict[str, list[str]] = {}
            for prop_name, prop in node_type.properties.items():
                if prop.type == "enum" and prop.values:
                    enums[prop_name] = prop.values
            if enums:
                self.enum_constraints[type_name] = enums

    def get_allowed_values(self, node_type: str, property_name: str) -> list[str] | None:
        """Get allowed enum values for a node type property.

        Returns None if the property is not an enum.
        """
        type_enums = self.enum_constraints.get(node_type, {})
        return type_enums.get(property_name)

    def validate_value(
        self,
        node_type: str,
        property_name: str,
        value: str,
    ) -> str | None:
        """Validate a single value against ontology enum constraints.

        Returns None if valid, error message if invalid.
        """
        allowed = self.get_allowed_values(node_type, property_name)
        if allowed is None:
            return None  # Not an enum — anything goes
        if value in allowed:
            return None
        return f"Invalid {property_name}={value!r} for {node_type}. Allowed: {allowed}"

    def validate_entity(
        self,
        node_type: str,
        properties: dict[str, Any],
    ) -> list[str]:
        """Validate an entity's properties against ontology constraints.

        Returns list of validation error messages (empty if valid).
        """
        errors: list[str] = []
        type_def = self.node_types.get(node_type)
        if type_def is None:
            return errors  # Unknown type — skip validation

        for prop_name, prop_def in type_def.properties.items():
            value = properties.get(prop_name)

            # Check required
            if prop_def.required and (value is None or value == ""):
                errors.append(f"{node_type}.{prop_name} is required but missing")

            # Check enum
            is_enum = prop_def.type == "enum" and prop_def.values
            if value and is_enum and value not in prop_def.values:
                errors.append(f"{node_type}.{prop_name}={value!r} not in {prop_def.values}")

        return errors

    def get_node_type_names(self) -> list[str]:
        """Get all registered node type names."""
        return list(self.node_types.keys())

    def get_relationship_type_names(self) -> list[str]:
        """Get all registered relationship type names."""
        return list(self.relationship_types.keys())


# ── Module-level singleton ─────────────────────────────────────────────────

_loaded_ontology: OntologyLoader | None = None


def get_ontology(
    genre: str = "litrpg",
    series: str = "",
    reload: bool = False,
) -> OntologyLoader:
    """Get or create the singleton ontology loader.

    Args:
        genre: Genre layer name.
        series: Series layer name.
        reload: Force reload from YAML files.

    Returns:
        OntologyLoader instance.
    """
    global _loaded_ontology  # noqa: PLW0603
    if _loaded_ontology is None or reload:
        _loaded_ontology = OntologyLoader.from_layers(genre=genre, series=series)
    return _loaded_ontology
