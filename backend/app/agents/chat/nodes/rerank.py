"""Rerank node: cross-encoder reranking via Cohere (optional fallback to RRF order)."""

from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

RERANK_TOP_N = 5
MIN_RELEVANCE = 0.1

_reranker_instance = None


def _get_reranker():
    """Lazy-load Cohere reranker if API key is configured."""
    global _reranker_instance
    if _reranker_instance is None and settings.cohere_api_key:
        from app.llm.reranker import CohereReranker
        _reranker_instance = CohereReranker()
    return _reranker_instance


async def rerank_results(state: dict[str, Any]) -> dict[str, Any]:
    """Rerank fused results using Cohere cross-encoder or fallback to RRF order."""
    fused = state.get("fused_results", [])
    query = state["query"]
    reranker = _get_reranker()

    if not fused:
        return {"reranked_chunks": []}

    if reranker:
        texts = [chunk["text"] for chunk in fused]
        reranked = await reranker.rerank(
            query=query,
            documents=texts,
            top_n=min(RERANK_TOP_N, len(fused)),
            min_relevance=MIN_RELEVANCE,
        )

        result = []
        for r in reranked:
            chunk = {**fused[r.index], "relevance_score": r.relevance_score}
            result.append(chunk)

        logger.info(
            "rerank_completed",
            input_count=len(fused),
            output_count=len(result),
            top_score=result[0]["relevance_score"] if result else 0,
        )
        return {"reranked_chunks": result}

    # No reranker available — use RRF order, take top-N
    top = fused[:RERANK_TOP_N]
    for chunk in top:
        chunk["relevance_score"] = chunk.get("rrf_score", 0.0)

    logger.info("rerank_skipped_no_cohere", output_count=len(top))
    return {"reranked_chunks": top}
