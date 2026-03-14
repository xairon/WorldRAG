"""Reader agent generate: produce answer from chapter context."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.reader.prompts import READER_ENTITY_SYSTEM, READER_GENERATE_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def generate_reader_answer(state: dict[str, Any]) -> dict[str, Any]:
    """Generate an answer using chapter paragraphs and entity context."""
    llm = get_langchain_llm(settings.llm_chat)
    query = state["query"]
    route = state.get("route", "context_qa")
    paragraphs = state.get("paragraph_context", [])
    kg_context = state.get("kg_context", "")
    max_chapter = state.get("max_chapter")
    chapter_number = state.get("chapter_number", 0)

    # Build spoiler guard instruction
    spoiler_guard = ""
    if max_chapter is not None:
        spoiler_guard = (
            f"SPOILER GUARD: The reader has read up to chapter {max_chapter}. "
            f"Do NOT reveal any information from chapters after {max_chapter}."
        )

    # Build context based on route
    if route == "entity_lookup" and kg_context:
        system_prompt = READER_ENTITY_SYSTEM.format(spoiler_guard=spoiler_guard)
        context_text = f"## Entity Knowledge Graph\n\n{kg_context}"
    else:
        system_prompt = READER_GENERATE_SYSTEM.format(spoiler_guard=spoiler_guard)
        para_lines = []
        for p in paragraphs:
            idx = p.get("index", 0)
            ptype = p.get("type", "narration")
            text = p.get("text", "")
            speaker = p.get("speaker")
            prefix = f"[Para.{idx}] ({ptype})"
            if speaker:
                prefix += f" [{speaker}]"
            para_lines.append(f"{prefix}: {text}")
        context_text = f"## Chapter {chapter_number} Paragraphs\n\n" + "\n\n".join(para_lines)

        if kg_context:
            context_text += f"\n\n## Entity Context\n\n{kg_context}"

    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"{context_text}\n\n---\n\nQuestion: {query}"),
        ]
    )

    generation = response.content if isinstance(response.content, str) else str(response.content)

    logger.info(
        "reader_answer_generated",
        route=route,
        chapter=chapter_number,
        answer_len=len(generation),
    )

    return {"generation": generation}
