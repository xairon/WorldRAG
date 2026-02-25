"""Pydantic schemas for the Chat/RAG query API.

Defines request and response models for the hybrid retrieval pipeline:
Vector search → Rerank → Graph context → LLM generation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for a chat query."""

    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    book_id: str = Field(..., min_length=1, description="Book to query against")
    top_k: int = Field(default=20, ge=1, le=100, description="Chunks to retrieve")
    rerank_top_n: int = Field(default=5, ge=1, le=50, description="Chunks after reranking")
    min_relevance: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Minimum reranker score"
    )
    include_sources: bool = Field(default=True, description="Include source chunks in response")


class SourceChunk(BaseModel):
    """A source chunk used to generate the answer."""

    text: str
    chapter_number: int
    chapter_title: str = ""
    position: int = 0
    relevance_score: float = 0.0


class RelatedEntity(BaseModel):
    """A KG entity related to the retrieved context."""

    name: str
    label: str
    description: str = ""


class ChatResponse(BaseModel):
    """Response schema for a chat query."""

    answer: str
    sources: list[SourceChunk] = []
    related_entities: list[RelatedEntity] = []
    chunks_retrieved: int = 0
    chunks_after_rerank: int = 0
