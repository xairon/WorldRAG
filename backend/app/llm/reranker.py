"""Cohere Rerank service.

Provides reranking of retrieval results for improved relevance.
Used in the hybrid retrieval pipeline (Vector + Fulltext + Graph → Rerank → LLM).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.core.logging import get_logger
from app.core.rate_limiter import cohere_limiter
from app.core.resilience import cohere_breaker, retry_llm_call

logger = get_logger(__name__)


@dataclass
class RerankResult:
    """A reranked document with relevance score."""

    index: int
    text: str
    relevance_score: float


class CohereReranker:
    """Async Cohere Rerank client.

    Features:
    - Rerank top-N documents by relevance to query
    - Circuit breaker and rate limiting
    - Returns scores for filtering
    """

    def __init__(self, model: str = "rerank-v3.5") -> None:
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import cohere

            self._client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
        return self._client

    @retry_llm_call(max_attempts=3)
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 10,
        min_relevance: float = 0.0,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query.
            documents: Documents to rerank.
            top_n: Number of top results to return.
            min_relevance: Minimum relevance score to include.

        Returns:
            List of RerankResult sorted by relevance (descending).
        """
        if not documents:
            return []

        await cohere_limiter.acquire()
        try:
            response = await cohere_breaker.call(
                self.client.rerank,
                query=query,
                documents=documents,
                model=self.model,
                top_n=min(top_n, len(documents)),
            )

            results = [
                RerankResult(
                    index=r.index,
                    text=documents[r.index],
                    relevance_score=r.relevance_score,
                )
                for r in response.results
                if r.relevance_score >= min_relevance
            ]

            logger.info(
                "rerank_completed",
                query_len=len(query),
                input_docs=len(documents),
                output_docs=len(results),
                top_score=results[0].relevance_score if results else 0,
            )
            return results
        finally:
            cohere_limiter.release()
