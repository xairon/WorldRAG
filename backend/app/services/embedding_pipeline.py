"""Embedding pipeline service.

Generates Voyage AI embeddings for Chunk nodes and writes them
back to Neo4j via batch UNWIND Cypher. Tracks cost via CostTracker.

Handles partial failures: failed batches are logged and skipped,
not propagated as fatal errors. This allows the pipeline to embed
as many chunks as possible even when some fail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.cost_tracker import calculate_cost, count_tokens
from app.core.logging import get_logger
from app.llm.embeddings import VoyageEmbedder

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from app.core.cost_tracker import CostTracker

logger = get_logger(__name__)

# Voyage API batch limit — matches VoyageEmbedder.embed_documents() internal batch size
EMBEDDING_BATCH_SIZE = 128


@dataclass
class EmbeddingResult:
    """Result of an embedding pipeline run."""

    book_id: str
    total_chunks: int
    embedded: int
    failed: int
    failed_keys: list[tuple[str, int]] = field(default_factory=list)
    total_tokens: int = 0
    cost_usd: float = 0.0


async def embed_book_chunks(
    driver: AsyncDriver,
    book_id: str,
    chunks: list[dict[str, Any]],
    cost_tracker: CostTracker | None = None,
) -> EmbeddingResult:
    """Embed all chunks for a book and write embeddings to Neo4j.

    Args:
        driver: Neo4j async driver.
        book_id: Book identifier (for cost tracking and logging).
        chunks: List of chunk descriptors from get_chunks_for_embedding().
            Each dict must have keys: chapter_id, position, text.
        cost_tracker: Optional CostTracker for cost recording.

    Returns:
        EmbeddingResult with stats and partial failure info.
    """
    result = EmbeddingResult(
        book_id=book_id,
        total_chunks=len(chunks),
        embedded=0,
        failed=0,
    )

    if not chunks:
        return result

    embedder = VoyageEmbedder()

    for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[i : i + EMBEDDING_BATCH_SIZE]
        texts = [c["text"] for c in batch]

        try:
            # embed_texts() handles retry + circuit breaker + rate limiting
            embeddings = await embedder.embed_texts(texts, input_type="document")
        except Exception:
            logger.exception(
                "embedding_batch_failed",
                book_id=book_id,
                batch_start=i,
                batch_size=len(batch),
            )
            result.failed += len(batch)
            result.failed_keys.extend((c["chapter_id"], int(c["position"])) for c in batch)
            continue

        # Count tokens for cost tracking (tiktoken approximation)
        batch_tokens = sum(count_tokens(t) for t in texts)
        result.total_tokens += batch_tokens

        # Write embeddings to Neo4j via UNWIND
        await _write_embeddings(driver, batch, embeddings)
        result.embedded += len(batch)

        # Record cost
        if cost_tracker:
            await cost_tracker.record(
                model="voyage-3.5",
                provider="voyage",
                input_tokens=batch_tokens,
                output_tokens=0,
                operation="embedding",
                book_id=book_id,
            )

    # Compute total cost
    result.cost_usd = calculate_cost("voyage-3.5", result.total_tokens, 0)

    logger.info(
        "embedding_pipeline_completed",
        book_id=book_id,
        total=result.total_chunks,
        embedded=result.embedded,
        failed=result.failed,
        total_tokens=result.total_tokens,
        cost_usd=round(result.cost_usd, 6),
    )

    return result


async def _write_embeddings(
    driver: AsyncDriver,
    batch: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    """Write a batch of embeddings to Chunk nodes via UNWIND.

    Matches on (chapter_id, position) — the compound unique key
    for Chunk nodes in this schema.
    """
    payload = [
        {
            "chapter_id": batch[j]["chapter_id"],
            "position": int(batch[j]["position"]),
            "embedding": embeddings[j],
        }
        for j in range(len(batch))
    ]

    async with driver.session() as session:
        await session.run(
            """
            UNWIND $items AS item
            MATCH (ck:Chunk {chapter_id: item.chapter_id, position: item.position})
            SET ck.embedding = item.embedding
            """,
            {"items": payload},
        )
