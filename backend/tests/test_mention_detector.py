"""Tests for the programmatic mention detector (Pass 5a)."""

from __future__ import annotations

import pytest

from app.services.extraction.mention_detector import detect_mentions


class TestDetectMentions:
    """Test mention detection for known entities."""

    def test_exact_name_match(self):
        text = "Jake observait la forêt. Caroline le rejoignit."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
        assert mentions[0].entity_name == "Jake"
        assert mentions[0].char_offset_start == 0
        assert mentions[0].char_offset_end == 4
        # Check attributes
        assert mentions[0].attributes.get("mention_type") == "direct_name"

    def test_alias_match(self):
        text = "Le Chasseur Primordial avançait dans la nuit."
        entities = [
            {
                "canonical_name": "Jake",
                "entity_type": "character",
                "name": "Jake",
                "aliases": ["Le Chasseur Primordial"],
            },
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
        assert mentions[0].entity_name == "Jake"
        assert mentions[0].attributes.get("mention_type") == "alias"

    def test_multiple_mentions_same_entity(self):
        text = "Jake marchait. Jake s'arrêta."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 2

    def test_no_overlap_longer_wins(self):
        """Shorter mention inside longer should be deduplicated."""
        text = "Jake Summers marchait dans la rue."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake", "aliases": []},
            {"canonical_name": "Jake Summers", "entity_type": "character", "name": "Jake Summers", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
        assert mentions[0].entity_name == "Jake Summers"

    def test_case_insensitive(self):
        text = "jake marchait."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1

    def test_multiple_entities(self):
        text = "Jake et Caroline marchaient ensemble."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake", "aliases": []},
            {"canonical_name": "Caroline", "entity_type": "character", "name": "Caroline", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 2

    def test_skill_entity(self):
        text = "Il utilisa Pas de l'ombre pour disparaître."
        entities = [
            {
                "canonical_name": "Pas de l'ombre",
                "entity_type": "skill",
                "name": "Pas de l'ombre",
                "aliases": ["Shadowstep"],
            },
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
        assert mentions[0].entity_type == "skill"

    def test_empty_entities(self):
        mentions = detect_mentions("Some text", [])
        assert mentions == []

    def test_empty_text(self):
        mentions = detect_mentions("", [{"canonical_name": "Jake", "entity_type": "character", "name": "Jake"}])
        assert mentions == []

    def test_short_names_skipped(self):
        """Names shorter than 2 chars should be skipped (too many false positives)."""
        text = "Il a dit X."
        entities = [
            {"canonical_name": "X", "entity_type": "character", "name": "X", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 0

    def test_grounded_entity_fields(self):
        """Verify all GroundedEntity fields are set correctly."""
        text = "Jake was here."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
        m = mentions[0]
        assert m.entity_type == "character"
        assert m.entity_name == "Jake"
        assert m.extraction_text == "Jake"
        assert m.pass_name == "mention_detect"
        assert m.alignment_status == "exact"
        assert m.confidence == 1.0

    def test_canonical_different_from_name(self):
        """When canonical_name differs from name, both should be searchable."""
        text = "Villy spoke. The Malefic Viper watched."
        entities = [
            {
                "canonical_name": "Vilastromoz",
                "entity_type": "character",
                "name": "Villy",
                "aliases": ["The Malefic Viper"],
            },
        ]
        mentions = detect_mentions(text, entities)
        # "Villy" matches as direct_name, "The Malefic Viper" matches as alias
        # "Vilastromoz" is canonical but doesn't appear in text
        assert len(mentions) == 2
        names = {m.entity_name for m in mentions}
        assert names == {"Vilastromoz"}

    def test_word_boundary_prevents_partial_match(self):
        """Should not match 'Jake' inside 'Jakesson'."""
        text = "Jakesson marchait dans la rue."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 0

    def test_entity_without_aliases_key(self):
        """Entity dict missing 'aliases' key should still work."""
        text = "Jake was here."
        entities = [
            {"canonical_name": "Jake", "entity_type": "character", "name": "Jake"},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
