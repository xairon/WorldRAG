"""Tests for retrieval upgrade nodes: multi-dense retrieve, dedup, temporal_sort."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.chat.nodes.dedup import deduplicate_chunks
from app.agents.chat.nodes.temporal_sort import temporal_sort
from app.agents.chat.nodes.retrieve import hybrid_retrieve, rrf_fuse


# ---------------------------------------------------------------------------
# rrf_fuse
# ---------------------------------------------------------------------------


def test_rrf_fuse_empty_lists():
    assert rrf_fuse([[], []], weights=[1.0, 1.0]) == []


def test_rrf_fuse_single_list():
    docs = [{"node_id": "a"}, {"node_id": "b"}]
    result = rrf_fuse([docs], weights=[1.0])
    assert [r["node_id"] for r in result] == ["a", "b"]


def test_rrf_fuse_deduplicates_across_lists():
    docs1 = [{"node_id": "a"}, {"node_id": "b"}]
    docs2 = [{"node_id": "a"}, {"node_id": "c"}]
    result = rrf_fuse([docs1, docs2], weights=[1.0, 1.0])
    ids = [r["node_id"] for r in result]
    assert ids.count("a") == 1  # deduplicated
    assert "a" in ids and "b" in ids and "c" in ids


def test_rrf_fuse_respects_top_k():
    docs = [{"node_id": str(i)} for i in range(10)]
    result = rrf_fuse([docs], weights=[1.0], top_k=3)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# hybrid_retrieve: extra_dense_embeddings param
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_retrieve_uses_extra_dense_embeddings():
    """Extra dense embeddings should each trigger a separate dense search."""
    mock_repo = MagicMock()
    mock_repo.execute_read = AsyncMock(return_value=[])

    await hybrid_retrieve(
        mock_repo,
        query_text="Who is Jake?",
        query_embedding=[0.1] * 768,
        extra_dense_embeddings=[[0.2] * 768, [0.3] * 768],
        book_id="b1",
        max_chapter=None,
    )

    # 3 dense + 1 sparse + 1 graph = 5 execute_read calls
    assert mock_repo.execute_read.call_count == 5


@pytest.mark.asyncio
async def test_hybrid_retrieve_no_extra_embeddings_backward_compat():
    """Without extra embeddings, should behave as before (1 dense arm)."""
    mock_repo = MagicMock()
    mock_repo.execute_read = AsyncMock(return_value=[])

    await hybrid_retrieve(
        mock_repo,
        query_text="Who is Jake?",
        query_embedding=[0.1] * 768,
        book_id="b1",
        max_chapter=None,
    )

    # 1 dense + 1 sparse + 1 graph = 3 execute_read calls
    assert mock_repo.execute_read.call_count == 3


# ---------------------------------------------------------------------------
# deduplicate_chunks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_removes_near_duplicates():
    """Chunks with cosine sim > 0.80 should be deduplicated."""
    import numpy as np

    chunks = [
        {"node_id": "a", "text": "Jake is a hunter."},
        {"node_id": "b", "text": "Jake is a hunter (duplicate)."},  # near-identical
        {"node_id": "c", "text": "Mira is a mage."},  # different
    ]

    # Simulate embeddings: a~b are very similar, c is different
    emb_a = np.array([1.0, 0.0, 0.0])
    emb_b = np.array([0.99, 0.1, 0.0])  # cos sim > 0.80 with a
    emb_c = np.array([0.0, 1.0, 0.0])

    # Normalize
    def norm(v):
        return v / np.linalg.norm(v)

    embeddings = [norm(emb_a).tolist(), norm(emb_b).tolist(), norm(emb_c).tolist()]

    mock_embedder = MagicMock()
    mock_embedder.embed_texts = AsyncMock(return_value=embeddings)

    result = await deduplicate_chunks(chunks, mock_embedder, threshold=0.80)

    ids = [r["node_id"] for r in result]
    assert "a" in ids
    assert "b" not in ids  # removed as near-duplicate of a
    assert "c" in ids


@pytest.mark.asyncio
async def test_dedup_single_chunk_no_op():
    mock_embedder = MagicMock()
    mock_embedder.embed_texts = AsyncMock(return_value=[[0.1] * 10])

    chunks = [{"node_id": "a", "text": "Some text."}]
    result = await deduplicate_chunks(chunks, mock_embedder)
    assert result == chunks
    mock_embedder.embed_texts.assert_not_called()  # skipped for single chunk


@pytest.mark.asyncio
async def test_dedup_empty_input():
    mock_embedder = MagicMock()
    result = await deduplicate_chunks([], mock_embedder)
    assert result == []


# ---------------------------------------------------------------------------
# temporal_sort
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_temporal_sort_orders_by_chapter_then_position():
    chunks = [
        {"node_id": "c", "chapter_number": 5, "position": 1},
        {"node_id": "a", "chapter_number": 2, "position": 3},
        {"node_id": "b", "chapter_number": 2, "position": 1},
    ]
    state = {"route": "timeline_qa", "reranked_chunks": chunks}
    result = await temporal_sort(state)

    sorted_ids = [c["node_id"] for c in result["reranked_chunks"]]
    assert sorted_ids == ["b", "a", "c"]


@pytest.mark.asyncio
async def test_temporal_sort_noop_for_non_timeline():
    chunks = [
        {"node_id": "c", "chapter_number": 5, "position": 1},
        {"node_id": "a", "chapter_number": 2, "position": 1},
    ]
    for route in ("factual_lookup", "entity_qa", "analytical", "conversational"):
        state = {"route": route, "reranked_chunks": chunks}
        result = await temporal_sort(state)
        assert result == {}, f"Expected no-op for route={route}"


@pytest.mark.asyncio
async def test_temporal_sort_noop_empty_chunks():
    result = await temporal_sort({"route": "timeline_qa", "reranked_chunks": []})
    assert result == {}
