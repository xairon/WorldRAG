"""SagaProfileInducer — analyzes Graphiti Entity nodes after Discovery Mode,
clusters them, formalizes types via LLM, detects text patterns, and outputs a SagaProfile.

This is the core induction algorithm (5 steps):
1. Fetch entities from Neo4j
2. Cluster by label (baseline)
3. Formalize via LLM
4. Detect text patterns
5. Assemble SagaProfile
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from neo4j import AsyncDriver

from app.config import settings
from app.core.logging import get_logger
from app.services.saga_profile.models import (
    InducedEntityType,
    InducedPattern,
    InducedRelationType,
    SagaProfile,
)

logger = get_logger(__name__)

MIN_CLUSTER_SIZE = 3
MIN_CONFIDENCE = 0.6

# Known LitRPG / progression-fantasy structural patterns
_PATTERN_DEFS: list[dict[str, str]] = [
    {
        "regex": r"\[Skill Acquired:\s*([^\]]+)\]",
        "extraction_type": "skill_acquisition",
    },
    {
        "regex": r"\[Level\s+(\d+)\s*[→>]+\s*(\d+)\]",
        "extraction_type": "level_up",
    },
    {
        "regex": r"\[Quest Complete:\s*([^\]]+)\]",
        "extraction_type": "quest_completion",
    },
    {
        "regex": r"\[New Title:\s*([^\]]+)\]",
        "extraction_type": "title_acquisition",
    },
    {
        "regex": r"\[Class Evolved:\s*([^\]]+)\]",
        "extraction_type": "class_evolution",
    },
    {
        "regex": r"\[Achievement Unlocked:\s*([^\]]+)\]",
        "extraction_type": "achievement",
    },
    {
        "regex": r"\[Stat Increase:\s*([^\]]+)\]",
        "extraction_type": "stat_increase",
    },
]

# Narrative system keywords mapped from entity type names
_NARRATIVE_SYSTEM_KEYWORDS: dict[str, list[str]] = {
    "magic_system": ["spell", "magic", "mana", "enchant", "rune", "arcane"],
    "progression": ["level", "skill", "class", "stat", "xp", "rank", "evolution"],
    "political": ["kingdom", "faction", "house", "court", "alliance", "guild"],
}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from *text* using bracket counting.

    Handles nested braces correctly, unlike a simple greedy regex.
    Returns the parsed dict or None if no valid JSON object is found.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _cluster_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group entities by their non-Entity label. Return clusters with >= MIN_CLUSTER_SIZE members."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entity in entities:
        labels = entity.get("labels", [])
        non_entity_labels = [lbl for lbl in labels if lbl != "Entity"]
        label = non_entity_labels[0] if non_entity_labels else "Unknown"
        groups[label].append(entity)

    return [
        {"label": label, "members": members}
        for label, members in groups.items()
        if len(members) >= MIN_CLUSTER_SIZE
    ]


async def _formalize_clusters_llm(
    clusters: list[dict[str, Any]],
    entities_by_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Call LLM to formalize each cluster into type proposals.

    For each cluster with >= MIN_CLUSTER_SIZE instances, asks the LLM to propose
    a type_name, description, typical_attributes, and confidence score.
    Falls back to a heuristic if LLM fails.
    """
    from app.llm.providers import get_langchain_llm

    llm = get_langchain_llm(settings.llm_generation)
    results: list[dict[str, Any]] = []

    for cluster in clusters:
        label = cluster["label"]
        members = cluster["members"]
        instance_names = [m["name"] for m in members]
        # Enrich with full entity summaries from entities_by_name when available
        summaries = []
        for m in members:
            name = m["name"]
            entity = entities_by_name.get(name, m)
            summary = entity.get("summary") or "N/A"
            summaries.append(f"- {name}: {summary}")

        prompt = (
            f"Voici {len(members)} entités extraites d'un roman, regroupées sous le label '{label}':\n"
            + "\n".join(summaries)
            + "\n\nPropose un type formel pour ce groupe. Réponds en JSON strict:\n"
            '{"type_name": "PascalCase", "description": "...", '
            '"typical_attributes": ["attr1", "attr2"], "confidence": 0.0-1.0}\n'
            "Réponds UNIQUEMENT avec le JSON, sans texte autour."
        )

        try:
            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            # Try direct JSON parse first, fall back to bracket-counting extraction
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = _extract_json_object(content)
                if parsed is None:
                    raise ValueError("No JSON object found in LLM response")

            results.append(
                {
                    "type_name": parsed.get("type_name", label),
                    "parent_universal": label,
                    "description": parsed.get("description", f"Entities of type {label}"),
                    "typical_attributes": parsed.get("typical_attributes", []),
                    "instances_found": instance_names,
                    "confidence": float(parsed.get("confidence", 0.7)),
                }
            )
        except Exception:
            logger.warning(
                "llm_formalize_fallback",
                label=label,
                member_count=len(members),
                exc_info=True,
            )
            # Fallback: use the label as type_name with moderate confidence
            results.append(
                {
                    "type_name": label,
                    "parent_universal": label,
                    "description": f"Entities of type {label}",
                    "typical_attributes": [],
                    "instances_found": instance_names,
                    "confidence": 0.5,
                }
            )

    return results


def _extract_json_array(text: str) -> list[Any] | None:
    """Extract the first JSON array from *text* using bracket counting.

    Handles nested brackets correctly.
    Returns the parsed list or None if no valid JSON array is found.
    """
    start = text.find("[")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# Universal entity types always available as relation endpoints
_UNIVERSAL_TYPES = [
    "Character",
    "Location",
    "Object",
    "Organization",
    "Event",
    "Concept",
]


async def _induce_relations_llm(
    entity_types: list[InducedEntityType],
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Call LLM to propose relation types between induced entity types.

    Builds a prompt listing all induced + universal entity types and asks the LLM
    to propose the most important relationships between them.

    Returns:
        List of dicts matching InducedRelationType fields, filtered to valid types only.
    """
    from app.llm.providers import get_langchain_llm

    llm = get_langchain_llm(settings.llm_generation)

    # Collect all valid type names (induced + universal)
    induced_names = [et.type_name for et in entity_types]
    all_type_names = list(dict.fromkeys(induced_names + _UNIVERSAL_TYPES))

    # Build a concise sample of entity instances for context
    instance_sample = []
    for et in entity_types:
        sample = et.instances_found[:3]
        instance_sample.append(f"- {et.type_name}: {', '.join(sample)}")

    prompt = (
        "You are analyzing a fiction novel's knowledge graph. "
        "Given the following entity types, propose the most important relationships between them.\n\n"
        "Entity types:\n"
        + "\n".join(f"  - {t}" for t in all_type_names)
        + "\n\nEntity instances (sample):\n"
        + ("\n".join(instance_sample) if instance_sample else "  (none)")
        + "\n\nExamples of good relations:\n"
        '  {"relation_name": "has_skill", "source_type": "Character", "target_type": "Skill", '
        '"cardinality": "N:N", "temporal": true, "description": "Character possesses a skill"}\n'
        '  {"relation_name": "belongs_to", "source_type": "Character", "target_type": "Organization", '
        '"cardinality": "N:N", "temporal": true, "description": "Character is a member of an org"}\n'
        '  {"relation_name": "located_in", "source_type": "Character", "target_type": "Location", '
        '"cardinality": "N:1", "temporal": true, "description": "Character resides in a location"}\n\n'
        "Rules:\n"
        "  - Only propose relations where both source_type AND target_type are in the list above.\n"
        "  - relation_name must be snake_case.\n"
        "  - cardinality must be one of: 1:1, 1:N, N:1, N:N.\n"
        "  - Only include confident, meaningful relations (omit speculative ones).\n"
        "  - Respond ONLY with a JSON array of relation objects, no text around it.\n\n"
        "JSON array:"
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Try direct JSON parse first, fall back to bracket-counting extraction
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError("Expected JSON array")
        except (json.JSONDecodeError, ValueError):
            parsed = _extract_json_array(content)
            if parsed is None:
                raise ValueError("No JSON array found in LLM response")

        # Filter: both source_type and target_type must exist in all_type_names
        valid_type_set = set(all_type_names)
        results: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            src = item.get("source_type", "")
            tgt = item.get("target_type", "")
            if src not in valid_type_set or tgt not in valid_type_set:
                logger.debug(
                    "relation_type_skipped_unknown_endpoint",
                    relation_name=item.get("relation_name"),
                    source_type=src,
                    target_type=tgt,
                )
                continue
            results.append(item)

        logger.info("relation_types_induced", count=len(results))
        return results

    except Exception:
        logger.warning("llm_induce_relations_failed", exc_info=True)
        return []


def _detect_patterns(raw_text: str) -> list[InducedPattern]:
    """Scan raw text for recurring structural patterns. Only keep patterns with >= 2 matches."""
    if not raw_text:
        return []

    results: list[InducedPattern] = []

    for pdef in _PATTERN_DEFS:
        matches = re.findall(pdef["regex"], raw_text)
        if len(matches) >= 2:
            # Get the first full match as example
            first_match = re.search(pdef["regex"], raw_text)
            example = first_match.group(0) if first_match else ""
            confidence = min(1.0, len(matches) / 5)
            results.append(
                InducedPattern(
                    pattern_regex=pdef["regex"],
                    extraction_type=pdef["extraction_type"],
                    example=example,
                    confidence=confidence,
                )
            )

    return results


def _detect_narrative_systems(type_names: list[str]) -> list[str]:
    """Detect narrative systems from induced type names."""
    systems: list[str] = []
    lower_names = [t.lower() for t in type_names]

    for system, keywords in _NARRATIVE_SYSTEM_KEYWORDS.items():
        if any(kw in name for name in lower_names for kw in keywords):
            systems.append(system)

    return systems


def _estimate_complexity(type_count: int) -> str:
    """Estimate ontology complexity based on the number of induced types."""
    if type_count <= 3:
        return "low"
    elif type_count <= 8:
        return "medium"
    else:
        return "high"


class SagaProfileInducer:
    """Analyzes Graphiti Entity nodes from Discovery Mode and induces a SagaProfile."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def induce(
        self,
        saga_id: str,
        saga_name: str,
        source_book: str,
        raw_text: str = "",
    ) -> SagaProfile:
        """Run full 5-step induction algorithm.

        Args:
            saga_id: Unique identifier for the saga / group_id in Neo4j.
            saga_name: Human-readable saga name.
            source_book: Source book identifier.
            raw_text: Raw text for pattern detection (optional).

        Returns:
            Fully assembled SagaProfile.
        """
        logger.info("saga_profile_induction_start", saga_id=saga_id, saga_name=saga_name)

        # Step 1 — Fetch entities from Neo4j
        entities = await self._fetch_entities(saga_id)
        logger.info("saga_profile_entities_fetched", count=len(entities))

        if not entities:
            logger.warning("saga_profile_no_entities", saga_id=saga_id)
            return SagaProfile(
                saga_id=saga_id,
                saga_name=saga_name,
                source_book=source_book,
                entity_types=[],
                relation_types=[],
                text_patterns=[],
            )

        # Step 2 — Cluster by label
        clusters = _cluster_entities(entities)
        logger.info("saga_profile_clusters", cluster_count=len(clusters))

        # Build lookup for formalization
        entities_by_name = {e["name"]: e for e in entities}

        # Step 3 — Formalize via LLM
        formalized = await _formalize_clusters_llm(clusters, entities_by_name)

        # Step 4 — Detect text patterns
        text_patterns = _detect_patterns(raw_text)
        logger.info("saga_profile_patterns", pattern_count=len(text_patterns))

        # Step 5 — Assemble
        entity_types = [
            InducedEntityType(**f) for f in formalized if f["confidence"] >= MIN_CONFIDENCE
        ]

        # Step 5b — Induce relation types via LLM
        raw_relations = await _induce_relations_llm(entity_types, entities)
        relation_types: list[InducedRelationType] = []
        for r in raw_relations:
            try:
                relation_types.append(InducedRelationType(**r))
            except Exception:
                logger.warning(
                    "relation_type_parse_error",
                    relation_data=r,
                    exc_info=True,
                )

        type_names = [et.type_name for et in entity_types]
        narrative_systems = _detect_narrative_systems(type_names)
        complexity = _estimate_complexity(len(entity_types))

        profile = SagaProfile(
            saga_id=saga_id,
            saga_name=saga_name,
            source_book=source_book,
            entity_types=entity_types,
            relation_types=relation_types,
            text_patterns=text_patterns,
            narrative_systems=narrative_systems,
            estimated_complexity=complexity,
        )

        logger.info(
            "saga_profile_induction_complete",
            saga_id=saga_id,
            entity_type_count=len(entity_types),
            relation_type_count=len(relation_types),
            pattern_count=len(text_patterns),
            complexity=complexity,
        )

        return profile

    async def _fetch_entities(self, saga_id: str) -> list[dict[str, Any]]:
        """Fetch Entity nodes from Neo4j for the given saga/group_id."""
        query = (
            "MATCH (n:Entity {group_id: $saga_id}) "
            "RETURN n.name AS name, n.summary AS summary, labels(n) AS labels"
        )
        async with self.driver.session() as session:
            result = await session.run(query, saga_id=saga_id)
            return result.data()
