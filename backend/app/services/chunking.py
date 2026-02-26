"""Structure-aware chunking service.

Splits chapters into chunks suitable for embedding and extraction.
Respects paragraph boundaries and maintains source grounding offsets.

Strategy:
- Primary unit: chapter (each chapter is processed independently)
- Chunk size: ~1000 tokens (configurable), soft boundary at paragraphs
- Overlap: 100 tokens between chunks for context continuity
- Preserves exact character offsets for source grounding
"""

from __future__ import annotations

import re

from app.core.cost_tracker import count_tokens
from app.core.logging import get_logger
from app.schemas.book import ChapterData, ChunkData

logger = get_logger(__name__)

DEFAULT_CHUNK_SIZE = 1000  # target tokens per chunk
DEFAULT_OVERLAP = 100  # overlap tokens between chunks
MIN_CHUNK_SIZE = 200  # minimum tokens for a chunk


def chunk_chapter(
    chapter: ChapterData,
    book_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[ChunkData]:
    """Split a chapter into overlapping chunks.

    Respects paragraph boundaries: never splits mid-paragraph.
    Each chunk includes character offsets for source grounding.

    Args:
        chapter: Chapter data with full text.
        book_id: Book identifier for chunk metadata.
        chunk_size: Target tokens per chunk.
        overlap: Overlap tokens between consecutive chunks.

    Returns:
        List of ChunkData with text, position, and offset information.
    """
    text = chapter.text
    if not text.strip():
        return []

    # Use structured paragraphs if available (V2 epub), else fall back to regex split
    if chapter.paragraphs:
        paragraphs = [
            (p.text, p.char_start, p.char_end)
            for p in chapter.paragraphs
            if p.text.strip()  # skip empty/scene-break paragraphs
        ]
    else:
        paragraphs = _split_paragraphs(text)

    if not paragraphs:
        return []

    chunks: list[ChunkData] = []
    current_paragraphs: list[tuple[str, int, int]] = []  # (text, start_offset, end_offset)
    current_tokens = 0

    for para_text, para_start, para_end in paragraphs:
        para_tokens = count_tokens(para_text)

        # If single paragraph exceeds chunk size, split it by sentences
        if para_tokens > chunk_size and not current_paragraphs:
            sentence_chunks = _split_long_paragraph(
                para_text, para_start, chapter.number, book_id, chunk_size, len(chunks)
            )
            chunks.extend(sentence_chunks)
            continue

        # If adding this paragraph exceeds limit, finalize current chunk
        if current_tokens + para_tokens > chunk_size and current_paragraphs:
            chunk = _create_chunk(
                current_paragraphs, chapter.number, book_id, len(chunks), current_tokens
            )
            chunks.append(chunk)

            # Keep last paragraph(s) as overlap for next chunk
            overlap_paras: list[tuple[str, int, int]] = []
            overlap_tokens = 0
            for p in reversed(current_paragraphs):
                p_tokens = count_tokens(p[0])
                if overlap_tokens + p_tokens > overlap:
                    break
                overlap_paras.insert(0, p)
                overlap_tokens += p_tokens

            current_paragraphs = overlap_paras
            current_tokens = overlap_tokens

        current_paragraphs.append((para_text, para_start, para_end))
        current_tokens += para_tokens

    # Don't forget the last chunk
    if current_paragraphs and current_tokens >= MIN_CHUNK_SIZE:
        chunk = _create_chunk(
            current_paragraphs, chapter.number, book_id, len(chunks), current_tokens
        )
        chunks.append(chunk)
    elif current_paragraphs and chunks:
        # Merge small remainder into last chunk
        last = chunks[-1]
        extra_text = "\n\n".join(p[0] for p in current_paragraphs)
        merged_text = last.text + "\n\n" + extra_text
        chunks[-1] = ChunkData(
            text=merged_text,
            position=last.position,
            chapter_number=last.chapter_number,
            book_id=last.book_id,
            token_count=count_tokens(merged_text),
            char_offset_start=last.char_offset_start,
            char_offset_end=current_paragraphs[-1][2],
        )

    logger.info(
        "chapter_chunked",
        chapter=chapter.number,
        book_id=book_id,
        chunks=len(chunks),
        avg_tokens=sum(c.token_count for c in chunks) // max(len(chunks), 1),
    )
    return chunks


def _split_paragraphs(text: str) -> list[tuple[str, int, int]]:
    """Split text into paragraphs with their character offsets.

    Returns list of (paragraph_text, start_offset, end_offset).
    """
    paragraphs: list[tuple[str, int, int]] = []
    current_start = 0

    for match in re.finditer(r"\n\s*\n", text):
        para_text = text[current_start : match.start()].strip()
        if para_text:
            paragraphs.append((para_text, current_start, match.start()))
        current_start = match.end()

    # Last paragraph
    remaining = text[current_start:].strip()
    if remaining:
        paragraphs.append((remaining, current_start, len(text)))

    return paragraphs


def _create_chunk(
    paragraphs: list[tuple[str, int, int]],
    chapter_number: int,
    book_id: str,
    position: int,
    token_count: int,
) -> ChunkData:
    """Create a ChunkData from accumulated paragraphs."""
    text = "\n\n".join(p[0] for p in paragraphs)
    return ChunkData(
        text=text,
        position=position,
        chapter_number=chapter_number,
        book_id=book_id,
        token_count=token_count,
        char_offset_start=paragraphs[0][1],
        char_offset_end=paragraphs[-1][2],
    )


def _split_long_paragraph(
    text: str,
    base_offset: int,
    chapter_number: int,
    book_id: str,
    chunk_size: int,
    start_position: int,
) -> list[ChunkData]:
    """Split an oversized paragraph into sentence-level chunks."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[ChunkData] = []
    current_text = ""
    current_start = base_offset
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = count_tokens(sentence)

        if current_tokens + sent_tokens > chunk_size and current_text:
            chunks.append(
                ChunkData(
                    text=current_text.strip(),
                    position=start_position + len(chunks),
                    chapter_number=chapter_number,
                    book_id=book_id,
                    token_count=current_tokens,
                    char_offset_start=current_start,
                    char_offset_end=current_start + len(current_text),
                )
            )
            current_start = current_start + len(current_text)
            current_text = ""
            current_tokens = 0

        current_text += (" " if current_text else "") + sentence
        current_tokens += sent_tokens

    if current_text.strip():
        chunks.append(
            ChunkData(
                text=current_text.strip(),
                position=start_position + len(chunks),
                chapter_number=chapter_number,
                book_id=book_id,
                token_count=current_tokens,
                char_offset_start=current_start,
                char_offset_end=current_start + len(current_text),
            )
        )

    return chunks
