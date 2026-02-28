"""Pydantic schemas for books, chapters, and chunks.

Defines the data models for the bibliographic layer of the KG:
Series → Book → Chapter → Chunk (FRBRoo/LRMoo hierarchy).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ProcessingStatus(StrEnum):
    """Status of book/chapter processing in the pipeline."""

    PENDING = "pending"
    INGESTING = "ingesting"
    CHUNKING = "chunking"
    EXTRACTING = "extracting"
    RECONCILING = "reconciling"
    VALIDATING = "validating"
    COMPLETED = "completed"
    EXTRACTED = "extracted"  # extraction done, embeddings pending
    EMBEDDING = "embedding"  # embedding in progress
    EMBEDDED = "embedded"  # fully complete (extraction + embeddings)
    PARTIAL = "partial"  # some chapters failed
    FAILED = "failed"


# --- Request schemas ---


class BookUpload(BaseModel):
    """Request schema for book upload metadata."""

    title: str = Field(..., min_length=1, max_length=500)
    series_name: str | None = None
    order_in_series: int | None = None
    author: str | None = None
    genre: str = "litrpg"


# --- Internal schemas ---


class ParagraphType(StrEnum):
    """Type of paragraph within a chapter."""

    NARRATION = "narration"
    DIALOGUE = "dialogue"
    BLUE_BOX = "blue_box"
    SCENE_BREAK = "scene_break"
    HEADER = "header"


class ParagraphData(BaseModel):
    """A paragraph within a chapter, classified by type."""

    index: int
    type: ParagraphType
    text: str
    html: str = ""
    char_start: int
    char_end: int
    speaker: str | None = None
    sentence_count: int = 0
    word_count: int = 0

    def model_post_init(self, _context: object) -> None:
        if not self.word_count and self.text:
            self.word_count = len(self.text.split())


class ChapterData(BaseModel):
    """Parsed chapter data from ingestion."""

    number: int = Field(..., ge=1)
    title: str = ""
    text: str
    xhtml: str = ""  # full chapter body HTML from epub (preserves structure)
    paragraphs: list[ParagraphData] = Field(default_factory=list)
    word_count: int = 0
    start_offset: int = 0  # character offset in original file

    def model_post_init(self, _context: object) -> None:
        if self.word_count == 0:
            self.word_count = len(self.text.split())


class ChunkData(BaseModel):
    """A chunk of text within a chapter, ready for embedding."""

    text: str
    position: int  # chunk index within chapter
    chapter_number: int
    book_id: str
    token_count: int = 0
    char_offset_start: int = 0  # offset within chapter text
    char_offset_end: int = 0


class RegexMatch(BaseModel):
    """A regex-extracted entity from Passe 0 (blue boxes, stats)."""

    pattern_name: str  # e.g., "skill_acquired", "level_up"
    entity_type: str  # e.g., "Skill", "Level", "Title"
    captures: dict[str, str]  # named captures from the regex
    raw_text: str  # full matched text
    char_offset_start: int
    char_offset_end: int
    chapter_number: int
    confidence: float = 0.95  # regex matches are high confidence


# --- Response schemas ---


class BookInfo(BaseModel):
    """Book information for API responses."""

    id: str
    title: str
    series_name: str | None = None
    order_in_series: int | None = None
    author: str | None = None
    genre: str = "litrpg"
    total_chapters: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    chapters_processed: int = 0
    total_cost_usd: float = 0.0


class SeriesInfo(BaseModel):
    """Series information for API responses."""

    name: str
    author: str | None = None
    genre: str = "litrpg"
    book_count: int = 0
    books: list[BookInfo] = Field(default_factory=list)


class ChapterInfo(BaseModel):
    """Chapter information for API responses."""

    number: int
    title: str = ""
    word_count: int = 0
    chunk_count: int = 0
    entity_count: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    regex_matches: int = 0


class BookDetail(BaseModel):
    """Detailed book information with chapter list."""

    book: BookInfo
    chapters: list[ChapterInfo] = []


class IngestionResult(BaseModel):
    """Result of book ingestion (parsing + chunking)."""

    book_id: str
    title: str
    chapters_found: int
    chunks_created: int
    regex_matches_total: int
    status: ProcessingStatus


class ExtractionResult(BaseModel):
    """Result of LLM extraction pipeline (Phase 2b+2c)."""

    book_id: str
    chapters_processed: int = 0
    chapters_failed: int = 0
    failed_chapters: list[int] = Field(default_factory=list)
    total_entities: int = 0
    status: str = "pending"


class JobEnqueuedResult(BaseModel):
    """Result of enqueueing a background job."""

    book_id: str
    job_id: str
    status: str = "enqueued"
    message: str = ""
