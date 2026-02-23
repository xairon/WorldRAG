"""Voyage AI embedding service.

Provides async embedding generation with batching and caching.
Used for entity embeddings and retrieval.
"""

from __future__ import annotations

from app.config import settings
from app.core.logging import get_logger
from app.core.rate_limiter import voyage_limiter
from app.core.resilience import retry_llm_call, voyage_breaker

logger = get_logger(__name__)


class VoyageEmbedder:
    """Async Voyage AI embedding client.

    Features:
    - Automatic batching (up to 128 texts per request)
    - Rate limiting per provider
    - Circuit breaker protection
    - Cost tracking integration
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.voyage_model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import voyageai

            self._client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        return self._client

    @retry_llm_call(max_attempts=3)
    async def embed_texts(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed.
            input_type: "document" for indexing, "query" for search.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        await voyage_limiter.acquire()
        try:
            result = await voyage_breaker.call(
                self.client.embed,
                texts,
                model=self.model,
                input_type=input_type,
            )
            logger.info(
                "embeddings_generated",
                count=len(texts),
                model=self.model,
                total_tokens=result.total_tokens,
            )
            return result.embeddings
        finally:
            voyage_limiter.release()

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query text."""
        result = await self.embed_texts([query], input_type="query")
        return result[0]

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """Embed documents in batches of 128."""
        all_embeddings: list[list[float]] = []
        batch_size = 128

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            embeddings = await self.embed_texts(batch, input_type="document")
            all_embeddings.extend(embeddings)

        return all_embeddings
