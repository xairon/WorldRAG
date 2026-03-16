# Extraction Single-Pass SOTA Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 4-pass LangExtract extraction pipeline with a 2-step KGGen-style architecture (entities → relations) using Instructor, plus book-level post-processing (iterative clustering, entity summaries, community clustering).

**Architecture:** 2-step extraction via Instructor (Pydantic discriminated union with 15 entity types → relation extraction with temporal invalidation), 4-node linear LangGraph, book-level KGGen-style clustering + Leiden communities. Neo4j direct storage (no Graphiti).

**Tech Stack:** Python 3.12+, Instructor, Pydantic v2, LangGraph, Neo4j 5.x, leidenalg, arq, structlog

**Spec:** `docs/superpowers/specs/2026-03-16-extraction-single-pass-sota-design.md`

---

## File Map

### New files

| File | Responsibility |
|---|---|
| `backend/app/schemas/extraction_v4.py` | All v4 Pydantic schemas: 15 entity types (12 core/genre + 3 Layer 3), EntityUnion, RelationExtractionResult, ExtractionStateV4, EntitySummary |
| `backend/app/services/extraction/entities.py` | Step 1 node: extract_entities_node(), validate_and_fix_grounding(), Instructor call |
| `backend/app/services/extraction/relations.py` | Step 2 node: extract_relations_node(), Instructor call |
| `backend/app/prompts/extraction_unified.py` | Unified prompts: entity prompt, relation prompt, few-shot examples, router hints |
| `backend/app/services/extraction/book_level.py` | Book-level: iterative_cluster(), generate_entity_summaries(), community_cluster() |
| `backend/tests/services/extraction/test_extraction_schemas_v4.py` | Schema tests |
| `backend/tests/services/extraction/test_entity_extraction.py` | Step 1 tests |
| `backend/tests/services/extraction/test_relation_extraction.py` | Step 2 tests |
| `backend/tests/services/extraction/test_grounding_validation.py` | Grounding post-validation tests |
| `backend/tests/services/extraction/test_extraction_graph_v4.py` | LangGraph 4-node integration tests |
| `backend/tests/services/extraction/test_book_level.py` | Book-level post-processing tests |

### Modified files

| File | Change |
|---|---|
| `backend/app/services/extraction/__init__.py` | New `build_extraction_graph_v4()` + `extract_chapter_v4()` (keep v3 for coexistence) |
| `backend/app/agents/state.py` | Add `ExtractionStateV4` (keep old state for coexistence) |
| `backend/app/prompts/base.py` | Add `router_hints` + `extracted_entities_json` params to `build_extraction_prompt()` |
| `backend/app/services/extraction/reconciler.py` | Add `reconcile_flat_entities()` accepting flat array |
| `backend/app/services/extraction/mention_detector.py` | Add overload accepting flat entity dicts |
| `backend/app/repositories/entity_repo.py` | Add `apply_relation_end()`, `upsert_entity_summary()`, `upsert_community()`, `upsert_v4_entities()` |
| `backend/app/services/graph_builder.py` | Add `apply_alias_map_v4()` for flat array + relations |
| `backend/app/workers/tasks.py` | Add `process_book_extraction_v4()` |
| `backend/app/api/routes/books.py` | Add `POST /books/{id}/extract/v4` endpoint |
| `backend/app/llm/providers.py` | Add `get_instructor_for_extraction()` |
| `backend/app/workers/settings.py` | Register v4 task function |

### Critical constraint

**NO `from __future__ import annotations`** in `extraction_v4.py` or `state.py` — LangGraph needs runtime type resolution.

---

## Chunk 1: Foundation — Schemas + Provider

### Task 1: v4 Pydantic schemas

**Files:**
- Create: `backend/app/schemas/extraction_v4.py`
- Create: `backend/tests/services/extraction/test_extraction_schemas_v4.py`

- [ ] **Step 1: Write schema tests**

```python
# backend/tests/services/extraction/test_extraction_schemas_v4.py
"""Tests for v4 extraction schemas — discriminated union + serialization."""
import pytest
from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    EntityUnion,
    ExtractedCharacter,
    ExtractedClass,
    ExtractedRelation,
    ExtractedSkill,
    RelationEnd,
    RelationExtractionResult,
)


class TestEntityUnionDiscriminator:
    def test_character_roundtrip(self):
        char = ExtractedCharacter(
            name="Jake", canonical_name="jake", extraction_text="Jake se leva",
        )
        data = char.model_dump()
        assert data["entity_type"] == "character"
        parsed = ExtractedCharacter.model_validate(data)
        assert parsed.name == "Jake"

    def test_class_literal_is_valid(self):
        """Literal['class'] is valid Python — class is only reserved as identifier."""
        cls = ExtractedClass(
            name="Archer", extraction_text="Classe : Archer",
        )
        assert cls.entity_type == "class"
        data = cls.model_dump()
        assert data["entity_type"] == "class"

    def test_discriminated_union_deserialization(self):
        result = EntityExtractionResult.model_validate({
            "entities": [
                {"entity_type": "character", "name": "Jake", "extraction_text": "Jake"},
                {"entity_type": "skill", "name": "Shadow Step", "extraction_text": "[Skill]"},
                {"entity_type": "class", "name": "Archer", "extraction_text": "Archer"},
            ],
            "chapter_number": 5,
        })
        assert len(result.entities) == 3
        assert isinstance(result.entities[0], ExtractedCharacter)
        assert isinstance(result.entities[1], ExtractedSkill)
        assert isinstance(result.entities[2], ExtractedClass)

    def test_all_15_entity_types(self):
        """Verify all 15 entity types are valid discriminator values."""
        valid_types = [
            "character", "skill", "class", "title", "event", "location",
            "item", "creature", "faction", "concept", "level_change",
            "stat_change", "bloodline", "profession", "church",
        ]
        for t in valid_types:
            data = {"entity_type": t, "name": "test", "extraction_text": "test"}
            if t == "level_change":
                data = {"entity_type": t, "character": "jake", "new_level": 5, "extraction_text": "t"}
            elif t == "stat_change":
                data = {"entity_type": t, "character": "jake", "stat_name": "STR", "value": 5, "extraction_text": "t"}
            elif t == "church":
                data = {"entity_type": t, "deity_name": "Villy", "extraction_text": "t"}
            result = EntityExtractionResult.model_validate({"entities": [data]})
            assert len(result.entities) == 1

    def test_default_offsets_are_minus_one(self):
        char = ExtractedCharacter(name="X", extraction_text="X")
        assert char.char_offset_start == -1
        assert char.char_offset_end == -1


class TestRelationSchemas:
    def test_relation_roundtrip(self):
        rel = ExtractedRelation(
            source="jake", target="shadow step",
            relation_type="HAS_SKILL", valid_from_chapter=5,
        )
        data = rel.model_dump()
        assert data["relation_type"] == "HAS_SKILL"

    def test_relation_end(self):
        end = RelationEnd(
            source="jake", target="old skill",
            relation_type="HAS_SKILL", ended_at_chapter=30,
            reason="skill lost during evolution",
        )
        assert end.ended_at_chapter == 30

    def test_relation_result_with_ended(self):
        result = RelationExtractionResult.model_validate({
            "relations": [
                {"source": "jake", "target": "archer", "relation_type": "HAS_CLASS"},
            ],
            "ended_relations": [
                {"source": "jake", "target": "novice", "relation_type": "HAS_CLASS", "ended_at_chapter": 10},
            ],
        })
        assert len(result.relations) == 1
        assert len(result.ended_relations) == 1

    def test_sentiment_bounds(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExtractedRelation(
                source="a", target="b", relation_type="RELATES_TO", sentiment=1.5,
            )
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_extraction_schemas_v4.py -v`
Expected: ImportError (module not found)

- [ ] **Step 3: Implement extraction_v4.py**

Create `backend/app/schemas/extraction_v4.py` with all schemas from spec section 3.1 + 3.2 + 3.3.

**Critical**: Do NOT add `from __future__ import annotations` at the top of this file.

Contents: Copy the full schema code from spec sections 3.1 and 3.2 (EntityUnion with 14 types, RelationExtractionResult, RelationEnd, ExtractionState TypedDict). Include `EntitySummary` from spec section 6.2.

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_extraction_schemas_v4.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/extraction_v4.py backend/tests/services/extraction/test_extraction_schemas_v4.py
git commit -m "feat(extraction): add v4 Pydantic schemas — 14-type discriminated union"
```

---

### Task 2: Instructor provider factory

**Files:**
- Modify: `backend/app/llm/providers.py`
- Test: `backend/tests/llm/test_providers.py` (add to existing)

- [ ] **Step 1: Write test for get_instructor_for_extraction**

```python
# Add to existing test file or create new
def test_get_instructor_for_extraction_default():
    """Default returns Gemini instructor."""
    client, model = get_instructor_for_extraction()
    assert "gemini" in model.lower() or "flash" in model.lower()

def test_get_instructor_for_extraction_local_override():
    """local: prefix routes to ollama."""
    client, model = get_instructor_for_extraction("local:qwen3:32b")
    assert model == "qwen3:32b"
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/llm/test_providers.py::test_get_instructor_for_extraction_default -v`
Expected: ImportError

- [ ] **Step 3: Implement get_instructor_for_extraction()**

Add to `backend/app/llm/providers.py` the function from spec section 9.1.

- [ ] **Step 4: Run test — verify it passes**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/llm/test_providers.py -k "instructor_for_extraction" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/providers.py backend/tests/llm/test_providers.py
git commit -m "feat(llm): add get_instructor_for_extraction() provider factory"
```

---

### Task 3: Grounding validation

**Files:**
- Create: `backend/app/services/extraction/grounding.py`
- Create: `backend/tests/services/extraction/test_grounding_validation.py`

- [ ] **Step 1: Write grounding tests**

```python
# backend/tests/services/extraction/test_grounding_validation.py
from app.schemas.extraction_v4 import ExtractedCharacter
from app.services.extraction.grounding import validate_and_fix_grounding


SAMPLE_TEXT = "Jake se leva et regarda Caroline. L'archer prépara son arc."


class TestGroundingValidation:
    def test_exact_match(self):
        entity = ExtractedCharacter(
            name="Jake", extraction_text="Jake se leva",
            char_offset_start=0, char_offset_end=11,
        )
        status, confidence = validate_and_fix_grounding(entity, SAMPLE_TEXT)
        assert status == "exact"
        assert confidence == 1.0

    def test_wrong_offset_fuzzy_recovery(self):
        entity = ExtractedCharacter(
            name="Jake", extraction_text="Jake se leva",
            char_offset_start=99, char_offset_end=110,  # wrong offsets
        )
        status, confidence = validate_and_fix_grounding(entity, SAMPLE_TEXT)
        assert status == "fuzzy"
        assert confidence == 0.7
        assert entity.char_offset_start == 0  # corrected

    def test_no_offsets_fuzzy_recovery(self):
        entity = ExtractedCharacter(
            name="Jake", extraction_text="Jake se leva",
            char_offset_start=-1, char_offset_end=-1,
        )
        status, confidence = validate_and_fix_grounding(entity, SAMPLE_TEXT)
        assert status == "fuzzy"
        assert entity.char_offset_start == 0

    def test_unaligned(self):
        entity = ExtractedCharacter(
            name="Unknown", extraction_text="texte inventé par le LLM",
        )
        status, confidence = validate_and_fix_grounding(entity, SAMPLE_TEXT)
        assert status == "unaligned"
        assert confidence <= 0.5
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_grounding_validation.py -v`
Expected: ImportError

- [ ] **Step 3: Implement grounding.py**

Create `backend/app/services/extraction/grounding.py` with `validate_and_fix_grounding()` from spec section 7.1. Use `thefuzz.fuzz.partial_ratio` for the partial match (already a project dependency).

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_grounding_validation.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/grounding.py backend/tests/services/extraction/test_grounding_validation.py
git commit -m "feat(extraction): add grounding post-validation (exact/fuzzy/unaligned)"
```

---

## Chunk 2: Extraction Nodes — Steps 1 & 2

### Task 4: Unified prompts

**Files:**
- Create: `backend/app/prompts/extraction_unified.py`
- Modify: `backend/app/prompts/base.py`

- [ ] **Step 1: Add router_hints + entities_json params to base.py**

Modify `build_extraction_prompt()` in `backend/app/prompts/base.py`:
- Add param `router_hints: list[str] | None = None`
- Add param `extracted_entities_json: str | None = None`
- Accept `phase` as `str` (not just `int`) — "entities" or "relations"
- If `router_hints`, add `[FOCUS]` section after `[CONTRAINTES]`
- If `extracted_entities_json`, add `[ENTITÉS EXTRAITES]` section

- [ ] **Step 2: Write prompt tests**

```python
# backend/tests/prompts/test_extraction_unified.py
from app.prompts.extraction_unified import build_entity_prompt, build_relation_prompt

def test_entity_prompt_contains_all_sections():
    prompt = build_entity_prompt(
        registry_context="jake: Character", phase0_hints=[{"type": "skill_acquired"}],
        router_hints=["Éléments de système"], language="fr",
    )
    assert "CHARACTER" in prompt
    assert "SKILL" in prompt
    assert "BLOODLINE" in prompt  # Layer 3
    assert "[FOCUS]" in prompt
    assert "[CONTEXTE]" in prompt
    assert "jake" in prompt  # registry injected

def test_relation_prompt_contains_entities():
    prompt = build_relation_prompt(
        chapter_text="Jake se leva.",
        entities_json='[{"entity_type": "character", "name": "Jake"}]',
        language="fr",
    )
    assert "RELATES_TO" in prompt
    assert "HAS_SKILL" in prompt
    assert "Jake" in prompt
    assert "INVALIDATION" in prompt

def test_entity_prompt_english():
    prompt = build_entity_prompt(language="en")
    assert "CHARACTER" in prompt
    assert "Extract" in prompt or "extract" in prompt
```

- [ ] **Step 3: Create extraction_unified.py**

Create `backend/app/prompts/extraction_unified.py` with:
- `ENTITY_PROMPT_DESCRIPTION`: Full entity prompt from spec section 4.1
- `RELATION_PROMPT_DESCRIPTION`: Full relation prompt from spec section 4.2
- `ENTITY_FEW_SHOT_EXAMPLES`: 2-3 JSON examples covering all types
- `RELATION_FEW_SHOT_EXAMPLES`: 2 JSON examples with relations + RelationEnd
- `build_entity_prompt(chapter_text, registry_context, phase0_hints, router_hints, language)` → str
- `build_relation_prompt(chapter_text, entities_json, language)` → str

Both functions call `build_extraction_prompt()` internally.

- [ ] **Step 4: Run prompt tests**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/prompts/test_extraction_unified.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts/base.py backend/app/prompts/extraction_unified.py backend/tests/prompts/test_extraction_unified.py
git commit -m "feat(prompts): add unified entity + relation extraction prompts"
```

---

### Task 5: Step 1 — Entity extraction node

**Files:**
- Create: `backend/app/services/extraction/entities.py`
- Create: `backend/tests/services/extraction/test_entity_extraction.py`

- [ ] **Step 1: Write entity extraction tests (mock Instructor)**

```python
# backend/tests/services/extraction/test_entity_extraction.py
import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.extraction_v4 import EntityExtractionResult, ExtractedCharacter, ExtractedSkill
from app.services.extraction.entities import extract_entities_node


CHAPTER_TEXT = """Jake se leva. Il avait acquis une nouvelle compétence.
[Skill Acquired: Shadow Step - Rare]
L'archer regarda la Grande Forêt au loin."""

MOCK_RESULT = EntityExtractionResult(
    entities=[
        ExtractedCharacter(name="Jake", canonical_name="jake", extraction_text="Jake se leva", char_offset_start=0, char_offset_end=11),
        ExtractedSkill(name="Shadow Step", owner="jake", rank="rare", extraction_text="Shadow Step - Rare", char_offset_start=70, char_offset_end=88),
    ],
    chapter_number=5,
)


@pytest.mark.asyncio
async def test_extract_entities_node_returns_entities():
    state = {
        "book_id": "test-book",
        "chapter_number": 5,
        "chapter_text": CHAPTER_TEXT,
        "regex_matches_json": "[]",
        "genre": "litrpg",
        "series_name": "",
        "source_language": "fr",
        "model_override": None,
        "entity_registry": {},
    }
    with patch("app.services.extraction.entities._call_instructor", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_entities_node(state)
    assert "entities" in result
    assert len(result["entities"]) == 2
    assert len(result["grounded_entities"]) >= 2


@pytest.mark.asyncio
async def test_extract_entities_validates_grounding():
    state = {
        "book_id": "test-book",
        "chapter_number": 5,
        "chapter_text": CHAPTER_TEXT,
        "regex_matches_json": "[]",
        "genre": "litrpg",
        "series_name": "",
        "source_language": "fr",
        "model_override": None,
        "entity_registry": {},
    }
    with patch("app.services.extraction.entities._call_instructor", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_entities_node(state)
    # All grounded entities should have alignment status
    for ge in result["grounded_entities"]:
        assert ge["alignment_status"] in ("exact", "fuzzy", "unaligned")
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_entity_extraction.py -v`
Expected: ImportError

- [ ] **Step 3: Implement entities.py**

Create `backend/app/services/extraction/entities.py`:

```python
"""Step 1: Entity extraction node for the v4 pipeline."""
# NO from __future__ import annotations — LangGraph constraint
import json
from typing import Any

import structlog
from app.llm.providers import get_instructor_for_extraction
from app.prompts.extraction_unified import build_entity_prompt
from app.schemas.extraction_v4 import EntityExtractionResult, EntityUnion
from app.schemas.extraction import GroundedEntity
from app.services.extraction.grounding import validate_and_fix_grounding
from app.services.extraction.entity_registry import EntityRegistry
from app.services.extraction.router import compute_router_hints

logger = structlog.get_logger()


async def _call_instructor(
    prompt: str,
    chapter_text: str,
    model_override: str | None,
) -> EntityExtractionResult:
    """Call Instructor to extract entities. Separated for testability."""
    client, model = get_instructor_for_extraction(model_override)
    return await client.chat.completions.create(
        model=model,
        response_model=EntityExtractionResult,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": chapter_text},
        ],
        max_retries=3,
    )


async def extract_entities_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Step 1 entity extraction."""
    chapter_text = state["chapter_text"]
    chapter_number = state["chapter_number"]

    # Build registry context
    registry = EntityRegistry.from_dict(state.get("entity_registry", {}))
    registry_context = registry.to_prompt_context()

    # Parse Phase 0 hints
    phase0_hints = json.loads(state.get("regex_matches_json", "[]"))

    # Router hints from keyword scan (reuse existing router logic)
    router_hints = compute_router_hints(chapter_text, state.get("genre", "litrpg"))

    # Build prompt
    prompt = build_entity_prompt(
        registry_context=registry_context,
        phase0_hints=phase0_hints,
        router_hints=router_hints,
        language=state.get("source_language", "fr"),
    )

    # Call LLM
    result = await _call_instructor(prompt, chapter_text, state.get("model_override"))
    result.chapter_number = chapter_number

    # Post-validate grounding
    grounded_entities: list[dict[str, Any]] = []
    entities_serialized: list[dict[str, Any]] = []

    for entity in result.entities:
        status, confidence = validate_and_fix_grounding(entity, chapter_text)
        ge = GroundedEntity(
            entity_type=entity.entity_type,
            entity_name=getattr(entity, "name", getattr(entity, "deity_name", getattr(entity, "character", ""))),
            extraction_text=entity.extraction_text,
            char_offset_start=entity.char_offset_start,
            char_offset_end=entity.char_offset_end,
            alignment_status=status,
            confidence=confidence,
            pass_name="entities",
        )
        grounded_entities.append(ge.model_dump())
        entities_serialized.append(entity.model_dump())

    total = len(entities_serialized)
    logger.info("entities_extracted", chapter=chapter_number, count=total)

    return {
        "entities": entities_serialized,
        "grounded_entities": grounded_entities,
        "total_entities": total,
    }
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_entity_extraction.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/entities.py backend/tests/services/extraction/test_entity_extraction.py
git commit -m "feat(extraction): add step 1 entity extraction node (Instructor)"
```

---

### Task 6: Step 2 — Relation extraction node

**Files:**
- Create: `backend/app/services/extraction/relations.py`
- Create: `backend/tests/services/extraction/test_relation_extraction.py`

- [ ] **Step 1: Write relation extraction tests (mock Instructor)**

```python
# backend/tests/services/extraction/test_relation_extraction.py
import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.extraction_v4 import RelationExtractionResult, ExtractedRelation, RelationEnd
from app.services.extraction.relations import extract_relations_node

ENTITIES = [
    {"entity_type": "character", "name": "Jake", "canonical_name": "jake", "extraction_text": "Jake"},
    {"entity_type": "skill", "name": "Shadow Step", "owner": "jake", "extraction_text": "Shadow Step"},
]

MOCK_RESULT = RelationExtractionResult(
    relations=[
        ExtractedRelation(source="jake", target="Shadow Step", relation_type="HAS_SKILL", valid_from_chapter=5),
    ],
    ended_relations=[
        RelationEnd(source="jake", target="Old Skill", relation_type="HAS_SKILL", ended_at_chapter=5),
    ],
)


@pytest.mark.asyncio
async def test_extract_relations_node():
    state = {
        "chapter_text": "Jake acquit Shadow Step.",
        "chapter_number": 5,
        "entities": ENTITIES,
        "source_language": "fr",
        "model_override": None,
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_relations_node(state)
    assert len(result["relations"]) == 1
    assert len(result["ended_relations"]) == 1
    assert result["relations"][0]["relation_type"] == "HAS_SKILL"
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_relation_extraction.py -v`
Expected: ImportError

- [ ] **Step 3: Implement relations.py**

Create `backend/app/services/extraction/relations.py` following the same pattern as entities.py:
- `_call_instructor_relations()` — separated for mocking
- `extract_relations_node(state)` — builds prompt with entities JSON, calls Instructor, returns serialized relations + ended_relations

- [ ] **Step 4: Run test — verify it passes**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_relation_extraction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/relations.py backend/tests/services/extraction/test_relation_extraction.py
git commit -m "feat(extraction): add step 2 relation extraction node (Instructor)"
```

---

## Chunk 3: LangGraph + Adapter Layer

### Task 7: Router hints (reuse existing keyword scan)

**Files:**
- Modify: `backend/app/services/extraction/router.py`

- [ ] **Step 1: Add compute_router_hints() function**

The existing `route_extraction_passes()` does keyword scanning to decide which passes to run. Extract the keyword scanning logic into a reusable `compute_router_hints(chapter_text, genre) -> list[str]` function that returns hint strings like "Éléments de système (skills, classes, levels)". The existing function continues to work unchanged.

- [ ] **Step 2: Test with existing router tests**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -k "router" -v`
Expected: Existing tests still pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/extraction/router.py
git commit -m "feat(extraction): extract compute_router_hints() from router for v4 prompt injection"
```

---

### Task 8: Adapt reconciler for flat array

**Files:**
- Modify: `backend/app/services/extraction/reconciler.py`

- [ ] **Step 1: Add reconcile_flat_entities() function**

Add a new function `reconcile_flat_entities(entities: list[dict], client, model) -> dict[str, str]` that:
1. Groups entities by `entity_type`
2. For each group, extracts `name` (or `canonical_name` or `deity_name` or `character`)
3. Calls existing `deduplicate_entities()` per group
4. Returns merged `alias_map`

Keep existing `reconcile_chapter_result()` unchanged for v3 compatibility.

- [ ] **Step 2: Test**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -k "reconcil" -v`
Expected: Existing + new tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/extraction/reconciler.py
git commit -m "feat(extraction): add reconcile_flat_entities() for v4 flat array input"
```

---

### Task 9: Adapt mention detector for flat array

**Files:**
- Modify: `backend/app/services/extraction/mention_detector.py`

- [ ] **Step 1: Add detect_mentions_from_flat() function**

Add a function `detect_mentions_from_flat(chapter_text: str, entities: list[dict]) -> list[GroundedEntity]` that:
1. Extracts name + canonical_name + aliases from each entity dict
2. Calls existing `detect_mentions()` logic

Keep existing `detect_mentions()` unchanged.

- [ ] **Step 2: Test**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -k "mention" -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/extraction/mention_detector.py
git commit -m "feat(extraction): add detect_mentions_from_flat() for v4"
```

---

### Task 10a: Adapt entity_repo — relation end + v4 entity dispatch

**Files:**
- Modify: `backend/app/repositories/entity_repo.py`

- [ ] **Step 1: Add apply_relation_end()**

```python
async def apply_relation_end(
    self, source: str, target: str, relation_type: str,
    ended_at_chapter: int, reason: str = "", book_id: str = "",
) -> None:
    """Set valid_to_chapter on an active relation.

    Uses specific relationship type label for index-friendly queries.
    """
    query = """
    MATCH (source {canonical_name: $source})-[r:$rel_type]->(target {name: $target})
    WHERE r.valid_to_chapter IS NULL
      AND source.book_id = $book_id
    SET r.valid_to_chapter = $ended_at_chapter,
        r.end_reason = $reason
    """
    # Note: $rel_type in MATCH requires APOC or dynamic query construction
    # Implement with f-string for relationship type (safe — controlled Literal enum)
```

- [ ] **Step 2: Add upsert_v4_entities()**

Add a method that takes the flat entity array + relations and dispatches to existing `upsert_characters()`, `upsert_skills()`, etc. by filtering on `entity_type`. Also handles new relation types and `RelationEnd` entries.

- [ ] **Step 3: Test**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -k "entity_repo" -v`
Expected: Existing tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/repositories/entity_repo.py
git commit -m "feat(entity_repo): add apply_relation_end() + upsert_v4_entities()"
```

---

### Task 10b: Adapt entity_repo — summaries + communities

**Files:**
- Modify: `backend/app/repositories/entity_repo.py`

- [ ] **Step 1: Add upsert_entity_summary()**

Uses MERGE with `summary_batch_id` for rollback. Sets `summary`, `key_facts`, `mention_count` on entity nodes.

- [ ] **Step 2: Add upsert_community()**

Uses MERGE (not CREATE) with `batch_id`. Creates Community nodes + BELONGS_TO_COMMUNITY edges. Adds `WHERE e.book_id = $book_id` to the member MATCH for safety.

- [ ] **Step 3: Test**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -k "entity_repo" -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/repositories/entity_repo.py
git commit -m "feat(entity_repo): add upsert_entity_summary() + upsert_community()"
```

---

### Task 11: Adapt graph_builder alias_map for v4

**Files:**
- Modify: `backend/app/services/graph_builder.py`

- [ ] **Step 1: Write test for apply_alias_map_v4**

```python
# Add to existing test file or create backend/tests/services/test_graph_builder_v4.py
def test_apply_alias_map_v4_normalizes_entities():
    entities = [
        {"entity_type": "character", "name": "Jon", "canonical_name": "jon", "aliases": []},
        {"entity_type": "skill", "name": "Strike", "owner": "Jon", "extraction_text": "t"},
    ]
    relations = [{"source": "Jon", "target": "Strike", "relation_type": "HAS_SKILL"}]
    alias_map = {"jon": "jake", "Jon": "jake"}

    apply_alias_map_v4(entities, relations, alias_map)
    assert entities[0]["canonical_name"] == "jake"
    assert entities[1]["owner"] == "jake"
    assert relations[0]["source"] == "jake"
```

- [ ] **Step 2: Implement apply_alias_map_v4()**

Add `apply_alias_map_v4(entities: list[dict], relations: list[dict], alias_map: dict[str, str]) -> None` that normalizes names in the flat arrays (in-place). For each entity, update `name`, `canonical_name`, `owner`, `character`. For each relation, update `source`, `target`.

- [ ] **Step 3: Run test**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/test_graph_builder_v4.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/graph_builder.py backend/tests/services/test_graph_builder_v4.py
git commit -m "feat(graph_builder): add apply_alias_map_v4() for flat array normalization"
```

---

### Task 12: LangGraph v4 — 4-node linear graph

**Files:**
- Modify: `backend/app/services/extraction/__init__.py`
- Modify: `backend/app/agents/state.py`
- Create: `backend/tests/services/extraction/test_extraction_graph_v4.py`

**Note:** The state is named `ExtractionStateV4` (not `ExtractionState` as in spec) for v3/v4 coexistence. Will rename when v3 is removed.

- [ ] **Step 1: Add ExtractionStateV4 to state.py**

Add the new state TypedDict from spec section 3.3 as `ExtractionStateV4` — keep existing `ExtractionPipelineState` for v3.

**Critical**: No `from __future__ import annotations` in this file (already absent).

- [ ] **Step 2: Create adapter nodes for mention_detect and reconcile_persist**

These adapter nodes bridge the v4 state to the existing logic:

```python
# In backend/app/services/extraction/__init__.py

async def mention_detect_v4_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: run mention detection on v4 flat entities."""
    from app.services.extraction.mention_detector import detect_mentions_from_flat
    mentions = detect_mentions_from_flat(state["chapter_text"], state["entities"])
    return {"grounded_entities": [m.model_dump() for m in mentions]}


async def reconcile_and_persist_v4_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: reconcile flat entities + persist to Neo4j + update registry."""
    from app.services.extraction.reconciler import reconcile_flat_entities
    from app.services.graph_builder import apply_alias_map_v4
    from app.services.extraction.entity_registry import EntityRegistry

    # 1. Reconcile
    client, model = get_instructor_for_task("dedup")
    alias_map = await reconcile_flat_entities(state["entities"], client, model)

    # 2. Normalize names
    entities = state["entities"]
    relations = state.get("relations", [])
    apply_alias_map_v4(entities, relations, alias_map)

    # 3. Persist to Neo4j (dispatch by entity_type to existing upsert methods)
    # ... calls entity_repo.upsert_v4_entities()

    # 4. Populate EntityRegistry
    registry = EntityRegistry.from_dict(state.get("entity_registry", {}))
    for entity_dict in entities:
        name = entity_dict.get("canonical_name") or entity_dict.get("name", "")
        registry.add(
            name=name,
            entity_type=entity_dict["entity_type"],
            aliases=entity_dict.get("aliases", []),
            significance=_infer_significance(entity_dict),
            first_seen_chapter=state["chapter_number"],
            description=entity_dict.get("description", ""),
        )

    return {"alias_map": alias_map, "entity_registry": registry.to_dict()}
```

- [ ] **Step 3: Write integration test for v4 graph**

```python
# backend/tests/services/extraction/test_extraction_graph_v4.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.extraction import build_extraction_graph_v4, extract_chapter_v4

@pytest.mark.asyncio
async def test_v4_graph_runs_4_nodes():
    """Graph should run: entities → relations → mention → reconcile_persist."""
    # Mock all LLM calls, verify graph runs end-to-end
    # Verify state contains entities, relations, grounded_entities, alias_map
    # ...
```

- [ ] **Step 4: Implement build_extraction_graph_v4()**

Add to `backend/app/services/extraction/__init__.py`:

```python
def build_extraction_graph_v4() -> CompiledStateGraph:
    graph = StateGraph(ExtractionStateV4)
    graph.add_node("extract_entities", extract_entities_node)
    graph.add_node("extract_relations", extract_relations_node)
    graph.add_node("mention_detect", mention_detect_v4_node)
    graph.add_node("reconcile_persist", reconcile_and_persist_v4_node)
    graph.add_edge(START, "extract_entities")
    graph.add_edge("extract_entities", "extract_relations")
    graph.add_edge("extract_relations", "mention_detect")
    graph.add_edge("mention_detect", "reconcile_persist")
    graph.add_edge("reconcile_persist", END)
    return graph.compile()
```

Also add `extract_chapter_v4()` entry point (similar to existing `extract_chapter()`).

- [ ] **Step 5: Run tests**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_extraction_graph_v4.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/state.py backend/app/services/extraction/__init__.py backend/tests/services/extraction/test_extraction_graph_v4.py
git commit -m "feat(extraction): add v4 LangGraph — 4-node linear pipeline with adapter nodes"
```

---

## Chunk 4: Worker + Endpoint + Book-Level

### Task 13: Worker task — process_book_extraction_v4

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/workers/settings.py`

- [ ] **Step 1: Add process_book_extraction_v4()**

Add to `backend/app/workers/tasks.py` — follows the same pattern as `process_book_extraction_v3()`:
1. Load entity registry from previous books (if series)
2. Filter non-content chapters
3. For each chapter (sequential):
   - Call `extract_chapter_v4()` (the new LangGraph)
   - Update entity registry
   - Publish progress to Redis pub/sub
4. Handle QuotaExhaustedError, CostCeilingError, generic exceptions
5. Auto-enqueue `process_book_embeddings`

- [ ] **Step 2: Register in worker settings**

Add `process_book_extraction_v4` to the `functions` list in `backend/app/workers/settings.py`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/workers/settings.py
git commit -m "feat(workers): add process_book_extraction_v4 task"
```

---

### Task 14: API endpoint — POST /books/{id}/extract/v4

**Files:**
- Modify: `backend/app/api/routes/books.py`

- [ ] **Step 1: Add v4 extract endpoint**

```python
@router.post("/books/{book_id}/extract/v4")
async def extract_book_v4(
    book_id: str,
    genre: str = Query("litrpg"),
    provider: str | None = Query(None),
    neo4j_driver=Depends(get_neo4j_driver),
    redis=Depends(get_redis),
):
    """Enqueue v4 2-step extraction job."""
    # Validate book exists + status
    # Enqueue arq job
    # Return job_id
```

Follow the same pattern as the existing `extract_book()` endpoint.

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/routes/books.py
git commit -m "feat(api): add POST /books/{id}/extract/v4 endpoint"
```

---

### Task 15: Book-level post-processing

**Files:**
- Create: `backend/app/services/extraction/book_level.py`
- Create: `backend/tests/services/extraction/test_book_level.py`

- [ ] **Step 1: Verify/add igraph dependency**

```bash
cd /home/ringuet/WorldRAG && python -m uv run python -c "import igraph; print(igraph.__version__)"
```

If ImportError, add to pyproject.toml: `"igraph>=0.11"` and run `uv sync`.

- [ ] **Step 2: Write book-level tests**

Test `iterative_cluster()`, `generate_entity_summaries()`, `community_cluster()` with mocked Neo4j driver + mocked LLM. Verify:
- Clustering calls embedder + LLM
- Entity summaries generated for entities with >= min_mentions
- Leiden clustering produces communities of size >= 3
- All Neo4j writes use MERGE + batch_id

- [ ] **Step 3: Implement book_level.py**

Create `backend/app/services/extraction/book_level.py` with three functions from spec section 6:
- `iterative_cluster(driver, book_id, embedder)` — KGGen-style
- `generate_entity_summaries(driver, book_id, min_mentions=3)` — LLM summaries
- `community_cluster(driver, book_id)` — Leiden + LLM summaries

Add Redis TTL (7 days) for cluster logs.

- [ ] **Step 4: Run tests**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/services/extraction/test_book_level.py -v`
Expected: PASS

- [ ] **Step 5: Integrate into worker task**

Add book-level post-processing calls at the end of `process_book_extraction_v4()` in tasks.py.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/extraction/book_level.py backend/tests/services/extraction/test_book_level.py backend/app/workers/tasks.py
git commit -m "feat(extraction): add book-level post-processing — clustering + summaries + communities"
```

---

## Chunk 5: Integration + Verification

### Task 16: Full integration test

**Files:**
- Create: `backend/tests/integration/test_v4_pipeline_integration.py`

- [ ] **Step 1: Write end-to-end integration test**

Test the full pipeline with a real chapter fixture (from `backend/tests/fixtures/`):
1. Upload mock book data to test Neo4j
2. Call `extract_chapter_v4()` with mocked LLM
3. Verify entities in Neo4j
4. Verify relations in Neo4j
5. Verify GROUNDED_IN relationships
6. Verify temporal properties (valid_from_chapter)
7. Call book-level post-processing with mocked LLM
8. Verify entity summaries and communities in Neo4j

- [ ] **Step 2: Run integration test**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/integration/test_v4_pipeline_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_v4_pipeline_integration.py
git commit -m "test: add v4 pipeline end-to-end integration test"
```

---

### Task 17: Verify existing tests still pass

- [ ] **Step 1: Run full test suite**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -x -v --timeout=60`
Expected: All existing tests PASS (v3 untouched, v4 additive)

- [ ] **Step 2: Run linter + type checker**

```bash
cd /home/ringuet/WorldRAG && python -m uv run ruff check backend/ --fix
cd /home/ringuet/WorldRAG && python -m uv run ruff format backend/
cd /home/ringuet/WorldRAG && python -m uv run pyright backend/
```

- [ ] **Step 3: Fix any issues and commit**

```bash
git add backend/ && git commit -m "fix: resolve lint/type issues in v4 extraction pipeline"
```

---

### Task 18: Final verification commit

- [ ] **Step 1: Run the full test suite one more time**

Run: `cd /home/ringuet/WorldRAG && python -m uv run pytest backend/tests/ -v`
Expected: All PASS

- [ ] **Step 2: Verify file structure**

```bash
ls -la backend/app/schemas/extraction_v4.py
ls -la backend/app/services/extraction/entities.py
ls -la backend/app/services/extraction/relations.py
ls -la backend/app/services/extraction/grounding.py
ls -la backend/app/services/extraction/book_level.py
ls -la backend/app/prompts/extraction_unified.py
```
All files should exist.

- [ ] **Step 3: Final commit**

```bash
git add backend/ && git commit -m "feat: complete v4 extraction pipeline — 2-step SOTA with book-level post-processing"
```
