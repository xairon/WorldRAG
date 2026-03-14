"""Router node: classifies user intent into kg_query / hybrid_rag / direct."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import ROUTER_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

VALID_ROUTES = {"kg_query", "hybrid_rag", "direct"}


async def classify_intent(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the user's question intent for routing.

    Includes conversation history (if any) so the router can resolve
    context in multi-turn conversations (C3 audit fix).
    """
    llm = get_langchain_llm(settings.llm_chat)

    # Build messages: system + optional conversation history + current query
    messages: list = [SystemMessage(content=ROUTER_SYSTEM)]

    # Include recent conversation history for multi-turn context (N7 fix)
    history = state.get("messages", [])
    if len(history) > 2:
        # Include up to 4 prior turns, excluding the last message (current query)
        # and the one before it on 2-message conversations to avoid duplicate
        for msg in history[-5:-1]:
            messages.append(msg)

    messages.append(HumanMessage(content=state["query"]))

    response = await llm.ainvoke(messages)
    route = response.content.strip().lower()

    if route not in VALID_ROUTES:
        logger.warning("router_unknown_route", raw=route, defaulting="hybrid_rag")
        route = "hybrid_rag"

    logger.info("router_classified", route=route, query_len=len(state["query"]))
    return {"route": route}
