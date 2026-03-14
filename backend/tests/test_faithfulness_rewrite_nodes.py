"""Tests for faithfulness check and rewrite query nodes."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage


class TestFaithfulnessNode:
    @pytest.mark.asyncio
    async def test_grounded_answer_passes(self):
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=(
                    '{"score": 0.95, "grounded": true, "relevant": true,'
                    ' "reason": "All claims supported."}'
                )
            )
        )

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
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=(
                    '{"score": 0.2, "grounded": false, "relevant": true,'
                    ' "reason": "Claim about level not in context."}'
                )
            )
        )

        state = {
            "query": "What level is Jake?",
            "context": "Jake is an Arcane Hunter.",
            "generation": "Jake is level 200.",
        }

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(state)

        assert result["faithfulness_score"] < 0.5

    @pytest.mark.asyncio
    async def test_parse_failure_defaults_to_fail(self):
        """Parse failure should default to 0.0 (fail) to force retry."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="not json"))

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(
                {
                    "query": "test",
                    "context": "ctx",
                    "generation": "gen",
                }
            )

        assert result["faithfulness_score"] == 0.0

    # -------------------------------------------------------------------
    # N6 regression: faithfulness returns grounded + relevant booleans
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_returns_grounded_and_relevant_booleans(self):
        """N6 fix: check_faithfulness returns grounded/relevant in state dict."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content='{"score": 0.85, "grounded": true, "relevant": false, "reason": "ok"}'
            )
        )

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(
                {"query": "q", "context": "c", "generation": "g"}
            )

        assert "faithfulness_grounded" in result
        assert "faithfulness_relevant" in result
        assert result["faithfulness_grounded"] is True
        assert result["faithfulness_relevant"] is False

    @pytest.mark.asyncio
    async def test_parse_failure_returns_false_booleans(self):
        """N6 fix: parse failure sets grounded/relevant to False."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="invalid"))

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(
                {"query": "q", "context": "c", "generation": "g"}
            )

        assert result["faithfulness_grounded"] is False
        assert result["faithfulness_relevant"] is False


class TestRewriteNode:
    @pytest.mark.asyncio
    async def test_rewrites_query(self):
        from app.agents.chat.nodes.rewrite import rewrite_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content="What are the specific combat abilities of Randidly Ghosthound?"
            )
        )

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
            result = await rewrite_query(
                {
                    "query": "old",
                    "original_query": "original",
                    "faithfulness_reason": "bad",
                }
            )

        assert "original_query" not in result
