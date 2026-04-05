# WorldRAG — Extraction Pipeline Architecture

## Pipeline Overview

```
INGESTION (sync, HTTP)              EXTRACTION V4 (async, arq worker)
========================            =======================================

Upload (epub/pdf/txt)               POST /books/{id}/extract/v4
  |                                   |
  v                                   v
[Parse chapters]                    [Load ontology (3 layers)]
  |                                   |
  v                                   v
[Chunk (narrative-aware)]           [Induce ontology (LLM, 3 chapters)]
  |                                   |
  v                                   v
[Regex extract (Passe 0)]           [Load cross-book EntityRegistry]
  |                                   |
  v                                   v
[Store: Neo4j]                      FOR EACH CHAPTER (sequential):
  |                                   |
  Status: completed                   [LangGraph 6-node pipeline] ----+
                                      |                               |
                                      [Persist to Neo4j]              |
                                      |                               |
                                      [Streaming dedup]               |
                                      |                               |
                                      [Update EntityRegistry] --------+
                                      |
                                    AFTER ALL CHAPTERS:
                                      |
                                      [Iterative clustering (global dedup)]
                                      [Entity summaries (LLM)]
                                      [State snapshots]
                                      [Community detection (Leiden)]
                                      |
                                      Status: extracted
                                      |
                                      [Auto-enqueue embedding job]
                                      |
                                      Status: embedded
```

---

## LangGraph V4 Pipeline (per chapter)

```
                    Input State
                        |
                        v
            +------------------------+
            | 1. extract_entities    |  LLM call (Instructor)
            |    Prompt: ontology +  |  Out: entities[], grounded_entities[]
            |    registry + hints    |
            +------------------------+
                        |
                        v
            +------------------------+
            | 2. verify_coverage     |  LLM call (optional, if >3 entities)
            |    "Any missed named   |  Out: entities[] (extended)
            |     entities?"         |
            +------------------------+
                        |
                        v
            +------------------------+
            | 3. extract_relations   |  LLM call (Instructor)
            |    Prompt: ontology +  |  Out: relations[], ended_relations[]
            |    entities JSON       |
            +------------------------+
                        |
                        v
            +------------------------+
            | 4. verify_extractions  |  NO LLM (heuristic)
            |    5 checks:           |  Out: entities[] (filtered),
            |    - name in text      |       chunk_metadata
            |    - generic roles     |
            |    - event = character |
            |    - game mech as type |
            |    - known char wrong  |
            +------------------------+
                        |
                        v
            +------------------------+
            | 5. mention_detect      |  NO LLM (regex)
            |    Word-boundary scan  |  Out: grounded_entities[]
            |    Names + aliases     |       (mention spans)
            +------------------------+
                        |
                        v
            +------------------------+
            | 6. reconcile_persist   |  LLM calls (dedup + faithfulness)
            |                        |
            |  6.0 Faithfulness NLI  |  Batch LLM: filter hallucinations
            |  6.1 Cross-type dedup  |  Same name, different types -> keep best
            |  6.2 Per-type 5-tier   |  exact->fuzzy->embed->CE->LLM
            |  6.3 Alias map apply   |  Normalize names
            |  6.4 Registry resolve  |  Cross-chapter matching (fuzzy 90%)
            |  6.5 Ontology validate |  Strip invalid enum values
            |  6.6 Relation validate |  Check source/target type constraints
            |  6.7 Registry update   |  Add new entities to registry
            |                        |
            +------------------------+
                        |
                        v
                  Output State
```

---

## Brick-by-Brick Reference

### Ingestion Phase

| # | Brick | File | In | Out | Purpose |
|---|-------|------|----|-----|---------|
| I1 | File parse | `services/ingestion.py` | epub/pdf/txt file | `list[ChapterData]` | Extract chapters from book file |
| I2 | Chunk | `services/chunking.py:280` | `ChapterData` | `list[ChunkData]` | Split chapters into ~1000 token chunks with scene-boundary awareness |
| I3 | Regex extract | `services/extraction/regex_extractor.py:225` | chapter text | `list[RegexMatch]` | Pattern-match game mechanics (skills, levels, titles, stats) |
| I4 | Neo4j store | `repositories/book_repo.py` | ChapterData, ChunkData, RegexMatch | Neo4j nodes | Create Book, Chapter, Chunk, Paragraph nodes |

### Worker Orchestration

| # | Brick | File | In | Out | Purpose |
|---|-------|------|----|-----|---------|
| W1 | Ontology load | `core/ontology_loader.py` | genre, series YAML | `OntologyLoader` | Merge 3 ontology layers (core + genre + series) |
| W2 | Ontology induce | `services/extraction/ontology_inducer.py` | 3 chapter texts, ontology | induced types | LLM discovers new entity/relation types not in YAML |
| W3 | Registry load | `services/extraction/entity_registry.py` | Neo4j (previous books) | `EntityRegistry` | Load known entities from earlier books in same series |
| W4 | Chapter filter | `services/graph_builder.py:411` | chapters | filtered chapters | Skip TOC, copyright, non-content chapters |
| W5 | Chapter loop | `workers/tasks.py:514` | chapters, ontology, registry | extracted KG | Sequential per-chapter extraction + persistence |
| W6 | Post-process | `services/extraction/book_level.py` | Neo4j KG | refined KG | Clustering, summaries, snapshots, communities |
| W7 | Auto-embed | `workers/tasks.py:746` | book_id | arq job | Enqueue embedding pipeline |

### LangGraph Nodes

| # | Node | File | In (state) | Out (state) | LLM? | Purpose |
|---|------|------|----|-----|------|---------|
| N1 | extract_entities | `entities.py:57` | chapter_text, ontology, registry, regex_hints | entities, grounded_entities, total_entities | Yes (Instructor) | Extract all entity types in single pass |
| N2 | verify_coverage | `__init__.py:1450` | entities, chapter_text | entities (extended) | Yes (Instructor) | Second-pass: catch missed named entities |
| N3 | extract_relations | `relations.py:52` | chapter_text, ontology, entities | relations, ended_relations | Yes (Instructor) | Extract relations between entities |
| N4 | verify_extractions | `verify.py:246` | entities, chapter_text, registry | entities (filtered), chunk_metadata | No | Heuristic quality checks (5 rules) |
| N5 | mention_detect | `__init__.py:1521` | chapter_text, entities | grounded_entities | No | Word-boundary regex mention spans |
| N6 | reconcile_persist | `__init__.py:1529` | entities, relations, registry, ontology | alias_map, registry, entities, relations | Yes (faithfulness + dedup) | 7-step reconciliation pipeline |

### Reconcile Sub-steps (Node 6)

| # | Step | File | In | Out | LLM? | Purpose |
|---|------|------|----|-----|------|---------|
| 6.0 | Faithfulness | `faithfulness.py:32` | entities, chapter_text | entities (filtered) | Yes | Batch NLI: remove hallucinated entities |
| 6.1 | Cross-type dedup | `reconciler.py:105` | entities | entities (deduped) | No | Same name + different types -> keep priority type |
| 6.2 | Per-type dedup | `reconciler.py:162` -> `deduplication.py` | entities per type | alias_map | Yes (tier 3+) | 5-tier: exact->fuzzy->embed->CE->LLM |
| 6.3 | Alias map apply | `graph_builder.py:503` | entities, relations, alias_map | normalized entities/relations | No | Apply name normalization |
| 6.4 | Registry resolve | `__init__.py:1562` | entities, registry | resolved entities | No | Cross-chapter fuzzy matching (90% threshold) |
| 6.5 | Ontology validate | `__init__.py:1594` | entities, ontology | entities (cleaned) | No | Strip invalid enum values per ontology |
| 6.6 | Relation validate | `validation.py:34` | relations, entity_map | relations (filtered) | No | Check 13 source/target type constraints |
| 6.7 | Registry update | `__init__.py:1623` | entities, registry | updated registry | No | Add new entities for next chapter context |

### Deduplication Engine (5 tiers)

| Tier | Name | File:line | Mechanism | Cost |
|------|------|-----------|-----------|------|
| 1 | Exact | `deduplication.py:exact_dedup` | Lowercase + strip articles (en/fr) | Free |
| 2 | Fuzzy | `deduplication.py:fuzzy_dedup` | thefuzz (4 algorithms, max score). >=95: auto-merge, 85-94: candidate | Free |
| 2.5a | Hybrid | `deduplication.py:hybrid_candidate_generation` | BM25 + BGE-m3 embedding cosine. Fused = max(BM25, cosine) | Local model |
| 2.5b | Cross-encoder | `deduplication.py:cross_encoder_rerank` | zerank-1-small. >0.7: merge, 0.4-0.7: escalate, <0.4: drop | Local model |
| 3 | LLM-as-Judge | `deduplication.py:llm_dedup` | Instructor batch (10 pairs). confidence>=0.8: merge | LLM call |

### Ontology System

| Component | File | What it does |
|-----------|------|-------------|
| YAML definitions | `ontology/core.yaml`, `ontology/litrpg.yaml`, `ontology/primal_hunter.yaml` | Define entity types, relation types, enum constraints, regex patterns |
| OntologyLoader | `core/ontology_loader.py` | Loads + merges YAML layers, validates enums, exports JSON schema for prompts |
| Ontology inducer | `services/extraction/ontology_inducer.py` | LLM discovers new types from first 3 chapters, extends loader at runtime |
| Entity descriptions | `prompts/templates/entity_descriptions.yaml` | Bilingual type descriptions injected into extraction prompts |
| Few-shot examples | `prompts/templates/few_shots.yaml` | Positive + negative extraction examples per genre per language |

### Post-Processing (book-level)

| # | Step | File:function | In | Out | LLM? | Purpose |
|---|------|--------------|-----|-----|------|---------|
| P1 | Iterative cluster | `book_level.py:iterative_cluster` | Neo4j entities | alias_map (merges applied) | Yes | Global dedup across all chapters via embedding + LLM |
| P2 | Entity summaries | `book_level.py:generate_entity_summaries` | entities with >=3 mentions | EntitySummary nodes | Yes | Generate 2-5 sentence entity descriptions |
| P3 | State snapshots | `book_level.py:generate_state_snapshots` | top 5 characters | StateSnapshot nodes | No | Character state every 10 chapters |
| P4 | Community detect | `book_level.py:community_cluster` | Neo4j graph | Community nodes + summaries | Yes | Hierarchical Leiden at 3 resolutions + LLM summaries |
| P5 | Consistency checks | `book_level.py:run_consistency_checks` | Neo4j graph | issue list | No | Orphans, cross-type dupes, relation violations |

---

## Known Issues / Gaps

| Issue | Location | Impact | Status |
|-------|----------|--------|--------|
| Verify rules hardcoded in Python, not from ontology YAML | `verify.py:21-49` | Maintenance split, not genre-conditional | TO FIX |
| Relation constraints hardcoded, not from ontology | `validation.py:14-31` | Same as above | TO FIX |
| `run_consistency_checks` never called in V4 worker | `tasks.py` (missing call) | Consistency checks only via admin API | TO FIX |
| Induced types not persisted (runtime only) | `ontology_inducer.py` | Lost on restart, can't be reviewed/promoted | TO FIX |
| Induction runs once (chapters 1-3 only) | `tasks.py:427` | Types introduced later are missed | FUTURE |
| Faithfulness check truncates to 4000 chars | `faithfulness.py:67` | Long chapters partially checked | MINOR |
| V4 mention_detect has no coreference resolution | `__init__.py:1521` | Pronouns ("he", "she") not resolved | KNOWN LIMITATION |
| Streaming dedup doesn't transfer relations | `deduplication.py:627` | Relations may be orphaned until book-level clustering | BY DESIGN |

---

## Proposed Change: Ontology-Driven Validation

### Before (current)

```
Ontology YAML ──> Prompt builder (entity descriptions, few-shots)
                  |
                  (DISCONNECTED)
                  |
Python code ────> Verify node (hardcoded _GENERIC_MECHANICS, _GENERIC_ROLES)
Python code ────> Validation module (hardcoded RELATION_TYPE_CONSTRAINTS)
```

### After (target)

```
Ontology YAML ──> Prompt builder (entity descriptions, few-shots)
      |
      +────────> OntologyLoader.validation_rules
                  |
                  +──> Verify node (reads type_exclusions from ontology)
                  +──> Validation module (reads domain_range from ontology)
                  +──> Consistency checks (reads cardinality from ontology)
```

**Implementation**: Add `validation_rules` section to YAML files. OntologyLoader parses them. Verify node and validation module read from OntologyLoader instead of Python constants.

```yaml
# core.yaml — universal rules
validation_rules:
  type_exclusions:
    character:
      excluded_terms: [guard, guards, soldier, soldiers, merchant, ...]
      reason: "Generic roles — only extract named individuals"
  domain_range:
    ALLIES_WITH: { from: [Character], to: [Character] }
    ENEMIES_WITH: { from: [Character], to: [Character] }

# litrpg.yaml — genre-specific rules (merged on top of core)
validation_rules:
  type_exclusions:
    concept:
      excluded_terms: [stamina, mana, health, hp, mp, xp, free points, ...]
      reason: "Game stats — use stat_change or genre_entity(sub_type=stat)"
    item:
      excluded_terms: [stamina, mana, health, hp, ...]
      reason: "Game stats — not items"
  domain_range:
    HAS_SKILL: { from: [Character], to: [Skill, GenreEntity] }
    HAS_CLASS: { from: [Character], to: [Class, GenreEntity] }
    LOCATED_AT: { from: [Character, Item, Event, Creature], to: [Location] }
    POSSESSES: { from: [Character], to: [Item, GenreEntity] }
    MEMBER_OF: { from: [Character], to: [Faction] }
    PARTICIPATES_IN: { from: [Character, Creature], to: [Event] }
```
