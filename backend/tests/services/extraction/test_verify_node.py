"""Tests for verify_extractions_node — heuristic entity filtering + metadata."""

import pytest

from app.services.extraction.verify import (
    _verify_single_entity,
    extract_chunk_metadata,
    verify_extractions_node,
)


# ── extract_chunk_metadata ──────────────────────────────────────────────


class TestExtractChunkMetadata:
    def test_empty_text(self):
        meta = extract_chunk_metadata("")
        assert meta["dialogue_ratio"] == 0.0
        assert meta["pov_character"] is None
        assert meta["scene_count"] == 1

    def test_dialogue_ratio(self):
        text = '"Hello," said Jake. "How are you?" asked Miranda. Some narrative text here.'
        meta = extract_chunk_metadata(text)
        assert meta["dialogue_ratio"] > 0.0
        assert meta["dialogue_ratio"] < 1.0

    def test_first_person_pov(self):
        text = "I thought about the forest. I felt the cold wind. The trees swayed."
        meta = extract_chunk_metadata(text)
        assert meta["pov_character"] == "(first-person)"

    def test_third_person_pov(self):
        text = "Jake thought about the mission. Jake felt uneasy. Miranda walked away."
        meta = extract_chunk_metadata(text)
        assert meta["pov_character"] == "Jake"

    def test_scene_count_with_breaks(self):
        text = "Scene one text.\n\n* * *\n\nScene two text.\n\n---\n\nScene three text."
        meta = extract_chunk_metadata(text)
        assert meta["scene_count"] == 3

    def test_scene_count_no_breaks(self):
        text = "Just a single continuous scene with no breaks at all."
        meta = extract_chunk_metadata(text)
        assert meta["scene_count"] == 1


# ── _verify_single_entity ──────────────────────────────────────────────


class TestVerifySingleEntity:
    def test_valid_entity_in_text(self):
        text = "Jake walked through the forest."
        text_lower = text.lower()
        entity = {"name": "Jake", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is True
        assert reason == ""

    def test_entity_not_in_text(self):
        text = "The forest was dark."
        text_lower = text.lower()
        entity = {"name": "Miranda", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is False
        assert "name_not_in_text" in reason

    def test_generic_role_rejected(self):
        text = "The guard stood at the gate."
        text_lower = text.lower()
        entity = {"name": "guard", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is False
        assert "generic_role" in reason

    def test_generic_role_plural_rejected(self):
        text = "The soldiers marched through the town."
        text_lower = text.lower()
        entity = {"name": "soldiers", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is False
        assert "generic_role" in reason

    def test_non_character_generic_name_ok(self):
        """Generic role names only block entity_type='character'."""
        text = "The guard stood at the gate."
        text_lower = text.lower()
        entity = {"name": "guard", "entity_type": "creature"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is True

    def test_multiword_name_partial_match(self):
        """Multi-word name: at least 2 significant words must appear."""
        text = "The dark iron was strong."
        text_lower = text.lower()
        entity = {"name": "Iron Sword of Power", "entity_type": "item"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        # "iron" appears but "sword" and "power" don't — only 1 of 3 significant words
        assert is_valid is False

    def test_multiword_name_enough_words(self):
        text = "The dark iron forge burned hot with power."
        text_lower = text.lower()
        entity = {"name": "Iron Power", "entity_type": "item"}
        is_valid, reason = _verify_single_entity(entity, text_lower, text)
        assert is_valid is True

    def test_empty_name_rejected(self):
        text = "Some text."
        entity = {"name": "", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text.lower(), text)
        assert is_valid is False
        assert reason == "empty_name"

    def test_canonical_name_used(self):
        """Uses canonical_name if name is missing."""
        text = "Jake fought bravely."
        entity = {"canonical_name": "Jake", "entity_type": "character"}
        is_valid, reason = _verify_single_entity(entity, text.lower(), text)
        assert is_valid is True


# ── verify_extractions_node (full node) ─────────────────────────────────


class TestVerifyExtractionsNode:
    @pytest.mark.asyncio
    async def test_filters_hallucinated_entities(self):
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": "Jake walked through the forest.",
            "entities": [
                {"name": "Jake", "entity_type": "character"},
                {"name": "Miranda", "entity_type": "character"},  # not in text
            ],
        }
        result = await verify_extractions_node(state)
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Jake"

    @pytest.mark.asyncio
    async def test_returns_chunk_metadata(self):
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": '"Hello," Jake said. I thought about it.',
            "entities": [],
        }
        result = await verify_extractions_node(state)
        assert "chunk_metadata" in result
        assert "dialogue_ratio" in result["chunk_metadata"]
        assert "pov_character" in result["chunk_metadata"]
        assert "scene_count" in result["chunk_metadata"]

    @pytest.mark.asyncio
    async def test_empty_entities_returns_metadata_only(self):
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": "Some text.",
            "entities": [],
        }
        result = await verify_extractions_node(state)
        assert "chunk_metadata" in result

    @pytest.mark.asyncio
    async def test_all_valid_entities_pass_through(self):
        text = "Jake and Casper explored the Dark Forest."
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": text,
            "entities": [
                {"name": "Jake", "entity_type": "character"},
                {"name": "Casper", "entity_type": "character"},
                {"name": "Dark Forest", "entity_type": "location"},
            ],
        }
        result = await verify_extractions_node(state)
        assert len(result["entities"]) == 3

    @pytest.mark.asyncio
    async def test_filters_generic_role_characters(self):
        text = "The guard and Jake stood at the gate."
        state = {
            "book_id": "test",
            "chapter_number": 1,
            "chapter_text": text,
            "entities": [
                {"name": "Jake", "entity_type": "character"},
                {"name": "guard", "entity_type": "character"},
            ],
        }
        result = await verify_extractions_node(state)
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Jake"
