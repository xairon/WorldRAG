"""Rewrite query node: reformulate the query after failed retrieval/generation."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import REWRITE_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def rewrite_query(state: dict[str, Any]) -> dict[str, Any]:
    """Rewrite the query for a corrective retry."""
    llm = get_langchain_llm(settings.llm_chat)
    original = state.get("original_query", state["query"])
    reason = state.get("faithfulness_reason", "Results not relevant enough")

    rewrite_input = (
        f"Original question: {original}\n"
        f"Current query: {state['query']}\n"
        f"Failure reason: {reason}\n\n"
        f"Rewrite the query:"
    )

    response = await llm.ainvoke([
        SystemMessage(content=REWRITE_SYSTEM),
        HumanMessage(content=rewrite_input),
    ])

    new_query = response.content.strip()
    if not new_query:
        new_query = original

    logger.info(
        "query_rewritten",
        old=state["query"][:100],
        new=new_query[:100],
        reason=reason[:100],
    )

    return {
        "query": new_query,
        "retries": 1,  # Uses operator.add reducer → increments
    }
