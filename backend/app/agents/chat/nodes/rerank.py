"""Rerank node: zerank-1-small local cross-encoder reranker with SSE source streaming.

Replaces the previous Cohere API reranker with a local sentence-transformers
CrossEncoder. After reranking, emits a custom SSE 'sources' event via
LangGraph's stream writer so the frontend receives chunks in real-time.
"""

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.llm.local_models import get_local_reranker

logger = get_logger(__name__)

RERANK_TOP_N = 5
MIN_SCORE = -10.0  # zerank scores are not normalized; very low scores = irrelevant


async def rerank_results(state: dict[str, Any]) -> dict[str, Any]:
    """Rerank fused results using the local zerank-1-small cross-encoder.

    Runs the CrossEncoder synchronously in a thread-pool executor to avoid
    blocking the async event loop. Emits a 'sources' SSE event after reranking
    for real-time frontend display.
    """
    fused = state.get("fused_results", [])
    query = state.get("query", "")

    if not fused:
        return {"reranked_chunks": []}

    reranker = get_local_reranker()
    texts = [chunk["text"] for chunk in fused]

    loop = asyncio.get_running_loop()
    ranked = await loop.run_in_executor(
        None,
        lambda: reranker.rank(query, texts, top_k=len(texts), return_documents=False),
    )

    # Filter to top-N and attach relevance_score
    top = ranked[:RERANK_TOP_N]
    result = [
        {**fused[r["corpus_id"]], "relevance_score": float(r["score"])} for r in top
    ]

    logger.info(
        "rerank_completed",
        input_count=len(fused),
        output_count=len(result),
        top_score=result[0]["relevance_score"] if result else 0.0,
        model="zerank-1-small",
    )

    # Emit SSE 'sources' event for real-time frontend display
    try:
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
        writer(
            {
                "event": "sources",
                "chunks": [
                    {
                        "text": c["text"][:300],
                        "chapter_number": c.get("chapter_number", 0),
                        "chapter_title": c.get("chapter_title", ""),
                        "position": c.get("position", 0),
                        "relevance_score": c.get("relevance_score", 0.0),
                    }
                    for c in result
                ],
            }
        )
    except Exception:  # noqa: BLE001 — streaming is best-effort
        pass

    return {"reranked_chunks": result}
