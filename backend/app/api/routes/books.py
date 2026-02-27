"""Book management API routes.

Handles book upload, listing, deletion, and processing status.
Upload triggers the ingestion pipeline: parse -> chunk -> regex extract -> store.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, UploadFile

from app.api.auth import require_auth
from app.api.dependencies import get_arq_pool, get_neo4j
from app.core.exceptions import ConflictError, ExtractionError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.repositories.book_repo import BookRepository
from app.schemas.book import (
    BookDetail,
    BookInfo,
    ChapterInfo,
    IngestionResult,
    JobEnqueuedResult,
    ProcessingStatus,
)
from app.schemas.pipeline import (  # noqa: TC001 — runtime use by FastAPI
    ExtractionRequest,
    ExtractionRequestV3,
    ReprocessRequest,
)
from app.services.chunking import chunk_chapter
from app.services.extraction.regex_extractor import RegexExtractor
from app.services.ingestion import extract_epub_metadata, ingest_file

if TYPE_CHECKING:
    from arq.connections import ArqRedis
    from neo4j import AsyncDriver

logger = get_logger(__name__)
router = APIRouter(prefix="/books", tags=["books"])

# Supported file extensions and content types
ALLOWED_EXTENSIONS = {".epub", ".pdf", ".txt"}
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/epub+zip",
        "application/pdf",
        "text/plain",
        "application/octet-stream",  # common fallback
    }
)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("", response_model=IngestionResult, dependencies=[Depends(require_auth)])
async def upload_book(
    file: UploadFile,
    title: str | None = Query(None, max_length=500),
    series_name: str | None = Query(None, max_length=200),
    order_in_series: int | None = Query(None, ge=1),
    author: str | None = Query(None, max_length=200),
    genre: str = Query("litrpg", max_length=50),
    driver: AsyncDriver = Depends(get_neo4j),
) -> IngestionResult:
    """Upload a book file and run the ingestion pipeline.

    Pipeline: Parse file -> Split chapters -> Chunk -> Regex extract -> Store in Neo4j.

    Supports ePub, PDF, and TXT formats.
    """
    # Validate file
    if not file.filename:
        raise ValidationError("No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported format: {suffix}. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validate content type
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Unsupported content type: {file.content_type}",
        )

    repo = BookRepository(driver)

    tmp_path: Path | None = None
    book_id: str | None = None

    try:
        # Save uploaded file to temp location (async + size enforcement)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            await asyncio.to_thread(shutil.copyfileobj, file.file, tmp)
            tmp_path = Path(tmp.name)

        # Enforce file size limit
        file_size = tmp_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            tmp_path.unlink(missing_ok=True)
            raise ValidationError(
                f"File too large ({file_size:,} bytes). Max: {MAX_FILE_SIZE:,} bytes."
            )

        # Auto-detect metadata from epub OPF (title, author, series, etc.)
        epub_meta: dict = {}
        if suffix == ".epub":
            epub_meta = await extract_epub_metadata(tmp_path)
            logger.info(
                "epub_metadata_detected",
                metadata={k: v for k, v in epub_meta.items() if v},
            )

        # Use epub metadata as defaults, user-provided values take priority
        book_title = title or epub_meta.get("title") or Path(file.filename).stem
        book_author = author or epub_meta.get("author")
        book_series = series_name or epub_meta.get("series_name")
        book_order = order_in_series or epub_meta.get("order_in_series")

        # Create book in Neo4j
        book_id = await repo.create_book(
            title=book_title,
            series_name=book_series,
            order_in_series=book_order,
            author=book_author,
            genre=genre,
        )

        await repo.update_book_status(book_id, ProcessingStatus.INGESTING.value)

        # 1. Parse file into chapters
        chapters = await ingest_file(tmp_path)

        if not chapters:
            raise ValidationError("No chapters found in file")

        # Store chapters in Neo4j
        await repo.create_chapters(book_id, chapters)
        await repo.update_book_chapter_count(book_id, len(chapters))

        # Store paragraphs for each chapter
        for chapter in chapters:
            if chapter.paragraphs:
                await repo.create_paragraphs(book_id, chapter.number, chapter.paragraphs)

        # 2. Chunk each chapter
        await repo.update_book_status(book_id, ProcessingStatus.CHUNKING.value)
        all_chunks = []
        for chapter in chapters:
            chunks = chunk_chapter(chapter, book_id)
            all_chunks.extend(chunks)

        # Store chunks in Neo4j
        await repo.create_chunks(book_id, all_chunks)

        # 3. Regex extraction (Passe 0) -- FREE, instant
        regex_extractor = RegexExtractor.default()
        all_regex_matches = []
        for chapter in chapters:
            matches = regex_extractor.extract(chapter.text, chapter.number)
            all_regex_matches.extend(matches)

        # Store regex matches
        await repo.store_regex_matches(book_id, all_regex_matches)

        # Update status
        await repo.update_book_status(book_id, ProcessingStatus.COMPLETED.value)

        logger.info(
            "book_ingestion_completed",
            book_id=book_id,
            title=book_title,
            chapters=len(chapters),
            chunks=len(all_chunks),
            regex_matches=len(all_regex_matches),
        )

        return IngestionResult(
            book_id=book_id,
            title=book_title,
            chapters_found=len(chapters),
            chunks_created=len(all_chunks),
            regex_matches_total=len(all_regex_matches),
            status=ProcessingStatus.COMPLETED,
        )

    except (ValidationError, NotFoundError, ConflictError):
        raise
    except Exception as e:
        logger.exception("book_ingestion_failed", book_id=book_id)
        if book_id:
            await repo.update_book_status(book_id, ProcessingStatus.FAILED.value)
        raise ExtractionError("Ingestion failed") from e
    finally:
        # Cleanup temp file
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)


@router.get("", response_model=list[BookInfo], dependencies=[Depends(require_auth)])
async def list_books(
    driver: AsyncDriver = Depends(get_neo4j),
) -> list[BookInfo]:
    """List all books in the system."""
    repo = BookRepository(driver)
    results = await repo.list_books()
    books = []
    for row in results:
        b = dict(row["b"])
        books.append(
            BookInfo(
                id=b.get("id", ""),
                title=b.get("title", ""),
                series_name=b.get("series_name"),
                order_in_series=b.get("order_in_series"),
                author=b.get("author"),
                genre=b.get("genre", "litrpg"),
                total_chapters=b.get("total_chapters", 0),
                status=b.get("status", "pending"),
                chapters_processed=b.get("chapters_processed", 0),
                total_cost_usd=b.get("total_cost_usd", 0.0),
            )
        )
    return books


@router.get("/series", dependencies=[Depends(require_auth)])
async def list_series(
    driver: AsyncDriver = Depends(get_neo4j),
) -> list[dict]:
    """List all series."""
    repo = BookRepository(driver)
    return await repo.list_series()


@router.get("/series/{series_name}", dependencies=[Depends(require_auth)])
async def get_series(
    series_name: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get series info with books."""
    repo = BookRepository(driver)
    result = await repo.get_series(series_name)
    if not result:
        raise NotFoundError(f"Series '{series_name}' not found")
    return result


@router.get("/{book_id}", response_model=BookDetail, dependencies=[Depends(require_auth)])
async def get_book(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> BookDetail:
    """Get detailed book info with chapter list."""
    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise NotFoundError("Book not found")

    chapters_data = await repo.list_chapters(book_id)
    chapters = [
        ChapterInfo(
            number=dict(row["c"]).get("number", 0),
            title=dict(row["c"]).get("title", ""),
            word_count=dict(row["c"]).get("word_count", 0),
            chunk_count=row.get("chunk_count", 0),
            entity_count=dict(row["c"]).get("entity_count", 0),
            status=dict(row["c"]).get("status", "pending"),
            regex_matches=dict(row["c"]).get("regex_matches", 0),
        )
        for row in chapters_data
    ]

    return BookDetail(
        book=BookInfo(
            id=book.get("id", ""),
            title=book.get("title", ""),
            series_name=book.get("series_name"),
            order_in_series=book.get("order_in_series"),
            author=book.get("author"),
            genre=book.get("genre", "litrpg"),
            total_chapters=book.get("total_chapters", 0),
            status=book.get("status", "pending"),
            chapters_processed=book.get("chapters_processed", 0),
        ),
        chapters=chapters,
    )


@router.get("/{book_id}/stats", dependencies=[Depends(require_auth)])
async def get_book_stats(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get book processing statistics."""
    repo = BookRepository(driver)
    stats = await repo.get_book_stats(book_id)
    if not stats:
        raise NotFoundError("Book not found")
    return stats


@router.post(
    "/{book_id}/extract",
    response_model=JobEnqueuedResult,
    dependencies=[Depends(require_auth)],
)
async def extract_book(
    book_id: str,
    body: ExtractionRequest | None = None,
    driver: AsyncDriver = Depends(get_neo4j),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> JobEnqueuedResult:
    """Enqueue LLM extraction pipeline for an ingested book.

    Optionally pass ``{"chapters": [1, 3, 5]}`` in the request body
    to extract only specific chapters.  Omit or pass ``null`` to
    extract all chapters.

    Returns immediately with a job_id. The extraction runs in a
    background arq worker. Poll GET /books/{book_id}/jobs for status.
    The book status field in Neo4j is updated throughout processing.

    After extraction completes, an embedding job is automatically enqueued.
    """
    chapter_list = body.chapters if body else None

    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise NotFoundError("Book not found")

    current_status = book.get("status", "")
    if current_status not in ("completed", "extracted", "partial", "embedded"):
        raise ConflictError(
            f"Book status is '{current_status}'. "
            "Extraction requires ingestion to be completed first."
        )

    # Validate chapters exist before enqueueing
    chapters = await repo.get_chapters_for_extraction(
        book_id,
        chapters=chapter_list,
    )
    if not chapters:
        raise ValidationError("No chapter text found for the requested selection.")

    # Include chapter selection in job_id to avoid collision
    suffix = ""
    if chapter_list:
        suffix = f":{','.join(str(c) for c in sorted(chapter_list)[:5])}"
        if len(chapter_list) > 5:
            suffix += f"...({len(chapter_list)})"

    job = await arq_pool.enqueue_job(
        "process_book_extraction",
        book_id,
        book.get("genre", "litrpg"),
        book.get("series_name", "") or "",
        chapter_list,
        _queue_name="worldrag:arq",
        _job_id=f"extract:{book_id}{suffix}",
    )

    if job is None:
        raise ConflictError("Job already enqueued or could not be created.")

    logger.info(
        "book_extraction_enqueued",
        book_id=book_id,
        job_id=job.job_id,
        chapters=chapter_list,
    )

    return JobEnqueuedResult(
        book_id=book_id,
        job_id=job.job_id,
        status="enqueued",
        message="Extraction job enqueued. Poll GET /books/{book_id}/jobs for status.",
    )


@router.post(
    "/{book_id}/extract/v3",
    response_model=JobEnqueuedResult,
    dependencies=[Depends(require_auth)],
)
async def extract_book_v3(
    book_id: str,
    body: ExtractionRequestV3 | None = None,
    driver: AsyncDriver = Depends(get_neo4j),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> JobEnqueuedResult:
    """Enqueue V3 extraction pipeline for an ingested book.

    Uses the 6-phase layered pipeline (narrative -> genre -> series)
    with EntityRegistry for cross-chapter context accumulation.
    """
    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise NotFoundError("Book not found")

    current_status = book.get("status", "")
    if current_status not in ("completed", "extracted", "partial", "embedded"):
        raise ConflictError(
            f"Book status is '{current_status}'. "
            "Extraction requires ingestion to be completed first."
        )

    chapter_list = body.chapters if body else None
    language = body.language if body else "fr"
    genre = (body.genre if body else None) or book.get("genre", "litrpg")
    series_name = (body.series_name if body else None) or book.get("series_name", "") or ""

    chapters = await repo.get_chapters_for_extraction(book_id, chapters=chapter_list)
    if not chapters:
        raise ValidationError("No chapter text found for the requested selection.")

    suffix = ""
    if chapter_list:
        suffix = f":{','.join(str(c) for c in sorted(chapter_list)[:5])}"
        if len(chapter_list) > 5:
            suffix += f"...({len(chapter_list)})"

    job = await arq_pool.enqueue_job(
        "process_book_extraction_v3",
        book_id,
        genre,
        series_name,
        chapter_list,
        language,
        _queue_name="worldrag:arq",
        _job_id=f"extract-v3:{book_id}{suffix}",
    )

    if job is None:
        raise ConflictError("Job already enqueued or could not be created.")

    logger.info(
        "book_extraction_v3_enqueued",
        book_id=book_id,
        job_id=job.job_id,
        chapters=chapter_list,
        language=language,
    )

    return JobEnqueuedResult(
        book_id=book_id,
        job_id=job.job_id,
        status="enqueued",
        message="V3 extraction job enqueued. Poll GET /books/{book_id}/jobs for status.",
    )


@router.post(
    "/{book_id}/reprocess",
    response_model=JobEnqueuedResult,
    dependencies=[Depends(require_auth)],
)
async def reprocess_book(
    book_id: str,
    body: ReprocessRequest | None = None,
    driver: AsyncDriver = Depends(get_neo4j),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> JobEnqueuedResult:
    """Reprocess specific chapters/phases after ontology evolution.

    If chapter_range is provided, only those chapters are reprocessed.
    If changes are provided, auto-detects affected chapters.
    If neither, reprocesses all chapters.
    """
    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise NotFoundError("Book not found")

    current_status = book.get("status", "")
    if current_status not in ("extracted", "partial", "embedded"):
        raise ConflictError(
            f"Book status is '{current_status}'. Reprocessing requires extraction first."
        )

    # Serialize OntologyChange models to dicts for arq transport
    changes_dicts = (
        [c.model_dump() for c in body.changes] if body and body.changes else None
    )

    job = await arq_pool.enqueue_job(
        "process_book_reprocessing",
        book_id,
        body.chapter_range if body else None,
        changes_dicts,
        book.get("genre", "litrpg"),
        book.get("series_name", "") or "",
        _queue_name="worldrag:arq",
        _job_id=f"reprocess:{book_id}",
    )

    if job is None:
        raise ConflictError("Reprocessing job already enqueued or could not be created.")

    logger.info(
        "book_reprocessing_enqueued",
        book_id=book_id,
        job_id=job.job_id,
    )

    return JobEnqueuedResult(
        book_id=book_id,
        job_id=job.job_id,
        status="enqueued",
        message="Reprocessing job enqueued. Poll GET /books/{book_id}/jobs for status.",
    )


@router.get("/{book_id}/jobs", dependencies=[Depends(require_auth)])
async def get_book_jobs(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> dict:
    """Check the status of background jobs for a book.

    Returns job status from arq plus the current Neo4j book status.
    """
    from arq.jobs import Job

    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise NotFoundError("Book not found")

    extract_job = Job(f"extract:{book_id}", arq_pool)
    embed_job = Job(f"embed:{book_id}", arq_pool)

    extract_status = await extract_job.status()
    embed_status = await embed_job.status()

    return {
        "book_id": book_id,
        "book_status": book.get("status", "unknown"),
        "jobs": {
            "extraction": {
                "job_id": f"extract:{book_id}",
                "status": extract_status.value,
            },
            "embedding": {
                "job_id": f"embed:{book_id}",
                "status": embed_status.value,
            },
        },
    }


@router.delete("/{book_id}", dependencies=[Depends(require_auth)])
async def delete_book(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Delete a book and all associated data."""
    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise NotFoundError("Book not found")

    chapters_deleted = await repo.delete_book(book_id)
    return {
        "deleted": True,
        "book_id": book_id,
        "chapters_deleted": chapters_deleted,
    }
