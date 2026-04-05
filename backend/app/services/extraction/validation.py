"""Post-extraction validation for entity and relation quality.

Validates relation source/target types against ontology constraints,
detects orphan entities, and flags consistency issues.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def validate_relations(
    relations: list[dict],
    entity_map: dict[str, dict],
    ontology: Any = None,
) -> list[dict]:
    """Validate relations against type constraints from ontology.

    Removes relations where source/target types don't match expected constraints.
    When no ontology is provided, all relations pass through.

    Args:
        relations: List of relation dicts with source, target, relation_type.
        entity_map: Map of entity name (lowercase) → entity dict with entity_type.
        ontology: OntologyLoader instance for domain/range constraints. If None,
                  all relations pass through (backward-compatible behaviour).

    Returns:
        Filtered list of valid relations.
    """
    valid = []
    removed = 0

    for rel in relations:
        rel_type = rel.get("relation_type", "")

        constraints = None
        if ontology:
            dr = ontology.get_domain_range(rel_type)
            if dr:
                constraints = dr  # (from_set, to_set)

        if constraints is None:
            # No constraint defined — allow through
            valid.append(rel)
            continue

        expected_src_types, expected_tgt_types = constraints
        src_name = (rel.get("source") or "").lower().strip()
        tgt_name = (rel.get("target") or "").lower().strip()
        src_entity = entity_map.get(src_name)
        tgt_entity = entity_map.get(tgt_name)

        src_type = (src_entity.get("entity_type", "") if src_entity else "").lower()
        tgt_type = (tgt_entity.get("entity_type", "") if tgt_entity else "").lower()

        src_ok = not src_entity or src_type in expected_src_types
        tgt_ok = not tgt_entity or tgt_type in expected_tgt_types

        if src_ok and tgt_ok:
            valid.append(rel)
        else:
            removed += 1
            logger.debug(
                "relation_type_violation",
                relation_type=rel_type,
                source=src_name,
                source_type=src_type,
                target=tgt_name,
                target_type=tgt_type,
                expected_src=list(expected_src_types),
                expected_tgt=list(expected_tgt_types),
            )

    if removed:
        logger.info(
            "relation_validation_completed",
            total=len(relations),
            valid=len(valid),
            removed=removed,
        )

    return valid
