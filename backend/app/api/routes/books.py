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
from app.services.chunking import chunk_chapter
from app.services.extraction.regex_extractor import RegexExtractor
from app.services.ingestion import ingest_file

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

    # Use filename as title if not provided
    book_title = title or Path(file.filename).stem

    # Create book in Neo4j
    book_id = await repo.create_book(
        title=book_title,
        series_name=series_name,
        order_in_series=order_in_series,
        author=author,
        genre=genre,
    )

    tmp_path: Path | None = None

    try:
        await repo.update_book_status(book_id, ProcessingStatus.INGESTING.value)

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

        # 1. Parse file into chapters
        chapters = await ingest_file(tmp_path)

        if not chapters:
            raise ValidationError("No chapters found in file")

        # Store chapters in Neo4j
        await repo.create_chapters(book_id, chapters)
        await repo.update_book_chapter_count(book_id, len(chapters))

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
            )
        )
    return books


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
    driver: AsyncDriver = Depends(get_neo4j),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> JobEnqueuedResult:
    """Enqueue LLM extraction pipeline for an ingested book.

    Returns immediately with a job_id. The extraction runs in a
    background arq worker. Poll GET /books/{book_id}/jobs for status.
    The book status field in Neo4j is updated throughout processing.

    After extraction completes, an embedding job is automatically enqueued.
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

    # Validate chapters exist before enqueueing
    chapters = await repo.get_chapters_for_extraction(book_id)
    if not chapters:
        raise ValidationError("No chapter text found. Re-ingest the book.")

    job = await arq_pool.enqueue_job(
        "process_book_extraction",
        book_id,
        book.get("genre", "litrpg"),
        book.get("series_name", "") or "",
        _queue_name="worldrag:arq",
        _job_id=f"extract:{book_id}",
    )

    logger.info("book_extraction_enqueued", book_id=book_id, job_id=job.job_id)

    return JobEnqueuedResult(
        book_id=book_id,
        job_id=job.job_id,
        status="enqueued",
        message="Extraction job enqueued. Poll GET /books/{book_id}/jobs for status.",
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
