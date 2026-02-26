"""Pass 5a — Programmatic mention detection.

Finds all exact name and alias mentions of known entities in chapter text.
This is FREE (no LLM calls) and provides word-level precise spans.

Produces GroundedEntity objects with mention_type="direct_name" or "alias".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.schemas.extraction import GroundedEntity

logger = get_logger(__name__)


@dataclass
class MentionMatch:
    """A single mention of an entity in text."""

    entity_name: str  # canonical name
    entity_type: str
    mention_text: str  # actual text matched
    mention_type: str  # "direct_name" or "alias"
    char_start: int
    char_end: int
    confidence: float = 1.0


def detect_mentions(
    chapter_text: str,
    entities: list[dict],
) -> list[GroundedEntity]:
    """Find all exact/alias mentions of known entities in chapter text.

    Args:
        chapter_text: Full chapter text.
        entities: List of entity dicts with keys:
            - canonical_name: str
            - entity_type: str (e.g., "character", "skill")
            - aliases: list[str] (optional)
            - name: str (the primary name used in text)

    Returns:
        List of GroundedEntity objects for each mention found.
    """
    if not chapter_text or not entities:
        return []

    # Build search terms: (pattern, canonical_name, entity_type, mention_type)
    search_terms: list[tuple[str, str, str, str]] = []

    for entity in entities:
        canonical = entity.get("canonical_name", entity.get("name", ""))
        entity_type = entity.get("entity_type", "character")
        name = entity.get("name", canonical)
        aliases = entity.get("aliases", [])

        if not canonical:
            continue

        # Add primary name
        if name and len(name) >= 2:
            search_terms.append((name, canonical, entity_type, "direct_name"))

        # Add canonical if different from name
        if canonical != name and len(canonical) >= 2:
            search_terms.append((canonical, canonical, entity_type, "direct_name"))

        # Add aliases
        for alias in aliases:
            alias = alias.strip()
            if alias and len(alias) >= 2:
                search_terms.append((alias, canonical, entity_type, "alias"))

    if not search_terms:
        return []

    # Sort by length descending — match longer terms first to avoid partial matches
    search_terms.sort(key=lambda x: len(x[0]), reverse=True)

    # Find all matches
    all_matches: list[MentionMatch] = []
    occupied: list[tuple[int, int]] = []  # track occupied spans to avoid overlaps

    for term, canonical, entity_type, mention_type in search_terms:
        # Use word boundary regex for exact matching
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)

        for match in pattern.finditer(chapter_text):
            start, end = match.start(), match.end()

            # Skip if this span overlaps with an already-matched longer term
            if _overlaps(start, end, occupied):
                continue

            occupied.append((start, end))
            all_matches.append(
                MentionMatch(
                    entity_name=canonical,
                    entity_type=entity_type,
                    mention_text=match.group(),
                    mention_type=mention_type,
                    char_start=start,
                    char_end=end,
                )
            )

    # Convert to GroundedEntity
    grounded = [
        GroundedEntity(
            entity_type=m.entity_type,
            entity_name=m.entity_name,
            extraction_text=m.mention_text,
            char_offset_start=m.char_start,
            char_offset_end=m.char_end,
            pass_name="mention_detect",
            alignment_status="exact",
            confidence=m.confidence,
            attributes={"mention_type": m.mention_type},
        )
        for m in all_matches
    ]

    logger.info(
        "mention_detection_complete",
        total_entities=len(entities),
        mentions_found=len(grounded),
    )

    return grounded


def _overlaps(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
    """Check if a span overlaps with any occupied span."""
    return any(start < occ_end and end > occ_start for occ_start, occ_end in occupied)
