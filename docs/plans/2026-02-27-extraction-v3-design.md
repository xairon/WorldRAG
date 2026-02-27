# WorldRAG V3 — Commercial-Grade Extraction Pipeline Overhaul

**Date**: 2026-02-27
**Status**: Approved
**Scope**: Complete redesign of ontology, prompts, regex, schemas, pipeline, and incremental evolution
**Supersedes**: V2 pipeline design (2026-02-26)

**Academic References**:
- GOLEM (MDPI 2025): Formal fiction ontology, CIDOC-CRM aligned
- KGGen (Google 2025): Generate → Aggregate → Cluster pipeline
- ODKE+ (2024): Ontology-Driven KG Extraction with grounding verification
- Schema-Guided Generation (NeurIPS 2024): Ontology as extraction schema
- OntoMedia (Southampton): Narrative entities, fabula/sjuzhet distinction
- SEM (VU Amsterdam): Simple Event Model
- Bamman et al. (CMU): Computational character model

---

## 1. Problem Statement

### Audit Findings

| Area | Issues Found |
|------|-------------|
| **Prompts** | FR/EN mix (4 FR, 2 EN), missing few-shots on coreference/narrative, vague extraction_series, no structured output schemas in prompts |
| **Regex** | Only 5 patterns (skill_acquired, level_up, class_change, title_gained, blue_box_generic). Missing: stat blocks, skill evolution, profession, bloodline, quest, achievement, damage, death, realm breakthrough, XP, item acquisition |
| **Ontology** | 3-layer structure exists but Layer 2/3 gaps — no Race, no StatBlock, no SystemNotification node. No mechanism for ontology evolution |
| **Schemas** | Missing: confidence scores, temporal evolution chains, entity status (alive/dead/unknown), aggregated stat tracking. `valid_to_chapter` rarely populated |
| **Pipeline** | Fixed 4-pass parallel (characters/systems/events/lore). No layered extraction. Router uses hard-coded keyword thresholds. No incremental learning |
| **Articulations** | Reconciler handles 10 types but no cross-book dedup. No ontology versioning. GROUNDED_IN merge-expands spans |

### Design Goals

1. **Layered extraction**: Narrative → Genre → Series (onion model)
2. **Hybrid ontology**: Validated templates + LLM auto-discovery for series-specific entities
3. **Multilingual**: French-first, language-agnostic architecture
4. **Incremental evolution**: System improves chapter-by-chapter, book-by-book
5. **Commercial quality**: Robust, novel, complete — every entity type covered

---

## 2. Design Principles

1. **Ontology-Driven**: The ontology is the contract. Every extraction pass receives its target schema from the ontology, not hard-coded in prompts.
2. **Layered Independence**: Each extraction layer (narrative, genre, series) is independently testable and deployable. Layers compose, never duplicate.
3. **Evolution-First**: The system is designed to improve over time. Ontology, regex, and extraction quality all evolve as more content is processed.
4. **Grounded Truth**: Every extracted fact links back to source text with char offsets. Ungrounded facts are quarantined, not persisted.
5. **Cost-Bounded**: Each layer has a cost ceiling. Free passes (regex, programmatic) always run before LLM passes.
6. **Idempotent Re-extraction**: Any chapter can be re-extracted without corrupting the graph. Versioned extractions layer, never overwrite.

---

## 3. Ontology Architecture (3 Layers)

### Layer 1 — Core Narrative (universal, all fiction)

Grounded in GOLEM + CIDOC-CRM + SEM + OntoMedia. Language-agnostic.

**Node types** (13):
- `Series`, `Book`, `Chapter`, `Chunk`, `Paragraph` — bibliographic
- `Character` — with `role`, `species`, `gender`, `status` (alive/dead/unknown/transformed)
- `Faction` — with `alignment`, `type`
- `Event` — with `event_type` (action/state_change/achievement/process/dialogue), `significance`, `fabula_order`
- `Arc` — story arcs with `chapter_start`/`chapter_end`, `status`
- `Location` — hierarchical with `parent_location`
- `Item` — with `item_type`, `rarity`
- `Concept` — abstract lore (magic systems, political structures, cosmology)
- `Prophecy` — with `status` (unfulfilled/fulfilled/subverted)

**Relationship types** (20+): Temporal (`valid_from_chapter`/`valid_to_chapter`), causal (CAUSES, ENABLES), structural (PART_OF), grounding (MENTIONED_IN).

**Unchanged from current**: This layer already exists in `ontology/core.yaml` and is solid.

### Layer 2 — Genre Template (LitRPG/Progression Fantasy)

Extends Layer 1. Loaded conditionally based on detected or specified genre.

**Node types** (7):
- `System` — progression system definition
- `Class` — character class with tier hierarchy
- `Skill` — with `skill_type`, `rank`, `effects`
- `Title` — earned titles with effects
- `Level` — with `realm` and `stage`
- `Race` — species/race with traits
- `Creature` — with `threat_level`, `habitat`

**New additions to current `litrpg.yaml`**:
- `StatBlock` node — snapshot of a character's stats at a point in time
- `QuestObjective` node — quest/objective tracking
- `Achievement` node — system achievements
- `Realm` node — cultivation/grade realms (separate from Level for progression tracking)

**Relationship types** (10+): HAS_CLASS, HAS_SKILL, HAS_TITLE, AT_LEVEL, EVOLVES_INTO, etc.

**Regex patterns**: Defined at this layer (not hard-coded in Python). See Section 6.

### Layer 3 — Series-Specific (auto-discovered + user-validated)

**Hybrid approach**: The system provides a template, the LLM enriches it during first-book processing, and the user validates.

**Process**:
1. User uploads Book 1 and optionally provides a series config YAML
2. If no config: after Pass 0 (regex) + Pass 1 (narrative), the system runs a **Series Discovery Pass** — LLM analyzes extracted entities + blue boxes to propose series-specific entity types
3. Proposed types are presented to user for validation (approve/modify/reject)
4. Validated types are persisted as `ontology/series_{slug}.yaml`
5. Subsequent books in the series use this config + can propose additions (see Section 9)

**Current Primal Hunter layer** (already solid):
- `Bloodline`, `PrimordialChurch`, `AlchemyRecipe`, `Profession`, `Floor`
- Series-specific regex (bloodline_notification, profession_obtained, blessing_received, grade_reference, nevermore_floor)

**Auto-discovery targets**: Entity types that appear in blue boxes with consistent formatting but aren't in the genre template.

---

## 4. Pipeline Architecture (6 Phases)

### Overview

```
Upload (epub/pdf/txt)
  ↓
Phase 0 — Regex Pre-Extraction ($0, deterministic)
  → Blue boxes, stat blocks, level-ups, system notifications
  → Outputs: structured entities + "entity hints" for later phases
  ↓
Phase 1 — Narrative Extraction (Layer 1 ontology)
  → Characters, events, locations, items, factions, concepts, arcs
  → Uses entity registry from Phase 0 as context
  ↓
Phase 2 — Genre Extraction (Layer 2 ontology)
  → Skills, classes, titles, levels, system mechanics
  → Uses entities from Phase 1 as context (knows which characters exist)
  ↓
Phase 3 — Series Extraction (Layer 3 ontology)
  → Series-specific: bloodlines, professions, recipes, etc.
  → Uses Phases 1+2 entities as context
  → Auto-discovery: proposes new entity types if novel patterns found
  ↓
Phase 4 — Reconciliation & Deduplication
  → Cross-phase entity resolution (3-tier: exact → fuzzy → LLM-as-Judge)
  → Cross-chapter consistency (growing entity registry)
  → Cross-book matching (series-level dedup)
  → Alias map construction
  ↓
Phase 5 — Grounding & Mention Detection
  → Source linking (MENTIONED_IN with char offsets)
  → Programmatic mention scan (regex/fuzzy on known entities, $0)
  → LLM coreference resolution (pronoun → entity)
  ↓
[Persist to Neo4j]
  → Versioned with ontology_version + extraction_run_id
  → UNWIND + MERGE (batch, idempotent)
```

### Phase 0 — Regex Pre-Extraction

**Cost**: $0 (pure regex, no LLM)

Runs all regex patterns from the active ontology layers (Layer 1 has none, Layer 2 has genre patterns, Layer 3 has series patterns).

**Outputs**:
- Structured entities (SkillAcquired, LevelUp, ClassObtained, etc.)
- Entity hints (names, types) injected into Phase 1-3 prompts
- Blue box boundaries (paragraph-level, for reader rendering)
- Stat block snapshots (structured JSON from regex capture groups)

**Evolution**: New regex patterns can be added at Layer 2/3 without changing code. The regex engine reads patterns from YAML at runtime.

### Phase 1 — Narrative Extraction (Layer 1)

**Target ontology**: Core narrative entities only
**LLM**: Gemini 2.5 Flash (cost-optimized)
**Parallelism**: 3 sub-passes (characters+factions, events+arcs, locations+items+concepts)

**Prompt structure** (see Section 5 for full prompt architecture):
- System: role definition + ontology schema (from YAML) + output format
- Context: entity registry (growing), previous chapter summary, entity hints from Phase 0
- User: chapter text
- Few-shot: 2 examples per sub-pass

**Key extraction targets**:
- Characters: identity, role, status, relationships, first/last appearance
- Events: type, participants, causality, significance, temporal order
- Locations: hierarchy, type, connections
- Items: type, rarity, ownership changes
- Arcs: start/end detection, status tracking
- Concepts: abstract lore, rules, cosmology

### Phase 2 — Genre Extraction (Layer 2)

**Target ontology**: Genre-specific entities (LitRPG for current use case)
**LLM**: Gemini 2.5 Flash
**Parallelism**: 2 sub-passes (progression: skills+classes+titles+levels, world: races+creatures+systems)

**Context enrichment**: Receives all Phase 1 entities as known context. This means the LLM knows which characters exist and can attribute skills/classes to the correct character without re-extracting character identities.

**Key extraction targets**:
- Skills: name, type, rank, effects, evolution chain
- Classes: name, tier, requirements, evolution paths
- Levels: value, realm, stage transitions
- Stat blocks: structured stat snapshots (cross-validated with Phase 0 regex)
- System mechanics: rules, progression thresholds

### Phase 3 — Series Extraction (Layer 3)

**Target ontology**: Series-specific entities
**LLM**: Gemini 2.5 Flash
**Parallelism**: Single pass (series entities are fewer and interdependent)

**Two modes**:
1. **Template mode**: Series YAML exists — extract per schema
2. **Discovery mode**: No series YAML — propose new entity types based on:
   - Recurring blue box formats not matching Layer 2 patterns
   - Named concepts appearing 3+ times with consistent structure
   - Character attributes not fitting any Layer 1/2 category

**Discovery output**: Proposed schema additions presented to user via API endpoint + frontend UI.

### Phase 4 — Reconciliation

**3-tier deduplication** (existing, enhanced):
1. **Exact match**: Canonical name normalization (lowercase, strip articles)
2. **Fuzzy match**: thefuzz ratio ≥ 85% (same type) or ≥ 95% (cross-type)
3. **LLM-as-Judge**: Embedding similarity > 0.85 → ask LLM to confirm/deny merge

**Cross-chapter**:
- Entity registry grows per chapter
- Later chapters reference earlier entities by canonical name
- Alias map accumulates (Jake → "Jake Thayne", "the hunter", "he")

**Cross-book**:
- When processing Book N, load entity registry from Books 1..N-1
- Match by canonical_name first, then fuzzy, then embedding+LLM
- Temporal continuity validation (can't die in Book 2 and appear alive in Book 1)

**Alias map**: Constructed during reconciliation, applied retroactively to all entities in the current extraction run. Maps detected aliases → canonical name for each entity type.

### Phase 5 — Grounding & Mentions

**5a — Source Grounding** (from LangExtract):
- Every entity has char_offset_start/end in its source chunk
- AlignmentStatus validation: reject UNALIGNED, flag FUZZY
- Store as MENTIONED_IN (not GROUNDED_IN — no merge expansion)

**5b — Programmatic Mention Scan** ($0):
- For each known entity, scan chapter text for name + aliases
- Produces additional MENTIONED_IN relationships
- mention_type: "alias" or "exact"

**5c — Coreference Resolution** (LLM, optional):
- Resolve pronouns (il/elle/ils → known entity)
- Batched by paragraph group
- mention_type: "pronoun"

---

## 5. Multilingual Prompt Architecture

### Design Principles

1. **Prompts in target language**: All extraction prompts are written in French (primary) with English fallback
2. **Ontology labels are language-agnostic**: Property names are in English (canonical), displayed labels are per-language
3. **Few-shot examples in target language**: Each prompt includes 2-3 examples from French LitRPG text
4. **Output schema always in English**: Pydantic models use English field names regardless of prompt language

### Prompt Template Structure

Every extraction prompt follows this 4-part structure:

```
[SYSTEM]
Rôle: Tu es un extracteur d'entités narratives expert en littérature de fiction.
Langue source: {source_language}
Ontologie cible: {ontology_schema_json}

[CONTRAINTES]
- Extraire UNIQUEMENT les types d'entités listés dans l'ontologie cible
- Chaque entité DOIT avoir un ancrage textuel (extraction_text) correspondant exactement au texte source
- Confiance: attribuer un score de 0.0 à 1.0 pour chaque entité extraite
- NE PAS inventer d'informations absentes du texte

[CONTEXTE]
Registre d'entités connues: {entity_registry_json}
Résumé des chapitres précédents: {previous_summary}
Indices Phase 0 (regex): {phase0_hints}

[EXEMPLES]
{few_shot_examples}

[TEXTE À ANALYSER]
{chapter_text}
```

### Prompt Files (new structure)

```
backend/app/prompts/
├── base.py              # Base template + language config
├── phase1_characters.py # Layer 1: characters + factions
├── phase1_events.py     # Layer 1: events + arcs
├── phase1_world.py      # Layer 1: locations + items + concepts
├── phase2_progression.py # Layer 2: skills + classes + titles + levels
├── phase2_creatures.py  # Layer 2: races + creatures + systems
├── phase3_series.py     # Layer 3: series-specific (dynamic from YAML)
├── phase3_discovery.py  # Layer 3: auto-discovery prompt
├── reconciliation.py    # Cross-entity dedup prompt
├── coreference.py       # Pronoun resolution prompt
└── narrative_analysis.py # Higher-order narrative structures
```

### Language Configuration

```python
class PromptLanguage(BaseModel):
    code: str  # "fr", "en", "es", etc.
    role_prefix: str  # "Tu es..." vs "You are..."
    constraint_label: str  # "CONTRAINTES" vs "CONSTRAINTS"
    context_label: str
    examples_label: str
    text_label: str
```

Default: French. Configurable per extraction run via `EXTRACTION_LANGUAGE` env var.

### Few-Shot Strategy

Each prompt includes 2-3 few-shot examples:
- **Example 1**: "Golden" example — covers the most common extraction pattern
- **Example 2**: "Edge case" example — covers a tricky disambiguation or multi-entity extraction
- **Example 3** (optional): "Negative" example — shows what NOT to extract (hallucination prevention)

Few-shots are stored alongside prompts, not in YAML, to allow prompt-specific tuning.

---

## 6. Regex Expansion

### Current State: 5 patterns (skill_acquired, level_up, class_change, title_gained, blue_box_generic)

### Target State: 25+ patterns across Layer 2 + Layer 3

### Layer 2 (Genre: LitRPG) — Regex Patterns

| Pattern | Regex | Entity Type | Captures |
|---------|-------|-------------|----------|
| skill_acquired | `\[(?:Skill\|Ability)\s+(?:Acquired\|Learned\|Gained):\s*(.+?)(?:\s*-\s*(.+?))?\]` | Skill | name, rank |
| skill_evolved | `\[(?:Skill\|Ability)\s+(?:Evolved\|Upgraded\|Enhanced):\s*(.+?)\s*(?:→\|->)\s*(.+?)\]` | SkillEvolution | old_name, new_name |
| skill_rank_up | `\[(.+?)\s+(?:has\s+)?reached\s+(?:rank\|level)\s+(.+?)\]` | SkillRankUp | name, new_rank |
| level_up | `Level:\s*(\d+)\s*(?:→\|->)\s*(\d+)` | LevelUp | old_value, new_value |
| class_obtained | `(?:Class\|Classe):\s*(.+?)\s*\((.+?)\)` | ClassObtained | name, tier_info |
| class_evolved | `(?:Class\|Classe)\s+(?:Evolved\|Advanced):\s*(.+?)\s*(?:→\|->)\s*(.+?)` | ClassEvolution | old_class, new_class |
| title_earned | `Title\s+(?:earned\|obtained\|acquired):\s*(.+?)(?:\n\|$)` | TitleEarned | name |
| stat_increase | `\+(\d+)\s+(Strength\|Agility\|Endurance\|Vitality\|...)` | StatIncrease | value, stat_name |
| stat_block | `(?:Stats?:?\n)((?:\s*\w+:\s*\d+\n?)+)` | StatBlock | block_text (parsed further) |
| xp_gain | `\+(\d[\d,]*)\s*(?:XP\|Experience\|Exp)` | XPGain | amount |
| quest_received | `\[(?:Quest\|Objective)\s+(?:Received\|Accepted\|Updated):\s*(.+?)\]` | QuestReceived | name |
| quest_completed | `\[(?:Quest\|Objective)\s+(?:Completed\|Fulfilled):\s*(.+?)\]` | QuestCompleted | name |
| achievement_unlocked | `\[Achievement\s+(?:Unlocked\|Earned):\s*(.+?)\]` | Achievement | name |
| realm_breakthrough | `\[(?:Breakthrough\|Evolution).*?(\w-grade)\]` | RealmBreakthrough | new_grade |
| item_acquired | `\[(?:Item\s+)?(?:Acquired\|Looted\|Received):\s*(.+?)(?:\s*-\s*(.+?))?\]` | ItemAcquired | name, rarity |
| damage_dealt | `(?:dealt\|inflicted)\s+(\d[\d,]*)\s+(?:damage\|dégâts)` | DamageEvent | amount |
| death_event | `\[(.+?)\s+(?:has\s+)?(?:been\s+)?(?:slain\|killed\|defeated\|died)\]` | DeathEvent | entity_name |
| blue_box_generic | `\[([^\[\]]{5,200})\]` | SystemNotification | content |
| evolution_generic | `(?:Evolution\|Upgrade\|Breakthrough).*?(?:→\|->)\s*(.+?)(?:\n\|$)` | Evolution | target |
| dungeon_entered | `\[(?:Entering\|Entered)\s+(?:Dungeon\|Instance):\s*(.+?)\]` | DungeonEvent | name |

### Layer 3 (Primal Hunter) — Additional Patterns

| Pattern | Entity Type | Captures |
|---------|-------------|----------|
| bloodline_notification | Bloodline | name |
| profession_obtained | Profession | name, tier |
| blessing_received | Blessing | deity |
| grade_reference | GradeReference | grade |
| nevermore_floor | Floor | number |
| primordial_mention | PrimordialChurch | deity_name |
| alchemy_recipe | AlchemyRecipe | name, rarity |

### Regex Runtime Architecture

Patterns are **not hard-coded in Python**. They live in ontology YAML files and are loaded at runtime:

```python
class RegexEngine:
    """Loads regex patterns from active ontology layers."""

    def __init__(self, ontology: LoadedOntology):
        self.patterns = []
        for layer in ontology.active_layers:
            if hasattr(layer, 'regex_patterns'):
                for name, spec in layer.regex_patterns.items():
                    self.patterns.append(CompiledPattern(
                        name=name,
                        regex=re.compile(spec['pattern'], re.IGNORECASE | re.MULTILINE),
                        entity_type=spec['entity_type'],
                        captures=spec['captures'],
                        layer=layer.name,
                    ))

    def extract(self, text: str) -> list[RegexMatch]:
        """Run all patterns against text, return matches with char offsets."""
```

This means adding a new regex pattern = adding a YAML entry. No code changes.

---

## 7. Schema Refonte (Pydantic Models)

### New Fields on All Entities

```python
class BaseExtractedEntity(BaseModel):
    """Base for all extraction outputs."""
    name: str
    canonical_name: str  # Normalized (lowercase, no articles)
    entity_type: str  # From ontology
    confidence: float = Field(ge=0.0, le=1.0)  # Extraction confidence
    extraction_text: str  # Source text span
    char_offset_start: int
    char_offset_end: int
    chapter_number: int
    extraction_layer: Literal["narrative", "genre", "series"]
    extraction_phase: int  # 0-5
    ontology_version: str  # Tracks which ontology was used
```

### Character (enhanced)

```python
class ExtractedCharacter(BaseExtractedEntity):
    role: CharacterRole  # protagonist, antagonist, mentor, etc.
    species: str | None = None
    gender: str | None = None
    status: Literal["alive", "dead", "unknown", "transformed"] = "alive"
    first_appearance_chapter: int
    last_seen_chapter: int | None = None
    aliases: list[str] = []
    description: str | None = None
    evolution_of: str | None = None  # Previous identity (e.g., class change)
```

### Event (enhanced)

```python
class ExtractedEvent(BaseExtractedEntity):
    event_type: EventType  # action, state_change, achievement, process, dialogue
    significance: Significance  # minor, moderate, major, critical, arc_defining
    participants: list[EventParticipant]  # character + role (agent/patient/witness)
    location_name: str | None = None
    temporal_order: int | None = None  # Ordering within chapter
    fabula_order: int | None = None  # In-universe chronological order
    causes_event: str | None = None  # Causal chain
    is_flashback: bool = False
```

### Skill (enhanced with evolution tracking)

```python
class ExtractedSkill(BaseExtractedEntity):
    skill_type: SkillType
    rank: SkillRank
    effects: list[str] = []
    system_name: str | None = None
    evolution_chain: list[str] = []  # [base_skill, evolved1, evolved2, ...]
    owner_name: str | None = None  # Resolved during reconciliation
```

### StatBlock (new)

```python
class ExtractedStatBlock(BaseExtractedEntity):
    character_name: str
    stats: dict[str, int]  # {"Strength": 42, "Agility": 38, ...}
    total: int | None = None
    source: Literal["blue_box", "narrative", "inferred"]
```

### Extraction State (LangGraph)

```python
class ExtractionPipelineState(TypedDict, total=False):
    # Input
    book_id: str
    chapter_number: int
    chapter_text: str
    source_language: str

    # Ontology context
    active_ontology: LoadedOntology
    ontology_version: str

    # Growing context (chapter-to-chapter)
    entity_registry: EntityRegistry
    alias_map: dict[str, str]
    previous_chapter_summary: str

    # Phase outputs
    phase0_regex: list[RegexMatch]
    phase1_narrative: list[BaseExtractedEntity]
    phase2_genre: list[BaseExtractedEntity]
    phase3_series: list[BaseExtractedEntity]

    # Reconciled output
    reconciled_entities: list[BaseExtractedEntity]
    mentions: list[MentionSpan]

    # Metadata
    extraction_run_id: str
    cost_tracker: CostTracker
    errors: list[ExtractionError]
```

---

## 8. Articulations & Data Flow

### Cross-Phase Entity Flow

```
Phase 0 (Regex)
  → entity_hints: [{name: "Arcane Powershot", type: "Skill", source: "regex"}]
  → stat_snapshots: [{character: "Jake", stats: {...}, chapter: 42}]
      ↓ injected as context
Phase 1 (Narrative)
  → characters, events, locations, items, factions, concepts, arcs
  → entity_registry grows (canonical names + types)
      ↓ entity_registry passed
Phase 2 (Genre)
  → skills, classes, titles, levels (attributed to known characters)
  → cross-validated with Phase 0 regex (stat blocks match?)
      ↓ full entity set passed
Phase 3 (Series)
  → series-specific entities (attributed to known characters/locations)
  → novel pattern proposals (if discovery mode)
      ↓ all entities collected
Phase 4 (Reconciliation)
  → dedup across all phases
  → alias_map built
  → cross-book matching (if Book N > 1)
      ↓ clean entity set
Phase 5 (Grounding)
  → MENTIONED_IN relationships (multiple per entity, no merge expansion)
  → coreference resolution (pronouns → entities)
      ↓
[Neo4j Persistence]
  → UNWIND + MERGE (batch_id, ontology_version, extraction_run_id)
  → Entity Registry updated for next chapter
```

### Cross-Chapter Entity Registry

The **Entity Registry** is the key data structure that makes extraction improve chapter-by-chapter:

```python
class EntityRegistry:
    """Growing registry of known entities, maintained per book."""

    entities: dict[str, RegistryEntry]  # canonical_name → entry
    alias_map: dict[str, str]  # alias → canonical_name
    chapter_summaries: list[str]  # One per processed chapter

    def add(self, entity: BaseExtractedEntity) -> None: ...
    def lookup(self, name: str) -> RegistryEntry | None: ...
    def to_prompt_context(self, max_tokens: int = 2000) -> str: ...
```

The registry is serialized to JSON and injected into every LLM prompt as context. It caps at `max_tokens` to avoid context overflow — prioritizing by entity significance and recency.

### Cross-Book Series Registry

When processing Book N:
1. Load entity registries from Books 1..N-1 (from Neo4j)
2. Merge into a **Series Registry** — superset of all known entities
3. Use as context for extraction + reconciliation
4. After Book N extraction, update the Series Registry

### Ontology ↔ Prompt Contract

The ontology YAML defines the extraction schema. Prompts receive this schema as JSON:

```python
def build_prompt(phase: int, ontology: LoadedOntology, ...) -> str:
    target_types = ontology.get_types_for_phase(phase)
    schema_json = ontology.to_json_schema(target_types)
    # Schema is injected into the prompt as the "ontologie cible"
```

This means changing the ontology automatically changes what the LLM extracts — no prompt rewriting needed.

---

## 9. Incremental Evolution & Reprocessing

### The Problem

Book 1 of a saga introduces basic elements. Book 5 introduces entirely new concepts (new entity types, new system mechanics, new recurring structures). The system built for Book 1 is insufficient for Book 5 — and Book 1 may contain foreshadowing of Book 5 concepts that were missed on first extraction.

### Three Scales of Evolution

#### 9.1 Intra-Book (Chapter → Chapter)

**Mechanism**: Entity Registry accumulation

As extraction progresses through a book:
- The Entity Registry grows with every chapter
- Later chapters benefit from knowing all previously extracted entities
- Coreference resolution improves (more aliases known)
- The LLM receives richer context → better disambiguation

**No reprocessing needed** — this is inherent to the sequential chapter processing.

#### 9.2 Inter-Book (Volume → Volume)

**Mechanism**: Series Registry + Ontology Changelog

When Book N is processed:
1. The Series Registry from Books 1..N-1 is loaded as context
2. The system detects new patterns:
   - New blue box formats not matching existing regex → **propose new regex**
   - New entity types consistently appearing → **propose Layer 3 additions**
   - Existing entity types with new subtypes → **propose enum extensions**
3. These proposals are logged in an **Ontology Changelog**:

```python
class OntologyChange(BaseModel):
    change_type: Literal["add_entity_type", "add_relationship", "add_regex", "extend_enum", "add_property"]
    layer: Literal["genre", "series"]
    target: str  # entity type or relationship name
    proposed_by: str  # "auto_discovery" or "user"
    discovered_in_book: int
    discovered_in_chapter: int
    confidence: float
    evidence: list[str]  # source text excerpts
    status: Literal["proposed", "validated", "rejected", "applied"]
```

4. User validates proposals via API/UI
5. Validated changes are applied to the ontology YAML

#### 9.3 Cross-Extraction Reprocessing

**When the ontology evolves significantly, should previous books be re-extracted?**

**Answer: Selective, surgical reprocessing — never full re-extraction.**

**Reprocessing Strategy**:

```
Ontology Change Detected
  ↓
Compute Impact Scope
  → Which entity types were added/modified?
  → Which chapters in previous books might contain these entities?
  ↓
Lightweight Impact Scan ($0 or minimal cost)
  → Regex scan: run new patterns on all previous chapters
  → Keyword scan: search for terms related to new entity types
  → Embedding scan: find chapters semantically similar to examples of new entity type
  ↓
Candidate Chapter List
  → Only chapters with potential matches (typically 5-20% of total)
  ↓
Targeted Re-extraction (one phase only)
  → Run ONLY the relevant extraction phase (e.g., Phase 3 for new series entities)
  → Use current (evolved) entity registry as context
  → Version the new extractions with updated ontology_version
  ↓
Merge with Existing Graph
  → New extractions are ADDED, not replacing originals
  → Conflict resolution: if new extraction contradicts old, flag for review
  → Update entity registry and alias map
```

**Cost control**: Re-extraction is bounded by:
- Only affected chapters (not all)
- Only affected phases (not all 5)
- Same cost ceiling per chapter applies
- User must approve re-extraction scope

### Ontology Versioning

Every extraction stores `ontology_version` on all persisted entities:

```cypher
MERGE (e:Character {canonical_name: $name})
SET e.ontology_version = $version,
    e.extraction_run_id = $run_id,
    e.last_extracted_chapter = $chapter
```

This enables:
- **Diff queries**: "Which entities were extracted with ontology v1 but not v2?"
- **Staleness detection**: "Which chapters haven't been re-extracted since ontology changed?"
- **Rollback**: "Remove all entities from extraction_run_id X"

### Regex Evolution

Regex patterns can evolve in two ways:

1. **Manual**: User adds patterns to ontology YAML
2. **Semi-automatic**: The system analyzes blue box content across all processed chapters:
   - Clusters blue box text by format similarity
   - Identifies recurring patterns not matched by existing regex
   - Proposes new regex patterns with capture groups
   - User validates before activation

```python
class RegexProposal(BaseModel):
    proposed_pattern: str
    entity_type: str
    captures: dict[str, int]
    example_matches: list[str]  # From actual text
    frequency: int  # How many times this pattern appears
    confidence: float
    discovered_in_book: int
```

### Entity Registry Persistence

The Entity Registry is persisted in Neo4j (not just in-memory during extraction):

```cypher
(:Book)-[:HAS_REGISTRY]->(:EntityRegistry {
    version: int,
    ontology_version: str,
    entity_count: int,
    alias_count: int,
    data: str  // JSON blob of the full registry
})
```

This allows:
- Resume extraction from any chapter (not just from the start)
- Load registry from previous books for cross-book context
- Compare registries across extraction runs to measure improvement

---

## 10. LangGraph Orchestration

### Graph Structure

```python
graph = StateGraph(ExtractionPipelineState)

# Phase 0: Regex (always runs, $0)
graph.add_node("regex_extract", regex_extract_node)

# Phase 1: Narrative (Layer 1)
graph.add_node("narrative_characters", extract_characters_node)
graph.add_node("narrative_events", extract_events_node)
graph.add_node("narrative_world", extract_world_node)
graph.add_node("merge_phase1", merge_narrative_node)

# Phase 2: Genre (Layer 2, conditional)
graph.add_node("genre_progression", extract_progression_node)
graph.add_node("genre_creatures", extract_creatures_node)
graph.add_node("merge_phase2", merge_genre_node)

# Phase 3: Series (Layer 3, conditional)
graph.add_node("series_extract", extract_series_node)
graph.add_node("series_discover", discover_series_node)  # Only if discovery mode

# Phase 4: Reconciliation
graph.add_node("reconcile", reconcile_node)

# Phase 5: Grounding
graph.add_node("ground_mentions", ground_mentions_node)
graph.add_node("coreference", coreference_node)

# Persistence
graph.add_node("persist", persist_to_neo4j_node)
graph.add_node("update_registry", update_registry_node)

# Edges
graph.add_edge(START, "regex_extract")
graph.add_edge("regex_extract", "narrative_characters")
graph.add_edge("regex_extract", "narrative_events")
graph.add_edge("regex_extract", "narrative_world")
graph.add_conditional_edges("merge_phase1", should_run_genre, {
    True: "genre_progression",
    False: "reconcile",
})
# ... (fan-out/fan-in pattern for each phase)
graph.add_edge("persist", "update_registry")
graph.add_edge("update_registry", END)
```

### Conditional Phase Execution

Not all phases run for every chapter:
- **Phase 0**: Always (regex, $0)
- **Phase 1**: Always (narrative is universal)
- **Phase 2**: Only if genre ontology is loaded AND chapter contains genre-relevant content (router decides)
- **Phase 3**: Only if series ontology is loaded AND chapter contains series-specific content
- **Discovery**: Only on first book of a series, or when user explicitly requests

---

## 11. Cost Estimation

| Phase | LLM Calls/Chapter | Est. Cost/Chapter | Notes |
|-------|-------------------|-------------------|-------|
| Phase 0 (Regex) | 0 | $0.00 | Pure regex |
| Phase 1 (Narrative) | 3 parallel | ~$0.03 | Characters + Events + World |
| Phase 2 (Genre) | 2 parallel | ~$0.02 | Progression + Creatures |
| Phase 3 (Series) | 1 | ~$0.01 | Series-specific |
| Phase 4 (Reconciliation) | 0-2 | ~$0.01 | Only for ambiguous merges |
| Phase 5 (Coreference) | 1-3 | ~$0.01 | Pronoun resolution |
| **Total/chapter** | | **~$0.08** | |
| **Full book (100 ch)** | | **~$8.00** | |
| **Re-extraction (10% chapters, 1 phase)** | | **~$0.30/book** | Surgical reprocessing |

---

## 12. Migration Strategy

### Phase A: Foundation (ontology + schemas + regex)
1. Refactor ontology YAML files with new entity types
2. Add `ontology_version` field to all YAML files
3. Implement runtime regex engine (reads from YAML)
4. Create new Pydantic schemas with all new fields
5. Update Neo4j constraints for new entity types

### Phase B: Pipeline Restructure
1. Refactor LangGraph to 6-phase structure
2. Implement Entity Registry (in-memory + Neo4j persistence)
3. Add conditional phase execution (genre/series routing)
4. Wire ontology schema → prompt injection

### Phase C: Prompts
1. Rewrite all prompts in French with new template structure
2. Add 2-3 few-shot examples per prompt
3. Implement ontology-to-prompt schema injection
4. Add prompt language configuration

### Phase D: Reconciliation & Evolution
1. Enhance reconciler for cross-book matching
2. Implement Ontology Changelog
3. Implement Series Discovery pass
4. Build selective reprocessing pipeline

### Phase E: Grounding & Mentions
1. Migrate GROUNDED_IN → MENTIONED_IN (no merge expansion)
2. Implement programmatic mention scan
3. Implement coreference resolution pass

### Phase F: Re-extract
1. Re-extract all existing books with V3 pipeline
2. Validate against golden dataset
3. Compare V2 vs V3 extraction quality

---

## 13. Open Questions (for implementation phase)

1. **Registry size limit**: How to handle entity registries that exceed LLM context windows (1000+ entities after 5 books)?
   - Proposed: Priority queue by significance + recency, capped at 2000 tokens
2. **Discovery validation UX**: How should the frontend present ontology proposals?
   - Proposed: Dedicated "Ontology Lab" page with approve/modify/reject actions
3. **Reprocessing triggers**: Automatic (threshold-based) or manual only?
   - Proposed: Manual for now, with dashboard showing "staleness score" per book
4. **Backward compatibility**: How to handle entities extracted with V2 pipeline?
   - Proposed: Migration script that adds `ontology_version: "2.0"` to all existing entities, then selective re-extraction with V3
