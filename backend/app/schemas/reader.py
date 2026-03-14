"""Pydantic schemas for the Reader Q&A API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReaderQueryRequest(BaseModel):
    """Request schema for a reader question."""

    query: str = Field(..., min_length=1, max_length=2000)
    book_id: str = Field(..., min_length=1, max_length=200, pattern=r"^[\w\-.:]+$")
    chapter_number: int = Field(..., ge=1)
    max_chapter: int | None = Field(default=None, ge=1)
    thread_id: str | None = Field(default=None, max_length=200, pattern=r"^[\w\-.:]+$")


class ReaderQueryResponse(BaseModel):
    """Response schema for a reader question."""

    answer: str
    route: str
    paragraphs_used: int = 0
    entities_found: int = 0
    thread_id: str | None = None
