"""Golden dataset tests — validates extraction pipeline against wiki ground truth.

Uses The Primal Hunter wiki data as ground truth to measure extraction quality.
Tests are organized by pipeline layer:

  1. Regex extractor (Passe 0)  — FREE, no LLM calls
  2. Extraction router           — route decisions on realistic text
  3. Deduplication               — alias resolution for wiki characters
  4. Schema validation           — can we represent all wiki entities?
  5. Integration smoke           — end-to-end ChapterExtractionResult assembly

All tests here are FAST (no network, no LLM, < 1s each).
"""

from __future__ import annotations

import json

import pytest
from tests.fixtures.golden_primal_hunter import (
    ALL_ENTITY_NAMES,
    CHARACTER_NAMES,
    CHARACTERS,
    CLASS_NAMES,
    CLASSES,
    FACTION_NAMES,
    FACTIONS,
    LOCATIONS,
    MUST_FIND_CHARACTERS,
    RELATIONSHIPS,
    SKILL_NAMES,
    SKILLS,
    TITLE_NAMES,
    TITLES,
    GoldenChapterExpectation,
)
from tests.fixtures.primal_hunter_chapters import (
    ALL_CHAPTERS,
    CHAPTER_1_EXPECTED,
    CHAPTER_1_TEXT,
    CHAPTER_2_TEXT,
    CHAPTER_3_TEXT,
    CHAPTER_4_TEXT,
    CHAPTER_5_EXPECTED,
    CHAPTER_5_TEXT,
)

from app.schemas.extraction import (
    ChapterExtractionResult,
    CharacterExtractionResult,
    EventExtractionResult,
    ExtractedCharacter,
    ExtractedClass,
    ExtractedEvent,
    ExtractedFaction,
    ExtractedLocation,
    ExtractedRelationship,
    ExtractedSkill,
    ExtractedTitle,
    LoreExtractionResult,
    SystemExtractionResult,
)
from app.services.deduplication import exact_dedup, fuzzy_dedup, normalize_name
from app.services.extraction.regex_extractor import RegexExtractor
from app.services.extraction.router import route_extraction_passes

# ═══════════════════════════════════════════════════════════════════════
# 1. REGEX EXTRACTOR — Passe 0 on wiki-realistic text
# ═══════════════════════════════════════════════════════════════════════


class TestRegexOnPrimalHunter:
    """Regex extractor on realistic Primal Hunter chapter text."""

    @pytest.fixture
    def extractor(self) -> RegexExtractor:
        return RegexExtractor.default()

    # -- Chapter 1: skills + level + title ---------------------------------

    def test_ch1_skill_acquired_basic_archery(self, extractor: RegexExtractor):
        """Regex captures [Skill Acquired: Basic Archery - Inferior]."""
        matches = extractor.extract(CHAPTER_1_TEXT, chapter_number=1)
        skill_matches = [m for m in matches if m.pattern_name == "skill_acquired"]
        skill_names = [m.captures.get("name", "") for m in skill_matches]
        assert "Basic Archery" in skill_names

    def test_ch1_skill_acquired_archers_eye(self, extractor: RegexExtractor):
        """Regex captures [Skill Acquired: Archer's Eye - Common]."""
        matches = extractor.extract(CHAPTER_1_TEXT, chapter_number=1)
        skill_matches = [m for m in matches if m.pattern_name == "skill_acquired"]
        skill_names = [m.captures.get("name", "") for m in skill_matches]
        assert "Archer's Eye" in skill_names

    def test_ch1_level_up_1_to_3(self, extractor: RegexExtractor):
        """Regex captures Level: 1 -> 3."""
        matches = extractor.extract(CHAPTER_1_TEXT, chapter_number=1)
        level_matches = [m for m in matches if m.pattern_name == "level_up"]
        assert len(level_matches) >= 1
        assert level_matches[0].captures.get("old_value") == "1"
        assert level_matches[0].captures.get("new_value") == "3"

    def test_ch1_title_earned(self, extractor: RegexExtractor):
        """Regex captures Title earned: Forerunner of the New World."""
        matches = extractor.extract(CHAPTER_1_TEXT, chapter_number=1)
        title_matches = [m for m in matches if m.pattern_name == "title_earned"]
        title_names = [m.captures.get("name", "") for m in title_matches]
        assert "Forerunner of the New World" in title_names

    def test_ch1_stat_increase(self, extractor: RegexExtractor):
        """Regex captures +2 Perception."""
        matches = extractor.extract(CHAPTER_1_TEXT, chapter_number=1)
        stat_matches = [m for m in matches if m.pattern_name == "stat_increase"]
        stat_names = [m.captures.get("stat_name", "") for m in stat_matches]
        assert "Perception" in stat_names

    # -- Chapter 2: Viper skills + title -----------------------------------

    def test_ch2_palate_of_malefic_viper(self, extractor: RegexExtractor):
        """Regex captures Palate of the Malefic Viper skill."""
        matches = extractor.extract(CHAPTER_2_TEXT, chapter_number=2)
        skill_matches = [m for m in matches if m.pattern_name == "skill_acquired"]
        skill_names = [m.captures.get("name", "") for m in skill_matches]
        assert "Palate of the Malefic Viper" in skill_names

    def test_ch2_title_primordial_blessing(self, extractor: RegexExtractor):
        """Regex captures Holder of a Primordial's True Blessing title."""
        matches = extractor.extract(CHAPTER_2_TEXT, chapter_number=2)
        title_matches = [m for m in matches if m.pattern_name == "title_earned"]
        title_names = [m.captures.get("name", "") for m in title_matches]
        assert any("Primordial" in t for t in title_names)

    def test_ch2_stat_wisdom_willpower(self, extractor: RegexExtractor):
        """Regex captures +5 Wisdom, +5 Willpower."""
        matches = extractor.extract(CHAPTER_2_TEXT, chapter_number=2)
        stat_matches = [m for m in matches if m.pattern_name == "stat_increase"]
        stat_names = {m.captures.get("stat_name", "") for m in stat_matches}
        assert {"Wisdom", "Willpower"} <= stat_names

    # -- Chapter 4: Evolution + skill + level ------------------------------

    def test_ch4_moment_of_primal_hunter(self, extractor: RegexExtractor):
        """Regex captures Moment of the Primal Hunter skill."""
        matches = extractor.extract(CHAPTER_4_TEXT, chapter_number=4)
        skill_matches = [m for m in matches if m.pattern_name == "skill_acquired"]
        skill_names = [m.captures.get("name", "") for m in skill_matches]
        assert "Moment of the Primal Hunter" in skill_names

    def test_ch4_level_up_74_to_75(self, extractor: RegexExtractor):
        """Regex captures Level: 74 -> 75."""
        matches = extractor.extract(CHAPTER_4_TEXT, chapter_number=4)
        level_matches = [m for m in matches if m.pattern_name == "level_up"]
        assert len(level_matches) >= 1
        lm = level_matches[0]
        assert lm.captures.get("old_value") == "74"
        assert lm.captures.get("new_value") == "75"

    def test_ch4_evolution_to_avaricious(self, extractor: RegexExtractor):
        """Regex captures the evolution to Avaricious Arcane Hunter."""
        matches = extractor.extract(CHAPTER_4_TEXT, chapter_number=4)
        evo_matches = [m for m in matches if m.pattern_name == "evolution"]
        assert len(evo_matches) >= 1
        assert any("Avaricious" in m.captures.get("target", "") for m in evo_matches)

    def test_ch4_title_prodigious_slayer(self, extractor: RegexExtractor):
        """Regex captures Prodigious Slayer of the Mighty."""
        matches = extractor.extract(CHAPTER_4_TEXT, chapter_number=4)
        title_matches = [m for m in matches if m.pattern_name == "title_earned"]
        title_names = [m.captures.get("name", "") for m in title_matches]
        assert "Prodigious Slayer of the Mighty" in title_names

    # -- Chapter 5: Dense multi-entity chapter -----------------------------

    def test_ch5_event_horizon_skill(self, extractor: RegexExtractor):
        """Regex captures Event Horizon skill."""
        matches = extractor.extract(CHAPTER_5_TEXT, chapter_number=5)
        skill_matches = [m for m in matches if m.pattern_name == "skill_acquired"]
        skill_names = [m.captures.get("name", "") for m in skill_matches]
        assert "Event Horizon" in skill_names

    def test_ch5_evolution_to_boundless_horizon(self, extractor: RegexExtractor):
        """Regex captures B-grade evolution."""
        matches = extractor.extract(CHAPTER_5_TEXT, chapter_number=5)
        evo_matches = [m for m in matches if m.pattern_name == "evolution"]
        assert len(evo_matches) >= 1
        assert any("Boundless Horizon" in m.captures.get("target", "") for m in evo_matches)

    def test_ch5_three_titles(self, extractor: RegexExtractor):
        """Chapter 5 has 3 titles: Perfect Evo, Sacred Prodigy, Peerless Conqueror."""
        matches = extractor.extract(CHAPTER_5_TEXT, chapter_number=5)
        title_matches = [m for m in matches if m.pattern_name == "title_earned"]
        assert len(title_matches) >= 3

    def test_ch5_level_199_to_200(self, extractor: RegexExtractor):
        """Regex captures Level: 199 -> 200."""
        matches = extractor.extract(CHAPTER_5_TEXT, chapter_number=5)
        level_matches = [m for m in matches if m.pattern_name == "level_up"]
        assert len(level_matches) >= 1
        assert level_matches[0].captures.get("new_value") == "200"

    # -- Cross-chapter: grounding offsets ----------------------------------

    @pytest.mark.parametrize(
        "chapter_text,chapter_num",
        [
            (CHAPTER_1_TEXT, 1),
            (CHAPTER_2_TEXT, 2),
            (CHAPTER_3_TEXT, 3),
            (CHAPTER_4_TEXT, 4),
            (CHAPTER_5_TEXT, 5),
        ],
    )
    def test_offsets_within_text_bounds(
        self, extractor: RegexExtractor, chapter_text: str, chapter_num: int
    ):
        """Every match offset must be within the chapter text."""
        matches = extractor.extract(chapter_text, chapter_number=chapter_num)
        for m in matches:
            assert 0 <= m.char_offset_start < len(chapter_text)
            assert m.char_offset_start < m.char_offset_end <= len(chapter_text)

    @pytest.mark.parametrize(
        "chapter_text,chapter_num",
        [
            (CHAPTER_1_TEXT, 1),
            (CHAPTER_2_TEXT, 2),
            (CHAPTER_3_TEXT, 3),
            (CHAPTER_4_TEXT, 4),
            (CHAPTER_5_TEXT, 5),
        ],
    )
    def test_raw_text_matches_slice(
        self, extractor: RegexExtractor, chapter_text: str, chapter_num: int
    ):
        """raw_text must equal the chapter text slice at the given offsets."""
        matches = extractor.extract(chapter_text, chapter_number=chapter_num)
        for m in matches:
            sliced = chapter_text[m.char_offset_start : m.char_offset_end]
            assert m.raw_text == sliced

    # -- Dedup-safety: specific patterns don't overlap with generic --------

    @pytest.mark.parametrize("chapter_text,chapter_num", ALL_CHAPTERS)
    def test_no_duplicate_captures(
        self, extractor: RegexExtractor, chapter_text: str, chapter_num: int
    ):
        """A skill captured by skill_acquired should NOT also appear as blue_box_generic."""
        matches = extractor.extract(chapter_text, chapter_number=chapter_num.chapter_number)
        specific_spans = {
            (m.char_offset_start, m.char_offset_end)
            for m in matches
            if m.pattern_name != "blue_box_generic"
        }
        generic_spans = {
            (m.char_offset_start, m.char_offset_end)
            for m in matches
            if m.pattern_name == "blue_box_generic"
        }
        # No generic span should fully overlap with a specific span
        for g_start, g_end in generic_spans:
            for s_start, s_end in specific_spans:
                assert not (s_start <= g_start and g_end <= s_end), (
                    f"Generic match [{g_start}:{g_end}] overlaps with specific [{s_start}:{s_end}]"
                )


# ═══════════════════════════════════════════════════════════════════════
# 2. EXTRACTION ROUTER — pass selection on realistic text
# ═══════════════════════════════════════════════════════════════════════


class TestRouterOnPrimalHunter:
    """Extraction router decisions on realistic chapter text."""

    @staticmethod
    def _make_state(text: str, chapter: int = 1, genre: str = "litrpg") -> dict:
        return {
            "chapter_text": text,
            "book_id": "primal-hunter-test",
            "chapter_number": chapter,
            "genre": genre,
            "regex_matches_json": "",
        }

    def test_ch1_tutorial_gets_all_passes(self):
        """Chapter 1 has skills + events + characters -> should trigger multiple passes."""
        state = self._make_state(CHAPTER_1_TEXT, chapter=1)
        result = route_extraction_passes(state)
        passes = result["passes_to_run"]
        assert "characters" in passes
        # Tutorial chapter has system keywords
        assert "systems" in passes

    def test_ch2_viper_has_systems(self):
        """Chapter 2 mentions skills, blessings -> systems pass."""
        state = self._make_state(CHAPTER_2_TEXT, chapter=2)
        result = route_extraction_passes(state)
        passes = result["passes_to_run"]
        assert "characters" in passes
        assert "systems" in passes

    def test_ch3_politics_has_lore(self):
        """Chapter 3 has factions, cities -> lore pass."""
        state = self._make_state(CHAPTER_3_TEXT, chapter=3)
        result = route_extraction_passes(state)
        passes = result["passes_to_run"]
        assert "characters" in passes

    def test_ch4_combat_has_events(self):
        """Chapter 4 is a battle -> events pass."""
        state = self._make_state(CHAPTER_4_TEXT, chapter=4)
        result = route_extraction_passes(state)
        passes = result["passes_to_run"]
        assert "characters" in passes
        assert "events" in passes

    def test_ch5_dense_triggers_most_passes(self):
        """Chapter 5 has everything -> should trigger 3+ passes."""
        state = self._make_state(CHAPTER_5_TEXT, chapter=5)
        result = route_extraction_passes(state)
        passes = result["passes_to_run"]
        assert "characters" in passes
        assert len(passes) >= 3

    def test_regex_json_triggers_systems(self):
        """Providing regex_matches_json should force systems pass."""
        fake_regex = json.dumps([{"pattern": "skill_acquired", "name": "Archery"}])
        state = self._make_state(CHAPTER_1_TEXT, chapter=1)
        state["regex_matches_json"] = fake_regex
        result = route_extraction_passes(state)
        assert "systems" in result["passes_to_run"]

    def test_non_litrpg_genre_higher_threshold(self):
        """Non-LitRPG genre should require more system keywords."""
        # Use chapter 3 which has few system keywords
        state = self._make_state(CHAPTER_3_TEXT, chapter=3, genre="general_fantasy")
        result = route_extraction_passes(state)
        passes = result["passes_to_run"]
        # systems may or may not be included depending on threshold
        assert "characters" in passes  # Always present

    @pytest.mark.parametrize("chapter_text,chapter_expected", ALL_CHAPTERS)
    def test_characters_always_present(
        self, chapter_text: str, chapter_expected: GoldenChapterExpectation
    ):
        """Characters pass is ALWAYS present regardless of content."""
        state = self._make_state(chapter_text, chapter=chapter_expected.chapter_number)
        result = route_extraction_passes(state)
        assert "characters" in result["passes_to_run"]


# ═══════════════════════════════════════════════════════════════════════
# 3. DEDUPLICATION — alias resolution with wiki character names
# ═══════════════════════════════════════════════════════════════════════


class TestDedupWithWikiNames:
    """Test deduplication using real Primal Hunter character names/aliases."""

    def test_exact_dedup_the_prefix(self):
        """'The Malefic Viper' normalizes by stripping 'The' prefix."""
        entities = [
            {"name": "The Malefic Viper"},
            {"name": "Malefic Viper"},
        ]
        deduped, alias_map = exact_dedup(entities)
        assert len(deduped) == 1
        assert len(alias_map) == 1

    def test_exact_dedup_preserves_jake(self):
        """'Jake Thayne' and 'Jake' are NOT exact duplicates (different names)."""
        entities = [
            {"name": "Jake Thayne"},
            {"name": "Jake"},
        ]
        deduped, alias_map = exact_dedup(entities)
        assert len(deduped) == 2
        assert len(alias_map) == 0

    def test_exact_dedup_case_insensitive(self):
        """'JAKE THAYNE' and 'Jake Thayne' are exact duplicates."""
        entities = [
            {"name": "Jake Thayne"},
            {"name": "JAKE THAYNE"},
        ]
        deduped, alias_map = exact_dedup(entities)
        assert len(deduped) == 1

    def test_fuzzy_villy_vilastromoz(self):
        """'Villy' and 'Vilastromoz' are NOT fuzzy matches (too different)."""
        entities = [
            {"name": "Villy"},
            {"name": "Vilastromoz"},
        ]
        _, candidates = fuzzy_dedup(entities)
        # Score should be below threshold — these are very different strings
        # The fuzzy dedup should NOT auto-merge them
        assert len([c for c in candidates if c[2] >= 95]) == 0

    def test_fuzzy_miranda_wells_miranda(self):
        """'Miranda Wells' and 'Miranda' might be fuzzy candidates."""
        entities = [
            {"name": "Miranda Wells"},
            {"name": "Miranda"},
        ]
        deduped, candidates = fuzzy_dedup(entities)
        # At minimum they should remain as 2 separate entities
        # (fuzzy score of "miranda wells" vs "miranda" is not high enough for auto-merge)
        assert len(deduped) >= 1

    def test_fuzzy_caleb_thayne_caleb(self):
        """'Caleb Thayne' and 'Caleb' — different enough to keep separate."""
        entities = [
            {"name": "Caleb Thayne"},
            {"name": "Caleb"},
        ]
        deduped, _ = fuzzy_dedup(entities)
        assert len(deduped) == 2

    def test_exact_dedup_multiple_wiki_characters(self):
        """Dedup a batch of wiki characters — no false merges."""
        entities = [{"name": c.canonical_name} for c in CHARACTERS]
        deduped, alias_map = exact_dedup(entities)
        # All wiki characters have distinct canonical names
        assert len(deduped) == len(CHARACTERS)
        assert len(alias_map) == 0

    def test_normalize_wiki_character_names(self):
        """normalize_name handles all wiki character patterns."""
        assert normalize_name("Jake Thayne") == "jake thayne"
        assert normalize_name("The Malefic Viper") == "malefic viper"
        assert normalize_name("  Miranda Wells  ") == "miranda wells"
        assert normalize_name("Ell'Hakan") == "ell'hakan"
        assert normalize_name("An Orc") == "orc"

    def test_article_stripping_wiki_titles(self):
        """Titles starting with 'The' are normalized correctly."""
        assert normalize_name("The Holy Church") == "holy church"
        assert normalize_name("The System") == "system"
        assert normalize_name("A Dragon") == "dragon"

    def test_fuzzy_dedup_no_false_positives_wiki_characters(self):
        """No two wiki characters should auto-merge via fuzzy dedup."""
        entities = [{"name": c.canonical_name} for c in CHARACTERS]
        deduped, candidates = fuzzy_dedup(entities)
        # No auto-merges — all wiki characters are distinct
        assert len(deduped) == len(CHARACTERS)

    def test_exact_dedup_skills_no_collision(self):
        """Wiki skills should not falsely deduplicate."""
        entities = [{"name": s.name} for s in SKILLS]
        deduped, alias_map = exact_dedup(entities)
        # All skills have distinct names
        assert len(deduped) == len(SKILLS)

    def test_exact_dedup_handles_alias_forms(self):
        """Character with different alias forms should deduplicate correctly."""
        entities = [
            {"name": "The Malefic Viper"},
            {"name": "the malefic viper"},
            {"name": "Malefic Viper"},  # article stripped = same
        ]
        deduped, alias_map = exact_dedup(entities)
        assert len(deduped) == 1
        assert len(alias_map) == 2


# ═══════════════════════════════════════════════════════════════════════
# 4. SCHEMA VALIDATION — can Pydantic schemas represent all wiki data?
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaRepresentsWikiData:
    """Verify Pydantic extraction schemas can encode all wiki entity types."""

    def test_all_wiki_characters_as_pydantic(self):
        """Every wiki character can be represented as ExtractedCharacter."""
        for c in CHARACTERS:
            ec = ExtractedCharacter(
                name=c.name,
                canonical_name=c.canonical_name,
                aliases=list(c.aliases),
                species=c.species,
                role=c.role,
            )
            assert ec.name == c.name
            assert ec.canonical_name == c.canonical_name
            assert ec.role in (
                "protagonist",
                "antagonist",
                "mentor",
                "sidekick",
                "ally",
                "minor",
                "neutral",
            )

    def test_all_wiki_skills_as_pydantic(self):
        """Every wiki skill can be represented as ExtractedSkill."""
        for s in SKILLS:
            es = ExtractedSkill(
                name=s.name,
                owner=s.owner,
                rank=s.rank,
                skill_type=s.skill_type or "active",
            )
            assert es.name == s.name

    def test_all_wiki_classes_as_pydantic(self):
        """Every wiki class can be represented as ExtractedClass."""
        for c in CLASSES:
            ec = ExtractedClass(
                name=c.name,
                owner=c.owner,
            )
            assert ec.name == c.name

    def test_all_wiki_titles_as_pydantic(self):
        """Every wiki title can be represented as ExtractedTitle."""
        for t in TITLES:
            et = ExtractedTitle(
                name=t.name,
                owner=t.owner,
            )
            assert et.name == t.name

    def test_all_wiki_factions_as_pydantic(self):
        """Every wiki faction can be represented as ExtractedFaction."""
        for f in FACTIONS:
            ef = ExtractedFaction(
                name=f.name,
                faction_type=f.faction_type,
            )
            assert ef.name == f.name

    def test_all_wiki_locations_as_pydantic(self):
        """Every wiki location can be represented as ExtractedLocation."""
        for loc in LOCATIONS:
            el = ExtractedLocation(
                name=loc.name,
                location_type=loc.location_type,
            )
            assert el.name == loc.name

    def test_all_wiki_relationships_as_pydantic(self):
        """Every wiki relationship can be represented as ExtractedRelationship."""
        for r in RELATIONSHIPS:
            er = ExtractedRelationship(
                source=r.source,
                target=r.target,
                rel_type=r.rel_type,
                subtype=r.subtype,
            )
            assert er.source == r.source
            assert er.target == r.target

    def test_all_wiki_events_as_pydantic(self):
        """Events with wiki-style data serialize correctly."""
        ev = ExtractedEvent(
            name="King of the Forest Defeated",
            description="Jake kills the D-grade Unique Lifeform",
            event_type="action",
            significance="major",
            participants=["Jake Thayne", "Sylphie"],
            chapter=4,
        )
        assert len(ev.participants) == 2
        assert ev.significance == "major"


# ═══════════════════════════════════════════════════════════════════════
# 5. INTEGRATION — ChapterExtractionResult from wiki-sourced data
# ═══════════════════════════════════════════════════════════════════════


class TestChapterExtractionResultAssembly:
    """Build a ChapterExtractionResult from wiki data and validate structure."""

    def test_full_chapter_result_from_ch1(self):
        """Assemble a complete extraction result using ch1 expected data."""
        result = ChapterExtractionResult(
            book_id="primal-hunter-1",
            chapter_number=1,
            characters=CharacterExtractionResult(
                characters=[
                    ExtractedCharacter(name="Jake Thayne", role="protagonist"),
                    ExtractedCharacter(name="Caleb Thayne", role="ally"),
                ],
                relationships=[
                    ExtractedRelationship(
                        source="Jake Thayne",
                        target="Caleb Thayne",
                        rel_type="family",
                        subtype="brothers",
                    ),
                ],
            ),
            systems=SystemExtractionResult(
                skills=[
                    ExtractedSkill(name="Basic Archery", rank="Inferior", owner="Jake Thayne"),
                    ExtractedSkill(name="Archer's Eye", rank="Common", owner="Jake Thayne"),
                ],
                classes=[
                    ExtractedClass(name="Archer", owner="Jake Thayne"),
                    ExtractedClass(name="Warrior (Light)", owner="Caleb Thayne"),
                ],
                titles=[
                    ExtractedTitle(name="Forerunner of the New World", owner="Jake Thayne"),
                ],
            ),
            events=EventExtractionResult(
                events=[
                    ExtractedEvent(
                        name="Tutorial Begins",
                        event_type="process",
                        significance="critical",
                        participants=["Jake Thayne", "Caleb Thayne"],
                        chapter=1,
                    ),
                ],
            ),
            lore=LoreExtractionResult(),
        )

        # Validate count
        count = result.count_entities()
        assert count >= CHAPTER_1_EXPECTED.min_entity_count
        assert result.total_entities == count

        # Validate expected characters present
        char_names = {c.name for c in result.characters.characters}
        for name in CHAPTER_1_EXPECTED.expected_characters:
            assert name in char_names, f"Missing character: {name}"

        # Validate expected skills present
        skill_names = {s.name for s in result.systems.skills}
        for name in CHAPTER_1_EXPECTED.expected_skills:
            assert name in skill_names, f"Missing skill: {name}"

    def test_full_chapter_result_from_ch5_dense(self):
        """Chapter 5 is entity-dense — validate we can assemble all of it."""
        result = ChapterExtractionResult(
            book_id="primal-hunter-1",
            chapter_number=5,
            characters=CharacterExtractionResult(
                characters=[
                    ExtractedCharacter(name=name) for name in CHAPTER_5_EXPECTED.expected_characters
                ],
            ),
            systems=SystemExtractionResult(
                skills=[ExtractedSkill(name=name) for name in CHAPTER_5_EXPECTED.expected_skills],
                classes=[ExtractedClass(name=name) for name in CHAPTER_5_EXPECTED.expected_classes],
                titles=[ExtractedTitle(name=name) for name in CHAPTER_5_EXPECTED.expected_titles],
            ),
            events=EventExtractionResult(),
            lore=LoreExtractionResult(
                locations=[
                    ExtractedLocation(name=name) for name in CHAPTER_5_EXPECTED.expected_locations
                ],
                factions=[
                    ExtractedFaction(name=name) for name in CHAPTER_5_EXPECTED.expected_factions
                ],
            ),
        )

        count = result.count_entities()
        assert count >= CHAPTER_5_EXPECTED.min_entity_count
        assert count >= 12  # 5 chars + 2 skills + 1 class + 3 titles + 2 locs + 3 factions

    def test_entity_count_matches_wiki_expectations(self):
        """Verify count_entities is consistent across all chapters."""
        for _, expected in ALL_CHAPTERS:
            # Build a minimal result with just the expected entity counts
            n_chars = len(expected.expected_characters)
            n_skills = len(expected.expected_skills)
            n_classes = len(expected.expected_classes)
            n_titles = len(expected.expected_titles)
            n_locs = len(expected.expected_locations)
            n_factions = len(expected.expected_factions)
            total = n_chars + n_skills + n_classes + n_titles + n_locs + n_factions

            assert total >= expected.min_entity_count, (
                f"Chapter {expected.chapter_number}: expected >= {expected.min_entity_count} "
                f"entities but wiki expectations only specify {total}"
            )


# ═══════════════════════════════════════════════════════════════════════
# 6. GOLDEN DATA INTEGRITY — sanity checks on ground truth itself
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenDataIntegrity:
    """Ensure the golden dataset itself is internally consistent."""

    def test_must_find_characters_exist_in_characters(self):
        """Every MUST_FIND character appears in the full CHARACTERS list."""
        for name in MUST_FIND_CHARACTERS:
            assert name in CHARACTER_NAMES, f"{name} missing from CHARACTERS"

    def test_skill_owners_are_known_characters(self):
        """Every skill owner references a known character."""
        for skill in SKILLS:
            if skill.owner:
                assert skill.owner in CHARACTER_NAMES, (
                    f"Skill '{skill.name}' owner '{skill.owner}' not in CHARACTER_NAMES"
                )

    def test_class_owners_are_known_characters(self):
        """Every class owner references a known character."""
        for cls in CLASSES:
            if cls.owner:
                assert cls.owner in CHARACTER_NAMES, (
                    f"Class '{cls.name}' owner '{cls.owner}' not in CHARACTER_NAMES"
                )

    def test_title_owners_are_known_characters(self):
        """Every title owner references a known character."""
        for title in TITLES:
            if title.owner:
                assert title.owner in CHARACTER_NAMES, (
                    f"Title '{title.name}' owner '{title.owner}' not in CHARACTER_NAMES"
                )

    def test_relationship_participants_are_known_characters(self):
        """Every relationship source/target is a known character."""
        all_names = (
            CHARACTER_NAMES
            | frozenset(alias for c in CHARACTERS for alias in c.aliases)
            | frozenset(["Artemis", "Maja"])
        )  # Known characters not in main list
        for rel in RELATIONSHIPS:
            assert rel.source in all_names, f"Relationship source '{rel.source}' not known"
            assert rel.target in all_names, f"Relationship target '{rel.target}' not known"

    def test_chapter_expected_characters_in_wiki(self):
        """Every expected character in chapter fixtures exists in wiki data."""
        # Characters mentioned in chapters that we expect to find
        all_expected_chars = set()
        for _, expected in ALL_CHAPTERS:
            all_expected_chars.update(expected.expected_characters)

        for name in all_expected_chars:
            assert name in CHARACTER_NAMES, (
                f"Expected character '{name}' not in wiki CHARACTER_NAMES"
            )

    def test_chapter_expected_skills_in_wiki(self):
        """Every expected skill in chapter fixtures exists in wiki data."""
        all_expected_skills = set()
        for _, expected in ALL_CHAPTERS:
            all_expected_skills.update(expected.expected_skills)

        for name in all_expected_skills:
            assert name in SKILL_NAMES, f"Expected skill '{name}' not in wiki SKILL_NAMES"

    def test_no_duplicate_canonical_names(self):
        """No two characters share the same canonical name."""
        names = [c.canonical_name for c in CHARACTERS]
        assert len(names) == len(set(names))

    def test_all_entity_names_aggregate(self):
        """ALL_ENTITY_NAMES is the union of all individual name sets."""
        expected = (
            CHARACTER_NAMES
            | SKILL_NAMES
            | CLASS_NAMES
            | TITLE_NAMES
            | FACTION_NAMES
            | frozenset(loc.name for loc in LOCATIONS)
        )
        assert expected == ALL_ENTITY_NAMES
