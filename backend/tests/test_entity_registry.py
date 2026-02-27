"""Tests for EntityRegistry — growing context for extraction."""
import pytest

from app.services.extraction.entity_registry import EntityRegistry, RegistryEntry


class TestEntityRegistryBasics:
    def test_empty_registry(self):
        reg = EntityRegistry()
        assert reg.entity_count == 0
        assert reg.alias_count == 0

    def test_add_entity(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake", "the hunter"])
        assert reg.entity_count == 1
        assert reg.alias_count == 2

    def test_add_updates_existing(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"])
        reg.add("Jake Thayne", "Character", aliases=["the hunter"])
        assert reg.entity_count == 1
        assert reg.alias_count == 2  # Both aliases registered

    def test_lookup_by_name(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character")
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.entity_type == "Character"

    def test_lookup_by_alias(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["the hunter"])
        entry = reg.lookup("the hunter")
        assert entry is not None
        assert entry.canonical_name == "jake thayne"

    def test_lookup_case_insensitive(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character")
        assert reg.lookup("jake thayne") is not None
        assert reg.lookup("JAKE THAYNE") is not None

    def test_lookup_miss(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character")
        assert reg.lookup("Unknown Person") is None

    def test_update_last_seen(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character")
        reg.update_last_seen("Jake Thayne", 42)
        entry = reg.lookup("Jake Thayne")
        assert entry is not None
        assert entry.last_seen_chapter == 42

    def test_get_all_names(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake", "the hunter"])
        names = reg.get_all_names()
        assert "jake thayne" in names
        assert "jake" in names
        assert "the hunter" in names


class TestEntityRegistryContext:
    def test_to_prompt_context(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"], significance="protagonist")
        reg.add("Arcane Powershot", "Skill")
        context = reg.to_prompt_context(max_tokens=500)
        assert "jake thayne" in context
        assert "arcane powershot" in context

    def test_prompt_context_respects_max_tokens(self):
        reg = EntityRegistry()
        for i in range(100):
            reg.add(f"Entity {i}", "Character", aliases=[f"alias_{i}"])
        context = reg.to_prompt_context(max_tokens=50)
        # Should be truncated — not all 100 entities
        assert context.count("\n") < 99

    def test_add_chapter_summary(self):
        reg = EntityRegistry()
        reg.add_chapter_summary(1, "Jake enters the tutorial.")
        reg.add_chapter_summary(2, "Jake gains his class.")
        assert len(reg.chapter_summaries) == 2
        assert reg.chapter_summaries[0] == "Jake enters the tutorial."


class TestEntityRegistrySerialization:
    def test_to_dict(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"])
        data = reg.to_dict()
        assert "entities" in data
        assert "alias_map" in data
        assert len(data["entities"]) == 1

    def test_from_dict(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"])
        reg.update_last_seen("Jake Thayne", 10)
        data = reg.to_dict()
        reg2 = EntityRegistry.from_dict(data)
        assert reg2.entity_count == 1
        assert reg2.lookup("Jake") is not None
        entry = reg2.lookup("Jake")
        assert entry is not None
        assert entry.last_seen_chapter == 10

    def test_roundtrip(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"])
        reg.add("Archer", "Class")
        reg.add_chapter_summary(1, "Chapter one summary.")
        data = reg.to_dict()
        reg2 = EntityRegistry.from_dict(data)
        assert reg2.entity_count == 2
        assert len(reg2.chapter_summaries) == 1

    def test_merge_registries(self):
        reg1 = EntityRegistry()
        reg1.add("Jake Thayne", "Character")
        reg2 = EntityRegistry()
        reg2.add("Miranda Wells", "Character")
        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 2
        assert merged.lookup("Jake Thayne") is not None
        assert merged.lookup("Miranda Wells") is not None

    def test_merge_deduplicates(self):
        reg1 = EntityRegistry()
        reg1.add("Jake Thayne", "Character", aliases=["Jake"])
        reg2 = EntityRegistry()
        reg2.add("Jake Thayne", "Character", aliases=["the hunter"])
        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 1
        assert merged.alias_count == 2  # Both aliases
