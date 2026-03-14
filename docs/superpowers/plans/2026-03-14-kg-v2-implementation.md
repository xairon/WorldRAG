# KG v2 — SOTA Assembly + SagaProfileInducer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom extraction pipeline with Graphiti (central engine) + SagaProfileInducer (ontology induction), rewrite the chat pipeline to use Graphiti retrieval, and validate on 3 fiction sagas.

**Architecture:** Graphiti handles extraction, entity resolution, temporal storage, and retrieval in a single `add_episode()` call. The SagaProfileInducer analyzes the raw graph after Discovery Mode ingestion, clusters entities, induces saga-specific types via LLM, and generates dynamic Pydantic models injected into Graphiti for Guided Mode. The chat pipeline is simplified from 17 to 8 LangGraph nodes using Graphiti's native search API.

**Tech Stack:** graphiti-core, kg-gen (optional clustering), Neo4j 5.x + GDS plugin, FastAPI, arq, LangGraph, Gemini 2.5 Flash via LiteLLM, BGE-m3 embeddings, PostgreSQL (checkpointing), Redis, Next.js 16.

**Spec:** `docs/superpowers/specs/2026-03-14-kg-v2-sota-assembly-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `backend/app/services/saga_profile/models.py` | SagaProfile, InducedEntityType, InducedRelationType, InducedPattern Pydantic models |
| `backend/app/services/saga_profile/pydantic_generator.py` | `saga_profile_to_graphiti_types()` — dynamic Pydantic model generation |
| `backend/app/services/saga_profile/inducer.py` | SagaProfileInducer — clustering + LLM induction algorithm |
| `backend/app/services/saga_profile/temporal.py` | NarrativeTemporalMapper — chapter ↔ datetime mapping |
| `backend/app/services/saga_profile/__init__.py` | Public exports |
| `backend/app/services/ingestion/graphiti_ingest.py` | Discovery/Guided mode orchestrator |
| `backend/app/services/ingestion/__init__.py` | Public exports |
| `backend/app/core/graphiti_client.py` | GraphitiClient singleton (init, ingest, search, close) |
| `backend/app/agents/chat_v2/graph.py` | New 8-node chat pipeline |
| `backend/app/agents/chat_v2/state.py` | ChatV2State TypedDict |
| `backend/app/agents/chat_v2/nodes/router.py` | Intent router (3 routes) |
| `backend/app/agents/chat_v2/nodes/graphiti_search.py` | Graphiti hybrid search node |
| `backend/app/agents/chat_v2/nodes/cypher_lookup.py` | Typed Cypher query node |
| `backend/app/agents/chat_v2/nodes/context_assembly.py` | Context builder (summaries + chunks) |
| `backend/app/agents/chat_v2/nodes/generate.py` | CoT generation node |
| `backend/app/agents/chat_v2/nodes/faithfulness.py` | NLI check + retry logic |
| `backend/app/agents/chat_v2/__init__.py` | Public exports |
| `backend/app/agents/chat_v2/nodes/__init__.py` | Public exports |
| `backend/tests/test_saga_profile_models.py` | SagaProfile model tests |
| `backend/tests/test_pydantic_generator.py` | Dynamic Pydantic generation tests |
| `backend/tests/test_narrative_temporal_mapper.py` | Temporal mapping tests |
| `backend/tests/test_saga_profile_inducer.py` | Inducer algorithm tests |
| `backend/tests/test_graphiti_client.py` | GraphitiClient tests |
| `backend/tests/test_graphiti_ingest.py` | Discovery/Guided flow tests |
| `backend/tests/test_chat_v2_pipeline.py` | New chat pipeline tests |

### Modified files

| File | Changes |
|---|---|
| `backend/app/main.py` | Add GraphitiClient to lifespan, remove ontology loader |
| `backend/app/workers/tasks.py` | Replace extraction tasks with Graphiti ingestion tasks |
| `backend/app/workers/settings.py` | Update worker context for Graphiti |
| `backend/app/api/routes/books.py` | Update extract endpoint to use Graphiti ingestion |
| `backend/app/api/routes/chat.py` | Switch to ChatV2 service |
| `backend/app/api/routes/graph.py` | Adapt entity search to Graphiti schema |
| `backend/app/api/dependencies.py` | Add `get_graphiti()` dependency |
| `backend/app/services/chat_service.py` | Rewrite to use Graphiti + new chat graph |
| `backend/app/config.py` | Add Graphiti-related settings |
| `docker-compose.prod.yml` | Add GDS plugin to Neo4j, increase memory |
| `pyproject.toml` (or requirements) | Add graphiti-core, kg-gen deps |

### Deleted files (deferred to final cleanup task)

All files in `backend/app/services/extraction/`, `backend/app/agents/chat/`, `backend/app/agents/reader/`, `ontology/*.yaml`, `backend/app/llm/embeddings.py`, `backend/app/core/ontology_loader.py`, `scripts/init_neo4j.cypher`, and corresponding tests.

---

## Chunk 1: Foundation — Models, Temporal Mapper, Dependencies

### Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml` (or `requirements.txt` — check which is used)

- [ ] **Step 1: Check dependency management**

```bash
ls backend/pyproject.toml backend/requirements*.txt 2>/dev/null
```

- [ ] **Step 2: Add graphiti-core and kg-gen**

Add to the project dependencies:
```
graphiti-core>=0.5
kg-gen>=0.1
leidenalg>=0.10
```

- [ ] **Step 3: Install and verify**

```bash
cd backend && pip install graphiti-core kg-gen leidenalg
python -c "from graphiti_core import Graphiti; print('graphiti OK')"
python -c "from kg_gen import KGGen; print('kggen OK')"
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(deps): add graphiti-core, kg-gen, leidenalg for KG v2"
```

---

### Task 2: SagaProfile models

**Files:**
- Create: `backend/app/services/saga_profile/__init__.py`
- Create: `backend/app/services/saga_profile/models.py`
- Test: `backend/tests/test_saga_profile_models.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_saga_profile_models.py
"""Tests for SagaProfile data models."""

from app.services.saga_profile.models import (
    InducedEntityType,
    InducedPattern,
    InducedRelationType,
    SagaProfile,
)


class TestSagaProfileModels:
    def test_create_minimal_profile(self):
        profile = SagaProfile(
            saga_id="test-saga",
            saga_name="Test Saga",
            source_book="book-1",
            entity_types=[],
            relation_types=[],
            text_patterns=[],
            narrative_systems=[],
            estimated_complexity="low",
        )
        assert profile.saga_id == "test-saga"
        assert profile.version == 1

    def test_create_entity_type(self):
        et = InducedEntityType(
            type_name="Spell",
            parent_universal="Concept",
            description="Magical spells cast by wizards",
            instances_found=["Expelliarmus", "Patronus"],
            typical_attributes=["incantation", "effect"],
            confidence=0.9,
        )
        assert et.type_name == "Spell"
        assert len(et.instances_found) == 2

    def test_create_relation_type(self):
        rt = InducedRelationType(
            relation_name="belongs_to_house",
            source_type="Character",
            target_type="House",
            cardinality="1:1",
            temporal=False,
            description="A character's Hogwarts house",
        )
        assert rt.temporal is False
        assert rt.cardinality == "1:1"

    def test_create_pattern(self):
        p = InducedPattern(
            pattern_regex=r"\[Skill Acquired: (.+?)\]",
            extraction_type="skill_acquisition",
            example="[Skill Acquired: Shadow Step]",
            confidence=0.95,
        )
        assert "Skill Acquired" in p.pattern_regex

    def test_full_primal_hunter_profile(self):
        """Integration test: a realistic Primal Hunter SagaProfile."""
        profile = SagaProfile(
            saga_id="primal-hunter",
            saga_name="The Primal Hunter",
            source_book="primal-hunter-book-1",
            entity_types=[
                InducedEntityType(
                    type_name="Skill",
                    parent_universal="Concept",
                    description="Acquired abilities with levels",
                    instances_found=["Shadow Step", "Arcane Powershot"],
                    typical_attributes=["rank", "mana_cost"],
                    confidence=0.95,
                ),
                InducedEntityType(
                    type_name="Class",
                    parent_universal="Concept",
                    description="Progression classes",
                    instances_found=["Alchemist"],
                    typical_attributes=["tier", "requirements"],
                    confidence=0.88,
                ),
            ],
            relation_types=[
                InducedRelationType(
                    relation_name="has_skill",
                    source_type="Character",
                    target_type="Skill",
                    cardinality="N:N",
                    temporal=True,
                    description="Character acquires a skill",
                ),
            ],
            text_patterns=[
                InducedPattern(
                    pattern_regex=r"\[Skill Acquired: (.+?)\]",
                    extraction_type="skill_acquisition",
                    example="[Skill Acquired: Shadow Step]",
                    confidence=0.95,
                ),
            ],
            narrative_systems=["progression", "magic_system"],
            estimated_complexity="high",
        )
        assert len(profile.entity_types) == 2
        assert len(profile.text_patterns) == 1
        assert profile.estimated_complexity == "high"

    def test_profile_serialization_roundtrip(self):
        """JSON serialization and deserialization."""
        profile = SagaProfile(
            saga_id="test",
            saga_name="Test",
            source_book="b1",
            entity_types=[],
            relation_types=[],
            text_patterns=[],
            narrative_systems=[],
            estimated_complexity="low",
        )
        json_str = profile.model_dump_json()
        restored = SagaProfile.model_validate_json(json_str)
        assert restored.saga_id == profile.saga_id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_saga_profile_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.saga_profile'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/saga_profile/__init__.py
"""Saga profile induction for automatic ontology discovery."""

from app.services.saga_profile.models import (
    InducedEntityType,
    InducedPattern,
    InducedRelationType,
    SagaProfile,
)

__all__ = [
    "InducedEntityType",
    "InducedPattern",
    "InducedRelationType",
    "SagaProfile",
]
```

```python
# backend/app/services/saga_profile/models.py
"""SagaProfile data models for induced ontology."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InducedEntityType(BaseModel):
    """An entity type discovered in a saga's universe."""

    type_name: str = Field(..., description="PascalCase type name, e.g. 'Spell', 'House'")
    parent_universal: str = Field(
        ..., description="Universal parent: Character, Location, Object, Organization, Event, Concept"
    )
    description: str = Field(..., description="What this type represents in the saga")
    instances_found: list[str] = Field(default_factory=list, description="Known instances")
    typical_attributes: list[str] = Field(
        default_factory=list, description="Attribute names typical for this type"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Induction confidence score")


class InducedRelationType(BaseModel):
    """A relationship type with cardinality constraints."""

    relation_name: str = Field(..., description="snake_case relation name")
    source_type: str
    target_type: str
    cardinality: str = Field(..., pattern=r"^[1N]:[1N]$")
    temporal: bool = Field(..., description="True if this relation can change over time")
    description: str


class InducedPattern(BaseModel):
    """A recurring textual pattern discovered in the saga."""

    pattern_regex: str = Field(..., description="Python regex pattern")
    extraction_type: str = Field(..., description="What this pattern extracts")
    example: str = Field(..., description="An example match from the text")
    confidence: float = Field(..., ge=0.0, le=1.0)


class SagaProfile(BaseModel):
    """Automatically induced ontology for a fiction saga.

    Generated during Discovery Mode (first book), evolved during Guided Mode
    (subsequent books). Translates to Pydantic entity_types for Graphiti.
    """

    saga_id: str
    saga_name: str
    source_book: str
    version: int = 1

    entity_types: list[InducedEntityType]
    relation_types: list[InducedRelationType]
    text_patterns: list[InducedPattern]

    narrative_systems: list[str] = Field(
        default_factory=list,
        description="Narrative systems detected: magic_system, progression, political, etc.",
    )
    estimated_complexity: str = Field(
        default="medium", description="low, medium, or high"
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_saga_profile_models.py -v
```
Expected: ALL PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/saga_profile/ backend/tests/test_saga_profile_models.py
git commit -m "feat(saga-profile): add SagaProfile data models"
```

---

### Task 3: NarrativeTemporalMapper

**Files:**
- Create: `backend/app/services/saga_profile/temporal.py`
- Test: `backend/tests/test_narrative_temporal_mapper.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_narrative_temporal_mapper.py
"""Tests for chapter ↔ datetime mapping."""

from datetime import datetime

import pytest

from app.services.saga_profile.temporal import NarrativeTemporalMapper


class TestNarrativeTemporalMapper:
    def test_book1_chapter1(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=1)
        assert dt == datetime(2000, 1, 2)  # epoch + 1 day

    def test_book1_chapter42(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=42)
        assert dt.year == 2000
        assert (dt - datetime(2000, 1, 1)).days == 42

    def test_book2_chapter1(self):
        dt = NarrativeTemporalMapper.to_datetime(book_num=2, chapter_num=1)
        delta = (dt - datetime(2000, 1, 1)).days
        assert delta == 10_001  # BOOK_OFFSET_DAYS + 1

    def test_scene_order_encoded_in_seconds(self):
        dt = NarrativeTemporalMapper.to_datetime(1, 5, scene_order=3)
        assert dt.second == 3

    def test_roundtrip(self):
        original = (3, 25, 7)
        dt = NarrativeTemporalMapper.to_datetime(*original)
        restored = NarrativeTemporalMapper.from_datetime(dt)
        assert restored == original

    def test_roundtrip_book1_chapter0(self):
        dt = NarrativeTemporalMapper.to_datetime(1, 0)
        book, chapter, scene = NarrativeTemporalMapper.from_datetime(dt)
        assert (book, chapter, scene) == (1, 0, 0)

    def test_invalid_book_num_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            NarrativeTemporalMapper.to_datetime(book_num=0, chapter_num=1)

    def test_negative_chapter_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            NarrativeTemporalMapper.to_datetime(book_num=1, chapter_num=-1)

    def test_before_epoch_raises(self):
        with pytest.raises(ValueError, match="before epoch"):
            NarrativeTemporalMapper.from_datetime(datetime(1999, 12, 31))

    def test_many_books_no_overflow(self):
        """70-book saga should not overflow."""
        dt = NarrativeTemporalMapper.to_datetime(book_num=70, chapter_num=200)
        book, chapter, _ = NarrativeTemporalMapper.from_datetime(dt)
        assert book == 70
        assert chapter == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_narrative_temporal_mapper.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/saga_profile/temporal.py
"""Narrative temporal mapping: (book, chapter, scene) ↔ datetime for Graphiti."""

from __future__ import annotations

from datetime import datetime, timedelta


class NarrativeTemporalMapper:
    """Maps (book, chapter, scene_order) → datetime for Graphiti's bi-temporal model.

    Each saga uses its own group_id in Graphiti, so datetime values are NOT
    comparable across different sagas. Within a saga, the ordering is:

        book 1 ch 0 < book 1 ch 1 < ... < book 2 ch 0 < book 2 ch 1 < ...

    Scene order (0–86399) is encoded in seconds within the day.
    """

    EPOCH = datetime(2000, 1, 1)
    BOOK_OFFSET_DAYS = 10_000

    @staticmethod
    def to_datetime(book_num: int, chapter_num: int, scene_order: int = 0) -> datetime:
        if book_num < 1 or chapter_num < 0:
            msg = f"Invalid book_num={book_num} or chapter_num={chapter_num}"
            raise ValueError(msg)
        days = (book_num - 1) * NarrativeTemporalMapper.BOOK_OFFSET_DAYS + chapter_num
        return NarrativeTemporalMapper.EPOCH + timedelta(days=days, seconds=scene_order)

    @staticmethod
    def from_datetime(dt: datetime) -> tuple[int, int, int]:
        delta = dt - NarrativeTemporalMapper.EPOCH
        if delta.days < 0:
            msg = f"Datetime {dt} is before epoch {NarrativeTemporalMapper.EPOCH}"
            raise ValueError(msg)
        book = delta.days // NarrativeTemporalMapper.BOOK_OFFSET_DAYS + 1
        chapter = delta.days % NarrativeTemporalMapper.BOOK_OFFSET_DAYS
        scene = delta.seconds
        return book, chapter, scene
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_narrative_temporal_mapper.py -v
```
Expected: ALL PASS (10 tests)

- [ ] **Step 5: Update `__init__.py` exports and commit**

Add to `backend/app/services/saga_profile/__init__.py`:
```python
from app.services.saga_profile.temporal import NarrativeTemporalMapper
# add to __all__
```

```bash
git add backend/app/services/saga_profile/ backend/tests/test_narrative_temporal_mapper.py
git commit -m "feat(saga-profile): add NarrativeTemporalMapper"
```

---

### Task 4: Pydantic generator (SagaProfile → Graphiti entity_types)

**Files:**
- Create: `backend/app/services/saga_profile/pydantic_generator.py`
- Test: `backend/tests/test_pydantic_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pydantic_generator.py
"""Tests for dynamic Pydantic model generation from SagaProfile."""

from pydantic import BaseModel

from app.services.saga_profile.models import (
    InducedEntityType,
    InducedRelationType,
    SagaProfile,
)
from app.services.saga_profile.pydantic_generator import (
    saga_profile_to_graphiti_edges,
    saga_profile_to_graphiti_types,
)


def _make_profile(*entity_types, relation_types=None) -> SagaProfile:
    return SagaProfile(
        saga_id="test",
        saga_name="Test",
        source_book="b1",
        entity_types=list(entity_types),
        relation_types=relation_types or [],
        text_patterns=[],
        narrative_systems=[],
        estimated_complexity="low",
    )


class TestPydanticGenerator:
    def test_universal_types_always_present(self):
        profile = _make_profile()
        types = saga_profile_to_graphiti_types(profile)
        assert "Character" in types
        assert "Location" in types
        assert "Concept" in types
        assert len(types) == 6  # 6 universal types

    def test_induced_type_added(self):
        et = InducedEntityType(
            type_name="Spell",
            parent_universal="Concept",
            description="Magical spells",
            instances_found=["Patronus"],
            typical_attributes=["incantation", "effect"],
            confidence=0.9,
        )
        types = saga_profile_to_graphiti_types(_make_profile(et))
        assert "Spell" in types
        assert len(types) == 7  # 6 universal + 1 induced

    def test_induced_type_is_valid_pydantic(self):
        et = InducedEntityType(
            type_name="Skill",
            parent_universal="Concept",
            description="Abilities",
            instances_found=[],
            typical_attributes=["rank", "mana_cost"],
            confidence=0.9,
        )
        types = saga_profile_to_graphiti_types(_make_profile(et))
        SkillModel = types["Skill"]
        assert issubclass(SkillModel, BaseModel)
        # Should be able to instantiate with optional fields
        instance = SkillModel()
        assert instance.rank is None
        assert instance.mana_cost is None

    def test_edge_types_generated(self):
        rt = InducedRelationType(
            relation_name="has_skill",
            source_type="Character",
            target_type="Skill",
            cardinality="N:N",
            temporal=True,
            description="Character has skill",
        )
        edge_types, edge_map = saga_profile_to_graphiti_edges(
            _make_profile(relation_types=[rt])
        )
        assert "has_skill" in edge_types
        assert ("Character", "Skill") in edge_map
        assert "has_skill" in edge_map[("Character", "Skill")]

    def test_multiple_edges_same_pair(self):
        rt1 = InducedRelationType(
            relation_name="has_skill",
            source_type="Character",
            target_type="Skill",
            cardinality="N:N",
            temporal=True,
            description="Owns skill",
        )
        rt2 = InducedRelationType(
            relation_name="lost_skill",
            source_type="Character",
            target_type="Skill",
            cardinality="N:N",
            temporal=True,
            description="Lost skill",
        )
        _, edge_map = saga_profile_to_graphiti_edges(
            _make_profile(relation_types=[rt1, rt2])
        )
        assert len(edge_map[("Character", "Skill")]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_pydantic_generator.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/saga_profile/pydantic_generator.py
"""Generate dynamic Pydantic models from SagaProfile for Graphiti entity_types."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, create_model

from app.services.saga_profile.models import SagaProfile


# --- Universal entity types (always present) ---

class Character(BaseModel):
    aliases: list[str] = Field(default_factory=list)
    role: str | None = None
    status: str | None = None


class Location(BaseModel):
    location_type: str | None = None
    parent_location: str | None = None


class Object(BaseModel):
    object_type: str | None = None


class Organization(BaseModel):
    org_type: str | None = None


class Event(BaseModel):
    event_type: str | None = None
    significance: str | None = None


class Concept(BaseModel):
    concept_type: str | None = None


_UNIVERSAL_TYPES: dict[str, type[BaseModel]] = {
    "Character": Character,
    "Location": Location,
    "Object": Object,
    "Organization": Organization,
    "Event": Event,
    "Concept": Concept,
}


def saga_profile_to_graphiti_types(
    profile: SagaProfile,
) -> dict[str, type[BaseModel]]:
    """Convert a SagaProfile into a dict of Pydantic models for Graphiti.

    Returns universal types + dynamically generated induced types.
    """
    types: dict[str, type[BaseModel]] = dict(_UNIVERSAL_TYPES)

    for induced in profile.entity_types:
        field_definitions: dict[str, Any] = {}
        for attr in induced.typical_attributes:
            field_definitions[attr] = (
                str | None,
                Field(None, description=f"{attr} of {induced.type_name}"),
            )
        model = create_model(induced.type_name, **field_definitions)
        types[induced.type_name] = model

    return types


def saga_profile_to_graphiti_edges(
    profile: SagaProfile,
) -> tuple[dict[str, type[BaseModel]], dict[tuple[str, str], list[str]]]:
    """Convert induced relation types into Graphiti edge_types + edge_type_map."""
    edge_types: dict[str, type[BaseModel]] = {}
    edge_type_map: dict[tuple[str, str], list[str]] = {}

    for rel in profile.relation_types:
        edge_model = create_model(
            rel.relation_name,
            temporal=(bool, Field(default=rel.temporal)),
        )
        edge_types[rel.relation_name] = edge_model
        key = (rel.source_type, rel.target_type)
        edge_type_map.setdefault(key, []).append(rel.relation_name)

    return edge_types, edge_type_map
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_pydantic_generator.py -v
```
Expected: ALL PASS (5 tests)

- [ ] **Step 5: Update `__init__.py` and commit**

```bash
git add backend/app/services/saga_profile/ backend/tests/test_pydantic_generator.py
git commit -m "feat(saga-profile): add Pydantic generator for Graphiti entity_types"
```

---

## Chunk 2: GraphitiClient + Ingestion Orchestrator

### Task 5: GraphitiClient

**Files:**
- Create: `backend/app/core/graphiti_client.py`
- Test: `backend/tests/test_graphiti_client.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_graphiti_client.py
"""Tests for GraphitiClient wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.graphiti_client import GraphitiClient


@pytest.fixture
def mock_graphiti():
    with patch("app.core.graphiti_client.Graphiti") as MockGraphiti:
        instance = AsyncMock()
        MockGraphiti.return_value = instance
        yield instance


class TestGraphitiClient:
    def test_init(self, mock_graphiti):
        client = GraphitiClient(
            neo4j_uri="bolt://localhost:7687",
            neo4j_auth=("neo4j", "password"),
        )
        assert client.client is not None

    @pytest.mark.asyncio
    async def test_init_schema(self, mock_graphiti):
        client = GraphitiClient(
            neo4j_uri="bolt://localhost:7687",
            neo4j_auth=("neo4j", "password"),
        )
        await client.init_schema()
        mock_graphiti.build_indices_and_constraints.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_delegates(self, mock_graphiti):
        mock_graphiti.search.return_value = []
        client = GraphitiClient(
            neo4j_uri="bolt://localhost:7687",
            neo4j_auth=("neo4j", "password"),
        )
        results = await client.search("who is Jake?", saga_id="test-saga")
        mock_graphiti.search.assert_awaited_once()
        assert results == []

    @pytest.mark.asyncio
    async def test_close(self, mock_graphiti):
        client = GraphitiClient(
            neo4j_uri="bolt://localhost:7687",
            neo4j_auth=("neo4j", "password"),
        )
        await client.close()
        mock_graphiti.close.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_graphiti_client.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/core/graphiti_client.py
"""Graphiti client singleton for WorldRAG."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

from app.core.logging import get_logger
from app.services.saga_profile.temporal import NarrativeTemporalMapper

if TYPE_CHECKING:
    from graphiti_core.edges import EntityEdge

logger = get_logger(__name__)


class GraphitiClient:
    """Thin wrapper around Graphiti — initialized once in FastAPI lifespan."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_auth: tuple[str, str],
        llm_client: Any | None = None,
        embedder: Any | None = None,
    ) -> None:
        self.client = Graphiti(
            uri=neo4j_uri,
            user=neo4j_auth[0],
            password=neo4j_auth[1],
            llm_client=llm_client,
            embedder=embedder,
        )

    async def init_schema(self) -> None:
        """Build Graphiti indexes and constraints in Neo4j."""
        await self.client.build_indices_and_constraints()
        logger.info("graphiti_schema_initialized")

    async def ingest_chapter(
        self,
        chapter_text: str,
        book_id: str,
        book_num: int,
        chapter_num: int,
        saga_id: str,
        entity_types: dict[str, Any] | None = None,
        edge_types: dict[str, Any] | None = None,
        edge_type_map: dict[tuple[str, str], list[str]] | None = None,
    ) -> None:
        """Ingest a single chapter as a Graphiti episode."""
        reference_time = NarrativeTemporalMapper.to_datetime(book_num, chapter_num)
        await self.client.add_episode(
            name=f"{book_id}:ch{chapter_num}",
            episode_body=chapter_text,
            source=EpisodeType.text,
            reference_time=reference_time,
            source_description=f"Chapter {chapter_num} of {book_id}",
            group_id=saga_id,
            entity_types=entity_types,
            edge_types=edge_types,
            edge_type_map=edge_type_map,
        )

    async def search(
        self,
        query: str,
        saga_id: str,
        num_results: int = 20,
    ) -> list[EntityEdge]:
        """Hybrid search (semantic + BM25 + BFS)."""
        return await self.client.search(
            query=query,
            group_ids=[saga_id],
            num_results=num_results,
        )

    async def close(self) -> None:
        """Close Graphiti and underlying connections."""
        await self.client.close()
        logger.info("graphiti_closed")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_graphiti_client.py -v
```
Expected: ALL PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/graphiti_client.py backend/tests/test_graphiti_client.py
git commit -m "feat(graphiti): add GraphitiClient wrapper"
```

---

### Task 6: Ingestion orchestrator (Discovery + Guided modes)

**Files:**
- Create: `backend/app/services/ingestion/__init__.py`
- Create: `backend/app/services/ingestion/graphiti_ingest.py`
- Test: `backend/tests/test_graphiti_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_graphiti_ingest.py
"""Tests for the Graphiti ingestion orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.saga_profile.models import InducedEntityType, SagaProfile
from app.services.ingestion.graphiti_ingest import BookIngestionOrchestrator


def _make_profile() -> SagaProfile:
    return SagaProfile(
        saga_id="test-saga",
        saga_name="Test Saga",
        source_book="book-1",
        entity_types=[
            InducedEntityType(
                type_name="Spell",
                parent_universal="Concept",
                description="Magic",
                instances_found=["Patronus"],
                typical_attributes=["incantation"],
                confidence=0.9,
            ),
        ],
        relation_types=[],
        text_patterns=[],
        narrative_systems=["magic_system"],
        estimated_complexity="medium",
    )


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.ingest_chapter = AsyncMock()
    return client


class TestBookIngestionOrchestrator:
    @pytest.mark.asyncio
    async def test_discovery_mode_uses_universal_types(self, mock_client):
        orch = BookIngestionOrchestrator(graphiti=mock_client)
        chapters = [{"number": 1, "text": "Jake found a sword."}]
        await orch.ingest_discovery(
            chapters=chapters,
            book_id="book-1",
            book_num=1,
            saga_id="test-saga",
        )
        mock_client.ingest_chapter.assert_awaited_once()
        call_kwargs = mock_client.ingest_chapter.call_args.kwargs
        assert "Character" in call_kwargs["entity_types"]
        assert "Spell" not in call_kwargs["entity_types"]

    @pytest.mark.asyncio
    async def test_guided_mode_uses_induced_types(self, mock_client):
        orch = BookIngestionOrchestrator(graphiti=mock_client)
        profile = _make_profile()
        chapters = [{"number": 1, "text": "Jake cast Patronus."}]
        await orch.ingest_guided(
            chapters=chapters,
            book_id="book-2",
            book_num=2,
            saga_id="test-saga",
            profile=profile,
        )
        mock_client.ingest_chapter.assert_awaited_once()
        call_kwargs = mock_client.ingest_chapter.call_args.kwargs
        assert "Spell" in call_kwargs["entity_types"]
        assert "Character" in call_kwargs["entity_types"]

    @pytest.mark.asyncio
    async def test_multiple_chapters_ingested_sequentially(self, mock_client):
        orch = BookIngestionOrchestrator(graphiti=mock_client)
        chapters = [
            {"number": 1, "text": "Chapter one."},
            {"number": 2, "text": "Chapter two."},
            {"number": 3, "text": "Chapter three."},
        ]
        await orch.ingest_discovery(
            chapters=chapters, book_id="b1", book_num=1, saga_id="s1"
        )
        assert mock_client.ingest_chapter.await_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_graphiti_ingest.py -v
```
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/ingestion/__init__.py
"""Book ingestion via Graphiti."""

from app.services.ingestion.graphiti_ingest import BookIngestionOrchestrator

__all__ = ["BookIngestionOrchestrator"]
```

```python
# backend/app/services/ingestion/graphiti_ingest.py
"""Orchestrate Discovery / Guided ingestion via Graphiti."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.services.saga_profile.pydantic_generator import (
    saga_profile_to_graphiti_edges,
    saga_profile_to_graphiti_types,
)

if TYPE_CHECKING:
    from app.core.graphiti_client import GraphitiClient
    from app.services.saga_profile.models import SagaProfile

logger = get_logger(__name__)

# Universal types — always present in every saga
_UNIVERSAL_ONLY: dict[str, Any] | None = None  # lazy-loaded


def _get_universal_types() -> dict[str, Any]:
    global _UNIVERSAL_ONLY
    if _UNIVERSAL_ONLY is None:
        from app.services.saga_profile.pydantic_generator import _UNIVERSAL_TYPES

        _UNIVERSAL_ONLY = dict(_UNIVERSAL_TYPES)
    return _UNIVERSAL_ONLY


class BookIngestionOrchestrator:
    """Orchestrates Graphiti ingestion for a book."""

    def __init__(self, graphiti: GraphitiClient) -> None:
        self.graphiti = graphiti

    async def ingest_discovery(
        self,
        chapters: list[dict[str, Any]],
        book_id: str,
        book_num: int,
        saga_id: str,
    ) -> None:
        """Discovery Mode: ingest with universal types only."""
        entity_types = _get_universal_types()
        logger.info(
            "ingestion_discovery_start",
            book_id=book_id,
            chapters=len(chapters),
            types=list(entity_types.keys()),
        )
        for ch in chapters:
            await self.graphiti.ingest_chapter(
                chapter_text=ch["text"],
                book_id=book_id,
                book_num=book_num,
                chapter_num=ch["number"],
                saga_id=saga_id,
                entity_types=entity_types,
            )
            logger.info("chapter_ingested", book_id=book_id, chapter=ch["number"])

    async def ingest_guided(
        self,
        chapters: list[dict[str, Any]],
        book_id: str,
        book_num: int,
        saga_id: str,
        profile: SagaProfile,
    ) -> None:
        """Guided Mode: ingest with universal + induced types."""
        entity_types = saga_profile_to_graphiti_types(profile)
        edge_types, edge_type_map = saga_profile_to_graphiti_edges(profile)
        logger.info(
            "ingestion_guided_start",
            book_id=book_id,
            chapters=len(chapters),
            types=list(entity_types.keys()),
            edge_types=list(edge_types.keys()),
        )
        for ch in chapters:
            await self.graphiti.ingest_chapter(
                chapter_text=ch["text"],
                book_id=book_id,
                book_num=book_num,
                chapter_num=ch["number"],
                saga_id=saga_id,
                entity_types=entity_types,
                edge_types=edge_types,
                edge_type_map=edge_type_map,
            )
            logger.info("chapter_ingested", book_id=book_id, chapter=ch["number"])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_graphiti_ingest.py -v
```
Expected: ALL PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ingestion/ backend/tests/test_graphiti_ingest.py
git commit -m "feat(ingestion): add Graphiti ingestion orchestrator"
```

---

## Chunk 3: SagaProfileInducer

### Task 7: SagaProfileInducer core algorithm

**Files:**
- Create: `backend/app/services/saga_profile/inducer.py`
- Test: `backend/tests/test_saga_profile_inducer.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_saga_profile_inducer.py
"""Tests for the SagaProfileInducer."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.saga_profile.inducer import SagaProfileInducer
from app.services.saga_profile.models import SagaProfile


@pytest.fixture
def mock_neo4j_driver():
    driver = AsyncMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
    driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return driver, session


class TestSagaProfileInducer:
    @pytest.mark.asyncio
    async def test_inducer_returns_saga_profile(self, mock_neo4j_driver):
        driver, session = mock_neo4j_driver
        # Mock: entities returned from Neo4j
        entities = [
            {"name": "Expelliarmus", "summary": "A disarming spell", "labels": ["Entity", "Concept"]},
            {"name": "Patronus", "summary": "A protection spell", "labels": ["Entity", "Concept"]},
            {"name": "Lumos", "summary": "A light spell", "labels": ["Entity", "Concept"]},
            {"name": "Harry", "summary": "The chosen one", "labels": ["Entity", "Character"]},
            {"name": "Hogwarts", "summary": "A school of magic", "labels": ["Entity", "Location"]},
        ]
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=entities)
        session.run = AsyncMock(return_value=result_mock)

        with patch(
            "app.services.saga_profile.inducer._cluster_entities"
        ) as mock_cluster, patch(
            "app.services.saga_profile.inducer._formalize_clusters_llm"
        ) as mock_formalize:
            mock_cluster.return_value = [
                {"names": ["Expelliarmus", "Patronus", "Lumos"], "label_hint": "Concept"},
            ]
            mock_formalize.return_value = [
                {
                    "type_name": "Spell",
                    "parent_universal": "Concept",
                    "description": "Magical spells",
                    "instances_found": ["Expelliarmus", "Patronus", "Lumos"],
                    "typical_attributes": ["incantation", "effect"],
                    "confidence": 0.92,
                }
            ]

            inducer = SagaProfileInducer(driver=driver)
            profile = await inducer.induce(
                saga_id="harry-potter",
                saga_name="Harry Potter",
                source_book="hp-book-1",
                raw_text="",  # not used when mocking
            )

        assert isinstance(profile, SagaProfile)
        assert profile.saga_id == "harry-potter"
        assert len(profile.entity_types) >= 1
        assert profile.entity_types[0].type_name == "Spell"

    @pytest.mark.asyncio
    async def test_low_confidence_types_filtered(self, mock_neo4j_driver):
        driver, session = mock_neo4j_driver
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[])
        session.run = AsyncMock(return_value=result_mock)

        with patch(
            "app.services.saga_profile.inducer._cluster_entities"
        ) as mock_cluster, patch(
            "app.services.saga_profile.inducer._formalize_clusters_llm"
        ) as mock_formalize:
            mock_cluster.return_value = [
                {"names": ["X", "Y", "Z"], "label_hint": "Concept"},
            ]
            mock_formalize.return_value = [
                {
                    "type_name": "Dubious",
                    "parent_universal": "Concept",
                    "description": "Unclear",
                    "instances_found": ["X", "Y", "Z"],
                    "typical_attributes": [],
                    "confidence": 0.3,  # below threshold
                }
            ]

            inducer = SagaProfileInducer(driver=driver)
            profile = await inducer.induce(
                saga_id="test", saga_name="Test", source_book="b1", raw_text=""
            )

        assert len(profile.entity_types) == 0  # filtered out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_saga_profile_inducer.py -v
```
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/saga_profile/inducer.py
"""SagaProfileInducer — automatic ontology induction for fiction sagas."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.services.saga_profile.models import (
    InducedEntityType,
    InducedPattern,
    InducedRelationType,
    SagaProfile,
)

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)

# Minimum cluster size to consider for type induction
MIN_CLUSTER_SIZE = 3
# Minimum confidence to include an induced type
MIN_CONFIDENCE = 0.6


def _cluster_entities(
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cluster entities by semantic similarity.

    Uses simple label-based grouping as baseline. For production,
    replace with embedding-based agglomerative clustering (BGE-m3).

    Returns list of {names: [...], label_hint: str} dicts.
    """
    # Group by Graphiti-assigned label (excluding "Entity" base label)
    groups: dict[str, list[str]] = {}
    for ent in entities:
        labels = [l for l in ent.get("labels", []) if l != "Entity"]
        label = labels[0] if labels else "Unknown"
        groups.setdefault(label, []).append(ent["name"])

    clusters = []
    for label, names in groups.items():
        if len(names) >= MIN_CLUSTER_SIZE:
            clusters.append({"names": names, "label_hint": label})

    return clusters


async def _formalize_clusters_llm(
    clusters: list[dict[str, Any]],
    entities_by_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Use LLM to formalize clusters into induced entity types.

    Each cluster of ≥3 entities with summaries is sent to the LLM
    to propose a type name, description, attributes, and relations.

    TODO: Wire to actual LLM (Gemini Flash via LiteLLM).
    For now, returns structured proposals based on cluster data.
    """
    from app.config import settings
    from app.llm.providers import get_llm

    proposals = []
    for cluster in clusters:
        names = cluster["names"]
        label_hint = cluster["label_hint"]

        summaries = []
        for name in names[:10]:  # limit to 10 for prompt size
            ent = entities_by_name.get(name, {})
            summary = ent.get("summary", "")
            if summary:
                summaries.append(f"- {name}: {summary}")

        summaries_text = "\n".join(summaries) if summaries else "(no summaries)"

        prompt = f"""You are analyzing entities extracted from a fiction novel.
These {len(names)} entities were grouped together by semantic similarity.
They are currently labeled as "{label_hint}" but may represent a more specific type.

Entities:
{summaries_text}

All entity names: {', '.join(names[:20])}

Based on these entities, propose:
1. A specific type name (PascalCase, e.g. "Spell", "House", "Bloodline")
2. A description of what this type represents
3. Typical attributes (list of attribute names)
4. Your confidence (0.0 to 1.0) that these entities form a coherent type

Respond in JSON:
{{"type_name": "...", "description": "...", "typical_attributes": ["..."], "confidence": 0.0}}"""

        try:
            llm = get_llm(settings.llm_generation)
            response = await llm.ainvoke(prompt)
            # Parse JSON from response
            import json

            content = response.content if hasattr(response, "content") else str(response)
            # Extract JSON from potential markdown code blocks
            json_match = re.search(r"\{[^}]+\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                proposals.append(
                    {
                        "type_name": data.get("type_name", label_hint),
                        "parent_universal": label_hint,
                        "description": data.get("description", ""),
                        "instances_found": names,
                        "typical_attributes": data.get("typical_attributes", []),
                        "confidence": float(data.get("confidence", 0.5)),
                    }
                )
        except Exception:
            logger.warning("saga_profile_llm_formalize_failed", cluster_label=label_hint)
            # Fallback: use cluster as-is
            proposals.append(
                {
                    "type_name": label_hint,
                    "parent_universal": label_hint,
                    "description": f"Auto-detected {label_hint} type",
                    "instances_found": names,
                    "typical_attributes": [],
                    "confidence": 0.5,
                }
            )

    return proposals


def _detect_patterns(raw_text: str) -> list[InducedPattern]:
    """Detect recurring structural patterns in the text (blue boxes, etc.)."""
    patterns_found: list[InducedPattern] = []

    # Common LitRPG patterns
    candidates = [
        (r"\[Skill Acquired: (.+?)\]", "skill_acquisition"),
        (r"\[Level (\d+) → (\d+)\]", "level_up"),
        (r"\[Level Up!\s*.*?→\s*(\d+)\]", "level_up"),
        (r"\[Quest Complete: (.+?)\]", "quest_complete"),
        (r"\[Title Earned: (.+?)\]", "title_earned"),
        (r"\[Class Obtained: (.+?)\]", "class_obtained"),
        (r"\[Achievement Unlocked: (.+?)\]", "achievement"),
        (r"\[(.+?) has evolved into (.+?)\]", "evolution"),
    ]

    for regex, extraction_type in candidates:
        matches = re.findall(regex, raw_text)
        if len(matches) >= 2:  # at least 2 occurrences
            example = re.search(regex, raw_text)
            patterns_found.append(
                InducedPattern(
                    pattern_regex=regex,
                    extraction_type=extraction_type,
                    example=example.group(0) if example else "",
                    confidence=min(1.0, len(matches) / 5),  # scale by frequency
                )
            )

    return patterns_found


class SagaProfileInducer:
    """Induces a SagaProfile from a Graphiti graph after Discovery Mode ingestion."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def induce(
        self,
        saga_id: str,
        saga_name: str,
        source_book: str,
        raw_text: str,
    ) -> SagaProfile:
        """Run the full induction algorithm.

        1. Fetch entities from Neo4j (Graphiti nodes)
        2. Cluster by semantic similarity
        3. Formalize clusters via LLM → InducedEntityType
        4. Detect text patterns → InducedPattern
        5. Assemble and filter → SagaProfile
        """
        # Step 1: Fetch entities
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Entity {group_id: $saga_id})
                RETURN n.name AS name, n.summary AS summary, labels(n) AS labels
                """,
                saga_id=saga_id,
            )
            entities = await result.data()

        logger.info("saga_inducer_entities_fetched", count=len(entities))

        entities_by_name = {e["name"]: e for e in entities}

        # Step 2: Cluster
        clusters = _cluster_entities(entities)
        logger.info("saga_inducer_clusters_found", count=len(clusters))

        # Step 3: Formalize via LLM
        proposals = await _formalize_clusters_llm(clusters, entities_by_name)

        # Step 4: Detect patterns
        patterns = _detect_patterns(raw_text)
        logger.info("saga_inducer_patterns_found", count=len(patterns))

        # Step 5: Assemble, filter by confidence
        entity_types = [
            InducedEntityType(**p)
            for p in proposals
            if p.get("confidence", 0) >= MIN_CONFIDENCE
        ]

        # Detect narrative systems from entity types
        narrative_systems = []
        type_names_lower = {et.type_name.lower() for et in entity_types}
        if type_names_lower & {"spell", "magicsystem", "manatype"}:
            narrative_systems.append("magic_system")
        if type_names_lower & {"skill", "class", "level", "stat"}:
            narrative_systems.append("progression")
        if type_names_lower & {"faction", "house", "kingdom", "guild"}:
            narrative_systems.append("political")

        complexity = "low"
        if len(entity_types) >= 5:
            complexity = "high"
        elif len(entity_types) >= 2:
            complexity = "medium"

        profile = SagaProfile(
            saga_id=saga_id,
            saga_name=saga_name,
            source_book=source_book,
            entity_types=entity_types,
            relation_types=[],  # TODO: induce relations in v2
            text_patterns=patterns,
            narrative_systems=narrative_systems,
            estimated_complexity=complexity,
        )

        logger.info(
            "saga_profile_induced",
            saga_id=saga_id,
            entity_types=len(entity_types),
            patterns=len(patterns),
            complexity=complexity,
        )

        return profile
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_saga_profile_inducer.py -v
```
Expected: ALL PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/saga_profile/inducer.py backend/tests/test_saga_profile_inducer.py
git commit -m "feat(saga-profile): add SagaProfileInducer algorithm"
```

---

## Chunk 4: Chat Pipeline v2

### Task 8: ChatV2 state and graph structure

**Files:**
- Create: `backend/app/agents/chat_v2/__init__.py`
- Create: `backend/app/agents/chat_v2/state.py`
- Create: `backend/app/agents/chat_v2/nodes/__init__.py`
- Create: `backend/app/agents/chat_v2/graph.py`
- Test: `backend/tests/test_chat_v2_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_chat_v2_pipeline.py
"""Tests for the v2 chat pipeline (Graphiti-based)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.chat_v2.graph import build_chat_v2_graph
from app.agents.chat_v2.state import ChatV2State


class TestChatV2State:
    def test_state_has_required_fields(self):
        state = ChatV2State(
            messages=[],
            query="who is Jake?",
            book_id="book-1",
            saga_id="primal-hunter",
            route="graphiti_search",
            retrieved_context=[],
            generation="",
            faithfulness_score=0.0,
            retries=0,
        )
        assert state["query"] == "who is Jake?"
        assert state["route"] == "graphiti_search"


class TestChatV2Graph:
    def test_graph_builds(self):
        mock_graphiti = AsyncMock()
        mock_driver = AsyncMock()
        graph = build_chat_v2_graph(graphiti=mock_graphiti, neo4j_driver=mock_driver)
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        mock_graphiti = AsyncMock()
        mock_driver = AsyncMock()
        graph = build_chat_v2_graph(graphiti=mock_graphiti, neo4j_driver=mock_driver)
        node_names = set(graph.nodes)
        assert "router" in node_names
        assert "graphiti_search" in node_names
        assert "cypher_lookup" in node_names
        assert "context_assembly" in node_names
        assert "generate" in node_names
        assert "faithfulness" in node_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_chat_v2_pipeline.py -v
```
Expected: FAIL

- [ ] **Step 3: Write ChatV2State**

```python
# backend/app/agents/chat_v2/state.py
"""State schema for the v2 chat pipeline."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class ChatV2State(TypedDict, total=False):
    """LangGraph state for the Graphiti-based chat pipeline."""

    messages: list[BaseMessage]
    query: str
    original_query: str
    book_id: str
    saga_id: str
    max_chapter: int | None

    # Router
    route: str  # "graphiti_search" | "cypher_lookup" | "direct"

    # Retrieval
    retrieved_context: list[dict[str, Any]]  # edges/nodes from Graphiti or Cypher
    entity_summaries: list[dict[str, Any]]
    community_summaries: list[str]

    # Generation
    generation: str
    generation_output: dict[str, Any]
    reasoning: str

    # Faithfulness
    faithfulness_score: float
    retries: int
```

- [ ] **Step 4: Write the graph builder and node stubs**

```python
# backend/app/agents/chat_v2/__init__.py
"""Chat v2 pipeline — Graphiti-based retrieval."""

from app.agents.chat_v2.graph import build_chat_v2_graph

__all__ = ["build_chat_v2_graph"]
```

```python
# backend/app/agents/chat_v2/nodes/__init__.py
"""Chat v2 pipeline nodes."""
```

```python
# backend/app/agents/chat_v2/graph.py
"""Build the v2 chat LangGraph (8 nodes, Graphiti-based retrieval)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from app.agents.chat_v2.state import ChatV2State
from app.core.logging import get_logger

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from app.core.graphiti_client import GraphitiClient

logger = get_logger(__name__)

MAX_RETRIES = 2


def _route_after_router(state: dict[str, Any]) -> str:
    return state.get("route", "graphiti_search")


def _route_after_faithfulness(state: dict[str, Any]) -> str:
    score = state.get("faithfulness_score", 0.0)
    retries = state.get("retries", 0)
    if score >= 0.6 or retries >= MAX_RETRIES:
        return END
    return "graphiti_search"  # retry


def build_chat_v2_graph(
    graphiti: GraphitiClient,
    neo4j_driver: AsyncDriver,
) -> StateGraph:
    """Build and return the v2 chat StateGraph (not compiled)."""

    async def router_node(state: ChatV2State) -> dict[str, Any]:
        """Classify intent into 3 routes."""
        query = state.get("query", "")
        # Simple heuristic router — replace with LLM router later
        q_lower = query.lower()
        if any(kw in q_lower for kw in ["list", "what skills", "what class", "at chapter"]):
            return {"route": "cypher_lookup"}
        if any(kw in q_lower for kw in ["hello", "hi", "thanks", "thank you"]):
            return {"route": "direct"}
        return {"route": "graphiti_search"}

    async def graphiti_search_node(state: ChatV2State) -> dict[str, Any]:
        """Hybrid search via Graphiti API."""
        query = state.get("query", "")
        saga_id = state.get("saga_id", "")
        results = await graphiti.search(query, saga_id=saga_id)
        context = [
            {"fact": str(edge.fact) if hasattr(edge, "fact") else str(edge), "source": "graphiti"}
            for edge in results
        ]
        return {"retrieved_context": context}

    async def cypher_lookup_node(state: ChatV2State) -> dict[str, Any]:
        """Structured Cypher query on typed Graphiti nodes."""
        query = state.get("query", "")
        saga_id = state.get("saga_id", "")
        # Basic Cypher lookup — match entities by name
        async with neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Entity {group_id: $saga_id})
                WHERE toLower(n.name) CONTAINS toLower($query_hint)
                RETURN n.name AS name, n.summary AS summary, labels(n) AS labels
                LIMIT 10
                """,
                saga_id=saga_id,
                query_hint=query.split()[-1] if query.split() else "",
            )
            rows = await result.data()
        context = [{"fact": f"{r['name']}: {r.get('summary', '')}", "source": "cypher"} for r in rows]
        return {"retrieved_context": context}

    async def direct_node(state: ChatV2State) -> dict[str, Any]:
        """No retrieval — conversational response."""
        return {"retrieved_context": []}

    async def context_assembly_node(state: ChatV2State) -> dict[str, Any]:
        """Assemble context from retrieved results + entity summaries."""
        context = state.get("retrieved_context", [])
        context_text = "\n".join(c.get("fact", "") for c in context[:10])
        return {"generation_output": {"context": context_text}}

    async def generate_node(state: ChatV2State) -> dict[str, Any]:
        """Generate answer with CoT reasoning."""
        from app.config import settings
        from app.llm.providers import get_llm

        query = state.get("query", "")
        context = state.get("generation_output", {}).get("context", "")

        prompt = f"""Answer the following question about a fiction novel based on the context provided.
Think step by step before answering.

Context:
{context}

Question: {query}

Answer:"""

        llm = get_llm(settings.llm_chat)
        response = await llm.ainvoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
        return {"generation": answer}

    async def faithfulness_node(state: ChatV2State) -> dict[str, Any]:
        """NLI faithfulness check."""
        # Simplified: score based on context availability
        context = state.get("retrieved_context", [])
        generation = state.get("generation", "")
        retries = state.get("retries", 0)

        if not context and state.get("route") != "direct":
            return {"faithfulness_score": 0.3, "retries": retries + 1}

        # TODO: wire DeBERTa NLI model for real faithfulness check
        return {"faithfulness_score": 0.8, "retries": retries}

    # Build graph
    graph = StateGraph(ChatV2State)

    graph.add_node("router", router_node)
    graph.add_node("graphiti_search", graphiti_search_node)
    graph.add_node("cypher_lookup", cypher_lookup_node)
    graph.add_node("direct", direct_node)
    graph.add_node("context_assembly", context_assembly_node)
    graph.add_node("generate", generate_node)
    graph.add_node("faithfulness", faithfulness_node)

    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "graphiti_search": "graphiti_search",
            "cypher_lookup": "cypher_lookup",
            "direct": "direct",
        },
    )
    graph.add_edge("graphiti_search", "context_assembly")
    graph.add_edge("cypher_lookup", "context_assembly")
    graph.add_edge("direct", "context_assembly")
    graph.add_edge("context_assembly", "generate")
    graph.add_edge("generate", "faithfulness")
    graph.add_conditional_edges(
        "faithfulness",
        _route_after_faithfulness,
        {
            END: END,
            "graphiti_search": "graphiti_search",
        },
    )

    return graph
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_chat_v2_pipeline.py -v
```
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/chat_v2/ backend/tests/test_chat_v2_pipeline.py
git commit -m "feat(chat-v2): add Graphiti-based chat pipeline (8 nodes)"
```

---

## Chunk 5: Wiring — FastAPI Lifespan, Workers, API Routes

### Task 9: Add Graphiti to FastAPI lifespan

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/dependencies.py`

- [ ] **Step 1: Add config fields**

Add to `backend/app/config.py` Settings class:
```python
# Graphiti
graphiti_enabled: bool = Field(default=False, description="Enable Graphiti KG v2 pipeline")
```

- [ ] **Step 2: Add `get_graphiti` dependency**

Add to `backend/app/api/dependencies.py`:
```python
async def get_graphiti(request: Request):
    """Get GraphitiClient from app state."""
    client = getattr(request.app.state, "graphiti", None)
    if client is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Graphiti not available")
    return client
```

- [ ] **Step 3: Add Graphiti init to lifespan**

In `backend/app/main.py`, after the PostgreSQL section, add:
```python
# --- Graphiti (KG v2) ---
graphiti = None
if settings.graphiti_enabled:
    from app.core.graphiti_client import GraphitiClient
    try:
        graphiti = GraphitiClient(
            neo4j_uri=settings.neo4j_uri,
            neo4j_auth=(settings.neo4j_user, settings.neo4j_password),
        )
        await graphiti.init_schema()
        logger.info("graphiti_connected")
    except Exception as e:
        logger.warning("graphiti_init_failed", error=type(e).__name__)
app.state.graphiti = graphiti
```

And in shutdown:
```python
if graphiti is not None:
    await graphiti.close()
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/config.py backend/app/api/dependencies.py
git commit -m "feat(lifespan): add GraphitiClient to FastAPI lifespan"
```

---

### Task 10: Add Graphiti ingestion worker task

**Files:**
- Modify: `backend/app/workers/tasks.py`

- [ ] **Step 1: Add new task function**

Add after existing tasks in `backend/app/workers/tasks.py`:
```python
async def process_book_graphiti(
    ctx: dict,
    book_id: str,
    saga_id: str,
    saga_name: str,
    book_num: int = 1,
    saga_profile_json: str | None = None,
) -> str:
    """Ingest a book via Graphiti (KG v2 pipeline).

    Discovery Mode if saga_profile_json is None, Guided Mode otherwise.
    """
    from app.core.graphiti_client import GraphitiClient
    from app.services.ingestion.graphiti_ingest import BookIngestionOrchestrator
    from app.services.saga_profile.models import SagaProfile

    graphiti: GraphitiClient = ctx["graphiti"]
    neo4j_driver = ctx["neo4j_driver"]

    # Fetch chapters from Neo4j
    async with neo4j_driver.session() as session:
        result = await session.run(
            """
            MATCH (b:Book {book_id: $book_id})-[:HAS_CHAPTER]->(c:Chapter)
            RETURN c.number AS number, c.text AS text
            ORDER BY c.number
            """,
            book_id=book_id,
        )
        chapters = await result.data()

    orchestrator = BookIngestionOrchestrator(graphiti=graphiti)

    if saga_profile_json:
        profile = SagaProfile.model_validate_json(saga_profile_json)
        await orchestrator.ingest_guided(
            chapters=chapters,
            book_id=book_id,
            book_num=book_num,
            saga_id=saga_id,
            profile=profile,
        )
        return f"guided:{len(chapters)} chapters"
    else:
        await orchestrator.ingest_discovery(
            chapters=chapters,
            book_id=book_id,
            book_num=book_num,
            saga_id=saga_id,
        )
        # Auto-run SagaProfileInducer after Discovery
        from app.services.saga_profile.inducer import SagaProfileInducer

        full_text = "\n".join(ch["text"] for ch in chapters)
        inducer = SagaProfileInducer(driver=neo4j_driver)
        profile = await inducer.induce(
            saga_id=saga_id,
            saga_name=saga_name,
            source_book=book_id,
            raw_text=full_text,
        )
        # Persist profile as JSON in Redis
        redis = ctx["redis"]
        await redis.set(f"saga_profile:{saga_id}", profile.model_dump_json())

        return f"discovery:{len(chapters)} chapters, {len(profile.entity_types)} types induced"
```

- [ ] **Step 2: Register task in WorkerSettings**

Add `process_book_graphiti` to the `functions` list in `backend/app/workers/settings.py`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/workers/settings.py
git commit -m "feat(workers): add Graphiti ingestion worker task"
```

---

### Task 11: Update Docker Compose for Neo4j GDS

**Files:**
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Update Neo4j config**

In `docker-compose.prod.yml`, update the neo4j service:
```yaml
environment:
  NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
  NEO4J_dbms_security_procedures_allowlist: "apoc.*,gds.*"
  NEO4J_dbms_memory_heap_max__size: "6G"
  NEO4J_dbms_memory_pagecache_size: "3G"
mem_limit: 12g
```

- [ ] **Step 2: Add `graphiti-core` and `kg-gen` to Dockerfile**

Verify that `graphiti-core` and `kg-gen` are in the project dependencies so the Docker image includes them.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "infra: add Neo4j GDS plugin, increase memory for Leiden clustering"
```

---

## Chunk 6: Frontend Adaptation + Cleanup

### Task 12: Adapt frontend graph explorer for dynamic types

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/components/chat/chat-message.tsx`

- [ ] **Step 1: Update API types**

The graph explorer needs to handle dynamic entity types (no more hardcoded "Character", "Skill", etc.). Update the entity type to be string-based rather than enum-based.

- [ ] **Step 2: Update chat-message to handle new response format**

The ChatV2 response schema may differ slightly (entity summaries from Graphiti). Adapt the display components.

- [ ] **Step 3: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): adapt graph explorer for dynamic entity types"
```

---

### Task 13: Delete old extraction code

**Files:**
- Delete: `backend/app/services/extraction/` (entire directory)
- Delete: `backend/app/agents/chat/` (old chat pipeline)
- Delete: `backend/app/agents/reader/` (reader agent)
- Delete: `ontology/*.yaml` (hardcoded ontology)
- Delete: `backend/app/core/ontology_loader.py`
- Delete: `backend/app/llm/embeddings.py`
- Delete: `scripts/init_neo4j.cypher`
- Delete: corresponding test files

- [ ] **Step 1: Verify new pipeline works end-to-end before deleting**

```bash
cd backend && python -m pytest tests/test_saga_profile_models.py tests/test_pydantic_generator.py tests/test_narrative_temporal_mapper.py tests/test_graphiti_client.py tests/test_graphiti_ingest.py tests/test_saga_profile_inducer.py tests/test_chat_v2_pipeline.py -v
```
All new tests must pass before proceeding.

- [ ] **Step 2: Delete old code**

```bash
rm -rf backend/app/services/extraction/
rm -rf backend/app/agents/chat/
rm -rf backend/app/agents/reader/
rm -f backend/app/core/ontology_loader.py
rm -f backend/app/llm/embeddings.py
rm -f scripts/init_neo4j.cypher
# Keep ontology/ for now as reference — remove later
```

- [ ] **Step 3: Delete old tests that import deleted modules**

Identify and remove test files that depend on deleted code. Run:
```bash
cd backend && python -m pytest --collect-only 2>&1 | grep "ImportError"
```
Delete each file that fails to import.

- [ ] **Step 4: Verify remaining tests pass**

```bash
cd backend && python -m pytest -x -v
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old extraction pipeline, chat v1, reader agent, hardcoded ontology"
```

---

### Task 14: End-to-end validation on 3 sagas

**Files:**
- No new files — validation script run manually

- [ ] **Step 1: Start infrastructure**

```bash
docker compose -f docker-compose.prod.yml up -d
```

- [ ] **Step 2: Upload and extract Primal Hunter (LitRPG)**

Upload via API, trigger Graphiti ingestion. Verify:
- SagaProfile induced with Skill, Class, Bloodline types
- Patterns detected: `[Skill Acquired: X]`, `[Level X → Y]`
- Entity summaries created in Neo4j
- Chat queries work via Graphiti search

- [ ] **Step 3: Upload and extract Harry Potter (fantasy)**

Verify:
- SagaProfile induced with Spell, House, MagicalCreature types
- No text patterns (prose pure)
- Entity resolution handles "Harry", "Harry Potter", "Potter"

- [ ] **Step 4: Upload and extract L'Assassin Royal (low-magic)**

Verify:
- Simple SagaProfile (MagicSystem with 2 instances)
- System adapts to low-complexity universe

- [ ] **Step 5: Document results and commit**

```bash
git commit --allow-empty -m "test: validate KG v2 on 3 sagas — Primal Hunter, Harry Potter, Assassin Royal"
```
