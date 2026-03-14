"""Tests for NarrativeTemporalMapper — maps (book, chapter, scene) ↔ datetime."""

from datetime import datetime, timedelta

import pytest

from app.services.saga_profile import NarrativeTemporalMapper


EPOCH = datetime(2000, 1, 1)
BOOK_OFFSET_DAYS = 10_000


class TestToDatetime:
    def test_book1_chapter1(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=1)
        expected = EPOCH + timedelta(days=1)
        assert dt == expected

    def test_book1_chapter42(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=42)
        expected = EPOCH + timedelta(days=42)
        assert dt == expected

    def test_book2_chapter1_crosses_book_offset(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=2, chapter_num=1)
        expected = EPOCH + timedelta(days=BOOK_OFFSET_DAYS + 1)
        assert dt == expected

    def test_scene_order_encoded_in_seconds(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=5, scene_order=30)
        expected = EPOCH + timedelta(days=5, seconds=30)
        assert dt == expected

    def test_book1_chapter0(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=0)
        assert dt == EPOCH

    def test_invalid_book_num_zero_raises(self):
        with pytest.raises(ValueError):
            NarrativeTemporalMapper.to_datetime(book_num=0, chapter_num=1)

    def test_negative_chapter_raises(self):
        with pytest.raises(ValueError):
            NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=-1)

    def test_70_book_saga_does_not_overflow(self):
        # Should not raise; datetime supports far future dates
        dt = NarrativeTemporalMapper.to_datetime(book_num=70, chapter_num=500)
        assert dt > EPOCH


class TestFromDatetime:
    def test_before_epoch_raises(self):
        dt = EPOCH - timedelta(seconds=1)
        with pytest.raises(ValueError):
            NarrativeTemporalMapper.from_datetime(dt)

    def test_epoch_itself(self):
        book, chapter, scene = NarrativeTemporalMapper.from_datetime(EPOCH)
        assert (book, chapter, scene) == (1, 0, 0)


class TestRoundtrip:
    @pytest.mark.parametrize(
        "book_num,chapter_num,scene_order",
        [
            (1, 1, 0),
            (1, 42, 0),
            (2, 1, 0),
            (1, 5, 30),
            (1, 0, 0),
            (70, 500, 99),
        ],
    )
    def test_roundtrip(self, book_num: int, chapter_num: int, scene_order: int):
        dt = NarrativeTemporalMapper.to_datetime(book_num, chapter_num, scene_order)
        result = NarrativeTemporalMapper.from_datetime(dt)
        assert result == (book_num, chapter_num, scene_order)
