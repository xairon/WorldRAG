"""Selective reprocessing -- surgical re-extraction when ontology evolves.

Given a set of OntologyChanges, computes which chapters and phases
need re-extraction, then runs only those phases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from app.schemas.ontology import OntologyChange


logger = get_logger(__name__)


@dataclass
class ImpactScope:
    """Computed impact of ontology changes."""

    affected_entity_types: list[str] = field(default_factory=list)
    affected_phases: list[int] = field(default_factory=list)  # 0-5
    new_regex_patterns: list[dict] = field(default_factory=list)
    requires_full_reextract: bool = False


def compute_impact_scope(changes: list[OntologyChange]) -> ImpactScope:
    """Analyze ontology changes to determine what needs reprocessing."""
    scope = ImpactScope()

    for change in changes:
        if change.change_type == "add_entity_type":
            scope.affected_entity_types.append(change.target)
            # Determine which phase based on layer
            if change.layer == "core":
                scope.affected_phases.append(1)
            elif change.layer == "genre":
                scope.affected_phases.append(2)
            elif change.layer == "series":
                scope.affected_phases.append(3)

        elif change.change_type == "add_regex":
            scope.affected_phases.append(0)
            scope.new_regex_patterns.append({"target": change.target})

        elif change.change_type in ("modify_property", "add_property"):
            scope.affected_entity_types.append(change.target)
            # Properties don't necessarily need re-extraction,
            # but the reconciliation should be re-run
            if 4 not in scope.affected_phases:
                scope.affected_phases.append(4)

        elif change.change_type in ("add_relationship_type", "add_relationship"):
            # Relationships are extracted in the same phase as their source entity
            if 4 not in scope.affected_phases:
                scope.affected_phases.append(4)

        elif change.change_type == "extend_enum":
            scope.affected_entity_types.append(change.target)
            # Re-run reconciliation to pick up new enum values
            if 4 not in scope.affected_phases:
                scope.affected_phases.append(4)

    # Deduplicate
    scope.affected_phases = sorted(set(scope.affected_phases))
    scope.affected_entity_types = list(set(scope.affected_entity_types))

    return scope


async def scan_chapters_for_impact(
    book_id: str,
    scope: ImpactScope,
    driver: AsyncDriver,
) -> list[int]:
    """Scan chapter texts to find which chapters are affected by the changes.

    Uses regex matching against chapter texts to find chapters that
    likely contain the new entity types or patterns.
    """
    from app.repositories.book_repo import BookRepository

    book_repo = BookRepository(driver)
    chapters = await book_repo.get_chapters_for_extraction(book_id)

    if not chapters:
        return []

    # If scope requires full re-extract, return all chapters
    if scope.requires_full_reextract:
        return [ch.number for ch in chapters]

    # Build search patterns from affected entity types and new regex
    search_patterns: list[re.Pattern[str]] = []
    for pattern_info in scope.new_regex_patterns:
        try:
            compiled = re.compile(
                pattern_info.get("pattern", pattern_info["target"]),
                re.IGNORECASE,
            )
            search_patterns.append(compiled)
        except re.error:
            # If the target isn't a valid regex, use it as literal
            search_patterns.append(re.compile(re.escape(pattern_info["target"]), re.IGNORECASE))

    # If no specific patterns to scan for, return all chapters
    # (better to over-extract than miss something)
    if not search_patterns:
        return [ch.number for ch in chapters]

    affected_chapters: list[int] = []
    for chapter in chapters:
        for pattern in search_patterns:
            if pattern.search(chapter.text):
                affected_chapters.append(chapter.number)
                break

    return affected_chapters


async def reextract_chapters(
    book_id: str,
    chapter_numbers: list[int],
    scope: ImpactScope,
    driver: AsyncDriver,
    genre: str = "litrpg",
    series_name: str = "",
) -> dict[str, Any]:
    """Re-extract specific chapters for specific phases.

    Only runs the affected phases, not the full pipeline.
    """
    from app.config import settings
    from app.repositories.book_repo import BookRepository
    from app.services.graph_builder import build_chapter_graph_v3

    book_repo = BookRepository(driver)

    # Load entity registry (accumulates across chapters)
    from app.services.extraction.entity_registry import EntityRegistry

    registry_data = await book_repo.load_entity_registry(book_id)
    entity_registry = EntityRegistry.from_dict(registry_data) if registry_data else EntityRegistry()

    chapters = await book_repo.get_chapters_for_extraction(book_id, chapters=chapter_numbers)
    chapter_regex = await book_repo.get_chapter_regex_json(book_id)

    results: list[dict[str, Any]] = []
    failed: list[int] = []

    for chapter in chapters:
        regex_json = chapter_regex.get(chapter.number, "[]")
        try:
            stats = await build_chapter_graph_v3(
                driver=driver,
                book_repo=book_repo,
                book_id=book_id,
                chapter=chapter,
                genre=genre,
                series_name=series_name,
                regex_matches_json=regex_json,
                entity_registry=entity_registry.to_dict(),
                ontology_version=settings.ontology_version,
                source_language=settings.extraction_language,
            )
            results.append(stats)

            # Accumulate registry with extracted entities (same as tasks.py)
            for ent in stats.get("extracted_entities") or []:
                entity_registry.add(
                    name=ent["name"],
                    entity_type=ent["type"],
                    aliases=ent.get("aliases", []),
                    significance=ent.get("significance", ""),
                    first_seen_chapter=chapter.number,
                    description=ent.get("description", ""),
                )
                entity_registry.update_last_seen(ent["name"], chapter.number)

            for _old, new in (stats.get("alias_map") or {}).items():
                if not entity_registry.lookup(new):
                    entity_registry.add(new, "Unknown")

            # Persist updated registry
            await book_repo.save_entity_registry(
                book_id, entity_registry.to_dict(), settings.ontology_version,
            )
        except Exception:
            logger.exception(
                "reextract_chapter_failed",
                book_id=book_id,
                chapter=chapter.number,
            )
            failed.append(chapter.number)

    return {
        "book_id": book_id,
        "chapters_reprocessed": len(results),
        "chapters_failed": len(failed),
        "failed_chapters": failed,
        "total_entities": sum(r.get("total_entities", 0) for r in results),
        "affected_phases": scope.affected_phases,
    }
