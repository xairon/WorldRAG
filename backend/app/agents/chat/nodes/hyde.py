"""HyDE (Hypothetical Document Embeddings) expansion node.

Generates a short hypothetical passage that would answer the user's question,
to be used as an additional dense retrieval vector alongside the query variants.

Only activated for entity_qa, relationship_qa, timeline_qa, and analytical routes.
Skipped for factual_lookup and conversational.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import HYDE_EXPAND_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

_HYDE_ROUTES = {"entity_qa", "relationship_qa", "timeline_qa", "analytical"}


async def hyde_expand(state: dict[str, Any]) -> dict[str, Any]:
    """Generate a hypothetical document for HyDE dense retrieval.

    Uses llm_auxiliary (Qwen3.5-4B by default) for fast local generation.
    Returns {"hyde_document": "<passage>"} on success, {} on skip/error.

    The hyde_document is consumed by retrieve_multi (Task 9) as an extra
    embedding vector to improve recall for non-factual questions.
    """
    route = state.get("route", "")
    if route not in _HYDE_ROUTES:
        logger.debug("hyde_skipped", route=route)
        return {}

    query = state.get("query", "")
    if not query:
        return {}

    try:
        llm = get_langchain_llm(settings.llm_auxiliary)
        response = await llm.ainvoke(
            [
                SystemMessage(content=HYDE_EXPAND_SYSTEM),
                HumanMessage(content=query),
            ]
        )
        doc = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
        logger.info("hyde_expanded", route=route, doc_len=len(doc))
        return {"hyde_document": doc}
    except Exception:  # noqa: BLE001 — HyDE failure is non-fatal
        logger.warning("hyde_expand_failed", route=route, exc_info=True)
        return {}
