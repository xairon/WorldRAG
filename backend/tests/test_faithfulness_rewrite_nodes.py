"""Tests for faithfulness check and rewrite query nodes."""
import pytest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage


class TestFaithfulnessNode:
    @pytest.mark.asyncio
    async def test_grounded_answer_passes(self):
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"score": 0.95, "grounded": true, "relevant": true, "reason": "All claims supported."}'
        ))

        state = {
            "query": "Who is Jake?",
            "context": "Jake is an Arcane Hunter.",
            "generation": "Jake is an Arcane Hunter.",
        }

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(state)

        assert result["faithfulness_score"] == pytest.approx(0.95)
        assert result["faithfulness_reason"] == "All claims supported."

    @pytest.mark.asyncio
    async def test_ungrounded_answer_fails(self):
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"score": 0.2, "grounded": false, "relevant": true, "reason": "Claim about level not in context."}'
        ))

        state = {
            "query": "What level is Jake?",
            "context": "Jake is an Arcane Hunter.",
            "generation": "Jake is level 200.",
        }

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(state)

        assert result["faithfulness_score"] < 0.5

    @pytest.mark.asyncio
    async def test_parse_failure_defaults_to_pass(self):
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="not json"))

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness({
                "query": "test", "context": "ctx", "generation": "gen",
            })

        assert result["faithfulness_score"] == 1.0


class TestRewriteNode:
    @pytest.mark.asyncio
    async def test_rewrites_query(self):
        from app.agents.chat.nodes.rewrite import rewrite_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content="What are the specific combat abilities of Randidly Ghosthound?"
        ))

        state = {
            "query": "What can Randidly do?",
            "original_query": "What can Randidly do?",
            "faithfulness_reason": "Answer too vague, not grounded",
        }

        with patch("app.agents.chat.nodes.rewrite.get_langchain_llm", return_value=mock_llm):
            result = await rewrite_query(state)

        assert result["query"] != "What can Randidly do?"
        assert result["retries"] == 1

    @pytest.mark.asyncio
    async def test_preserves_original_query(self):
        from app.agents.chat.nodes.rewrite import rewrite_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="rewritten"))

        with patch("app.agents.chat.nodes.rewrite.get_langchain_llm", return_value=mock_llm):
            result = await rewrite_query({
                "query": "old", "original_query": "original",
                "faithfulness_reason": "bad",
            })

        assert "original_query" not in result
