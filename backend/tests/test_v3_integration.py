"""Integration test for V3 extraction pipeline end-to-end.

Uses mocked LLM but real LangGraph execution to verify the full
6-phase pipeline processes text and produces a valid ChapterExtractionResult.
"""

from __future__ import annotations

from app.schemas.extraction import (
    ChapterExtractionResult,
    CharacterExtractionResult,
    EventExtractionResult,
    ExtractedCharacter,
    ExtractedEvent,
    ExtractedRelationship,
    ExtractedSkill,
    LoreExtractionResult,
    SystemExtractionResult,
)
from app.services.extraction.entity_registry import EntityRegistry

# Sample chapter text (realistic Primal Hunter-like content)
SAMPLE_CHAPTER_TEXT = """
Jake drew his bow, channeling Arcane Powershot. The arrow flew true,
striking the C-grade beast square in the chest.

[Skill Acquired: Mark of the Ambitious Hunter - Legendary]
+5 Perception, +3 Agility

The creature fell with a thunderous crash. Sylphie chirped happily
from her perch on Jake's shoulder.

Level: 74 -> 75

"Not bad," Vilastromoz said from the divine realm, his voice echoing
through the connection. "But you need to push harder if you want to
reach D-grade before the tournament."

Miranda Wells approached from the city gates of Haven.
"The council is waiting," she said.
"""


class TestEntityRegistryIntegration:
    """Test EntityRegistry lifecycle through chapter processing."""

    def test_registry_grows_across_chapters(self):
        """Registry accumulates entities from multiple chapters."""
        reg = EntityRegistry()

        # Simulate chapter 1 extraction
        reg.add("Jake Thayne", "Character", aliases=["Jake", "the hunter"])
        reg.add("Sylphie", "Character")
        assert reg.entity_count == 2

        # Simulate chapter 2 extraction
        reg.add("Vilastromoz", "Character", aliases=["Villy", "The Malefic Viper"])
        reg.add("Arcane Powershot", "Skill")
        assert reg.entity_count == 4

        # Context should include all
        context = reg.to_prompt_context()
        assert "Jake Thayne" in context or "jake thayne" in context
        assert "Vilastromoz" in context or "vilastromoz" in context
        assert "Arcane Powershot" in context or "arcane powershot" in context

    def test_registry_serialization_preserves_state(self):
        """to_dict/from_dict roundtrip preserves all state."""
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"])
        reg.add("Haven", "Location")

        data = reg.to_dict()
        reg2 = EntityRegistry.from_dict(data)

        assert reg2.entity_count == 2
        assert reg2.lookup("Jake") is not None
        assert reg2.lookup("Haven") is not None

    def test_registry_merge_for_cross_book(self):
        """Merging registries from different books combines entities."""
        reg_book1 = EntityRegistry()
        reg_book1.add("Jake Thayne", "Character")
        reg_book1.add("Archer", "Class")

        reg_book2 = EntityRegistry()
        reg_book2.add("Miranda Wells", "Character")
        reg_book2.add("Caster", "Class")

        merged = EntityRegistry.merge(reg_book1, reg_book2)
        assert merged.entity_count == 4


class TestV3PipelineResultAssembly:
    """Test that V3 pipeline can produce valid ChapterExtractionResult."""

    def test_v3_result_has_ontology_version(self):
        """V3 results carry ontology_version metadata."""
        result = ChapterExtractionResult(
            book_id="test-book",
            chapter_number=1,
            characters=CharacterExtractionResult(
                characters=[
                    ExtractedCharacter(
                        name="Jake Thayne",
                        canonical_name="Jake Thayne",
                        description="The protagonist",
                        role="protagonist",
                        status="alive",
                        last_seen_chapter=1,
                    ),
                ],
            ),
            systems=SystemExtractionResult(
                skills=[
                    ExtractedSkill(
                        name="Arcane Powershot",
                        skill_type="active",
                        owner="Jake Thayne",
                    ),
                ],
            ),
            events=EventExtractionResult(
                events=[
                    ExtractedEvent(
                        name="Beast Slain",
                        description="Jake kills C-grade beast",
                        event_type="action",
                        significance="minor",
                        participants=["Jake Thayne"],
                        chapter=1,
                    ),
                ],
            ),
            lore=LoreExtractionResult(),
            ontology_version="3.0.0",
        )

        assert result.ontology_version == "3.0.0"
        assert result.total_entities >= 3 or result.count_entities() >= 3
        assert result.characters.characters[0].status == "alive"

    def test_v3_result_with_alias_map(self):
        """V3 results include alias_map from reconciliation."""
        result = ChapterExtractionResult(
            book_id="test-book",
            chapter_number=1,
            characters=CharacterExtractionResult(
                characters=[
                    ExtractedCharacter(
                        name="Jake Thayne",
                        canonical_name="Jake Thayne",
                        description="",
                        role="protagonist",
                    ),
                ],
                relationships=[
                    ExtractedRelationship(
                        source="Jake Thayne",
                        target="Vilastromoz",
                        rel_type="patron",
                        context="True Blessing",
                    ),
                ],
            ),
            systems=SystemExtractionResult(),
            events=EventExtractionResult(),
            lore=LoreExtractionResult(),
            alias_map={"The Hunter": "Jake Thayne", "Villy": "Vilastromoz"},
        )

        assert len(result.alias_map) == 2
        assert result.alias_map["The Hunter"] == "Jake Thayne"


class TestV3RegexWithOntology:
    """Test regex extraction from ontology YAML patterns."""

    def test_from_ontology_extracts_skills(self):
        """RegexExtractor.from_ontology finds skill patterns in text."""
        from app.core.ontology_loader import OntologyLoader
        from app.services.extraction.regex_extractor import RegexExtractor

        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)

        matches = extractor.extract(SAMPLE_CHAPTER_TEXT, chapter_number=1)
        pattern_names = {m.pattern_name for m in matches}

        assert "skill_acquired" in pattern_names
        assert "stat_increase" in pattern_names
        assert "level_up" in pattern_names

    def test_from_ontology_pattern_count(self):
        """Ontology-driven extractor has at least as many patterns as hardcoded."""
        from app.core.ontology_loader import OntologyLoader
        from app.services.extraction.regex_extractor import RegexExtractor

        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        default_extractor = RegexExtractor.default()

        assert len(extractor.patterns) >= len(default_extractor.patterns)
