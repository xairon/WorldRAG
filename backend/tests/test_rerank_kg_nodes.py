"""Tests for rerank and KG query nodes."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage


def _make_mock_reranker(scores: list[float]):
    """Return a mock zerank CrossEncoder whose rank() returns scores sorted desc (real API)."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    ranked = sorted(
        [{"corpus_id": i, "score": s} for i, s in enumerate(scores)],
        key=lambda x: x["score"],
        reverse=True,
    )
    mock.rank = MagicMock(return_value=ranked)
    return mock


class TestRerankNode:
    """Tests for the zerank rerank node."""

    @pytest.mark.asyncio
    async def test_rerank_with_zerank(self):
        from app.agents.chat.nodes.rerank import rerank_results

        # second chunk scores higher → should come first
        mock_reranker = _make_mock_reranker([0.6, 0.95])

        state = {
            "query": "test",
            "fused_results": [
                {"node_id": "a", "text": "less relevant", "chapter_number": 1, "rrf_score": 0.5},
                {"node_id": "b", "text": "relevant", "chapter_number": 2, "rrf_score": 0.4},
            ],
        }

        with patch("app.agents.chat.nodes.rerank.get_local_reranker", return_value=mock_reranker):
            result = await rerank_results(state)

        assert len(result["reranked_chunks"]) == 2
        assert result["reranked_chunks"][0]["node_id"] == "b"
        assert result["reranked_chunks"][0]["relevance_score"] == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_rerank_empty_fused(self):
        from app.agents.chat.nodes.rerank import rerank_results

        result = await rerank_results({"query": "test", "fused_results": []})
        assert result["reranked_chunks"] == []

    @pytest.mark.asyncio
    async def test_rerank_returns_top_n(self):
        from app.agents.chat.nodes.rerank import RERANK_TOP_N, rerank_results

        chunks = [{"node_id": str(i), "text": f"t{i}", "rrf_score": 0.1} for i in range(10)]
        scores = list(range(10, 0, -1))  # descending
        mock_reranker = _make_mock_reranker(scores)

        state = {"query": "test", "fused_results": chunks}
        with patch("app.agents.chat.nodes.rerank.get_local_reranker", return_value=mock_reranker):
            result = await rerank_results(state)

        assert len(result["reranked_chunks"]) == RERANK_TOP_N


class TestKGQueryNode:
    """Tests for the KG query node."""

    @pytest.mark.asyncio
    async def test_entity_lookup(self):
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content='{"entities": ["Randidly"], "query_type": "entity_lookup"}'
            )
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                [
                    {
                        "name": "Randidly Ghosthound",
                        "label": "Character",
                        "description": "Main protagonist",
                        "score": 5.0,
                    }
                ],
                [
                    {
                        "source": "Randidly Ghosthound",
                        "rel_type": "HAS_SKILL",
                        "target_name": "Spear Mastery",
                        "target_label": "Skill",
                    }
                ],
                [
                    {
                        "text": "Randidly gripped his spear...",
                        "chapter_number": 1,
                        "chapter_title": "Awakening",
                        "node_id": "c1",
                    }
                ],
            ]
        )

        with patch("app.agents.chat.nodes.kg_query.get_langchain_llm", return_value=mock_llm):
            result = await kg_search(
                {"query": "Who is Randidly?", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        assert len(result["kg_cypher_result"]) > 0
        assert len(result["kg_entities"]) > 0

    @pytest.mark.asyncio
    async def test_empty_entity_fallback(self):
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content='{"entities": ["NonExistent"], "query_type": "entity_lookup"}'
            )
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        with patch("app.agents.chat.nodes.kg_query.get_langchain_llm", return_value=mock_llm):
            result = await kg_search(
                {"query": "Who is NonExistent?", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        assert result["route"] == "entity_qa"
        assert result["kg_cypher_result"] == []
