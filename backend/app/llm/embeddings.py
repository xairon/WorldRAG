"""Local sentence-transformers embedding service.

Provides async embedding generation using a local model on GPU.
Replaces VoyageAI for offline, zero-cost embeddings.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level singleton — loaded once, reused across requests
_model_instance: Any = None
_model_lock = asyncio.Lock()


async def _get_model():
    """Lazy-load and cache the SentenceTransformer model (async-safe)."""
    global _model_instance  # noqa: PLW0603
    if _model_instance is not None:
        return _model_instance

    async with _model_lock:
        if _model_instance is not None:
            return _model_instance

        loop = asyncio.get_running_loop()
        _model_instance = await loop.run_in_executor(None, _load_model)
        return _model_instance


def _load_model():
    """Synchronous model loading (runs in thread pool)."""
    from sentence_transformers import SentenceTransformer

    model_name = settings.embedding_model
    device = settings.embedding_device
    logger.info("loading_embedding_model", model=model_name, device=device)
    model = SentenceTransformer(model_name, device=device)
    dims = model.get_sentence_embedding_dimension()
    logger.info("embedding_model_loaded", model=model_name, device=device, dimensions=dims)
    return model


class LocalEmbedder:
    """Async local embedding client using sentence-transformers.

    Features:
    - GPU-accelerated inference (CUDA)
    - No API calls (offline, zero cost)
    - Same interface as the previous VoyageEmbedder
    """

    def __init__(self, model: str | None = None) -> None:
        self.model_name = model or settings.embedding_model

    async def embed_texts(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed.
            input_type: "document" for indexing, "query" for search (ignored for local).

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        model = await _get_model()
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
        )

        logger.info(
            "embeddings_generated",
            count=len(texts),
            model=self.model_name,
            device=settings.embedding_device,
        )
        return embeddings.tolist()

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query text."""
        result = await self.embed_texts([query], input_type="query")
        return result[0]

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """Embed documents in batches."""
        all_embeddings: list[list[float]] = []
        batch_size = settings.embedding_batch_size

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            embeddings = await self.embed_texts(batch, input_type="document")
            all_embeddings.extend(embeddings)

        return all_embeddings


# Backward-compatible alias
VoyageEmbedder = LocalEmbedder
