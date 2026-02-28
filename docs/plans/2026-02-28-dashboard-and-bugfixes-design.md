# Dashboard Extraction & Bugfixes Design

**Date**: 2026-02-28
**Status**: Approved

## Problem Statement

Three issues identified in the frontend:

1. **Characters page shows mixed entity types** — Backend `/graph/subgraph` returns both nodes of each relationship, so filtering by `label=Character` returns Characters AND their connected Events, Concepts, Skills, etc.
2. **Duplicate React key in Entity Wiki page** — `key={app.chapter}` causes collisions when an entity has multiple relationships to the same chapter.
3. **Extraction progress is a blind spinner** — No percentage, no per-chapter status, no entity counts, no DLQ visibility.

## Design

### Part 1: Bug Fixes (Quick)

#### 1A. New `/api/graph/entities` endpoint

Create a proper entity listing endpoint instead of reusing subgraph for entity lists.

```
GET /api/graph/entities?book_id=X&label=Character&limit=50&offset=0
```

Returns:
```json
{
  "entities": [
    {"id": "...", "name": "Jake", "labels": ["Character"], "description": "...", "canonical_name": "jake"}
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

Cypher:
```cypher
MATCH (n:Character {book_id: $book_id})
RETURN n
ORDER BY n.name
SKIP $offset LIMIT $limit
```

Frontend Characters page calls this instead of `getSubgraph()`.

#### 1B. Fix duplicate key in Wiki page

Change from `key={app.chapter}` to `key={index}` and deduplicate appearances array using `DISTINCT` in backend Cypher query.

### Part 2: Extraction Dashboard

#### Data Sources

- **Progress bar + %**: SSE stream (`/stream/extraction/{book_id}`) already provides `chapters_done/total` — wire it up properly
- **Entity counts by type**: `GET /graph/stats?book_id=X` — already exists, returns `{Character: 42, Skill: 87, ...}`
- **Per-chapter status**: `GET /books/{book_id}` — already returns chapter list with `status` and `entity_count`
- **DLQ**: `GET /admin/dlq?book_id=X` — already exists, returns failed chapters with error messages

#### UI Layout

```
┌──────────────────────────────────────────────────────┐
│  Primal Hunter Tome 1          Status: Extracting    │
├──────────────────────────────────────────────────────┤
│  ████████████░░░░░░░░░░░░░  Chapitre 12/74 (16%)    │
│  ~45 min restantes                                    │
├──────────────────────────────────────────────────────┤
│  Entity Counts                                        │
│  👤 35 Characters · ⚔️ 87 Skills · 🏰 2 Locations    │
│  🎯 78 Events · 🛡️ 43 Classes · 👑 13 Titles         │
│  📦 1 Items · 💡 26 Concepts                          │
├──────────────────────────────────────────────────────┤
│  Chapter Progress                                     │
│  ┌─────┬────────────────────┬────────┬───────────┐   │
│  │  #  │ Title              │ Status │ Entities  │   │
│  ├─────┼────────────────────┼────────┼───────────┤   │
│  │  1  │ Jour J             │  ✅    │ 26        │   │
│  │  2  │ Tutoriel           │  ✅    │ 111       │   │
│  │  3  │ Première bataille  │  ✅    │ 118       │   │
│  │  4  │ Première chasse    │  🔄    │ ...       │   │
│  │  5  │ ...                │  ⏳    │ —         │   │
│  └─────┴────────────────────┴────────┴───────────┘   │
├──────────────────────────────────────────────────────┤
│  ❌ Failed Chapters (DLQ)                             │
│  Ch. 15 — JSONDecodeError: Unterminated string...     │
│  [Retry] [Retry All]                                  │
└──────────────────────────────────────────────────────┘
```

#### Polling Strategy

- During `extracting` status: poll `/books/{id}` every 5s for chapter statuses + `/graph/stats` every 10s for entity counts
- SSE stream for real-time progress bar updates
- Once `extracted`: stop polling, show final state
- DLQ section: only shown when there are failed chapters

#### Components

1. `ExtractionDashboard` — main container, manages polling
2. `ProgressBar` — animated bar with % and ETA
3. `EntityCountBadges` — colored badges per type
4. `ChapterTable` — sortable table with status icons
5. `DLQSection` — failed chapters with retry buttons

### Part 3: Subgraph label filter fix

Also fix the existing subgraph Cypher to only return nodes matching the label filter (for the graph explorer), even though Characters page will use the new endpoint.

## Implementation Order

1. Backend: New `/graph/entities` endpoint
2. Backend: Fix subgraph Cypher label filter
3. Backend: Ensure DLQ endpoint returns useful error messages
4. Frontend: Fix Characters page to use new endpoint
5. Frontend: Fix Wiki page duplicate key
6. Frontend: Build ExtractionDashboard components
7. Test everything end-to-end
