"""Book ingestion service — Parse ePub/PDF/TXT into chapters.

Handles multiple file formats and extracts structured chapter data
from raw book files. The primary input for the WorldRAG pipeline.

Supported formats:
- ePub: Parsed via ebooklib + BeautifulSoup (HTML chapters)
- PDF: Parsed via pdfplumber (page-based, heuristic chapter detection)
- TXT: Plain text with chapter delimiter detection
"""

from __future__ import annotations

import asyncio
import re
from functools import partial
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.schemas.book import ChapterData

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

# --- Chapter detection patterns ---

CHAPTER_PATTERNS = [
    # "Chapter 1", "Chapter 1: Title", "CHAPTER ONE"
    re.compile(
        r"^\s*(?:chapter|chapitre)\s+(\d+|[a-z]+)(?:\s*[:\-–—]\s*(.+?))?$",
        re.IGNORECASE | re.MULTILINE,
    ),
    # "Ch. 1", "Ch 42"
    re.compile(r"^\s*ch\.?\s*(\d+)(?:\s*[:\-–—]\s*(.+?))?$", re.IGNORECASE | re.MULTILINE),
    # Standalone numbers as chapter markers (common in web novels)
    re.compile(r"^(\d{1,4})\.\s+(.+?)$", re.MULTILINE),
]

# Number words for "Chapter One" style
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "prologue": 0,
    "epilogue": 9999,
}


def _parse_chapter_number(raw: str) -> int:
    """Parse chapter number from string (digit or word)."""
    raw = raw.strip().lower()
    if raw.isdigit():
        return int(raw)
    return NUMBER_WORDS.get(raw, 0)


# --- ePub parsing ---


async def parse_epub(file_path: Path) -> list[ChapterData]:
    """Parse an ePub file into chapters.

    Uses ebooklib to read the spine, then BeautifulSoup to extract
    text from each HTML chapter document.
    """
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    book = await asyncio.to_thread(epub.read_epub, str(file_path))
    chapters: list[ChapterData] = []
    chapter_num = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        content = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        # Skip very short documents (likely TOC, copyright, etc.)
        if len(text.strip()) < 200:
            continue

        chapter_num += 1
        title = ""

        # Try to extract chapter title from first heading
        heading = soup.find(["h1", "h2", "h3"])
        if heading:
            title = heading.get_text(strip=True)
            # If title looks like "Chapter X: Title", parse the number
            for pattern in CHAPTER_PATTERNS:
                match = pattern.match(title)
                if match:
                    parsed_num = _parse_chapter_number(match.group(1))
                    if parsed_num > 0:
                        chapter_num = parsed_num
                    if match.lastindex and match.lastindex >= 2 and match.group(2):
                        title = match.group(2).strip()
                    break

        chapters.append(
            ChapterData(
                number=chapter_num,
                title=title,
                text=text,
            )
        )

    logger.info("epub_parsed", file=str(file_path), chapters=len(chapters))
    return chapters


# --- PDF parsing ---


async def parse_pdf(file_path: Path) -> list[ChapterData]:
    """Parse a PDF file into chapters.

    Uses pdfplumber for text extraction, then applies heuristic
    chapter boundary detection based on chapter heading patterns.
    """

    def _read_pdf() -> str:
        import pdfplumber

        text_parts: list[str] = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    full_text = await asyncio.to_thread(_read_pdf)

    if not full_text.strip():
        logger.warning("pdf_empty", file=str(file_path))
        return []

    chapters = _split_text_into_chapters(full_text)
    logger.info("pdf_parsed", file=str(file_path), chapters=len(chapters))
    return chapters


# --- TXT parsing ---


async def parse_txt(file_path: Path) -> list[ChapterData]:
    """Parse a plain text file into chapters.

    Detects chapter boundaries using heading patterns.
    If no chapter markers found, treats the entire text as one chapter.
    """
    text = await asyncio.to_thread(
        partial(file_path.read_text, encoding="utf-8", errors="replace"),
    )

    if not text.strip():
        logger.warning("txt_empty", file=str(file_path))
        return []

    chapters = _split_text_into_chapters(text)
    logger.info("txt_parsed", file=str(file_path), chapters=len(chapters))
    return chapters


# --- Shared chapter splitting ---


def _split_text_into_chapters(text: str) -> list[ChapterData]:
    """Split a full text into chapters using heading pattern detection.

    Returns at least one chapter even if no markers are found.
    """
    # Find all chapter boundary positions
    boundaries: list[tuple[int, int, str]] = []  # (position, chapter_num, title)

    for pattern in CHAPTER_PATTERNS:
        for match in pattern.finditer(text):
            num = _parse_chapter_number(match.group(1))
            title = ""
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                title = match.group(2).strip()
            boundaries.append((match.start(), num, title))

    # Deduplicate and sort by position
    boundaries.sort(key=lambda x: x[0])

    # Remove boundaries too close together (likely false positives)
    if boundaries:
        filtered = [boundaries[0]]
        for b in boundaries[1:]:
            if b[0] - filtered[-1][0] > 500:  # at least 500 chars apart
                filtered.append(b)
        boundaries = filtered

    # If no chapters found, treat entire text as chapter 1
    if not boundaries:
        return [
            ChapterData(
                number=1,
                title="",
                text=text.strip(),
                start_offset=0,
            )
        ]

    # Split text at boundaries
    chapters: list[ChapterData] = []
    for i, (pos, num, title) in enumerate(boundaries):
        end_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        chapter_text = text[pos:end_pos].strip()

        if len(chapter_text) < 100:  # skip very short fragments
            continue

        chapters.append(
            ChapterData(
                number=num if num > 0 else i + 1,
                title=title,
                text=chapter_text,
                start_offset=pos,
            )
        )

    return chapters


# --- Main entry point ---


PARSERS = {
    ".epub": parse_epub,
    ".pdf": parse_pdf,
    ".txt": parse_txt,
}


async def ingest_file(file_path: Path) -> list[ChapterData]:
    """Parse a book file into chapters.

    Dispatches to the appropriate parser based on file extension.

    Args:
        file_path: Path to the book file (ePub, PDF, or TXT).

    Returns:
        List of ChapterData objects.

    Raises:
        ValueError: If file format is not supported.
    """
    suffix = file_path.suffix.lower()
    parser = PARSERS.get(suffix)

    if parser is None:
        supported = ", ".join(PARSERS.keys())
        raise ValueError(f"Unsupported file format: {suffix}. Supported: {supported}")

    logger.info("ingestion_started", file=str(file_path), format=suffix)
    chapters = await parser(file_path)

    # Ensure chapter numbers are sequential if they're all 0 or duplicated
    seen_nums = {c.number for c in chapters}
    if len(seen_nums) < len(chapters):
        for i, chapter in enumerate(chapters):
            chapter.number = i + 1

    logger.info(
        "ingestion_completed",
        file=str(file_path),
        chapters=len(chapters),
        total_words=sum(c.word_count for c in chapters),
    )
    return chapters
