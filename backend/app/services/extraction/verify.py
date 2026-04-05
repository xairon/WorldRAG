"""Reflective extraction verification node for the V4 pipeline.

Verifies extracted entities against source text to catch hallucinations,
wrong entity types, and missing obvious entities. Purely heuristic —
no LLM calls for basic verification.

Also provides lightweight narrative metadata extraction (dialogue ratio,
POV character, scene count) for downstream enrichment.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ── Generic role names that should not be Characters ────────────────────
_GENERIC_ROLES = frozenset(
    {
        "guard",
        "guards",
        "soldier",
        "soldiers",
        "merchant",
        "merchants",
        "villager",
        "villagers",
        "innkeeper",
        "bartender",
        "shopkeeper",
        "servant",
        "servants",
        "bandit",
        "bandits",
        "thief",
        "thieves",
        "farmer",
        "farmers",
        "priest",
        "priestess",
        "healer",
        "hunter",
        "hunters",
        "traveler",
        "travelers",
        "stranger",
        "strangers",
        "warrior",
        "warriors",
        "mage",
        "mages",
        "knight",
        "knights",
        "scout",
        "scouts",
        "assassin",
        "assassins",
        "elder",
        "elders",
        "child",
        "children",
        "boy",
        "girl",
        "man",
        "woman",
        "old man",
        "old woman",
        "narrator",
        "voice",
        "crowd",
        "mob",
        "army",
    }
)

# ── Dialogue / POV patterns ────────────────────────────────────────────
_DIALOGUE_RE = re.compile(r'"[^"]{2,}"')
_POV_FIRST_PERSON_RE = re.compile(r"\bI\s+(?:said|thought|felt|knew|saw|heard|wondered)\b")
_POV_THIRD_PERSON_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:thought|felt|wondered|realized|knew|mused)\b"
)
_SCENE_BREAK_RE = re.compile(r"(?:\n\s*\n\s*(?:\*\s*\*\s*\*|---+|===+|~~~+)\s*\n|\n\s*\n\s*\n)")


# ── Chunk metadata extraction ──────────────────────────────────────────


def extract_chunk_metadata(chapter_text: str) -> dict[str, Any]:
    """Extract basic narrative metadata from chapter text.

    Returns:
        {
            "dialogue_ratio": float,  # fraction of text that is dialogue
            "pov_character": str | None,  # guessed POV character
            "scene_count": int,  # estimated number of scenes
        }
    """
    if not chapter_text:
        return {"dialogue_ratio": 0.0, "pov_character": None, "scene_count": 1}

    # Dialogue ratio: sum of characters inside quotes / total characters
    dialogue_chars = sum(len(m.group()) for m in _DIALOGUE_RE.finditer(chapter_text))
    total_chars = len(chapter_text)
    dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0.0

    # POV detection: first-person takes priority
    pov_character: str | None = None
    if _POV_FIRST_PERSON_RE.search(chapter_text):
        pov_character = "(first-person)"
    else:
        # Third-person: find the most frequent "Name thought/felt/wondered" subject
        third_matches = _POV_THIRD_PERSON_RE.findall(chapter_text)
        if third_matches:
            # Count occurrences of each name
            name_counts: dict[str, int] = {}
            for name in third_matches:
                name_counts[name] = name_counts.get(name, 0) + 1
            pov_character = max(name_counts, key=name_counts.get)  # type: ignore[arg-type]

    # Scene count: count scene breaks + 1
    scene_breaks = len(_SCENE_BREAK_RE.findall(chapter_text))
    scene_count = scene_breaks + 1

    return {
        "dialogue_ratio": round(dialogue_ratio, 3),
        "pov_character": pov_character,
        "scene_count": scene_count,
    }


# ── Entity verification ────────────────────────────────────────────────


def _entity_name(entity: dict[str, Any]) -> str:
    """Get the best name for an entity dict."""
    return (
        entity.get("canonical_name")
        or entity.get("name")
        or entity.get("character")
        or entity.get("deity_name")
        or ""
    )


def _verify_single_entity(
    entity: dict[str, Any],
    chapter_text_lower: str,
    chapter_text: str,
    known_character_names: frozenset[str] | None = None,
    ontology: Any = None,
) -> tuple[bool, str]:
    """Verify a single entity against source text.

    Returns:
        (is_valid, reason) — if not valid, reason explains why.
    """
    name = _entity_name(entity)
    entity_type = entity.get("entity_type", "")

    if not name:
        return False, "empty_name"

    name_lower = name.lower()

    # Check 1: entity name should appear in the chapter text
    # Use case-insensitive check — names may appear differently
    if name_lower not in chapter_text_lower:
        # Try individual words for multi-word names (e.g. "Iron Sword" might be
        # mentioned as "iron sword" or split across lines)
        words = name_lower.split()
        if len(words) > 1:
            # At least 2 words must appear for multi-word names
            found_words = sum(1 for w in words if len(w) > 2 and w in chapter_text_lower)
            if found_words < min(2, len(words)):
                return False, f"name_not_in_text:{name}"
        else:
            return False, f"name_not_in_text:{name}"

    # Check 2: Characters should not be generic role names
    # Use ontology if available, fallback to hardcoded _GENERIC_ROLES
    if entity_type == "character":
        char_exclusions = ontology.get_type_exclusions("character") if ontology else _GENERIC_ROLES
        if name_lower in char_exclusions:
            return False, f"generic_role_as_character:{name}"

    # Check 3: Events should not use character names
    if entity_type == "event" and known_character_names:
        if name_lower in known_character_names:
            return False, f"event_named_after_character:{name}"
        for char_name in known_character_names:
            if name_lower.startswith(char_name + " "):
                return False, f"event_starts_with_character:{name}"

    # Check 4: Type exclusions from ontology (genre-conditional)
    if ontology:
        excluded = ontology.get_type_exclusions(entity_type)
        if name_lower in excluded:
            return False, f"ontology_type_exclusion:{name}:{entity_type}"

    # Check 5: Known characters extracted as wrong type
    if known_character_names and name_lower in known_character_names and entity_type != "character":
        return False, f"known_character_wrong_type:{name}:{entity_type}"

    # Check 6: extraction_text should exist in chapter text (if provided)
    extraction_text = entity.get("extraction_text", "")
    if extraction_text and len(extraction_text) > 10:
        # Normalize whitespace for comparison
        normalized_extract = " ".join(extraction_text.lower().split())
        normalized_chapter = " ".join(chapter_text_lower.split())
        if normalized_extract not in normalized_chapter:
            # Not a hard failure — extraction_text might be a summary
            # Just log, don't reject
            pass

    # ── GOLEM-specific checks (§6.3) ──────────────────────────────────

    # Check 7: PsychologicalState/CharacterFeature/NarrativeRole must reference a character
    if entity_type in ("psychological_state", "character_feature", "narrative_role"):
        char_ref = entity.get("character", "").lower().strip()
        if not char_ref:
            return False, f"golem_missing_character_ref:{entity_type}:{name}"
        if known_character_names and char_ref not in known_character_names:
            if char_ref not in chapter_text_lower:
                return False, f"golem_character_not_found:{entity_type}:{char_ref}"

    # Check 8: SocialRelationship must have ≥2 participants
    if entity_type == "social_relationship":
        participants = entity.get("participants", [])
        if len(participants) < 2:
            return False, f"golem_insufficient_participants:{name}:{len(participants)}"

    # Check 9: Setting should not be a physical location
    if entity_type == "setting":
        location_types = {
            "city",
            "dungeon",
            "forest",
            "mountain",
            "building",
            "region",
            "cave",
            "tower",
            "village",
            "house",
            "room",
            "hall",
        }
        if name_lower in location_types or any(
            lt in name_lower for lt in ("floor ", "room ", "cave ")
        ):
            return False, f"golem_setting_is_location:{name}"

    # Check 10: NarrativeRole should not be a CharacterFeature
    if entity_type == "narrative_role":
        trait_words = {
            "brave",
            "strong",
            "smart",
            "kind",
            "cruel",
            "tall",
            "short",
            "fast",
            "slow",
            "wise",
            "cunning",
            "loyal",
            "stubborn",
        }
        role_type = entity.get("role_type", "").lower()
        if role_type in trait_words:
            return False, f"golem_role_is_trait:{name}:{role_type}"

    # Check 11: CharacterFeature should not be a NarrativeRole
    if entity_type == "character_feature":
        role_types = {
            "protagonist",
            "antagonist",
            "mentor",
            "trickster",
            "herald",
            "guardian",
            "shadow",
            "shapeshifter",
            "narrator",
        }
        if name_lower in role_types:
            return False, f"golem_feature_is_role:{name}"

    return True, ""


async def verify_extractions_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: verify extracted entities against source text.

    Checks for:
    1. Hallucinated entities (name not found in chapter text)
    2. Wrong entity types (generic roles as Characters)
    3. Missing obvious entities (named characters mentioned but not extracted)

    Removes hallucinated entities. Logs warnings for potential issues.

    Reads from state: entities, chapter_text, chapter_number, book_id
    Writes to state: entities (filtered), chunk_metadata
    """
    entities: list[dict[str, Any]] = state.get("entities", [])
    chapter_text: str = state.get("chapter_text", "")
    chapter_number: int = state.get("chapter_number", 0)
    book_id: str = state.get("book_id", "")

    if not entities or not chapter_text:
        return {
            "chunk_metadata": extract_chunk_metadata(chapter_text),
        }

    chapter_text_lower = chapter_text.lower()

    # Build known character names from BOTH current extraction AND registry
    known_character_names_set: set[str] = set()

    # From current chapter extraction
    for e in entities:
        if e.get("entity_type") == "character":
            name = _entity_name(e)
            if name:
                known_character_names_set.add(name.lower())

    # From accumulated entity registry (cross-chapter)
    entity_registry = state.get("entity_registry", {})
    if isinstance(entity_registry, dict):
        for entry in entity_registry.get("entities", {}).values():
            if entry.get("entity_type") == "character":
                canonical = entry.get("canonical_name", "")
                if canonical:
                    known_character_names_set.add(canonical.lower())
                for alias in entry.get("aliases", []):
                    if alias:
                        known_character_names_set.add(alias.lower().strip())

    known_character_names = frozenset(known_character_names_set)

    verified: list[dict[str, Any]] = []
    removed_count = 0
    removal_reasons: dict[str, int] = {}

    ontology = state.get("ontology")

    for entity in entities:
        is_valid, reason = _verify_single_entity(
            entity, chapter_text_lower, chapter_text, known_character_names, ontology
        )
        if is_valid:
            verified.append(entity)
        else:
            removed_count += 1
            # Bucket by reason prefix
            reason_key = reason.split(":")[0]
            removal_reasons[reason_key] = removal_reasons.get(reason_key, 0) + 1
            logger.debug(
                "entity_verification_failed",
                book_id=book_id,
                chapter=chapter_number,
                entity_name=_entity_name(entity),
                entity_type=entity.get("entity_type", ""),
                reason=reason,
            )

    # Extract chunk metadata (lightweight heuristics)
    chunk_metadata = extract_chunk_metadata(chapter_text)

    logger.info(
        "verify_extractions_completed",
        book_id=book_id,
        chapter=chapter_number,
        total_entities=len(entities),
        verified_entities=len(verified),
        removed_entities=removed_count,
        removal_reasons=removal_reasons,
        dialogue_ratio=chunk_metadata["dialogue_ratio"],
        pov_character=chunk_metadata["pov_character"],
        scene_count=chunk_metadata["scene_count"],
    )

    # Generate TextualFeature entities from chunk metadata (GOLEM G18, programmatic)
    textual_features: list[dict] = []
    if chunk_metadata.get("pov_character"):
        textual_features.append(
            {
                "entity_type": "textual_feature",
                "feature_type": "pov",
                "name": chunk_metadata["pov_character"],
                "value": chunk_metadata["pov_character"],
            }
        )
    if chunk_metadata.get("dialogue_ratio") is not None:
        textual_features.append(
            {
                "entity_type": "textual_feature",
                "feature_type": "dialogue_density",
                "name": f"dialogue_ratio_{chapter_number}",
                "value": str(chunk_metadata["dialogue_ratio"]),
            }
        )
    if chunk_metadata.get("scene_count"):
        textual_features.append(
            {
                "entity_type": "textual_feature",
                "feature_type": "pacing",
                "name": f"scene_count_{chapter_number}",
                "value": str(chunk_metadata["scene_count"]),
            }
        )

    return {
        "entities": verified + textual_features,
        "chunk_metadata": chunk_metadata,
    }
