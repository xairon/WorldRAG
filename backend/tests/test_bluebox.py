"""Tests for app.services.extraction.bluebox — Passe 0.5 BlueBox grouping."""

from __future__ import annotations

from app.services.extraction.bluebox import (
    BlueBoxGroup,
    _classify_box,
    group_blue_boxes,
)


# -- Helper to build paragraph dicts ----------------------------------------


def _para(index: int, ptype: str = "narration", text: str = "Some narration.") -> dict:
    """Build a paragraph dict matching the expected schema."""
    return {"index": index, "type": ptype, "text": text}


def _blue(index: int, text: str = "System notification.") -> dict:
    """Build a blue_box paragraph dict."""
    return _para(index, "blue_box", text)


# -- Empty / no blue_box ---------------------------------------------------


class TestEmptyInput:
    """Edge cases with no paragraphs or no blue_box paragraphs."""

    def test_empty_paragraphs_returns_empty(self):
        assert group_blue_boxes([]) == []

    def test_no_blue_box_paragraphs_returns_empty(self):
        paragraphs = [
            _para(0, "narration", "Jake walked through the forest."),
            _para(1, "narration", "He drew his sword."),
            _para(2, "dialogue", '"Watch out!" Viper shouted.'),
        ]
        assert group_blue_boxes(paragraphs) == []


# -- Single blue_box -------------------------------------------------------


class TestSingleBlueBox:
    """A single blue_box paragraph produces exactly one group."""

    def test_single_blue_box_returns_one_group(self):
        paragraphs = [
            _para(0),
            _blue(1, "Skill Acquired: Stealth"),
            _para(2),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1

    def test_single_blue_box_start_end_equal(self):
        paragraphs = [_blue(0, "Level 5 → 6")]
        result = group_blue_boxes(paragraphs)
        assert result[0].paragraph_start == 0
        assert result[0].paragraph_end == 0

    def test_single_blue_box_indexes(self):
        paragraphs = [_para(0), _blue(3, "Info"), _para(4)]
        result = group_blue_boxes(paragraphs)
        assert result[0].paragraph_indexes == [3]

    def test_single_blue_box_raw_text(self):
        text = "Skill Acquired: Shadow Strike"
        paragraphs = [_blue(0, text)]
        result = group_blue_boxes(paragraphs)
        assert result[0].raw_text == text


# -- Consecutive blue_boxes → merged group ---------------------------------


class TestConsecutiveGrouping:
    """Consecutive blue_box paragraphs merge into a single group."""

    def test_two_consecutive_blue_boxes(self):
        paragraphs = [
            _blue(0, "Skill Acquired: Backstab"),
            _blue(1, "+5 Agility"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1
        assert result[0].paragraph_start == 0
        assert result[0].paragraph_end == 1
        assert result[0].paragraph_indexes == [0, 1]

    def test_three_consecutive_blue_boxes(self):
        paragraphs = [
            _blue(0, "Level 10 → 11"),
            _blue(1, "+3 Strength"),
            _blue(2, "+2 Agility"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1
        assert result[0].paragraph_indexes == [0, 1, 2]

    def test_raw_text_joins_with_newline(self):
        paragraphs = [
            _blue(0, "Skill Acquired: Fireball"),
            _blue(1, "+10 Intelligence"),
        ]
        result = group_blue_boxes(paragraphs)
        assert result[0].raw_text == "Skill Acquired: Fireball\n+10 Intelligence"


# -- Gap tolerance ---------------------------------------------------------


class TestGapTolerance:
    """Gap of 1 narration paragraph still merges; gap of 2+ splits."""

    def test_gap_of_one_narration_merges(self):
        paragraphs = [
            _blue(0, "Skill Acquired: Dash"),
            _para(1, "narration", "A warm glow filled his body."),
            _blue(2, "+5 Agility"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1
        assert result[0].paragraph_start == 0
        assert result[0].paragraph_end == 2
        assert result[0].paragraph_indexes == [0, 2]

    def test_gap_of_one_raw_text_excludes_narration(self):
        """The narration paragraph between two blue boxes is NOT included in raw_text."""
        paragraphs = [
            _blue(0, "AAA"),
            _para(1, "narration", "NARRATION"),
            _blue(2, "BBB"),
        ]
        result = group_blue_boxes(paragraphs)
        assert result[0].raw_text == "AAA\nBBB"

    def test_gap_of_two_splits_into_two_groups(self):
        paragraphs = [
            _blue(0, "Skill Acquired: Stealth"),
            _para(1, "narration", "He looked around."),
            _para(2, "narration", "Nothing happened."),
            _blue(3, "Title earned: Shadow Walker"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 2
        assert result[0].paragraph_indexes == [0]
        assert result[1].paragraph_indexes == [3]

    def test_gap_of_three_splits(self):
        paragraphs = [
            _blue(0, "Level 1 → 2"),
            _para(1),
            _para(2),
            _para(3),
            _blue(4, "Level 2 → 3"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 2

    def test_multiple_groups_with_gaps(self):
        """Three separate groups: two singles and one merged pair."""
        paragraphs = [
            _blue(0, "Skill Acquired: A"),
            _para(1),
            _para(2),
            _para(3),
            _blue(4, "Skill Acquired: B"),
            _blue(5, "+3 Strength"),
            _para(6),
            _para(7),
            _para(8),
            _blue(9, "Title earned: Hero"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 3
        assert result[0].paragraph_indexes == [0]
        assert result[1].paragraph_indexes == [4, 5]
        assert result[2].paragraph_indexes == [9]


# -- Classification --------------------------------------------------------


class TestClassification:
    """Test _classify_box returns the correct box_type."""

    def test_level_up_arrow(self):
        assert _classify_box("Level 87 → 88") == "level_up"

    def test_level_up_dash_arrow(self):
        assert _classify_box("Level 5 -> 6") == "level_up"

    def test_level_up_to(self):
        assert _classify_box("Level increased from 10 to 11") == "level_up"

    def test_skill_acquired(self):
        assert _classify_box("Skill Acquired: Backstab [Rare]") == "skill_acquisition"

    def test_ability_learned(self):
        assert _classify_box("Ability Learned: Mana Shield") == "skill_acquisition"

    def test_skill_obtained(self):
        assert _classify_box("Skill Obtained: Greater Fireball") == "skill_acquisition"

    def test_title_earned(self):
        assert _classify_box("Title earned: Primal Hunter") == "title"

    def test_title_obtained(self):
        assert _classify_box("Title obtained: Dragon Slayer") == "title"

    def test_title_acquired(self):
        assert _classify_box("Title acquired: Worldwalker") == "title"

    def test_stat_block_positive(self):
        assert _classify_box("+5 Strength") == "stat_block"

    def test_stat_block_negative(self):
        assert _classify_box("-2 Wisdom") == "stat_block"

    def test_stat_block_free_points(self):
        assert _classify_box("+10 Free Points") == "stat_block"

    def test_stat_block_multiple(self):
        text = "+3 Agility\n+2 Perception\n+1 Endurance"
        assert _classify_box(text) == "stat_block"

    def test_mixed_level_and_skill(self):
        text = "Level 10 → 11\nSkill Acquired: Power Strike"
        assert _classify_box(text) == "mixed"

    def test_mixed_level_and_title(self):
        text = "Level 99 → 100\nTitle earned: Centurion"
        assert _classify_box(text) == "mixed"

    def test_mixed_unrecognized(self):
        assert _classify_box("Some random system text") == "mixed"

    def test_stat_with_level_is_level(self):
        """Level takes precedence over stat when only level flag is set (stat is not in flags count)."""
        text = "Level 5 → 6\n+3 Strength"
        # has_level=True, has_stat=True, but flags only counts level/skill/title
        # flags=1 (only level), so returns level_up
        assert _classify_box(text) == "level_up"


# -- Classification via group_blue_boxes -----------------------------------


class TestGroupClassification:
    """Verify that group_blue_boxes assigns box_type via _classify_box."""

    def test_group_classified_as_skill_acquisition(self):
        paragraphs = [_blue(0, "Skill Acquired: Fireball")]
        result = group_blue_boxes(paragraphs)
        assert result[0].box_type == "skill_acquisition"

    def test_group_classified_as_level_up(self):
        paragraphs = [_blue(0, "Level 22 → 23")]
        result = group_blue_boxes(paragraphs)
        assert result[0].box_type == "level_up"

    def test_merged_group_classified_as_mixed(self):
        paragraphs = [
            _blue(0, "Level 1 → 2"),
            _blue(1, "Skill Acquired: Basic Strike"),
        ]
        result = group_blue_boxes(paragraphs)
        assert result[0].box_type == "mixed"

    def test_group_classified_as_stat_block(self):
        paragraphs = [
            _blue(0, "+5 Strength"),
            _blue(1, "+3 Agility"),
        ]
        result = group_blue_boxes(paragraphs)
        assert result[0].box_type == "stat_block"


# -- Paragraph ordering / non-sequential indexes ---------------------------


class TestNonSequentialIndexes:
    """Blue_box paragraphs may not have sequential indexes (gaps from narration)."""

    def test_sparse_indexes_group_correctly(self):
        paragraphs = [
            _para(0),
            _para(1),
            _blue(2, "A"),
            _blue(3, "B"),
            _para(4),
            _para(5),
            _para(6),
            _para(7),
            _blue(8, "C"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 2
        assert result[0].paragraph_indexes == [2, 3]
        assert result[1].paragraph_indexes == [8]

    def test_blue_boxes_at_end(self):
        paragraphs = [
            _para(0),
            _para(1),
            _blue(2, "X"),
            _blue(3, "Y"),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1
        assert result[0].paragraph_end == 3

    def test_blue_boxes_at_start(self):
        paragraphs = [
            _blue(0, "X"),
            _blue(1, "Y"),
            _para(2),
            _para(3),
        ]
        result = group_blue_boxes(paragraphs)
        assert len(result) == 1
        assert result[0].paragraph_start == 0


# -- BlueBoxGroup dataclass -----------------------------------------------


class TestBlueBoxGroupDataclass:
    """Verify BlueBoxGroup defaults and field behavior."""

    def test_default_box_type_is_mixed(self):
        box = BlueBoxGroup(paragraph_start=0, paragraph_end=0, raw_text="test")
        assert box.box_type == "mixed"

    def test_default_paragraph_indexes_is_empty_list(self):
        box = BlueBoxGroup(paragraph_start=0, paragraph_end=0, raw_text="test")
        assert box.paragraph_indexes == []

    def test_paragraph_indexes_not_shared_between_instances(self):
        """Ensure default_factory produces distinct lists."""
        box1 = BlueBoxGroup(paragraph_start=0, paragraph_end=0, raw_text="a")
        box2 = BlueBoxGroup(paragraph_start=1, paragraph_end=1, raw_text="b")
        box1.paragraph_indexes.append(99)
        assert 99 not in box2.paragraph_indexes
