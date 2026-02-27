"""Tests for V3 reconciliation with cross-book matching and ontology schemas."""

import pytest

from app.schemas.ontology import OntologyChange, OntologyChangelog, RegexProposal


class TestOntologyChange:
    def test_create(self):
        change = OntologyChange(
            change_type="add_entity_type",
            layer="series",
            target="PrimordialChurch",
            proposed_by="auto_discovery",
            discovered_in_book=1,
            discovered_in_chapter=42,
            confidence=0.85,
            evidence=["[Blessing of Vilastromoz received]"],
        )
        assert change.status == "proposed"
        assert change.change_type == "add_entity_type"
        assert change.layer == "series"
        assert change.target == "PrimordialChurch"
        assert change.confidence == 0.85
        assert len(change.evidence) == 1

    def test_changelog(self):
        changelog = OntologyChangelog(series_name="primal_hunter")
        changelog.add_change(
            OntologyChange(
                change_type="add_regex",
                layer="series",
                target="nevermore_floor",
                proposed_by="auto_discovery",
                discovered_in_book=3,
                discovered_in_chapter=100,
                confidence=0.9,
            )
        )
        assert len(changelog.get_pending()) == 1
        assert len(changelog.get_applied()) == 0

    def test_changelog_applied(self):
        changelog = OntologyChangelog(series_name="primal_hunter")
        changelog.add_change(
            OntologyChange(
                change_type="add_entity_type",
                layer="genre",
                target="Floor",
                proposed_by="auto_discovery",
                discovered_in_book=3,
                discovered_in_chapter=100,
                confidence=0.95,
                status="applied",
            )
        )
        assert len(changelog.get_pending()) == 0
        assert len(changelog.get_applied()) == 1

    def test_regex_proposal(self):
        proposal = RegexProposal(
            proposed_pattern=r"\[Floor (\d+) of Nevermore\]",
            entity_type="Floor",
            captures={"number": 1},
            example_matches=["[Floor 1 of Nevermore]", "[Floor 42 of Nevermore]"],
            frequency=15,
            confidence=0.92,
            discovered_in_book=3,
        )
        assert proposal.frequency == 15
        assert proposal.confidence == 0.92
        assert len(proposal.example_matches) == 2

    def test_ontology_change_defaults(self):
        change = OntologyChange(
            change_type="add_property",
            layer="core",
            target="Character",
            proposed_by="user",
            discovered_in_book=1,
            discovered_in_chapter=1,
            confidence=1.0,
        )
        assert change.status == "proposed"
        assert change.evidence == []
        assert change.details == {}

    def test_changelog_version(self):
        changelog = OntologyChangelog(series_name="test")
        assert changelog.current_version == "3.0.0"


class TestCrossBookReconciliation:
    @pytest.mark.asyncio
    async def test_reconcile_with_empty_series_registry(self):
        from app.schemas.extraction import ChapterExtractionResult
        from app.services.extraction.reconciler import reconcile_with_cross_book

        result = ChapterExtractionResult(book_id="test-book", chapter_number=1)
        reconciled = await reconcile_with_cross_book(result, series_registry=None)
        assert reconciled is not None
        assert isinstance(reconciled.alias_map, dict)
        assert isinstance(reconciled.merges, list)
        assert isinstance(reconciled.conflicts, list)

    @pytest.mark.asyncio
    async def test_reconcile_with_series_registry_matching(self):
        from app.schemas.extraction import (
            ChapterExtractionResult,
            CharacterExtractionResult,
            ExtractedCharacter,
        )

        # Build a registry with a known entity
        from app.services.extraction.entity_registry import EntityRegistry
        from app.services.extraction.reconciler import reconcile_with_cross_book

        registry = EntityRegistry()
        registry.add(
            name="Jake Thayne",
            entity_type="Character",
            aliases=["Jake"],
        )
        registry_dict = registry.to_dict()

        # Build an extraction result with a character that matches an alias
        result = ChapterExtractionResult(
            book_id="test-book",
            chapter_number=5,
            characters=CharacterExtractionResult(
                characters=[
                    ExtractedCharacter(name="Jake", canonical_name="Jake"),
                ]
            ),
        )

        reconciled = await reconcile_with_cross_book(result, series_registry=registry_dict)
        assert reconciled is not None
        # "Jake" should be matched to "jake thayne" from the registry
        assert "Jake" in reconciled.alias_map

    @pytest.mark.asyncio
    async def test_reconcile_no_match_in_registry(self):
        from app.schemas.extraction import (
            ChapterExtractionResult,
            CharacterExtractionResult,
            ExtractedCharacter,
        )
        from app.services.extraction.entity_registry import EntityRegistry
        from app.services.extraction.reconciler import reconcile_with_cross_book

        registry = EntityRegistry()
        registry.add(name="Vilastromoz", entity_type="Character")
        registry_dict = registry.to_dict()

        result = ChapterExtractionResult(
            book_id="test-book",
            chapter_number=5,
            characters=CharacterExtractionResult(
                characters=[
                    ExtractedCharacter(name="NewCharacter", canonical_name="NewCharacter"),
                ]
            ),
        )

        reconciled = await reconcile_with_cross_book(result, series_registry=registry_dict)
        # "NewCharacter" should NOT appear in alias_map
        assert "NewCharacter" not in reconciled.alias_map


class TestEntityRegistry:
    def test_registry_roundtrip(self):
        from app.services.extraction.entity_registry import EntityRegistry

        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake", "JT"])
        reg.add("Perception", "Skill")
        reg.add_chapter_summary(1, "Jake starts his journey")

        data = reg.to_dict()
        restored = EntityRegistry.from_dict(data)

        assert restored.entity_count == 2
        assert restored.lookup("Jake") is not None
        assert restored.lookup("Perception") is not None
        assert len(restored.chapter_summaries) == 1

    def test_registry_merge(self):
        from app.services.extraction.entity_registry import EntityRegistry

        reg1 = EntityRegistry()
        reg1.add("Jake Thayne", "Character")

        reg2 = EntityRegistry()
        reg2.add("Vilastromoz", "Character")

        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 2
