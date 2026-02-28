# WorldRAG V2 — SOTA Extraction Pipeline & Structured Reader

**Date**: 2026-02-26
**Status**: Approved
**Scope**: Structured epub ingestion, tuned LangExtract, mention detection, narrative analysis, reader redesign

**References**: [Kokash et al. 2022 — From Books to Knowledge Graphs](https://arxiv.org/abs/2204.10766), [Google LangExtract](https://github.com/google/langextract)

---

## 1. Problem Statement

| Issue | Root Cause |
|-------|-----------|
| Chapters displayed as raw text blocks | `BeautifulSoup.get_text()` strips all HTML structure |
| Annotation spans too broad | `max_char_buffer` not configured on LangExtract → chunks too large for precise alignment |
| Same entity highlights huge text blocks | `store_grounding()` MERGE ON MATCH expands spans (union min/max) |
| No subtle narrative detection | Pipeline only extracts entities, no arcs/foreshadowing/progression |
| No cross-book entity continuity | Each book processed independently |
| AlignmentStatus not validated | FUZZY/UNALIGNED spans kept without quality filtering |

## 2. Design Principles

1. **Keep LangExtract, fix our code** — LangExtract's WordAligner + AlignmentStatus is SOTA for grounding; our storage was expanding spans
2. **Structure-aware** — Preserve epub HTML through the entire pipeline
3. **Supplement, don't replace** — Add mention detection + narrative analysis ON TOP of LangExtract
4. **Multi-resolution** — Word-level for names, sentence-level for events, chapter-level for arcs
5. **Cross-book continuity** — Series-level entity graph shared across volumes
6. **Three-stage pattern** (per Kokash et al.): Extraction → Disambiguation → Normalization

## 3. Architecture

```
epub file
  ↓
[Ingestion] HTML-preserving parser (NEW)
  → Paragraph nodes (typed: narration/dialogue/blue_box/scene_break/header)
  → HTML preserved on each paragraph
  → Chunks (paragraph-aligned, for vector search)
  ↓
[Pass 0] Regex (existing, enhanced)
  → Blue boxes, stats, level-ups, dialogue tags, proper noun pre-scan
  → Precise spans via Python re
  ↓
[Passes 1-4] LangExtract (existing, TUNED)
  → max_char_buffer=2000 (was unconfigured)
  → AlignmentStatus validation (reject UNALIGNED, flag FUZZY)
  → Same 4 parallel passes: characters, systems, events, lore
  → Output: grounded entities with precise char_interval
  ↓
[Pass 5] Mention Detection (NEW, programmatic + LLM coref)
  5a. Regex/fuzzy on names + aliases → additional word-level spans (free)
  5b. LLM coreference → pronoun resolution (il→Jake, elle→Caroline)
  → Supplements LangExtract mentions
  ↓
[Pass 6] Narrative Analysis (NEW, Gemini + Instructor)
  → Character development, power progression, foreshadowing, themes
  ↓
[Pass 7] Reconciliation (existing, enhanced for cross-book)
  → 3-tier deduplication (exact → fuzzy → LLM-as-Judge)
  → Series-level entity matching + alias normalization
  ↓
[Storage] MENTIONED_IN (REPLACES GROUNDED_IN)
  → Multiple per entity/chapter (one per mention, NO merge expansion)
  → mention_type: langextract | regex | alias | pronoun
```

## 4. Ingestion: Structure-Aware Epub Parsing

### 4.1 HTML Preservation

Replace `soup.get_text()` with a DOM walker that classifies block elements:

```python
def classify_block(element: Tag) -> ParagraphType:
    tag = element.name
    text = element.get_text(strip=True)
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return "header"
    if is_blue_box(element):   # CSS classes, brackets, styled divs
        return "blue_box"
    if is_scene_break(element): # ***, ---, empty styled divs
        return "scene_break"
    if starts_with_dialogue(text): # «, ", —, –
        return "dialogue"
    return "narration"
```

### 4.2 Paragraph Node Schema

```cypher
(:Chapter)-[:HAS_PARAGRAPH {position: int}]->(:Paragraph {
  index: int,              // 0-based within chapter
  type: str,               // narration|dialogue|blue_box|scene_break|header
  text: str,               // cleaned text
  html: str,               // original HTML preserved
  char_start: int,         // offset in full chapter text
  char_end: int,
  speaker: str | null,     // for dialogue
  sentence_count: int,
  word_count: int
})
```

### 4.3 Chunks (paragraph-aligned)

- Chunk boundaries respect paragraph boundaries (never split mid-paragraph)
- Each chunk tracks its paragraph range
- Embedding pipeline unchanged

## 5. Extraction Pipeline

### Pass 0 — Enhanced Regex (existing + improvements)

Existing patterns + new additions:
- Dialogue tag extraction: `speaker` from «...», dit/murmura/cria [Name]
- Proper noun pre-scan: capitalized multi-word sequences as entity candidates

### Passes 1-4 — LangExtract (KEPT, tuned)

**Same 4 parallel passes**: characters, systems, events, lore

**Tuning**:
- `max_char_buffer=2000` → smaller chunks = tighter spans
- Validate `AlignmentStatus` per extraction: reject `UNALIGNED`, flag `FUZZY`
- Improved few-shot examples with shorter extraction_text spans
- Track alignment quality metrics per chapter

### Pass 5 — Mention Detection (NEW, hybrid)

**5a — Programmatic** (free, deterministic):
For each entity from LangExtract, find additional mentions via regex/fuzzy matching on name + aliases. Produces word-level spans.

**5b — Coreference Resolution** (LLM, Gemini Flash):
Resolve pronouns (il/elle/ils) to known entities. Batched by paragraph group.

### Pass 6 — Narrative Analysis (NEW, Gemini + Instructor)

Detects higher-order structures:
- **Character development**: personality shifts, growth moments
- **Power progression**: level-ups, skill acquisitions (cross-referenced with regex Pass 0)
- **Foreshadowing**: narrative hints linking to future events
- **Themes**: recurring motifs

Stored as Events with `subtype` field, not new node types.

### Pass 7 — Reconciliation (existing, enhanced)

- 3-tier dedup maintained (exact → fuzzy → LLM-as-Judge)
- **Cross-book**: When processing Book N, match against Books 1..N-1 in same Series
- Temporal consistency validation

## 6. Storage Model

### New Node Types

- `Series` — groups Books (`CONTAINS` relationship with position)
- `Paragraph` — typed chapter content with HTML

### MENTIONED_IN (replaces GROUNDED_IN)

```cypher
(entity)-[:MENTIONED_IN {
  char_start: int,
  char_end: int,
  mention_text: str,
  mention_type: str,         // langextract|regex|alias|pronoun
  sentence_index: int,
  paragraph_index: int,
  confidence: float,
  alignment_status: str      // exact|fuzzy (from LangExtract)
}]->(chapter:Chapter)
```

**Key**: Multiple relationships per entity/chapter. No MERGE expansion.

### SPANS (events)

```cypher
(event:Event)-[:SPANS {
  sentence_start: int, sentence_end: int,
  paragraph_start: int, paragraph_end: int
}]->(chapter:Chapter)
```

### FORESHADOWS

```cypher
(hint:Event {subtype: "foreshadowing"})-[:FORESHADOWS]->(resolved:Event)
```

### Unchanged

All 10 entity types, Chunk nodes + embeddings, temporal relationships (HAS_SKILL, etc.)

## 7. Frontend Reader

### Structured Rendering

| Paragraph Type | Rendering |
|---------------|-----------|
| `narration` | Standard text, natural paragraph spacing |
| `dialogue` | Slightly indented, optional speaker tag |
| `blue_box` | Styled card with border (LitRPG system message) |
| `scene_break` | Horizontal rule or centered `***` |
| `header` | Section heading |

### Annotation Toggles

Toolbar with toggles per entity type, count badges, color-coded.

### Inline vs Sidebar

- **Inline** (<=50 chars): names, skills, items → colored underline + hover card
- **Sidebar**: events, power progressions, foreshadowing → margin cards

### Mention Type Indicators

- `direct_name` / `langextract`: solid underline
- `alias`: dashed underline
- `pronoun`: subtle dotted (toggleable)

## 8. LangGraph Orchestration

```
START
  → [parallel] LangExtract passes 1-4 (characters, systems, events, lore)
  → merge_results
  → mention_detect (Pass 5, depends on extracted entities)
  → [parallel] narrative_analysis (Pass 6) + reconcile (Pass 7)
  → persist_to_neo4j
END
```

## 9. Cost Estimation

| Pass | LLM Calls | Est. Cost/Chapter |
|------|-----------|-----------|
| Pass 0 (Regex) | 0 | $0 |
| Passes 1-4 (LangExtract) | 4 parallel | ~$0.03 |
| Pass 5a (Mention Detection) | 0 | $0 |
| Pass 5b (Coreference) | 1-3 | ~$0.01 |
| Pass 6 (Narrative) | 1 | ~$0.01 |
| Pass 7 (Reconciliation) | 0-2 | ~$0.01 |
| **Total/chapter** | | **~$0.06** |
| **Full book (100 ch)** | | **~$6.00** |

## 10. Migration Phases

1. **Phase 1**: Structured epub ingestion (Paragraph nodes, HTML preserved)
2. **Phase 2**: LangExtract tuning (max_char_buffer, AlignmentStatus)
3. **Phase 3**: MENTIONED_IN storage (replace GROUNDED_IN, no merge expansion)
4. **Phase 4**: Mention Detection pass
5. **Phase 5**: Narrative Analysis pass
6. **Phase 6**: Reconciliation cross-book + Series support
7. **Phase 7**: Frontend reader redesign
8. **Phase 8**: Re-extract existing books
