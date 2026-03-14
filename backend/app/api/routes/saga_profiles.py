"""CRUD endpoints for saga profiles stored in Redis.

Saga profiles are keyed as `saga_profile:{saga_id}` in Redis and store
the full SagaProfile JSON that describes a saga's KG ontology.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.api.auth import require_auth
from app.core.logging import get_logger
from app.schemas.saga_profile import SagaProfileListItem, SagaProfileListResponse, SagaProfileResponse
from app.services.saga_profile.models import SagaProfile

logger = get_logger(__name__)

router = APIRouter(prefix="/saga-profiles", tags=["saga-profiles"])
REDIS_PREFIX = "saga_profile:"


async def _get_redis(request: Request) -> Redis:
    return request.app.state.redis


@router.get(
    "",
    response_model=SagaProfileListResponse,
    dependencies=[Depends(require_auth)],
)
async def list_saga_profiles(
    redis: Redis = Depends(_get_redis),
) -> SagaProfileListResponse:
    """List all saga profiles stored in Redis."""
    keys: list[str] = await redis.keys(f"{REDIS_PREFIX}*")
    items: list[SagaProfileListItem] = []

    for key in keys:
        raw = await redis.get(key)
        if raw is None:
            continue
        try:
            profile = SagaProfile.model_validate_json(raw)
            items.append(
                SagaProfileListItem(
                    saga_id=profile.saga_id,
                    saga_name=profile.saga_name,
                    version=profile.version,
                    entity_types_count=len(profile.entity_types),
                    patterns_count=len(profile.text_patterns),
                    estimated_complexity=profile.estimated_complexity,
                )
            )
        except Exception as exc:
            logger.warning("saga_profile_parse_error", key=key, error=type(exc).__name__)

    logger.info("saga_profiles_listed", total=len(items))
    return SagaProfileListResponse(profiles=items, total=len(items))


@router.get(
    "/{saga_id}",
    dependencies=[Depends(require_auth)],
)
async def get_saga_profile(
    saga_id: str,
    redis: Redis = Depends(_get_redis),
) -> JSONResponse:
    """Return a single saga profile by saga_id. Returns 404 if not found."""
    raw = await redis.get(f"{REDIS_PREFIX}{saga_id}")
    if raw is None:
        logger.info("saga_profile_not_found", saga_id=saga_id)
        return JSONResponse(status_code=404, content={"detail": f"Saga profile '{saga_id}' not found"})

    profile = SagaProfile.model_validate_json(raw)
    response = SagaProfileResponse(profile=profile, exists=True)
    return JSONResponse(status_code=200, content=response.model_dump())


@router.put(
    "/{saga_id}",
    response_model=SagaProfileResponse,
    dependencies=[Depends(require_auth)],
)
async def upsert_saga_profile(
    saga_id: str,
    profile: SagaProfile,
    redis: Redis = Depends(_get_redis),
) -> SagaProfileResponse:
    """Create or update a saga profile. saga_id in the URL takes precedence."""
    # Ensure the saga_id in the body is consistent with the URL param
    profile = profile.model_copy(update={"saga_id": saga_id})
    raw = profile.model_dump_json()
    await redis.set(f"{REDIS_PREFIX}{saga_id}", raw)
    logger.info("saga_profile_upserted", saga_id=saga_id)
    return SagaProfileResponse(profile=profile, exists=True)


@router.delete(
    "/{saga_id}",
    dependencies=[Depends(require_auth)],
)
async def delete_saga_profile(
    saga_id: str,
    redis: Redis = Depends(_get_redis),
) -> JSONResponse:
    """Delete a saga profile. Returns 404 if not found."""
    deleted = await redis.delete(f"{REDIS_PREFIX}{saga_id}")
    if deleted == 0:
        logger.info("saga_profile_delete_not_found", saga_id=saga_id)
        return JSONResponse(status_code=404, content={"detail": f"Saga profile '{saga_id}' not found"})

    logger.info("saga_profile_deleted", saga_id=saga_id)
    return JSONResponse(status_code=200, content={"deleted": saga_id})
