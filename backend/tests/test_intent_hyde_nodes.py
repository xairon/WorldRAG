"""Unit tests for the 6-route intent classifier and HyDE expansion node."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.chat.nodes.hyde import _HYDE_ROUTES, hyde_expand
from app.agents.chat.nodes.router import VALID_ROUTES, _parse_route, classify_intent

# ---------------------------------------------------------------------------
# _parse_route unit tests
# ---------------------------------------------------------------------------


def test_parse_route_valid_json():
    assert _parse_route('{"route": "factual_lookup"}') == "factual_lookup"
    assert _parse_route('{"route": "analytical"}') == "analytical"


def test_parse_route_plain_text():
    for route in VALID_ROUTES:
        assert _parse_route(route) == route


def test_parse_route_partial_match():
    assert _parse_route("I think timeline_qa fits") == "timeline_qa"


def test_parse_route_unknown_falls_back():
    result = _parse_route("completely unknown output")
    assert result in VALID_ROUTES  # fallback is valid


def test_parse_route_json_wrong_value_falls_back():
    result = _parse_route('{"route": "nonexistent_route"}')
    assert result in VALID_ROUTES


def test_parse_route_all_valid_routes_accepted():
    for route in VALID_ROUTES:
        assert _parse_route(f'{{"route": "{route}"}}') == route


# ---------------------------------------------------------------------------
# classify_intent integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_intent_returns_valid_route():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"route": "factual_lookup"}'))

    with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
        result = await classify_intent(
            {
                "query": "What level is Jake?",
                "messages": [HumanMessage(content="What level is Jake?")],
            }
        )

    assert result["route"] == "factual_lookup"


@pytest.mark.asyncio
async def test_classify_intent_includes_history_for_context():
    """Classifier receives conversation history when > 2 messages exist."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"route": "relationship_qa"}'))

    history = [
        HumanMessage(content="Who is Jake?"),
        AIMessage(content="Jake is the main character."),
        HumanMessage(content="How are they related?"),
    ]

    with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
        result = await classify_intent({"query": "How are they related?", "messages": history})

    # LLM was called with messages (system + history + query)
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert len(call_args) >= 3
    assert result["route"] == "relationship_qa"


@pytest.mark.asyncio
async def test_classify_intent_fallback_on_bad_response():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="gibberish text here"))

    with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
        result = await classify_intent({"query": "test", "messages": []})

    assert result["route"] in VALID_ROUTES


# ---------------------------------------------------------------------------
# hyde_expand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hyde_expand_returns_document_for_hyde_routes():
    for route in _HYDE_ROUTES:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="Jake reached level 10 in Chapter 5.")
        )

        with patch("app.agents.chat.nodes.hyde.get_langchain_llm", return_value=mock_llm):
            result = await hyde_expand({"route": route, "query": "What level is Jake?"})

        assert "hyde_document" in result
        assert result["hyde_document"] == "Jake reached level 10 in Chapter 5."


@pytest.mark.asyncio
async def test_hyde_expand_skips_factual_lookup():
    result = await hyde_expand({"route": "factual_lookup", "query": "What level is Jake?"})
    assert result == {}


@pytest.mark.asyncio
async def test_hyde_expand_skips_conversational():
    result = await hyde_expand({"route": "conversational", "query": "Hello!"})
    assert result == {}


@pytest.mark.asyncio
async def test_hyde_expand_skips_empty_query():
    result = await hyde_expand({"route": "entity_qa", "query": ""})
    assert result == {}


@pytest.mark.asyncio
async def test_hyde_expand_swallows_llm_error():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with patch("app.agents.chat.nodes.hyde.get_langchain_llm", return_value=mock_llm):
        result = await hyde_expand({"route": "entity_qa", "query": "Who is Jake?"})

    assert result == {}
