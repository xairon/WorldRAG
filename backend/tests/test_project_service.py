"""Tests for app.services.project_service — ProjectService."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.project_service import ProjectService

PROJECT_SLUG = "the-primal-hunter"
PROJECT_NAME = "The Primal Hunter"
PROJECT_DESC = "LitRPG saga by Zogarth"
PROJECT_ID = "uuid-proj-001"
FILE_ID = "uuid-file-001"
BOOK_ID = "uuid-book-001"

_BASE_PROJECT_ROW = {
    "id": PROJECT_ID,
    "slug": PROJECT_SLUG,
    "name": PROJECT_NAME,
    "description": PROJECT_DESC,
    "cover_image": None,
    "created_at": "2026-03-14T00:00:00",
    "updated_at": "2026-03-14T00:00:00",
}


def make_service(
    repo_create=None,
    repo_get=None,
    repo_list=None,
    repo_update=None,
    repo_delete=None,
    repo_add_file=None,
    repo_list_files=None,
    repo_count_books=0,
    redis_get=None,
    neo4j_records=None,
):
    """Build a ProjectService with fully mocked dependencies."""
    pool = MagicMock()
    redis = AsyncMock()
    neo4j_driver = MagicMock()

    # Redis mock
    redis.get = AsyncMock(return_value=redis_get)
    redis.delete = AsyncMock(return_value=1)

    # Neo4j mock session
    neo4j_session_cm = MagicMock()
    neo4j_session = AsyncMock()
    result_mock = AsyncMock()
    result_mock.data = AsyncMock(return_value=neo4j_records or [])
    neo4j_session.run = AsyncMock(return_value=result_mock)
    neo4j_session_cm.__aenter__ = AsyncMock(return_value=neo4j_session)
    neo4j_session_cm.__aexit__ = AsyncMock(return_value=False)
    neo4j_driver.session = MagicMock(return_value=neo4j_session_cm)

    svc = ProjectService(pool=pool, redis=redis, neo4j_driver=neo4j_driver)

    # Patch the internal repo
    svc._repo.create = AsyncMock(return_value=repo_create)
    svc._repo.get_by_slug = AsyncMock(return_value=repo_get)
    svc._repo.list_all = AsyncMock(return_value=repo_list or [])
    svc._repo.update = AsyncMock(return_value=repo_update)
    svc._repo.delete = AsyncMock(return_value=repo_delete)
    svc._repo.add_file = AsyncMock(return_value=repo_add_file)
    svc._repo.list_files = AsyncMock(return_value=repo_list_files or [])
    svc._repo.count_books = AsyncMock(return_value=repo_count_books)

    return svc, redis, neo4j_session


class TestCreateProject:
    async def test_returns_created_row(self):
        svc, _, _ = make_service(repo_create=_BASE_PROJECT_ROW)
        with patch("app.services.project_service.Path") as mock_path:
            mock_path.return_value.mkdir = MagicMock()
            result = await svc.create_project(PROJECT_SLUG, PROJECT_NAME, PROJECT_DESC)
        assert result == _BASE_PROJECT_ROW

    async def test_creates_filesystem_directory(self):
        svc, _, _ = make_service(repo_create=_BASE_PROJECT_ROW)
        with patch("app.services.project_service.Path") as mock_path:
            mock_dir = MagicMock()
            mock_path.return_value.__truediv__ = MagicMock(return_value=mock_dir)
            mock_dir.mkdir = MagicMock()
            await svc.create_project(PROJECT_SLUG, PROJECT_NAME, PROJECT_DESC)
            mock_dir.mkdir.assert_called_once()

    async def test_delegates_to_repo_create(self):
        svc, _, _ = make_service(repo_create=_BASE_PROJECT_ROW)
        with patch("app.services.project_service.Path"):
            await svc.create_project(PROJECT_SLUG, PROJECT_NAME, PROJECT_DESC)
        svc._repo.create.assert_awaited_once_with(PROJECT_SLUG, PROJECT_NAME, PROJECT_DESC)


class TestGetProject:
    async def test_returns_project_when_found(self):
        svc, _, _ = make_service(repo_get=_BASE_PROJECT_ROW)
        result = await svc.get_project(PROJECT_SLUG)
        assert result == _BASE_PROJECT_ROW

    async def test_returns_none_when_not_found(self):
        svc, _, _ = make_service(repo_get=None)
        result = await svc.get_project(PROJECT_SLUG)
        assert result is None

    async def test_delegates_to_repo(self):
        svc, _, _ = make_service(repo_get=_BASE_PROJECT_ROW)
        await svc.get_project(PROJECT_SLUG)
        svc._repo.get_by_slug.assert_awaited_once_with(PROJECT_SLUG)


class TestListProjects:
    async def test_returns_empty_list(self):
        svc, _, _ = make_service(repo_list=[])
        result = await svc.list_projects()
        assert result == []

    async def test_enriches_with_books_count(self):
        svc, _, _ = make_service(
            repo_list=[_BASE_PROJECT_ROW],
            repo_count_books=3,
        )
        result = await svc.list_projects()
        assert result[0]["books_count"] == 3

    async def test_enriches_with_has_profile_true(self):
        profile_json = json.dumps({"saga_id": PROJECT_SLUG})
        svc, _, _ = make_service(
            repo_list=[_BASE_PROJECT_ROW],
            redis_get=profile_json.encode(),
        )
        result = await svc.list_projects()
        assert result[0]["has_profile"] is True

    async def test_enriches_with_has_profile_false_when_redis_empty(self):
        svc, _, _ = make_service(repo_list=[_BASE_PROJECT_ROW], redis_get=None)
        result = await svc.list_projects()
        assert result[0]["has_profile"] is False

    async def test_checks_redis_key_per_project(self):
        svc, redis, _ = make_service(repo_list=[_BASE_PROJECT_ROW])
        await svc.list_projects()
        redis.get.assert_awaited_once()
        call_key = redis.get.call_args[0][0]
        assert PROJECT_SLUG in call_key


class TestUpdateProject:
    async def test_returns_updated_row(self):
        updated = {**_BASE_PROJECT_ROW, "name": "New Name"}
        svc, _, _ = make_service(repo_update=updated)
        result = await svc.update_project(PROJECT_SLUG, name="New Name")
        assert result == updated

    async def test_delegates_to_repo(self):
        svc, _, _ = make_service(repo_update=_BASE_PROJECT_ROW)
        await svc.update_project(PROJECT_SLUG, name="New Name")
        svc._repo.update.assert_awaited_once_with(PROJECT_SLUG, name="New Name")


class TestDeleteProject:
    async def test_deletes_redis_saga_profile(self):
        svc, redis, _ = make_service(repo_delete=PROJECT_SLUG)
        with patch("app.services.project_service.shutil") as mock_shutil:
            mock_shutil.rmtree = MagicMock()
            with patch("app.services.project_service.Path") as mock_path:
                mock_path.return_value.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=False)))
                await svc.delete_project(PROJECT_SLUG)
        redis.delete.assert_awaited_once()
        key = redis.delete.call_args[0][0]
        assert PROJECT_SLUG in key

    async def test_deletes_neo4j_entities(self):
        svc, _, neo4j_session = make_service(repo_delete=PROJECT_SLUG)
        with patch("app.services.project_service.shutil"):
            with patch("app.services.project_service.Path") as mock_path:
                mock_path.return_value.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=False)))
                await svc.delete_project(PROJECT_SLUG)
        assert neo4j_session.run.await_count >= 1
        first_call_query = neo4j_session.run.call_args_list[0][0][0].upper()
        assert "DETACH DELETE" in first_call_query or "DELETE" in first_call_query

    async def test_deletes_filesystem_when_exists(self):
        svc, _, _ = make_service(repo_delete=PROJECT_SLUG)
        with patch("app.services.project_service.shutil") as mock_shutil:
            with patch("app.services.project_service.Path") as mock_path:
                project_dir = MagicMock()
                project_dir.exists = MagicMock(return_value=True)
                mock_path.return_value.__truediv__ = MagicMock(return_value=project_dir)
                await svc.delete_project(PROJECT_SLUG)
            mock_shutil.rmtree.assert_called_once()

    async def test_skips_rmtree_when_dir_not_exists(self):
        svc, _, _ = make_service(repo_delete=PROJECT_SLUG)
        with patch("app.services.project_service.shutil") as mock_shutil:
            with patch("app.services.project_service.Path") as mock_path:
                project_dir = MagicMock()
                project_dir.exists = MagicMock(return_value=False)
                mock_path.return_value.__truediv__ = MagicMock(return_value=project_dir)
                await svc.delete_project(PROJECT_SLUG)
            mock_shutil.rmtree.assert_not_called()

    async def test_delegates_pg_delete_to_repo(self):
        svc, _, _ = make_service(repo_delete=PROJECT_SLUG)
        with patch("app.services.project_service.shutil"):
            with patch("app.services.project_service.Path") as mock_path:
                mock_path.return_value.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=False)))
                await svc.delete_project(PROJECT_SLUG)
        svc._repo.delete.assert_awaited_once_with(PROJECT_SLUG)


class TestGetStats:
    async def test_returns_books_count_from_repo(self):
        svc, _, _ = make_service(repo_get=_BASE_PROJECT_ROW, repo_count_books=4)
        result = await svc.get_stats(PROJECT_SLUG)
        assert result["books_count"] == 4

    async def test_returns_entity_count_from_neo4j(self):
        svc, _, neo4j_session = make_service(repo_get=_BASE_PROJECT_ROW)
        neo4j_session.run.return_value.data = AsyncMock(
            return_value=[{"count": 250}]
        )
        result = await svc.get_stats(PROJECT_SLUG)
        assert result["entity_count"] == 250

    async def test_returns_has_profile_true_when_redis_has_key(self):
        profile_data = json.dumps({"saga_id": PROJECT_SLUG, "entity_types": []}).encode()
        svc, redis, _ = make_service(repo_get=_BASE_PROJECT_ROW, redis_get=profile_data)
        result = await svc.get_stats(PROJECT_SLUG)
        assert result["has_profile"] is True

    async def test_returns_has_profile_false_when_no_redis(self):
        svc, _, _ = make_service(repo_get=_BASE_PROJECT_ROW, redis_get=None)
        result = await svc.get_stats(PROJECT_SLUG)
        assert result["has_profile"] is False

    async def test_returns_profile_types_count(self):
        profile = {
            "saga_id": PROJECT_SLUG,
            "entity_types": [{"type_name": "Spell"}, {"type_name": "House"}],
        }
        svc, redis, _ = make_service(
            repo_get=_BASE_PROJECT_ROW,
            redis_get=json.dumps(profile).encode(),
        )
        result = await svc.get_stats(PROJECT_SLUG)
        assert result["profile_types_count"] == 2

    async def test_slug_in_stats(self):
        svc, _, _ = make_service(repo_get=_BASE_PROJECT_ROW)
        result = await svc.get_stats(PROJECT_SLUG)
        assert result["slug"] == PROJECT_SLUG


async def _noop_to_thread(fn, *args, **kwargs):
    """Replacement for asyncio.to_thread in tests — just call fn directly."""
    return fn(*args, **kwargs)


class TestStoreBookFile:
    @staticmethod
    def _make_path_mocks():
        """Create mock objects for Path that pass the C2 path traversal check."""
        mock_file = MagicMock()
        mock_dir = MagicMock()
        # file_path.resolve() must start with file_dir.resolve()
        mock_dir.resolve = MagicMock(return_value=MagicMock(__str__=lambda s: "/data/projects/slug"))
        mock_file.resolve = MagicMock(return_value=MagicMock(__str__=lambda s: "/data/projects/slug/book1.epub"))
        mock_dir.__truediv__ = MagicMock(return_value=mock_file)
        mock_dir.exists = MagicMock(return_value=True)
        return mock_file, mock_dir

    async def test_writes_file_to_disk(self):
        file_row = {
            "id": FILE_ID,
            "filename": "book1.epub",
            "file_size": 5,
            "mime_type": "application/epub+zip",
            "book_num": 1,
            "book_id": None,
            "uploaded_at": "2026-03-14T00:00:00",
        }
        svc, _, _ = make_service(
            repo_get=_BASE_PROJECT_ROW,
            repo_add_file=file_row,
        )
        content = b"hello"
        with patch("app.services.project_service.Path") as mock_path:
            mock_file, mock_dir = self._make_path_mocks()
            mock_path.return_value.__truediv__ = MagicMock(return_value=mock_dir)
            mock_file.write_bytes = MagicMock()
            with patch("app.services.project_service.asyncio.to_thread", side_effect=_noop_to_thread):
                await svc.store_book_file(
                    PROJECT_SLUG, "book1.epub", content, 1, "application/epub+zip"
                )
            mock_file.write_bytes.assert_called_once_with(content)

    async def test_calls_add_file_record(self):
        file_row = {
            "id": FILE_ID, "filename": "book1.epub", "file_size": 5,
            "mime_type": "application/epub+zip", "book_num": 1,
            "book_id": None, "uploaded_at": "2026-03-14T00:00:00",
        }
        svc, _, _ = make_service(
            repo_get=_BASE_PROJECT_ROW,
            repo_add_file=file_row,
        )
        with patch("app.services.project_service.Path") as mock_path:
            mock_file, mock_dir = self._make_path_mocks()
            mock_path.return_value.__truediv__ = MagicMock(return_value=mock_dir)
            with patch("app.services.project_service.asyncio.to_thread", side_effect=_noop_to_thread):
                await svc.store_book_file(
                    PROJECT_SLUG, "book1.epub", b"data", 1, "application/epub+zip"
                )
        svc._repo.add_file.assert_awaited_once()

    async def test_returns_file_record(self):
        file_row = {
            "id": FILE_ID, "filename": "book1.epub", "file_size": 5,
            "mime_type": "application/epub+zip", "book_num": 1,
            "book_id": None, "uploaded_at": "2026-03-14T00:00:00",
        }
        svc, _, _ = make_service(
            repo_get=_BASE_PROJECT_ROW,
            repo_add_file=file_row,
        )
        with patch("app.services.project_service.Path") as mock_path:
            mock_file, mock_dir = self._make_path_mocks()
            mock_path.return_value.__truediv__ = MagicMock(return_value=mock_dir)
            with patch("app.services.project_service.asyncio.to_thread", side_effect=_noop_to_thread):
                result = await svc.store_book_file(
                    PROJECT_SLUG, "book1.epub", b"data", 1, "application/epub+zip"
                )
        assert result == file_row
