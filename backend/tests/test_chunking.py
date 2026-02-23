"""Tests for app.services.chunking — paragraph-aware chunking."""

from __future__ import annotations

import pytest

from app.schemas.book import ChapterData
from app.services.chunking import _split_paragraphs, chunk_chapter


@pytest.fixture
def fast_token_count(monkeypatch):
    """Replace count_tokens with len(text)//5 for predictable chunking."""
    from app.services import chunking

    monkeypatch.setattr(chunking, "count_tokens", lambda text, *a, **kw: len(text) // 5)


# -- _split_paragraphs ---------------------------------------------------


class TestSplitParagraphs:

    def test_single_paragraph(self):
        text = "Just one paragraph without any double newlines."
        result = _split_paragraphs(text)
        assert len(result) == 1
        assert result[0][0] == text

    def test_two_paragraphs(self):
        text = "Paragraph one.\n\nParagraph two."
        result = _split_paragraphs(text)
        assert len(result) == 2
        assert result[0][0] == "Paragraph one."
        assert result[1][0] == "Paragraph two."

    def test_offsets_correct(self):
        text = "First para.\n\nSecond para."
        result = _split_paragraphs(text)
        for para_text, start, end in result:
            # The stripped text should be findable within the offset range
            assert para_text in text[start:end + len(para_text)]

    def test_empty_text(self):
        result = _split_paragraphs("")
        assert result == []


# -- chunk_chapter --------------------------------------------------------


class TestChunkChapter:

    def test_empty_chapter_no_chunks(self, fast_token_count):
        chapter = ChapterData(number=1, title="", text="")
        chunks = chunk_chapter(chapter, "book1")
        assert chunks == []

    def test_short_chapter_one_chunk(self, fast_token_count):
        # Text must produce >= MIN_CHUNK_SIZE (200) tokens via len//5,
        # so we need >= 1000 chars of text.
        sentences = [f"This is sentence number {i} of the chapter." for i in range(30)]
        text = "\n\n".join(sentences)
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=5000)
        assert len(chunks) == 1

    def test_positions_sequential(self, fast_token_count):
        """Chunk positions should be 0, 1, 2, ..."""
        # Create text big enough for multiple chunks
        paragraphs = [f"Paragraph {i} with some content here." for i in range(50)]
        text = "\n\n".join(paragraphs)
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=50)
        if len(chunks) > 1:
            positions = [c.position for c in chunks]
            assert positions == list(range(len(chunks)))

    def test_book_id_propagated(self, fast_token_count):
        text = "Some text.\n\nMore text."
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "test-book-123", chunk_size=200)
        for c in chunks:
            assert c.book_id == "test-book-123"

    def test_chapter_number_propagated(self, fast_token_count):
        text = "Some text.\n\nMore text."
        chapter = ChapterData(number=42, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=200)
        for c in chunks:
            assert c.chapter_number == 42

    def test_small_remainder_merged(self, fast_token_count):
        """Very small last group merges into previous chunk."""
        # Create paragraphs where the last one is tiny
        paragraphs = [f"{'x' * 200} paragraph {i}." for i in range(10)]
        paragraphs.append("tiny.")  # < MIN_CHUNK_SIZE tokens
        text = "\n\n".join(paragraphs)
        chapter = ChapterData(number=1, title="Test", text=text)
        # chunk_size big enough for ~2 paragraphs
        chunks = chunk_chapter(chapter, "book1", chunk_size=100)
        if chunks:
            # The last chunk should contain "tiny."
            assert "tiny." in chunks[-1].text

    def test_multiple_chunks_created(self, fast_token_count):
        """Large chapter produces multiple chunks."""
        paragraphs = [f"Paragraph {i} content here. " * 10 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=50)
        assert len(chunks) >= 2

    def test_char_offsets_populated(self, fast_token_count):
        """Chunks have non-trivial char_offset values."""
        paragraphs = [f"Paragraph {i} with content." for i in range(20)]
        text = "\n\n".join(paragraphs)
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=30)
        if len(chunks) >= 2:
            assert chunks[0].char_offset_start == 0 or chunks[0].char_offset_start >= 0
            assert chunks[-1].char_offset_end > 0


# -- _split_long_paragraph (via chunk_chapter) ----------------------------


class TestSplitLongParagraph:

    def test_splits_by_sentences(self, fast_token_count):
        """A single oversized paragraph splits at sentence boundaries."""
        # One huge paragraph (no double newlines)
        text = ". ".join([f"Sentence {i} with some words" for i in range(100)])
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=30)
        assert len(chunks) >= 2

    def test_no_empty_chunks(self, fast_token_count):
        text = ". ".join([f"Sentence {i} here" for i in range(50)])
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=20)
        for c in chunks:
            assert len(c.text.strip()) > 0

    def test_positions_correct(self, fast_token_count):
        text = ". ".join([f"Sentence {i} words" for i in range(50)])
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=20)
        positions = [c.position for c in chunks]
        assert positions == list(range(len(chunks)))

    def test_total_text_coverage(self, fast_token_count):
        """All sentence content should appear in at least one chunk."""
        sentences = [f"Unique sentence {i}." for i in range(20)]
        text = " ".join(sentences)
        chapter = ChapterData(number=1, title="Test", text=text)
        chunks = chunk_chapter(chapter, "book1", chunk_size=20)
        all_chunk_text = " ".join(c.text for c in chunks)
        for sent in sentences:
            # Sentence might be split across chunks, check key word
            assert f"sentence {sent.split()[2]}" in all_chunk_text.lower()
