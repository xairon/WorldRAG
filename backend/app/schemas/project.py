"""API schemas for project endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request to create a new project."""

    name: str = Field(..., min_length=1, max_length=300)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    description: str = ""


class ProjectUpdate(BaseModel):
    """Request to update project metadata."""

    name: str | None = Field(default=None, max_length=300)
    description: str | None = None


class ProjectResponse(BaseModel):
    """Response for a single project."""

    id: str
    slug: str
    name: str
    description: str
    cover_image: str | None = None
    created_at: datetime
    updated_at: datetime
    books_count: int = 0
    has_profile: bool = False
    entity_count: int = 0


class ProjectListResponse(BaseModel):
    """Response for listing all projects."""

    projects: list[ProjectResponse]
    total: int


class ProjectFileResponse(BaseModel):
    """Response for a stored file."""

    id: str
    filename: str
    file_size: int
    mime_type: str
    book_id: str | None = None
    book_num: int
    uploaded_at: datetime


class ProjectStatsResponse(BaseModel):
    """Response for project statistics."""

    slug: str
    books_count: int
    chapters_total: int
    entities_total: int
    community_count: int
    has_profile: bool
    profile_types_count: int
