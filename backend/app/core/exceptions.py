"""Custom exception hierarchy for WorldRAG.

Business-logic exceptions that map cleanly to HTTP status codes.
Routes catch these instead of using bare HTTPException everywhere.

Hierarchy:
    WorldRAGError (base)
    +-- NotFoundError          -> 404
    +-- ValidationError        -> 422
    +-- ConflictError          -> 409
    +-- CostCeilingError       -> 402
    +-- ExtractionError        -> 500
    +-- ServiceUnavailableError -> 503
    +-- AuthenticationError    -> 401
    +-- ForbiddenError         -> 403
    +-- RateLimitError         -> 429
"""

from __future__ import annotations


class WorldRAGError(Exception):
    """Base exception for all WorldRAG business-logic errors."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None, *, context: dict[str, object] | None = None):
        self.detail = detail or self.__class__.detail
        self.context = context or {}
        super().__init__(self.detail)


class NotFoundError(WorldRAGError):
    """Resource not found (404)."""

    status_code = 404
    detail = "Resource not found"


class ValidationError(WorldRAGError):
    """Input validation failed (422)."""

    status_code = 422
    detail = "Validation error"


class ConflictError(WorldRAGError):
    """Operation conflicts with current state (409)."""

    status_code = 409
    detail = "Resource conflict"


class CostCeilingError(WorldRAGError):
    """LLM cost ceiling exceeded (402 Payment Required)."""

    status_code = 402
    detail = "Cost ceiling exceeded"


class ExtractionError(WorldRAGError):
    """LLM extraction pipeline failure (500)."""

    status_code = 500
    detail = "Extraction failed"


class ServiceUnavailableError(WorldRAGError):
    """External service unavailable (503)."""

    status_code = 503
    detail = "Service unavailable"


class AuthenticationError(WorldRAGError):
    """Missing or invalid authentication (401)."""

    status_code = 401
    detail = "Authentication required"


class ForbiddenError(WorldRAGError):
    """Insufficient permissions (403)."""

    status_code = 403
    detail = "Forbidden"


class RateLimitError(WorldRAGError):
    """Too many requests (429)."""

    status_code = 429
    detail = "Rate limit exceeded"
