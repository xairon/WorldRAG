"""Business logic for Project lifecycle management.

Coordinates PostgreSQL (metadata), Redis (saga profiles), Neo4j (KG entities),
and the local filesystem (uploaded book files).
"""

from __future__ import annotations

import asyncio
import json
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


class ProjectService:
    """Service layer for project operations.

    Owns cascading create / delete across all storage backends.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        redis: Redis,
        neo4j_driver: AsyncDriver,
    ) -> None:
        self._pool = pool
        self._redis = redis
        self._neo4j = neo4j_driver
        self._repo = ProjectRepository(pool)

    @property
    def repo(self) -> ProjectRepository:
        """Public accessor for the repository (used by route handlers)."""
        return self._repo

    # --- Create ---

    async def create_project(
        self,
        slug: str,
        name: str,
        description: str = "",
    ) -> dict[str, Any] | None:
        """Create a project record and provision its filesystem directory.

        Args:
            slug: URL-safe unique identifier.
            name: Human-readable project name.
            description: Optional description.

        Returns:
            Created project row dict, or None.
        """
        row = await self._repo.create(slug, name, description)

        project_dir = Path(settings.project_data_dir) / slug
        project_dir.mkdir(parents=True, exist_ok=True)
        logger.info("project_dir_created", slug=slug, path=str(project_dir))

        return row

    # --- Read ---

    async def get_project(self, slug: str) -> dict[str, Any] | None:
        """Fetch a single project by slug.

        Args:
            slug: The project slug.

        Returns:
            Project row dict or None.
        """
        return await self._repo.get_by_slug(slug)

    async def list_projects(self) -> list[dict[str, Any]]:
        """List all projects enriched with books_count and has_profile.

        Returns:
            List of enriched project dicts.
        """
        rows = await self._repo.list_all()
        enriched = []
        for row in rows:
            slug = row["slug"]
            books_count = await self._repo.count_books(slug)
            profile_raw = await self._redis.get(f"saga_profile:{slug}")
            has_profile = profile_raw is not None
            # H11: entity_count defaults to 0 in list view to avoid N+1 Neo4j queries.
            # TODO: Add a batch query or materialized count for entity_count in list_projects.
            enriched.append({
                **row,
                "books_count": books_count,
                "has_profile": has_profile,
                "entity_count": 0,
            })
        return enriched

    # --- Update ---

    async def update_project(self, slug: str, **fields: Any) -> dict[str, Any] | None:
        """Update project metadata fields.

        Args:
            slug: The project slug.
            **fields: Column-value pairs to update (None values are ignored by repo).

        Returns:
            Updated project row dict, or None if not found.
        """
        return await self._repo.update(slug, **fields)

    # --- Delete (cascade) ---

    async def delete_project(self, slug: str) -> None:
        """Cascade-delete a project across all storage backends.

        Order of operations:
        1. Delete PostgreSQL row (CASCADE deletes project_files).
        2. Delete Redis saga_profile:{slug}.
        3. Delete Neo4j entities with group_id == slug + Community nodes.
        4. Delete filesystem directory.

        Args:
            slug: The project slug to delete.
        """
        # 1. PostgreSQL (CASCADE handles project_files)
        await self._repo.delete(slug)

        # 2. Redis saga profile
        await self._redis.delete(f"saga_profile:{slug}")

        # 3. Neo4j: entities and communities belonging to this project
        # C7: Scope deletes by label to avoid unbounded property scan
        async with self._neo4j.session() as session:
            await session.run(
                "MATCH (n:Entity {group_id: $slug}) DETACH DELETE n",
                {"slug": slug},
            )
            await session.run(
                "MATCH (n:Episodic {group_id: $slug}) DETACH DELETE n",
                {"slug": slug},
            )
            await session.run(
                "MATCH (c:Community {saga_id: $slug}) DETACH DELETE c",
                {"slug": slug},
            )

        # 4. Filesystem
        project_dir = Path(settings.project_data_dir) / slug
        if project_dir.exists():
            shutil.rmtree(project_dir)
            logger.info("project_dir_deleted", slug=slug, path=str(project_dir))

        logger.info("project_deleted_cascade", slug=slug)

    # --- Stats ---

    async def get_stats(self, slug: str) -> dict[str, Any]:
        """Return aggregate statistics for a project.

        Args:
            slug: The project slug.

        Returns:
            Dict with books_count, entity_count, community_count,
            has_profile, profile_types_count, slug.
        """
        books_count = await self._repo.count_books(slug)

        # Neo4j: entity count
        entity_count = 0
        community_count = 0
        async with self._neo4j.session() as session:
            entity_result = await session.run(
                "MATCH (n:Entity {group_id: $slug}) RETURN count(n) AS count",
                {"slug": slug},
            )
            entity_records = await entity_result.data()
            if entity_records:
                entity_count = entity_records[0].get("count", 0)

            community_result = await session.run(
                "MATCH (c:Community {saga_id: $slug}) RETURN count(c) AS count",
                {"slug": slug},
            )
            community_records = await community_result.data()
            if community_records:
                community_count = community_records[0].get("count", 0)

        # Redis: profile
        profile_raw = await self._redis.get(f"saga_profile:{slug}")
        has_profile = profile_raw is not None
        profile_types_count = 0
        if has_profile and profile_raw:
            try:
                profile_data = json.loads(profile_raw)
                profile_types_count = len(profile_data.get("entity_types", []))
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "slug": slug,
            "books_count": books_count,
            "chapters_total": 0,  # reserved for future chapter-level query
            "entity_count": entity_count,
            "entities_total": entity_count,
            "community_count": community_count,
            "has_profile": has_profile,
            "profile_types_count": profile_types_count,
        }

    # --- File storage ---

    async def store_book_file(
        self,
        slug: str,
        filename: str,
        file_content: bytes,
        book_num: int,
        mime_type: str,
    ) -> dict[str, Any] | None:
        """Write file bytes to disk and record in project_files.

        Args:
            slug: Project slug (used to locate filesystem directory).
            filename: Original filename.
            file_content: Raw bytes to persist.
            book_num: Ordinal position within the saga (1-based).
            mime_type: MIME type string.

        Returns:
            Created project_file row dict, or None.
        """
        from pathlib import PurePosixPath

        safe_name = PurePosixPath(filename).name
        if not safe_name or safe_name.startswith("."):
            raise ValueError(f"Invalid filename: {filename!r}")

        project_dir = Path(settings.project_data_dir) / slug
        file_dir = project_dir
        file_path = project_dir / safe_name

        # C2: Path traversal check — ensure resolved path stays within project dir
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(file_dir.resolve())):
            raise ValueError(f"Path traversal detected: {filename!r}")

        # C3: Use asyncio.to_thread to avoid blocking file I/O in async context
        await asyncio.to_thread(file_path.write_bytes, file_content)
        logger.info(
            "book_file_written",
            slug=slug,
            filename=safe_name,
            size=len(file_content),
        )

        # Fetch project to get id
        project_row = await self._repo.get_by_slug(slug)
        project_id = project_row["id"] if project_row else slug

        return await self._repo.add_file(
            project_id,
            safe_name,
            str(file_path),
            len(file_content),
            mime_type,
            book_num,
        )
