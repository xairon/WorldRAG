"""Project management API routes.

Handles project lifecycle: create, list, get, update, delete, stats,
book upload, and Graphiti extraction trigger.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Form, Request, UploadFile
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
    from uuid import UUID

    result = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, UUID):
            result[k] = str(v)
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


@router.get("/{slug}/books", dependencies=[Depends(require_auth)])
async def list_books(slug: str, request: Request) -> JSONResponse:
    """List all books (files) in a project."""
    svc = _get_service(request)
    existing = await svc.get_project(slug)
    if existing is None:
        return JSONResponse(status_code=404, content={"detail": f"Project '{slug}' not found"})
    files = await svc.repo.list_files(str(existing["id"]))
    serialized = [_serialize_project(f) for f in files]
    return JSONResponse(status_code=200, content=serialized)


@router.post("/{slug}/books", dependencies=[Depends(require_auth)])
async def upload_book(
    slug: str,
    file: UploadFile,
    request: Request,
    book_num: int = Form(default=1),
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

    # Duplicate check: reject if same filename already exists in project
    existing_files = await svc.repo.list_files(str(existing["id"]))
    for ef in existing_files:
        if ef.get("filename") == file.filename:
            return JSONResponse(
                status_code=409,
                content={"detail": f"File '{file.filename}' already uploaded to this project"},
            )

    suffix = Path(file.filename).suffix.lower()
    allowed = {".epub", ".pdf", ".txt"}
    if suffix not in allowed:
        return JSONResponse(
            status_code=422,
            content={"detail": f"Unsupported format: {suffix}. Allowed: {', '.join(allowed)}"},
        )

    # C1: Check Content-Length header BEFORE reading file into memory
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)}MB)"},
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)}MB)"},
        )

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

    # ── Run ingestion pipeline (parse → chunk → regex → Neo4j) ──────
    from pathlib import Path as _Path
    from app.services.ingestion import extract_epub_metadata, ingest_file
    from app.services.chunking import chunk_chapter
    from app.services.extraction.regex_extractor import RegexExtractor
    from app.schemas.book import ProcessingStatus

    file_path = _Path(file_row["file_path"])
    neo4j_driver = request.app.state.neo4j_driver
    from app.repositories.book_repo import BookRepository
    repo = BookRepository(neo4j_driver)

    try:
        # Auto-detect metadata from epub
        epub_meta: dict = {}
        if suffix == ".epub":
            epub_meta = await extract_epub_metadata(file_path)

        book_title = epub_meta.get("title") or file_path.stem
        book_author = epub_meta.get("author")
        book_series = epub_meta.get("series_name")
        book_order = epub_meta.get("order_in_series")

        # Create book in Neo4j
        book_id = await repo.create_book(
            title=book_title,
            series_name=book_series,
            order_in_series=book_order,
            author=book_author,
            genre=None,
        )

        await repo.update_book_status(book_id, ProcessingStatus.INGESTING.value)

        # Parse file into chapters
        chapters, epub_css = await ingest_file(file_path)
        if not chapters:
            await repo.update_book_status(book_id, ProcessingStatus.FAILED.value)
            return JSONResponse(status_code=422, content={"detail": "No chapters found in file"})

        await repo.create_chapters(book_id, chapters)
        await repo.update_book_chapter_count(book_id, len(chapters))

        if epub_css:
            await repo.set_book_epub_css(book_id, epub_css)

        for chapter in chapters:
            if chapter.paragraphs:
                await repo.create_paragraphs(book_id, chapter.number, chapter.paragraphs)

        # Chunk each chapter
        await repo.update_book_status(book_id, ProcessingStatus.CHUNKING.value)
        all_chunks = []
        for chapter in chapters:
            chunks = chunk_chapter(chapter, book_id)
            all_chunks.extend(chunks)
        await repo.create_chunks(book_id, all_chunks)

        # Regex extraction (Passe 0)
        regex_extractor = RegexExtractor.default()
        all_regex_matches = []
        for chapter in chapters:
            matches = regex_extractor.extract(chapter.text, chapter.number)
            all_regex_matches.extend(matches)
        await repo.store_regex_matches(book_id, all_regex_matches)

        await repo.update_book_status(book_id, ProcessingStatus.COMPLETED.value)

        # Update project_files row with the Neo4j book_id
        await svc.repo.update_file_book_id(str(file_row["id"]), book_id)

        logger.info(
            "project_book_ingested",
            slug=slug,
            book_id=book_id,
            chapters=len(chapters),
            chunks=len(all_chunks),
            regex_matches=len(all_regex_matches),
        )

        file_row["book_id"] = book_id
    except Exception:
        logger.exception("project_book_ingestion_failed", slug=slug, filename=file.filename)
        # File is stored but ingestion failed — return partial result
        pass

    return JSONResponse(status_code=201, content=_serialize_project(file_row))


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

    # H18: book_num=1 is a default; the worker processes chapters sequentially
    # from file records. Multi-book projects should determine book_num from
    # the project_files table. This is acceptable for single-book extraction.
    job = await arq_pool.enqueue_job(
        "process_book_graphiti",
        slug,
        slug,  # saga_id = slug
        existing.get("name", slug),  # saga_name
        1,  # book_num default — see comment above
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


# ── KG Export ─────────────────────────────────────────────────────────


@router.get("/{slug}/export/cypher", dependencies=[Depends(require_auth)])
async def export_cypher(slug: str, request: Request) -> JSONResponse:
    """Export the project's KG as Cypher CREATE statements."""
    svc = _get_service(request)
    if await svc.get_project(slug) is None:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})

    from app.services.kg_export import export_cypher as do_export

    driver = request.app.state.neo4j_driver
    cypher = await do_export(driver, saga_id=slug)
    return JSONResponse(
        status_code=200,
        content={"format": "cypher", "slug": slug, "data": cypher},
    )


@router.get("/{slug}/export/jsonld", dependencies=[Depends(require_auth)])
async def export_jsonld(slug: str, request: Request) -> JSONResponse:
    """Export the project's KG as JSON-LD."""
    svc = _get_service(request)
    if await svc.get_project(slug) is None:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})

    from app.services.kg_export import export_json_ld as do_export

    driver = request.app.state.neo4j_driver
    data = await do_export(driver, saga_id=slug)
    return JSONResponse(status_code=200, content=data)


@router.get("/{slug}/export/csv", dependencies=[Depends(require_auth)])
async def export_csv(slug: str, request: Request) -> JSONResponse:
    """Export the project's KG as CSV (entities + relationships)."""
    svc = _get_service(request)
    if await svc.get_project(slug) is None:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})

    from app.services.kg_export import export_csv as do_export

    driver = request.app.state.neo4j_driver
    data = await do_export(driver, saga_id=slug)
    return JSONResponse(
        status_code=200,
        content={"format": "csv", "slug": slug, **data},
    )
