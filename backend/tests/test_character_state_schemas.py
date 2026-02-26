"""Tests for V3 character state Pydantic schemas."""

from app.schemas.character_state import (
    CategoryDiff,
    CharacterComparison,
    CharacterStateSnapshot,
    CharacterSummary,
    ClassSnapshot,
    ItemSnapshot,
    LevelSnapshot,
    ProgressionMilestone,
    ProgressionTimeline,
    SkillSnapshot,
    StatDiff,
    StatEntry,
    StateChangeRecord,
    TitleSnapshot,
)


class TestStatEntry:
    def test_creates_with_required_fields(self):
        entry = StatEntry(name="Perception", value=37, last_changed_chapter=14)
        assert entry.name == "Perception"
        assert entry.value == 37

    def test_defaults(self):
        entry = StatEntry(name="Strength", value=10, last_changed_chapter=1)
        assert entry.last_changed_chapter == 1


class TestSkillSnapshot:
    def test_creates_with_name_only(self):
        skill = SkillSnapshot(name="Archer's Eye")
        assert skill.name == "Archer's Eye"
        assert skill.rank == ""
        assert skill.skill_type == ""
        assert skill.description == ""
        assert skill.acquired_chapter is None

    def test_creates_with_all_fields(self):
        skill = SkillSnapshot(
            name="Archer's Eye",
            rank="rare",
            skill_type="active",
            description="Enhanced perception",
            acquired_chapter=1,
        )
        assert skill.rank == "rare"
        assert skill.acquired_chapter == 1


class TestClassSnapshot:
    def test_creates_with_name_only(self):
        cls = ClassSnapshot(name="Hunter")
        assert cls.name == "Hunter"
        assert cls.tier is None
        assert cls.is_active is False

    def test_creates_with_all_fields(self):
        cls = ClassSnapshot(
            name="Avaricious Arcane Hunter",
            tier=3,
            description="A powerful hunter class",
            acquired_chapter=30,
            is_active=True,
        )
        assert cls.tier == 3
        assert cls.is_active is True


class TestTitleSnapshot:
    def test_creates_with_name_only(self):
        title = TitleSnapshot(name="Hydra Slayer")
        assert title.effects == []
        assert title.acquired_chapter is None

    def test_creates_with_effects(self):
        title = TitleSnapshot(
            name="Hydra Slayer",
            effects=["fear_aura", "+10 Strength"],
            acquired_chapter=42,
        )
        assert len(title.effects) == 2


class TestItemSnapshot:
    def test_creates_with_name_only(self):
        item = ItemSnapshot(name="Nanoblade")
        assert item.item_type == ""
        assert item.grants == []

    def test_creates_with_all_fields(self):
        item = ItemSnapshot(
            name="Nanoblade",
            item_type="weapon",
            rarity="legendary",
            description="A blade of nanomaterial",
            acquired_chapter=20,
            grants=["Shadow Strike", "Armor Pierce"],
        )
        assert len(item.grants) == 2
        assert item.rarity == "legendary"


class TestLevelSnapshot:
    def test_creates_empty(self):
        level = LevelSnapshot()
        assert level.level is None
        assert level.realm == ""
        assert level.since_chapter is None

    def test_creates_with_all_fields(self):
        level = LevelSnapshot(level=88, realm="D-grade", since_chapter=42)
        assert level.level == 88
        assert level.realm == "D-grade"


class TestStateChangeRecord:
    def test_creates_stat_change(self):
        sc = StateChangeRecord(
            chapter=14,
            category="stat",
            name="Perception",
            action="gain",
            value_delta=5,
        )
        assert sc.value_delta == 5
        assert sc.detail == ""

    def test_creates_skill_acquire(self):
        sc = StateChangeRecord(
            chapter=14,
            category="skill",
            name="Mark of the Hunter",
            action="acquire",
        )
        assert sc.value_delta is None

    def test_creates_with_detail(self):
        sc = StateChangeRecord(
            chapter=14,
            category="item",
            name="Nanoblade",
            action="acquire",
            detail="Looted from dungeon boss",
        )
        assert sc.detail == "Looted from dungeon boss"


class TestCharacterStateSnapshot:
    def test_creates_minimal(self):
        snap = CharacterStateSnapshot(
            character_name="Jake Thayne",
            canonical_name="Jake Thayne",
            book_id="abc",
            as_of_chapter=14,
            total_chapters_in_book=100,
        )
        assert snap.stats == []
        assert snap.skills == []
        assert snap.level.level is None

    def test_full_snapshot(self):
        snap = CharacterStateSnapshot(
            character_name="Jake Thayne",
            canonical_name="Jake Thayne",
            book_id="abc",
            as_of_chapter=14,
            total_chapters_in_book=100,
            role="protagonist",
            species="Human",
            description="A hunter",
            aliases=["Jake", "Thayne"],
            level=LevelSnapshot(level=88, realm="D-grade", since_chapter=42),
            stats=[
                StatEntry(name="Perception", value=37, last_changed_chapter=14),
            ],
            skills=[
                SkillSnapshot(
                    name="Archer's Eye",
                    rank="rare",
                    skill_type="active",
                    acquired_chapter=1,
                ),
            ],
            classes=[
                ClassSnapshot(
                    name="Avaricious Arcane Hunter",
                    tier=3,
                    acquired_chapter=30,
                    is_active=True,
                ),
            ],
            titles=[
                TitleSnapshot(
                    name="Hydra Slayer",
                    effects=["fear_aura"],
                    acquired_chapter=42,
                ),
            ],
            items=[
                ItemSnapshot(
                    name="Nanoblade",
                    item_type="weapon",
                    rarity="legendary",
                    acquired_chapter=20,
                    grants=["Shadow Strike"],
                ),
            ],
            chapter_changes=[
                StateChangeRecord(
                    chapter=14,
                    category="stat",
                    name="Perception",
                    action="gain",
                    value_delta=5,
                ),
            ],
            total_changes_to_date=45,
        )
        assert snap.level.level == 88
        assert len(snap.stats) == 1
        assert snap.items[0].grants == ["Shadow Strike"]

    def test_default_collections_are_independent(self):
        """Verify default_factory creates independent lists per instance."""
        snap1 = CharacterStateSnapshot(
            character_name="A",
            canonical_name="A",
            book_id="1",
            as_of_chapter=1,
            total_chapters_in_book=10,
        )
        snap2 = CharacterStateSnapshot(
            character_name="B",
            canonical_name="B",
            book_id="2",
            as_of_chapter=1,
            total_chapters_in_book=10,
        )
        snap1.stats.append(
            StatEntry(name="Strength", value=10, last_changed_chapter=1)
        )
        assert len(snap2.stats) == 0

    def test_serialization_roundtrip(self):
        snap = CharacterStateSnapshot(
            character_name="Jake Thayne",
            canonical_name="Jake Thayne",
            book_id="abc",
            as_of_chapter=14,
            total_chapters_in_book=100,
            level=LevelSnapshot(level=88, realm="D-grade", since_chapter=42),
            stats=[
                StatEntry(name="Perception", value=37, last_changed_chapter=14),
            ],
        )
        data = snap.model_dump()
        restored = CharacterStateSnapshot.model_validate(data)
        assert restored.level.level == 88
        assert restored.stats[0].name == "Perception"


class TestProgressionMilestone:
    def test_creates_milestone(self):
        m = ProgressionMilestone(
            chapter=14,
            category="stat",
            name="Perception",
            action="gain",
            value_delta=5,
        )
        assert m.chapter == 14
        assert m.detail == ""

    def test_creates_without_optional_fields(self):
        m = ProgressionMilestone(
            chapter=30,
            category="class",
            name="Avaricious Arcane Hunter",
            action="acquire",
        )
        assert m.value_delta is None
        assert m.value_after is None


class TestProgressionTimeline:
    def test_creates_empty(self):
        t = ProgressionTimeline(character_name="Jake", book_id="abc")
        assert t.milestones == []
        assert t.total == 0
        assert t.limit == 50

    def test_creates_with_milestones(self):
        t = ProgressionTimeline(
            character_name="Jake",
            book_id="abc",
            milestones=[
                ProgressionMilestone(
                    chapter=1,
                    category="skill",
                    name="Archer's Eye",
                    action="acquire",
                ),
                ProgressionMilestone(
                    chapter=14,
                    category="stat",
                    name="Perception",
                    action="gain",
                    value_delta=5,
                ),
            ],
            total=2,
            offset=0,
            limit=50,
        )
        assert len(t.milestones) == 2
        assert t.total == 2


class TestStatDiff:
    def test_creates_diff(self):
        diff = StatDiff(
            name="Perception", value_at_from=20, value_at_to=37, delta=17
        )
        assert diff.delta == 17
        assert diff.value_at_from == 20


class TestCategoryDiff:
    def test_creates_empty(self):
        cd = CategoryDiff()
        assert cd.gained == []
        assert cd.lost == []

    def test_creates_with_changes(self):
        cd = CategoryDiff(
            gained=["Shadow Strike", "Mark of the Hunter"],
            lost=["Basic Slash"],
        )
        assert len(cd.gained) == 2
        assert len(cd.lost) == 1


class TestCharacterComparison:
    def test_creates_diff(self):
        comp = CharacterComparison(
            character_name="Jake Thayne",
            book_id="abc",
            from_chapter=10,
            to_chapter=20,
            stat_diffs=[
                StatDiff(
                    name="Perception",
                    value_at_from=20,
                    value_at_to=37,
                    delta=17,
                ),
            ],
            skills=CategoryDiff(
                gained=["Mark of the Ambitious Hunter"], lost=[]
            ),
            classes=CategoryDiff(),
            titles=CategoryDiff(),
            items=CategoryDiff(),
            total_changes=12,
        )
        assert comp.stat_diffs[0].delta == 17

    def test_creates_minimal(self):
        comp = CharacterComparison(
            character_name="Jake Thayne",
            book_id="abc",
            from_chapter=1,
            to_chapter=50,
        )
        assert comp.level_from is None
        assert comp.level_to is None
        assert comp.stat_diffs == []
        assert comp.skills.gained == []
        assert comp.total_changes == 0


class TestCharacterSummary:
    def test_creates_summary(self):
        summary = CharacterSummary(
            name="Jake Thayne",
            canonical_name="Jake Thayne",
            role="protagonist",
            species="Human",
        )
        assert summary.top_skills == []
        assert summary.level is None

    def test_creates_full_summary(self):
        summary = CharacterSummary(
            name="Jake Thayne",
            canonical_name="Jake Thayne",
            role="protagonist",
            species="Human",
            level=88,
            realm="D-grade",
            active_class="Avaricious Arcane Hunter",
            top_skills=["Archer's Eye", "Mark of the Hunter", "Stealth"],
            description="A hunter from Earth",
        )
        assert summary.level == 88
        assert summary.active_class == "Avaricious Arcane Hunter"
        assert len(summary.top_skills) == 3
