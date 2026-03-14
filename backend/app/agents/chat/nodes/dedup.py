"""Chunk deduplication node: remove near-duplicate chunks via cosine similarity.

Filters out chunks that are semantically near-identical (cosine sim > threshold)
to avoid feeding redundant context to the generator, which hurts faithfulness
scoring and wastes the context window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.llm.embeddings import LocalEmbedder

logger = get_logger(__name__)

_DEDUP_THRESHOLD = 0.80  # remove chunk if cos-sim > this with a higher-ranked chunk


async def deduplicate_chunks(
    chunks: list[dict[str, Any]],
    embedder: LocalEmbedder,
    *,
    threshold: float = _DEDUP_THRESHOLD,
) -> list[dict[str, Any]]:
    """Remove near-duplicate chunks from a ranked list.

    Preserves the input ranking order — the first occurrence of a near-duplicate
    cluster is kept, later occurrences are removed.

    Args:
        chunks: Ranked list of chunk dicts, each with a "text" field.
        embedder: Local embedder for computing cosine similarities.
        threshold: Cosine similarity above which a chunk is considered a duplicate.

    Returns:
        Deduplicated list in the same relative order.
    """
    if len(chunks) <= 1:
        return chunks

    import numpy as np

    texts = [c["text"] for c in chunks]
    embeddings = await embedder.embed_texts(texts)
    emb = np.array(embeddings)  # (N, D) — already L2-normalized by LocalEmbedder

    sim = emb @ emb.T  # cosine similarity matrix: (N, N)

    kept: list[dict[str, Any]] = []
    removed: set[int] = set()

    for i in range(len(chunks)):
        if i in removed:
            continue
        kept.append(chunks[i])
        for j in range(i + 1, len(chunks)):
            if j not in removed and float(sim[i, j]) > threshold:
                removed.add(j)

    logger.info(
        "dedup_completed",
        input_count=len(chunks),
        output_count=len(kept),
        removed_count=len(removed),
        threshold=threshold,
    )
    return kept
