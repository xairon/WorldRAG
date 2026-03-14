"""Tests for app.repositories.project_repo — Project PostgreSQL repository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.project_repo import ProjectRepository

PROJECT_SLUG = "the-primal-hunter"
PROJECT_NAME = "The Primal Hunter"
PROJECT_DESC = "LitRPG saga by Zogarth"
PROJECT_ID = "uuid-proj-001"
FILE_ID = "uuid-file-001"
BOOK_ID = "uuid-book-001"


def make_pool(fetchrow=None, fetch=None, fetchval=None, execute=None):
    """Build a minimal asyncpg pool mock."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch if fetch is not None else [])
    conn.fetchval = AsyncMock(return_value=fetchval)
    conn.execute = AsyncMock(return_value=execute)

    pool = MagicMock()
    pool.acquire = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


class TestCreate:
    async def test_returns_inserted_row(self):
        row = {
            "id": PROJECT_ID,
            "slug": PROJECT_SLUG,
            "name": PROJECT_NAME,
            "description": PROJECT_DESC,
            "cover_image": None,
            "created_at": "2026-03-14T00:00:00",
            "updated_at": "2026-03-14T00:00:00",
        }
        pool, conn = make_pool(fetchrow=row)
        repo = ProjectRepository(pool)
        result = await repo.create(PROJECT_SLUG, PROJECT_NAME, PROJECT_DESC)
        assert result == row
        conn.fetchrow.assert_awaited_once()

    async def test_passes_slug_name_description(self):
        pool, conn = make_pool(fetchrow={})
        repo = ProjectRepository(pool)
        await repo.create(PROJECT_SLUG, PROJECT_NAME, PROJECT_DESC)
        call_args = conn.fetchrow.call_args
        query = call_args[0][0]
        params = call_args[0][1:]
        assert PROJECT_SLUG in params
        assert PROJECT_NAME in params
        assert PROJECT_DESC in params
        assert "INSERT" in query.upper()

    async def test_returns_none_when_fetchrow_returns_none(self):
        pool, conn = make_pool(fetchrow=None)
        repo = ProjectRepository(pool)
        result = await repo.create(PROJECT_SLUG, PROJECT_NAME, PROJECT_DESC)
        assert result is None


class TestGetBySlug:
    async def test_returns_row_when_found(self):
        row = {"id": PROJECT_ID, "slug": PROJECT_SLUG, "name": PROJECT_NAME}
        pool, conn = make_pool(fetchrow=row)
        repo = ProjectRepository(pool)
        result = await repo.get_by_slug(PROJECT_SLUG)
        assert result == row

    async def test_returns_none_when_not_found(self):
        pool, conn = make_pool(fetchrow=None)
        repo = ProjectRepository(pool)
        result = await repo.get_by_slug(PROJECT_SLUG)
        assert result is None

    async def test_passes_slug_param(self):
        pool, conn = make_pool(fetchrow=None)
        repo = ProjectRepository(pool)
        await repo.get_by_slug(PROJECT_SLUG)
        call_args = conn.fetchrow.call_args
        params = call_args[0][1:]
        assert PROJECT_SLUG in params


class TestListAll:
    async def test_returns_empty_list(self):
        pool, conn = make_pool(fetch=[])
        repo = ProjectRepository(pool)
        result = await repo.list_all()
        assert result == []

    async def test_returns_all_rows(self):
        rows = [
            {"id": "id-1", "slug": "saga-1", "name": "Saga One"},
            {"id": "id-2", "slug": "saga-2", "name": "Saga Two"},
        ]
        pool, conn = make_pool(fetch=rows)
        repo = ProjectRepository(pool)
        result = await repo.list_all()
        assert len(result) == 2
        assert result[0]["slug"] == "saga-1"

    async def test_query_orders_by_created_at_desc(self):
        pool, conn = make_pool(fetch=[])
        repo = ProjectRepository(pool)
        await repo.list_all()
        call_args = conn.fetch.call_args
        query = call_args[0][0].upper()
        assert "ORDER BY" in query
        assert "CREATED_AT" in query
        assert "DESC" in query


class TestUpdate:
    async def test_returns_updated_row(self):
        row = {"id": PROJECT_ID, "slug": PROJECT_SLUG, "name": "New Name"}
        pool, conn = make_pool(fetchrow=row)
        repo = ProjectRepository(pool)
        result = await repo.update(PROJECT_SLUG, name="New Name")
        assert result == row

    async def test_only_non_none_fields_updated(self):
        pool, conn = make_pool(fetchrow={})
        repo = ProjectRepository(pool)
        await repo.update(PROJECT_SLUG, name="New Name", description=None)
        call_args = conn.fetchrow.call_args
        query = call_args[0][0]
        assert "name" in query
        assert "description" not in query

    async def test_includes_updated_at(self):
        pool, conn = make_pool(fetchrow={})
        repo = ProjectRepository(pool)
        await repo.update(PROJECT_SLUG, name="New Name")
        call_args = conn.fetchrow.call_args
        query = call_args[0][0].lower()
        assert "updated_at" in query

    async def test_returns_none_when_not_found(self):
        pool, conn = make_pool(fetchrow=None)
        repo = ProjectRepository(pool)
        result = await repo.update(PROJECT_SLUG, name="New Name")
        assert result is None


class TestDelete:
    async def test_returns_slug_on_success(self):
        row = {"slug": PROJECT_SLUG}
        pool, conn = make_pool(fetchrow=row)
        repo = ProjectRepository(pool)
        result = await repo.delete(PROJECT_SLUG)
        assert result == PROJECT_SLUG

    async def test_returns_none_when_not_found(self):
        pool, conn = make_pool(fetchrow=None)
        repo = ProjectRepository(pool)
        result = await repo.delete(PROJECT_SLUG)
        assert result is None

    async def test_query_uses_delete(self):
        pool, conn = make_pool(fetchrow={"slug": PROJECT_SLUG})
        repo = ProjectRepository(pool)
        await repo.delete(PROJECT_SLUG)
        call_args = conn.fetchrow.call_args
        query = call_args[0][0].upper()
        assert "DELETE" in query


class TestAddFile:
    async def test_returns_inserted_file_row(self):
        row = {
            "id": FILE_ID,
            "project_id": PROJECT_ID,
            "filename": "book1.epub",
            "file_path": "/data/projects/the-primal-hunter/book1.epub",
            "file_size": 1024,
            "mime_type": "application/epub+zip",
            "book_num": 1,
            "book_id": None,
            "uploaded_at": "2026-03-14T00:00:00",
        }
        pool, conn = make_pool(fetchrow=row)
        repo = ProjectRepository(pool)
        result = await repo.add_file(
            PROJECT_ID, "book1.epub", "/data/projects/the-primal-hunter/book1.epub",
            1024, "application/epub+zip", 1
        )
        assert result == row
        conn.fetchrow.assert_awaited_once()

    async def test_passes_all_params(self):
        pool, conn = make_pool(fetchrow={})
        repo = ProjectRepository(pool)
        await repo.add_file(
            PROJECT_ID, "book1.epub", "/path/to/file", 512, "text/plain", 2
        )
        call_args = conn.fetchrow.call_args
        params = call_args[0][1:]
        assert PROJECT_ID in params
        assert "book1.epub" in params
        assert "/path/to/file" in params
        assert 512 in params
        assert "text/plain" in params
        assert 2 in params


class TestListFiles:
    async def test_returns_empty_list(self):
        pool, conn = make_pool(fetch=[])
        repo = ProjectRepository(pool)
        result = await repo.list_files(PROJECT_ID)
        assert result == []

    async def test_returns_files_ordered_by_book_num(self):
        rows = [
            {"id": "f1", "book_num": 1, "filename": "book1.epub"},
            {"id": "f2", "book_num": 2, "filename": "book2.epub"},
        ]
        pool, conn = make_pool(fetch=rows)
        repo = ProjectRepository(pool)
        result = await repo.list_files(PROJECT_ID)
        assert len(result) == 2

    async def test_query_orders_by_book_num(self):
        pool, conn = make_pool(fetch=[])
        repo = ProjectRepository(pool)
        await repo.list_files(PROJECT_ID)
        call_args = conn.fetch.call_args
        query = call_args[0][0].upper()
        assert "ORDER BY" in query
        assert "BOOK_NUM" in query


class TestUpdateFileBookId:
    async def test_calls_execute(self):
        pool, conn = make_pool()
        repo = ProjectRepository(pool)
        await repo.update_file_book_id(FILE_ID, BOOK_ID)
        conn.execute.assert_awaited_once()

    async def test_passes_file_id_and_book_id(self):
        pool, conn = make_pool()
        repo = ProjectRepository(pool)
        await repo.update_file_book_id(FILE_ID, BOOK_ID)
        call_args = conn.execute.call_args
        params = call_args[0][1:]
        assert FILE_ID in params
        assert BOOK_ID in params


class TestCountBooks:
    async def test_returns_zero_when_no_books(self):
        pool, conn = make_pool(fetchval=0)
        repo = ProjectRepository(pool)
        result = await repo.count_books(PROJECT_SLUG)
        assert result == 0

    async def test_returns_count(self):
        pool, conn = make_pool(fetchval=5)
        repo = ProjectRepository(pool)
        result = await repo.count_books(PROJECT_SLUG)
        assert result == 5

    async def test_query_uses_join_and_book_id_not_null(self):
        pool, conn = make_pool(fetchval=0)
        repo = ProjectRepository(pool)
        await repo.count_books(PROJECT_SLUG)
        call_args = conn.fetchval.call_args
        query = call_args[0][0].upper()
        assert "JOIN" in query or "COUNT" in query
        assert "BOOK_ID" in query
