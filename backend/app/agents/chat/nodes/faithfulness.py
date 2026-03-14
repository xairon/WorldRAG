"""NLI faithfulness check: DeBERTa-v3-large cross-encoder replaces LLM-as-judge.

Pipeline per turn:
1. Split generated answer into sentence-level claims
2. For each claim, run NLI (CrossEncoder) against the assembled context
   - entailment  → supported (1.0)
   - neutral     → partially supported (0.5)
   - contradiction → unsupported (0.0)
3. faithfulness_score = mean(per-claim scores)
4. Set faithfulness_passed based on adaptive route threshold
5. Flag contradictions for rewrite

Adaptive thresholds (route → minimum score to pass):
  factual_lookup:  0.8
  entity_qa:       0.7
  relationship_qa: 0.7
  timeline_qa:     0.6
  analytical:      0.5
  conversational:  skip (always passes)
"""

from __future__ import annotations

import asyncio
import copy
import math
import re
from typing import Any

from app.core.logging import get_logger
from app.llm.local_models import get_nli_model

logger = get_logger(__name__)

# Per-route faithfulness thresholds
_ROUTE_THRESHOLDS: dict[str, float] = {
    "factual_lookup": 0.8,
    "entity_qa": 0.7,
    "relationship_qa": 0.7,
    "timeline_qa": 0.6,
    "analytical": 0.5,
    "conversational": 2.0,  # > 1.0 → always skip
    "direct": 2.0,
}
_DEFAULT_THRESHOLD = 0.7
# Truncate context to avoid OOM in NLI model
_CTX_MAX_CHARS = 2000
# Min words per claim to bother scoring (skip very short fragments)
_MIN_CLAIM_WORDS = 4


def _split_claims(text: str) -> list[str]:
    """Split answer text into sentence-level claims for NLI scoring."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.split()) >= _MIN_CLAIM_WORDS]


def _nli_scores_to_faithfulness(
    raw_scores: list[list[float]],
) -> tuple[list[float], bool]:
    """Convert NLI logits to per-claim faithfulness scores.

    The NLI CrossEncoder returns logits in order: [contradiction, entailment, neutral].
    We apply softmax and compute: score = p_entail * 1.0 + p_neutral * 0.5.

    Returns:
        (per_claim_scores, has_contradiction)
    """
    claim_scores: list[float] = []
    has_contradiction = False

    for logits in raw_scores:
        c_logit, e_logit, n_logit = float(logits[0]), float(logits[1]), float(logits[2])
        exp_c, exp_e, exp_n = math.exp(c_logit), math.exp(e_logit), math.exp(n_logit)
        total = exp_c + exp_e + exp_n
        p_contra = exp_c / total
        p_entail = exp_e / total
        p_neutral = exp_n / total

        score = p_entail * 1.0 + p_neutral * 0.5
        claim_scores.append(score)

        if p_contra > 0.5:
            has_contradiction = True

    return claim_scores, has_contradiction


async def check_faithfulness(state: dict[str, Any]) -> dict[str, Any]:
    """NLI-based faithfulness check for the generated answer.

    Runs DeBERTa-v3-large in a thread-pool executor to avoid blocking the
    async event loop. Falls back to a neutral score (0.5) on any error.
    """
    route = state.get("route", "entity_qa")
    threshold = _ROUTE_THRESHOLDS.get(route, _DEFAULT_THRESHOLD)

    # Skip faithfulness check for conversational route
    if threshold > 1.0:
        return {
            "faithfulness_score": 1.0,
            "faithfulness_reason": "skipped for conversational route",
            "faithfulness_grounded": True,
            "faithfulness_relevant": True,
            "faithfulness_passed": True,
        }

    generation = state.get("generation", "")
    context = state.get("context", "")

    claims = _split_claims(generation)
    if not claims:
        logger.warning("faithfulness_no_claims", generation_len=len(generation))
        return {
            "faithfulness_score": 0.0,
            "faithfulness_reason": "no scoreable claims in answer",
            "faithfulness_grounded": False,
            "faithfulness_relevant": False,
            "faithfulness_passed": False,
        }

    truncated_ctx = context[:_CTX_MAX_CHARS]
    pairs = [(claim, truncated_ctx) for claim in claims]

    try:
        nli_model = get_nli_model()
        loop = asyncio.get_running_loop()
        raw_scores = await loop.run_in_executor(None, lambda: nli_model.predict(pairs).tolist())
        claim_scores, has_contradiction = _nli_scores_to_faithfulness(raw_scores)
        faith_score = sum(claim_scores) / len(claim_scores)
        passed = faith_score >= threshold and not has_contradiction
        reason = f"NLI score {faith_score:.2f} (threshold {threshold})" + (
            " — contradiction detected" if has_contradiction else ""
        )
    except Exception:  # noqa: BLE001
        logger.warning("faithfulness_nli_failed", route=route, exc_info=True)
        # Default to neutral (0.5) on error — neither pass nor fail forcefully
        faith_score = 0.5
        passed = threshold <= 0.5
        has_contradiction = False
        reason = "NLI model error, defaulting to 0.5"

    # Update generation_output confidence if present (deep copy to avoid shared state)
    gen_output = state.get("generation_output", {})
    if isinstance(gen_output, dict):
        gen_output = copy.deepcopy(gen_output)
        gen_output["confidence"] = faith_score

    logger.info(
        "faithfulness_check_completed",
        route=route,
        score=round(faith_score, 3),
        threshold=threshold,
        passed=passed,
        claims=len(claims),
        has_contradiction=has_contradiction,
    )

    return {
        "faithfulness_score": faith_score,
        "faithfulness_reason": reason,
        "faithfulness_grounded": not has_contradiction,
        "faithfulness_relevant": faith_score >= 0.3,
        "faithfulness_passed": passed,
        "generation_output": gen_output,
    }
