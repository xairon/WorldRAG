"""Tests for app.services.extraction.router — extraction pass routing."""

from __future__ import annotations

import pytest

from app.services.extraction.router import route_extraction_passes


def make_state(
    text: str,
    genre: str = "litrpg",
    regex_json: str = "",
) -> dict:
    """Build a minimal state dict for the router."""
    return {
        "book_id": "book-1",
        "chapter_number": 1,
        "chapter_text": text,
        "genre": genre,
        "regex_matches_json": regex_json,
    }


# Padding text with no keywords (just filler)
LONG_FILLER = "Lorem ipsum dolor sit amet. " * 100  # ~2800 chars


# -- Short chapter routing ------------------------------------------------


class TestShortChapterRouting:
    def test_short_chapter_runs_all_passes(self):
        state = make_state("Short text here.", genre="fantasy")
        result = route_extraction_passes(state)
        assert set(result["passes_to_run"]) == {
            "characters",
            "systems",
            "events",
            "lore",
        }

    def test_boundary_at_2000_chars(self):
        """Text < 2000 chars -> all passes. Text >= 2000 -> normal routing."""
        short = make_state("x" * 1999, genre="fantasy")
        result_short = route_extraction_passes(short)
        assert len(result_short["passes_to_run"]) == 4

        long = make_state(LONG_FILLER, genre="fantasy")
        result_long = route_extraction_passes(long)
        # Fantasy with no keywords: only characters (+ maybe events safety)
        assert "characters" in result_long["passes_to_run"]


# -- Characters always included -------------------------------------------


class TestCharactersAlwaysIncluded:
    def test_characters_always_in_passes(self):
        state = make_state(LONG_FILLER, genre="fantasy")
        result = route_extraction_passes(state)
        assert "characters" in result["passes_to_run"]


# -- System pass routing --------------------------------------------------


class TestSystemPassRouting:
    def test_system_keywords_threshold(self):
        """3+ system keywords trigger systems pass (non-litrpg genre)."""
        text = LONG_FILLER + " skill level class title evolution "
        state = make_state(text, genre="fantasy")
        result = route_extraction_passes(state)
        assert "systems" in result["passes_to_run"]

    def test_litrpg_reduced_threshold(self):
        """LitRPG genre: 1 system keyword is enough."""
        text = LONG_FILLER + " skill "
        state = make_state(text, genre="litrpg")
        result = route_extraction_passes(state)
        assert "systems" in result["passes_to_run"]

    def test_regex_matches_trigger_systems(self):
        """Non-empty regex JSON triggers systems pass."""
        text = LONG_FILLER  # no system keywords
        state = make_state(
            text,
            genre="fantasy",
            regex_json='[{"type":"skill","name":"Fireball"}]',
        )
        result = route_extraction_passes(state)
        assert "systems" in result["passes_to_run"]

    @pytest.mark.parametrize(
        "genre,hits_needed,expected",
        [
            ("litrpg", 1, True),
            ("cultivation", 1, True),
            ("progression_fantasy", 1, True),
            ("fantasy", 1, False),  # needs 3 for non-progression genre
        ],
    )
    def test_genre_system_threshold(self, genre, hits_needed, expected):
        # Add exactly 1 system keyword
        text = LONG_FILLER + " skill "
        state = make_state(text, genre=genre)
        result = route_extraction_passes(state)
        assert ("systems" in result["passes_to_run"]) == expected


# -- Event pass routing ---------------------------------------------------


class TestEventPassRouting:
    def test_event_keywords_threshold(self):
        """2+ event keywords trigger events pass."""
        text = LONG_FILLER + " battle fight "
        state = make_state(text, genre="fantasy")
        result = route_extraction_passes(state)
        assert "events" in result["passes_to_run"]

    def test_event_safety_fallback(self):
        """1 event keyword still adds events (safety net)."""
        text = LONG_FILLER + " battle "
        state = make_state(text, genre="fantasy")
        result = route_extraction_passes(state)
        assert "events" in result["passes_to_run"]


# -- Lore pass routing ----------------------------------------------------


class TestLorePassRouting:
    def test_lore_keywords_threshold(self):
        """3+ lore keywords trigger lore pass."""
        text = LONG_FILLER + " dungeon realm kingdom "
        state = make_state(text, genre="fantasy")
        result = route_extraction_passes(state)
        assert "lore" in result["passes_to_run"]

    def test_lore_below_threshold(self):
        """2 lore keywords: NOT enough for lore pass."""
        text = LONG_FILLER + " dungeon realm "
        state = make_state(text, genre="fantasy")
        result = route_extraction_passes(state)
        assert "lore" not in result["passes_to_run"]
