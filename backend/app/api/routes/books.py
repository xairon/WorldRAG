"""Book management API routes.

Handles book upload, listing, deletion, and processing status.
Upload triggers the ingestion pipeline: parse → chunk → regex extract → store.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.dependencies import get_neo4j
from app.core.logging import get_logger
from app.repositories.book_repo import BookRepository
from app.schemas.book import (
    BookDetail,
    BookInfo,
    ChapterInfo,
    ExtractionResult,
    IngestionResult,
    ProcessingStatus,
)
from app.services.chunking import chunk_chapter
from app.services.extraction.regex_extractor import RegexExtractor
from app.services.graph_builder import build_book_graph
from app.services.ingestion import ingest_file

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)
router = APIRouter(prefix="/books", tags=["books"])

# Supported file extensions
ALLOWED_EXTENSIONS = {".epub", ".pdf", ".txt"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("", response_model=IngestionResult)
async def upload_book(
    file: UploadFile,
    title: str | None = None,
    series_name: str | None = None,
    order_in_series: int | None = None,
    author: str | None = None,
    genre: str = "litrpg",
    driver: AsyncDriver = Depends(get_neo4j),
) -> IngestionResult:
    """Upload a book file and run the ingestion pipeline.

    Pipeline: Parse file → Split chapters → Chunk → Regex extract → Store in Neo4j.

    Supports ePub, PDF, and TXT formats.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {suffix}. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
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

    try:
        await repo.update_book_status(book_id, ProcessingStatus.INGESTING.value)

        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        # 1. Parse file into chapters
        chapters = await ingest_file(tmp_path)

        if not chapters:
            raise HTTPException(status_code=422, detail="No chapters found in file")

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

        # 3. Regex extraction (Passe 0) — FREE, instant
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

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("book_ingestion_failed", book_id=book_id, error=str(e))
        await repo.update_book_status(book_id, ProcessingStatus.FAILED.value)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}") from e
    finally:
        # Cleanup temp file
        with contextlib.suppress(Exception):
            tmp_path.unlink(missing_ok=True)  # noqa: ASYNC240


@router.get("", response_model=list[BookInfo])
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


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> BookDetail:
    """Get detailed book info with chapter list."""
    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

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


@router.get("/{book_id}/stats")
async def get_book_stats(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Get book processing statistics."""
    repo = BookRepository(driver)
    stats = await repo.get_book_stats(book_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Book not found")
    return stats


@router.post("/{book_id}/extract", response_model=ExtractionResult)
async def extract_book(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> ExtractionResult:
    """Trigger LLM extraction pipeline for an ingested book.

    Runs the 4-pass LangExtract pipeline + reconciliation + Neo4j persistence
    for every chapter. This is the expensive step (LLM calls).

    The book must already be ingested (status >= 'completed').
    """
    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    current_status = book.get("status", "")
    if current_status not in ("completed", "extracted", "partial"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Book status is '{current_status}'. "
                "Extraction requires ingestion to be completed first."
            ),
        )

    # Retrieve chapter texts and regex data
    chapters = await repo.get_chapters_for_extraction(book_id)
    if not chapters:
        raise HTTPException(
            status_code=422,
            detail="No chapter text found. Re-ingest the book.",
        )

    chapter_regex = await repo.get_chapter_regex_json(book_id)

    try:
        result = await build_book_graph(
            driver=driver,
            book_repo=repo,
            book_id=book_id,
            chapters=chapters,
            genre=book.get("genre", "litrpg"),
            series_name=book.get("series_name", ""),
            chapter_regex_matches=chapter_regex,
        )

        logger.info(
            "book_extraction_completed",
            book_id=book_id,
            **result,
        )

        return ExtractionResult(
            book_id=book_id,
            chapters_processed=result["chapters_processed"],
            chapters_failed=result["chapters_failed"],
            failed_chapters=result["failed_chapters"],
            total_entities=result["total_entities"],
            status=result["status"],
        )

    except Exception as e:
        logger.exception(
            "book_extraction_failed",
            book_id=book_id,
            error=str(e),
        )
        await repo.update_book_status(book_id, ProcessingStatus.FAILED.value)
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {e}",
        ) from e


@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Delete a book and all associated data."""
    repo = BookRepository(driver)
    book = await repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    chapters_deleted = await repo.delete_book(book_id)
    return {
        "deleted": True,
        "book_id": book_id,
        "chapters_deleted": chapters_deleted,
    }
