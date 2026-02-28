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
import contextlib
import re
from functools import partial
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.schemas.book import ChapterData, ParagraphData, ParagraphType

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


# --- Structure-aware paragraph parsing ---

# Scene break patterns: just stars, dashes, spaced stars, or very short decorative text
_SCENE_BREAK_RE = re.compile(
    r"^[\s]*(\*\s*\*\s*\*|[*]{2,5}|[-]{2,5}|[—–]{2,5}|~{2,5}|[#]{2,5}|⁂)[\s]*$"
)

# Blue box markers (LitRPG system notifications)
_BLUE_BOX_RE = re.compile(
    r"^\[("
    r"Skill|Level|New Title|Title|Class|Compétence|Niveau|Titre|Classe"
    r"|Profession|Bloodline|Quest|Achievement|System|Warning|Evolution"
    r"|Stat|Status|Notification"
    r")\b",
    re.IGNORECASE,
)

# Dialogue starters
_DIALOGUE_STARTERS = ("«", "\u201c", "\u201d", "—", "–")

# Speaker extraction from French dialogue: "dit Jake", "murmura Caroline", "cria-t-il"
_SPEAKER_RE = re.compile(
    '(?:\u00bb|\u201d|")'
    r"\s*"
    r"(?:dit|murmura|chuchota|cria|hurla|demanda|r\u00e9pondit|souffla|grommela|lan\u00e7a"
    r"|s['\u2019]exclama|ajouta|reprit|continua|expliqua|affirma|soupira|g\u00e9mit"
    r"|ordonna|sugg\u00e9ra|protesta|marmonna|annon\u00e7a|d\u00e9clara|interrogea|confirma"
    r"|r\u00e9torqua|proposa|insista|objecta|admit|conc\u00e9da|pr\u00e9cisa|observa)"
    r"(?:-t-(?:il|elle|on))?"
    r"\s+([A-Z\u00c0-\u017d][a-z\u00e0-\u017e]+(?:\s+[A-Z\u00c0-\u017d][a-z\u00e0-\u017e]+)?)",
    re.UNICODE,
)

_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "div", "blockquote", "li"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

# Sentence splitting: split on .!? followed by space or end, ignoring common abbreviations
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s|$)")


def _classify_block_text(tag: str, text: str) -> ParagraphType:
    """Classify an HTML block element into a ParagraphType.

    Args:
        tag: The HTML tag name (e.g. 'p', 'h1', 'div').
        text: The text content of the element.

    Returns:
        The classified ParagraphType.
    """
    # Headers
    if tag in _HEADING_TAGS:
        return ParagraphType.HEADER

    # Scene breaks: very short decorative separators
    stripped = text.strip()
    if _SCENE_BREAK_RE.match(stripped):
        return ParagraphType.SCENE_BREAK

    # Blue boxes: LitRPG system notifications in brackets
    if _BLUE_BOX_RE.match(stripped):
        return ParagraphType.BLUE_BOX

    # Dialogue: starts with quote marks or dashes
    if stripped and (
        stripped[0] in _DIALOGUE_STARTERS
        or (stripped.startswith('"') and not stripped.startswith('""'))
    ):
        return ParagraphType.DIALOGUE

    return ParagraphType.NARRATION


def _extract_speaker(text: str) -> str | None:
    """Try to extract speaker name from dialogue text.

    Looks for French dialogue attribution patterns like
    'dit Jake', 'murmura Caroline', 'cria-t-il'.

    Returns:
        The speaker name if found, None otherwise.
    """
    match = _SPEAKER_RE.search(text)
    if match:
        return match.group(1)
    return None


def _count_sentences(text: str) -> int:
    """Count sentences in text using simple punctuation splitting."""
    if not text.strip():
        return 0
    parts = _SENTENCE_SPLIT_RE.split(text)
    # Filter out empty parts
    return len([p for p in parts if p.strip()])


def _build_paragraphs_from_html(html: str) -> list[ParagraphData]:
    """Parse HTML content into a list of typed paragraphs.

    Walks the DOM finding block-level elements (p, h1-h6, div, blockquote, li),
    classifies each one, and tracks character offsets for grounding.

    Args:
        html: Raw HTML content of a chapter.

    Returns:
        List of ParagraphData with types, offsets, and metadata.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    paragraphs: list[ParagraphData] = []
    running_offset = 0
    idx = 0

    # Semantic containers whose children we process directly — skip nested
    # blocks inside these. Generic wrappers like <div> are NOT in this set
    # because EPUBs commonly wrap multiple <p> elements in <div>s.
    _semantic_containers = {"blockquote", "li"}

    for element in soup.find_all(_BLOCK_TAGS):
        # Skip elements nested inside semantic containers
        if element.parent and element.parent.name in _semantic_containers:
            continue
        # Skip wrapper divs that contain other block-level children
        if element.name == "div" and element.find(_BLOCK_TAGS - {"div"}):
            continue

        text = element.get_text(strip=True)
        if not text:
            continue

        tag = element.name or "p"
        para_type = _classify_block_text(tag, text)

        # Extract speaker for dialogue
        speaker = None
        if para_type == ParagraphType.DIALOGUE:
            speaker = _extract_speaker(text)

        char_start = running_offset
        char_end = char_start + len(text)

        paragraphs.append(
            ParagraphData(
                index=idx,
                type=para_type,
                text=text,
                html=str(element),
                char_start=char_start,
                char_end=char_end,
                speaker=speaker,
                sentence_count=_count_sentences(text),
                word_count=len(text.split()),
            )
        )

        idx += 1
        running_offset = char_end + 1  # +1 for \n separator

    return paragraphs


# --- ePub metadata extraction ---

# Patterns for non-chapter items (TOC, cover, copyright, etc.)
_SKIP_FILENAME_PATTERNS = re.compile(
    r"(?:^|/)(?:toc|nav|cover|copyright|colophon|title(?:page)?|dedication|about|"
    r"also[-_]by|acknowledgment|appendix|index|glossary|author[-_]note|"
    r"frontmatter|backmatter|halftitle)(?:\.x?html?)?$",
    re.IGNORECASE,
)

_SKIP_TITLE_PATTERNS = re.compile(
    r"^\s*(?:sommaire|table\s+(?:of\s+contents|des\s+mati[eè]res)|"
    r"contents|copyright|couverture|cover|d[eé]dicace|remerciements|"
    r"acknowledgments?|also\s+by|about\s+the\s+author|glossaire|glossary|"
    r"titre|title\s*page|table\s+of\s+contents)\s*$",
    re.IGNORECASE,
)


def _is_epub_boilerplate(item_name: str, first_heading: str, text: str) -> bool:
    """Check if an epub item is boilerplate (TOC, cover, copyright, etc.)."""
    # Check filename
    if _SKIP_FILENAME_PATTERNS.search(item_name):
        return True
    # Check first heading text
    if first_heading and _SKIP_TITLE_PATTERNS.match(first_heading):
        return True
    # Check if content is mostly links (typical of TOC pages)
    # Count links vs total paragraphs — TOC pages are 80%+ links
    if text.count("\n") > 5:
        lines = text.strip().split("\n")
        short_lines = sum(1 for ln in lines if len(ln.strip()) < 80)
        if short_lines > len(lines) * 0.8 and len(lines) > 10:
            return True
    return False


async def extract_epub_metadata(file_path: Path) -> dict[str, Any]:
    """Extract OPF/Dublin Core metadata from an epub file.

    Reads the epub's OPF package metadata without parsing full chapter content.
    Returns a dict with keys: title, author, language, date, description, publisher, subject.
    Values are strings or None if not present.
    """
    from ebooklib import epub

    book = await asyncio.to_thread(epub.read_epub, str(file_path))

    def _first_dc(field: str) -> str | None:
        """Get first Dublin Core metadata value."""
        values = book.get_metadata("DC", field)
        if values:
            val = values[0]
            # ebooklib returns tuples: (value, attributes)
            return val[0] if isinstance(val, tuple) else str(val)
        return None

    metadata: dict[str, Any] = {
        "title": _first_dc("title"),
        "author": _first_dc("creator"),
        "language": _first_dc("language"),
        "date": _first_dc("date"),
        "description": _first_dc("description"),
        "publisher": _first_dc("publisher"),
        "subject": _first_dc("subject"),
    }

    # Try to extract series info from calibre metadata (common for ebooks)
    opf_meta = book.get_metadata("OPF", "meta")
    for _val, attrs in opf_meta:
        if attrs.get("name") == "calibre:series":
            metadata["series_name"] = attrs.get("content")
        elif attrs.get("name") == "calibre:series_index":
            with contextlib.suppress(ValueError, TypeError):
                metadata["order_in_series"] = int(float(attrs.get("content", "0")))

    logger.info(
        "epub_metadata_extracted",
        file=str(file_path),
        title=metadata.get("title"),
        author=metadata.get("author"),
        language=metadata.get("language"),
    )
    return metadata


# --- ePub parsing ---


async def parse_epub(file_path: Path) -> tuple[list[ChapterData], str]:
    """Parse an ePub file into chapters, preserving original XHTML.

    Uses ebooklib to read the spine, then BeautifulSoup to extract
    text from each HTML chapter document. Filters out non-chapter items
    like TOC, cover, copyright, etc.

    Returns:
        Tuple of (chapters, epub_css) where epub_css is all stylesheets concatenated.
    """
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    book = await asyncio.to_thread(epub.read_epub, str(file_path))

    # Extract all CSS from epub stylesheets
    css_parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_STYLE):
        try:
            css_text = item.get_content().decode("utf-8", errors="replace")
            if css_text.strip():
                css_parts.append(css_text)
        except Exception:
            continue
    epub_css = "\n\n".join(css_parts)

    chapters: list[ChapterData] = []
    chapter_num = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        # Skip EPUB3 navigation documents
        item_props = item.get_properties() if hasattr(item, "get_properties") else []
        if item_props and "nav" in item_props:
            continue

        content = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(content, "html.parser")

        # Build paragraphs from HTML structure
        paragraphs = _build_paragraphs_from_html(content)

        # Reconstruct text from paragraphs (backward compatible)
        text = "\n".join(p.text for p in paragraphs)

        # Skip very short documents (likely TOC, copyright, etc.)
        if len(text.strip()) < 200:
            continue

        # Extract heading for boilerplate detection
        heading = soup.find(["h1", "h2", "h3"])
        heading_text = heading.get_text(strip=True) if heading else ""

        # Skip boilerplate items (TOC, cover, copyright, etc.)
        item_name = item.get_name() if hasattr(item, "get_name") else ""
        if _is_epub_boilerplate(item_name, heading_text, text):
            logger.debug("epub_skip_boilerplate", item=item_name, heading=heading_text)
            continue

        # Extract full body inner HTML (preserves all structural elements)
        body = soup.find("body")
        if body:
            chapter_xhtml = "".join(str(child) for child in body.children)
        else:
            # Fallback: use everything (minus <html>/<head> wrappers)
            chapter_xhtml = content

        chapter_num += 1
        title = ""

        if heading_text:
            title = heading_text
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
                xhtml=chapter_xhtml,
                paragraphs=paragraphs,
            )
        )

    logger.info("epub_parsed", file=str(file_path), chapters=len(chapters), css_bytes=len(epub_css))
    return chapters, epub_css


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


async def ingest_file(file_path: Path) -> tuple[list[ChapterData], str]:
    """Parse a book file into chapters.

    Dispatches to the appropriate parser based on file extension.

    Args:
        file_path: Path to the book file (ePub, PDF, or TXT).

    Returns:
        Tuple of (chapters, epub_css). epub_css is empty for non-epub formats.

    Raises:
        ValueError: If file format is not supported.
    """
    suffix = file_path.suffix.lower()

    if suffix not in PARSERS:
        supported = ", ".join(PARSERS.keys())
        raise ValueError(f"Unsupported file format: {suffix}. Supported: {supported}")

    logger.info("ingestion_started", file=str(file_path), format=suffix)

    epub_css = ""
    if suffix == ".epub":
        chapters, epub_css = await parse_epub(file_path)
    else:
        parser = PARSERS[suffix]
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
    return chapters, epub_css
