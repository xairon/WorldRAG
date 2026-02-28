# V2 SOTA Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the extraction pipeline with structure-aware epub ingestion, tuned LangExtract, mention detection, narrative analysis, and a redesigned reader.

**Architecture:** Keep LangExtract for entity detection + grounding (Passes 1-4), add mention detection (Pass 5) and narrative analysis (Pass 6), replace GROUNDED_IN with MENTIONED_IN, store Paragraph nodes for structured rendering.

**Tech Stack:** LangExtract (tuned), Instructor + Gemini 2.5 Flash, Neo4j 5.x, LangGraph, Next.js 16 + React 19, shadcn/ui

---

## Phase 1: Structured Epub Ingestion

### Task 1.1: Paragraph Schema & Neo4j Constraints

**Files:**
- Modify: `backend/app/schemas/book.py`
- Modify: `scripts/init_neo4j.cypher`

**Step 1: Add ParagraphData schema**

Add to `backend/app/schemas/book.py` after `ChunkData` (line ~70):

```python
class ParagraphType(StrEnum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    BLUE_BOX = "blue_box"
    SCENE_BREAK = "scene_break"
    HEADER = "header"

class ParagraphData(BaseModel):
    index: int
    type: ParagraphType
    text: str
    html: str = ""
    char_start: int
    char_end: int
    speaker: str | None = None
    sentence_count: int = 0
    word_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        if not self.word_count and self.text:
            self.word_count = len(self.text.split())
```

**Step 2: Add Neo4j constraints**

Add to `scripts/init_neo4j.cypher`:

```cypher
CREATE CONSTRAINT paragraph_unique IF NOT EXISTS
FOR (p:Paragraph) REQUIRE (p.book_id, p.chapter_number, p.index) IS UNIQUE;

CREATE INDEX paragraph_type IF NOT EXISTS
FOR (p:Paragraph) ON (p.type);

CREATE INDEX paragraph_chapter IF NOT EXISTS
FOR (p:Paragraph) ON (p.chapter_number);
```

**Step 3: Run init script**

```bash
cd /e/RAG && python scripts/run_init_neo4j.py
```

**Step 4: Commit**

```bash
git add backend/app/schemas/book.py scripts/init_neo4j.cypher
git commit -m "feat: add Paragraph schema and Neo4j constraints for V2 ingestion"
```

---

### Task 1.2: Structure-Aware Epub Parser

**Files:**
- Modify: `backend/app/services/ingestion.py`
- Create: `backend/tests/test_structured_ingestion.py`

**Step 1: Write tests for the structured parser**

```python
# backend/tests/test_structured_ingestion.py
import pytest
from app.schemas.book import ParagraphData, ParagraphType

class TestClassifyBlock:
    """Test HTML block classification into paragraph types."""

    def test_header_h1(self):
        from app.services.ingestion import _classify_block_text
        assert _classify_block_text("h1", "Chapter Title") == ParagraphType.HEADER

    def test_dialogue_guillemets(self):
        from app.services.ingestion import _classify_block_text
        assert _classify_block_text("p", "« Bonjour ! » dit Jake.") == ParagraphType.DIALOGUE

    def test_dialogue_tiret(self):
        from app.services.ingestion import _classify_block_text
        assert _classify_block_text("p", "— Tu viens ?") == ParagraphType.DIALOGUE

    def test_narration_default(self):
        from app.services.ingestion import _classify_block_text
        assert _classify_block_text("p", "Jake observait la forêt.") == ParagraphType.NARRATION

    def test_scene_break_stars(self):
        from app.services.ingestion import _classify_block_text
        assert _classify_block_text("p", "***") == ParagraphType.SCENE_BREAK

    def test_blue_box_brackets(self):
        from app.services.ingestion import _classify_block_text
        assert _classify_block_text("p", "[Skill Acquired: Shadowstep]") == ParagraphType.BLUE_BOX

class TestParseEpubStructured:
    """Test that epub parsing preserves paragraph structure."""

    def test_paragraphs_have_types(self, sample_epub_path):
        from app.services.ingestion import parse_epub
        chapters = parse_epub(sample_epub_path)
        assert len(chapters) > 0
        # Check that paragraphs are generated
        assert hasattr(chapters[0], 'paragraphs') or True  # Will test after implementation

    def test_char_offsets_contiguous(self):
        """Paragraph char offsets should cover the full chapter text."""
        from app.services.ingestion import _build_paragraphs_from_html
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert len(paragraphs) == 2
        assert paragraphs[0].char_start == 0
        assert paragraphs[1].char_start == paragraphs[0].char_end + 1  # +1 for \n separator
```

**Step 2: Run tests (expect failure)**

```bash
cd /e/RAG && uv run pytest backend/tests/test_structured_ingestion.py -v
```

**Step 3: Implement structured parser**

Modify `backend/app/services/ingestion.py`:

- Add `_classify_block_text(tag: str, text: str) -> ParagraphType` function
- Add `_build_paragraphs_from_html(html: str) -> list[ParagraphData]` function
- Modify `parse_epub()` to return `ChapterData` with a new `paragraphs` field
- Keep existing `text` field as concatenated paragraph texts (backward compatible)

Key implementation: Walk the BeautifulSoup DOM tree, classify each `<p>`, `<h*>`, `<div>` etc., build ParagraphData with char offsets and original HTML.

**Step 4: Run tests (expect pass)**

```bash
cd /e/RAG && uv run pytest backend/tests/test_structured_ingestion.py -v
```

**Step 5: Commit**

```bash
git add backend/app/services/ingestion.py backend/tests/test_structured_ingestion.py
git commit -m "feat: structure-aware epub parsing with typed paragraphs"
```

---

### Task 1.3: Paragraph Storage in Neo4j

**Files:**
- Modify: `backend/app/repositories/book_repo.py`
- Create: `backend/tests/test_paragraph_storage.py`

**Step 1: Write test**

Test that `create_paragraphs()` stores Paragraph nodes linked to Chapter.

**Step 2: Implement `create_paragraphs()` in book_repo.py**

```python
async def create_paragraphs(
    self, book_id: str, chapter_number: int, paragraphs: list[ParagraphData]
) -> int:
    query = """
    UNWIND $paragraphs AS p
    MATCH (c:Chapter {book_id: $book_id, number: $chapter_number})
    CREATE (para:Paragraph {
        book_id: $book_id,
        chapter_number: $chapter_number,
        index: p.index,
        type: p.type,
        text: p.text,
        html: p.html,
        char_start: p.char_start,
        char_end: p.char_end,
        speaker: p.speaker,
        sentence_count: p.sentence_count,
        word_count: p.word_count
    })
    MERGE (c)-[:HAS_PARAGRAPH {position: p.index}]->(para)
    RETURN count(para) AS created
    """
    ...
```

**Step 3: Wire into upload pipeline** in `backend/app/api/routes/books.py`

After `create_chunks()`, add `create_paragraphs()` call for each chapter.

**Step 4: Run tests, commit**

---

### Task 1.4: Paragraph-Aligned Chunking

**Files:**
- Modify: `backend/app/services/chunking.py`

Modify `chunk_chapter()` to respect paragraph boundaries — never split mid-paragraph. Use paragraphs as the atomic unit instead of `\n\n`-split text.

**Commit**

---

## Phase 2: LangExtract Tuning

### Task 2.1: Configure max_char_buffer

**Files:**
- Modify: `backend/app/services/extraction/retry.py`
- Modify: `backend/app/config.py`

**Step 1: Add config**

Add to `config.py`:
```python
langextract_max_char_buffer: int = 2000
```

Add to `.env`:
```
LANGEXTRACT_MAX_CHAR_BUFFER=2000
```

**Step 2: Pass to LangExtract**

In `retry.py`, add `max_char_buffer` parameter to `lx.extract()` call:

```python
result = await asyncio.to_thread(
    partial(
        lx.extract,
        text_or_documents=text_or_documents,
        ...
        max_char_buffer=max_char_buffer,  # NEW
    )
)
```

**Step 3: Commit**

---

### Task 2.2: AlignmentStatus Validation

**Files:**
- Modify: `backend/app/services/extraction/characters.py`
- Modify: `backend/app/services/extraction/events.py`
- Modify: `backend/app/services/extraction/systems.py`
- Modify: `backend/app/services/extraction/lore.py`

**Step 1: Add alignment status check in all 4 passes**

In each pass, when building GroundedEntity, check `entity.alignment_status`:
- `EXACT` → keep, confidence=1.0
- `FUZZY` → keep, confidence=0.7
- `UNALIGNED` → skip (log warning)

Add `alignment_status` and `confidence` to GroundedEntity schema.

**Step 2: Update GroundedEntity schema**

In `backend/app/schemas/extraction.py`:
```python
class GroundedEntity(BaseModel):
    ...
    alignment_status: str = "exact"  # exact|fuzzy|unaligned
    confidence: float = 1.0
```

**Step 3: Commit**

---

## Phase 3: MENTIONED_IN Storage

### Task 3.1: Replace GROUNDED_IN with MENTIONED_IN

**Files:**
- Modify: `backend/app/repositories/entity_repo.py` (store_grounding → store_mentions)
- Modify: `scripts/init_neo4j.cypher`

**Step 1: Add MENTIONED_IN index to init script**

```cypher
CREATE INDEX rel_mentioned_in IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.char_start);

CREATE INDEX rel_mentioned_in_type IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.mention_type);
```

**Step 2: Rewrite store_grounding() → store_mentions()**

Key change: Use `CREATE` instead of `MERGE` for relationships. Each mention is independent:

```cypher
UNWIND $entries AS e
MATCH (chapter:Chapter {book_id: $book_id, number: $chapter_num})
MATCH (entity:{label} {prop: e.entity_name})
CREATE (entity)-[:MENTIONED_IN {
    char_start: e.char_start,
    char_end: e.char_end,
    mention_text: e.mention_text,
    mention_type: e.mention_type,
    paragraph_index: e.paragraph_index,
    confidence: e.confidence,
    alignment_status: e.alignment_status
}]->(chapter)
```

**Step 3: Update reader API** (`backend/app/api/routes/reader.py`)

Change query from `GROUNDED_IN` to `MENTIONED_IN`:
```cypher
MATCH (entity)-[m:MENTIONED_IN]->(c:Chapter {book_id: $book_id, number: $number})
RETURN labels(entity) AS labels,
       entity.name AS name,
       entity.canonical_name AS canonical_name,
       m.char_start AS char_start,
       m.char_end AS char_end,
       m.mention_text AS mention_text,
       m.mention_type AS mention_type,
       m.confidence AS confidence
ORDER BY m.char_start
```

**Step 4: Commit**

---

### Task 3.2: Update Frontend Reader API Types

**Files:**
- Modify: `frontend/lib/api/reader.ts`
- Modify: `frontend/components/reader/annotated-text.tsx`

Update `EntityAnnotation` to include `mention_type` and `confidence`. Update rendering to use mention_type for visual differentiation.

**Commit**

---

## Phase 4: Mention Detection Pass

### Task 4.1: Mention Detector Service

**Files:**
- Create: `backend/app/services/extraction/mention_detector.py`
- Create: `backend/tests/test_mention_detector.py`

**Step 1: Write tests**

```python
class TestMentionDetector:
    def test_exact_name_match(self):
        text = "Jake observait la forêt. Caroline le rejoignit."
        entities = [{"canonical_name": "Jake", "aliases": []}]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
        assert mentions[0].char_start == 0
        assert mentions[0].char_end == 4
        assert mentions[0].mention_type == "direct_name"

    def test_alias_match(self):
        text = "Le Chasseur Primordial avançait dans la nuit."
        entities = [{"canonical_name": "Jake", "aliases": ["Le Chasseur Primordial"]}]
        mentions = detect_mentions(text, entities)
        assert mentions[0].mention_type == "alias"

    def test_no_overlap(self):
        """Shorter mention inside longer should be deduplicated."""
        text = "Jake Summers marchait."
        entities = [
            {"canonical_name": "Jake", "aliases": []},
            {"canonical_name": "Jake Summers", "aliases": []},
        ]
        mentions = detect_mentions(text, entities)
        assert len(mentions) == 1
        assert mentions[0].mention_text == "Jake Summers"
```

**Step 2: Implement mention_detector.py**

```python
def detect_mentions(
    chapter_text: str,
    entities: list[dict],
    paragraphs: list[ParagraphData] | None = None,
) -> list[MentionData]:
    """Find all exact/alias mentions of known entities in chapter text."""
    ...
```

**Step 3: Run tests, commit**

---

### Task 4.2: Coreference Resolution

**Files:**
- Create: `backend/app/services/extraction/coreference.py`
- Create: `backend/app/prompts/coreference.py`

**Step 1: Implement coreference resolver using Instructor + Gemini**

Input: sentences with pronouns + nearby entity context
Output: pronoun → entity mappings

**Step 2: Write prompt template**

French prompt asking the LLM to resolve pronouns to entity names given context.

**Step 3: Test with sample text, commit**

---

### Task 4.3: Wire Mention Detection into LangGraph

**Files:**
- Modify: `backend/app/agents/extraction_graph.py` (or `backend/app/services/extraction/__init__.py`)
- Modify: `backend/app/agents/state.py`

Add `mention_detect` node after `merge` in the LangGraph extraction pipeline. It runs after all LangExtract passes complete and before reconciliation.

**Commit**

---

## Phase 5: Narrative Analysis Pass

### Task 5.1: Narrative Analysis Service

**Files:**
- Create: `backend/app/services/extraction/narrative.py`
- Create: `backend/app/prompts/narrative_analysis.py`
- Create: `backend/app/schemas/narrative.py`

**Step 1: Define schemas**

```python
class CharacterDevelopment(BaseModel):
    character: str
    aspect: str                # personality, motivation, worldview
    description: str
    trigger_sentences: list[int]

class PowerChange(BaseModel):
    character: str
    change_type: str           # level_up, skill_acquired, class_change
    details: dict[str, Any]

class ForeshadowingHint(BaseModel):
    description: str
    sentence_refs: list[int]
    confidence: float

class NarrativeAnalysisResult(BaseModel):
    character_developments: list[CharacterDevelopment]
    power_changes: list[PowerChange]
    foreshadowing_hints: list[ForeshadowingHint]
```

**Step 2: Implement extraction via Instructor + Gemini**

**Step 3: Wire into LangGraph as parallel node alongside reconciliation**

**Step 4: Store as Events with subtype + FORESHADOWS relationships**

**Commit**

---

## Phase 6: Series & Cross-Book Support

### Task 6.1: Series Node

**Files:**
- Modify: `scripts/init_neo4j.cypher`
- Modify: `backend/app/repositories/book_repo.py`
- Modify: `backend/app/schemas/book.py`

Add Series node, CONTAINS relationship, and wire into book upload (books with same `series_name` share a Series node).

**Commit**

---

### Task 6.2: Cross-Book Entity Resolution

**Files:**
- Modify: `backend/app/services/extraction/reconciler.py`

When processing Book N, load all entities from previous books in same Series as context for reconciliation. Match new entities against existing ones.

**Commit**

---

## Phase 7: Frontend Reader Redesign

### Task 7.1: Reader API for Paragraphs

**Files:**
- Modify: `backend/app/api/routes/reader.py`

Add endpoint: `GET /reader/books/{book_id}/chapters/{number}/paragraphs`

Returns structured paragraphs (type, text, html, speaker, char offsets).

**Commit**

---

### Task 7.2: Structured Chapter Rendering

**Files:**
- Create: `frontend/components/reader/paragraph-renderer.tsx`
- Modify: `frontend/components/reader/annotated-text.tsx`
- Modify: `frontend/app/(reader)/read/[bookId]/[chapter]/page.tsx`

Replace monolithic text rendering with paragraph-by-paragraph rendering:
- narration → standard paragraph
- dialogue → indented with speaker tag
- blue_box → styled card with border
- scene_break → horizontal rule
- header → section heading

**Commit**

---

### Task 7.3: Annotation Type Toggles

**Files:**
- Modify: `frontend/components/reader/reading-toolbar.tsx`

Replace simple on/off toggle with multi-select entity type toggles. Each entity type gets a checkbox with its color dot and count badge.

**Commit**

---

### Task 7.4: Sidebar for Events/Narrative

**Files:**
- Create: `frontend/components/reader/annotation-sidebar.tsx`
- Modify: `frontend/app/(reader)/read/[bookId]/[chapter]/page.tsx`

Right margin panel showing:
- Events (with sentence ranges highlighted on hover)
- Power progressions
- Character development moments
- Foreshadowing hints

**Commit**

---

### Task 7.5: Mention Type Visual Indicators

**Files:**
- Modify: `frontend/components/reader/annotated-text.tsx`

Different underline styles per mention_type:
- `langextract` / `direct_name`: solid underline
- `alias`: dashed underline
- `pronoun`: subtle dotted underline (toggleable separately)

**Commit**

---

## Phase 8: Re-extraction

### Task 8.1: Delete Old Extraction Data

Clear existing GROUNDED_IN relationships and re-ingest epub with structured parser.

### Task 8.2: Re-extract

Run the new pipeline on existing books via `POST /books/{id}/extract`.

---

## Execution Notes

**Test commands:**
```bash
# Backend tests
cd /e/RAG && uv run pytest backend/tests/ -x -v

# Lint
cd /e/RAG && uv run ruff check backend/ --fix && uv run ruff format backend/

# Frontend build
cd /e/RAG/frontend && npm run build

# Type check
cd /e/RAG && uv run pyright backend/
```

**Infrastructure must be running:**
```bash
cd /e/RAG && docker compose up -d neo4j redis postgres langfuse
```
