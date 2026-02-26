# V3 Design: Character State Tracking

**Date**: 2026-02-26
**Author**: Claude (synthesized from 3 specialist agents)
**Status**: Approved
**Approach**: A — Stat Ledger (immutable event log, Cypher aggregation at query time)

---

## 1. Problem Statement

The V2 extraction pipeline captures entities (skills, classes, titles, stats, items) but:

1. **No temporal stat snapshots** — `upsert_stat_changes` accumulates `ON MATCH SET r.value = r.value + sc.value`, destroying per-chapter history
2. **No character sheet at chapter N** — can't answer "what were Jake's stats at chapter 14?"
3. **No provenance** — no link between an item/class/bloodline and the skills it grants
4. **No blue box grouping** — individual stat lines aren't grouped into coherent system notifications
5. **Layer 3 ontology entities defined but never extracted** — Bloodline, Profession, PrimordialChurch, AlchemyRecipe, Floor exist in `ontology/primal_hunter.yaml` but have no extraction pass

## 2. Solution: Stat Ledger Pattern

Immutable `StateChange` nodes form an append-only event log. Character state at any chapter is reconstructed via Cypher aggregation (`sum(value_delta) WHERE chapter <= N`). No precomputed materialized views — Neo4j handles the aggregation in 5-15ms for typical character sizes (50-200 change nodes).

### Design Principles

- **Immutability**: StateChange nodes are never updated, only created
- **Reconstruction over storage**: state at chapter N is computed, not stored
- **Provenance as static capability**: GRANTS relations describe what an item/class CAN provide; temporal ownership lives on HAS_SKILL/POSSESSES
- **Layer 3 activation**: Series-specific entities extracted alongside existing passes

---

## 3. Neo4j Data Model

### 3.1 StateChange Node (new)

```cypher
(:Character)-[:STATE_CHANGED]->(sc:StateChange {
  character_name: String,     -- denormalized for fast lookup
  book_id: String,
  chapter: Integer,
  category: String,           -- "stat"|"skill"|"class"|"title"|"item"|"level"
  name: String,               -- stat name, skill name, class name, etc.
  action: String,             -- "gain"|"lose"|"upgrade"|"evolve"|"acquire"|"drop"
  value_delta: Integer?,      -- numeric change (null for non-numeric)
  value_after: Integer?,      -- absolute value after change (null if unknown)
  detail: String,             -- contextual note
  source_chunk_id: String?,   -- grounding link
  batch_id: String,
  created_at: DateTime
})
```

**Constraint**:
```cypher
CREATE CONSTRAINT state_change_unique IF NOT EXISTS
  FOR (sc:StateChange)
  REQUIRE (sc.character_name, sc.book_id, sc.chapter, sc.category, sc.name) IS UNIQUE;
```

**Indexes**:
```cypher
CREATE INDEX state_change_character IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.character_name, sc.book_id);
CREATE INDEX state_change_chapter IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.chapter);
```

### 3.2 BlueBox Node (new)

Groups consecutive `blue_box` paragraphs into coherent system notification blocks.

```cypher
(:BlueBox {
  book_id: String,
  chapter: Integer,
  index: Integer,             -- ordering within chapter
  raw_text: String,           -- complete raw text of the blue box
  box_type: String,           -- "skill_acquisition"|"level_up"|"title"|"stat_block"|"mixed"
  paragraph_start: Integer,   -- first paragraph index
  paragraph_end: Integer      -- last paragraph index
})-[:CONTAINS_CHANGE]->(sc:StateChange)
```

**Constraint**:
```cypher
CREATE CONSTRAINT bluebox_unique IF NOT EXISTS
  FOR (bb:BlueBox) REQUIRE (bb.book_id, bb.chapter, bb.index) IS UNIQUE;
```

### 3.3 GRANTS Relations (static capability)

```cypher
(:Item)-[:GRANTS_SKILL]->(:Skill)
(:Class)-[:GRANTS_SKILL]->(:Skill)
(:Bloodline)-[:GRANTS_SKILL]->(:Skill)
(:Item)-[:GRANTS_STAT {stat_name: String, value: Integer}]->(:Character)
```

These are static declarations — "this item CAN grant this skill". Temporal ownership is on HAS_SKILL (`valid_from_chapter`/`valid_to_chapter`).

### 3.4 Layer 3 Entities

```cypher
-- Bloodline
CREATE CONSTRAINT bloodline_unique IF NOT EXISTS
  FOR (b:Bloodline) REQUIRE b.name IS UNIQUE;

(:Character)-[:HAS_BLOODLINE {
  awakened_chapter: Integer?,
  evolution_chapter: Integer?
}]->(:Bloodline {name, description, effects: [String], origin})

-- Profession
CREATE CONSTRAINT profession_unique IF NOT EXISTS
  FOR (p:Profession) REQUIRE (p.name, p.book_id) IS UNIQUE;

(:Character)-[:HAS_PROFESSION {
  valid_from_chapter: Integer,
  valid_to_chapter: Integer?
}]->(:Profession {name, tier, type})

-- PrimordialChurch
CREATE CONSTRAINT church_unique IF NOT EXISTS
  FOR (pc:PrimordialChurch) REQUIRE pc.deity_name IS UNIQUE;

(:Character)-[:WORSHIPS {
  blessing: String?,
  valid_from_chapter: Integer?
}]->(:PrimordialChurch {deity_name, domain, blessing_effects: [String]})
```

### 3.5 Reconstruction Queries

**Stats at chapter N** (core ledger aggregation):
```cypher
MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
WHERE sc.chapter <= $chapter AND sc.category = 'stat' AND sc.book_id = $book_id
WITH sc.name AS stat_name, sum(sc.value_delta) AS total, max(sc.chapter) AS last_ch
RETURN stat_name, total, last_ch
ORDER BY stat_name
```

**Skills at chapter N**:
```cypher
MATCH (ch:Character {canonical_name: $name})-[r:HAS_SKILL]->(sk:Skill)
WHERE r.valid_from_chapter <= $chapter
  AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter > $chapter)
RETURN sk.name, sk.rank, sk.skill_type, sk.description, r.valid_from_chapter
ORDER BY r.valid_from_chapter
```

**Level at chapter N** (latest level change):
```cypher
MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
WHERE sc.chapter <= $chapter AND sc.category = 'level' AND sc.book_id = $book_id
ORDER BY sc.chapter DESC LIMIT 1
RETURN sc.value_after AS level, sc.detail AS realm, sc.chapter AS since_chapter
```

---

## 4. Extraction Pipeline Changes

### 4.1 Existing Passes Modified

**entity_repo.upsert_stat_changes** — Currently: `ON MATCH SET r.value = r.value + sc.value` (lossy). New behavior:
1. MERGE the HAS_STAT relationship (keeps latest value for backward compat)
2. CREATE a StateChange node per delta (immutable ledger)

Same dual-write pattern for: `upsert_skills`, `upsert_classes`, `upsert_titles`, `upsert_items`, `upsert_level_changes`.

### 4.2 New: BlueBox Grouping (Passe 0.5)

Runs after Passe 0 (regex), before LLM passes.

1. Query consecutive `blue_box` paragraphs in each chapter
2. Group adjacent paragraphs (gap <= 1 non-blue-box paragraph) into BlueBox nodes
3. Parse combined text with existing regex patterns
4. Create CONTAINS_CHANGE relationships to StateChange nodes

V2 already has `type: "blue_box"` paragraphs, so grouping is straightforward.

### 4.3 New: Provenance Extraction (Pass 2b)

After systems extraction (Pass 2), a provenance sub-pass:

- Input: skills acquired in this chapter + surrounding context
- Output: `{skill_name, source_type: "item"|"class"|"bloodline"|"unknown", source_name, confidence}`
- Only create GRANTS relations when confidence > 0.7
- Uses Instructor (Gemini Flash) with structured output

LitRPG specialist estimates: ~40% explicit provenance, ~40% implicit, ~20% absent. We capture the first two categories.

### 4.4 New: Layer 3 Extraction (Pass 4b)

Series-specific pass using `ontology/primal_hunter.yaml`:

**Regex patterns** (already defined in YAML, wire into Passe 0):
- `bloodline_notification`: `\[Bloodline\s+(?:Awakened|Evolved|Activated):\s*(.+?)\]`
- `profession_obtained`: `Profession\s+(?:Obtained|Acquired|Gained):\s*(.+?)\s*(?:\((.+?)\))?`
- `blessing_received`: `\[Blessing\s+(?:of|from)\s+(.+?)(?:\s+received|\])`
- `nevermore_floor`: `(?:Floor|Level)\s+(\d+)\s+(?:of\s+)?Nevermore`

**LLM pass** for narrative mentions (Bloodline descriptions, church interactions, profession context).

Priority: Bloodline > PrimordialChurch > Profession > AlchemyRecipe > Floor

### 4.5 Edge Cases

| Case | Handling |
|---|---|
| Skill evolution | `action="evolve"` + SKILL_EVOLVES_INTO |
| Temporary buffs | `action="gain"` + `detail="temporary"`, paired `action="lose"` if expiry mentioned |
| Multi-source skills | Multiple GRANTS edges (item + class synergy) |
| Grade transitions (D→C) | `action="upgrade"` on Level category |
| Equipment loss | `action="drop"` StateChange + close POSSESSES valid_to_chapter |

---

## 5. API Endpoints

### 5.1 Routes

New router: `backend/app/api/routes/characters.py`

| Method | Path | Response Model | Description |
|---|---|---|---|
| GET | `/api/characters/{name}/at/{chapter}` | `CharacterStateSnapshot` | Full character sheet at chapter N |
| GET | `/api/characters/{name}/progression` | `ProgressionTimeline` | Paginated progression timeline |
| GET | `/api/characters/{name}/compare` | `CharacterComparison` | Diff between two chapters |
| GET | `/api/characters/{name}/summary` | `CharacterSummary` | Lightweight hover tooltip |

### 5.2 Schemas

**CharacterStateSnapshot** (full sheet):
```python
class CharacterStateSnapshot(BaseModel):
    character_name: str
    canonical_name: str
    book_id: str
    as_of_chapter: int
    total_chapters_in_book: int
    role: str
    species: str
    description: str
    aliases: list[str]
    level: LevelSnapshot
    stats: list[StatEntry]           # {name, value, last_changed_chapter}
    skills: list[SkillSnapshot]      # {name, rank, skill_type, acquired_chapter}
    classes: list[ClassSnapshot]     # {name, tier, acquired_chapter, is_active}
    titles: list[TitleSnapshot]      # {name, effects, acquired_chapter}
    items: list[ItemSnapshot]        # {name, rarity, grants: [], acquired_chapter}
    chapter_changes: list[StateChange]  # changes in THIS chapter only
    total_changes_to_date: int
```

**CharacterComparison** (diff):
```python
class CharacterComparison(BaseModel):
    character_name: str
    from_chapter: int
    to_chapter: int
    level_from: int | None
    level_to: int | None
    stat_diffs: list[StatDiff]       # {name, value_at_from, value_at_to, delta}
    skills: CategoryDiff             # {gained: [], lost: []}
    classes: CategoryDiff
    titles: CategoryDiff
    items: CategoryDiff
    total_changes: int
```

**CharacterSummary** (lightweight, for hover):
```python
# Returns: name, canonical_name, role, species, level, realm,
#          active_class, top_skills (3), description, wiki_url
```

### 5.3 Performance

| Concern | Strategy |
|---|---|
| Ledger aggregation | Direct Cypher `sum()`, ~10ms |
| Repeated requests | Redis cache, 5-min TTL |
| Slider dragging | Debounce 300ms client-side + SWR `keepPreviousData` |
| Protagonist warmup | Optional arq job post-extraction (top 5 chars, every 10th chapter) |
| Hover cards | Lightweight `/summary` endpoint + SWR dedup |
| Progression timeline | Server-side pagination (offset/limit) |

---

## 6. Frontend

### 6.1 Character Sheet Page

Route: `/characters/[name]?book_id=...&chapter=...`

```
CharacterSheetPage
  |-- ChapterSlider (shadcn Slider, debounced 300ms, URL synced)
  |-- CharacterHeader (name, role, species, level badge, class)
  |-- Tabs
  |   |-- Stats (3-col grid of stat cards + mini sparklines via recharts)
  |   |-- Skills (filterable by type, grouped by acquisition chapter)
  |   |-- Classes (vertical timeline of class acquisitions/evolutions)
  |   |-- Equipment (ItemCard with GRANTS links to skills/effects)
  |   |-- Titles (with effects)
  |   |-- Changelog (all StateChanges for current chapter)
  |-- ComparisonDrawer (Sheet component, side-by-side two-chapter diff)
```

- **CSR** with SWR (`keepPreviousData: true`)
- URL param `?chapter=N` makes it shareable/bookmarkable
- shadcn/ui: Card, Tabs, Badge, Slider, Sheet, Separator, Skeleton, ScrollArea

### 6.2 Reader Integration

Enhanced HoverCard on Character annotations:
- Calls `/characters/{name}/summary?chapter=N`
- Shows: name, level badge, active class, top 3 skills, description (2 lines)
- "Full Character Sheet" link at bottom
- SWR dedup prevents repeated API calls on re-hover

### 6.3 Progression View

Dual mode (toggle):
- **Timeline**: vertical, grouped by chapter, category filter chips, color-coded by category
- **Chart**: recharts LineChart, one line per stat, x=chapter, y=value, toggle per stat

---

## 7. Files to Create/Modify

### New Files

| File | Purpose |
|---|---|
| `backend/app/schemas/character_state.py` | Pydantic models (snapshot, progression, comparison, summary) |
| `backend/app/api/routes/characters.py` | 4 FastAPI endpoints |
| `backend/app/repositories/character_state_repo.py` | Cypher queries for ledger aggregation |
| `backend/app/services/extraction/bluebox.py` | BlueBox grouping logic (Passe 0.5) |
| `backend/app/services/extraction/provenance.py` | Provenance extraction (Pass 2b) |
| `backend/app/services/extraction/series_entities.py` | Layer 3 extraction (Pass 4b) |
| `backend/app/prompts/extraction_provenance.py` | Provenance LLM prompt |
| `backend/app/prompts/extraction_series.py` | Series-specific LLM prompt |
| `frontend/lib/api/characters.ts` | TypeScript API client + types |
| `frontend/hooks/useCharacterState.ts` | SWR hook for snapshot fetching |
| `frontend/app/(explorer)/characters/[name]/page.tsx` | Character Sheet page |
| `frontend/components/characters/*.tsx` | 10+ components (slider, stats, skills, etc.) |
| `frontend/components/reader/character-hover-content.tsx` | Enhanced hover card |

### Modified Files

| File | Change |
|---|---|
| `scripts/init_neo4j.cypher` | Add StateChange, BlueBox, Bloodline, Profession, Church constraints + indexes |
| `backend/app/main.py` | Register `characters_router` |
| `backend/app/repositories/entity_repo.py` | Dual-write: existing upsert + StateChange creation |
| `backend/app/services/extraction/regex_extractor.py` | Add Layer 3 regex patterns |
| `backend/app/services/extraction/__init__.py` | Wire new passes into LangGraph |
| `backend/app/prompts/extraction_systems.py` | Add provenance-aware few-shot examples |
| `frontend/components/shared/sidebar.tsx` | Add "Characters" nav item |
| `frontend/components/reader/annotated-text.tsx` | CharacterHoverContent for Character annotations |

---

## 8. Implementation Phases

### Phase 1: Data Model + Ledger (backend core)
- Neo4j schema changes (constraints, indexes)
- StateChange creation in entity_repo upsert methods
- CharacterStateSnapshot reconstruction queries
- 4 API endpoints + Pydantic schemas

### Phase 2: BlueBox + Provenance (extraction enrichment)
- BlueBox grouping (Passe 0.5)
- Provenance extraction (Pass 2b)
- GRANTS relation creation

### Phase 3: Layer 3 Extraction (series-specific)
- Wire primal_hunter.yaml regex into regex_extractor
- LLM pass for Bloodline/Profession/Church
- Layer 3 entity persistence

### Phase 4: Frontend (character sheet + reader)
- Character Sheet page with all tabs
- Chapter slider with SWR
- Reader hover card enhancement
- Progression timeline + chart

### Phase 5: Polish
- Redis caching
- Protagonist warmup job
- Comparison drawer
- Re-extraction migration script
