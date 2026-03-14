# Project System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Project entity as the top-level organizational unit — a project = a saga, containing books, a SagaProfile, graph data, stored EPUB files, and chat threads. `project.slug` maps to `saga_id` / `group_id`.

**Architecture:** PostgreSQL `projects` + `project_files` tables for metadata and file tracking. Filesystem storage for EPUBs under `/data/projects/{slug}/files/`. Project-scoped API endpoints that delegate to existing Graphiti/SagaProfile/Chat services using `slug` as `saga_id`. Frontend dashboard with project cards and tabbed project view.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, filesystem storage, Next.js 16, Zustand.

**Spec:** `docs/superpowers/specs/2026-03-14-project-system-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `scripts/migrations/002_projects.sql` | PostgreSQL DDL for projects + project_files |
| `backend/app/schemas/project.py` | API request/response schemas |
| `backend/app/repositories/project_repo.py` | PostgreSQL CRUD queries |
| `backend/app/services/project_service.py` | Business logic (create, delete cascade, stats) |
| `backend/app/api/routes/projects.py` | All project endpoints (CRUD + scoped resources) |
| `backend/tests/test_project_repo.py` | Repository tests |
| `backend/tests/test_project_service.py` | Service tests |
| `backend/tests/test_project_api.py` | API endpoint tests |
| `frontend/app/page.tsx` | Dashboard (project grid) — replaces current home |
| `frontend/app/projects/[slug]/layout.tsx` | Project layout with tabs |
| `frontend/app/projects/[slug]/page.tsx` | Project overview (redirect to books) |
| `frontend/app/projects/[slug]/books/page.tsx` | Books tab |
| `frontend/app/projects/[slug]/graph/page.tsx` | Graph tab |
| `frontend/app/projects/[slug]/chat/page.tsx` | Chat tab |
| `frontend/app/projects/[slug]/profile/page.tsx` | Profile tab |
| `frontend/components/projects/project-card.tsx` | Dashboard card component |
| `frontend/components/projects/create-project-dialog.tsx` | New project modal |
| `frontend/stores/project-store.ts` | Zustand project state |
| `frontend/lib/api/projects.ts` | API client for projects |

### Modified files

| File | Changes |
|---|---|
| `backend/app/main.py` | Register projects router |
| `backend/app/config.py` | Add `project_data_dir` setting |
| `docker-compose.prod.yml` | Add `project_data` volume |

---

## Chunk 1: Backend — Database + Repository + Schemas

### Task 1: PostgreSQL migration

**Files:**
- Create: `scripts/migrations/002_projects.sql`

- [ ] **Step 1: Create migration file**

```sql
-- 002_projects.sql
-- Project system: projects + file tracking

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

- [ ] **Step 2: Commit**

```bash
git add scripts/migrations/002_projects.sql
git commit -m "feat(db): add projects + project_files migration"
```

---

### Task 2: Project API schemas

**Files:**
- Create: `backend/app/schemas/project.py`

- [ ] **Step 1: Create schemas**

```python
# backend/app/schemas/project.py
"""API schemas for project endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    cover_image: str | None = None
    created_at: datetime
    updated_at: datetime
    books_count: int = 0
    has_profile: bool = False
    entity_count: int = 0


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class ProjectFileResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    mime_type: str
    book_id: str | None = None
    book_num: int
    uploaded_at: datetime


class ProjectStatsResponse(BaseModel):
    slug: str
    books_count: int
    chapters_total: int
    entities_total: int
    community_count: int
    has_profile: bool
    profile_types_count: int
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/project.py
git commit -m "feat(schemas): add project API schemas"
```

---

### Task 3: Project repository

**Files:**
- Create: `backend/app/repositories/project_repo.py`
- Create: `backend/tests/test_project_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_project_repo.py
"""Tests for ProjectRepository."""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.repositories.project_repo import ProjectRepository


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    return pool


class TestProjectRepo:
    @pytest.mark.asyncio
    async def test_create_project(self, mock_pool):
        row = {
            "id": uuid4(), "slug": "test-saga", "name": "Test Saga",
            "description": "", "cover_image": None,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }
        mock_pool.fetchrow = AsyncMock(return_value=row)
        repo = ProjectRepository(mock_pool)
        result = await repo.create("test-saga", "Test Saga", "")
        assert result["slug"] == "test-saga"
        mock_pool.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_slug(self, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={"slug": "test", "name": "Test"})
        repo = ProjectRepository(mock_pool)
        result = await repo.get_by_slug("test")
        assert result["slug"] == "test"

    @pytest.mark.asyncio
    async def test_get_by_slug_not_found(self, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value=None)
        repo = ProjectRepository(mock_pool)
        result = await repo.get_by_slug("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, mock_pool):
        mock_pool.fetch = AsyncMock(return_value=[
            {"slug": "a", "name": "A"}, {"slug": "b", "name": "B"}
        ])
        repo = ProjectRepository(mock_pool)
        result = await repo.list_all()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_delete(self, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value="test-saga")
        repo = ProjectRepository(mock_pool)
        result = await repo.delete("test-saga")
        assert result == "test-saga"

    @pytest.mark.asyncio
    async def test_add_file(self, mock_pool):
        row = {"id": uuid4(), "filename": "book.epub", "file_size": 1024}
        mock_pool.fetchrow = AsyncMock(return_value=row)
        repo = ProjectRepository(mock_pool)
        result = await repo.add_file(
            project_id=str(uuid4()), filename="book.epub",
            file_path="/data/projects/test/files/book.epub",
            file_size=1024, mime_type="application/epub+zip", book_num=1,
        )
        assert result["filename"] == "book.epub"

    @pytest.mark.asyncio
    async def test_list_files(self, mock_pool):
        mock_pool.fetch = AsyncMock(return_value=[
            {"filename": "book1.epub"}, {"filename": "book2.epub"}
        ])
        repo = ProjectRepository(mock_pool)
        result = await repo.list_files(str(uuid4()))
        assert len(result) == 2
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run python -m pytest backend/tests/test_project_repo.py -v
```

- [ ] **Step 3: Write implementation**

```python
# backend/app/repositories/project_repo.py
"""PostgreSQL repository for projects and project files."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    import asyncpg

logger = get_logger(__name__)


class ProjectRepository:
    """CRUD operations for projects and project_files tables."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(self, slug: str, name: str, description: str = "") -> dict[str, Any]:
        row = await self.pool.fetchrow(
            """
            INSERT INTO projects (slug, name, description)
            VALUES ($1, $2, $3)
            RETURNING id, slug, name, description, cover_image, created_at, updated_at
            """,
            slug, name, description,
        )
        return dict(row)

    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM projects WHERE slug = $1", slug,
        )
        return dict(row) if row else None

    async def list_all(self) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT * FROM projects ORDER BY created_at DESC",
        )
        return [dict(r) for r in rows]

    async def update(self, slug: str, **fields: Any) -> dict[str, Any] | None:
        sets = []
        params = []
        idx = 1
        for key, value in fields.items():
            if value is not None:
                sets.append(f"{key} = ${idx}")
                params.append(value)
                idx += 1
        if not sets:
            return await self.get_by_slug(slug)
        sets.append(f"updated_at = NOW()")
        params.append(slug)
        query = f"""
            UPDATE projects SET {', '.join(sets)}
            WHERE slug = ${idx}
            RETURNING id, slug, name, description, cover_image, created_at, updated_at
        """
        row = await self.pool.fetchrow(query, *params)
        return dict(row) if row else None

    async def delete(self, slug: str) -> str | None:
        return await self.pool.fetchval(
            "DELETE FROM projects WHERE slug = $1 RETURNING slug", slug,
        )

    # --- Project Files ---

    async def add_file(
        self,
        project_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        book_num: int = 1,
    ) -> dict[str, Any]:
        row = await self.pool.fetchrow(
            """
            INSERT INTO project_files (project_id, filename, file_path, file_size, mime_type, book_num)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, project_id, filename, file_path, file_size, mime_type, book_id, book_num, uploaded_at
            """,
            project_id, filename, file_path, file_size, mime_type, book_num,
        )
        return dict(row)

    async def list_files(self, project_id: str) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT * FROM project_files WHERE project_id = $1 ORDER BY book_num",
            project_id,
        )
        return [dict(r) for r in rows]

    async def update_file_book_id(self, file_id: str, book_id: str) -> None:
        await self.pool.execute(
            "UPDATE project_files SET book_id = $1 WHERE id = $2",
            book_id, file_id,
        )

    async def count_books(self, slug: str) -> int:
        return await self.pool.fetchval(
            """
            SELECT COUNT(*) FROM project_files pf
            JOIN projects p ON p.id = pf.project_id
            WHERE p.slug = $1 AND pf.book_id IS NOT NULL
            """,
            slug,
        ) or 0
```

- [ ] **Step 4: Run tests**

```bash
uv run python -m pytest backend/tests/test_project_repo.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/project_repo.py backend/tests/test_project_repo.py
git commit -m "feat(repo): add ProjectRepository for projects + files"
```

---

## Chunk 2: Backend — Service + API Routes

### Task 4: Project service

**Files:**
- Create: `backend/app/services/project_service.py`
- Create: `backend/tests/test_project_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_project_service.py
"""Tests for ProjectService."""
from unittest.mock import AsyncMock, patch
import pytest
from app.services.project_service import ProjectService


@pytest.fixture
def mock_deps():
    pool = AsyncMock()
    redis = AsyncMock()
    neo4j_driver = AsyncMock()
    return pool, redis, neo4j_driver


class TestProjectService:
    @pytest.mark.asyncio
    async def test_create_project(self, mock_deps):
        pool, redis, driver = mock_deps
        pool.fetchrow = AsyncMock(return_value={
            "id": "uuid-1", "slug": "test", "name": "Test",
            "description": "", "cover_image": None,
            "created_at": "2026-01-01", "updated_at": "2026-01-01",
        })
        service = ProjectService(pool=pool, redis=redis, neo4j_driver=driver)
        result = await service.create_project("test", "Test")
        assert result["slug"] == "test"

    @pytest.mark.asyncio
    async def test_delete_project_cascades(self, mock_deps):
        pool, redis, driver = mock_deps
        pool.fetchrow = AsyncMock(return_value={
            "id": "uuid-1", "slug": "test", "name": "Test"
        })
        pool.fetch = AsyncMock(return_value=[
            {"file_path": "/data/projects/test/files/book.epub"}
        ])
        pool.fetchval = AsyncMock(return_value="test")
        redis.delete = AsyncMock()
        session = AsyncMock()
        driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
        driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        service = ProjectService(pool=pool, redis=redis, neo4j_driver=driver)
        with patch("app.services.project_service.shutil") as mock_shutil:
            await service.delete_project("test")

        # Verify cascade: Redis profile deleted, Neo4j entities deleted
        redis.delete.assert_awaited()
        session.run.assert_awaited()  # Neo4j DETACH DELETE

    @pytest.mark.asyncio
    async def test_get_project_stats(self, mock_deps):
        pool, redis, driver = mock_deps
        pool.fetchval = AsyncMock(side_effect=[3, 42])  # books_count, chapters
        redis.get = AsyncMock(return_value=None)
        session = AsyncMock()
        result_mock = AsyncMock()
        result_mock.single = AsyncMock(return_value={"count": 150})
        session.run = AsyncMock(return_value=result_mock)
        driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
        driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        service = ProjectService(pool=pool, redis=redis, neo4j_driver=driver)
        stats = await service.get_stats("test")
        assert stats["slug"] == "test"
        assert stats["books_count"] == 3
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run python -m pytest backend/tests/test_project_service.py -v
```

- [ ] **Step 3: Write implementation**

```python
# backend/app/services/project_service.py
"""Project business logic — create, delete (cascade), stats."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.core.logging import get_logger
from app.repositories.project_repo import ProjectRepository

if TYPE_CHECKING:
    import asyncpg
    from neo4j import AsyncDriver
    from redis.asyncio import Redis

logger = get_logger(__name__)

SAGA_PROFILE_PREFIX = "saga_profile:"


class ProjectService:
    def __init__(
        self,
        pool: asyncpg.Pool,
        redis: Redis,
        neo4j_driver: AsyncDriver,
    ) -> None:
        self.repo = ProjectRepository(pool)
        self.redis = redis
        self.neo4j_driver = neo4j_driver

    async def create_project(
        self, slug: str, name: str, description: str = ""
    ) -> dict[str, Any]:
        project = await self.repo.create(slug, name, description)
        # Create filesystem directory
        project_dir = Path(settings.project_data_dir) / slug / "files"
        project_dir.mkdir(parents=True, exist_ok=True)
        logger.info("project_created", slug=slug)
        return project

    async def get_project(self, slug: str) -> dict[str, Any] | None:
        return await self.repo.get_by_slug(slug)

    async def list_projects(self) -> list[dict[str, Any]]:
        projects = await self.repo.list_all()
        enriched = []
        for p in projects:
            books_count = await self.repo.count_books(p["slug"])
            has_profile = await self.redis.get(f"{SAGA_PROFILE_PREFIX}{p['slug']}") is not None
            enriched.append({**p, "books_count": books_count, "has_profile": has_profile})
        return enriched

    async def update_project(self, slug: str, **fields: Any) -> dict[str, Any] | None:
        return await self.repo.update(slug, **fields)

    async def delete_project(self, slug: str) -> None:
        """Delete project with full cascade: PG, Redis, Neo4j, filesystem."""
        project = await self.repo.get_by_slug(slug)
        if not project:
            return

        # 1. Delete file records and get paths
        files = await self.repo.list_files(str(project["id"]))

        # 2. Delete from PostgreSQL (CASCADE deletes project_files too)
        await self.repo.delete(slug)

        # 3. Delete SagaProfile from Redis
        await self.redis.delete(f"{SAGA_PROFILE_PREFIX}{slug}")

        # 4. Delete entities from Neo4j
        async with self.neo4j_driver.session() as session:
            await session.run(
                "MATCH (n {group_id: $slug}) DETACH DELETE n", slug=slug,
            )
            await session.run(
                "MATCH (c:Community {saga_id: $slug}) DELETE c", slug=slug,
            )

        # 5. Delete filesystem
        project_dir = Path(settings.project_data_dir) / slug
        if project_dir.exists():
            shutil.rmtree(project_dir)

        logger.info("project_deleted", slug=slug)

    async def get_stats(self, slug: str) -> dict[str, Any]:
        books_count = await self.repo.count_books(slug)
        chapters = await self.repo.pool.fetchval(
            """
            SELECT COUNT(*) FROM project_files pf
            JOIN projects p ON p.id = pf.project_id
            WHERE p.slug = $1
            """,
            slug,
        ) or 0

        # Entity count from Neo4j
        entities_total = 0
        community_count = 0
        async with self.neo4j_driver.session() as session:
            result = await session.run(
                "MATCH (n:Entity {group_id: $slug}) RETURN count(n) AS count",
                slug=slug,
            )
            record = await result.single()
            if record:
                entities_total = record["count"]

            result = await session.run(
                "MATCH (c:Community {saga_id: $slug}) RETURN count(c) AS count",
                slug=slug,
            )
            record = await result.single()
            if record:
                community_count = record["count"]

        # Profile
        profile_json = await self.redis.get(f"{SAGA_PROFILE_PREFIX}{slug}")
        has_profile = profile_json is not None
        profile_types_count = 0
        if has_profile:
            from app.services.saga_profile.models import SagaProfile
            profile = SagaProfile.model_validate_json(profile_json)
            profile_types_count = len(profile.entity_types)

        return {
            "slug": slug,
            "books_count": books_count,
            "chapters_total": chapters,
            "entities_total": entities_total,
            "community_count": community_count,
            "has_profile": has_profile,
            "profile_types_count": profile_types_count,
        }

    async def store_book_file(
        self,
        slug: str,
        filename: str,
        file_content: bytes,
        book_num: int = 1,
        mime_type: str = "application/epub+zip",
    ) -> dict[str, Any]:
        """Store an uploaded EPUB file and create a project_files record."""
        project = await self.repo.get_by_slug(slug)
        if not project:
            msg = f"Project {slug} not found"
            raise ValueError(msg)

        file_dir = Path(settings.project_data_dir) / slug / "files"
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / filename
        file_path.write_bytes(file_content)

        record = await self.repo.add_file(
            project_id=str(project["id"]),
            filename=filename,
            file_path=str(file_path),
            file_size=len(file_content),
            mime_type=mime_type,
            book_num=book_num,
        )
        logger.info("project_file_stored", slug=slug, filename=filename)
        return record
```

- [ ] **Step 4: Run tests**

```bash
uv run python -m pytest backend/tests/test_project_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/project_service.py backend/tests/test_project_service.py
git commit -m "feat(service): add ProjectService with cascade delete + stats"
```

---

### Task 5: Project API routes

**Files:**
- Create: `backend/app/api/routes/projects.py`
- Create: `backend/tests/test_project_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add config field**

In `backend/app/config.py`, add:
```python
    # --- Projects ---
    project_data_dir: str = "/data/projects"
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_project_api.py
"""Tests for project API endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes.projects import router


@pytest.fixture
def mock_app():
    app = FastAPI()
    app.state.pg_pool = AsyncMock()
    app.state.redis = AsyncMock()
    app.state.neo4j_driver = AsyncMock()
    app.state.arq_pool = AsyncMock()
    app.state.graphiti = AsyncMock()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def client(mock_app):
    return TestClient(mock_app)


class TestProjectCRUD:
    def test_create_project(self, client, mock_app):
        mock_app.state.pg_pool.fetchrow = AsyncMock(return_value={
            "id": "uuid-1", "slug": "test", "name": "Test Saga",
            "description": "", "cover_image": None,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        })
        with patch("app.services.project_service.Path"):
            resp = client.post("/api/projects", json={
                "slug": "test", "name": "Test Saga"
            })
        assert resp.status_code == 201

    def test_list_projects(self, client, mock_app):
        mock_app.state.pg_pool.fetch = AsyncMock(return_value=[])
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_project_not_found(self, client, mock_app):
        mock_app.state.pg_pool.fetchrow = AsyncMock(return_value=None)
        resp = client.get("/api/projects/nonexistent")
        assert resp.status_code == 404

    def test_delete_project(self, client, mock_app):
        mock_app.state.pg_pool.fetchrow = AsyncMock(return_value={
            "id": "uuid-1", "slug": "test", "name": "Test"
        })
        mock_app.state.pg_pool.fetch = AsyncMock(return_value=[])
        mock_app.state.pg_pool.fetchval = AsyncMock(return_value="test")
        mock_app.state.redis.delete = AsyncMock()
        session = AsyncMock()
        mock_app.state.neo4j_driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_app.state.neo4j_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("app.services.project_service.shutil"), patch("app.services.project_service.Path"):
            resp = client.delete("/api/projects/test")
        assert resp.status_code == 200
```

- [ ] **Step 3: Write the implementation**

```python
# backend/app/api/routes/projects.py
"""Project CRUD + scoped resource API routes."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.auth import require_auth
from app.api.dependencies import get_arq_pool, get_neo4j, get_postgres
from app.core.logging import get_logger
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectStatsResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

if TYPE_CHECKING:
    from arq.connections import ArqRedis

logger = get_logger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


def _get_service(request: Request) -> ProjectService:
    return ProjectService(
        pool=request.app.state.pg_pool,
        redis=request.app.state.redis,
        neo4j_driver=request.app.state.neo4j_driver,
    )


@router.post("", status_code=201, response_model=ProjectResponse)
async def create_project(body: ProjectCreate, request: Request):
    service = _get_service(request)
    existing = await service.get_project(body.slug)
    if existing:
        return JSONResponse(status_code=409, content={"detail": f"Project '{body.slug}' already exists"})
    project = await service.create_project(body.slug, body.name, body.description)
    return ProjectResponse(
        id=str(project["id"]), slug=project["slug"], name=project["name"],
        description=project["description"], cover_image=project.get("cover_image"),
        created_at=project["created_at"], updated_at=project["updated_at"],
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(request: Request):
    service = _get_service(request)
    projects = await service.list_projects()
    items = [
        ProjectResponse(
            id=str(p["id"]), slug=p["slug"], name=p["name"],
            description=p["description"], cover_image=p.get("cover_image"),
            created_at=p["created_at"], updated_at=p["updated_at"],
            books_count=p.get("books_count", 0),
            has_profile=p.get("has_profile", False),
        )
        for p in projects
    ]
    return ProjectListResponse(projects=items, total=len(items))


@router.get("/{slug}", response_model=ProjectResponse)
async def get_project(slug: str, request: Request):
    service = _get_service(request)
    project = await service.get_project(slug)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})
    books_count = await service.repo.count_books(slug)
    has_profile = await service.redis.get(f"saga_profile:{slug}") is not None
    return ProjectResponse(
        id=str(project["id"]), slug=project["slug"], name=project["name"],
        description=project["description"], cover_image=project.get("cover_image"),
        created_at=project["created_at"], updated_at=project["updated_at"],
        books_count=books_count, has_profile=has_profile,
    )


@router.put("/{slug}", response_model=ProjectResponse)
async def update_project(slug: str, body: ProjectUpdate, request: Request):
    service = _get_service(request)
    fields = body.model_dump(exclude_none=True)
    project = await service.update_project(slug, **fields)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})
    return ProjectResponse(
        id=str(project["id"]), slug=project["slug"], name=project["name"],
        description=project["description"], cover_image=project.get("cover_image"),
        created_at=project["created_at"], updated_at=project["updated_at"],
    )


@router.delete("/{slug}")
async def delete_project(slug: str, request: Request):
    service = _get_service(request)
    project = await service.get_project(slug)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})
    await service.delete_project(slug)
    return {"deleted": True, "slug": slug}


@router.get("/{slug}/stats", response_model=ProjectStatsResponse)
async def get_project_stats(slug: str, request: Request):
    service = _get_service(request)
    project = await service.get_project(slug)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})
    stats = await service.get_stats(slug)
    return ProjectStatsResponse(**stats)


@router.post("/{slug}/books", status_code=201)
async def upload_book(
    slug: str,
    file: UploadFile,
    request: Request,
    book_num: int = 1,
):
    """Upload an EPUB file into a project."""
    service = _get_service(request)
    project = await service.get_project(slug)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})

    content = await file.read()
    record = await service.store_book_file(
        slug=slug,
        filename=file.filename or "book.epub",
        file_content=content,
        book_num=book_num,
        mime_type=file.content_type or "application/epub+zip",
    )

    # Parse the EPUB via existing ingestion pipeline
    from app.services.ingestion import ingest_file

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    driver = request.app.state.neo4j_driver
    result = await ingest_file(
        driver=driver,
        file_path=tmp_path,
        title=file.filename or "Untitled",
        genre="litrpg",
    )

    # Link book_id back to file record
    if result and result.get("book_id"):
        await service.repo.update_file_book_id(str(record["id"]), result["book_id"])

    Path(tmp_path).unlink(missing_ok=True)

    return {
        "file_id": str(record["id"]),
        "book_id": result.get("book_id") if result else None,
        "filename": record["filename"],
        "chapters_found": result.get("chapters_found", 0) if result else 0,
    }


@router.post("/{slug}/extract", status_code=202)
async def extract_project_book(
    slug: str,
    request: Request,
    book_id: str | None = None,
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """Trigger Graphiti extraction for a book in this project."""
    service = _get_service(request)
    project = await service.get_project(slug)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})

    # Check for existing profile (guided vs discovery)
    existing_profile = await service.redis.get(f"saga_profile:{slug}")
    mode = "guided" if existing_profile else "discovery"

    # Get book_num from project_files if book_id provided
    book_num = 1
    if book_id:
        files = await service.repo.list_files(str(project["id"]))
        for f in files:
            if f.get("book_id") == book_id:
                book_num = f.get("book_num", 1)
                break

    job = await arq_pool.enqueue_job(
        "process_book_graphiti",
        book_id or "",
        slug,
        project["name"],
        book_num,
        existing_profile,
        _queue_name="worldrag:arq",
        _job_id=f"graphiti:{slug}:{book_id or 'all'}",
    )
    return {"job_id": job.job_id, "mode": mode, "slug": slug}
```

- [ ] **Step 4: Register router in main.py**

In `backend/app/main.py`, add `projects` to imports and `app.include_router(projects.router, prefix="/api")`.

- [ ] **Step 5: Run tests**

```bash
uv run python -m pytest backend/tests/test_project_api.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/projects.py backend/app/schemas/project.py backend/app/config.py backend/app/main.py backend/tests/test_project_api.py
git commit -m "feat(api): add project CRUD + scoped book upload + extraction"
```

---

### Task 6: Docker Compose volume

**Files:**
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Add project_data volume**

In `docker-compose.prod.yml`, add to backend and worker services:
```yaml
    volumes:
      - project_data:/data/projects
```

And in the volumes section:
```yaml
  project_data:    # persists uploaded EPUBs and project files
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "infra: add project_data volume for EPUB storage"
```

---

## Chunk 3: Frontend — Dashboard + Project View

### Task 7: Project API client + store

**Files:**
- Create: `frontend/lib/api/projects.ts`
- Create: `frontend/stores/project-store.ts`

- [ ] **Step 1: Create API client**

```typescript
// frontend/lib/api/projects.ts
import { apiFetch } from "./client";

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string;
  cover_image: string | null;
  created_at: string;
  updated_at: string;
  books_count: number;
  has_profile: boolean;
  entity_count: number;
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

export async function listProjects(): Promise<ProjectListResponse> {
  return apiFetch("/projects");
}

export async function getProject(slug: string): Promise<Project> {
  return apiFetch(`/projects/${slug}`);
}

export async function createProject(data: {
  slug: string;
  name: string;
  description?: string;
}): Promise<Project> {
  return apiFetch("/projects", { method: "POST", body: JSON.stringify(data) });
}

export async function deleteProject(slug: string): Promise<void> {
  return apiFetch(`/projects/${slug}`, { method: "DELETE" });
}

export async function uploadBookToProject(
  slug: string,
  file: File,
  bookNum: number = 1
): Promise<{ file_id: string; book_id: string; chapters_found: number }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("book_num", String(bookNum));
  return apiFetch(`/projects/${slug}/books`, {
    method: "POST",
    body: formData,
    headers: {},  // Let browser set Content-Type for multipart
  });
}

export async function triggerExtraction(
  slug: string,
  bookId?: string
): Promise<{ job_id: string; mode: string }> {
  const params = bookId ? `?book_id=${bookId}` : "";
  return apiFetch(`/projects/${slug}/extract${params}`, { method: "POST" });
}

export async function getProjectStats(slug: string) {
  return apiFetch(`/projects/${slug}/stats`);
}
```

- [ ] **Step 2: Create Zustand store**

```typescript
// frontend/stores/project-store.ts
import { create } from "zustand";
import type { Project } from "@/lib/api/projects";

interface ProjectStore {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  setProjects: (projects: Project[]) => void;
  setCurrentProject: (project: Project | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useProjectStore = create<ProjectStore>((set) => ({
  projects: [],
  currentProject: null,
  loading: false,
  setProjects: (projects) => set({ projects }),
  setCurrentProject: (project) => set({ currentProject: project }),
  setLoading: (loading) => set({ loading }),
}));
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/projects.ts frontend/stores/project-store.ts
git commit -m "feat(frontend): add project API client + Zustand store"
```

---

### Task 8: Dashboard page

**Files:**
- Create: `frontend/components/projects/project-card.tsx`
- Create: `frontend/components/projects/create-project-dialog.tsx`
- Modify: `frontend/app/page.tsx` (replace with dashboard)

- [ ] **Step 1: Create ProjectCard component**

A card showing: project name, books count, entity count, profile status badge, last updated.
Clicking navigates to `/projects/{slug}`.

- [ ] **Step 2: Create CreateProjectDialog**

A dialog/modal with: name input, slug input (auto-generated from name), description textarea.
Submit calls `createProject()`.

- [ ] **Step 3: Update app/page.tsx**

Replace the current home page with a grid of ProjectCard components + a "New Project" card.
Use `listProjects()` to fetch data on mount.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/projects/ frontend/app/page.tsx
git commit -m "feat(frontend): add project dashboard with cards + create dialog"
```

---

### Task 9: Project layout and tabs

**Files:**
- Create: `frontend/app/projects/[slug]/layout.tsx`
- Create: `frontend/app/projects/[slug]/page.tsx`
- Create: `frontend/app/projects/[slug]/books/page.tsx`
- Create: `frontend/app/projects/[slug]/graph/page.tsx`
- Create: `frontend/app/projects/[slug]/chat/page.tsx`
- Create: `frontend/app/projects/[slug]/profile/page.tsx`

- [ ] **Step 1: Create project layout with tabs**

```typescript
// frontend/app/projects/[slug]/layout.tsx
// Tabbed layout: Books | Graph | Chat | Profile
// Fetches project data via getProject(slug) and sets in store
// Tabs use Next.js Link components with active state
```

- [ ] **Step 2: Create tab pages**

Each tab page reuses existing components but scoped to the project:
- **books/page.tsx**: Upload dropzone + book list (from project_files)
- **graph/page.tsx**: Existing Sigma.js explorer with `group_id={slug}` filter
- **chat/page.tsx**: Existing chat UI with `saga_id={slug}`
- **profile/page.tsx**: SagaProfile viewer showing induced types, patterns, relations

- [ ] **Step 3: Create project overview page** (redirects to books tab)

- [ ] **Step 4: Commit**

```bash
git add frontend/app/projects/
git commit -m "feat(frontend): add project view with Books/Graph/Chat/Profile tabs"
```
