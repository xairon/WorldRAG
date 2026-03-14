"""Convert a SagaProfile into entity_types and edge_types dicts for Graphiti's add_episode() API."""

from pydantic import BaseModel, Field, create_model

from app.services.saga_profile.models import SagaProfile


# ---------------------------------------------------------------------------
# Universal entity types — always present regardless of saga
# ---------------------------------------------------------------------------

class Character(BaseModel):
    aliases: list[str] = Field(default_factory=list)
    role: str | None = None
    status: str | None = None


class Location(BaseModel):
    location_type: str | None = None
    parent_location: str | None = None


class Object(BaseModel):
    object_type: str | None = None


class Organization(BaseModel):
    org_type: str | None = None


class Event(BaseModel):
    event_type: str | None = None
    significance: str | None = None


class Concept(BaseModel):
    concept_type: str | None = None


_UNIVERSAL_TYPES: dict[str, type[BaseModel]] = {
    "Character": Character,
    "Location": Location,
    "Object": Object,
    "Organization": Organization,
    "Event": Event,
    "Concept": Concept,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def saga_profile_to_graphiti_types(profile: SagaProfile) -> dict[str, type[BaseModel]]:
    """Return universal entity types merged with dynamically generated induced types.

    Universal types are always present. Induced types from the profile are
    generated via ``create_model`` with all typical_attributes as optional
    ``str | None`` fields.  An induced type whose name matches a universal type
    will override the universal entry (the caller decides on naming discipline).
    """
    types: dict[str, type[BaseModel]] = dict(_UNIVERSAL_TYPES)

    for induced in profile.entity_types:
        field_definitions: dict[str, tuple[type, Field]] = {  # type: ignore[type-arg]
            attr: (
                str | None,
                Field(None, description=f"{attr} of {induced.type_name}"),
            )
            for attr in induced.typical_attributes
        }
        model = create_model(induced.type_name, **field_definitions)
        types[induced.type_name] = model

    return types


def saga_profile_to_graphiti_edges(
    profile: SagaProfile,
) -> tuple[dict[str, type[BaseModel]], dict[tuple[str, str], list[str]]]:
    """Return ``(edge_types, edge_type_map)`` for Graphiti.

    - ``edge_types``: mapping of relation_name → Pydantic model with a
      ``temporal`` bool field whose default mirrors the relation definition.
    - ``edge_type_map``: mapping of ``(source_type, target_type)`` → list of
      relation names applicable to that pair.
    """
    edge_types: dict[str, type[BaseModel]] = {}
    edge_type_map: dict[tuple[str, str], list[str]] = {}

    for rel in profile.relation_types:
        edge_model = create_model(
            rel.relation_name,
            temporal=(bool, Field(default=rel.temporal)),
        )
        edge_types[rel.relation_name] = edge_model

        key = (rel.source_type, rel.target_type)
        edge_type_map.setdefault(key, []).append(rel.relation_name)

    return edge_types, edge_type_map
