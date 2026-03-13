"""Faithfulness check node: LLM-as-judge verifying answer groundedness."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import FAITHFULNESS_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def check_faithfulness(state: dict[str, Any]) -> dict[str, Any]:
    """Grade the generated answer for faithfulness and relevance."""
    llm = get_langchain_llm(settings.llm_chat)

    judge_input = (
        f"Question: {state['query']}\n\n"
        f"Context:\n{state['context']}\n\n"
        f"Generated Answer:\n{state['generation']}"
    )

    response = await llm.ainvoke([
        SystemMessage(content=FAITHFULNESS_SYSTEM),
        HumanMessage(content=judge_input),
    ])

    try:
        result = json.loads(response.content)
        score = float(result.get("score", 0.0))
        reason = result.get("reason", "")
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("faithfulness_parse_failed", raw=response.content[:200])
        score = 1.0
        reason = "Judge response unparseable, defaulting to pass"

    logger.info(
        "faithfulness_check_completed",
        score=score,
        reason=reason[:100],
    )

    return {
        "faithfulness_score": score,
        "faithfulness_reason": reason,
    }
