"""Tests for individual chat agent nodes."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


class TestRouterNode:
    """Tests for the router node."""

    @pytest.mark.asyncio
    async def test_routes_entity_question_to_factual_lookup(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content='{"route": "factual_lookup"}')
        )

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent(
                {
                    "messages": [HumanMessage(content="Who is Randidly?")],
                    "original_query": "Who is Randidly?",
                    "query": "Who is Randidly?",
                    "book_id": "b1",
                }
            )

        assert result["route"] == "factual_lookup"

    @pytest.mark.asyncio
    async def test_routes_narrative_to_analytical(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content='{"route": "analytical"}')
        )

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent(
                {
                    "messages": [HumanMessage(content="Why did Jake betray the guild?")],
                    "original_query": "Why did Jake betray the guild?",
                    "query": "Why did Jake betray the guild?",
                    "book_id": "b1",
                }
            )

        assert result["route"] == "analytical"

    @pytest.mark.asyncio
    async def test_routes_greeting_to_conversational(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content='{"route": "conversational"}')
        )

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent(
                {
                    "messages": [HumanMessage(content="Hello!")],
                    "original_query": "Hello!",
                    "query": "Hello!",
                    "book_id": "b1",
                }
            )

        assert result["route"] == "conversational"

    @pytest.mark.asyncio
    async def test_defaults_to_entity_qa_on_unknown(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="something_weird"))

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent(
                {
                    "messages": [HumanMessage(content="test")],
                    "original_query": "test",
                    "query": "test",
                    "book_id": "b1",
                }
            )

        assert result["route"] == "entity_qa"


class TestQueryTransformNode:
    """Tests for the query transform node."""

    @pytest.mark.asyncio
    async def test_generates_multiple_queries(self):
        from app.agents.chat.nodes.query_transform import transform_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content='["What class does Randidly have?", "Randidly character class", "Randidly Ghosthound class type"]'
            )
        )

        with patch(
            "app.agents.chat.nodes.query_transform.get_langchain_llm", return_value=mock_llm
        ):
            result = await transform_query(
                {
                    "query": "What is Randidly's class?",
                    "book_id": "b1",
                }
            )

        assert len(result["transformed_queries"]) >= 3
        assert result["transformed_queries"][0] == "What is Randidly's class?"

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(self):
        from app.agents.chat.nodes.query_transform import transform_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="not json"))

        with patch(
            "app.agents.chat.nodes.query_transform.get_langchain_llm", return_value=mock_llm
        ):
            result = await transform_query(
                {
                    "query": "test query",
                    "book_id": "b1",
                }
            )

        assert result["transformed_queries"] == ["test query"]
