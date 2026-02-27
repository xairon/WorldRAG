"""Ontology evolution schemas for tracking changes across books."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OntologyChange(BaseModel):
    """A proposed or applied change to the ontology."""

    change_type: Literal[
        "add_entity_type",
        "add_relationship",
        "add_relationship_type",
        "add_regex",
        "extend_enum",
        "add_property",
        "modify_property",
    ]
    layer: Literal["core", "genre", "series"]
    target: str  # Entity type or relationship name
    proposed_by: Literal["auto_discovery", "user", "migration", "system", "admin"]
    discovered_in_book: int = 0
    discovered_in_chapter: int = 0
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)  # Source text excerpts
    status: Literal["proposed", "validated", "rejected", "applied"] = "proposed"
    details: dict = Field(default_factory=dict)  # Additional info (properties, pattern, etc.)


class OntologyChangelog(BaseModel):
    """Collection of ontology changes for a series."""

    series_name: str
    changes: list[OntologyChange] = Field(default_factory=list)
    current_version: str = "3.0.0"

    def add_change(self, change: OntologyChange) -> None:
        self.changes.append(change)

    def get_pending(self) -> list[OntologyChange]:
        return [c for c in self.changes if c.status == "proposed"]

    def get_applied(self) -> list[OntologyChange]:
        return [c for c in self.changes if c.status == "applied"]


class RegexProposal(BaseModel):
    """A proposed new regex pattern discovered during extraction."""

    proposed_pattern: str
    entity_type: str
    captures: dict[str, int]
    example_matches: list[str]
    frequency: int
    confidence: float = Field(ge=0.0, le=1.0)
    discovered_in_book: int
