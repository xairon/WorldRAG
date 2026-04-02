"""Tests for EntityRegistry — growing context accumulator."""

from app.services.extraction.entity_registry import EntityRegistry


class TestAdd:
    def test_add_new_entity(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake"], significance="protagonist")
        assert reg.entity_count == 1
        assert reg.alias_count == 1

    def test_add_duplicate_merges_aliases(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake"])
        reg.add("Jake Thayne", "character", aliases=["The Primal Hunter"])
        assert reg.entity_count == 1
        assert reg.alias_count == 2

    def test_add_updates_significance(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", significance="minor")
        reg.add("Jake Thayne", "character", significance="protagonist")
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.significance == "protagonist"

    def test_add_updates_description(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", description="A hunter")
        reg.add("Jake Thayne", "character", description="The Primal Hunter")
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.description == "The Primal Hunter"


class TestLookup:
    def test_lookup_by_canonical_name(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        assert reg.lookup("Jake Thayne") is not None

    def test_lookup_case_insensitive(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        assert reg.lookup("jake thayne") is not None
        assert reg.lookup("JAKE THAYNE") is not None

    def test_lookup_by_alias(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake", "The Primal Hunter"])
        entry = reg.lookup("Jake")
        assert entry is not None
        assert entry.canonical_name == "jake thayne"

    def test_lookup_alias_case_insensitive(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["The Primal Hunter"])
        assert reg.lookup("the primal hunter") is not None

    def test_lookup_unknown_returns_none(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        assert reg.lookup("Unknown Entity") is None


class TestUpdateLastSeen:
    def test_update_last_seen(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character")
        reg.update_last_seen("Jake Thayne", 5)
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.last_seen_chapter == 5

    def test_update_last_seen_via_alias(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake"])
        reg.update_last_seen("Jake", 10)
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.last_seen_chapter == 10

    def test_update_last_seen_unknown_is_noop(self):
        reg = EntityRegistry()
        reg.update_last_seen("Nobody", 1)  # should not raise


class TestChapterSummaries:
    def test_add_chapter_summary(self):
        reg = EntityRegistry()
        reg.add_chapter_summary(1, "Jake wakes up in a forest.")
        assert reg.chapter_summaries[0] == "Jake wakes up in a forest."

    def test_add_chapter_summary_fills_gaps(self):
        reg = EntityRegistry()
        reg.add_chapter_summary(3, "Third chapter summary")
        assert len(reg.chapter_summaries) == 3
        assert reg.chapter_summaries[0] == ""
        assert reg.chapter_summaries[2] == "Third chapter summary"


class TestPromptContext:
    def test_empty_registry(self):
        reg = EntityRegistry()
        assert reg.to_prompt_context() == ""

    def test_protagonist_first(self):
        reg = EntityRegistry()
        reg.add("Minor NPC", "character", significance="minor")
        reg.add("Jake", "character", significance="protagonist")
        context = reg.to_prompt_context()
        lines = context.strip().split("\n")
        assert "jake" in lines[0].lower()

    def test_respects_max_tokens(self):
        reg = EntityRegistry()
        for i in range(100):
            reg.add(f"Entity {i}", "character", description="A" * 200)
        context = reg.to_prompt_context(max_tokens=50)
        # Should be truncated well before 100 entities
        assert context.count("\n") < 50


class TestSerialization:
    def test_roundtrip(self):
        reg = EntityRegistry()
        reg.add(
            "Jake Thayne",
            "character",
            aliases=["Jake"],
            significance="protagonist",
            first_seen_chapter=1,
            description="A hunter",
        )
        reg.update_last_seen("Jake Thayne", 5)
        reg.add_chapter_summary(1, "First chapter")

        data = reg.to_dict()
        restored = EntityRegistry.from_dict(data)

        assert restored.entity_count == 1
        entry = restored.lookup("Jake Thayne")
        assert entry is not None
        assert entry.significance == "protagonist"
        assert entry.last_seen_chapter == 5
        assert entry.description == "A hunter"
        assert restored.chapter_summaries == ["First chapter"]

    def test_roundtrip_with_aliases(self):
        reg = EntityRegistry()
        reg.add("Jake", "character", aliases=["The Hunter", "Thayne"])

        data = reg.to_dict()
        restored = EntityRegistry.from_dict(data)

        assert restored.lookup("The Hunter") is not None
        assert restored.lookup("Thayne") is not None

    def test_from_dict_empty(self):
        reg = EntityRegistry.from_dict({})
        assert reg.entity_count == 0


class TestMerge:
    def test_merge_two_registries(self):
        reg1 = EntityRegistry()
        reg1.add("Jake", "character", significance="protagonist")

        reg2 = EntityRegistry()
        reg2.add("Casper", "character", significance="minor")

        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 2
        assert merged.lookup("Jake") is not None
        assert merged.lookup("Casper") is not None

    def test_merge_overlapping_entities(self):
        reg1 = EntityRegistry()
        reg1.add("Jake", "character", aliases=["Thayne"])

        reg2 = EntityRegistry()
        reg2.add("Jake", "character", aliases=["The Hunter"])

        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 1
        entry = merged.lookup("Jake")
        assert entry is not None

    def test_merge_empty(self):
        merged = EntityRegistry.merge()
        assert merged.entity_count == 0


class TestGetAllNames:
    def test_includes_canonical_and_aliases(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "character", aliases=["Jake", "The Primal Hunter"])
        names = reg.get_all_names()
        assert "jake thayne" in names
        assert "jake" in names
        assert "the primal hunter" in names
