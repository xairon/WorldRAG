# Pipeline Optimization Design — 2026-02-25

## Context

After running the full extraction pipeline on `tome1.epub` (11 chapters, French LitRPG), we identified 7 optimization areas. The pipeline extracted 917 entities but 3 chapters (2, 4, 8) produced 0 entities due to Gemini 503 errors and missing French keyword routing.

## Changes

### 1. French keyword support in extraction router (`router.py`)

Add French terms to SYSTEM_KEYWORDS, EVENT_KEYWORDS, LORE_KEYWORDS regex patterns. Single compile per category (EN + FR merged with `|`). Lower SYSTEM_THRESHOLD from 3 to 2 for LitRPG.

### 2. Structlog exc_info rendering (`logging.py`)

Add `structlog.processors.format_exc_info` to shared_processors so `logger.exception()` includes the full traceback in JSON logs.

### 3. Parallel chapter processing (`graph_builder.py`)

Replace sequential `for chapter in chapters` with `asyncio.Semaphore(3)` + `asyncio.gather()`. Collects results, handles errors per-chapter. 3 concurrent chapters respects Gemini rate limits.

### 4. French article normalization in dedup (`deduplication.py`)

Add French articles to `normalize_name()`: le, la, les, l', un, une, des, du, de, d'.

### 5. Missing Neo4j indexes (`init_neo4j.cypher`)

Add indexes: `Event.event_type`, `Skill.skill_type`, `Item.rarity`, compound `Character(role, first_appearance_chapter)`. Add fulltext indexes for Creature and Faction.

### 6. Retry wrapper for Gemini 503 (extraction passes)

Wrap `lx.extract()` with tenacity retry (3 attempts, exponential backoff 5s/15s/45s) in all 4 extraction pass files.

### 7. Error logging in graph builder (`graph_builder.py`)

Log warning when `extraction_result.errors` is non-empty after extraction returns.

## Files Modified

- `backend/app/services/extraction/router.py`
- `backend/app/core/logging.py`
- `backend/app/services/graph_builder.py`
- `backend/app/services/deduplication.py`
- `scripts/init_neo4j.cypher`
- `backend/app/services/extraction/characters.py`
- `backend/app/services/extraction/systems.py`
- `backend/app/services/extraction/events.py`
- `backend/app/services/extraction/lore.py`

## Non-Goals

- Full LangGraph checkpointing (requires PostgreSQL schema design)
- Chat/RAG implementation
- Book-level cross-chapter reconciliation (future pass)
