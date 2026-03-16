"""Tests for grounding post-validation (TDD — written before implementation)."""
from dataclasses import dataclass

import pytest

from backend.app.services.extraction.grounding import validate_and_fix_grounding


@dataclass
class MockEntity:
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


CHAPTER = (
    "Elara stepped into the sunlit hall. "
    "Her sword gleamed with a pale blue light. "
    "System: [Level Up! You are now Level 10]"
)


def test_exact_match():
    """Correctly claimed offsets return 'exact' with confidence 1.0."""
    phrase = "Her sword gleamed with a pale blue light."
    idx = CHAPTER.find(phrase)
    entity = MockEntity(
        extraction_text=phrase,
        char_offset_start=idx,
        char_offset_end=idx + len(phrase),
    )
    status, confidence = validate_and_fix_grounding(entity, CHAPTER)
    assert status == "exact"
    assert confidence == 1.0
    # Offsets should be unchanged
    assert entity.char_offset_start == idx
    assert entity.char_offset_end == idx + len(phrase)


def test_wrong_offset_fuzzy_recovery():
    """Wrong offsets but text exists elsewhere → 'fuzzy' with offsets corrected."""
    phrase = "Elara stepped into the sunlit hall."
    correct_idx = CHAPTER.find(phrase)
    entity = MockEntity(
        extraction_text=phrase,
        char_offset_start=50,   # deliberately wrong
        char_offset_end=50 + len(phrase),
    )
    status, confidence = validate_and_fix_grounding(entity, CHAPTER)
    assert status == "fuzzy"
    assert confidence == 0.7
    # Offsets must be corrected to actual location
    assert entity.char_offset_start == correct_idx
    assert entity.char_offset_end == correct_idx + len(phrase)


def test_no_offsets_fuzzy_recovery():
    """Offsets=-1 (LLM didn't provide them) but text exists → 'fuzzy', offsets set."""
    phrase = "pale blue light"
    correct_idx = CHAPTER.find(phrase)
    entity = MockEntity(
        extraction_text=phrase,
        char_offset_start=-1,
        char_offset_end=-1,
    )
    status, confidence = validate_and_fix_grounding(entity, CHAPTER)
    assert status == "fuzzy"
    assert confidence == 0.7
    assert entity.char_offset_start == correct_idx
    assert entity.char_offset_end == correct_idx + len(phrase)


def test_unaligned():
    """Text not present in source at all → 'unaligned' with confidence ≤ 0.5."""
    entity = MockEntity(
        extraction_text="Completely fabricated text that does not appear anywhere",
        char_offset_start=-1,
        char_offset_end=-1,
    )
    status, confidence = validate_and_fix_grounding(entity, CHAPTER)
    assert status == "unaligned"
    assert confidence <= 0.5


def test_exact_match_with_trailing_whitespace():
    """extraction_text with surrounding whitespace should still match exactly."""
    phrase = "Elara stepped into the sunlit hall."
    idx = CHAPTER.find(phrase)
    entity = MockEntity(
        extraction_text=f"  {phrase}  ",   # padded with spaces
        char_offset_start=idx,
        char_offset_end=idx + len(phrase),
    )
    status, confidence = validate_and_fix_grounding(entity, CHAPTER)
    assert status == "exact"
    assert confidence == 1.0
