"""API key authentication for WorldRAG.

Simple bearer-token authentication via the Authorization header.
Set WORLDRAG_API_KEY in .env to enable; if blank, auth is disabled
(dev mode) and all requests are allowed through.

Usage in routes:
    from app.api.auth import require_auth, require_admin

    @router.post("/books", dependencies=[Depends(require_auth)])
    async def upload_book(...): ...

    @router.post("/admin/dlq/clear", dependencies=[Depends(require_admin)])
    async def clear_dlq(...): ...
"""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.logging import get_logger

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def _get_api_keys(request: Request) -> tuple[str, str]:
    """Read API keys from app settings (loaded once at startup)."""
    from app.config import settings

    return (
        getattr(settings, "api_key", ""),
        getattr(settings, "admin_api_key", ""),
    )


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Validate Bearer token against WORLDRAG_API_KEY.

    If WORLDRAG_API_KEY is empty (dev mode), all requests pass through.

    Returns:
        The validated API key (or "dev" in dev mode).

    Raises:
        AuthenticationError: If the token is missing or invalid.
    """
    api_key, admin_key = _get_api_keys(request)

    # Dev mode: no key configured — allow everything
    if not api_key:
        return "dev"

    if credentials is None:
        raise AuthenticationError("Missing Authorization header. Use: Bearer <api_key>")

    token = credentials.credentials
    if token == api_key or (admin_key and token == admin_key):
        return token

    raise AuthenticationError("Invalid API key")


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Validate Bearer token against WORLDRAG_ADMIN_API_KEY.

    Admin endpoints require the admin key specifically.
    In dev mode (no keys configured), all requests pass through.

    Returns:
        The validated admin key (or "dev" in dev mode).

    Raises:
        AuthenticationError: If the token is missing.
        ForbiddenError: If the token is not the admin key.
    """
    _, admin_key = _get_api_keys(request)

    # Dev mode
    if not admin_key:
        return "dev"

    if credentials is None:
        raise AuthenticationError("Missing Authorization header. Use: Bearer <admin_api_key>")

    token = credentials.credentials
    if token == admin_key:
        return token

    raise ForbiddenError("Admin access required")
