"""Project management API routes.

Handles project lifecycle: create, list, get, update, delete, stats,
book upload, and Graphiti extraction trigger.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.auth import require_auth
from app.core.logging import get_logger
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectStatsResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_service(request: Request) -> ProjectService:
    """Construct a ProjectService from app.state."""
    return ProjectService(
        pool=request.app.state.pg_pool,
        redis=request.app.state.redis,
        neo4j_driver=request.app.state.neo4j_driver,
    )


def _serialize_project(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a project DB row to a JSON-serialisable dict.

    datetime objects are converted to ISO-8601 strings so they can be
    embedded directly in a JSONResponse without hitting the default
    serialiser which does not handle datetime.
    """
    result = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", dependencies=[Depends(require_auth)], status_code=201)
async def create_project(
    body: ProjectCreate,
    request: Request,
) -> JSONResponse:
    """Create a new project. Returns 409 if the slug already exists."""
    svc = _get_service(request)

    # Check for slug conflict
    existing = await svc.get_project(body.slug)
    if existing is not None:
        logger.info("project_slug_conflict", slug=body.slug)
        return JSONResponse(
            status_code=409,
            content={"detail": f"Project with slug '{body.slug}' already exists"},
        )

    row = await svc.create_project(
        slug=body.slug,
        name=body.name,
        description=body.description,
    )
    if row is None:
        return JSONResponse(status_code=500, content={"detail": "Failed to create project"})

    logger.info("project_created_via_api", slug=body.slug)
    return JSONResponse(status_code=201, content=_serialize_project(row))


@router.get("", dependencies=[Depends(require_auth)])
async def list_projects(request: Request) -> JSONResponse:
    """List all projects."""
    svc = _get_service(request)
    rows = await svc.list_projects()
    projects = [_serialize_project(r) for r in rows]
    return JSONResponse(
        status_code=200,
        content={"projects": projects, "total": len(projects)},
    )


@router.get("/{slug}", dependencies=[Depends(require_auth)])
async def get_project(slug: str, request: Request) -> JSONResponse:
    """Get a single project by slug. Returns 404 if not found."""
    svc = _get_service(request)
    row = await svc.get_project(slug)
    if row is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})
    return JSONResponse(status_code=200, content=_serialize_project(row))


@router.put("/{slug}", dependencies=[Depends(require_auth)])
async def update_project(
    slug: str,
    body: ProjectUpdate,
    request: Request,
) -> JSONResponse:
    """Update project metadata. Returns 404 if not found."""
    svc = _get_service(request)

    # Confirm project exists before attempting update
    existing = await svc.get_project(slug)
    if existing is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})

    row = await svc.update_project(
        slug,
        name=body.name,
        description=body.description,
    )
    if row is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})

    logger.info("project_updated_via_api", slug=slug)
    return JSONResponse(status_code=200, content=_serialize_project(row))


@router.delete("/{slug}", dependencies=[Depends(require_auth)])
async def delete_project(slug: str, request: Request) -> JSONResponse:
    """Cascade-delete a project and all associated data. Returns 404 if not found."""
    svc = _get_service(request)

    existing = await svc.get_project(slug)
    if existing is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})

    await svc.delete_project(slug)
    logger.info("project_deleted_via_api", slug=slug)
    return JSONResponse(status_code=200, content={"deleted": slug})


@router.get("/{slug}/stats", dependencies=[Depends(require_auth)])
async def get_project_stats(slug: str, request: Request) -> JSONResponse:
    """Return aggregate statistics for a project. Returns 404 if not found."""
    svc = _get_service(request)

    existing = await svc.get_project(slug)
    if existing is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})

    stats = await svc.get_stats(slug)
    return JSONResponse(status_code=200, content=stats)


@router.post("/{slug}/books", dependencies=[Depends(require_auth)])
async def upload_book(
    slug: str,
    file: UploadFile,
    request: Request,
    book_num: int = 1,
) -> JSONResponse:
    """Upload an EPUB/PDF/TXT file to a project and run ingestion pipeline.

    Stores the file in the project directory, then triggers the standard
    ingestion pipeline (parse → chunk → regex extract → Neo4j store).
    """
    from pathlib import Path

    svc = _get_service(request)

    existing = await svc.get_project(slug)
    if existing is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})

    if not file.filename:
        return JSONResponse(status_code=422, content={"detail": "No filename provided"})

    suffix = Path(file.filename).suffix.lower()
    allowed = {".epub", ".pdf", ".txt"}
    if suffix not in allowed:
        return JSONResponse(
            status_code=422,
            content={"detail": f"Unsupported format: {suffix}. Allowed: {', '.join(allowed)}"},
        )

    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    file_row = await svc.store_book_file(
        slug=slug,
        filename=file.filename,
        file_content=content,
        book_num=book_num,
        mime_type=mime_type,
    )

    logger.info("project_book_uploaded", slug=slug, filename=file.filename)

    if file_row is None:
        return JSONResponse(status_code=500, content={"detail": "Failed to store book file"})

    # Serialize datetimes in file_row
    result = {}
    for k, v in file_row.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return JSONResponse(status_code=201, content=result)


@router.post("/{slug}/extract", dependencies=[Depends(require_auth)], status_code=202)
async def extract_project(slug: str, request: Request) -> JSONResponse:
    """Enqueue Graphiti KG extraction for the project.

    Checks Redis for an existing saga profile:
    - If found → guided mode (profile JSON passed to worker)
    - If not found → discovery mode (worker induces profile from scratch)

    Returns 202 immediately with {job_id, mode, slug}.
    """
    svc = _get_service(request)

    existing = await svc.get_project(slug)
    if existing is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})

    arq_pool = request.app.state.arq_pool
    if arq_pool is None:
        return JSONResponse(status_code=503, content={"detail": "Job queue unavailable"})

    redis = request.app.state.redis
    existing_profile = await redis.get(f"saga_profile:{slug}")
    mode = "guided" if existing_profile else "discovery"

    job = await arq_pool.enqueue_job(
        "process_book_graphiti",
        slug,
        slug,  # saga_id = slug
        existing.get("name", slug),  # saga_name
        1,  # book_num default
        existing_profile,
        _queue_name="worldrag:arq",
        _job_id=f"graphiti-project:{slug}",
    )

    job_id = job.job_id if job else f"graphiti-project:{slug}"
    logger.info("project_extract_enqueued", slug=slug, mode=mode, job_id=job_id)
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "mode": mode, "slug": slug},
    )
