"""Tests for app.services.extraction.regex_extractor — Passe 0 regex extraction."""

from __future__ import annotations

from app.services.extraction.regex_extractor import RegexExtractor

# -- Default patterns -----------------------------------------------------


class TestRegexExtractorDefault:
    """Tests for RegexExtractor.default() setup."""

    def test_default_seven_patterns(self):
        extractor = RegexExtractor.default()
        assert len(extractor.patterns) == 7

    def test_pattern_names_exact(self):
        extractor = RegexExtractor.default()
        names = {p.name for p in extractor.patterns}
        assert names == {
            "skill_acquired",
            "level_up",
            "class_obtained",
            "title_earned",
            "stat_increase",
            "evolution",
            "blue_box_generic",
        }

    def test_blue_box_generic_is_last(self):
        """blue_box_generic must be last so specific patterns match first."""
        extractor = RegexExtractor.default()
        assert extractor.patterns[-1].name == "blue_box_generic"


# -- Extract with sample chapter ------------------------------------------


class TestExtractSampleChapter:
    """Tests using the golden sample_chapter_text fixture."""

    def test_skill_acquired(self, sample_chapter_text):
        extractor = RegexExtractor.default()
        matches = extractor.extract(sample_chapter_text, 42)
        skills = [m for m in matches if m.pattern_name == "skill_acquired"]
        assert len(skills) >= 1
        skill = skills[0]
        assert skill.captures["name"] == "Mark of the Ambitious Hunter"
        assert skill.captures["rank"] == "Legendary"

    def test_level_up(self, sample_chapter_text):
        extractor = RegexExtractor.default()
        matches = extractor.extract(sample_chapter_text, 42)
        levels = [m for m in matches if m.pattern_name == "level_up"]
        assert len(levels) >= 1
        assert levels[0].captures["old_value"] == "87"
        assert levels[0].captures["new_value"] == "88"

    def test_title_earned(self, sample_chapter_text):
        extractor = RegexExtractor.default()
        matches = extractor.extract(sample_chapter_text, 42)
        titles = [m for m in matches if m.pattern_name == "title_earned"]
        assert len(titles) >= 1
        assert titles[0].captures["name"] == "Hydra Slayer"

    def test_stat_increase_multiple(self, sample_chapter_text):
        extractor = RegexExtractor.default()
        matches = extractor.extract(sample_chapter_text, 42)
        stats = [m for m in matches if m.pattern_name == "stat_increase"]
        assert len(stats) >= 2
        stat_names = {s.captures["stat_name"] for s in stats}
        assert "Perception" in stat_names
        assert "Agility" in stat_names


# -- Overlap deduplication ------------------------------------------------


class TestExtractDeduplication:
    """Tests for specific-vs-generic overlap suppression."""

    def test_skill_not_duplicated_as_generic(self):
        """A skill box should NOT also produce a blue_box_generic match."""
        text = "[Skill Acquired: Fireball - Rare]"
        extractor = RegexExtractor.default()
        matches = extractor.extract(text, 1)
        skills = [m for m in matches if m.pattern_name == "skill_acquired"]
        generics = [m for m in matches if m.pattern_name == "blue_box_generic"]
        assert len(skills) == 1
        assert len(generics) == 0

    def test_generic_captures_unmatched_boxes(self):
        """A bracket box that doesn't match specific patterns -> generic."""
        text = "[Quest Complete: Defeat the Troll King]"
        extractor = RegexExtractor.default()
        matches = extractor.extract(text, 1)
        generics = [m for m in matches if m.entity_type == "SystemNotification"]
        assert len(generics) >= 1

    def test_chapter_number_propagated(self):
        text = "[Skill Acquired: Test Skill - Common]"
        extractor = RegexExtractor.default()
        matches = extractor.extract(text, 99)
        for m in matches:
            assert m.chapter_number == 99


# -- Offset accuracy ------------------------------------------------------


class TestExtractOffsets:
    """Tests for character offset correctness."""

    def test_offsets_valid_range(self, sample_chapter_text):
        extractor = RegexExtractor.default()
        matches = extractor.extract(sample_chapter_text, 42)
        assert len(matches) > 0
        for m in matches:
            assert 0 <= m.char_offset_start < m.char_offset_end
            assert m.char_offset_end <= len(sample_chapter_text)

    def test_raw_text_matches_slice(self, sample_chapter_text):
        extractor = RegexExtractor.default()
        matches = extractor.extract(sample_chapter_text, 42)
        for m in matches:
            sliced = sample_chapter_text[m.char_offset_start:m.char_offset_end]
            assert sliced == m.raw_text
