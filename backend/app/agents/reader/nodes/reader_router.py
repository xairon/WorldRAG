"""Reader agent router: classifies question intent."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.reader.prompts import READER_ROUTER_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def classify_reader_intent(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the reader's question into a route."""
    llm = get_langchain_llm(settings.llm_chat)
    query = state.get("query") or state["messages"][-1].content

    response = await llm.ainvoke(
        [
            SystemMessage(content=READER_ROUTER_SYSTEM),
            HumanMessage(content=query),
        ]
    )

    try:
        parsed = json.loads(response.content)
        route = parsed.get("route", "context_qa")
        if route not in ("context_qa", "entity_lookup", "summarize"):
            route = "context_qa"
    except (json.JSONDecodeError, KeyError):
        logger.warning("reader_router_parse_failed", raw=str(response.content)[:200])
        route = "context_qa"

    logger.info("reader_route_classified", route=route, chapter=state.get("chapter_number"))
    return {"route": route, "query": query}
