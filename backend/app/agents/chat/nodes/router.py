"""Intent analyzer node: classifies user query into one of 6 routes.

Routes:
  factual_lookup  — direct entity attribute/stat lookup via KG
  entity_qa       — entity profile Q requiring passage evidence
  relationship_qa — inter-entity relationship questions
  timeline_qa     — chronological / event-sequence questions
  analytical      — complex, multi-part, synthesis questions
  conversational  — greetings, meta, out-of-scope (no retrieval needed)
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import INTENT_ANALYZER_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

VALID_ROUTES = {
    "factual_lookup",
    "entity_qa",
    "relationship_qa",
    "timeline_qa",
    "analytical",
    "conversational",
}

_FALLBACK_ROUTE = "entity_qa"


async def classify_intent(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the user's query intent for 6-route dispatch.

    Uses llm_auxiliary (local Qwen3.5-4B by default) for fast, free inference.
    Includes recent conversation history so the classifier can resolve
    co-references and follow-up questions correctly.

    Returns {"route": <one of VALID_ROUTES>}.
    """
    llm = get_langchain_llm(settings.llm_auxiliary)

    messages: list = [SystemMessage(content=INTENT_ANALYZER_SYSTEM)]

    # Include up to 4 prior turns for context resolution
    history = state.get("messages", [])
    if len(history) > 2:
        for msg in history[-5:-1]:
            messages.append(msg)

    messages.append(HumanMessage(content=state["query"]))

    response = await llm.ainvoke(messages)
    raw = response.content.strip() if isinstance(response.content, str) else str(response.content)

    route = _parse_route(raw)
    logger.info("intent_classified", route=route, query_len=len(state["query"]))
    return {"route": route}


def _parse_route(raw: str) -> str:
    """Parse the LLM response and return a valid route name.

    Accepts:
    - JSON object: {"route": "factual_lookup"}
    - Plain route name as fallback
    """
    # Try JSON parse
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            candidate = str(parsed.get("route", "")).strip().lower()
            if candidate in VALID_ROUTES:
                return candidate
    except (json.JSONDecodeError, ValueError):
        pass

    # Try plain text match (model may ignore JSON instruction)
    candidate = raw.strip().lower()
    if candidate in VALID_ROUTES:
        return candidate

    # Partial match: return first valid route found in response
    for route in VALID_ROUTES:
        if route in candidate:
            return route

    logger.warning("intent_parse_failed", raw=raw[:200], defaulting=_FALLBACK_ROUTE)
    return _FALLBACK_ROUTE
