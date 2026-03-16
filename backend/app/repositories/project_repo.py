"""PostgreSQL repository for Project and ProjectFile entities.

Uses asyncpg connection pool directly (no ORM).
All queries use parameterized $N placeholders.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    import asyncpg

logger = get_logger(__name__)


class ProjectRepository:
    """Repository for project and project_file CRUD operations backed by PostgreSQL."""

    ALLOWED_UPDATE_COLUMNS: frozenset[str] = frozenset({
        "name", "description", "cover_image",
    })

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- Project operations ---

    async def create(
        self,
        slug: str,
        name: str,
        description: str = "",
    ) -> dict[str, Any] | None:
        """INSERT a new project row and return it.

        Args:
            slug: URL-safe unique identifier.
            name: Human-readable project name.
            description: Optional description.

        Returns:
            Row dict on success, None if insert returned nothing.
        """
        query = """
            INSERT INTO projects (slug, name, description)
            VALUES ($1, $2, $3)
            RETURNING *
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, slug, name, description)
            if row is None:
                return None
            result = dict(row)
            logger.info("project_created", slug=slug)
            return result

    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        """Fetch a project by its slug.

        Args:
            slug: The project slug to look up.

        Returns:
            Row dict if found, None otherwise.
        """
        query = "SELECT * FROM projects WHERE slug = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, slug)
            return dict(row) if row is not None else None

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all projects ordered by creation date descending.

        Returns:
            List of project row dicts.
        """
        query = "SELECT * FROM projects ORDER BY created_at DESC"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(r) for r in rows]

    async def update(
        self,
        slug: str,
        **fields: Any,
    ) -> dict[str, Any] | None:
        """Dynamic UPDATE — only non-None fields are written.

        Always appends updated_at = NOW().

        Args:
            slug: The project slug to update.
            **fields: Keyword arguments for columns to update (None values skipped).

        Returns:
            Updated row dict, or None if project not found.
        """
        non_null = {k: v for k, v in fields.items() if v is not None}
        if not non_null:
            return await self.get_by_slug(slug)

        # Validate column names against allowlist to prevent SQL injection
        invalid_cols = set(non_null.keys()) - self.ALLOWED_UPDATE_COLUMNS
        if invalid_cols:
            raise ValueError(f"Disallowed update columns: {invalid_cols}")

        set_clauses = []
        params: list[Any] = []
        idx = 1
        for col, val in non_null.items():
            set_clauses.append(f"{col} = ${idx}")
            params.append(val)
            idx += 1

        set_clauses.append(f"updated_at = NOW()")
        # slug is the WHERE param — add last
        params.append(slug)

        query = f"""
            UPDATE projects
            SET {', '.join(set_clauses)}
            WHERE slug = ${idx}
            RETURNING *
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row is not None else None

    async def delete(self, slug: str) -> str | None:
        """DELETE a project by slug.

        Args:
            slug: The project slug to delete.

        Returns:
            The deleted slug on success, None if not found.
        """
        query = "DELETE FROM projects WHERE slug = $1 RETURNING slug"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, slug)
            if row is None:
                return None
            logger.info("project_deleted", slug=slug)
            return row["slug"]

    # --- ProjectFile operations ---

    async def add_file(
        self,
        project_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        book_num: int,
    ) -> dict[str, Any] | None:
        """INSERT a project_file record and return it.

        Args:
            project_id: UUID of the parent project.
            filename: Original filename.
            file_path: Absolute path on disk.
            file_size: File size in bytes.
            mime_type: MIME type string.
            book_num: Ordinal position within the saga (1-based).

        Returns:
            Inserted row dict, or None.
        """
        query = """
            INSERT INTO project_files
                (project_id, filename, file_path, file_size, mime_type, book_num)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query, project_id, filename, file_path, file_size, mime_type, book_num
            )
            return dict(row) if row is not None else None

    async def list_files(self, project_id: str) -> list[dict[str, Any]]:
        """Return all files for a project ordered by book_num.

        Args:
            project_id: UUID of the project.

        Returns:
            List of project_file row dicts.
        """
        query = """
            SELECT * FROM project_files
            WHERE project_id = $1
            ORDER BY book_num
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, project_id)
            return [dict(r) for r in rows]

    async def update_file_book_id(self, file_id: str, book_id: str) -> None:
        """Set book_id on a project_file after successful book ingestion.

        Args:
            file_id: UUID of the project_file row.
            book_id: Neo4j book ID to associate.
        """
        query = "UPDATE project_files SET book_id = $1 WHERE id = $2"
        async with self._pool.acquire() as conn:
            await conn.execute(query, book_id, file_id)

    async def list_books(self, slug: str) -> list[dict[str, Any]]:
        """Return project_files with a non-null book_id for a project slug."""
        query = """
            SELECT pf.*
            FROM projects p
            JOIN project_files pf ON pf.project_id = p.id
            WHERE p.slug = $1
              AND pf.book_id IS NOT NULL
            ORDER BY pf.book_num
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, slug)
            return [dict(r) for r in rows]

    async def count_books(self, slug: str) -> int:
        """Count ingested books (book_id IS NOT NULL) for a project.

        Args:
            slug: The project slug.

        Returns:
            Number of project files with a non-null book_id.
        """
        query = """
            SELECT COUNT(pf.id)
            FROM projects p
            JOIN project_files pf ON pf.project_id = p.id
            WHERE p.slug = $1
              AND pf.book_id IS NOT NULL
        """
        async with self._pool.acquire() as conn:
            val = await conn.fetchval(query, slug)
            return int(val) if val is not None else 0
