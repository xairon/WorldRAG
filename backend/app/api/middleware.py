"""FastAPI middleware for request context injection.

Injects request_id into structlog context for every request,
enabling automatic correlation of all logs within a request.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import get_logger, request_id_var

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that binds a unique request_id to every request.

    Also logs request start/end with timing information.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_var.set(request_id)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger.info("request_started")

        try:
            response = await call_next(request)
            logger.info("request_completed", status_code=response.status_code)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception("request_failed")
            raise
        finally:
            structlog.contextvars.clear_contextvars()
            request_id_var.set(None)
