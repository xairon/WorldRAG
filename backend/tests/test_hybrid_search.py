"""Tests for hybrid search with RRF fusion."""

import pytest

from app.agents.chat.nodes.retrieve import RRF_K, rrf_fuse


def test_rrf_fuse_single_list():
    """RRF with one result list returns ranked scores."""
    results = [
        {"node_id": "a", "text": "t1"},
        {"node_id": "b", "text": "t2"},
        {"node_id": "c", "text": "t3"},
    ]
    fused = rrf_fuse([results], weights=[1.0], top_k=3)
    assert len(fused) == 3
    assert fused[0]["node_id"] == "a"
    assert fused[0]["rrf_score"] == pytest.approx(1.0 / (RRF_K + 1))


def test_rrf_fuse_two_lists_boosts_overlap():
    """Documents appearing in both lists get boosted."""
    dense = [
        {"node_id": "a", "text": "t1"},
        {"node_id": "b", "text": "t2"},
    ]
    sparse = [
        {"node_id": "b", "text": "t2"},
        {"node_id": "c", "text": "t3"},
    ]
    fused = rrf_fuse([dense, sparse], weights=[1.0, 1.0], top_k=3)
    assert fused[0]["node_id"] == "b"


def test_rrf_fuse_respects_weights():
    """Higher weight amplifies one list's contribution."""
    list_a = [{"node_id": "x", "text": "tx"}]
    list_b = [{"node_id": "y", "text": "ty"}]
    fused = rrf_fuse([list_a, list_b], weights=[0.1, 10.0], top_k=2)
    assert fused[0]["node_id"] == "y"


def test_rrf_fuse_top_k_limit():
    """Returns at most top_k results."""
    results = [{"node_id": str(i), "text": f"t{i}"} for i in range(20)]
    fused = rrf_fuse([results], weights=[1.0], top_k=5)
    assert len(fused) == 5


def test_rrf_fuse_empty_lists():
    """Empty input returns empty output."""
    fused = rrf_fuse([[], []], weights=[1.0, 1.0], top_k=5)
    assert fused == []


def test_rrf_fuse_preserves_metadata():
    """Fused results preserve all original metadata from first occurrence."""
    results = [
        {"node_id": "a", "text": "hello", "chapter_number": 5, "chapter_title": "Ch5"},
    ]
    fused = rrf_fuse([results], weights=[1.0], top_k=1)
    assert fused[0]["chapter_number"] == 5
    assert fused[0]["chapter_title"] == "Ch5"
    assert "rrf_score" in fused[0]
