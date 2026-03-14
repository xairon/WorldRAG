"""Tests for the NLI faithfulness check and rewrite query nodes."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from langchain_core.messages import AIMessage


def _nli_mock(scores_per_pair: list[list[float]]):
    """Build a mock NLI CrossEncoder whose predict() returns given logits.

    scores_per_pair: list of [contradiction, entailment, neutral] logits per pair.
    """
    mock = MagicMock()
    mock.predict = MagicMock(return_value=np.array(scores_per_pair))
    return mock


# High entailment logits → entailment prob ~ 1
_ENTAIL_HIGH = [-10.0, 10.0, -10.0]
# High contradiction logits → contradiction prob ~ 1
_CONTRA_HIGH = [10.0, -10.0, -10.0]
# Equal logits → uniform distribution (~neutral)
_NEUTRAL = [0.0, 0.0, 0.0]


class TestFaithfulnessNode:
    @pytest.mark.asyncio
    async def test_grounded_answer_passes(self):
        """High entailment logits → high score → passes threshold."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        state = {
            "query": "Who is Jake?",
            "context": "Jake is an Arcane Hunter.",
            "generation": "Jake is an Arcane Hunter and a skilled fighter.",
            "route": "entity_qa",
        }

        with patch(
            "app.agents.chat.nodes.faithfulness.get_nli_model",
            return_value=_nli_mock([_ENTAIL_HIGH, _ENTAIL_HIGH]),
        ):
            result = await check_faithfulness(state)

        assert result["faithfulness_score"] > 0.9
        assert result["faithfulness_passed"] is True
        assert result["faithfulness_grounded"] is True

    @pytest.mark.asyncio
    async def test_contradicted_answer_fails(self):
        """High contradiction logits → low score → fails and sets has_contradiction."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        state = {
            "query": "What level is Jake?",
            "context": "Jake is an Arcane Hunter.",
            "generation": "Jake is level 200 and the most powerful being.",
            "route": "factual_lookup",
        }

        with patch(
            "app.agents.chat.nodes.faithfulness.get_nli_model",
            return_value=_nli_mock([_CONTRA_HIGH, _CONTRA_HIGH]),
        ):
            result = await check_faithfulness(state)

        assert result["faithfulness_score"] < 0.3
        assert result["faithfulness_passed"] is False
        assert result["faithfulness_grounded"] is False

    @pytest.mark.asyncio
    async def test_nli_failure_defaults_to_neutral_score(self):
        """NLI model error → fallback to 0.5 score, not crash."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_nli = MagicMock()
        mock_nli.predict = MagicMock(side_effect=RuntimeError("CUDA OOM"))

        with patch("app.agents.chat.nodes.faithfulness.get_nli_model", return_value=mock_nli):
            result = await check_faithfulness(
                {
                    "query": "test",
                    "context": "ctx",
                    "generation": "some answer about the context.",
                    "route": "entity_qa",
                }
            )

        assert result["faithfulness_score"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_returns_grounded_and_relevant_booleans(self):
        """Result always contains faithfulness_grounded and faithfulness_relevant."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        with patch(
            "app.agents.chat.nodes.faithfulness.get_nli_model",
            return_value=_nli_mock([_ENTAIL_HIGH]),
        ):
            result = await check_faithfulness(
                {
                    "query": "q",
                    "context": "c",
                    "generation": "Jake is an Arcane Hunter.",
                    "route": "entity_qa",
                }
            )

        assert "faithfulness_grounded" in result
        assert "faithfulness_relevant" in result
        assert "faithfulness_passed" in result

    @pytest.mark.asyncio
    async def test_empty_generation_fails(self):
        """Empty generation with no claims → score 0.0, not passed."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        result = await check_faithfulness(
            {"query": "q", "context": "c", "generation": "", "route": "entity_qa"}
        )

        assert result["faithfulness_score"] == 0.0
        assert result["faithfulness_passed"] is False

    @pytest.mark.asyncio
    async def test_conversational_route_always_passes(self):
        """Conversational route skips NLI check and always passes."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        result = await check_faithfulness(
            {"query": "Hello", "context": "", "generation": "Hi there!", "route": "conversational"}
        )

        assert result["faithfulness_passed"] is True
        assert result["faithfulness_score"] == 1.0

    @pytest.mark.asyncio
    async def test_adaptive_threshold_factual_is_stricter(self):
        """factual_lookup threshold 0.8 is stricter than analytical 0.5."""
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        # Neutral score (0.5 * each claim) = just above analytical threshold,
        # but below factual_lookup threshold
        with patch(
            "app.agents.chat.nodes.faithfulness.get_nli_model",
            return_value=_nli_mock([_NEUTRAL, _NEUTRAL]),
        ):
            result_factual = await check_faithfulness(
                {
                    "query": "q",
                    "context": "ctx",
                    "generation": "Jake is a hunter. He has skills.",
                    "route": "factual_lookup",
                }
            )
            result_analytical = await check_faithfulness(
                {
                    "query": "q",
                    "context": "ctx",
                    "generation": "Jake is a hunter. He has skills.",
                    "route": "analytical",
                }
            )

        # Neutral score is ~0.5 which passes analytical (0.5) but not factual (0.8)
        # (equal logits softmax to 0.333 each → score = 0.333*1 + 0.333*0.5 = 0.5)
        assert result_factual["faithfulness_passed"] is False
        assert result_analytical["faithfulness_passed"] is True


class TestRewriteNode:
    @pytest.mark.asyncio
    async def test_rewrites_query(self):
        from app.agents.chat.nodes.rewrite import rewrite_query

        mock_llm = MagicMock()
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

        mock_llm = MagicMock()
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
