"""Generate node: LLM answer generation with inline chapter citations."""

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.chat.prompts import GENERATOR_SYSTEM, SPOILER_GUARD
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

_CITATION_PATTERN = re.compile(r"\[Ch\.(\d+)(?:,\s*p\.(\d+))?\]")


def _parse_citations(text: str) -> list[dict[str, Any]]:
    """Extract [Ch.N] or [Ch.N, p.M] citations from generated text."""
    citations = []
    for match in _CITATION_PATTERN.finditer(text):
        chapter = int(match.group(1))
        position = int(match.group(2)) if match.group(2) else None
        citations.append({"chapter": chapter, "position": position})
    return citations


async def generate_answer(state: dict[str, Any]) -> dict[str, Any]:
    """Generate an answer from the assembled context."""
    context = state.get("context", "")
    query = state["query"]
    max_chapter = state.get("max_chapter")

    if not context:
        return {
            "generation": "I couldn't find any relevant content for your question. "
            "Try rephrasing or asking about something more specific.",
            "citations": [],
        }

    # Build system prompt with optional spoiler guard
    spoiler_text = ""
    if max_chapter is not None:
        spoiler_text = SPOILER_GUARD.format(max_chapter=max_chapter)
    system_prompt = GENERATOR_SYSTEM.format(spoiler_guard=spoiler_text)

    llm = get_langchain_llm(settings.llm_chat)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"{context}\n\n---\n\nQuestion: {query}"),
    ]

    response = await llm.ainvoke(messages)
    answer = response.content if isinstance(response.content, str) else str(response.content)

    citations = _parse_citations(answer)

    logger.info(
        "generate_completed",
        answer_len=len(answer),
        citation_count=len(citations),
    )

    return {
        "generation": answer,
        "citations": citations,
        "messages": [AIMessage(content=answer)],
    }
