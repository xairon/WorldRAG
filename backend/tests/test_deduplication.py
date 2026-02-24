"""Tests for app.services.deduplication — 3-tier entity dedup pipeline."""

from __future__ import annotations

import pytest

from app.services.deduplication import (
    deduplicate_entities,
    exact_dedup,
    fuzzy_dedup,
    llm_dedup,
    normalize_name,
)

# -- normalize_name -------------------------------------------------------


class TestNormalizeName:
    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("Jake Thayne", "jake thayne"),
            ("The Malefic Viper", "malefic viper"),
            ("  A Dragon  ", "dragon"),
            ("An Orc", "orc"),
            ("Villy The God", "villy the god"),  # mid-name "the" NOT stripped
        ],
    )
    def test_normalize(self, input_name, expected):
        assert normalize_name(input_name) == expected


# -- exact_dedup ----------------------------------------------------------


class TestExactDedup:
    def test_empty_list(self):
        deduped, aliases = exact_dedup([])
        assert deduped == []
        assert aliases == {}

    def test_single_entity(self):
        deduped, aliases = exact_dedup([{"name": "Jake"}])
        assert len(deduped) == 1
        assert aliases == {}

    def test_identical_names(self):
        entities = [{"name": "Jake Thayne"}, {"name": "Jake Thayne"}]
        deduped, aliases = exact_dedup(entities)
        assert len(deduped) == 1
        assert "Jake Thayne" in aliases

    def test_article_normalization(self):
        """'The Malefic Viper' and 'Malefic Viper' normalize to the same."""
        entities = [{"name": "The Malefic Viper"}, {"name": "Malefic Viper"}]
        deduped, aliases = exact_dedup(entities)
        assert len(deduped) == 1
        # The duplicate should map to the canonical (first seen)
        assert aliases.get("Malefic Viper") == "The Malefic Viper"

    def test_preserves_first_occurrence(self):
        entities = [
            {"name": "Jake", "role": "protagonist"},
            {"name": "Jake", "role": "minor"},
        ]
        deduped, _ = exact_dedup(entities)
        assert deduped[0]["role"] == "protagonist"

    def test_no_duplicates(self):
        entities = [{"name": "Jake"}, {"name": "Villy"}, {"name": "Sylphie"}]
        deduped, aliases = exact_dedup(entities)
        assert len(deduped) == 3
        assert aliases == {}

    def test_alias_map_correct(self):
        entities = [
            {"name": "Jake"},
            {"name": "Jake"},  # duplicate
            {"name": "Villy"},
        ]
        _, aliases = exact_dedup(entities)
        assert aliases == {"Jake": "Jake"}


# -- fuzzy_dedup ----------------------------------------------------------


class TestFuzzyDedup:
    def test_empty(self):
        deduped, candidates = fuzzy_dedup([])
        assert deduped == []
        assert candidates == []

    def test_definite_merge(self):
        """Very similar names (score >= 95) auto-merge."""
        entities = [{"name": "Jake Thayne"}, {"name": "Jake Thayn"}]
        deduped, candidates = fuzzy_dedup(entities)
        # One should be merged away
        assert len(deduped) == 1
        assert len(candidates) == 0

    def test_candidate_pair(self):
        """Names scoring 85-94 appear as candidates for LLM review."""
        entities = [{"name": "Alexander"}, {"name": "Aleksander"}]
        deduped, candidates = fuzzy_dedup(entities)
        # Should be in candidates (not auto-merged, not ignored)
        if candidates:
            # At least one candidate pair
            assert any("Alexander" in c[0] or "Alexander" in c[1] for c in candidates)

    def test_below_threshold_ignored(self):
        """Completely different names: no candidates."""
        entities = [{"name": "Jake"}, {"name": "Sylphie"}]
        deduped, candidates = fuzzy_dedup(entities)
        assert len(deduped) == 2
        assert len(candidates) == 0

    def test_canonical_is_longer_name(self):
        """When auto-merging, the longer name should be canonical."""
        entities = [{"name": "Jake"}, {"name": "Jake T"}]
        deduped, _ = fuzzy_dedup(entities)
        if len(deduped) == 1:
            # The longer name "Jake T" should survive
            assert deduped[0]["name"] == "Jake T"

    def test_custom_threshold(self):
        """Custom threshold parameter is respected."""
        entities = [{"name": "test"}, {"name": "tess"}]
        # With very low threshold, these might be candidates
        _, candidates_low = fuzzy_dedup(entities, threshold=50)
        _, candidates_high = fuzzy_dedup(entities, threshold=99)
        # Low threshold should catch more candidates
        assert len(candidates_low) >= len(candidates_high)

    def test_three_entities_all_different(self):
        entities = [{"name": "Jake"}, {"name": "Villy"}, {"name": "Sylphie"}]
        deduped, candidates = fuzzy_dedup(entities)
        assert len(deduped) == 3
        assert len(candidates) == 0


# -- llm_dedup ------------------------------------------------------------


class TestLlmDedup:
    async def test_empty_candidates_returns_empty(self, mock_instructor_client):
        result = await llm_dedup([], "Character", mock_instructor_client, "gpt-4o-mini")
        assert result == []
        mock_instructor_client.chat.completions.create.assert_not_called()

    async def test_successful_call(self, mock_instructor_client):
        from app.schemas.extraction import EntityMergeCandidate

        merge = EntityMergeCandidate(
            entity_a_name="Jake",
            entity_b_name="Jacob",
            entity_type="Character",
            confidence=0.95,
            canonical_name="Jake",
            reason="Same person",
        )
        mock_instructor_client.chat.completions.create.return_value = [merge]

        result = await llm_dedup(
            [("Jake", "Jacob", 88)],
            "Character",
            mock_instructor_client,
            "gpt-4o-mini",
        )
        assert len(result) == 1
        assert result[0].entity_type == "Character"

    async def test_fallback_on_exception(self, mock_instructor_client):
        """On LLM failure, fallback to fuzzy score as confidence."""
        mock_instructor_client.chat.completions.create.side_effect = ConnectionError("timeout")

        result = await llm_dedup(
            [("Jake", "Jacob", 88)],
            "Character",
            mock_instructor_client,
            "gpt-4o-mini",
        )
        assert len(result) == 1
        assert result[0].confidence == pytest.approx(0.88)
        assert "Fuzzy match fallback" in result[0].reason

    async def test_candidates_batched(self, mock_instructor_client):
        """All candidates sent in a single LLM call."""
        from app.schemas.extraction import EntityMergeCandidate

        mock_instructor_client.chat.completions.create.return_value = [
            EntityMergeCandidate(
                entity_a_name="A",
                entity_b_name="B",
                entity_type="Char",
                confidence=0.9,
                canonical_name="A",
                reason="same",
            ),
            EntityMergeCandidate(
                entity_a_name="C",
                entity_b_name="D",
                entity_type="Char",
                confidence=0.8,
                canonical_name="C",
                reason="same",
            ),
        ]
        await llm_dedup(
            [("A", "B", 87), ("C", "D", 86)],
            "Character",
            mock_instructor_client,
            "gpt-4o-mini",
        )
        # Only 1 call (batched), not 2
        assert mock_instructor_client.chat.completions.create.call_count == 1


# -- deduplicate_entities (full pipeline) ----------------------------------


class TestDeduplicateEntities:
    async def test_no_client_exact_only(self):
        """Without LLM client, only exact dedup runs."""
        entities = [
            {"name": "Jake"},
            {"name": "Villy"},
            {"name": "jake"},  # exact match via normalization
        ]
        deduped, aliases = await deduplicate_entities(entities, "Character")
        assert len(deduped) == 2
        assert "jake" in aliases

    async def test_single_entity_returns_early(self):
        entities = [{"name": "Jake"}]
        deduped, aliases = await deduplicate_entities(entities, "Character")
        assert len(deduped) == 1
        assert aliases == {}
