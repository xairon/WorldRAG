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
from app.api.dependencies import get_neo4j, get_postgres
from app.config import settings
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse
from app.services.chat_service import ChatService

if TYPE_CHECKING:
    import asyncpg
    from neo4j import AsyncDriver

    from app.services.chat_service_v2 import ChatServiceV2

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _get_chat_service_v2(
    request: Request, driver: AsyncDriver, checkpointer: object | None
) -> ChatServiceV2:
    """Return a cached ChatServiceV2 from app.state, creating it on first call."""
    from app.services.chat_service_v2 import ChatServiceV2

    existing = getattr(request.app.state, "chat_service_v2", None)
    if existing is not None:
        return existing

    graphiti = getattr(request.app.state, "graphiti", None)
    service = ChatServiceV2(graphiti, driver, checkpointer=checkpointer)
    request.app.state.chat_service_v2 = service
    return service


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
    if settings.graphiti_enabled:
        service_v2 = _get_chat_service_v2(http_request, driver, checkpointer)
        return await service_v2.query(
            query=request.query,
            book_id=request.book_id,
            saga_id=request.book_id,  # default: saga_id = book_id
            max_chapter=request.max_chapter,
            thread_id=request.thread_id,
        )
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
    if settings.graphiti_enabled:
        service_v2 = _get_chat_service_v2(request, driver, checkpointer)

        async def event_generator_v2():
            async for event in service_v2.query_stream(
                query=q,
                book_id=book_id,
                saga_id=book_id,  # default: saga_id = book_id
                max_chapter=max_chapter,
                thread_id=thread_id,
            ):
                yield event

        return EventSourceResponse(event_generator_v2())

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


@router.post(
    "/feedback",
    dependencies=[Depends(require_auth)],
    response_model=FeedbackResponse,
    status_code=201,
)
async def submit_feedback(
    body: FeedbackRequest,
    pool: asyncpg.Pool = Depends(get_postgres),
) -> FeedbackResponse:
    """Submit a thumbs-up / thumbs-down rating for a chat answer.

    ``thread_id`` links the rating back to the conversation.
    ``rating`` must be ``1`` (positive) or ``-1`` (negative).
    ``comment`` is optional free-text feedback.
    """
    row = await pool.fetchrow(
        """
        INSERT INTO chat_feedback (thread_id, message_id, rating, comment, book_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, thread_id, message_id, rating, comment, book_id, created_at
        """,
        body.thread_id,
        body.message_id,
        body.rating,
        body.comment,
        body.book_id,
    )
    logger.info(
        "chat_feedback_submitted",
        thread_id=body.thread_id,
        rating=body.rating,
        has_comment=bool(body.comment),
    )
    return FeedbackResponse(**dict(row))


@router.get(
    "/feedback/{thread_id}",
    dependencies=[Depends(require_auth)],
    response_model=list[FeedbackResponse],
)
async def get_feedback(
    thread_id: str,
    pool: asyncpg.Pool = Depends(get_postgres),
) -> list[FeedbackResponse]:
    """Retrieve all feedback records for a conversation thread."""
    rows = await pool.fetch(
        """
        SELECT id, thread_id, message_id, rating, comment, book_id, created_at
        FROM chat_feedback
        WHERE thread_id = $1
        ORDER BY created_at DESC
        """,
        thread_id,
    )
    return [FeedbackResponse(**dict(row)) for row in rows]
