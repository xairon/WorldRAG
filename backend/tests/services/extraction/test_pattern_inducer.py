"""Tests for co-evolutionary pattern induction."""

from app.services.extraction.pattern_inducer import (
    InducedRegexPattern,
    _validate_induced_patterns,
    naive_structural_capture,
)


class TestNaiveStructuralCapture:
    def test_captures_bracketed_content(self):
        text = "Jake acquired [Skill Acquired: Shadow Step - Rare] in the forest."
        captures = naive_structural_capture(text)
        assert len(captures) >= 1
        assert any("Skill Acquired" in c["text"] for c in captures)

    def test_captures_stat_gains(self):
        text = "Stats updated:\n+5 Perception\n+3 Agility\nEnd of chapter."
        captures = naive_structural_capture(text)
        assert len(captures) >= 2

    def test_captures_level_transitions(self):
        text = "Level: 42 -> 43"
        captures = naive_structural_capture(text)
        assert len(captures) >= 1

    def test_empty_text_returns_empty(self):
        captures = naive_structural_capture("")
        assert captures == []

    def test_no_structured_content(self):
        text = "Jake walked through the forest. It was dark and cold."
        captures = naive_structural_capture(text)
        assert captures == []

    def test_deduplicates_overlapping_spans(self):
        text = "[Skill Acquired: Shadow Step]"
        captures = naive_structural_capture(text)
        # Should not have duplicate captures for the same span
        spans = [(c["start"], c["end"]) for c in captures]
        assert len(spans) == len(set(spans))


class TestValidateInducedPatterns:
    def test_valid_pattern_accepted(self):
        patterns = [
            InducedRegexPattern(
                name="skill_test",
                entity_type="Skill",
                regex=r"\[Skill.*?: (?P<name>.+?)\]",
                example_matches=[
                    "[Skill Acquired: Shadow Step]",
                    "[Skill Learned: Fireball]",
                ],
            ),
        ]
        result = _validate_induced_patterns(patterns)
        assert len(result) == 1
        assert result[0]["name"] == "skill_test"

    def test_invalid_regex_rejected(self):
        patterns = [
            InducedRegexPattern(
                name="bad_regex",
                entity_type="Test",
                regex=r"[invalid(regex",  # Unbalanced bracket
                example_matches=["test"],
            ),
        ]
        result = _validate_induced_patterns(patterns)
        assert len(result) == 0

    def test_low_match_rate_rejected(self):
        patterns = [
            InducedRegexPattern(
                name="bad_pattern",
                entity_type="Test",
                regex=r"NOMATCH",
                example_matches=["abc", "def", "ghi"],
            ),
        ]
        result = _validate_induced_patterns(patterns)
        assert len(result) == 0

    def test_no_examples_rejected(self):
        patterns = [
            InducedRegexPattern(
                name="no_examples",
                entity_type="Test",
                regex=r".*",
                example_matches=[],
            ),
        ]
        result = _validate_induced_patterns(patterns)
        assert len(result) == 0

    def test_captures_extracted(self):
        patterns = [
            InducedRegexPattern(
                name="with_captures",
                entity_type="Skill",
                regex=r"\[Skill: (?P<name>.+?) - (?P<rank>.+?)\]",
                example_matches=["[Skill: Shadow Step - Rare]"],
            ),
        ]
        result = _validate_induced_patterns(patterns)
        assert len(result) == 1
        assert "name" in result[0]["captures"]
        assert "rank" in result[0]["captures"]
