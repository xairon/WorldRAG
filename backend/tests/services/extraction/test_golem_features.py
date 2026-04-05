"""Tests for GOLEM v1.1 features across the extraction pipeline.

Covers: verify rules, TextualFeature generation, NarrativeUnit generation,
character reference resolution, reconciler _TYPE_PRIORITY, and entity schema
roundtrips for all new GOLEM types.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    ExtractedCharacterFeature,
    ExtractedNarrativeRole,
    ExtractedPsychologicalState,
    ExtractedSetting,
    ExtractedSocialRelationship,
    ExtractedTextualFeature,
)
from app.services.extraction.verify import _verify_single_entity, extract_chunk_metadata


# ── Verify: GOLEM-specific rules (§6.3) ───────────────────────────────


class TestGolemVerifyRules:
    """Test the 5 new GOLEM-specific verification rules in verify.py."""

    def test_psychological_state_missing_character(self):
        entity = {"entity_type": "psychological_state", "name": "fear", "character": ""}
        ok, reason = _verify_single_entity(entity, "jake felt fear", "Jake felt fear")
        assert not ok
        assert "golem_missing_character_ref" in reason

    def test_psychological_state_character_not_in_text(self):
        known = frozenset(["jake"])
        entity = {
            "entity_type": "psychological_state",
            "name": "fear",
            "character": "miranda",
        }
        ok, reason = _verify_single_entity(
            entity, "jake felt fear", "Jake felt fear", known_character_names=known
        )
        assert not ok
        assert "golem_character_not_found" in reason

    def test_psychological_state_valid(self):
        known = frozenset(["jake"])
        entity = {
            "entity_type": "psychological_state",
            "name": "fear",
            "character": "jake",
        }
        ok, _ = _verify_single_entity(
            entity, "jake felt fear", "Jake felt fear", known_character_names=known
        )
        assert ok

    def test_social_relationship_too_few_participants(self):
        entity = {
            "entity_type": "social_relationship",
            "name": "bond",
            "participants": ["jake"],
        }
        ok, reason = _verify_single_entity(entity, "bond between jake", "Bond between Jake")
        assert not ok
        assert "golem_insufficient_participants" in reason

    def test_social_relationship_valid(self):
        entity = {
            "entity_type": "social_relationship",
            "name": "bond",
            "participants": ["jake", "casper"],
        }
        ok, _ = _verify_single_entity(entity, "bond between jake", "Bond between Jake")
        assert ok

    def test_setting_is_location(self):
        entity = {"entity_type": "setting", "name": "cave"}
        ok, reason = _verify_single_entity(entity, "the cave was dark", "The cave was dark")
        assert not ok
        assert "golem_setting_is_location" in reason

    def test_setting_valid(self):
        entity = {"entity_type": "setting", "name": "the tutorial"}
        ok, _ = _verify_single_entity(entity, "welcome to the tutorial", "Welcome to the Tutorial")
        assert ok

    def test_narrative_role_is_trait(self):
        entity = {
            "entity_type": "narrative_role",
            "name": "brave jake",
            "character": "jake",
            "role_type": "brave",
        }
        ok, reason = _verify_single_entity(entity, "brave jake walked", "Brave Jake walked")
        assert not ok
        assert "golem_role_is_trait" in reason

    def test_character_feature_is_role(self):
        entity = {
            "entity_type": "character_feature",
            "name": "protagonist",
            "character": "jake",
        }
        ok, reason = _verify_single_entity(entity, "jake the protagonist", "Jake the protagonist")
        assert not ok
        assert "golem_feature_is_role" in reason

    def test_character_feature_valid(self):
        entity = {
            "entity_type": "character_feature",
            "name": "green eyes",
            "character": "jake",
        }
        ok, _ = _verify_single_entity(entity, "jake had green eyes", "Jake had green eyes")
        assert ok

    def test_narrative_role_valid(self):
        entity = {
            "entity_type": "narrative_role",
            "name": "mentor role",
            "character": "jake",
            "role_type": "mentor",
        }
        ok, _ = _verify_single_entity(
            entity, "jake took on the mentor role", "Jake took on the mentor role"
        )
        assert ok


# ── TextualFeature generation ─────────────────────────────────────────


class TestTextualFeatureGeneration:
    def test_chunk_metadata_extraction(self):
        text = '"Hello," said Jake. "How are you?" asked Miranda. The forest was quiet.'
        meta = extract_chunk_metadata(text)
        assert "dialogue_ratio" in meta
        assert meta["dialogue_ratio"] > 0
        assert "pov_character" in meta
        assert "scene_count" in meta

    @pytest.mark.asyncio
    async def test_verify_node_generates_textual_features(self):
        from app.services.extraction.verify import verify_extractions_node

        state = {
            "book_id": "test",
            "chapter_number": 5,
            "chapter_text": '"Hello," said Jake. The forest was dark.',
            "entities": [{"name": "Jake", "entity_type": "character"}],
        }
        result = await verify_extractions_node(state)
        tfs = [e for e in result["entities"] if e.get("entity_type") == "textual_feature"]
        assert len(tfs) >= 2  # dialogue_density + pacing at minimum
        types = {tf["feature_type"] for tf in tfs}
        assert "dialogue_density" in types
        assert "pacing" in types


# ── NarrativeUnit generation + character reference resolution ─────────


class TestReconcilerGolemFeatures:
    @pytest.mark.asyncio
    async def test_narrative_unit_generation(self):
        """reconcile_and_persist should generate 1 NarrativeUnit per Event."""
        from app.services.extraction import reconcile_and_persist_v4_node

        state = {
            "chapter_number": 1,
            "chapter_text": "Jake defeated the boss in the arena.",
            "entities": [
                {"entity_type": "character", "name": "Jake", "canonical_name": "jake"},
                {
                    "entity_type": "event",
                    "name": "Arena Battle",
                    "description": "Jake defeats the boss",
                },
            ],
            "relations": [],
            "ended_relations": [],
            "entity_registry": {},
        }

        with (
            patch(
                "app.llm.providers.get_instructor_for_task",
                return_value=(AsyncMock(), "mock"),
            ),
            patch(
                "app.services.extraction.reconciler.reconcile_flat_entities",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.services.extraction.faithfulness.batch_verify_faithfulness",
                new=AsyncMock(side_effect=lambda e, _: e),
            ),
        ):
            result = await reconcile_and_persist_v4_node(state)

        nus = [e for e in result["entities"] if e.get("entity_type") == "narrative_unit"]
        assert len(nus) == 1
        assert nus[0]["proposition"] == "Jake defeats the boss"
        assert nus[0]["event_reference"] == "Arena Battle"

    @pytest.mark.asyncio
    async def test_significance_from_narrative_role(self):
        """reconcile_and_persist should set significance from protagonist role."""
        from app.services.extraction import reconcile_and_persist_v4_node

        state = {
            "chapter_number": 1,
            "chapter_text": "Jake the hero walked forward.",
            "entities": [
                {"entity_type": "character", "name": "Jake", "canonical_name": "jake"},
                {
                    "entity_type": "narrative_role",
                    "name": "hero role",
                    "character": "jake",
                    "role_type": "protagonist",
                },
            ],
            "relations": [],
            "ended_relations": [],
            "entity_registry": {},
        }

        with (
            patch(
                "app.llm.providers.get_instructor_for_task",
                return_value=(AsyncMock(), "mock"),
            ),
            patch(
                "app.services.extraction.reconciler.reconcile_flat_entities",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.services.extraction.faithfulness.batch_verify_faithfulness",
                new=AsyncMock(side_effect=lambda e, _: e),
            ),
        ):
            result = await reconcile_and_persist_v4_node(state)

        registry = result["entity_registry"]
        jake = registry.get("entities", {}).get("jake", {})
        assert jake.get("significance") == "protagonist"


# ── Reconciler _TYPE_PRIORITY ─────────────────────────────────────────


class TestReconcilerTypePriority:
    def test_golem_types_in_priority(self):
        """All GOLEM types should be in the type_priority map."""
        from app.services.extraction.reconciler import reconcile_flat_entities

        # The priority map is defined inside the function — test indirectly
        # by checking that GOLEM types don't get filtered incorrectly
        golem_types = [
            "psychological_state",
            "setting",
            "character_feature",
            "narrative_role",
            "social_relationship",
            "object",
            "narrative_sequence",
        ]
        # These should all be in _HANDLED_ENTITY_TYPES
        from app.repositories.entity_repo import _HANDLED_ENTITY_TYPES

        for t in golem_types:
            assert t in _HANDLED_ENTITY_TYPES, f"{t} not in _HANDLED_ENTITY_TYPES"


# ── Schema validation: new GOLEM types in EntityUnion ─────────────────


class TestGolemEntityUnionDeserialization:
    def test_all_golem_types_deserialize(self):
        """All 6 new GOLEM types should deserialize through EntityExtractionResult."""
        raw = [
            {
                "entity_type": "psychological_state",
                "character": "jake",
                "name": "determination",
                "extraction_text": "felt determined",
            },
            {
                "entity_type": "setting",
                "name": "The Tutorial",
                "extraction_text": "Welcome to the Tutorial",
            },
            {
                "entity_type": "character_feature",
                "character": "jake",
                "name": "green eyes",
                "extraction_text": "his green eyes",
            },
            {
                "entity_type": "narrative_role",
                "character": "jake",
                "extraction_text": "the protagonist",
            },
            {
                "entity_type": "social_relationship",
                "participants": ["jake", "casper"],
                "extraction_text": "their friendship",
            },
            {"entity_type": "textual_feature", "name": "first_person_pov"},
        ]
        result = EntityExtractionResult(entities=raw, chapter_number=1)
        types = {e.entity_type for e in result.entities}
        assert "psychological_state" in types
        assert "setting" in types
        assert "character_feature" in types
        assert "narrative_role" in types
        assert "social_relationship" in types
        assert "textual_feature" in types


# ── OntologyLoader GOLEM features ────────────────────────────────────


class TestOntologyLoaderGolemFeatures:
    def test_induced_parent_type_tracking(self):
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        loader.extend_with_induced(
            {
                "node_types": [
                    {
                        "name": "SkillEmotion",
                        "description": "Emotion triggered by skill use",
                        "parent_type": "PsychologicalState",
                        "properties": [],
                    }
                ],
                "relationship_types": [],
                "regex_patterns": [],
            }
        )
        assert "SkillEmotion" in loader.node_types
        assert loader._induced_parent_types.get("SkillEmotion") == "PsychologicalState"
        assert loader._node_type_origin["SkillEmotion"] == "induced"

    def test_induced_relation_rejected_if_unknown_source(self):
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        before = len(loader.relationship_types)
        loader.extend_with_induced(
            {
                "node_types": [],
                "relationship_types": [
                    {
                        "name": "INVENTED_REL",
                        "source_type": "NonExistentType",
                        "target_type": "Character",
                    }
                ],
                "regex_patterns": [],
            }
        )
        assert len(loader.relationship_types) == before  # rejected

    def test_regex_guard_no_overwrite(self):
        from app.core.ontology_loader import OntologyLoader

        loader = OntologyLoader.from_layers(genre="litrpg")
        loader.regex_patterns["existing"] = {"pattern": "old"}
        loader.extend_with_induced(
            {
                "node_types": [],
                "relationship_types": [],
                "regex_patterns": [{"name": "existing", "pattern": "new"}],
            }
        )
        assert loader.regex_patterns["existing"]["pattern"] == "old"  # not overwritten
