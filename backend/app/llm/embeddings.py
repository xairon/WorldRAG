"""Embedding service — local (sentence-transformers) or API (Voyage AI).

Default: local BGE-M3 model via sentence-transformers (no API key needed).
Override: set EMBEDDING_PROVIDER=voyage + VOYAGE_API_KEY in .env to use Voyage AI.

Features:
- Automatic batching (up to 128 texts per request)
- Rate limiting per provider (Voyage only)
- Circuit breaker protection (Voyage only)
- Cost tracking integration
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.core.resilience import retry_llm_call

logger = get_logger(__name__)


class LocalEmbedder:
    """Local embedding client using sentence-transformers (BGE-M3).

    Runs on GPU if available, otherwise CPU.
    No API key required, zero cost.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model_name = model or settings.embedding_model
        self._model: Any = None
        self._lock = asyncio.Lock()

    async def _get_model(self):
        """Lazy-load model (thread-safe)."""
        if self._model is None:
            async with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name)
                    logger.info(
                        "local_embedder_loaded",
                        model=self.model_name,
                        device=str(self._model.device),
                    )
        return self._model

    async def embed_texts(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed.
            input_type: "document" or "query" (ignored for local models).

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        model = await self._get_model()
        # Run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True).tolist(),
        )
        logger.info(
            "embeddings_generated",
            count=len(texts),
            model=self.model_name,
            provider="local",
        )
        return embeddings

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


class VoyageEmbedder:
    """Async Voyage AI embedding client (API-based).

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
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        from app.core.rate_limiter import voyage_limiter
        from app.core.resilience import voyage_breaker

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
                provider="voyage",
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


def get_embedder() -> LocalEmbedder | VoyageEmbedder:
    """Factory: return the configured embedder instance.

    Uses EMBEDDING_PROVIDER setting: "local" (default) or "voyage".
    """
    if settings.embedding_provider == "voyage":
        if not settings.voyage_api_key:
            logger.warning("voyage_api_key_missing, falling back to local embedder")
            return LocalEmbedder()
        return VoyageEmbedder()
    return LocalEmbedder()
