# V4 SOTA Extraction Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewire the V4 extraction pipeline to load entity types, relation types, and prompts dynamically from the ontology YAML files, support EN/FR languages, and fix the worker dispatcher bug.

**Architecture:** Static Pydantic superset (12 types including GenreEntity catch-all) + dynamic prompt generation from OntologyLoader + post-validation relation coercion. The ontology YAML drives what the LLM sees; Pydantic schemas cover the structural superset.

**Tech Stack:** Python 3.12, Pydantic v2, Instructor, LangGraph, OntologyLoader (existing), YAML templates

**Spec:** `docs/superpowers/specs/2026-03-18-v4-sota-pipeline-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/schemas/extraction_v4.py` | Rewrite | Pydantic models: 12-type union (+Arc, +Prophecy, +GenreEntity, -Bloodline/-Church/-Profession/-Skill/-Class/-Title), `relation_type` → plain `str` |
| `backend/app/prompts/extraction_unified.py` | Rewrite | Dynamic prompt builders that take `OntologyLoader` instance |
| `backend/app/prompts/templates/entity_descriptions.yaml` | Create | Bilingual (EN/FR) entity type descriptions indexed by layer |
| `backend/app/prompts/templates/few_shots.yaml` | Create | Few-shot examples indexed by genre + language |
| `backend/app/services/extraction/entities.py` | Edit | Wire OntologyLoader from state, regex fallback |
| `backend/app/services/extraction/relations.py` | Edit | Wire OntologyLoader, post-validation coercion |
| `backend/app/services/extraction/__init__.py` | Edit | `extract_chapter_v4` accepts+passes ontology in state |
| `backend/app/schemas/extraction_v4.py` (state) | Edit | Add `ontology` field to `ExtractionStateV4` |
| `backend/app/config.py` | Edit | `extraction_language="en"`, `default_genre="litrpg"` |
| `backend/app/workers/tasks.py` | Edit | Fix dispatcher, create OntologyLoader per-job |
| `backend/app/schemas/pipeline.py` | Edit | Add `ExtractionRequestV4` |
| `backend/app/api/routes/books.py` | Edit | Use `ExtractionRequestV4`, fix language fallback |
| `backend/tests/services/extraction/test_extraction_schemas_v4.py` | Rewrite | Test new 12-type union, GenreEntity, Arc, Prophecy |
| `backend/tests/prompts/test_extraction_unified.py` | Rewrite | Test dynamic prompt generation with OntologyLoader |
| `backend/tests/services/extraction/test_extraction_graph_v4.py` | Edit | Update mocks for new schema types |

---

### Task 1: Rewrite Pydantic schemas (`extraction_v4.py`)

**Files:**
- Rewrite: `backend/app/schemas/extraction_v4.py`
- Test: `backend/tests/services/extraction/test_extraction_schemas_v4.py`

- [ ] **Step 1: Write failing tests for new schema types**

Create tests for `ExtractedArc`, `ExtractedProphecy`, `ExtractedGenreEntity`, and the new 12-type `EntityUnion`. Also test that `ExtractedRelation.relation_type` is a plain `str` (no coercion at model level).

```python
# backend/tests/services/extraction/test_extraction_schemas_v4.py
"""Tests for v4 extraction schemas (12-type discriminated union)."""

import pytest
from pydantic import ValidationError

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    EntityUnion,
    ExtractedArc,
    ExtractedCharacter,
    ExtractedConcept,
    ExtractedCreature,
    ExtractedEvent,
    ExtractedFaction,
    ExtractedGenreEntity,
    ExtractedItem,
    ExtractedLevelChange,
    ExtractedLocation,
    ExtractedProphecy,
    ExtractedRelation,
    ExtractedStatChange,
    RelationEnd,
    RelationExtractionResult,
)


def test_character_roundtrip():
    char = ExtractedCharacter(
        name="Jake Thayne",
        canonical_name="jake thayne",
        aliases=["Jake", "The Primal Hunter"],
        role="protagonist",
        species="Human",
        description="A hunter awakened in the tutorial.",
        status="alive",
        extraction_text="Jake Thayne stepped forward.",
        char_offset_start=0,
        char_offset_end=26,
    )
    dumped = char.model_dump()
    assert dumped["entity_type"] == "character"
    assert dumped["name"] == "Jake Thayne"
    reloaded = ExtractedCharacter.model_validate(dumped)
    assert reloaded.name == char.name


def test_arc_roundtrip():
    arc = ExtractedArc(
        name="Tutorial Arc",
        canonical_name="tutorial arc",
        arc_type="main_plot",
        status="active",
        description="The initial tutorial phase.",
        extraction_text="The tutorial had begun.",
    )
    dumped = arc.model_dump()
    assert dumped["entity_type"] == "arc"
    reloaded = ExtractedArc.model_validate(dumped)
    assert reloaded.arc_type == "main_plot"


def test_prophecy_roundtrip():
    prophecy = ExtractedProphecy(
        name="The Chosen One",
        canonical_name="the chosen one",
        status="unfulfilled",
        description="A prophecy about a destined hero.",
        extraction_text="The prophecy spoke of one who would come.",
    )
    dumped = prophecy.model_dump()
    assert dumped["entity_type"] == "prophecy"


def test_genre_entity_skill():
    skill = ExtractedGenreEntity(
        sub_type="skill",
        name="Arcane Powershot",
        canonical_name="arcane powershot",
        owner="jake",
        rank="epic",
        description="A powerful ranged attack.",
        extraction_text="Arcane Powershot activated.",
    )
    dumped = skill.model_dump()
    assert dumped["entity_type"] == "genre_entity"
    assert dumped["sub_type"] == "skill"
    assert dumped["rank"] == "epic"


def test_genre_entity_bloodline():
    bl = ExtractedGenreEntity(
        sub_type="bloodline",
        name="Primal Hunter",
        owner="jake",
        properties={"origin": "Primordial"},
        extraction_text="His bloodline awakened.",
    )
    dumped = bl.model_dump()
    assert dumped["sub_type"] == "bloodline"
    assert dumped["properties"]["origin"] == "Primordial"


def test_genre_entity_spell_fantasy():
    spell = ExtractedGenreEntity(
        sub_type="spell",
        name="Wingardium Leviosa",
        description="Levitation charm",
        properties={"incantation": "Wingardium Leviosa"},
        extraction_text="Wingardium Leviosa!",
    )
    assert spell.sub_type == "spell"


def test_discriminated_union_resolves_all_12_types():
    """Each entity_type literal should deserialize into the correct class."""
    type_map = {
        "character": ExtractedCharacter,
        "event": ExtractedEvent,
        "location": ExtractedLocation,
        "item": ExtractedItem,
        "creature": ExtractedCreature,
        "faction": ExtractedFaction,
        "concept": ExtractedConcept,
        "arc": ExtractedArc,
        "prophecy": ExtractedProphecy,
        "level_change": ExtractedLevelChange,
        "stat_change": ExtractedStatChange,
        "genre_entity": ExtractedGenreEntity,
    }
    for entity_type, cls in type_map.items():
        # Minimal valid data per type
        if entity_type == "level_change":
            data = {"entity_type": entity_type, "character": "test"}
        elif entity_type == "stat_change":
            data = {"entity_type": entity_type, "stat_name": "STR", "value": 5}
        elif entity_type == "genre_entity":
            data = {"entity_type": entity_type, "sub_type": "skill", "name": "test"}
        else:
            data = {"entity_type": entity_type, "name": "test"}

        result = EntityExtractionResult(entities=[data])
        assert type(result.entities[0]) is cls


def test_relation_type_is_plain_str():
    """relation_type should accept any string (no BeforeValidator coercion)."""
    rel = ExtractedRelation(
        source="jake",
        target="aria",
        relation_type="HAS_BLOODLINE",
    )
    assert rel.relation_type == "HAS_BLOODLINE"

    # Unknown types should also be accepted (no coercion)
    rel2 = ExtractedRelation(
        source="jake",
        target="aria",
        relation_type="CUSTOM_RELATION",
    )
    assert rel2.relation_type == "CUSTOM_RELATION"


def test_entity_extraction_result_with_mixed_types():
    result = EntityExtractionResult(
        entities=[
            {"entity_type": "character", "name": "Jake"},
            {"entity_type": "genre_entity", "sub_type": "skill", "name": "Shadow Step"},
            {"entity_type": "arc", "name": "Tutorial Arc"},
        ],
        chapter_number=1,
    )
    assert len(result.entities) == 3
    assert isinstance(result.entities[0], ExtractedCharacter)
    assert isinstance(result.entities[1], ExtractedGenreEntity)
    assert isinstance(result.entities[2], ExtractedArc)


def test_coercion_still_works_for_core_enums():
    """Role, status, event_type etc. should still coerce."""
    char = ExtractedCharacter(name="Test", role="PROTAGONIST")
    assert char.role == "protagonist"

    event = ExtractedEvent(name="Battle", event_type="COMBAT")
    assert event.event_type == "combat"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_extraction_schemas_v4.py -v --tb=short 2>&1 | head -60`
Expected: FAIL — `ExtractedArc`, `ExtractedProphecy`, `ExtractedGenreEntity` do not exist yet.

- [ ] **Step 3: Rewrite `extraction_v4.py`**

Rewrite the file with these changes:
1. **Import fix**: Add `Any` to typing imports: `from typing import Annotated, Any, Literal` (needed for `ExtractedGenreEntity.properties: dict[str, Any]` and `ExtractionStateV4.ontology: Any`)
2. **Keep**: `ExtractedCharacter`, `ExtractedEvent`, `ExtractedLocation`, `ExtractedItem`, `ExtractedCreature`, `ExtractedFaction`, `ExtractedConcept`, `ExtractedLevelChange`, `ExtractedStatChange` — unchanged
3. **Keep**: `_make_coercer` helper function + all core enum coercers (`_coerce_role`, `_coerce_status`, `_coerce_event_type`, `_coerce_significance`). These are still used by core entity types.
4. **Remove**: `ExtractedSkill`, `ExtractedClass`, `ExtractedTitle`, `ExtractedBloodline`, `ExtractedProfession`, `ExtractedChurch` — absorbed into `ExtractedGenreEntity`
5. **Add**: `ExtractedArc` (Literal["arc"]), `ExtractedProphecy` (Literal["prophecy"]), `ExtractedGenreEntity` (Literal["genre_entity"])
6. **Change**: `_RELATION_TYPES` set → removed. `CoercedRelationType` → removed. `ExtractedRelation.relation_type` becomes plain `str`.
7. **Remove**: `_coerce_relation_type` and `CoercedRelationType` (relation coercion moves to post-validation in `extract_relations_node`)
8. **Update**: `EntityUnion` to 12 types, `ExtractionStateV4` adds `ontology: Any` field

Key code for new types:

```python
class ExtractedArc(BaseModel):
    entity_type: Literal["arc"] = "arc"
    name: str = Field(..., description="Narrative arc name")
    canonical_name: str = ""
    arc_type: str = ""  # main_plot, subplot, character_arc, world_arc
    status: str = ""  # active, completed, abandoned
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedProphecy(BaseModel):
    entity_type: Literal["prophecy"] = "prophecy"
    name: str = Field(..., description="Prophecy name or title")
    canonical_name: str = ""
    status: str = ""  # unfulfilled, fulfilled, subverted
    description: str = ""
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedGenreEntity(BaseModel):
    """Catch-all for genre/series-specific entity types."""
    entity_type: Literal["genre_entity"] = "genre_entity"
    sub_type: str = Field(..., description="Ontology-defined sub-type (e.g. skill, class, spell)")
    name: str = Field(..., description="Entity name as in text")
    canonical_name: str = ""
    description: str = ""
    owner: str = ""
    tier: str = ""
    rank: str = ""
    effects: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    extraction_text: str = ""
    char_offset_start: int = -1
    char_offset_end: int = -1
```

For `ExtractedRelation`, change:
```python
# BEFORE
relation_type: CoercedRelationType = Field(...)

# AFTER
relation_type: str = Field(..., description="Neo4j relation type — post-validated by node")
```

For `ExtractionStateV4`, add:
```python
# Add to the TypedDict
ontology: Any  # OntologyLoader instance, passed from worker
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_extraction_schemas_v4.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/extraction_v4.py backend/tests/services/extraction/test_extraction_schemas_v4.py
git commit -m "feat(schemas): rewrite V4 extraction schemas — 12-type union with GenreEntity catch-all

- Add ExtractedArc, ExtractedProphecy, ExtractedGenreEntity
- Remove ExtractedSkill/Class/Title/Bloodline/Profession/Church (→ GenreEntity)
- relation_type becomes plain str (post-validated in node)
- ExtractionStateV4 gains ontology field"
```

---

### Task 2: Create prompt templates (YAML files)

**Files:**
- Create: `backend/app/prompts/templates/entity_descriptions.yaml`
- Create: `backend/app/prompts/templates/few_shots.yaml`

- [ ] **Step 1: Create entity_descriptions.yaml**

Create `backend/app/prompts/templates/entity_descriptions.yaml` with bilingual (EN/FR) descriptions for:
- **core**: character, event, location, item, creature, faction, concept, arc, prophecy
- **genre**: skill, class, title, system, race, quest, achievement, realm, level, stat_block
- **series**: bloodline, profession, church, alchemy_recipe, floor

Each entry has `en:` and `fr:` keys with the full field descriptions as shown in the spec Section 5 "Templates YAML". Copy the entity descriptions from the current hardcoded `ENTITY_PROMPT_DESCRIPTION` in `extraction_unified.py`, adapting them to the new `genre_entity` format for genre/series types.

For genre types, prefix with: `SKILL (use entity_type="genre_entity", sub_type="skill"):` to teach the LLM the mapping.

- [ ] **Step 2: Create few_shots.yaml**

Create `backend/app/prompts/templates/few_shots.yaml` with:
- `litrpg.entities.en` — English LitRPG entity extraction example (from spec Section 5)
- `litrpg.entities.fr` — French version (adapted from current `ENTITY_FEW_SHOT_FR`)
- `litrpg.relations.en` — English relation extraction example
- `litrpg.relations.fr` — French version (adapted from current `RELATION_FEW_SHOT_FR`)
- `core.entities.en` — Generic fiction entity example (no genre-specific types)
- `core.entities.fr` — French version

The LitRPG few-shots must use `genre_entity` format:
```json
{"entity_type": "genre_entity", "sub_type": "skill", "name": "Thunderstrike", ...}
```

- [ ] **Step 3: Validate YAML structure loads correctly**

Run: `cd /home/ringuet/WorldRAG && python -m uv run python -c "
import yaml
from pathlib import Path
d = Path('backend/app/prompts/templates')
descs = yaml.safe_load((d / 'entity_descriptions.yaml').read_text())
shots = yaml.safe_load((d / 'few_shots.yaml').read_text())
# Verify key structure matches what _build_type_descriptions expects
assert 'core' in descs, 'Missing core key'
assert 'character' in descs['core'], 'Missing core.character'
assert 'en' in descs['core']['character'], 'Missing core.character.en'
assert 'fr' in descs['core']['character'], 'Missing core.character.fr'
if 'genre' in descs:
    assert 'skill' in descs['genre'], 'Missing genre.skill'
# Verify few_shots structure
assert 'litrpg' in shots, 'Missing litrpg key'
assert 'entities' in shots['litrpg'], 'Missing litrpg.entities'
assert 'en' in shots['litrpg']['entities'], 'Missing litrpg.entities.en'
print('YAML structure OK')
"`
Expected: `YAML structure OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/prompts/templates/
git commit -m "feat(prompts): add bilingual YAML templates for entity descriptions and few-shots"
```

---

### Task 3: Rewrite prompt builders (`extraction_unified.py`)

**Files:**
- Rewrite: `backend/app/prompts/extraction_unified.py`
- Test: `backend/tests/prompts/test_extraction_unified.py`

- [ ] **Step 1: REPLACE the existing test file with new failing tests**

**Important:** The existing `test_extraction_unified.py` has 9 tests using the old `build_entity_prompt(language="fr")` signature (no `ontology` param). Delete the entire file and replace with the new tests below.

```python
# backend/tests/prompts/test_extraction_unified.py
"""Tests for dynamic ontology-driven prompt builders (v4)."""

from __future__ import annotations

from app.core.ontology_loader import OntologyLoader
from app.prompts.extraction_unified import build_entity_prompt, build_relation_prompt


def _get_ontology(genre: str = "litrpg", series: str = "") -> OntologyLoader:
    return OntologyLoader.from_layers(genre=genre, series=series)


def test_entity_prompt_en_contains_core_types():
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "CHARACTER" in prompt
    assert "EVENT" in prompt
    assert "LOCATION" in prompt
    assert "ARC" in prompt
    assert "PROPHECY" in prompt


def test_entity_prompt_en_contains_genre_types():
    onto = _get_ontology(genre="litrpg")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "SKILL" in prompt
    assert "genre_entity" in prompt
    assert 'sub_type="skill"' in prompt


def test_entity_prompt_en_contains_series_types():
    onto = _get_ontology(genre="litrpg", series="primal_hunter")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "BLOODLINE" in prompt
    assert "PROFESSION" in prompt


def test_entity_prompt_fr_is_french():
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="fr")
    assert "Tu es" in prompt or "CHARACTER" in prompt  # French role prefix
    assert "extraction_text" in prompt


def test_entity_prompt_en_is_not_empty():
    """The EN prompt must NOT be empty (was the old bug)."""
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert len(prompt) > 500  # Must have substantial content


def test_entity_prompt_core_only_no_genre_types():
    # NOTE: genre="core" loads core.yaml twice (as Layer 1 and as genre layer).
    # OntologyLoader dedupes node_types via dict merge, but layers_loaded will be
    # ["core", "core"]. The prompt builder checks layer count > 1 to show genre types.
    # We use genre="" which logs a warning but truly loads only Layer 1.
    # TODO: fix OntologyLoader.from_layers to skip genre if genre == "core" or genre == ""
    onto = OntologyLoader.from_layers(genre="", series="")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "CHARACTER" in prompt
    # Should NOT have LitRPG-specific types
    assert "SKILL" not in prompt
    assert "BLOODLINE" not in prompt


def test_entity_prompt_injects_ontology_schema():
    onto = _get_ontology()
    prompt = build_entity_prompt(ontology=onto, language="en")
    # to_json_schema() output should appear
    assert "Target ontology" in prompt or "ontology" in prompt.lower()


def test_entity_prompt_with_registry_and_hints():
    onto = _get_ontology()
    prompt = build_entity_prompt(
        ontology=onto,
        language="en",
        registry_context="jake thayne: character, protagonist",
        phase0_hints=[{"type": "skill_acquired", "name": "Shadow Step"}],
    )
    assert "jake thayne" in prompt
    assert "Shadow Step" in prompt


def test_relation_prompt_en_contains_relation_types():
    onto = _get_ontology()
    prompt = build_relation_prompt(
        ontology=onto,
        entities_json='[{"entity_type": "character", "name": "Jake"}]',
        language="en",
    )
    assert "RELATES_TO" in prompt
    assert "HAS_SKILL" in prompt
    assert "OCCURS_BEFORE" in prompt  # Was missing in old version
    assert "Jake" in prompt


def test_relation_prompt_includes_layer3_relations():
    onto = _get_ontology(genre="litrpg", series="primal_hunter")
    prompt = build_relation_prompt(
        ontology=onto,
        entities_json="[]",
        language="en",
    )
    assert "HAS_BLOODLINE" in prompt
    assert "WORSHIPS" in prompt
    assert "CLEARS_FLOOR" in prompt


def test_few_shots_included_for_litrpg():
    onto = _get_ontology(genre="litrpg")
    prompt = build_entity_prompt(ontology=onto, language="en")
    assert "Example" in prompt or "example" in prompt


def test_few_shots_included_for_fr():
    onto = _get_ontology(genre="litrpg")
    prompt = build_entity_prompt(ontology=onto, language="fr")
    assert "Exemple" in prompt or "exemple" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/prompts/test_extraction_unified.py -v --tb=short 2>&1 | head -40`
Expected: FAIL — `build_entity_prompt` signature changed, `ontology` param doesn't exist yet.

- [ ] **Step 3: Rewrite `extraction_unified.py`**

Replace the entire file. Remove all hardcoded constants (`ENTITY_PROMPT_DESCRIPTION`, `RELATION_PROMPT_DESCRIPTION`, `ENTITY_FEW_SHOT_FR`, `RELATION_FEW_SHOT_FR`). New structure:

```python
"""Dynamic ontology-driven extraction prompts for WorldRAG v4 pipeline.

Prompts are generated from:
1. OntologyLoader — entity types + relation types active for the genre/series
2. templates/entity_descriptions.yaml — bilingual field descriptions per type
3. templates/few_shots.yaml — few-shot examples per genre + language
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from app.prompts.base import build_extraction_prompt

if TYPE_CHECKING:
    from app.core.ontology_loader import OntologyLoader

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Cache loaded templates at module level
_entity_descriptions: dict | None = None
_few_shots: dict | None = None


def _load_entity_descriptions() -> dict:
    global _entity_descriptions
    if _entity_descriptions is None:
        with open(_TEMPLATES_DIR / "entity_descriptions.yaml", encoding="utf-8") as f:
            _entity_descriptions = yaml.safe_load(f)
    return _entity_descriptions


def _load_few_shots() -> dict:
    global _few_shots
    if _few_shots is None:
        with open(_TEMPLATES_DIR / "few_shots.yaml", encoding="utf-8") as f:
            _few_shots = yaml.safe_load(f)
    return _few_shots


def _build_type_descriptions(ontology: OntologyLoader, language: str) -> str:
    """Build the [TASK] section listing active entity types with descriptions."""
    descs = _load_entity_descriptions()
    sections = []

    # Core types (always active)
    core_descs = descs.get("core", {})
    if core_descs:
        header = "=== CORE ENTITY TYPES ===" if language == "en" else "=== TYPES D'ENTITÉS CORE ==="
        sections.append(header)
        for type_name, lang_map in core_descs.items():
            text = lang_map.get(language, lang_map.get("en", ""))
            if text:
                sections.append(text.strip())

    # Genre types (only if a real genre layer loaded — not "core" again)
    genre_descs = descs.get("genre", {})
    has_genre = len(ontology.layers_loaded) > 1 and ontology.layers_loaded[1] != "core"
    if genre_descs and has_genre:
        genre_label = ontology.layers_loaded[1] if len(ontology.layers_loaded) > 1 else "genre"
        header = (
            f"=== GENRE-SPECIFIC ENTITY TYPES ({genre_label.upper()}) ==="
            if language == "en"
            else f"=== TYPES D'ENTITÉS GENRE ({genre_label.upper()}) ==="
        )
        sections.append(header)
        for type_name, lang_map in genre_descs.items():
            # Only include types that exist in the loaded ontology
            if type_name.capitalize() in ontology.node_types or type_name in ontology.node_types:
                text = lang_map.get(language, lang_map.get("en", ""))
                if text:
                    sections.append(text.strip())

    # Series types (only if series layer loaded)
    series_descs = descs.get("series", {})
    has_series = len(ontology.layers_loaded) > 2
    if series_descs and has_series:
        series_label = ontology.layers_loaded[2] if len(ontology.layers_loaded) > 2 else "series"
        header = (
            f"=== SERIES-SPECIFIC ({series_label.upper()}) ==="
            if language == "en"
            else f"=== SPÉCIFIQUE À LA SÉRIE ({series_label.upper()}) ==="
        )
        sections.append(header)
        for type_name, lang_map in series_descs.items():
            if type_name.capitalize() in ontology.node_types or type_name in ontology.node_types:
                text = lang_map.get(language, lang_map.get("en", ""))
                if text:
                    sections.append(text.strip())

    return "\n\n".join(sections)


def _build_relation_descriptions(ontology: OntologyLoader, language: str) -> str:
    """Build relation type descriptions from ontology."""
    sections = []
    for rel_name, rel_type in ontology.relationship_types.items():
        # Skip bibliographic relations
        if rel_name in ("CONTAINS_WORK", "HAS_CHAPTER", "HAS_CHUNK", "GROUNDED_IN", "MENTIONED_IN"):
            continue
        line = f"{rel_name} ({rel_type.from_type} → {rel_type.to_type})"
        if rel_type.properties:
            props = ", ".join(rel_type.properties.keys())
            line += f" — properties: {props}"
        sections.append(line)
    return "\n".join(sections)


def _get_few_shots(genre: str, phase: str, language: str) -> str:
    """Load few-shot examples for genre + phase + language."""
    shots = _load_few_shots()
    # Try genre-specific first, fallback to "core"
    genre_shots = shots.get(genre, shots.get("core", {}))
    phase_shots = genre_shots.get(phase, {})
    return phase_shots.get(language, phase_shots.get("en", ""))


def build_entity_prompt(
    ontology: OntologyLoader,
    language: str = "en",
    registry_context: str = "",
    phase0_hints: list[dict] | None = None,
    router_hints: list[str] | None = None,
) -> str:
    """Build Step 1 entity extraction prompt from ontology."""
    # Determine active genre for few-shots
    active_genre = (
        ontology.layers_loaded[1]
        if len(ontology.layers_loaded) > 1 and ontology.layers_loaded[1] != "core"
        else "core"
    )

    role = (
        "an expert in Knowledge Graph extraction for narrative fiction"
        if language == "en"
        else "un expert en extraction de Knowledge Graphs pour la fiction narrative"
    )

    type_descriptions = _build_type_descriptions(ontology, language)
    few_shots = _get_few_shots(active_genre, "entities", language)

    # Filter ontology schema to extractable types only (exclude bibliographic)
    extractable = {
        k: v
        for k, v in ontology.to_json_schema().items()
        if k not in ("Series", "Book", "Chapter", "Chunk")
    }

    return build_extraction_prompt(
        phase="entities",
        role_description=role,
        ontology_schema=extractable,
        task_instructions=type_descriptions,
        entity_registry_context=registry_context,
        phase0_hints=phase0_hints,
        router_hints=router_hints,
        few_shot_examples=few_shots,
        language=language,
    )


def build_relation_prompt(
    ontology: OntologyLoader,
    entities_json: str = "",
    language: str = "en",
) -> str:
    """Build Step 2 relation extraction prompt from ontology."""
    active_genre = (
        ontology.layers_loaded[1]
        if len(ontology.layers_loaded) > 1 and ontology.layers_loaded[1] != "core"
        else "core"
    )

    role = (
        "an expert in narrative relation analysis for Knowledge Graphs"
        if language == "en"
        else "un expert en analyse de relations narratives pour Knowledge Graphs"
    )

    relation_descriptions = _build_relation_descriptions(ontology, language)
    few_shots = _get_few_shots(active_genre, "relations", language)

    return build_extraction_prompt(
        phase="relations",
        role_description=role,
        ontology_schema={},  # Relations don't need the entity schema
        task_instructions=relation_descriptions,
        extracted_entities_json=entities_json,
        few_shot_examples=few_shots,
        language=language,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/prompts/test_extraction_unified.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts/extraction_unified.py backend/tests/prompts/test_extraction_unified.py
git commit -m "feat(prompts): dynamic ontology-driven prompt generation — replaces hardcoded FR/LitRPG"
```

---

### Task 4: Wire OntologyLoader into extraction nodes

**Files:**
- Edit: `backend/app/services/extraction/entities.py`
- Edit: `backend/app/services/extraction/relations.py`
- Edit: `backend/app/services/extraction/__init__.py:1548-1583`

- [ ] **Step 1: Edit `entities.py` — wire ontology + regex fallback**

Changes to `extract_entities_node`:
1. Read `ontology` from `state["ontology"]` (OntologyLoader instance)
2. Pass `ontology` to `build_entity_prompt()` (new signature)
3. Add regex fallback: if stored hints are empty, run `RegexExtractor.from_ontology()` live

```python
# Key changes in extract_entities_node:
from app.core.ontology_loader import OntologyLoader

async def extract_entities_node(state: dict[str, Any]) -> dict[str, Any]:
    chapter_text = state["chapter_text"]
    chapter_number = state["chapter_number"]
    ontology: OntologyLoader = state["ontology"]  # NEW: from state

    registry = EntityRegistry.from_dict(state.get("entity_registry", {}))
    registry_context = registry.to_prompt_context()

    # Phase 0 hints — stored or live fallback
    stored_hints = json.loads(state.get("regex_matches_json", "[]"))
    if not stored_hints:
        try:
            from app.services.extraction.regex_extractor import RegexExtractor
            # from_ontology takes an OntologyLoader instance, NOT genre/series kwargs
            extractor = RegexExtractor.from_ontology(ontology)
            stored_hints = extractor.extract(chapter_text)
        except Exception:
            pass  # regex is optional
    phase0_hints = stored_hints

    # ALSO: update entity_name extraction in grounding loop (old line 86-90).
    # Remove `getattr(entity, "deity_name", "")` — ExtractedChurch is gone.
    # GenreEntity always has `name`, so use:
    #   entity_name = getattr(entity, "name", "") or getattr(entity, "character", "")

    # Router hints
    router_hints: list[str] = []
    try:
        from app.services.extraction.router import compute_router_hints
        router_hints = compute_router_hints(chapter_text, state.get("genre", "litrpg"))
    except (ImportError, AttributeError):
        pass

    # Build prompt from ontology (NEW)
    prompt = build_entity_prompt(
        ontology=ontology,  # NEW
        language=state.get("source_language", "en"),  # DEFAULT: en
        registry_context=registry_context,
        phase0_hints=phase0_hints,
        router_hints=router_hints,
    )

    # ... rest unchanged
```

- [ ] **Step 2: Edit `relations.py` — wire ontology + post-coercion**

Changes to `extract_relations_node`:
1. Read `ontology` from state
2. Pass `ontology` to `build_relation_prompt()`
3. Post-validate `relation_type` using ontology-driven coercer

```python
from app.core.ontology_loader import OntologyLoader
from app.schemas.extraction_v4 import _make_coercer  # Reuse existing helper

async def extract_relations_node(state: dict[str, Any]) -> dict[str, Any]:
    chapter_text = state["chapter_text"]
    chapter_number = state["chapter_number"]
    entities = state.get("entities", [])
    ontology: OntologyLoader = state["ontology"]  # NEW

    entities_json = json.dumps(entities, ensure_ascii=False, indent=2)

    prompt = build_relation_prompt(
        ontology=ontology,  # NEW
        entities_json=entities_json,
        language=state.get("source_language", "en"),  # DEFAULT: en
    )

    result = await _call_instructor_relations(prompt, chapter_text, state.get("model_override"))

    # Post-coerce relation types from ontology (NEW)
    allowed = set(ontology.get_relationship_type_names())
    coerce = _make_coercer(allowed, default="RELATES_TO")

    relations_serialized = []
    for rel in result.relations:
        d = rel.model_dump()
        d["relation_type"] = coerce(d["relation_type"])  # NEW: post-coerce
        if d.get("valid_from_chapter") is None:
            d["valid_from_chapter"] = chapter_number
        relations_serialized.append(d)

    # ... rest unchanged
```

- [ ] **Step 3: Edit `__init__.py` — pass ontology through state**

In `extract_chapter_v4` (line 1548), add `ontology` parameter and pass it to initial state:

```python
async def extract_chapter_v4(
    *,
    book_id: str,
    chapter_number: int,
    chapter_text: str,
    regex_matches_json: str = "[]",
    genre: str = "litrpg",
    series_name: str = "",
    source_language: str = "en",  # CHANGED: default en
    model_override: str | None = None,
    entity_registry: dict | None = None,
    chunk_texts: list[str] | None = None,
    ontology: Any = None,  # NEW
) -> dict[str, Any]:
    graph = _get_v4_graph()

    # Create ontology if not provided (backward compat)
    if ontology is None:
        from app.core.ontology_loader import OntologyLoader
        ontology = OntologyLoader.from_layers(genre=genre, series=series_name)

    initial_state = {
        "book_id": book_id,
        "chapter_number": chapter_number,
        "chapter_text": chapter_text,
        "chunk_texts": chunk_texts or [],
        "regex_matches_json": regex_matches_json,
        "genre": genre,
        "series_name": series_name,
        "source_language": source_language,
        "model_override": model_override,
        "entity_registry": entity_registry or {},
        "series_entities": [],
        "ontology": ontology,  # NEW
    }

    result = await graph.ainvoke(initial_state)
    return result
```

- [ ] **Step 4: Run schema + prompt + graph tests**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_extraction_schemas_v4.py backend/tests/prompts/test_extraction_unified.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/entities.py backend/app/services/extraction/relations.py backend/app/services/extraction/__init__.py
git commit -m "feat(extraction): wire OntologyLoader into V4 nodes — dynamic prompts + relation coercion + regex fallback"
```

---

### Task 5: Config + Worker + API fixes

**Files:**
- Edit: `backend/app/config.py:99-102`
- Edit: `backend/app/workers/tasks.py:27-58,436-593`
- Edit: `backend/app/schemas/pipeline.py:192-221`
- Edit: `backend/app/api/routes/books.py:516-610`

- [ ] **Step 1: Edit `config.py` — change defaults**

```python
# Line 101: change "fr" to "en"
extraction_language: str = "en"

# Add after line 102:
default_genre: str = "litrpg"
```

- [ ] **Step 2: Edit `pipeline.py` — add `ExtractionRequestV4`**

Add after the `ExtractionRequestV3` class (line 221):

```python
class ExtractionRequestV4(BaseModel):
    """Request body for POST /books/{id}/extract/v4."""

    chapters: list[int] | None = Field(
        None,
        description="Chapter numbers to extract. null = all chapters.",
    )
    language: str = Field(
        "en",
        description="Source language of the book text (en, fr).",
    )
    series_name: str | None = Field(
        None,
        description="Override series name for this extraction.",
    )
    genre: str | None = Field(
        None,
        description="Override genre for this extraction (litrpg, fantasy, core).",
    )
    provider: str | None = Field(
        None,
        description="LLM provider override (provider:model format).",
    )
```

- [ ] **Step 3: Edit `books.py` — use `ExtractionRequestV4`**

Change line 524:
```python
# BEFORE
body: ExtractionRequestV3 | None = None,

# AFTER
body: ExtractionRequestV4 | None = None,
```

Change line 547:
```python
# BEFORE
language = body.language if body else "fr"

# AFTER
from app.config import settings
language = body.language if body else settings.extraction_language
```

Update import at top of file:
```python
from app.schemas.pipeline import (
    ExtractionRequest,
    ExtractionRequestV3,
    ExtractionRequestV4,  # NEW
    ReprocessRequest,
)
```

- [ ] **Step 4: Edit `tasks.py` — fix dispatcher + pass ontology**

Fix `process_book_extraction` (line 49-58): when `use_v3_pipeline=False`, delegate to `process_book_extraction_v4` instead of `build_book_graph`.

**Important:** Keep the existing function signature unchanged. Only replace the `use_v3_pipeline=False` branch (lines 59-161). The V3 branch (lines 49-58) stays as-is. Do NOT simplify or remove the existing error handling (QuotaExhaustedError, progress publishing, etc.) — those are handled inside `process_book_extraction_v4` already.

```python
async def process_book_extraction(
    ctx: dict[str, Any],
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    chapters: list[int] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    from app.config import settings

    if settings.use_v3_pipeline:
        return await process_book_extraction_v3(
            ctx, book_id, genre, series_name, chapters,
            settings.extraction_language,
        )

    # FIX: delegate to V4 (was calling build_book_graph which is V3 legacy)
    # All error handling (QuotaExhausted, progress, DLQ) lives inside V4 task
    return await process_book_extraction_v4(
        ctx, book_id, genre, series_name, chapters,
        settings.extraction_language, provider,
    )
```

In `process_book_extraction_v4` (line 436), create OntologyLoader per-job and pass to `extract_chapter_v4`:

After line 506 (`entity_registry = EntityRegistry()`), add:
```python
from app.core.ontology_loader import OntologyLoader
ontology = OntologyLoader.from_layers(genre=genre, series=series_name)
logger.info("v4_ontology_loaded", layers=ontology.layers_loaded, node_types=len(ontology.node_types))
```

In the `extract_chapter_v4` call (line 583), add `ontology=ontology`:
```python
result = await extract_chapter_v4(
    book_id=book_id,
    chapter_number=chapter.number,
    chapter_text=chapter.text,
    regex_matches_json=regex_json,
    genre=genre,
    series_name=series_name,
    source_language=language,
    model_override=provider,
    entity_registry=entity_registry.to_dict(),
    ontology=ontology,  # NEW
)
```

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -x -v --tb=short -q 2>&1 | tail -30`
Expected: No new failures (some existing failures may remain from other branches)

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/schemas/pipeline.py backend/app/api/routes/books.py backend/app/workers/tasks.py
git commit -m "fix(pipeline): wire V4 dispatcher + config defaults EN + ExtractionRequestV4 + ontology per-job"
```

---

### Task 6: Update V4 graph test mocks

**Files:**
- Edit: `backend/tests/services/extraction/test_extraction_graph_v4.py`

- [ ] **Step 1: Update test to use new schema types**

The test uses `ExtractedSkill` which no longer exists. Replace with `ExtractedGenreEntity`:

```python
# BEFORE
from app.schemas.extraction_v4 import ExtractedSkill
ExtractedSkill(name="Shadow Step", owner="jake", ...)

# AFTER
from app.schemas.extraction_v4 import ExtractedGenreEntity
ExtractedGenreEntity(sub_type="skill", name="Shadow Step", owner="jake", ...)
```

Also add `ontology` to the test's initial state:
```python
from app.core.ontology_loader import OntologyLoader
ontology = OntologyLoader.from_layers(genre="litrpg", series="")

# In the state dict:
"ontology": ontology,
```

- [ ] **Step 2: Run the updated test**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_extraction_graph_v4.py -v --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/extraction/test_extraction_graph_v4.py
git commit -m "test: update V4 graph tests for new schema types (GenreEntity, ontology in state)"
```

---

### Task 7: Final verification + lint

- [ ] **Step 1: Run ruff check**

Run: `cd /home/ringuet/WorldRAG && python -m uv run ruff check backend/app/schemas/extraction_v4.py backend/app/prompts/extraction_unified.py backend/app/services/extraction/entities.py backend/app/services/extraction/relations.py backend/app/workers/tasks.py backend/app/config.py backend/app/schemas/pipeline.py --fix`

- [ ] **Step 2: Run ruff format**

Run: `cd /home/ringuet/WorldRAG && python -m uv run ruff format backend/app/schemas/extraction_v4.py backend/app/prompts/extraction_unified.py backend/app/services/extraction/entities.py backend/app/services/extraction/relations.py backend/app/workers/tasks.py backend/app/config.py backend/app/schemas/pipeline.py`

- [ ] **Step 3: Run full test suite**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -x -v --tb=short -q 2>&1 | tail -40`

- [ ] **Step 4: Fix any failures and commit**

```bash
git add -u
git commit -m "fix: lint and test fixes for V4 SOTA pipeline"
```
