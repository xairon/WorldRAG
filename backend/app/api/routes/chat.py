"""Chat/RAG query API routes.

Provides the hybrid retrieval endpoint that powers the chat frontend:
Vector search → Rerank → Graph context → LLM generation.

Supports multi-turn conversations via optional ``thread_id`` parameter.
When a thread_id is provided, the agentic pipeline maintains conversation
history through LangGraph checkpointing for contextual follow-up questions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.api.auth import require_auth
from app.api.dependencies import get_neo4j
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/query", dependencies=[Depends(require_auth)], response_model=ChatResponse)
async def chat_query(
    request: ChatRequest,
    http_request: Request,
    driver: AsyncDriver = Depends(get_neo4j),
) -> ChatResponse:
    """Ask a question about a book, grounded in the Knowledge Graph.

    Uses hybrid retrieval (vector + rerank + graph) to find relevant
    context, then generates a natural language answer with the LLM.

    Pass ``thread_id`` to enable multi-turn conversations — the agentic
    pipeline will load prior messages from the checkpoint store and use
    them as context for follow-up questions.
    """
    checkpointer = getattr(http_request.app.state, "checkpointer", None)
    service = ChatService(driver, checkpointer=checkpointer)
    return await service.query(
        query=request.query,
        book_id=request.book_id,
        top_k=request.top_k,
        rerank_top_n=request.rerank_top_n,
        min_relevance=request.min_relevance,
        include_sources=request.include_sources,
        max_chapter=request.max_chapter,
        thread_id=request.thread_id,
    )


@router.get("/stream", dependencies=[Depends(require_auth)])
async def chat_stream(
    request: Request,
    q: str = Query(..., min_length=1, max_length=2000, description="User question"),
    book_id: str = Query(
        ...,
        min_length=1,
        max_length=200,
        pattern=r"^[\w\-.:]+$",
        description="Book to query against",
    ),
    top_k: int = Query(default=20, ge=1, le=100),
    rerank_top_n: int = Query(default=5, ge=1, le=50),
    max_chapter: int | None = Query(default=None, ge=1),
    thread_id: str | None = Query(
        default=None,
        max_length=200,
        pattern=r"^[\w\-.:]+$",
        description="Thread ID for multi-turn",
    ),
    driver: AsyncDriver = Depends(get_neo4j),
) -> EventSourceResponse:
    """Stream a chat answer as Server-Sent Events.

    Pass ``thread_id`` to maintain conversation context across requests.

    Events:
      - `sources`: retrieval metadata (sources, related_entities, counts)
      - `token`: a chunk of the LLM answer
      - `done`: generation complete
      - `error`: something went wrong
    """
    checkpointer = getattr(request.app.state, "checkpointer", None)
    service = ChatService(driver, checkpointer=checkpointer)

    async def event_generator():
        async for event in service.query_stream(
            query=q,
            book_id=book_id,
            top_k=top_k,
            rerank_top_n=rerank_top_n,
            max_chapter=max_chapter,
            thread_id=thread_id,
        ):
            yield event

    return EventSourceResponse(event_generator())
