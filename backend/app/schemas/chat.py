"""Pydantic schemas for the Chat/RAG query API.

Defines request and response models for the hybrid retrieval pipeline:
Vector search → Rerank → Graph context → LLM generation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for a chat query."""

    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    book_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
        pattern=r"^[\w\-.:]+$",
        description="Book to query against",
    )
    top_k: int = Field(default=20, ge=1, le=100, description="Chunks to retrieve")
    rerank_top_n: int = Field(default=5, ge=1, le=50, description="Chunks after reranking")
    min_relevance: float = Field(default=0.1, ge=0.0, le=1.0, description="Minimum reranker score")
    include_sources: bool = Field(default=True, description="Include source chunks in response")
    max_chapter: int | None = Field(
        default=None, ge=1, description="Spoiler guard: only search up to this chapter"
    )
    thread_id: str | None = Field(
        default=None,
        max_length=200,
        pattern=r"^[\w\-.:]+$",
        description="Conversation thread ID for multi-turn support",
    )


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


class Citation(BaseModel):
    """A citation linking a generated answer back to a source chunk."""

    chapter: int
    position: int | None = None


class GeneratedCitation(BaseModel):
    """Rich citation produced by the structured generation node."""

    chapter: int
    position: int | None = None
    claim: str = ""       # the specific claim being cited
    source_span: str = "" # exact text from the chunk (Phase 2 verification)


class GenerationOutput(BaseModel):
    """Structured output from the generation node.

    Stored in state["generation_output"] as a dict.
    state["generation"] is kept for backward compatibility (= answer).
    """

    answer: str
    citations: list[GeneratedCitation] = []
    entities_mentioned: list[str] = []
    confidence: float = 0.0  # filled by nli_check post-generation


class ChatResponse(BaseModel):
    """Response schema for a chat query."""

    answer: str
    sources: list[SourceChunk] = []
    related_entities: list[RelatedEntity] = []
    chunks_retrieved: int = 0
    chunks_after_rerank: int = 0
    thread_id: str | None = None
    citations: list[Citation] = []
    confidence: float = 0.0          # NLI faithfulness score
    entities_mentioned: list[str] = []  # entities referenced in the answer
