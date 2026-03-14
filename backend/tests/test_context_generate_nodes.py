"""Tests for context assembly and generate nodes."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


class TestContextAssemblyNode:
    @pytest.mark.asyncio
    async def test_builds_context_from_chunks_and_entities(self):
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            return_value=[
                {"name": "Jake", "label": "Character", "description": "Archer class"},
            ]
        )

        state = {
            "reranked_chunks": [
                {
                    "text": "Jake fired his bow.",
                    "chapter_number": 5,
                    "chapter_title": "Arena",
                    "relevance_score": 0.9,
                },
            ],
            "book_id": "b1",
            "max_chapter": 10,
        }

        result = await assemble_context(state, repo=mock_repo)
        assert "## Source Passages" in result["context"]
        assert "Chapter 5" in result["context"]
        assert "Jake" in result["context"]
        assert len(result["kg_entities"]) == 1

    @pytest.mark.asyncio
    async def test_empty_chunks_produces_minimal_context(self):
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        result = await assemble_context(
            {"reranked_chunks": [], "book_id": "b1", "max_chapter": None},
            repo=mock_repo,
        )
        assert result["context"] == ""
        assert result["kg_entities"] == []


class TestGenerateNode:
    @pytest.mark.asyncio
    async def test_generates_answer_with_context(self):
        from app.agents.chat.nodes.generate import generate_answer

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content="Jake is a level 88 Arcane Hunter [Ch.5]. He defeated the Hydra [Ch.5]."
            )
        )

        state = {
            "query": "Who is Jake?",
            "context": "## Source Passages\n### [1] Chapter 5\nJake is level 88.",
            "messages": [HumanMessage(content="Who is Jake?")],
            "max_chapter": None,
        }

        with patch("app.agents.chat.nodes.generate.get_langchain_llm", return_value=mock_llm):
            result = await generate_answer(state)

        assert "Jake" in result["generation"]
        assert len(result["citations"]) == 2
        assert result["citations"][0]["chapter"] == 5

    @pytest.mark.asyncio
    async def test_empty_context_returns_apology(self):
        from app.agents.chat.nodes.generate import generate_answer

        state = {
            "query": "test",
            "context": "",
            "messages": [HumanMessage(content="test")],
            "max_chapter": None,
        }

        result = await generate_answer(state)
        assert "couldn't find" in result["generation"].lower()

    def test_parse_citations(self):
        from app.agents.chat.nodes.generate import _parse_citations

        text = "Jake is level 88 [Ch.5]. He has Spear Mastery [Ch.12, p.3]."
        citations = _parse_citations(text)
        assert len(citations) == 2
        assert citations[0] == {"chapter": 5, "position": None}
        assert citations[1] == {"chapter": 12, "position": 3}
