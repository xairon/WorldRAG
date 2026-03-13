"""Query transform node: multi-query reformulation + optional HyDE."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import QUERY_TRANSFORM_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def transform_query(state: dict[str, Any]) -> dict[str, Any]:
    """Generate query reformulations for better retrieval recall."""
    llm = get_langchain_llm(settings.llm_chat)
    query = state["query"]

    messages = [
        SystemMessage(content=QUERY_TRANSFORM_SYSTEM),
        HumanMessage(content=query),
    ]

    response = await llm.ainvoke(messages)

    try:
        variants = json.loads(response.content)
        if not isinstance(variants, list) or not all(isinstance(v, str) for v in variants):
            raise ValueError("Expected list of strings")
    except (json.JSONDecodeError, ValueError):
        logger.warning("query_transform_parse_failed", raw=response.content[:200])
        variants = []

    # Always include the original query
    all_queries = [query] + [v for v in variants if v != query]

    logger.info("query_transform_completed", original=query, variants=len(variants))
    return {"transformed_queries": all_queries}
