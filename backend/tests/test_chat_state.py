"""Tests for ChatAgentState schema."""

import operator

from langgraph.graph.message import add_messages

from app.agents.chat.state import ChatAgentState


def test_state_has_required_keys():
    """ChatAgentState defines all required keys."""
    hints = ChatAgentState.__annotations__
    required = [
        "messages",
        "original_query",
        "query",
        "route",
        "transformed_queries",
        "fused_results",
        "reranked_chunks",
        "kg_entities",
        "kg_cypher_result",
        "context",
        "generation",
        "citations",
        "faithfulness_score",
        "faithfulness_reason",
        "faithfulness_grounded",
        "faithfulness_relevant",
        "faithfulness_passed",
        "retries",
        # memory fields (Chunk 2)
        "conversation_summary",
        "entity_memory",
        "turn_count",
        # query expansion (Chunk 2)
        "hyde_document",
        "sub_questions",
        # retrieval (Chunk 2)
        "deduplicated_chunks",
        "book_id",
        "max_chapter",
    ]
    for key in required:
        assert key in hints, f"Missing state key: {key}"


def test_state_is_total_false():
    """State uses total=False so nodes can return partial updates."""
    assert ChatAgentState.__total__ is False


def test_messages_uses_add_messages_reducer():
    """The messages field uses LangGraph's add_messages reducer."""
    from typing import get_type_hints

    hints = get_type_hints(ChatAgentState, include_extras=True)
    msg_hint = hints["messages"]
    assert hasattr(msg_hint, "__metadata__")
    assert msg_hint.__metadata__[0] is add_messages


def test_retries_uses_operator_add():
    """The retries field uses operator.add reducer for increment."""
    from typing import get_type_hints

    hints = get_type_hints(ChatAgentState, include_extras=True)
    retries_hint = hints["retries"]
    assert hasattr(retries_hint, "__metadata__")
    assert retries_hint.__metadata__[0] is operator.add


from app.schemas.chat import ChatRequest, ChatResponse, Citation


def test_chat_request_has_thread_id():
    req = ChatRequest(query="test", book_id="b1")
    assert req.thread_id is None
    req2 = ChatRequest(query="test", book_id="b1", thread_id="t-123")
    assert req2.thread_id == "t-123"


def test_chat_response_has_thread_id():
    resp = ChatResponse(answer="hi", thread_id="t-123")
    assert resp.thread_id == "t-123"


def test_citation_model():
    c = Citation(chapter=5)
    assert c.chapter == 5
    assert c.position is None
    c2 = Citation(chapter=5, position=3)
    assert c2.position == 3
