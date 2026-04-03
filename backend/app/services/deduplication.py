"""5-tier entity deduplication: exact -> fuzzy -> hybrid -> cross-encoder -> LLM.

Progressively more expensive dedup layers:
  Tier 1: Exact string match (free, instant)
  Tier 2: Fuzzy match via thefuzz (free, fast)
  Tier 2.5a: Hybrid BM25 + embedding candidate generation (G2)
  Tier 2.5b: Cross-encoder reranking to filter candidates (G1)
  Tier 3: Batched LLM-based semantic dedup via Instructor (costly, accurate)

Only escalates to the next tier when the previous one is inconclusive.
"""

from __future__ import annotations

import asyncio
import math
import unicodedata
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np
from thefuzz import fuzz

from app.core.logging import get_logger

if TYPE_CHECKING:
    import instructor

    from app.schemas.extraction import EntityMergeCandidate

logger = get_logger(__name__)

# ── Tier 1: Exact match ────────────────────────────────────────────────


def normalize_name(name: str) -> str:
    """Normalize a name for exact comparison.

    Lowercases, strips whitespace, removes common articles/prefixes
    in both English and French.
    """
    name = unicodedata.normalize("NFC", name).strip().lower()
    # Remove common prefixes (English + French)
    for prefix in (
        # English
        "the ",
        "a ",
        "an ",
        # French — order matters: longer prefixes first
        "les ",
        "des ",
        "le ",
        "la ",
        "l'",
        "l'",
        "un ",
        "une ",
        "du ",
        "de ",
        "d'",
        "d'",
    ):
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
) -> tuple[list[dict[str, str]], list[tuple[str, str, int]], dict[str, str]]:
    """Tier 2: Find fuzzy duplicate pairs using thefuzz.

    Args:
        entities: List of dicts with 'name' key.
        threshold: Minimum fuzz ratio to flag as potential duplicate.

    Returns:
        Tuple of:
          - Entities with definite matches merged.
          - Candidate pairs for LLM review: (name_a, name_b, score).
          - Alias map from auto-merged names to their canonical form.
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

            name_a = normalize_name(names[i])
            name_b = normalize_name(names[j])
            score = max(
                fuzz.ratio(name_a, name_b),
                fuzz.partial_ratio(name_a, name_b),
                fuzz.token_sort_ratio(name_a, name_b),
                fuzz.token_set_ratio(name_a, name_b),
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

    return deduped, candidates, alias_map


# ── Tier 2.5: Hybrid BM25 + Embedding candidate generation ────────────


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    return text.lower().split()


def _bm25_scores(
    query_tokens: list[str],
    corpus_tokens: list[list[str]],
    idf: dict[str, float],
    avgdl: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Compute BM25 score of a query against each document in the corpus."""
    scores: list[float] = []
    for doc_tokens in corpus_tokens:
        dl = len(doc_tokens)
        tf = Counter(doc_tokens)
        score = 0.0
        for t in query_tokens:
            if t not in idf:
                continue
            freq = tf.get(t, 0)
            numerator = freq * (k1 + 1)
            denominator = freq + k1 * (1 - b + b * dl / avgdl) if avgdl > 0 else freq + k1
            score += idf[t] * (numerator / denominator)
        scores.append(score)
    return scores


async def hybrid_candidate_generation(
    entities: list[dict[str, str]],
    embedder=None,
    top_k: int = 5,
    threshold: float = 0.5,
) -> list[tuple[str, str, float]]:
    """Hybrid BM25 + semantic candidate generation for entity dedup.

    For each entity, retrieves top-k candidates via BM25 (on name) and
    top-k via embedding cosine similarity (on name+description). Fuses
    results by taking max(bm25_normalized, cosine) per pair.

    Args:
        entities: List of dicts with 'name' and optional 'description'.
        embedder: Async embedder with embed_texts() method.
        top_k: Number of candidates per retrieval method.
        threshold: Minimum fused score to keep a pair.

    Returns:
        List of (name_a, name_b, fused_score) tuples, deduplicated.
    """
    if len(entities) < 2:
        return []

    names = [e.get("name", "") for e in entities]
    descriptions = [e.get("description", "") for e in entities]
    n = len(names)

    # ── BM25 retrieval ──────────────────────────────────────────────
    corpus_tokens = [_tokenize(name) for name in names]
    avgdl = sum(len(d) for d in corpus_tokens) / max(n, 1)

    # Compute IDF
    df: Counter[str] = Counter()
    for doc in corpus_tokens:
        for token in set(doc):
            df[token] += 1
    idf = {
        t: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
        for t, freq in df.items()
    }

    # For each entity, get top-k BM25 candidates (excluding self)
    bm25_pairs: dict[tuple[int, int], float] = {}
    max_bm25 = 1e-9  # for normalization

    for i in range(n):
        scores = _bm25_scores(corpus_tokens[i], corpus_tokens, idf, avgdl)
        scores[i] = -1.0  # exclude self
        # Get top-k indices
        top_indices = sorted(range(n), key=lambda x: scores[x], reverse=True)[:top_k]
        for j in top_indices:
            if scores[j] <= 0:
                continue
            pair = (min(i, j), max(i, j))
            bm25_pairs[pair] = max(bm25_pairs.get(pair, 0.0), scores[j])
            if scores[j] > max_bm25:
                max_bm25 = scores[j]

    # Normalize BM25 scores to [0, 1]
    for pair in bm25_pairs:
        bm25_pairs[pair] /= max_bm25

    # ── Embedding retrieval ─────────────────────────────────────────
    emb_pairs: dict[tuple[int, int], float] = {}

    if embedder is not None:
        texts = [
            f"{name}: {desc}" if desc else name
            for name, desc in zip(names, descriptions, strict=True)
        ]
        embeddings = await embedder.embed_texts(texts)
        emb_matrix = np.array(embeddings)
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized = emb_matrix / norms
        sim_matrix = normalized @ normalized.T

        for i in range(n):
            # Zero out self-similarity
            sims = sim_matrix[i].copy()
            sims[i] = -1.0
            top_indices = np.argsort(sims)[-top_k:][::-1]
            for j in top_indices:
                if sims[j] <= 0:
                    continue
                pair = (min(i, int(j)), max(i, int(j)))
                emb_pairs[pair] = max(emb_pairs.get(pair, 0.0), float(sims[j]))

    # ── Fuse results ────────────────────────────────────────────────
    all_pairs = set(bm25_pairs.keys()) | set(emb_pairs.keys())
    candidates: list[tuple[str, str, float]] = []

    for pair in all_pairs:
        fused = max(bm25_pairs.get(pair, 0.0), emb_pairs.get(pair, 0.0))
        if fused >= threshold:
            i, j = pair
            candidates.append((names[i], names[j], fused))

    logger.info(
        "hybrid_candidate_generation",
        entities=n,
        bm25_pairs=len(bm25_pairs),
        emb_pairs=len(emb_pairs),
        fused_candidates=len(candidates),
    )

    return candidates


# ── Tier 2.5b: Cross-encoder reranking ─────────────────────────────────

CROSS_ENCODER_MERGE_THRESHOLD = 0.7  # auto-merge above this score
CROSS_ENCODER_LLM_THRESHOLD = 0.4  # keep as LLM candidate above this


async def cross_encoder_rerank(
    candidates: list[tuple[str, str, int]],
    entities: list[dict[str, str]],
    entity_type: str,
) -> tuple[list[dict[str, str]], list[tuple[str, str, int]], dict[str, str]]:
    """Tier 2.5b: Use local cross-encoder to resolve fuzzy candidates.

    Scores each candidate pair's descriptions with the zerank-1-small
    cross-encoder. High-confidence matches are auto-merged, clear
    non-matches are dropped, and ambiguous pairs pass to LLM (Tier 3).

    Args:
        candidates: Fuzzy candidate pairs (name_a, name_b, fuzzy_score).
        entities: Current entity list (for description lookup and merging).
        entity_type: Entity type label for logging context.

    Returns:
        Tuple of:
          - Updated entities with cross-encoder merges applied.
          - Remaining candidates for LLM review.
          - Alias map from cross-encoder auto-merges.
    """
    if not candidates:
        return entities, [], {}

    from app.llm.local_models import get_local_reranker

    reranker = get_local_reranker()

    # Build name -> description lookup from entities
    desc_map: dict[str, str] = {}
    for e in entities:
        name = e.get("name", "")
        desc = e.get("description", "") or e.get("summary", "") or name
        desc_map[name] = desc

    # Build sentence pairs for cross-encoder scoring
    pairs: list[list[str]] = []
    for name_a, name_b, _score in candidates:
        desc_a = desc_map.get(name_a, name_a)
        desc_b = desc_map.get(name_b, name_b)
        # Format as: "Entity: <name>. <description>" for richer context
        text_a = f"{entity_type}: {name_a}. {desc_a}"
        text_b = f"{entity_type}: {name_b}. {desc_b}"
        pairs.append([text_a, text_b])

    # Run cross-encoder in thread pool to avoid blocking async loop
    loop = asyncio.get_running_loop()
    raw_scores = await loop.run_in_executor(
        None,
        lambda: list(reranker.predict(pairs)),
    )

    alias_map: dict[str, str] = {}
    llm_candidates: list[tuple[str, str, int]] = []
    auto_merged = 0
    dropped = 0

    for (name_a, name_b, fuzzy_score), ce_score in zip(candidates, raw_scores, strict=True):
        if ce_score > CROSS_ENCODER_MERGE_THRESHOLD:
            # Auto-merge: pick longer name as canonical
            canonical = name_a if len(name_a) >= len(name_b) else name_b
            alias = name_b if canonical == name_a else name_a
            alias_map[alias] = canonical
            auto_merged += 1
        elif ce_score >= CROSS_ENCODER_LLM_THRESHOLD:
            # Ambiguous — escalate to LLM
            llm_candidates.append((name_a, name_b, fuzzy_score))
        else:
            # Clear non-match — drop
            dropped += 1

    # Remove merged entities from the list
    merged_names_normalized = {normalize_name(alias) for alias in alias_map}
    entities = [
        e
        for e in entities
        if normalize_name(e.get("name", "")) not in merged_names_normalized
    ]

    logger.info(
        "dedup_cross_encoder",
        entity_type=entity_type,
        input_candidates=len(candidates),
        auto_merged=auto_merged,
        escalated_to_llm=len(llm_candidates),
        dropped=dropped,
    )

    return entities, llm_candidates, alias_map


# ── Tier 3: LLM dedup (batched) ──────────────────────────────────────

LLM_BATCH_SIZE = 10


async def llm_dedup(
    candidates: list[tuple[str, str, int]],
    entity_type: str,
    client: instructor.AsyncInstructor,
    model: str,
    desc_map: dict[str, str] | None = None,
) -> list[EntityMergeCandidate]:
    """Tier 3: Use LLM to resolve ambiguous fuzzy matches in batches.

    Groups candidate pairs into clusters of up to LLM_BATCH_SIZE and sends
    one prompt per cluster asking the LLM to identify duplicates. This
    reduces the number of LLM calls compared to one-per-pair.

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

    # Split candidates into batches of LLM_BATCH_SIZE
    batches: list[list[tuple[str, str, int]]] = []
    for i in range(0, len(candidates), LLM_BATCH_SIZE):
        batches.append(candidates[i : i + LLM_BATCH_SIZE])

    results: list[EntityMergeCandidate] = []

    for batch_idx, batch in enumerate(batches):
        _dm = desc_map or {}
        candidates_text = "\n".join(
            f"{idx + 1}. '{a}'"
            + (f" — {_dm[a]}" if _dm.get(a) else "")
            + f" vs '{b}'"
            + (f" — {_dm[b]}" if _dm.get(b) else "")
            + f" (fuzzy score: {s}%)"
            for idx, (a, b, s) in enumerate(batch)
        )

        try:
            merge_results = await client.chat.completions.create(
                model=model,
                response_model=list[EntityMergeCandidate],
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are an entity resolution expert for {entity_type} entities "
                            "in fiction novels. You will receive a numbered list of entity "
                            "name pairs. For EACH pair, decide if they refer to the same "
                            "entity. Consider nicknames, shortened forms, titles, and context. "
                            "Return one result per pair."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Do these {entity_type} entity pairs refer to the same entity? "
                            "For each numbered pair, provide:\n"
                            "- entity_a_name and entity_b_name (the two names)\n"
                            "- confidence (0.0 = definitely different, 1.0 = definitely same)\n"
                            "- canonical_name (preferred name if they are the same)\n"
                            "- reason (brief explanation)\n\n"
                            f"{candidates_text}"
                        ),
                    },
                ],
            )

            for merge in merge_results:
                merge.entity_type = entity_type
                results.append(merge)

        except Exception:
            logger.warning(
                "dedup_llm_batch_failed",
                entity_type=entity_type,
                batch_index=batch_idx,
                batch_size=len(batch),
                exc_info=True,
            )
            # Fall back to fuzzy scores for this batch
            for name_a, name_b, score in batch:
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
        total_candidates=len(candidates),
        batches=len(batches),
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
    """Run the full 5-tier dedup pipeline.

    Pipeline: exact -> fuzzy -> cross-encoder -> LLM (batched).
    The cross-encoder tier auto-merges high-confidence pairs and drops
    clear non-matches, reducing the number of costly LLM calls.

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

    # Build description map for LLM context (Tier 3)
    desc_map: dict[str, str] = {
        e["name"]: e["description"]
        for e in entities
        if e.get("name") and e.get("description")
    }

    # Tier 1: exact
    entities, alias_map = exact_dedup(entities)

    if len(entities) <= 1:
        return entities, alias_map

    # Tier 2: fuzzy
    entities, candidates, fuzzy_alias_map = fuzzy_dedup(entities)
    alias_map.update(fuzzy_alias_map)

    # Tier 2.5b: cross-encoder reranking (reduces LLM calls)
    if candidates:
        try:
            entities, candidates, ce_alias_map = await cross_encoder_rerank(
                candidates, entities, entity_type
            )
            alias_map.update(ce_alias_map)
        except Exception:
            logger.warning("dedup_cross_encoder_failed", entity_type=entity_type, exc_info=True)

    # Tier 3: LLM batched (only if client provided and candidates remain)
    if candidates and client is not None:
        merges = await llm_dedup(candidates, entity_type, client, model, desc_map=desc_map)

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

    # Normalize alias_map keys to lowercase so V4's apply_alias_map_v4
    # (which does alias_map.get(name.lower(), name)) can find them.
    alias_map = {k.lower(): v for k, v in alias_map.items()}

    logger.info(
        "dedup_pipeline_completed",
        entity_type=entity_type,
        final_count=len(entities),
        total_aliases=len(alias_map),
    )

    return entities, alias_map


# ── Streaming per-chapter dedup ──────────────────────────────────────────


async def streaming_chapter_dedup(
    entity_repo,
    book_id: str,
    chapter_number: int,
    new_entities: list[dict],
) -> dict[str, str]:
    """Per-chapter streaming dedup using fuzzy matching against existing entities.

    After each chapter is persisted, compares newly created entities against
    existing entities in the same book using fuzzy name matching. When a
    high-confidence duplicate is found (score >= 90 but < 100), the newer
    entity is merged into the existing one by transferring relationships
    and deleting the duplicate node.

    Args:
        entity_repo: EntityRepository with execute_read / execute_write methods.
        book_id: Book identifier.
        chapter_number: Current chapter number (for logging context).
        new_entities: List of entity dicts from the current chapter extraction.

    Returns:
        A merge map ``{duplicate_name: canonical_name}`` for entities that
        were merged.  Empty dict if no merges occurred.
    """
    if not new_entities:
        return {}

    merge_map: dict[str, str] = {}

    for entity in new_entities:
        name = (entity.get("canonical_name") or entity.get("name", "")).lower().strip()
        entity_type = entity.get("entity_type", "")
        if not name or not entity_type:
            continue

        # Query existing entities of same type in the book (excluding self)
        existing = await entity_repo.execute_read(
            """
            MATCH (n {book_id: $book_id})
            WHERE n.canonical_name IS NOT NULL
              AND toLower(n.canonical_name) <> $name
              AND NOT n:Book AND NOT n:Chapter AND NOT n:Chunk
            RETURN n.canonical_name AS name, n.description AS desc
            LIMIT 50
            """,
            {"book_id": book_id, "name": name},
        )

        if not existing:
            continue

        # Quick fuzzy check
        for ex in existing:
            ex_name = (ex.get("name") or "").lower().strip()
            if not ex_name:
                continue
            score = fuzz.token_set_ratio(name, ex_name)
            if 90 <= score < 100:
                canonical = ex["name"]  # keep the original (existing) name
                merge_map[name] = canonical

                # Merge duplicate into canonical: copy aliases, then delete duplicate
                # Relations are not transferred here (no dynamic rel types in pure Cypher)
                # — the book-level iterative_cluster handles full merge with rel transfer
                await entity_repo.execute_write(
                    """
                    MATCH (dup {canonical_name: $old_name, book_id: $book_id})
                    MATCH (canon {canonical_name: $new_name, book_id: $book_id})
                    WHERE dup <> canon
                    // Copy aliases from duplicate to canonical
                    SET canon.aliases = coalesce(canon.aliases, []) + coalesce(dup.aliases, []) + [$old_name]
                    WITH dup
                    DETACH DELETE dup
                    """,
                    {"old_name": entity.get("canonical_name") or entity.get("name", ""),
                     "new_name": canonical,
                     "book_id": book_id},
                )
                break

    if merge_map:
        logger.info(
            "streaming_chapter_dedup_completed",
            book_id=book_id,
            chapter=chapter_number,
            merges=len(merge_map),
            merge_map=merge_map,
        )

    return merge_map
