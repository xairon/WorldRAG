"""3-tier entity deduplication: exact -> fuzzy -> LLM.

Progressively more expensive dedup layers:
  Tier 1: Exact string match (free, instant)
  Tier 2: Fuzzy match via thefuzz (free, fast)
  Tier 3: LLM-based semantic dedup via Instructor (costly, accurate)

Only escalates to the next tier when the previous one is inconclusive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from thefuzz import fuzz

from app.core.logging import get_logger

if TYPE_CHECKING:
    import instructor

    from app.schemas.extraction import EntityMergeCandidate

logger = get_logger(__name__)

# ── Tier 1: Exact match ────────────────────────────────────────────────


def normalize_name(name: str) -> str:
    """Normalize a name for exact comparison.

    Lowercases, strips whitespace, removes common articles/prefixes.
    """
    name = name.strip().lower()
    # Remove common prefixes
    for prefix in ("the ", "a ", "an "):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return name


def exact_dedup(
    entities: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Tier 1: Remove exact duplicate names.

    Args:
        entities: List of dicts with at least a 'name' key.

    Returns:
        Tuple of (deduplicated entities, alias_map {alias -> canonical}).
    """
    seen: dict[str, dict[str, str]] = {}
    alias_map: dict[str, str] = {}

    for entity in entities:
        name = entity.get("name", "")
        normalized = normalize_name(name)

        if normalized in seen:
            # Map the duplicate to the canonical
            canonical = seen[normalized]["name"]
            alias_map[name] = canonical
        else:
            seen[normalized] = entity

    deduped = list(seen.values())
    if alias_map:
        logger.info(
            "dedup_exact",
            original=len(entities),
            deduplicated=len(deduped),
            aliases=len(alias_map),
        )

    return deduped, alias_map


# ── Tier 2: Fuzzy match ────────────────────────────────────────────────

FUZZY_THRESHOLD = 85  # fuzz ratio threshold for "likely same entity"
FUZZY_DEFINITE = 95  # auto-merge without LLM confirmation


def fuzzy_dedup(
    entities: list[dict[str, str]],
    threshold: int = FUZZY_THRESHOLD,
) -> tuple[list[dict[str, str]], list[tuple[str, str, int]]]:
    """Tier 2: Find fuzzy duplicate pairs using thefuzz.

    Args:
        entities: List of dicts with 'name' key.
        threshold: Minimum fuzz ratio to flag as potential duplicate.

    Returns:
        Tuple of:
          - Entities with definite matches merged.
          - Candidate pairs for LLM review: (name_a, name_b, score).
    """
    names = [e.get("name", "") for e in entities]
    merged_indices: set[int] = set()
    candidates: list[tuple[str, str, int]] = []
    alias_map: dict[str, str] = {}

    for i in range(len(names)):
        if i in merged_indices:
            continue
        for j in range(i + 1, len(names)):
            if j in merged_indices:
                continue

            score = fuzz.ratio(
                normalize_name(names[i]),
                normalize_name(names[j]),
            )

            if score >= FUZZY_DEFINITE:
                # Auto-merge: pick the longer name as canonical
                canonical = names[i] if len(names[i]) >= len(names[j]) else names[j]
                alias = names[j] if canonical == names[i] else names[i]
                alias_map[alias] = canonical
                merged_indices.add(j if canonical == names[i] else i)
            elif score >= threshold:
                # Candidate for LLM review
                candidates.append((names[i], names[j], score))

    deduped = [e for idx, e in enumerate(entities) if idx not in merged_indices]

    if merged_indices or candidates:
        logger.info(
            "dedup_fuzzy",
            original=len(entities),
            auto_merged=len(merged_indices),
            candidates_for_llm=len(candidates),
        )

    return deduped, candidates


# ── Tier 3: LLM dedup ──────────────────────────────────────────────────


async def llm_dedup(
    candidates: list[tuple[str, str, int]],
    entity_type: str,
    client: instructor.AsyncInstructor,
    model: str,
) -> list[EntityMergeCandidate]:
    """Tier 3: Use LLM to resolve ambiguous fuzzy matches.

    Only called for pairs that scored between FUZZY_THRESHOLD and
    FUZZY_DEFINITE — the "uncertain zone".

    Args:
        candidates: List of (name_a, name_b, fuzzy_score) tuples.
        entity_type: Type of entity being compared (for context).
        client: Instructor async client.
        model: Model name.

    Returns:
        List of EntityMergeCandidate with LLM decisions.
    """
    from app.schemas.extraction import EntityMergeCandidate

    if not candidates:
        return []

    results: list[EntityMergeCandidate] = []

    # Batch candidates into a single LLM call for efficiency
    candidates_text = "\n".join(f"- '{a}' vs '{b}' (fuzzy score: {s}%)" for a, b, s in candidates)

    try:
        merge_results = await client.chat.completions.create(
            model=model,
            response_model=list[EntityMergeCandidate],
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are an entity resolution expert for {entity_type} entities "
                        "in fiction novels. For each pair, decide if they refer to the same "
                        "entity. Consider nicknames, shortened forms, titles, and context."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Are these {entity_type} entity pairs the same entity? "
                        "For each, provide confidence (0.0=different, 1.0=same) "
                        f"and the canonical name to use:\n\n{candidates_text}"
                    ),
                },
            ],
        )

        for merge in merge_results:
            merge.entity_type = entity_type
            results.append(merge)

    except Exception:
        logger.warning(
            "dedup_llm_failed",
            entity_type=entity_type,
            candidates=len(candidates),
            exc_info=True,
        )
        # Fall back to fuzzy scores
        for name_a, name_b, score in candidates:
            results.append(
                EntityMergeCandidate(
                    entity_a_name=name_a,
                    entity_b_name=name_b,
                    entity_type=entity_type,
                    confidence=score / 100.0,
                    canonical_name=name_a if len(name_a) >= len(name_b) else name_b,
                    reason=f"Fuzzy match fallback (score={score}%)",
                )
            )

    logger.info(
        "dedup_llm_completed",
        entity_type=entity_type,
        candidates=len(candidates),
        merges=sum(1 for r in results if r.confidence >= 0.8),
    )

    return results


# ── Full pipeline ───────────────────────────────────────────────────────


async def deduplicate_entities(
    entities: list[dict[str, str]],
    entity_type: str,
    client: instructor.AsyncInstructor | None = None,
    model: str = "gpt-4o-mini",
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Run the full 3-tier dedup pipeline.

    Args:
        entities: List of entity dicts with 'name' key.
        entity_type: Entity type label for context.
        client: Optional Instructor client for Tier 3 LLM dedup.
        model: Model for Tier 3. Defaults to gpt-4o-mini.

    Returns:
        Tuple of (deduplicated entities, alias_map).
    """
    if len(entities) <= 1:
        return entities, {}

    # Tier 1: exact
    entities, alias_map = exact_dedup(entities)

    if len(entities) <= 1:
        return entities, alias_map

    # Tier 2: fuzzy
    entities, candidates = fuzzy_dedup(entities)

    # Tier 3: LLM (only if client provided and candidates exist)
    if candidates and client is not None:
        merges = await llm_dedup(candidates, entity_type, client, model)

        # Apply high-confidence merges
        for merge in merges:
            if merge.confidence >= 0.8:
                alias_map[merge.entity_a_name] = merge.canonical_name
                alias_map[merge.entity_b_name] = merge.canonical_name
                # Remove the non-canonical entity
                entities = [
                    e
                    for e in entities
                    if normalize_name(e.get("name", ""))
                    != normalize_name(
                        merge.entity_a_name
                        if merge.canonical_name != merge.entity_a_name
                        else merge.entity_b_name
                    )
                ]
    elif candidates:
        # No LLM client — just log the unresolved candidates
        logger.info(
            "dedup_unresolved_candidates",
            entity_type=entity_type,
            count=len(candidates),
        )

    logger.info(
        "dedup_pipeline_completed",
        entity_type=entity_type,
        final_count=len(entities),
        total_aliases=len(alias_map),
    )

    return entities, alias_map
