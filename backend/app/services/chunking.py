"""Narrative-aware chunking service.

Splits chapters into chunks suitable for embedding and extraction.
Respects paragraph boundaries, scene breaks, and temporal/location shifts.

Strategy:
- Primary unit: chapter (each chapter is processed independently)
- Chunk size: ~1000 tokens (configurable), soft boundary at paragraphs
- Overlap: 100 tokens between chunks for context continuity
- Prefers splitting at scene boundaries (explicit breaks, time jumps,
  location changes) over arbitrary paragraph boundaries
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

# --- Scene boundary detection patterns ---

# Explicit scene dividers: ***, ---, * * *, ###, ~~~, etc.
_SCENE_DIVIDER_RE = re.compile(
    r"^[ \t]*(?:"
    r"\*\s*\*\s*\*"      # * * * or ***
    r"|---+"              # --- or longer
    r"|===+"              # === or longer
    r"|~~~+"              # ~~~ or longer
    r"|#{1,3}\s*$"        # # or ## or ### (bare heading markers)
    r"|[◆●■▪]"           # decorative dividers
    r")[ \t]*$",
    re.MULTILINE,
)

# Time jump phrases (at start of paragraph or after dialogue)
_TIME_JUMP_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"(?:The\s+)?(?:next|following)\s+(?:morning|day|evening|night|week|hour)"
    r"|(?:Three|Two|Four|Five|Six|Seven|Several|A\s+few|Many)\s+"
    r"(?:days?|hours?|weeks?|months?|minutes?|years?)\s+(?:later|passed|went\s+by)"
    r"|(?:Hours?|Days?|Weeks?|Months?|Minutes?)\s+(?:later|passed)"
    r"|When\s+(?:they|he|she|it|we|I)\s+(?:arrived|returned|woke|finally)"
    r"|By\s+the\s+time"
    r"|(?:Much|Some\s+time|A\s+long\s+time|Not\s+long)\s+later"
    r"|It\s+was(?:n't)?\s+(?:long|until|nearly|almost|well\s+past)"
    r"|Dawn\s+(?:broke|came|arrived)"
    r"|(?:Morning|Night|Dusk|Twilight)\s+(?:came|fell|arrived|found)"
    r")",
    re.IGNORECASE,
)

# Location change phrases (at start of paragraph)
_LOCATION_CHANGE_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"Back\s+(?:at|in|inside|outside)\s+(?:the|his|her|their)"
    r"|(?:In|Inside|Outside|Beneath|Above|Beyond|Across|Within)\s+the\s+"
    r"|(?:They|He|She|I|We)\s+(?:entered|stepped\s+into|arrived\s+at|reached|approached)"
    r"|The\s+(?:room|hall|cave|dungeon|forest|city|camp|tent|tower|castle|village)"
    r"\s+(?:was|looked|felt|smelled)"
    r")",
    re.IGNORECASE,
)


# --- POV / character shift detection ---

# Capitalized proper names appearing as sentence subjects (word at start or after period/newline)
_PROPER_NAME_RE = re.compile(
    r"(?:^|(?<=\.\s)|(?<=\n))([A-Z][a-z]{2,})",
)

# Common non-name capitalized words to exclude
_NON_NAME_WORDS = frozenset({
    "The", "This", "That", "These", "Those", "There", "Then", "They",
    "Their", "What", "When", "Where", "Which", "While", "Who", "Why",
    "How", "His", "Her", "Its", "Our", "She", "But", "And", "For",
    "Not", "With", "From", "Into", "After", "Before", "Between",
    "Under", "Over", "Just", "Only", "Every", "Each", "Some", "Any",
    "All", "Most", "Many", "Much", "Such", "Very", "Still", "Even",
    "Now", "Here", "Back", "Down", "Once", "Soon", "Already",
    "Something", "Nothing", "Everything", "Everyone", "Someone",
    "Nobody", "Anything", "However", "Perhaps", "Maybe", "Another",
    "Without", "Within", "Beyond", "Above", "Below", "Around",
})


def _extract_paragraph_names(para_text: str) -> set[str]:
    """Extract likely character names from a paragraph.

    Finds capitalized words that appear in subject position (start of
    sentence or paragraph) and are not common English words.
    """
    names: set[str] = set()
    for m in _PROPER_NAME_RE.finditer(para_text):
        word = m.group(1)
        if word not in _NON_NAME_WORDS:
            names.add(word)
    return names


def _detect_pov_shifts(text: str) -> set[int]:
    """Detect POV/character shifts between paragraphs.

    Compares the dominant character name in each paragraph against a
    sliding window of the previous 3 paragraphs. If a paragraph's
    first subject name has not appeared in the recent window, it is
    flagged as a potential scene boundary (POV shift).

    This catches cases like paragraphs 1-5 mentioning "Jake" repeatedly,
    then paragraph 6 starting with "William looked at his forge".

    Returns:
        Set of character offsets marking detected POV shift boundaries.
    """
    # Split into paragraphs with offsets
    paragraphs: list[tuple[str, int]] = []
    current_start = 0
    for m in re.finditer(r"\n\s*\n", text):
        para_text = text[current_start:m.start()].strip()
        if para_text:
            paragraphs.append((para_text, current_start))
        current_start = m.end()
    remaining = text[current_start:].strip()
    if remaining:
        paragraphs.append((remaining, current_start))

    if len(paragraphs) < 4:
        return set()

    # Extract names for each paragraph
    para_names: list[set[str]] = [_extract_paragraph_names(p) for p, _ in paragraphs]

    boundaries: set[int] = set()
    window_size = 3

    for i in range(window_size, len(paragraphs)):
        current_names = para_names[i]
        if not current_names:
            continue

        # Build the recent window of names from previous paragraphs
        window_names: set[str] = set()
        for j in range(max(0, i - window_size), i):
            window_names.update(para_names[j])

        if not window_names:
            continue

        # Get the first (dominant) name in the current paragraph
        first_match = _PROPER_NAME_RE.search(paragraphs[i][0])
        if not first_match:
            continue
        dominant_name = first_match.group(1)
        if dominant_name in _NON_NAME_WORDS:
            continue

        # If the dominant name is completely new (not in the window), flag as POV shift
        if dominant_name not in window_names:
            boundaries.add(paragraphs[i][1])

    return boundaries


def detect_scene_boundaries(text: str) -> list[int]:
    """Detect likely scene boundaries in narrative text.

    Returns character offsets where scene breaks are detected.
    Uses heuristic/regex patterns -- no LLM calls.

    Detection covers:
    1. Explicit scene dividers (``***``, ``---``, ``* * *``, etc.)
    2. Time jump phrases ("The next morning", "Three days later")
    3. Location change phrases ("Back at the camp", "In the dungeon")
    4. POV/character shift detection (new dominant character not in recent window)

    Args:
        text: Full chapter text.

    Returns:
        Sorted list of unique character offsets marking scene boundaries.
    """
    boundaries: set[int] = set()

    # 1. Explicit scene dividers -- the boundary is where the next
    #    non-whitespace content starts after the divider
    for m in _SCENE_DIVIDER_RE.finditer(text):
        after = text[m.end():]
        stripped = after.lstrip("\n\r \t")
        if stripped:
            offset = m.end() + (len(after) - len(stripped))
            boundaries.add(offset)
        else:
            boundaries.add(m.start())

    # 2. Time jumps -- boundary is the start of the paragraph
    for m in _TIME_JUMP_RE.finditer(text):
        para_start = _content_start_from_match(text, m)
        boundaries.add(para_start)

    # 3. Location changes -- boundary is the start of the paragraph
    for m in _LOCATION_CHANGE_RE.finditer(text):
        para_start = _content_start_from_match(text, m)
        boundaries.add(para_start)

    # 4. POV/character shift detection
    pov_boundaries = _detect_pov_shifts(text)
    boundaries.update(pov_boundaries)

    # Remove offset 0 -- the very start of the chapter is not a "break"
    boundaries.discard(0)

    return sorted(boundaries)


def _content_start_from_match(text: str, m: re.Match[str]) -> int:
    """Find the paragraph start offset for a regex match.

    The regex anchor ``(?:^|\\n)`` may consume a leading newline, so we
    skip any leading whitespace in the match to find the actual content,
    then walk back to the paragraph boundary.
    """
    content_offset = m.start()
    while content_offset < m.end() and text[content_offset] in "\n\r \t":
        content_offset += 1
    return _find_paragraph_start(text, content_offset)


def _find_paragraph_start(text: str, pos: int) -> int:
    """Find the start of the paragraph containing ``pos``.

    Walks backwards from ``pos`` to find the nearest double-newline
    boundary and returns the offset of the first non-whitespace character
    after it.
    """
    search_region = text[:pos]
    last_break = search_region.rfind("\n\n")
    if last_break == -1:
        stripped = text.lstrip("\n\r \t")
        return len(text) - len(stripped) if stripped else 0

    after = text[last_break + 2:]
    stripped = after.lstrip("\n\r \t")
    if stripped:
        return last_break + 2 + (len(after) - len(stripped))
    return last_break + 2


def _build_scene_boundary_set(
    paragraphs: list[tuple[str, int, int]],
    scene_offsets: list[int],
) -> set[int]:
    """Map scene boundary offsets to paragraph indices.

    Returns a set of paragraph indices (0-based) where a scene boundary
    falls at or just before the paragraph's start offset.
    """
    if not scene_offsets:
        return set()

    boundary_indices: set[int] = set()
    offset_idx = 0

    for para_idx, (_text, para_start, _para_end) in enumerate(paragraphs):
        while offset_idx < len(scene_offsets) and scene_offsets[offset_idx] <= para_start:
            boundary_indices.add(para_idx)
            offset_idx += 1

    return boundary_indices


def chunk_chapter(
    chapter: ChapterData,
    book_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[ChunkData]:
    """Split a chapter into overlapping, narrative-aware chunks.

    Respects paragraph boundaries and prefers splitting at scene breaks
    (explicit dividers, time jumps, location changes). Never splits
    mid-paragraph. Each chunk includes character offsets for source grounding
    and a ``scene_break`` flag indicating if it starts at a detected boundary.

    Args:
        chapter: Chapter data with full text.
        book_id: Book identifier for chunk metadata.
        chunk_size: Target tokens per chunk.
        overlap: Overlap tokens between consecutive chunks.

    Returns:
        List of ChunkData with text, position, offset, and scene_break info.
    """
    text = chapter.text
    if not text.strip():
        return []

    # Use structured paragraphs if available (V2 epub), else fall back to regex split
    if chapter.paragraphs:
        paragraphs = [
            (p.text, p.char_start, p.char_end)
            for p in chapter.paragraphs
            if p.text.strip()
        ]
    else:
        paragraphs = _split_paragraphs(text)

    if not paragraphs:
        return []

    # Detect scene boundaries and map them to paragraph indices
    scene_offsets = detect_scene_boundaries(text)
    scene_para_indices = _build_scene_boundary_set(paragraphs, scene_offsets)

    chunks: list[ChunkData] = []
    # Each entry: (para_text, para_start, para_end, para_idx_in_chapter)
    current_paragraphs: list[tuple[str, int, int, int]] = []
    current_tokens = 0
    # How many paragraphs at the front of current_paragraphs are overlap
    overlap_count = 0

    for para_idx, (para_text, para_start, para_end) in enumerate(paragraphs):
        para_tokens = count_tokens(para_text)

        # If single paragraph exceeds chunk size, split it by sentences
        if para_tokens > chunk_size and not current_paragraphs:
            is_scene = bool(chunks) and para_idx in scene_para_indices
            sentence_chunks = _split_long_paragraph(
                para_text, para_start, chapter.number, book_id, chunk_size, len(chunks)
            )
            if sentence_chunks and is_scene:
                sentence_chunks[0] = ChunkData(
                    **{**sentence_chunks[0].model_dump(), "scene_break": True}
                )
            chunks.extend(sentence_chunks)
            continue

        # Decide whether to split before adding this paragraph
        should_split = False

        if current_tokens + para_tokens > chunk_size and current_paragraphs:
            # Over budget -- must split
            should_split = True
        elif (
            current_paragraphs
            and para_idx in scene_para_indices
            and len(current_paragraphs) > overlap_count  # have at least 1 non-overlap para
            and current_tokens >= MIN_CHUNK_SIZE // 2
        ):
            # Proactive split at scene boundary: accept smaller chunks (half
            # MIN_CHUNK_SIZE) to honor narrative structure
            should_split = True

        if should_split:
            # Determine scene_break for the chunk we're about to emit
            is_scene = _chunk_has_scene_start(
                current_paragraphs, overlap_count, scene_para_indices, bool(chunks)
            )
            plain_paras = [(t, s, e) for t, s, e, _ in current_paragraphs]
            chunk = _create_chunk(
                plain_paras,
                chapter.number,
                book_id,
                len(chunks),
                current_tokens,
                scene_break=is_scene,
            )
            chunks.append(chunk)

            # Keep last paragraph(s) as overlap for next chunk
            overlap_paras: list[tuple[str, int, int, int]] = []
            overlap_tokens = 0
            for p in reversed(current_paragraphs):
                p_tokens = count_tokens(p[0])
                if overlap_tokens + p_tokens > overlap:
                    break
                overlap_paras.insert(0, p)
                overlap_tokens += p_tokens

            current_paragraphs = overlap_paras
            current_tokens = overlap_tokens
            overlap_count = len(overlap_paras)

        current_paragraphs.append((para_text, para_start, para_end, para_idx))
        current_tokens += para_tokens

    # Don't forget the last chunk
    if current_paragraphs and current_tokens >= MIN_CHUNK_SIZE:
        is_scene = _chunk_has_scene_start(
            current_paragraphs, overlap_count, scene_para_indices, bool(chunks)
        )
        plain_paras = [(t, s, e) for t, s, e, _ in current_paragraphs]
        chunk = _create_chunk(
            plain_paras,
            chapter.number,
            book_id,
            len(chunks),
            current_tokens,
            scene_break=is_scene,
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
            scene_break=last.scene_break,
        )

    scene_count = sum(1 for c in chunks if c.scene_break)
    logger.info(
        "chapter_chunked",
        chapter=chapter.number,
        book_id=book_id,
        chunks=len(chunks),
        scene_boundaries=len(scene_offsets),
        scene_break_chunks=scene_count,
        avg_tokens=sum(c.token_count for c in chunks) // max(len(chunks), 1),
    )
    return chunks


def _chunk_has_scene_start(
    paras: list[tuple[str, int, int, int]],
    overlap_count: int,
    scene_para_indices: set[int],
    has_prior_chunks: bool,
) -> bool:
    """Check if a chunk starts at a scene boundary.

    Looks at the first non-overlap paragraph in the chunk. The very first
    chunk of the chapter is never marked as a scene break (no prior context
    to break from).

    Args:
        paras: Paragraphs in the chunk, each with (text, start, end, global_idx).
        overlap_count: Number of leading paragraphs carried over as overlap.
        scene_para_indices: Set of paragraph indices that are scene boundaries.
        has_prior_chunks: Whether any chunks have been emitted before this one.

    Returns:
        True if the chunk starts at a scene boundary.
    """
    if not has_prior_chunks:
        return False
    # The first "new" paragraph is the one after overlap
    first_new_idx = min(overlap_count, len(paras) - 1)
    _text, _start, _end, global_idx = paras[first_new_idx]
    return global_idx in scene_para_indices


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
    *,
    scene_break: bool = False,
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
        scene_break=scene_break,
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
