"""Generate node: structured LLM answer generation with inline chapter citations.

Returns a GenerationOutput (stored as dict in state["generation_output"]).
state["generation"] is kept for backward compatibility (= answer text).

Uses GENERATOR_COT_SYSTEM for analytical and timeline_qa routes (chain-of-thought),
and GENERATOR_SYSTEM for all other routes.
"""

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.chat.prompts import (
    DIRECT_RESPONSE_SYSTEM,
    GENERATOR_COT_SYSTEM,
    GENERATOR_SYSTEM,
    SPOILER_GUARD,
)
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm
from app.schemas.chat import GenerationOutput

logger = get_logger(__name__)

_CITATION_PATTERN = re.compile(r"\[Ch\.(\d+)(?:,\s*p\.(\d+))?\]")
# Routes that use chain-of-thought prompting
_COT_ROUTES = {"analytical", "timeline_qa"}


def _parse_citations(text: str) -> list[dict[str, Any]]:
    """Extract [Ch.N] or [Ch.N, p.M] citations from generated text."""
    citations = []
    for match in _CITATION_PATTERN.finditer(text):
        chapter = int(match.group(1))
        position = int(match.group(2)) if match.group(2) else None
        citations.append({"chapter": chapter, "position": position})
    return citations


def _parse_generation_output(raw: str) -> GenerationOutput:
    """Parse structured JSON from LLM, with fallback to plain text extraction.

    The LLM is prompted to return JSON with {answer, citations, entities_mentioned}.
    If parsing fails, we extract the answer from the raw text and use regex citations.
    """
    # Try JSON parse
    try:
        # Strip markdown code blocks if present
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("` ")
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "answer" in parsed:
            citations_raw = parsed.get("citations", [])
            citations = []
            for c in citations_raw:
                if isinstance(c, dict) and "chapter" in c:
                    citations.append(
                        {
                            "chapter": int(c["chapter"]),
                            "position": c.get("position"),
                            "claim": c.get("claim", ""),
                            "source_span": c.get("source_span", ""),
                        }
                    )
            return GenerationOutput(
                answer=str(parsed["answer"]),
                citations=citations,
                entities_mentioned=[str(e) for e in parsed.get("entities_mentioned", [])],
            )
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: use raw text as answer, extract citations via regex
    return GenerationOutput(
        answer=raw.strip(),
        citations=[
            {"chapter": c["chapter"], "position": c.get("position"), "claim": "", "source_span": ""}
            for c in _parse_citations(raw)
        ],
    )


async def generate_answer(state: dict[str, Any]) -> dict[str, Any]:
    """Generate an answer from the assembled context.

    Uses CoT prompt for analytical and timeline_qa routes.
    Uses direct response prompt for conversational route (no context needed).
    Returns both structured generation_output and plain generation for compat.
    """
    context = state.get("context", "")
    query = state["query"]
    max_chapter = state.get("max_chapter")
    route = state.get("route", "entity_qa")

    # Conversational route: lightweight response without context
    if route in ("direct", "conversational"):
        llm = get_langchain_llm(settings.llm_chat)
        response = await llm.ainvoke(
            [
                SystemMessage(content=DIRECT_RESPONSE_SYSTEM),
                HumanMessage(content=query),
            ]
        )
        answer = response.content if isinstance(response.content, str) else str(response.content)
        output = GenerationOutput(answer=answer)
        return {
            "generation": answer,
            "generation_output": output.model_dump(),
            "citations": [],
            "messages": [AIMessage(content=answer)],
        }

    if not context:
        answer = (
            "I couldn't find any relevant content for your question. "
            "Try rephrasing or asking about something more specific."
        )
        output = GenerationOutput(answer=answer)
        return {
            "generation": answer,
            "generation_output": output.model_dump(),
            "citations": [],
        }

    # Build system prompt: CoT for complex routes, standard for others
    spoiler_text = SPOILER_GUARD.format(max_chapter=max_chapter) if max_chapter else ""
    if route in _COT_ROUTES:
        system_prompt = GENERATOR_COT_SYSTEM.format(spoiler_guard=spoiler_text)
    else:
        system_prompt = GENERATOR_SYSTEM.format(spoiler_guard=spoiler_text)

    llm = get_langchain_llm(settings.llm_generation)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"{context}\n\n---\n\nQuestion: {query}"),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content if isinstance(response.content, str) else str(response.content)

    output = _parse_generation_output(raw)

    # Backward-compat simple citations (chapter + position only)
    simple_citations = [
        {"chapter": c.chapter, "position": c.position} for c in output.citations
    ]

    logger.info(
        "generate_completed",
        route=route,
        answer_len=len(output.answer),
        citation_count=len(output.citations),
        entities_count=len(output.entities_mentioned),
        cot=route in _COT_ROUTES,
    )

    return {
        "generation": output.answer,
        "generation_output": output.model_dump(),
        "citations": simple_citations,
        "messages": [AIMessage(content=output.answer)],
    }
