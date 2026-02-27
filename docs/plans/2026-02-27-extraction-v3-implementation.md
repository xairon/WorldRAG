# V3 Extraction Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current 4-pass parallel extraction with a 6-phase layered pipeline (narrative → genre → series), with ontology-driven schemas, multilingual prompts, expanded regex, incremental evolution, and cross-book entity matching.

**Architecture:** Layered extraction where each phase receives the output of prior phases as context. An EntityRegistry accumulates knowledge chapter-by-chapter. The ontology YAML is the contract — prompts receive their target schema from it dynamically. All extractions are versioned for surgical reprocessing.

**Tech Stack:** Python 3.12, LangGraph StateGraph, LangExtract, Instructor, Pydantic v2, Neo4j 5.x, arq, Gemini 2.5 Flash

**Design Doc:** `docs/plans/2026-02-27-extraction-v3-design.md`

---

## Phase A: Foundation (Ontology + Schemas + Config + Regex)

### Task 1: Add ontology versioning to YAML files

**Files:**
- Modify: `ontology/core.yaml` (add `version` + `layer` fields at top)
- Modify: `ontology/litrpg.yaml` (add `version` + new entity types: StatBlock, QuestObjective, Achievement, Realm)
- Modify: `ontology/primal_hunter.yaml` (add `version`)

**Step 1: Update core.yaml**

Add at the top of `ontology/core.yaml`:

```yaml
version: "3.0.0"
layer: core
```

**Step 2: Update litrpg.yaml with version + new entity types**

Add at the top:
```yaml
version: "3.0.0"
layer: genre
```

Add new node types after `Creature`:
```yaml
  StatBlock:
    properties:
      character_name: { type: string, required: true }
      stats: { type: json }  # {"Strength": 42, "Agility": 38, ...}
      total: { type: integer }
      source: { type: enum, values: [blue_box, narrative, inferred] }
      chapter: { type: integer, required: true }
    constraints:
      - unique: [character_name, chapter]

  QuestObjective:
    properties:
      name: { type: string, required: true }
      description: { type: string }
      status: { type: enum, values: [active, completed, failed, abandoned] }
      chapter_received: { type: integer }
      chapter_completed: { type: integer }
    constraints:
      - unique: [name]

  Achievement:
    properties:
      name: { type: string, required: true, unique: true }
      description: { type: string }
      effects: { type: string_array }
      earned_by: { type: string }

  Realm:
    properties:
      name: { type: string, required: true, unique: true }
      grade: { type: string }
      description: { type: string }
      order: { type: integer }
```

Add new regex patterns (expand from 7 to 20):
```yaml
  # Add after existing regex_patterns:
  skill_evolved:
    pattern: '\[(?:Skill|Ability)\s+(?:Evolved|Upgraded|Enhanced):\s*(.+?)\s*(?:→|->|=>)\s*(.+?)(?:\s*-\s*(.+?))?\]'
    entity_type: SkillEvolution
    captures: { old_name: 1, new_name: 2, rank: 3 }

  skill_rank_up:
    pattern: '\[(.+?)\s+(?:has\s+)?reached\s+(?:rank|level)\s+(.+?)\]'
    entity_type: SkillRankUp
    captures: { name: 1, new_rank: 2 }

  class_evolved:
    pattern: '(?:Class|Classe)\s+(?:Evolved|Advanced|Upgraded):\s*(.+?)\s*(?:→|->|=>)\s*(.+)'
    entity_type: ClassEvolution
    captures: { old_class: 1, new_class: 2 }

  stat_block:
    pattern: '(?:Stats?:?\s*\n)((?:\s*\w+:\s*\d+[\s,]*)+)'
    entity_type: StatBlock
    captures: { block_text: 1 }

  xp_gain:
    pattern: '\+(\d[\d,]*)\s*(?:XP|Experience|Exp)'
    entity_type: XPGain
    captures: { amount: 1 }

  quest_received:
    pattern: '\[(?:Quest|Objective|Mission)\s+(?:Received|Accepted|Updated|Started):\s*(.+?)\]'
    entity_type: QuestReceived
    captures: { name: 1 }

  quest_completed:
    pattern: '\[(?:Quest|Objective|Mission)\s+(?:Completed|Fulfilled|Finished):\s*(.+?)\]'
    entity_type: QuestCompleted
    captures: { name: 1 }

  achievement_unlocked:
    pattern: '\[(?:Achievement|Accomplishment)\s+(?:Unlocked|Earned|Gained):\s*(.+?)\]'
    entity_type: Achievement
    captures: { name: 1 }

  realm_breakthrough:
    pattern: '\[(?:Breakthrough|Evolution|Advancement).*?(\w+-grade)\]'
    entity_type: RealmBreakthrough
    captures: { new_grade: 1 }

  item_acquired:
    pattern: '\[(?:Item\s+)?(?:Acquired|Looted|Received|Found):\s*(.+?)(?:\s*-\s*(.+?))?\]'
    entity_type: ItemAcquired
    captures: { name: 1, rarity: 2 }

  death_event:
    pattern: '\[(.+?)\s+(?:has\s+)?(?:been\s+)?(?:slain|killed|defeated|fell)\]'
    entity_type: DeathEvent
    captures: { entity_name: 1 }

  dungeon_entered:
    pattern: '\[(?:Entering|Entered)\s+(?:Dungeon|Instance|Zone):\s*(.+?)\]'
    entity_type: DungeonEvent
    captures: { name: 1 }

  damage_dealt:
    pattern: '(?:dealt|inflicted)\s+(\d[\d,]*)\s+(?:damage|dégâts|points?\s+de\s+d[eé]gâts)'
    entity_type: DamageEvent
    captures: { amount: 1 }
```

**Step 3: Update primal_hunter.yaml**

Add at the top:
```yaml
version: "3.0.0"
layer: series
```

**Step 4: Commit**

```bash
git add ontology/
git commit -m "feat(v3): add ontology versioning and 13 new regex patterns"
```

---

### Task 2: Update OntologyLoader to support versioning

**Files:**
- Modify: `backend/app/core/ontology_loader.py`
- Test: `backend/tests/test_ontology_loader.py` (create)

**Step 1: Write failing tests**

Create `backend/tests/test_ontology_loader.py`:

```python
"""Tests for the 3-layer ontology loader with version support."""
import pytest
from app.core.ontology_loader import OntologyLoader


class TestOntologyVersion:
    def test_core_has_version(self):
        loader = OntologyLoader.from_layers()
        assert loader.version is not None
        assert loader.version.startswith("3.")

    def test_combined_version_string(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        # Version should combine all active layers
        assert "3.0.0" in loader.version

    def test_layer_names(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        assert loader.active_layer_names == ["core", "genre", "series"]


class TestOntologySchemaExport:
    def test_get_types_for_layer(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        core_types = loader.get_node_types_for_layer("core")
        assert "Character" in core_types
        assert "Event" in core_types
        genre_types = loader.get_node_types_for_layer("genre")
        assert "Skill" in genre_types
        assert "Class" in genre_types

    def test_to_json_schema(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        schema = loader.to_json_schema(["Character", "Event"])
        assert "Character" in schema
        assert "properties" in schema["Character"]

    def test_new_entity_types_loaded(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        all_types = loader.get_all_node_types()
        assert "StatBlock" in all_types
        assert "QuestObjective" in all_types
        assert "Achievement" in all_types
        assert "Realm" in all_types


class TestRegexPatternsFromYaml:
    def test_loads_genre_regex(self):
        loader = OntologyLoader.from_layers(genre="litrpg")
        patterns = loader.get_regex_patterns()
        names = {p["name"] for p in patterns}
        assert "skill_acquired" in names
        assert "skill_evolved" in names
        assert "xp_gain" in names

    def test_loads_series_regex(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        patterns = loader.get_regex_patterns()
        names = {p["name"] for p in patterns}
        assert "bloodline_notification" in names
        assert "profession_obtained" in names

    def test_regex_pattern_count(self):
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        patterns = loader.get_regex_patterns()
        assert len(patterns) >= 25  # 20 genre + 5 series
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_ontology_loader.py -v`
Expected: FAIL (methods don't exist yet)

**Step 3: Implement versioning and schema export in OntologyLoader**

Read current `ontology_loader.py` and add:
- `version` property that combines layer versions
- `active_layer_names` property
- `get_node_types_for_layer(layer_name)` method
- `to_json_schema(type_names)` method
- `get_regex_patterns()` method that collects from all active layers
- `get_all_node_types()` method

**Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_ontology_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/ontology_loader.py backend/tests/test_ontology_loader.py
git commit -m "feat(v3): ontology loader with versioning, schema export, and regex collection"
```

---

### Task 3: New Pydantic base schemas

**Files:**
- Modify: `backend/app/schemas/extraction.py`
- Test: `backend/tests/test_v3_schemas.py` (create)

**Step 1: Write failing tests**

Create `backend/tests/test_v3_schemas.py`:

```python
"""Tests for V3 extraction schemas with base entity and new fields."""
import pytest
from pydantic import ValidationError


class TestBaseExtractedEntity:
    def test_required_fields(self):
        from app.schemas.extraction import BaseExtractedEntity
        entity = BaseExtractedEntity(
            name="Jake Thayne",
            canonical_name="jake thayne",
            entity_type="Character",
            confidence=0.95,
            extraction_text="Jake drew his bow",
            char_offset_start=0,
            char_offset_end=17,
            chapter_number=1,
            extraction_layer="narrative",
            extraction_phase=1,
            ontology_version="3.0.0",
        )
        assert entity.name == "Jake Thayne"
        assert entity.confidence == 0.95

    def test_confidence_bounds(self):
        from app.schemas.extraction import BaseExtractedEntity
        with pytest.raises(ValidationError):
            BaseExtractedEntity(
                name="X", canonical_name="x", entity_type="Character",
                confidence=1.5,  # Too high
                extraction_text="X", char_offset_start=0, char_offset_end=1,
                chapter_number=1, extraction_layer="narrative",
                extraction_phase=1, ontology_version="3.0.0",
            )

    def test_extraction_layer_literal(self):
        from app.schemas.extraction import BaseExtractedEntity
        with pytest.raises(ValidationError):
            BaseExtractedEntity(
                name="X", canonical_name="x", entity_type="Character",
                confidence=0.9, extraction_text="X",
                char_offset_start=0, char_offset_end=1,
                chapter_number=1, extraction_layer="invalid",
                extraction_phase=1, ontology_version="3.0.0",
            )


class TestExtractedCharacterV3:
    def test_new_fields(self):
        from app.schemas.extraction import ExtractedCharacter
        char = ExtractedCharacter(
            name="Jake", canonical_name="jake thayne",
            aliases=["the hunter"], role="protagonist",
            description="An archer", context="",
        )
        # New V3 fields should have defaults
        assert char.status == "alive"
        assert char.last_seen_chapter is None
        assert char.evolution_of is None


class TestExtractedStatBlock:
    def test_create(self):
        from app.schemas.extraction import ExtractedStatBlock
        sb = ExtractedStatBlock(
            character_name="Jake Thayne",
            stats={"Strength": 42, "Agility": 38},
            total=80,
            source="blue_box",
            chapter_number=5,
        )
        assert sb.stats["Strength"] == 42
        assert sb.source == "blue_box"


class TestExtractionPipelineStateV3:
    def test_new_state_fields(self):
        from app.agents.state import ExtractionPipelineState
        # Verify new fields are in the TypedDict
        annotations = ExtractionPipelineState.__annotations__
        assert "entity_registry" in annotations
        assert "ontology_version" in annotations
        assert "extraction_run_id" in annotations
        assert "phase0_regex" in annotations
        assert "phase1_narrative" in annotations
        assert "phase2_genre" in annotations
        assert "phase3_series" in annotations
        assert "source_language" in annotations
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_v3_schemas.py -v`
Expected: FAIL (BaseExtractedEntity, ExtractedStatBlock don't exist)

**Step 3: Add BaseExtractedEntity and new schemas**

In `backend/app/schemas/extraction.py`, add:

```python
class BaseExtractedEntity(BaseModel):
    """V3 base for all extraction outputs."""
    name: str
    canonical_name: str
    entity_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_text: str
    char_offset_start: int
    char_offset_end: int
    chapter_number: int
    extraction_layer: Literal["narrative", "genre", "series"]
    extraction_phase: int
    ontology_version: str

class ExtractedStatBlock(BaseModel):
    """Snapshot of character stats at a chapter."""
    character_name: str
    stats: dict[str, int]
    total: int | None = None
    source: Literal["blue_box", "narrative", "inferred"]
    chapter_number: int
```

Add new fields to `ExtractedCharacter`:
```python
    status: Literal["alive", "dead", "unknown", "transformed"] = "alive"
    last_seen_chapter: int | None = None
    evolution_of: str | None = None
```

Update `ExtractionPipelineState` in `backend/app/agents/state.py` with new fields:
```python
    entity_registry: dict  # EntityRegistry serialized
    ontology_version: str
    extraction_run_id: str
    source_language: str
    phase0_regex: list[dict]
    phase1_narrative: list[dict]
    phase2_genre: list[dict]
    phase3_series: list[dict]
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_v3_schemas.py -v`
Expected: PASS

**Step 5: Run all existing tests to verify no regression**

Run: `uv run pytest backend/tests/ -x -v`
Expected: All existing tests PASS (new fields have defaults, old code unaffected)

**Step 6: Commit**

```bash
git add backend/app/schemas/extraction.py backend/app/agents/state.py backend/tests/test_v3_schemas.py
git commit -m "feat(v3): add BaseExtractedEntity, StatBlock schema, and V3 state fields"
```

---

### Task 4: EntityRegistry class

**Files:**
- Create: `backend/app/services/extraction/entity_registry.py`
- Test: `backend/tests/test_entity_registry.py` (create)

**Step 1: Write failing tests**

Create `backend/tests/test_entity_registry.py`:

```python
"""Tests for EntityRegistry — growing context for extraction."""
import json
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


class TestEntityRegistryContext:
    def test_to_prompt_context(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"], significance="protagonist")
        reg.add("Arcane Powershot", "Skill")
        context = reg.to_prompt_context(max_tokens=500)
        assert "Jake Thayne" in context
        assert "Arcane Powershot" in context

    def test_prompt_context_respects_max_tokens(self):
        reg = EntityRegistry()
        for i in range(100):
            reg.add(f"Entity {i}", "Character", aliases=[f"alias_{i}"])
        context = reg.to_prompt_context(max_tokens=200)
        # Should be truncated
        assert len(context.split()) < 300  # rough token proxy

    def test_add_chapter_summary(self):
        reg = EntityRegistry()
        reg.add_chapter_summary(1, "Jake enters the tutorial.")
        reg.add_chapter_summary(2, "Jake gains his class.")
        assert len(reg.chapter_summaries) == 2


class TestEntityRegistrySerialization:
    def test_to_json_roundtrip(self):
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character", aliases=["Jake"])
        reg.add("Archer", "Class")
        data = reg.to_dict()
        reg2 = EntityRegistry.from_dict(data)
        assert reg2.entity_count == 2
        assert reg2.lookup("Jake") is not None

    def test_merge_registries(self):
        reg1 = EntityRegistry()
        reg1.add("Jake Thayne", "Character")
        reg2 = EntityRegistry()
        reg2.add("Miranda Wells", "Character")
        merged = EntityRegistry.merge(reg1, reg2)
        assert merged.entity_count == 2
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_entity_registry.py -v`
Expected: FAIL (module doesn't exist)

**Step 3: Implement EntityRegistry**

Create `backend/app/services/extraction/entity_registry.py`:

```python
"""EntityRegistry — growing context for chapter-by-chapter extraction.

Accumulates known entities, aliases, and chapter summaries.
Injected into LLM prompts as context for better disambiguation.
Serializable to JSON for Neo4j persistence and cross-book sharing.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RegistryEntry:
    canonical_name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    significance: str = ""
    first_seen_chapter: int | None = None
    last_seen_chapter: int | None = None
    description: str = ""


class EntityRegistry:
    """Growing registry of known entities, maintained per book."""

    def __init__(self) -> None:
        self._entities: dict[str, RegistryEntry] = {}  # canonical_name → entry
        self._alias_map: dict[str, str] = {}  # lowercase alias → canonical_name
        self.chapter_summaries: list[str] = []

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def alias_count(self) -> int:
        return len(self._alias_map)

    def add(
        self,
        name: str,
        entity_type: str,
        aliases: list[str] | None = None,
        significance: str = "",
        first_seen_chapter: int | None = None,
        description: str = "",
    ) -> None:
        canonical = name.lower().strip()
        entry = RegistryEntry(
            canonical_name=canonical,
            entity_type=entity_type,
            aliases=aliases or [],
            significance=significance,
            first_seen_chapter=first_seen_chapter,
            description=description,
        )
        self._entities[canonical] = entry
        for alias in (aliases or []):
            self._alias_map[alias.lower().strip()] = canonical

    def lookup(self, name: str) -> RegistryEntry | None:
        key = name.lower().strip()
        if key in self._entities:
            return self._entities[key]
        canonical = self._alias_map.get(key)
        if canonical:
            return self._entities.get(canonical)
        return None

    def add_chapter_summary(self, chapter_number: int, summary: str) -> None:
        while len(self.chapter_summaries) < chapter_number:
            self.chapter_summaries.append("")
        if chapter_number <= len(self.chapter_summaries):
            self.chapter_summaries[chapter_number - 1] = summary
        else:
            self.chapter_summaries.append(summary)

    def to_prompt_context(self, max_tokens: int = 2000) -> str:
        lines: list[str] = []
        token_estimate = 0
        sorted_entries = sorted(
            self._entities.values(),
            key=lambda e: (e.significance == "protagonist", e.last_seen_chapter or 0),
            reverse=True,
        )
        for entry in sorted_entries:
            aliases_str = ", ".join(entry.aliases) if entry.aliases else ""
            line = f"- {entry.canonical_name} ({entry.entity_type})"
            if aliases_str:
                line += f" [aliases: {aliases_str}]"
            words = len(line.split())
            if token_estimate + words > max_tokens:
                break
            lines.append(line)
            token_estimate += words
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "entities": {
                k: {
                    "canonical_name": v.canonical_name,
                    "entity_type": v.entity_type,
                    "aliases": v.aliases,
                    "significance": v.significance,
                    "first_seen_chapter": v.first_seen_chapter,
                    "last_seen_chapter": v.last_seen_chapter,
                    "description": v.description,
                }
                for k, v in self._entities.items()
            },
            "alias_map": self._alias_map,
            "chapter_summaries": self.chapter_summaries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EntityRegistry:
        reg = cls()
        for _key, val in data.get("entities", {}).items():
            reg.add(
                name=val["canonical_name"],
                entity_type=val["entity_type"],
                aliases=val.get("aliases", []),
                significance=val.get("significance", ""),
                first_seen_chapter=val.get("first_seen_chapter"),
                description=val.get("description", ""),
            )
        reg.chapter_summaries = data.get("chapter_summaries", [])
        return reg

    @classmethod
    def merge(cls, *registries: EntityRegistry) -> EntityRegistry:
        merged = cls()
        for reg in registries:
            for entry in reg._entities.values():
                if entry.canonical_name not in merged._entities:
                    merged.add(
                        name=entry.canonical_name,
                        entity_type=entry.entity_type,
                        aliases=entry.aliases,
                        significance=entry.significance,
                        first_seen_chapter=entry.first_seen_chapter,
                        description=entry.description,
                    )
        return merged
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_entity_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/extraction/entity_registry.py backend/tests/test_entity_registry.py
git commit -m "feat(v3): add EntityRegistry for chapter-by-chapter context accumulation"
```

---

### Task 5: Refactor regex engine to be YAML-driven

**Files:**
- Modify: `backend/app/services/extraction/regex_extractor.py`
- Modify: `backend/tests/test_regex_extractor.py`

**Step 1: Write failing tests for YAML-driven loading**

Add to `backend/tests/test_regex_extractor.py`:

```python
class TestYamlDrivenRegex:
    def test_loads_from_ontology(self):
        from app.core.ontology_loader import OntologyLoader
        from app.services.extraction.regex_extractor import RegexExtractor
        loader = OntologyLoader.from_layers(genre="litrpg", series="primal_hunter")
        extractor = RegexExtractor.from_ontology(loader)
        assert len(extractor.patterns) >= 25

    def test_new_patterns_match(self):
        from app.core.ontology_loader import OntologyLoader
        from app.services.extraction.regex_extractor import RegexExtractor
        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "[Skill Evolved: Basic Archery → Advanced Archery - Rare]"
        matches = extractor.extract(text)
        evolved = [m for m in matches if m.pattern_name == "skill_evolved"]
        assert len(evolved) >= 1

    def test_xp_gain_pattern(self):
        from app.core.ontology_loader import OntologyLoader
        from app.services.extraction.regex_extractor import RegexExtractor
        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "You gained +1,500 XP from the kill."
        matches = extractor.extract(text)
        xp = [m for m in matches if m.pattern_name == "xp_gain"]
        assert len(xp) >= 1

    def test_quest_patterns(self):
        from app.core.ontology_loader import OntologyLoader
        from app.services.extraction.regex_extractor import RegexExtractor
        loader = OntologyLoader.from_layers(genre="litrpg")
        extractor = RegexExtractor.from_ontology(loader)
        text = "[Quest Received: Defeat the Dungeon Boss]\n[Quest Completed: Defeat the Dungeon Boss]"
        matches = extractor.extract(text)
        quests = [m for m in matches if "quest" in m.pattern_name.lower()]
        assert len(quests) >= 2
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_regex_extractor.py::TestYamlDrivenRegex -v`
Expected: FAIL (from_ontology doesn't exist)

**Step 3: Add `from_ontology` classmethod to RegexExtractor**

In `regex_extractor.py`, add a classmethod that reads patterns from the OntologyLoader instead of hard-coding them. Keep the existing `__init__` for backward compatibility but mark it as legacy. The `from_ontology` method should:
- Call `loader.get_regex_patterns()`
- Compile each pattern into a `RegexPattern` dataclass
- Return a `RegexExtractor` instance

**Step 4: Run ALL regex tests to verify no regression**

Run: `uv run pytest backend/tests/test_regex_extractor.py -v`
Expected: ALL PASS (old tests use old constructor, new tests use from_ontology)

**Step 5: Commit**

```bash
git add backend/app/services/extraction/regex_extractor.py backend/tests/test_regex_extractor.py
git commit -m "feat(v3): YAML-driven regex engine via OntologyLoader"
```

---

### Task 6: Config updates

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Add new settings**

```python
    # V3 extraction settings
    extraction_language: str = "fr"
    ontology_version: str = "3.0.0"
```

**Step 2: Run existing config tests**

Run: `uv run pytest backend/tests/ -k config -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(v3): add extraction_language and ontology_version config"
```

---

## Phase B: Pipeline Restructure

### Task 7: Prompt base template with ontology injection

**Files:**
- Create: `backend/app/prompts/base.py`
- Test: `backend/tests/test_prompt_base.py` (create)

**Step 1: Write failing tests**

Create `backend/tests/test_prompt_base.py`:

```python
"""Tests for V3 prompt base template with ontology injection."""
import pytest


class TestPromptLanguage:
    def test_french_config(self):
        from app.prompts.base import PromptLanguage, get_language_config
        config = get_language_config("fr")
        assert config.role_prefix == "Tu es"
        assert config.constraint_label == "CONTRAINTES"

    def test_english_config(self):
        from app.prompts.base import get_language_config
        config = get_language_config("en")
        assert config.role_prefix == "You are"
        assert config.constraint_label == "CONSTRAINTS"


class TestPromptBuilder:
    def test_build_extraction_prompt(self):
        from app.prompts.base import build_extraction_prompt
        prompt = build_extraction_prompt(
            phase=1,
            role_description="an expert narrative entity extractor",
            ontology_schema={"Character": {"properties": {"name": "string"}}},
            entity_registry_context="- Jake Thayne (Character)",
            previous_summary="Jake entered the tutorial.",
            phase0_hints=[{"name": "Basic Archery", "type": "Skill"}],
            few_shot_examples="[example text here]",
            language="fr",
        )
        assert "CONTRAINTES" in prompt
        assert "Jake Thayne" in prompt
        assert "Basic Archery" in prompt

    def test_ontology_schema_injected(self):
        from app.prompts.base import build_extraction_prompt
        prompt = build_extraction_prompt(
            phase=1,
            role_description="test",
            ontology_schema={"Character": {"properties": {"name": "string", "role": "enum"}}},
            language="fr",
        )
        assert "Character" in prompt
        assert "name" in prompt
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_prompt_base.py -v`
Expected: FAIL

**Step 3: Implement base prompt module**

Create `backend/app/prompts/base.py`:

```python
"""V3 prompt base template with ontology-driven schema injection.

Every extraction prompt follows a 4-part structure:
[SYSTEM] Role + language + ontology schema
[CONTRAINTES] Extraction rules
[CONTEXTE] Entity registry + previous summary + Phase 0 hints
[EXEMPLES] Few-shot examples
"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class PromptLanguage:
    code: str
    role_prefix: str
    constraint_label: str
    context_label: str
    examples_label: str
    text_label: str


_LANGUAGES = {
    "fr": PromptLanguage(
        code="fr",
        role_prefix="Tu es",
        constraint_label="CONTRAINTES",
        context_label="CONTEXTE",
        examples_label="EXEMPLES",
        text_label="TEXTE À ANALYSER",
    ),
    "en": PromptLanguage(
        code="en",
        role_prefix="You are",
        constraint_label="CONSTRAINTS",
        context_label="CONTEXT",
        examples_label="EXAMPLES",
        text_label="TEXT TO ANALYZE",
    ),
}


def get_language_config(language: str) -> PromptLanguage:
    return _LANGUAGES.get(language, _LANGUAGES["fr"])


def build_extraction_prompt(
    *,
    phase: int,
    role_description: str,
    ontology_schema: dict,
    entity_registry_context: str = "",
    previous_summary: str = "",
    phase0_hints: list[dict] | None = None,
    few_shot_examples: str = "",
    language: str = "fr",
) -> str:
    lang = get_language_config(language)
    schema_json = json.dumps(ontology_schema, ensure_ascii=False, indent=2)

    sections = []

    # SYSTEM
    sections.append(f"[SYSTEM]\n{lang.role_prefix} {role_description}.")
    sections.append(f"Phase d'extraction: {phase}")
    sections.append(f"Ontologie cible:\n```json\n{schema_json}\n```")

    # CONSTRAINTS
    constraints = [
        "Extraire UNIQUEMENT les types d'entités listés dans l'ontologie cible"
        if language == "fr" else
        "Extract ONLY the entity types listed in the target ontology",
        "Chaque entité DOIT avoir un ancrage textuel (extraction_text)"
        if language == "fr" else
        "Each entity MUST have a textual anchor (extraction_text)",
        "Confiance: attribuer un score de 0.0 à 1.0"
        if language == "fr" else
        "Confidence: assign a score from 0.0 to 1.0",
        "NE PAS inventer d'informations absentes du texte"
        if language == "fr" else
        "Do NOT invent information absent from the text",
    ]
    sections.append(f"[{lang.constraint_label}]")
    for c in constraints:
        sections.append(f"- {c}")

    # CONTEXT
    if entity_registry_context or previous_summary or phase0_hints:
        sections.append(f"\n[{lang.context_label}]")
        if entity_registry_context:
            label = "Registre d'entités connues" if language == "fr" else "Known entity registry"
            sections.append(f"{label}:\n{entity_registry_context}")
        if previous_summary:
            label = "Résumé des chapitres précédents" if language == "fr" else "Previous chapters summary"
            sections.append(f"{label}: {previous_summary}")
        if phase0_hints:
            label = "Indices Phase 0 (regex)" if language == "fr" else "Phase 0 hints (regex)"
            hints_str = json.dumps(phase0_hints, ensure_ascii=False)
            sections.append(f"{label}: {hints_str}")

    # EXAMPLES
    if few_shot_examples:
        sections.append(f"\n[{lang.examples_label}]\n{few_shot_examples}")

    return "\n".join(sections)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_prompt_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/prompts/base.py backend/tests/test_prompt_base.py
git commit -m "feat(v3): prompt base template with ontology injection and multilingual support"
```

---

### Task 8: Phase 1 prompts (narrative extraction — FR)

**Files:**
- Modify: `backend/app/prompts/extraction_characters.py` (rewrite)
- Modify: `backend/app/prompts/extraction_events.py` (rewrite)
- Modify: `backend/app/prompts/extraction_lore.py` (rewrite)

**Step 1: Rewrite extraction_characters.py**

Replace the current prompt with the V3 template structure. Key changes:
- Use `build_extraction_prompt()` from `base.py`
- All text in French
- 3 few-shot examples (golden, edge case, negative)
- Ontology schema injected dynamically (not hard-coded entity types)
- Extraction targets: Character, Faction, RELATES_TO, MEMBER_OF

**Step 2: Rewrite extraction_events.py**

Same pattern:
- Targets: Event, Arc, PARTICIPATES_IN, CAUSES, ENABLES
- Few-shots showing significance classification
- Temporal ordering (fabula_order)

**Step 3: Rewrite extraction_lore.py**

Same pattern:
- Targets: Location, Item, Concept, Prophecy
- Few-shots showing hierarchical locations, item acquisition

**Step 4: Run existing extraction tests**

Run: `uv run pytest backend/tests/test_golden_extraction.py -v`
Expected: PASS (prompts are string constants, tests mock LLM calls)

**Step 5: Commit**

```bash
git add backend/app/prompts/extraction_characters.py backend/app/prompts/extraction_events.py backend/app/prompts/extraction_lore.py
git commit -m "feat(v3): rewrite Phase 1 narrative prompts in FR with ontology injection"
```

---

### Task 9: Phase 2 prompts (genre extraction)

**Files:**
- Modify: `backend/app/prompts/extraction_systems.py` (rewrite)
- Create: `backend/app/prompts/extraction_creatures.py`

**Step 1: Rewrite extraction_systems.py as phase2_progression.py**

Targets: Skill, Class, Title, Level, StatBlock (cross-validated with Phase 0)
- Include Phase 0 regex hints in context
- 3 few-shots showing blue box → structured extraction

**Step 2: Create extraction_creatures.py**

Targets: Race, Creature, System, QuestObjective, Achievement
- Few-shots showing creature classification, system mechanics

**Step 3: Run existing system extraction tests**

Run: `uv run pytest backend/tests/ -k "system" -v`
Expected: PASS (tests mock LLM, don't depend on prompt content)

**Step 4: Commit**

```bash
git add backend/app/prompts/extraction_systems.py backend/app/prompts/extraction_creatures.py
git commit -m "feat(v3): Phase 2 genre prompts — progression and creatures"
```

---

### Task 10: Phase 3 prompts (series + discovery)

**Files:**
- Modify: `backend/app/prompts/extraction_series.py` (rewrite in FR)
- Create: `backend/app/prompts/extraction_discovery.py`

**Step 1: Rewrite extraction_series.py in French**

This is the prompt that was in English — fix it:
- Targets loaded dynamically from Layer 3 YAML
- Ontology schema passed as JSON
- 2 few-shots from Primal Hunter

**Step 2: Create extraction_discovery.py**

New prompt for auto-discovering series-specific entity types:
- Analyzes blue box patterns not matching existing regex
- Proposes new entity types with evidence
- Output schema: list of OntologyChange proposals

**Step 3: Commit**

```bash
git add backend/app/prompts/extraction_series.py backend/app/prompts/extraction_discovery.py
git commit -m "feat(v3): Phase 3 series + discovery prompts in FR"
```

---

### Task 11: Rewrite coreference and narrative analysis prompts

**Files:**
- Modify: `backend/app/prompts/coreference.py`
- Modify: `backend/app/prompts/narrative_analysis.py`

**Step 1: Rewrite coreference.py in French with few-shots**

Add 2 few-shots showing pronoun resolution in French text.

**Step 2: Rewrite narrative_analysis.py in French with output schema**

Add structured output schema + 2 few-shots showing arc detection, foreshadowing.

**Step 3: Commit**

```bash
git add backend/app/prompts/coreference.py backend/app/prompts/narrative_analysis.py
git commit -m "feat(v3): rewrite coreference and narrative prompts in FR"
```

---

### Task 12: LangGraph restructure — 6-phase pipeline

**Files:**
- Modify: `backend/app/services/extraction/__init__.py` (major rewrite)
- Modify: `backend/app/agents/state.py` (already updated in Task 3)
- Test: `backend/tests/test_v3_pipeline.py` (create)

**Step 1: Write failing tests for the new graph structure**

Create `backend/tests/test_v3_pipeline.py`:

```python
"""Tests for the V3 6-phase LangGraph pipeline."""
import pytest
from unittest.mock import AsyncMock, patch


class TestV3GraphStructure:
    def test_graph_has_6_phases(self):
        from app.services.extraction import build_extraction_graph_v3
        graph = build_extraction_graph_v3()
        node_names = set(graph.nodes.keys())
        # Phase 0
        assert "regex_extract" in node_names
        # Phase 1 (narrative)
        assert "narrative_characters" in node_names or "extract_narrative" in node_names
        # Phase 2 (genre, conditional)
        assert "extract_genre" in node_names or "genre_progression" in node_names
        # Phase 3 (series, conditional)
        assert "extract_series" in node_names or "series_extract" in node_names
        # Phase 4
        assert "reconcile" in node_names
        # Phase 5
        assert "ground_mentions" in node_names

    def test_graph_compiles(self):
        from app.services.extraction import build_extraction_graph_v3
        graph = build_extraction_graph_v3()
        compiled = graph.compile()
        assert compiled is not None


class TestPhaseRouting:
    def test_genre_phase_skipped_when_no_genre(self):
        from app.services.extraction import should_run_genre
        state = {"genre": "", "phase1_narrative": []}
        assert should_run_genre(state) is False

    def test_genre_phase_runs_for_litrpg(self):
        from app.services.extraction import should_run_genre
        state = {"genre": "litrpg", "phase1_narrative": [{"name": "Jake"}]}
        assert should_run_genre(state) is True

    def test_series_phase_skipped_when_no_series(self):
        from app.services.extraction import should_run_series
        state = {"series_name": "", "phase2_genre": []}
        assert should_run_series(state) is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_v3_pipeline.py -v`
Expected: FAIL (build_extraction_graph_v3 doesn't exist)

**Step 3: Implement the V3 graph**

In `backend/app/services/extraction/__init__.py`:
- Keep `build_extraction_graph()` as legacy (for backward compat during migration)
- Add `build_extraction_graph_v3()` with the new 6-phase structure:

```
START → regex_extract
  → [narrative_characters, narrative_events, narrative_world] (parallel)
    → merge_phase1
      → [conditional: genre_progression, genre_creatures] (parallel)
        → merge_phase2
          → [conditional: series_extract]
            → reconcile
              → ground_mentions
                → update_registry
                  → END
```

Add routing functions:
- `should_run_genre(state)` → True if genre is set and Phase 1 found entities
- `should_run_series(state)` → True if series_name is set and Phase 2 found entities

**Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_v3_pipeline.py -v`
Expected: PASS

**Step 5: Run all existing tests**

Run: `uv run pytest backend/tests/ -x -v`
Expected: ALL PASS (old graph still exists as legacy)

**Step 6: Commit**

```bash
git add backend/app/services/extraction/__init__.py backend/tests/test_v3_pipeline.py
git commit -m "feat(v3): 6-phase LangGraph pipeline with conditional genre/series routing"
```

---

### Task 13: Phase 1 extraction nodes (narrative)

**Files:**
- Modify: `backend/app/services/extraction/characters.py`
- Modify: `backend/app/services/extraction/events.py`
- Modify: `backend/app/services/extraction/lore.py`

**Step 1: Update extract_characters to accept EntityRegistry context**

Add `entity_registry` from state as prompt context. Use `build_extraction_prompt()`. Output to `phase1_narrative` state key (not just `characters`).

**Step 2: Update extract_events similarly**

**Step 3: Update extract_lore similarly**

**Step 4: Run existing tests**

Run: `uv run pytest backend/tests/ -x -v`
Expected: PASS (backward compat — old state keys still populated)

**Step 5: Commit**

```bash
git add backend/app/services/extraction/characters.py backend/app/services/extraction/events.py backend/app/services/extraction/lore.py
git commit -m "feat(v3): Phase 1 nodes with EntityRegistry context injection"
```

---

### Task 14: Phase 2 extraction nodes (genre)

**Files:**
- Modify: `backend/app/services/extraction/systems.py`
- Create: `backend/app/services/extraction/creatures.py`

**Step 1: Update extract_systems to receive Phase 1 entities as context**

The system extraction prompt should know which characters exist (from Phase 1) so it can attribute skills/classes correctly.

**Step 2: Create extract_creatures node**

New node for Race, Creature, System extraction. Uses Phase 1 entities as context.

**Step 3: Run tests**

Run: `uv run pytest backend/tests/ -x -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/services/extraction/systems.py backend/app/services/extraction/creatures.py
git commit -m "feat(v3): Phase 2 genre nodes with Phase 1 context enrichment"
```

---

### Task 15: Phase 3 extraction node (series) + discovery

**Files:**
- Create: `backend/app/services/extraction/series.py`
- Create: `backend/app/services/extraction/discovery.py`
- Test: `backend/tests/test_series_extraction.py` (create)

**Step 1: Write failing tests**

```python
class TestSeriesExtraction:
    def test_extracts_primal_hunter_entities(self):
        # Test that series-specific entities are extracted
        # Mock LLM, verify prompt contains Layer 3 schema
        ...

class TestSeriesDiscovery:
    def test_proposes_new_entity_type(self):
        # Given: blue box text with a pattern not in any regex
        # When: discovery pass runs
        # Then: returns OntologyChange proposals
        ...
```

**Step 2: Implement series extraction and discovery nodes**

**Step 3: Run tests**

**Step 4: Commit**

```bash
git add backend/app/services/extraction/series.py backend/app/services/extraction/discovery.py backend/tests/test_series_extraction.py
git commit -m "feat(v3): Phase 3 series extraction and auto-discovery nodes"
```

---

### Task 16: Enhanced reconciliation with cross-book matching

**Files:**
- Modify: `backend/app/services/extraction/reconciler.py`
- Modify: `backend/app/services/deduplication.py`
- Modify: `backend/tests/test_deduplication.py`

**Step 1: Write failing tests for cross-book dedup**

```python
class TestCrossBookDedup:
    def test_matches_entity_across_books(self):
        # Jake from Book 1 matches Jake from Book 2
        ...

    def test_no_false_cross_book_merge(self):
        # "Jake" in Book 1 != "Jake" in unrelated series
        ...
```

**Step 2: Implement cross-book entity matching**

In reconciler, when `series_entities` is provided:
- Load entity registry from previous books
- Match new entities against series registry
- Use 3-tier dedup (exact → fuzzy → LLM)
- Track `discovered_in_book` for each entity

**Step 3: Run tests**

Run: `uv run pytest backend/tests/test_deduplication.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/services/extraction/reconciler.py backend/app/services/deduplication.py backend/tests/test_deduplication.py
git commit -m "feat(v3): cross-book entity matching in reconciliation"
```

---

## Phase C: Evolution & Persistence

### Task 17: OntologyChangelog model

**Files:**
- Create: `backend/app/schemas/ontology.py`
- Test: `backend/tests/test_ontology_changelog.py` (create)

**Step 1: Write failing tests**

```python
class TestOntologyChange:
    def test_create_change(self):
        from app.schemas.ontology import OntologyChange
        change = OntologyChange(
            change_type="add_entity_type",
            layer="series",
            target="PrimordialChurch",
            proposed_by="auto_discovery",
            discovered_in_book=1,
            discovered_in_chapter=42,
            confidence=0.85,
            evidence=["[Blessing of Vilastromoz received]"],
            status="proposed",
        )
        assert change.status == "proposed"
```

**Step 2: Implement OntologyChange schema**

**Step 3: Commit**

```bash
git add backend/app/schemas/ontology.py backend/tests/test_ontology_changelog.py
git commit -m "feat(v3): OntologyChangelog schema for incremental evolution"
```

---

### Task 18: EntityRegistry persistence in Neo4j

**Files:**
- Modify: `backend/app/repositories/book_repo.py`
- Test: `backend/tests/test_entity_registry.py` (add persistence tests)

**Step 1: Write failing tests**

```python
class TestRegistryPersistence:
    @pytest.mark.asyncio
    async def test_save_and_load_registry(self, mock_neo4j_driver_with_session):
        from app.repositories.book_repo import BookRepository
        repo = BookRepository(mock_neo4j_driver_with_session)
        reg = EntityRegistry()
        reg.add("Jake Thayne", "Character")
        # Mock the save/load Cypher
        await repo.save_entity_registry("book-1", reg, "3.0.0")
        # Verify Cypher was called with JSON data
        ...
```

**Step 2: Add save/load methods to BookRepository**

```python
async def save_entity_registry(self, book_id: str, registry: EntityRegistry, ontology_version: str) -> None:
    """Persist entity registry as JSON on the Book node."""
    ...

async def load_entity_registry(self, book_id: str) -> EntityRegistry | None:
    """Load entity registry from Book node."""
    ...
```

**Step 3: Commit**

```bash
git add backend/app/repositories/book_repo.py backend/tests/test_entity_registry.py
git commit -m "feat(v3): EntityRegistry Neo4j persistence on Book node"
```

---

### Task 19: Update graph_builder for V3 pipeline

**Files:**
- Modify: `backend/app/services/graph_builder.py`

**Step 1: Add `build_chapter_graph_v3()` function**

New orchestration function that:
1. Creates EntityRegistry (or loads from previous chapter)
2. Calls `extract_chapter_v3()` with registry context
3. Updates registry with new entities
4. Persists registry to Neo4j
5. Stores `ontology_version` and `extraction_run_id` on all entities

Keep `build_chapter_graph()` as legacy wrapper.

**Step 2: Run existing tests**

Run: `uv run pytest backend/tests/test_workers.py -v`
Expected: PASS (workers still call legacy function)

**Step 3: Commit**

```bash
git add backend/app/services/graph_builder.py
git commit -m "feat(v3): graph builder V3 with EntityRegistry lifecycle"
```

---

### Task 20: Update entity_repo for new entity types + ontology_version

**Files:**
- Modify: `backend/app/repositories/entity_repo.py`
- Modify: `backend/tests/test_entity_repo_v3.py`

**Step 1: Add upsert methods for new entity types**

```python
async def upsert_stat_blocks(self, book_id, chapter, stat_blocks, batch_id): ...
async def upsert_quest_objectives(self, book_id, chapter, quests, batch_id): ...
async def upsert_achievements(self, book_id, chapter, achievements, batch_id): ...
async def upsert_realms(self, book_id, realms, batch_id): ...
```

**Step 2: Add `ontology_version` to all upsert Cypher queries**

Every MERGE query should SET `e.ontology_version = $ontology_version`.

**Step 3: Run tests**

Run: `uv run pytest backend/tests/test_entity_repo_v3.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/repositories/entity_repo.py backend/tests/test_entity_repo_v3.py
git commit -m "feat(v3): entity repo with new entity types and ontology_version tracking"
```

---

### Task 21: Update Neo4j schema for new entity types

**Files:**
- Modify: `scripts/init_neo4j.cypher`

**Step 1: Add constraints and indexes**

```cypher
-- New V3 entity types
CREATE CONSTRAINT stat_block_unique IF NOT EXISTS
  FOR (s:StatBlock) REQUIRE (s.character_name, s.chapter) IS UNIQUE;

CREATE CONSTRAINT quest_unique IF NOT EXISTS
  FOR (q:QuestObjective) REQUIRE q.name IS UNIQUE;

CREATE CONSTRAINT achievement_unique IF NOT EXISTS
  FOR (a:Achievement) REQUIRE a.name IS UNIQUE;

CREATE CONSTRAINT realm_unique IF NOT EXISTS
  FOR (r:Realm) REQUIRE r.name IS UNIQUE;

-- Indexes
CREATE INDEX stat_block_character IF NOT EXISTS FOR (s:StatBlock) ON (s.character_name);
CREATE INDEX quest_status IF NOT EXISTS FOR (q:QuestObjective) ON (q.status);

-- EntityRegistry on Book
CREATE INDEX book_registry IF NOT EXISTS FOR (b:Book) ON (b.registry_version);
```

**Step 2: Commit**

```bash
git add scripts/init_neo4j.cypher
git commit -m "feat(v3): Neo4j schema for StatBlock, QuestObjective, Achievement, Realm"
```

---

### Task 22: Update worker tasks for V3

**Files:**
- Modify: `backend/app/workers/tasks.py`

**Step 1: Add `process_book_extraction_v3` task**

New task function that:
- Uses `build_book_graph_v3()` instead of `build_book_graph()`
- Initializes EntityRegistry at start
- Passes registry through chapter-by-chapter
- Saves registry to Neo4j after each chapter
- Records `ontology_version` in job metadata

Keep `process_book_extraction` as legacy.

**Step 2: Register in WorkerSettings**

Modify `backend/app/workers/settings.py` to include new task function.

**Step 3: Run tests**

Run: `uv run pytest backend/tests/test_workers.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/workers/settings.py
git commit -m "feat(v3): V3 extraction worker task with EntityRegistry"
```

---

### Task 23: Update API endpoint for V3 extraction

**Files:**
- Modify: `backend/app/api/routes/books.py`

**Step 1: Add V3 extraction endpoint**

```python
@router.post("/{book_id}/extract/v3")
async def extract_book_v3(
    book_id: str,
    request: ExtractionRequestV3,  # includes language, force_reprocess
    arq_pool = Depends(get_arq_pool),
    ...
):
    job = await arq_pool.enqueue_job(
        "process_book_extraction_v3",
        book_id=book_id,
        genre=request.genre,
        series_name=request.series_name,
        language=request.language,
    )
    ...
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/books.py
git commit -m "feat(v3): API endpoint for V3 extraction pipeline"
```

---

## Phase D: Selective Reprocessing

### Task 24: Selective reprocessing pipeline

**Files:**
- Create: `backend/app/services/reprocessing.py`
- Test: `backend/tests/test_reprocessing.py` (create)

**Step 1: Write failing tests**

```python
class TestImpactScanning:
    def test_compute_impact_scope(self):
        from app.services.reprocessing import compute_impact_scope
        changes = [OntologyChange(change_type="add_entity_type", target="PrimordialChurch", ...)]
        scope = compute_impact_scope(changes)
        assert scope.affected_entity_types == ["PrimordialChurch"]

    def test_scan_chapters_for_impact(self):
        from app.services.reprocessing import scan_chapters_for_impact
        # Given: new regex pattern for "PrimordialChurch"
        # When: scan chapter texts
        # Then: return list of candidate chapter numbers
        ...

class TestSelectiveReextraction:
    def test_reextract_single_phase(self):
        # Only Phase 3 should run for new series entities
        ...
```

**Step 2: Implement reprocessing module**

```python
async def compute_impact_scope(changes: list[OntologyChange]) -> ImpactScope: ...
async def scan_chapters_for_impact(book_id, scope, driver) -> list[int]: ...
async def reextract_chapters(book_id, chapters, phase, ontology, driver) -> dict: ...
```

**Step 3: Run tests**

**Step 4: Commit**

```bash
git add backend/app/services/reprocessing.py backend/tests/test_reprocessing.py
git commit -m "feat(v3): selective reprocessing pipeline for ontology evolution"
```

---

### Task 25: Reprocessing API endpoint

**Files:**
- Modify: `backend/app/api/routes/books.py`

**Step 1: Add reprocessing endpoint**

```python
@router.post("/{book_id}/reprocess")
async def reprocess_book(
    book_id: str,
    request: ReprocessRequest,  # includes target_phases, chapter_range
    ...
): ...
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/books.py
git commit -m "feat(v3): API endpoint for selective reprocessing"
```

---

## Phase E: Integration & Validation

### Task 26: Update golden dataset for V3 schemas

**Files:**
- Modify: `backend/tests/fixtures/golden_primal_hunter.py`
- Modify: `backend/tests/test_golden_extraction.py`

**Step 1: Add V3 fields to golden data**

Add `confidence`, `extraction_layer`, `ontology_version` to all golden entities where appropriate.

**Step 2: Add new golden entity types**

Add golden stat blocks, quest objectives if present in test chapters.

**Step 3: Run golden tests**

Run: `uv run pytest backend/tests/test_golden_extraction.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/tests/fixtures/ backend/tests/test_golden_extraction.py
git commit -m "test(v3): update golden dataset with V3 schema fields"
```

---

### Task 27: Wire V3 as default pipeline

**Files:**
- Modify: `backend/app/services/extraction/__init__.py`
- Modify: `backend/app/services/graph_builder.py`
- Modify: `backend/app/workers/tasks.py`

**Step 1: Switch default to V3**

- `build_extraction_graph()` → calls `build_extraction_graph_v3()`
- `build_chapter_graph()` → calls `build_chapter_graph_v3()`
- `process_book_extraction()` → calls V3 logic
- Remove legacy functions (or keep behind `V3_ENABLED` config flag)

**Step 2: Run full test suite**

Run: `uv run pytest backend/tests/ -x -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add backend/app/services/ backend/app/workers/
git commit -m "feat(v3): wire V3 pipeline as default extraction path"
```

---

### Task 28: Full integration test — extract a chapter with V3

**Files:**
- Create: `backend/tests/test_v3_integration.py`

**Step 1: Write integration test**

```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_v3_full_chapter_extraction():
    """End-to-end test: Chapter text → V3 pipeline → ChapterExtractionResult."""
    # Uses mocked LLM but real LangGraph execution
    # Verifies: Phase 0 regex → Phase 1 narrative → Phase 2 genre → reconcile → ground
    # Checks: entity_registry grows, ontology_version set, extraction_layer correct
    ...
```

**Step 2: Implement and run**

Run: `uv run pytest backend/tests/test_v3_integration.py -v`

**Step 3: Commit**

```bash
git add backend/tests/test_v3_integration.py
git commit -m "test(v3): full integration test for V3 extraction pipeline"
```

---

### Task 29: Lint and type check

**Step 1: Run ruff**

```bash
uv run ruff check backend/ --fix
uv run ruff format backend/
```

**Step 2: Run pyright**

```bash
uv run pyright backend/
```

Fix any issues.

**Step 3: Run full test suite**

```bash
uv run pytest backend/tests/ -x -v
```

**Step 4: Commit fixes**

```bash
git add -A
git commit -m "fix(v3): lint and type check fixes"
```

---

### Task 30: Re-extract existing books with V3

This is a manual step after deployment:

```bash
# Via API
curl -X POST http://localhost:8000/api/books/{book_id}/extract/v3 \
  -H "Content-Type: application/json" \
  -d '{"genre": "litrpg", "series_name": "primal_hunter", "language": "fr"}'
```

Or via worker directly:
```bash
uv run python -c "
import asyncio
from app.workers.tasks import process_book_extraction_v3
# ...
"
```

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| **A: Foundation** | 1-6 | Ontology versioning, new schemas, EntityRegistry, YAML-driven regex, config |
| **B: Pipeline** | 7-15 | Prompt templates, 6-phase LangGraph, narrative/genre/series nodes |
| **C: Evolution** | 16-23 | Cross-book matching, OntologyChangelog, registry persistence, worker tasks |
| **D: Reprocessing** | 24-25 | Impact scanning, selective re-extraction, API endpoint |
| **E: Integration** | 26-30 | Golden dataset update, V3 as default, integration tests, lint/types |

**Total**: 30 tasks, ~150 steps
**Estimated LOC changed**: ~3000-4000 (across 30+ files)
**Risk**: Low — additive changes with backward compatibility via legacy wrappers
