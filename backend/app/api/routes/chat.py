"""Chat/RAG query API routes.

Provides the hybrid retrieval endpoint that powers the chat frontend:
Vector search → Rerank → Graph context → LLM generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

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
    driver: AsyncDriver = Depends(get_neo4j),
) -> ChatResponse:
    """Ask a question about a book, grounded in the Knowledge Graph.

    Uses hybrid retrieval (vector + rerank + graph) to find relevant
    context, then generates a natural language answer with the LLM.
    """
    service = ChatService(driver)
    return await service.query(
        query=request.query,
        book_id=request.book_id,
        top_k=request.top_k,
        rerank_top_n=request.rerank_top_n,
        min_relevance=request.min_relevance,
        include_sources=request.include_sources,
    )
