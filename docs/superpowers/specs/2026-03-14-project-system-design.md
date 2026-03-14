# Project System — Design Spec

**2026-03-14 — Nicolas, LIFAT / Universite de Tours**

---

## 1. Goal

Add a "Project" entity as the top-level organizational unit in WorldRAG. A project = a saga. It contains books, a SagaProfile, graph data, stored EPUB files, and chat threads. All data is scoped to the project via `project.slug` which maps directly to the existing `saga_id` / `group_id`.

---

## 2. Data Model

### Project

```
Project
  id:           UUID (PK, auto-generated)
  slug:         TEXT UNIQUE (url-safe, = saga_id = group_id)
  name:         TEXT (display name)
  description:  TEXT (optional)
  cover_image:  TEXT (optional, path to image)
  created_at:   TIMESTAMPTZ
  updated_at:   TIMESTAMPTZ
```

### ProjectFile

```
ProjectFile
  id:           UUID (PK)
  project_id:   UUID (FK → projects.id, CASCADE)
  filename:     TEXT (original filename)
  file_path:    TEXT (absolute path on filesystem)
  file_size:    BIGINT (bytes)
  mime_type:    TEXT (application/epub+zip, etc.)
  book_id:      TEXT (link to Neo4j Book node after parsing)
  book_num:     INTEGER (order in series)
  uploaded_at:  TIMESTAMPTZ
```

### Storage mapping

| Data | Storage | Key/Scope |
|------|---------|-----------|
| Project metadata | PostgreSQL `projects` table | `id` / `slug` |
| EPUB files | Filesystem `/data/projects/{slug}/files/` | file path |
| SagaProfile | Redis `saga_profile:{slug}` | existing, unchanged |
| Graph entities | Neo4j via Graphiti `group_id={slug}` | existing, unchanged |
| Chat threads | PostgreSQL checkpointing | `thread_id` prefixed with slug |
| Community summaries | Neo4j `:Community {saga_id={slug}}` | existing, unchanged |

### Key insight

`project.slug` = `saga_id` = Graphiti `group_id`. No new isolation mechanism. The Project is a metadata wrapper that formalizes what `saga_id` already does.

---

## 3. PostgreSQL Schema

```sql
-- Migration: 002_projects.sql

CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    cover_image TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS projects_slug_idx ON projects (slug);
CREATE INDEX IF NOT EXISTS projects_created_at_idx ON projects (created_at DESC);

CREATE TABLE IF NOT EXISTS project_files (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    file_size   BIGINT NOT NULL DEFAULT 0,
    mime_type   TEXT NOT NULL DEFAULT 'application/octet-stream',
    book_id     TEXT,
    book_num    INTEGER NOT NULL DEFAULT 1,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS project_files_project_id_idx ON project_files (project_id);
```

---

## 4. API Endpoints

### Project CRUD

```
POST   /api/projects                         → Create project
GET    /api/projects                         → List projects (with stats)
GET    /api/projects/{slug}                  → Project details + books + profile summary
PUT    /api/projects/{slug}                  → Update name/description
DELETE /api/projects/{slug}                  → Delete project + all data (cascade)
```

### Project-scoped resources

```
POST   /api/projects/{slug}/books            → Upload EPUB into project
GET    /api/projects/{slug}/books            → List books in project
POST   /api/projects/{slug}/books/{book_id}/extract  → Trigger Graphiti extraction
GET    /api/projects/{slug}/profile          → Get SagaProfile
PUT    /api/projects/{slug}/profile          → Update SagaProfile
GET    /api/projects/{slug}/graph            → Graph data (Sigma.js)
GET    /api/projects/{slug}/graph/search     → Search entities in project
POST   /api/projects/{slug}/chat/query       → Chat (scoped to project)
GET    /api/projects/{slug}/chat/stream      → SSE stream (scoped to project)
GET    /api/projects/{slug}/stats            → Extraction stats, entity counts, costs
```

### Backward compatibility

Existing endpoints (`/api/books`, `/api/chat/*`, `/api/saga-profiles/*`) continue working unchanged. New project-scoped endpoints coexist alongside them. Migration is gradual — the frontend switches to project-scoped routes, old routes are deprecated but not removed.

---

## 5. API Schemas

```python
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    description: str = ""

class ProjectResponse(BaseModel):
    id: str  # UUID as string
    slug: str
    name: str
    description: str
    cover_image: str | None
    created_at: datetime
    updated_at: datetime
    books_count: int = 0
    has_profile: bool = False
    entity_count: int = 0

class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class ProjectBookUpload(BaseModel):
    # Multipart form: file + metadata
    book_num: int = 1
    title: str = ""
    author: str = ""

class ProjectStatsResponse(BaseModel):
    slug: str
    books_count: int
    chapters_total: int
    entities_total: int
    community_count: int
    has_profile: bool
    profile_types_count: int
    extraction_cost_usd: float
```

---

## 6. File Storage

### Directory structure

```
/data/projects/
  primal-hunter/
    files/
      primal-hunter-book-1.epub
      primal-hunter-book-2.epub
  harry-potter/
    files/
      philosophers-stone.epub
```

### Config

New setting in `config.py`:
```python
project_data_dir: str = "/data/projects"
```

In Docker Compose, mount as a named volume:
```yaml
backend:
  volumes:
    - project_data:/data/projects

volumes:
  project_data:
```

---

## 7. Frontend

### Routes

```
/                              → Dashboard: project cards grid
/projects/{slug}               → Project view: tabs (Books | Graph | Chat | Profile)
/projects/{slug}/books         → Book list + upload dropzone
/projects/{slug}/graph         → Sigma.js scoped to project
/projects/{slug}/chat          → Chat scoped to project
/projects/{slug}/profile       → SagaProfile viewer/editor
```

### Dashboard

Grid of project cards showing:
- Project name
- Book count
- Entity count
- SagaProfile status (induced / not yet)
- Last activity timestamp
- "New Project" card with + icon

### Project view

Tabbed layout:
- **Books** tab: list of books with status (uploaded / extracting / extracted), upload dropzone
- **Graph** tab: existing Sigma.js explorer, scoped to `group_id={slug}`
- **Chat** tab: existing chat UI, scoped to project
- **Profile** tab: SagaProfile viewer showing induced types, patterns, relations

---

## 8. Extraction Flow (updated)

```
1. User creates project "primal-hunter"
   → INSERT INTO projects (slug, name)

2. User uploads primal-hunter-book-1.epub
   → Store file in /data/projects/primal-hunter/files/
   → INSERT INTO project_files
   → Parse EPUB → chapters → chunks → Neo4j (existing pipeline)
   → Link book_id back to project_files row

3. User clicks "Extract"
   → POST /api/projects/primal-hunter/books/{book_id}/extract
   → Enqueue process_book_graphiti(saga_id="primal-hunter", ...)
   → Discovery Mode (first book) → SagaProfile induced
   → Community clustering

4. User uploads book 2
   → Same flow but Guided Mode (SagaProfile exists)

5. User chats
   → POST /api/projects/primal-hunter/chat/query
   → ChatServiceV2 with saga_id="primal-hunter"
```

---

## 9. Project Deletion

Cascade delete:
1. Delete all `project_files` rows (PostgreSQL CASCADE)
2. Delete stored EPUB files from filesystem
3. Delete SagaProfile from Redis (`saga_profile:{slug}`)
4. Delete entities from Neo4j: `MATCH (n {group_id: $slug}) DETACH DELETE n`
5. Delete community nodes: `MATCH (c:Community {saga_id: $slug}) DELETE c`
6. Delete project row from PostgreSQL

This is a destructive operation — requires admin auth + confirmation.

---

## 10. New Files

| File | Role |
|------|------|
| `scripts/migrations/002_projects.sql` | PostgreSQL DDL |
| `backend/app/schemas/project.py` | API schemas |
| `backend/app/api/routes/projects.py` | Project CRUD + scoped endpoints |
| `backend/app/repositories/project_repo.py` | PostgreSQL project queries |
| `backend/app/services/project_service.py` | Business logic (create, delete cascade, stats) |
| `frontend/app/page.tsx` | Dashboard (project grid) |
| `frontend/app/projects/[slug]/layout.tsx` | Project layout (tabs) |
| `frontend/app/projects/[slug]/page.tsx` | Project overview |
| `frontend/app/projects/[slug]/books/page.tsx` | Books tab |
| `frontend/app/projects/[slug]/graph/page.tsx` | Graph tab |
| `frontend/app/projects/[slug]/chat/page.tsx` | Chat tab |
| `frontend/app/projects/[slug]/profile/page.tsx` | Profile tab |
| `frontend/components/projects/project-card.tsx` | Dashboard card |
| `frontend/components/projects/create-project-dialog.tsx` | New project modal |
| `frontend/stores/project-store.ts` | Zustand project state |
| `backend/tests/test_project_api.py` | API tests |
| `backend/tests/test_project_service.py` | Service tests |

## 11. Modified Files

| File | Changes |
|------|---------|
| `backend/app/main.py` | Register projects router |
| `backend/app/config.py` | Add `project_data_dir` setting |
| `docker-compose.prod.yml` | Add `project_data` volume |

---

## 12. What does NOT change

- Graphiti client and ingestion orchestrator (already use `saga_id`)
- SagaProfileInducer (already uses `saga_id`)
- Chat pipeline v2 (already uses `saga_id`)
- Community clustering (already uses `saga_id`)
- Redis saga profile storage (key format unchanged)
- Neo4j schema (Graphiti manages it)
