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
    """Classify the user's question intent for routing."""
    llm = get_langchain_llm(settings.llm_chat)

    messages = [
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=state["query"]),
    ]

    response = await llm.ainvoke(messages)
    route = response.content.strip().lower()

    if route not in VALID_ROUTES:
        logger.warning("router_unknown_route", raw=route, defaulting="hybrid_rag")
        route = "hybrid_rag"

    logger.info("router_classified", route=route, query_len=len(state["query"]))
    return {"route": route}
