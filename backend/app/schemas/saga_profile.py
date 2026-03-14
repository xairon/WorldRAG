"""API schemas for saga profile endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.saga_profile.models import SagaProfile


class SagaProfileResponse(BaseModel):
    """Response wrapper for a saga profile."""

    profile: SagaProfile
    exists: bool = True


class SagaProfileListItem(BaseModel):
    """Summary item for saga profile listing."""

    saga_id: str
    saga_name: str
    version: int
    entity_types_count: int
    patterns_count: int
    estimated_complexity: str


class SagaProfileListResponse(BaseModel):
    """Response for listing all saga profiles."""

    profiles: list[SagaProfileListItem]
    total: int


class ExtractGraphitiRequest(BaseModel):
    """Request to trigger Graphiti extraction."""

    saga_id: str = Field(..., min_length=1, max_length=200, pattern=r"^[\w\-.:]+$")
    saga_name: str = Field(..., min_length=1, max_length=500)
    book_num: int = Field(default=1, ge=1)
