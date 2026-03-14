"""Memory nodes: load and summarize conversation history for multi-turn chat.

load_memory  — runs at graph START each turn; sets turn_count, initializes defaults.
summarize_memory — runs before END every 5 turns; compresses history via aux LLM.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import SUMMARIZE_MEMORY_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

# Sliding window: how many recent messages to pass to summarizer
_SUMMARY_WINDOW = 20  # last 10 turns (human + AI)
# Summarize every N completed turns
_SUMMARY_EVERY_N = 5


async def load_memory(state: dict[str, Any]) -> dict[str, Any]:
    """Load and initialize conversation memory at the start of each turn.

    - Counts completed human turns from message history.
    - Initializes entity_memory and conversation_summary on first turn.

    Does NOT trim messages — the add_messages reducer manages the full history.
    Nodes that need a windowed view can slice state["messages"][-N:].
    """
    messages = state.get("messages", [])

    # Count human messages to determine current turn (includes the new message)
    turn_count = sum(1 for m in messages if getattr(m, "type", "") == "human")

    updates: dict[str, Any] = {"turn_count": turn_count}

    if not state.get("entity_memory"):
        updates["entity_memory"] = []

    if not state.get("conversation_summary"):
        updates["conversation_summary"] = ""

    logger.info(
        "memory_loaded",
        turn_count=turn_count,
        has_summary=bool(state.get("conversation_summary")),
        entity_count=len(state.get("entity_memory") or []),
    )
    return updates


async def summarize_memory(state: dict[str, Any]) -> dict[str, Any]:
    """Compress recent conversation history into a summary every N turns.

    No-op unless turn_count is a positive multiple of _SUMMARY_EVERY_N.
    Uses llm_auxiliary (Qwen3.5-4B via Ollama by default) for compression.
    Failures are silently swallowed — memory summarization is best-effort.
    """
    turn_count = state.get("turn_count", 0)
    if turn_count == 0 or turn_count % _SUMMARY_EVERY_N != 0:
        return {}

    messages = state.get("messages", [])
    if not messages:
        return {}

    # Build history text from the last _SUMMARY_WINDOW messages
    window = messages[-_SUMMARY_WINDOW:]
    history_lines: list[str] = []
    for m in window:
        role = "User" if getattr(m, "type", "") == "human" else "Assistant"
        content = m.content if isinstance(m.content, str) else str(m.content)
        history_lines.append(f"{role}: {content[:500]}")
    history_text = "\n".join(history_lines)

    existing_summary = state.get("conversation_summary", "")
    if existing_summary:
        prompt = f"Previous summary:\n{existing_summary}\n\n---\n\nRecent conversation:\n{history_text}"
    else:
        prompt = history_text

    try:
        llm = get_langchain_llm(settings.llm_auxiliary)
        response = await llm.ainvoke(
            [
                SystemMessage(content=SUMMARIZE_MEMORY_SYSTEM),
                HumanMessage(content=prompt),
            ]
        )
        summary = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
        logger.info("memory_summarized", turn_count=turn_count, summary_len=len(summary))
        return {"conversation_summary": summary}
    except Exception:  # noqa: BLE001 — best-effort, must not crash the pipeline
        logger.warning("memory_summarize_failed", turn_count=turn_count, exc_info=True)
        return {}
