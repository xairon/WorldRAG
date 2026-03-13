"""Tests for rerank and KG query nodes."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from langchain_core.messages import AIMessage


class TestRerankNode:
    """Tests for the rerank node."""

    @pytest.mark.asyncio
    async def test_rerank_with_cohere(self):
        from app.agents.chat.nodes.rerank import rerank_results
        from app.llm.reranker import RerankResult

        mock_reranker = AsyncMock()
        mock_reranker.rerank = AsyncMock(return_value=[
            RerankResult(index=1, text="relevant", relevance_score=0.95),
            RerankResult(index=0, text="less relevant", relevance_score=0.6),
        ])

        state = {
            "query": "test",
            "fused_results": [
                {"node_id": "a", "text": "less relevant", "chapter_number": 1, "rrf_score": 0.5},
                {"node_id": "b", "text": "relevant", "chapter_number": 2, "rrf_score": 0.4},
            ],
        }

        with patch("app.agents.chat.nodes.rerank._get_reranker", return_value=mock_reranker):
            result = await rerank_results(state)

        assert len(result["reranked_chunks"]) == 2
        assert result["reranked_chunks"][0]["node_id"] == "b"
        assert result["reranked_chunks"][0]["relevance_score"] == 0.95

    @pytest.mark.asyncio
    async def test_rerank_without_cohere_uses_rrf_order(self):
        from app.agents.chat.nodes.rerank import rerank_results

        state = {
            "query": "test",
            "fused_results": [
                {"node_id": "a", "text": "t1", "rrf_score": 0.5},
                {"node_id": "b", "text": "t2", "rrf_score": 0.4},
            ],
        }

        with patch("app.agents.chat.nodes.rerank._get_reranker", return_value=None):
            result = await rerank_results(state)

        assert len(result["reranked_chunks"]) == 2
        assert result["reranked_chunks"][0]["node_id"] == "a"

    @pytest.mark.asyncio
    async def test_rerank_empty_fused(self):
        from app.agents.chat.nodes.rerank import rerank_results

        with patch("app.agents.chat.nodes.rerank._get_reranker", return_value=None):
            result = await rerank_results({"query": "test", "fused_results": []})

        assert result["reranked_chunks"] == []


class TestKGQueryNode:
    """Tests for the KG query node."""

    @pytest.mark.asyncio
    async def test_entity_lookup(self):
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"entities": ["Randidly"], "query_type": "entity_lookup"}'
        ))

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(side_effect=[
            [{"name": "Randidly Ghosthound", "label": "Character",
              "description": "Main protagonist", "score": 5.0}],
            [{"source": "Randidly Ghosthound", "rel_type": "HAS_SKILL", "target_name": "Spear Mastery",
              "target_label": "Skill"}],
            [{"text": "Randidly gripped his spear...", "chapter_number": 1,
              "chapter_title": "Awakening", "node_id": "c1"}],
        ])

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
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"entities": ["NonExistent"], "query_type": "entity_lookup"}'
        ))

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        with patch("app.agents.chat.nodes.kg_query.get_langchain_llm", return_value=mock_llm):
            result = await kg_search(
                {"query": "Who is NonExistent?", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        assert result["route"] == "hybrid_rag"
        assert result["kg_cypher_result"] == []
