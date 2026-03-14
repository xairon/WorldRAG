# WorldRAG Frontend v2 — Regression Analysis & Feature Roadmap

**2026-03-15 — Nicolas, LIFAT / Universite de Tours**

---

## 1. Context

The KG v2 migration (Graphiti + SagaProfileInducer + Project system) replaced the entire frontend. The old frontend had ~50 files covering book management, extraction monitoring, graph explorer, chat, reader, character pages, and pipeline dashboard. The new frontend has only the project system (dashboard + 4 tabs). **Critical user-facing features were lost.**

---

## 2. Features Lost in Migration

### 2.1 Book Ingestion Pipeline (CRITICAL)

**What existed:**
- Upload EPUB → automatic chapter parsing → chunk creation → regex pre-extraction → Neo4j storage
- Real-time progress bar during ingestion
- Chapter list with page counts after parsing
- Error reporting per chapter

**What exists now:**
- Upload stores file on disk + creates DB record
- File is NOT parsed into chapters
- No `ingest_file()` call — the bridge between upload and Graphiti extraction is broken
- User sees "Uploaded" but nothing actually happened

**Impact:** The entire pipeline is broken from the user's perspective. Upload does nothing useful.

### 2.2 Extraction Monitoring (CRITICAL)

**What existed:**
- Real-time extraction progress via SSE (Redis pub/sub)
- Per-chapter progress bar with entity count
- Entity type breakdown (Characters: 12, Skills: 8, Events: 15...)
- Cost tracking display ($ spent per chapter)
- Failed chapter indicators with DLQ retry button
- Extraction status badges (pending → extracting → extracted → embedded)
- Pipeline dashboard showing prompt templates, regex patterns, ontology tree

**What exists now:**
- "Start Extraction" button that enqueues a job
- No feedback after clicking — user has no idea if it's running, failed, or done
- No progress tracking
- No entity counts
- No cost display

**Impact:** User clicks "Extract" and stares at a static page with no feedback.

### 2.3 Book Detail Page (HIGH)

**What existed:**
- Book metadata (title, author, series, genre)
- Chapter list with status per chapter
- Entity statistics (total entities, by type)
- Extraction history (when extracted, cost, duration)
- Delete book button with confirmation

**What exists now:**
- Book card showing filename, size, upload date
- No chapter view
- No entity stats
- No delete

### 2.4 Graph Explorer (MEDIUM — partially preserved)

**What existed:**
- Full-bleed Sigma.js canvas with floating glass panels
- Book selector dropdown
- Entity type filter toggles
- Chapter range slider
- Full-text entity search with results dropdown
- Node detail panel (slide-in from right)
- Character profile in detail panel (skills, classes, titles, relationships)
- Zoom controls
- Stats display (nodes, edges count)

**What exists now:**
- Sigma.js in a 600px box (not full-bleed)
- Search bar
- Zoom controls
- Node detail panel
- No book selector (uses first book)
- No entity type filters
- No chapter range slider
- No character profile in detail panel (CharacterProfile API still exists but components deleted)

### 2.5 Chat (MEDIUM — partially preserved)

**What existed:**
- Thread sidebar with history
- Book selector
- Spoiler guard (chapter limiter)
- Source panel (collapsible, shows retrieved chunks)
- Citation highlights in responses
- Confidence badge per response
- Feedback buttons (thumbs up/down)
- SSE streaming with token + source events

**What exists now:**
- Thread sidebar
- Chat input + streaming
- No book selector (uses first book)
- No spoiler guard
- Source panel, citations, confidence, feedback components still exist but may not render correctly with ChatServiceV2 response format

### 2.6 Character Pages (LOW — genre-specific)

**What existed:**
- Character list page
- Character detail: stats, skills, classes, titles, equipment
- Chapter slider to see character state at any point
- State change timeline
- Character comparison

**What exists now:**
- Nothing — all character components deleted

### 2.7 Reader (LOW — was incomplete)

**What existed:**
- EPUB reader with annotated text
- Entity hover cards
- Annotation sidebar
- Chapter navigation

**What exists now:**
- Nothing — all reader components deleted

### 2.8 Search (MEDIUM)

**What existed:**
- Global search page with entity type filters
- Search results with entity badges
- Click to navigate to entity detail

**What exists now:**
- Nothing — search page deleted (graph search still works within the graph tab)

---

## 3. Features Required for Public-Facing Tool

### 3.1 Must Have (MVP)

#### 3.1.1 Working Upload → Parse → Extract Pipeline
- Upload EPUB → parse chapters automatically → show chapter list
- Real-time parsing progress (SSE or polling)
- Chapter count, word count displayed after parsing
- "Start Extraction" only enabled after parsing complete
- Extraction progress with per-chapter status (SSE)
- Entity count per chapter updating in real-time
- Clear status progression: uploading → parsing → ready → extracting → extracted
- Error handling with retry option per failed chapter

#### 3.1.2 Book Management
- Book detail view: metadata, chapters, entity stats
- Delete book from project (with confirmation dialog)
- Re-extract button (re-run extraction on already parsed book)
- Book status badges throughout the UI

#### 3.1.3 Extraction Dashboard
- Entity type breakdown chart (bar or donut)
- Total entities, relationships, communities
- Cost tracking (if API provides it)
- SagaProfile summary (types discovered, patterns found)
- Extraction history log

#### 3.1.4 Graph Explorer (restore full functionality)
- Full-bleed canvas (not boxed)
- Entity type filter toggles
- Chapter range slider (spoiler control)
- Book selector for multi-book sagas
- Character/entity detail panel with relationships
- Community clusters visualization

#### 3.1.5 Chat (restore full functionality)
- Book selector in chat
- Spoiler guard (chapter limiter)
- Source panel with retrieved chunks
- Citation highlights
- Confidence badge
- Feedback buttons
- Clear "no book extracted yet" state

#### 3.1.6 Profile Tab (enhance)
- Editable SagaProfile (add/remove entity types)
- Visual ontology graph (types + relations as a mini graph)
- Pattern tester (paste text, see which patterns match)
- Compare induced profile with actual entities in graph

### 3.2 Should Have (v1.0)

#### 3.2.1 Project Management
- Project settings page (rename, change description, cover image)
- Project deletion with full cascade confirmation
- Project duplication
- Export project (all data as archive)
- Import project from archive

#### 3.2.2 Multi-Book Saga Flow
- Clear "Book 1 = Discovery, Book 2+ = Guided" UX flow
- Side-by-side comparison of entity counts across books
- Timeline view spanning multiple books
- Cross-book entity resolution display

#### 3.2.3 Entity Browser
- Searchable entity list with filters (type, book, chapter range)
- Entity detail page (summary, relationships, mentions, timeline)
- Entity merge/split tool (manual entity resolution)
- Entity edit (correct name, add aliases)

#### 3.2.4 Dashboard Analytics
- Project-level analytics (entities over time, extraction costs)
- Global dashboard (all projects summary)
- Usage stats (queries, extractions, storage)

#### 3.2.5 Notifications
- Toast notifications for long-running operations
- Extraction complete notification
- Error alerts

### 3.3 Nice to Have (v1.1+)

#### 3.3.1 Reader Integration
- EPUB reader with entity annotations inline
- Click entity to see KG context
- Chapter-by-chapter reading with KG sidebar

#### 3.3.2 Wiki Auto-Generation
- Export KG as structured wiki (Markdown/HTML)
- Per-entity wiki pages
- Timeline page
- Character relationship map

#### 3.3.3 Collaboration
- Multi-user support
- Shared projects
- Comment/annotation system

#### 3.3.4 API Documentation
- Interactive API explorer (Swagger-like but integrated)
- API key management UI
- Webhook configuration

---

## 4. Technical Debt to Address

### 4.1 Backend Issues

| Issue | Priority |
|---|---|
| Upload doesn't call `ingest_file()` — chapters never parsed | CRITICAL |
| `process_book_graphiti` assumes chapters exist in Neo4j but upload doesn't create them | CRITICAL |
| Old backend routes (books.py extract endpoints) reference deleted extraction code | HIGH |
| No SSE progress endpoint for Graphiti extraction | HIGH |
| ChatServiceV2 response may not include all fields chat components expect | MEDIUM |
| Old backend services (graph_builder, reprocessing, etc.) still exist but are unused | LOW |

### 4.2 Frontend Issues

| Issue | Priority |
|---|---|
| No ingestion progress tracking | CRITICAL |
| No extraction progress tracking | CRITICAL |
| Graph explorer is boxed instead of full-bleed | MEDIUM |
| Chat missing spoiler guard, source panel rendering | MEDIUM |
| No book management (delete, re-extract) | MEDIUM |
| Entity type filter removed from graph | LOW |
| Character detail panel has no data source | LOW |

---

## 5. Recommended Implementation Order

### Sprint 1: Fix the Broken Pipeline (CRITICAL)
1. Wire `ingest_file()` into the upload endpoint → parse chapters + chunks
2. Add ingestion progress SSE endpoint
3. Add extraction progress SSE endpoint
4. Rebuild extraction progress component (entity counts per chapter)
5. Add book status tracking in UI (parsing → ready → extracting → done)

### Sprint 2: Restore Core UI Features
1. Book detail page (chapters, stats, metadata)
2. Graph explorer: restore full-bleed, filters, chapter slider
3. Chat: restore spoiler guard, source panel, confidence badge, feedback
4. Entity search within project

### Sprint 3: Polish for Public Release
1. Profile tab: visual ontology graph, pattern tester
2. Multi-book UX flow improvements
3. Project settings + deletion
4. KG export from UI (Cypher, JSON-LD, CSV download buttons)
5. Responsive design audit + mobile support
6. Error boundaries + loading states audit
7. Accessibility audit (aria labels, keyboard nav, screen reader)

### Sprint 4: Advanced Features
1. Entity browser with CRUD
2. Dashboard analytics
3. Wiki auto-generation
4. Reader integration
