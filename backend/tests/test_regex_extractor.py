"""Tests for app.services.extraction.regex_extractor — Passe 0 regex extraction."""

from __future__ import annotations

import pytest

from app.services.extraction.regex_extractor import RegexExtractor

# -- Default patterns -----------------------------------------------------


class TestRegexExtractorDefault:
    """Tests for RegexExtractor.default() setup."""

    def test_default_ten_patterns(self):
        extractor = RegexExtractor.default()
        assert len(extractor.patterns) == 10

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
            "bloodline_notification",
            "profession_obtained",
            "blessing_received",
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
            sliced = sample_chapter_text[m.char_offset_start : m.char_offset_end]
            assert sliced == m.raw_text


# -- Layer 3: Primal Hunter series-specific patterns -------------------------


class TestLayer3Patterns:
    """Tests for Layer 3 series-specific regex patterns (bloodline, profession, blessing)."""

    @pytest.fixture
    def extractor(self) -> RegexExtractor:
        return RegexExtractor.default()

    def test_bloodline_notification(self, extractor: RegexExtractor):
        text = "[Bloodline Awakened: Bloodline of the Primal Hunter]"
        matches = extractor.extract(text, chapter_number=1)
        bloodline_matches = [m for m in matches if m.pattern_name == "bloodline_notification"]
        assert len(bloodline_matches) >= 1
        names = [m.captures.get("name", "") for m in bloodline_matches]
        assert "Bloodline of the Primal Hunter" in names

    def test_bloodline_evolved(self, extractor: RegexExtractor):
        text = "[Bloodline Evolved: Bloodline of the Primal Hunter]"
        matches = extractor.extract(text, chapter_number=1)
        bloodline_matches = [m for m in matches if m.pattern_name == "bloodline_notification"]
        assert len(bloodline_matches) >= 1

    def test_profession_obtained(self, extractor: RegexExtractor):
        text = "Profession Obtained: Alchemist of the Malefic Viper (Legendary)"
        matches = extractor.extract(text, chapter_number=1)
        prof_matches = [m for m in matches if m.pattern_name == "profession_obtained"]
        assert len(prof_matches) >= 1
        names = [m.captures.get("name", "") for m in prof_matches]
        assert "Alchemist of the Malefic Viper" in names

    def test_profession_without_tier(self, extractor: RegexExtractor):
        text = "Profession Acquired: Herbalist"
        matches = extractor.extract(text, chapter_number=1)
        prof_matches = [m for m in matches if m.pattern_name == "profession_obtained"]
        assert len(prof_matches) >= 1

    def test_blessing_received(self, extractor: RegexExtractor):
        text = "[Blessing of the Malefic Viper received]"
        matches = extractor.extract(text, chapter_number=1)
        blessing_matches = [m for m in matches if m.pattern_name == "blessing_received"]
        assert len(blessing_matches) >= 1
        names = [m.captures.get("name", "") for m in blessing_matches]
        assert "the Malefic Viper" in names

    def test_blessing_from_variant(self, extractor: RegexExtractor):
        text = "[Blessing from the Holy Mother]"
        matches = extractor.extract(text, chapter_number=1)
        blessing_matches = [m for m in matches if m.pattern_name == "blessing_received"]
        assert len(blessing_matches) >= 1


# -- YAML-driven regex via OntologyLoader ------------------------------------


class TestYamlDrivenRegex:
    """Tests for RegexExtractor.from_ontology() — loading patterns from YAML ontology."""

    def test_loads_from_ontology(self):
        """Genre + series layers should load >= 25 patterns."""
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        extractor = RegexExtractor.from_ontology(loader)
        assert len(extractor.patterns) >= 25

    def test_new_skill_evolution_pattern(self):
        """skill_evolved pattern from litrpg.yaml should match evolution arrows."""
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "[Skill Evolved: Basic Archery \u2192 Advanced Archery - Rare]"
        matches = extractor.extract(text, chapter_number=1)
        evolved = [m for m in matches if m.pattern_name == "skill_evolved"]
        assert len(evolved) >= 1

    def test_xp_gain_pattern(self):
        """xp_gain pattern should match XP notifications with commas."""
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "+1,500 XP"
        matches = extractor.extract(text, chapter_number=1)
        xp = [m for m in matches if m.pattern_name == "xp_gain"]
        assert len(xp) >= 1

    def test_quest_patterns(self):
        """Quest received + completed should produce >= 2 matches."""
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "[Quest Received: Defeat the Dungeon Boss]\n[Quest Completed: Defeat the Dungeon Boss]"
        matches = extractor.extract(text, chapter_number=1)
        quests = [m for m in matches if "quest" in m.pattern_name.lower()]
        assert len(quests) >= 2

    def test_item_acquired_pattern(self):
        """item_acquired pattern should match item notifications with rarity."""
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "[Item Acquired: Sword of Shadows - Legendary]"
        matches = extractor.extract(text, chapter_number=1)
        items = [m for m in matches if m.pattern_name == "item_acquired"]
        assert len(items) >= 1

    def test_death_event_pattern(self):
        """death_event pattern should match slain notifications."""
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "[Dark Beast has been slain]"
        matches = extractor.extract(text, chapter_number=1)
        deaths = [m for m in matches if m.pattern_name == "death_event"]
        assert len(deaths) >= 1

    def test_backward_compat_default_constructor(self):
        """Ensure the default constructor still works."""
        extractor = RegexExtractor()
        assert len(extractor.patterns) == 0  # Empty default_factory

    def test_backward_compat_default_classmethod(self):
        """Ensure RegexExtractor.default() still works with hardcoded patterns."""
        extractor = RegexExtractor.default()
        assert len(extractor.patterns) >= 5  # Original hardcoded patterns
