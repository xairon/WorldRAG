"""Chat/RAG query service.

Thin wrapper around the LangGraph chat agent graph. The graph handles
all retrieval, reranking, KG lookups, generation, and faithfulness checks.
This service compiles the graph, invokes it, and maps the final state
back to API response schemas.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from neo4j import AsyncDriver

from langchain_core.messages import AIMessageChunk, HumanMessage

from app.agents.chat.graph import build_chat_graph
from app.config import settings
from app.core.logging import get_logger
from app.llm.embeddings import LocalEmbedder
from app.repositories.base import Neo4jRepository
from app.schemas.chat import (
    ChatResponse,
    Citation,
    RelatedEntity,
    SourceChunk,
)

logger = get_logger(__name__)


def _build_langfuse_callbacks(
    *,
    session_id: str | None = None,
    book_id: str = "",
) -> list[Any]:
    """Build Langfuse CallbackHandler list for LangGraph config.

    Returns a list with one handler if Langfuse is configured, empty list otherwise.
    Each request gets a fresh handler so session_id/user_id are scoped correctly.
    """
    has_langfuse = (
        settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key
    )
    if not has_langfuse:
        return []

    try:
        from langfuse.callback import CallbackHandler

        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            session_id=session_id or f"chat-{book_id}",
            tags=["chat-agent", f"book:{book_id}"],
            metadata={"book_id": book_id, "pipeline": "agentic-rag"},
        )
        return [handler]
    except ImportError:
        logger.warning("langfuse_callback_import_failed")
        return []


def _flush_langfuse_score(
    config: dict[str, Any],
    *,
    score_name: str,
    value: float,
) -> None:
    """Push a numeric score to the Langfuse trace (best-effort, fire-and-forget).

    Extracts the CallbackHandler from config and calls `langfuse.score()`.
    Silently does nothing if no handler is present or on any error.
    """
    callbacks = config.get("callbacks", [])
    if not callbacks:
        return

    try:
        handler = callbacks[0]
        # CallbackHandler exposes .langfuse and .get_trace_id()
        if hasattr(handler, "langfuse") and hasattr(handler, "get_trace_id"):
            handler.langfuse.score(
                trace_id=handler.get_trace_id(),
                name=score_name,
                value=value,
            )
    except Exception:  # noqa: BLE001 — best-effort observability
        logger.debug("langfuse_score_push_failed", score_name=score_name)


class ChatService:
    """Hybrid retrieval + generation service for novel Q&A.

    Delegates all pipeline logic to the LangGraph chat agent graph
    built by ``build_chat_graph``. The service is responsible for:

    - Constructing the graph with the right dependencies (repo, embedder).
    - Mapping user inputs into the graph's state schema.
    - Mapping the graph's output state back to ``ChatResponse``.
    - Providing an SSE streaming interface via ``query_stream``.

    The compiled graph is cached as a class-level singleton to avoid
    expensive recompilation on every request (C1 audit fix).
    """

    _compiled_graph: Any = None
    _shared_repo: Any = None
    _shared_embedder: Any = None
    _shared_driver: Any = None  # Track driver identity for invalidation (N5 fix)
    _shared_checkpointer: Any = None
    # Note: asyncio is single-threaded (cooperative). The entire __init__ block
    # has no await points, so the check-and-set of _compiled_graph is atomic
    # within the event loop — no lock needed.

    def __init__(self, driver: AsyncDriver, checkpointer: Any = None) -> None:
        self.repo = Neo4jRepository(driver)

        # Invalidate cached graph if driver changed (N5 fix - e.g. pool refresh)
        if ChatService._shared_driver is not None and ChatService._shared_driver is not driver:
            logger.info("chat_service_driver_changed_recompiling")
            ChatService._compiled_graph = None
            ChatService._shared_repo = None
            ChatService._shared_embedder = None
            ChatService._shared_checkpointer = None

        # Compile graph once and reuse across all instances
        if ChatService._compiled_graph is None:
            self.embedder = LocalEmbedder()
            ChatService._shared_repo = self.repo
            ChatService._shared_embedder = self.embedder
            ChatService._shared_driver = driver
            ChatService._shared_checkpointer = checkpointer
            builder = build_chat_graph(
                repo=self.repo,
                embedder=self.embedder,
            )
            ChatService._compiled_graph = builder.compile(
                checkpointer=checkpointer,
            )
        else:
            self.embedder = ChatService._shared_embedder

        self._graph = ChatService._compiled_graph

    def _build_config(
        self,
        *,
        thread_id: str | None = None,
        book_id: str = "",
    ) -> dict[str, Any]:
        """Build LangGraph invoke/stream config with optional Langfuse + thread_id."""
        config: dict[str, Any] = {}

        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        callbacks = _build_langfuse_callbacks(session_id=thread_id, book_id=book_id)
        if callbacks:
            config["callbacks"] = callbacks

        return config

    async def query(
        self,
        query: str,
        book_id: str,
        *,
        top_k: int = 20,
        rerank_top_n: int = 5,
        min_relevance: float = 0.1,
        include_sources: bool = True,
        max_chapter: int | None = None,
        thread_id: str | None = None,
    ) -> ChatResponse:
        """Run the full RAG pipeline via the LangGraph chat agent.

        Args:
            query: User question.
            book_id: Book to scope the search to.
            top_k: Number of chunks to retrieve from vector search.
            rerank_top_n: Number of chunks to keep after reranking.
            min_relevance: Minimum reranker relevance score.
            include_sources: Whether to include source chunks in response.
            max_chapter: Spoiler guard: only search up to this chapter.
            thread_id: Conversation thread ID for multi-turn support.

        Returns:
            ChatResponse with answer, sources, related entities, and citations.
        """
        # top_k, rerank_top_n, min_relevance kept for API backward compat;
        # the graph nodes manage their own retrieval configuration.
        _ = top_k, rerank_top_n, min_relevance

        state_input: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
            "query": query,
            "book_id": book_id,
            "max_chapter": max_chapter,
            "retries": 0,
        }

        config = self._build_config(thread_id=thread_id, book_id=book_id)

        result = await self._graph.ainvoke(state_input, config=config)

        # Map graph output to ChatResponse
        gen_output = result.get("generation_output", {})
        answer = (
            gen_output.get("answer")
            or result.get("generation", "")
            or "I wasn't able to generate an answer."
        )

        sources: list[SourceChunk] = []
        if include_sources:
            for chunk in result.get("reranked_chunks", []):
                sources.append(
                    SourceChunk(
                        text=chunk.get("text", "")[:500],
                        chapter_number=chunk.get("chapter_number", 0),
                        chapter_title=chunk.get("chapter_title", ""),
                        position=chunk.get("position", 0),
                        relevance_score=chunk.get("relevance_score", 0.0),
                    )
                )

        related_entities = [
            RelatedEntity(
                name=e.get("name", ""),
                label=e.get("label", ""),
                description=e.get("description", ""),
            )
            for e in result.get("kg_entities", [])
            if e.get("name")
        ]

        citations = [
            Citation(
                chapter=c["chapter"],
                position=c.get("position"),
            )
            for c in result.get("citations", [])
            if "chapter" in c
        ]

        # Push faithfulness score to Langfuse trace (best-effort)
        _flush_langfuse_score(
            config,
            score_name="faithfulness",
            value=result.get("faithfulness_score", 0.0),
        )

        logger.info(
            "chat_query_completed",
            book_id=book_id,
            query_len=len(query),
            chunks_retrieved=len(result.get("fused_results", [])),
            chunks_after_rerank=len(result.get("reranked_chunks", [])),
            entities_found=len(related_entities),
            faithfulness_score=result.get("faithfulness_score"),
            thread_id=thread_id,
        )

        return ChatResponse(
            answer=answer,
            sources=sources,
            related_entities=related_entities,
            chunks_retrieved=len(result.get("fused_results", [])),
            chunks_after_rerank=len(result.get("reranked_chunks", [])),
            thread_id=thread_id,
            citations=citations,
            confidence=gen_output.get("confidence", result.get("faithfulness_score", 0.0)),
            entities_mentioned=gen_output.get("entities_mentioned", []),
        )

    async def query_stream(
        self,
        query: str,
        book_id: str,
        *,
        top_k: int = 20,
        rerank_top_n: int = 5,
        min_relevance: float = 0.1,
        max_chapter: int | None = None,
        thread_id: str | None = None,
    ) -> AsyncGenerator[dict[str, str], None]:
        """Stream the RAG pipeline as SSE events via LangGraph astream.

        Yields dicts with "event" and "data" keys:
          - {"event": "step", "data": <json step info>}
          - {"event": "token", "data": {"token": "..."}}
          - {"event": "done", "data": "{}"}
          - {"event": "error", "data": {"message": "..."}}
        """
        _ = top_k, rerank_top_n, min_relevance  # backward compat; graph manages config

        state_input: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
            "query": query,
            "book_id": book_id,
            "max_chapter": max_chapter,
            "retries": 0,
        }

        config = self._build_config(thread_id=thread_id, book_id=book_id)

        try:
            async for stream_type, event_data in self._graph.astream(
                state_input, config=config, stream_mode=["messages", "custom"]
            ):
                if stream_type == "custom":
                    yield {
                        "event": "step",
                        "data": json.dumps(event_data if isinstance(event_data, dict) else {}),
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
        except Exception as exc:  # noqa: BLE001 — stream must not crash
            logger.exception("chat_stream_error", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Stream failed: {type(exc).__name__}"}),
            }
            return

        yield {"event": "done", "data": "{}"}

        logger.info(
            "chat_stream_completed",
            book_id=book_id,
            query_len=len(query),
            thread_id=thread_id,
        )
