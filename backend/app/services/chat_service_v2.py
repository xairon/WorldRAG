"""Chat v2 service — Graphiti-based RAG pipeline.

Thin wrapper around the ChatV2 LangGraph. Responsible for:
- Compiling the graph with optional checkpointer.
- Mapping user inputs into graph state.
- Mapping graph output state back to ``ChatResponse``.
- Providing an SSE streaming interface via ``query_stream``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessageChunk, HumanMessage

from app.agents.chat_v2.graph import build_chat_v2_graph
from app.core.logging import get_logger
from app.schemas.chat import ChatResponse

logger = get_logger(__name__)


class ChatServiceV2:
    """Graphiti-backed chat service using the v2 LangGraph pipeline.

    Args:
        graphiti: A :class:`~app.core.graphiti_client.GraphitiClient` instance.
        neo4j_driver: An async Neo4j driver instance.
        checkpointer: Optional LangGraph checkpointer for multi-turn memory.
    """

    def __init__(
        self,
        graphiti: Any,
        neo4j_driver: Any,
        checkpointer: Any = None,
    ) -> None:
        builder = build_chat_v2_graph(graphiti=graphiti, neo4j_driver=neo4j_driver)
        self._graph = builder.compile(checkpointer=checkpointer)

    async def query(
        self,
        query: str,
        book_id: str,
        saga_id: str,
        *,
        max_chapter: int | None = None,
        thread_id: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Run the full Graphiti RAG pipeline and return a ``ChatResponse``.

        Args:
            query: User question.
            book_id: Book to scope the search to.
            saga_id: Saga / group identifier for Graphiti.
            max_chapter: Spoiler guard — only search up to this chapter.
            thread_id: Conversation thread ID for multi-turn support.
            **kwargs: Ignored; kept for API-level backward compatibility.

        Returns:
            ``ChatResponse`` populated from the final graph state.
        """
        state_input: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "original_query": query,
            "book_id": book_id,
            "saga_id": saga_id,
            "max_chapter": max_chapter,
            "retries": 0,
        }

        config: dict[str, Any] = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        logger.info(
            "chat_v2_query_start",
            book_id=book_id,
            saga_id=saga_id,
            query_len=len(query),
            thread_id=thread_id,
        )

        result = await self._graph.ainvoke(state_input, config=config)

        answer: str = (
            result.get("generation") or "I wasn't able to generate an answer."
        )
        context: list[Any] = result.get("retrieved_context", [])

        logger.info(
            "chat_v2_query_done",
            book_id=book_id,
            context_count=len(context),
            faithfulness_score=result.get("faithfulness_score"),
        )

        return ChatResponse(
            answer=answer,
            sources=[],
            related_entities=[],
            chunks_retrieved=len(context),
            chunks_after_rerank=len(context),
            thread_id=thread_id,
            citations=[],
            confidence=result.get("faithfulness_score", 0.0),
            entities_mentioned=[],
        )

    async def query_stream(
        self,
        query: str,
        book_id: str,
        saga_id: str,
        *,
        max_chapter: int | None = None,
        thread_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, str], None]:
        """Stream the v2 pipeline as SSE events via LangGraph ``astream``.

        Yields dicts with ``"event"`` and ``"data"`` keys:
          - ``{"event": "step", "data": <json step info>}``
          - ``{"event": "token", "data": {"token": "..."}}``
          - ``{"event": "done", "data": "{}"}``
          - ``{"event": "error", "data": {"message": "..."}}``
        """
        state_input: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "original_query": query,
            "book_id": book_id,
            "saga_id": saga_id,
            "max_chapter": max_chapter,
            "retries": 0,
        }

        config: dict[str, Any] = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        try:
            async for stream_type, event_data in self._graph.astream(
                state_input, config, stream_mode=["messages", "custom"]
            ):
                if stream_type == "custom":
                    yield {
                        "event": "step",
                        "data": json.dumps(
                            event_data if isinstance(event_data, dict) else {}
                        ),
                    }
                elif stream_type == "messages":
                    # messages mode yields (AIMessageChunk, metadata) tuples
                    chunk_msg, _ = event_data
                    if isinstance(chunk_msg, AIMessageChunk) and chunk_msg.content:
                        content = chunk_msg.content
                        token = content if isinstance(content, str) else str(content)
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }
        except Exception as exc:  # noqa: BLE001 — stream must not crash caller
            logger.exception("chat_v2_stream_error", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": f"Stream failed: {type(exc).__name__}"}
                ),
            }
            return

        yield {"event": "done", "data": "{}"}

        logger.info(
            "chat_v2_stream_done",
            book_id=book_id,
            saga_id=saga_id,
            query_len=len(query),
            thread_id=thread_id,
        )
