"""Unit tests for memory nodes: load_memory and summarize_memory."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.chat.nodes.memory import _SUMMARY_EVERY_N, load_memory, summarize_memory


# ---------------------------------------------------------------------------
# load_memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_memory_counts_turns_from_messages():
    messages = [
        HumanMessage(content="q1"),
        AIMessage(content="a1"),
        HumanMessage(content="q2"),
        AIMessage(content="a2"),
        HumanMessage(content="q3"),
    ]
    result = await load_memory({"messages": messages})
    assert result["turn_count"] == 3


@pytest.mark.asyncio
async def test_load_memory_first_turn_initializes_defaults():
    result = await load_memory({"messages": [HumanMessage(content="hi")]})
    assert result["turn_count"] == 1
    assert result["entity_memory"] == []
    assert result["conversation_summary"] == ""


@pytest.mark.asyncio
async def test_load_memory_does_not_overwrite_existing_memory():
    state = {
        "messages": [HumanMessage(content="q1"), AIMessage(content="a1")],
        "entity_memory": [{"name": "Jake", "label": "Character"}],
        "conversation_summary": "Jake is a hunter.",
    }
    result = await load_memory(state)
    assert result["turn_count"] == 1
    # existing values preserved (not overwritten by load_memory)
    assert "entity_memory" not in result
    assert "conversation_summary" not in result


@pytest.mark.asyncio
async def test_load_memory_empty_messages():
    result = await load_memory({"messages": []})
    assert result["turn_count"] == 0


# ---------------------------------------------------------------------------
# summarize_memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_memory_noop_wrong_turn():
    """No-op when turn_count is not a multiple of _SUMMARY_EVERY_N."""
    for turn in [1, 2, 3, 4, 6, 7, 8, 9]:
        result = await summarize_memory({"turn_count": turn, "messages": []})
        assert result == {}, f"Expected no-op at turn {turn}"


@pytest.mark.asyncio
async def test_summarize_memory_noop_turn_zero():
    result = await summarize_memory({"turn_count": 0, "messages": []})
    assert result == {}


@pytest.mark.asyncio
async def test_summarize_memory_noop_empty_messages():
    result = await summarize_memory({"turn_count": _SUMMARY_EVERY_N, "messages": []})
    assert result == {}


@pytest.mark.asyncio
async def test_summarize_memory_calls_aux_llm():
    """summarize_memory calls get_langchain_llm and returns the summary."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Jake is a hunter who reached level 10."
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    messages = [
        HumanMessage(content="Who is Jake?"),
        AIMessage(content="Jake is a hunter."),
    ] * 5  # 5 human messages → turn_count=5

    with patch("app.agents.chat.nodes.memory.get_langchain_llm", return_value=mock_llm):
        result = await summarize_memory(
            {
                "turn_count": _SUMMARY_EVERY_N,
                "messages": messages,
                "conversation_summary": "",
            }
        )

    assert result == {"conversation_summary": "Jake is a hunter who reached level 10."}
    mock_llm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_summarize_memory_includes_existing_summary_in_prompt():
    """When a prior summary exists, it's included in the LLM prompt."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Updated summary."
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    messages = [HumanMessage(content="new question"), AIMessage(content="new answer")] * 5

    with patch("app.agents.chat.nodes.memory.get_langchain_llm", return_value=mock_llm):
        result = await summarize_memory(
            {
                "turn_count": _SUMMARY_EVERY_N,
                "messages": messages,
                "conversation_summary": "Prior summary here.",
            }
        )

    assert result == {"conversation_summary": "Updated summary."}
    # Verify the prompt included the existing summary
    call_args = mock_llm.ainvoke.call_args[0][0]
    human_msg = call_args[1]
    assert "Prior summary" in human_msg.content


@pytest.mark.asyncio
async def test_summarize_memory_swallows_llm_error():
    """If the LLM call fails, summarize_memory returns {} without raising."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("Ollama unavailable"))

    messages = [HumanMessage(content="q"), AIMessage(content="a")] * 5

    with patch("app.agents.chat.nodes.memory.get_langchain_llm", return_value=mock_llm):
        result = await summarize_memory(
            {
                "turn_count": _SUMMARY_EVERY_N,
                "messages": messages,
                "conversation_summary": "",
            }
        )

    assert result == {}
