"""Repository for character state reconstruction queries.

Implements the Stat Ledger pattern: aggregates immutable StateChange
nodes to reconstruct character state at any chapter.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

logger = get_logger(__name__)


class CharacterStateRepository(Neo4jRepository):
    """Read-only queries for reconstructing character state at any chapter."""

    async def get_stats_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Aggregate stat deltas up to a chapter.

        Returns list of {stat_name, value, last_changed_chapter}.
        """
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id
              AND sc.chapter <= $chapter
              AND sc.category = 'stat'
            WITH sc.name AS stat_name,
                 sum(sc.value_delta) AS value,
                 max(sc.chapter) AS last_changed_chapter
            RETURN stat_name, value, last_changed_chapter
            ORDER BY stat_name
            """,
            {"name": character_name, "book_id": book_id, "chapter": chapter},
        )

    async def get_level_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> dict[str, Any]:
        """Get latest level change at or before chapter.

        Returns {level, realm, since_chapter}.
        """
        rows = await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id
              AND sc.chapter <= $chapter
              AND sc.category = 'level'
            ORDER BY sc.chapter DESC
            LIMIT 1
            RETURN sc.value_after AS level, sc.detail AS realm, sc.chapter AS since_chapter
            """,
            {"name": character_name, "book_id": book_id, "chapter": chapter},
        )
        if rows:
            return rows[0]
        return {"level": None, "realm": "", "since_chapter": None}

    async def get_skills_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get skills the character has at a chapter (temporal filtering)."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:HAS_SKILL]->(sk:Skill)
            WHERE r.valid_from_chapter <= $chapter
              AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter > $chapter)
            RETURN sk.name AS name, sk.rank AS rank, sk.skill_type AS skill_type,
                   sk.description AS description, r.valid_from_chapter AS acquired_chapter
            ORDER BY r.valid_from_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_classes_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get classes the character has at a chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:HAS_CLASS]->(cls:Class)
            WHERE r.valid_from_chapter <= $chapter
              AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter > $chapter)
            RETURN cls.name AS name, cls.tier AS tier, cls.description AS description,
                   r.valid_from_chapter AS acquired_chapter
            ORDER BY r.valid_from_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_titles_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get titles the character holds at a chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:HAS_TITLE]->(ti:Title)
            WHERE (r.acquired_chapter IS NULL OR r.acquired_chapter <= $chapter)
            RETURN ti.name AS name, ti.description AS description,
                   ti.effects AS effects, r.acquired_chapter AS acquired_chapter
            ORDER BY r.acquired_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_items_at_chapter(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get items the character possesses at a chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[r:POSSESSES]->(it:Item)
            WHERE r.valid_from_chapter <= $chapter
              AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter > $chapter)
            OPTIONAL MATCH (it)-[:GRANTS_SKILL]->(sk:Skill)
            WITH it, r, collect(sk.name) AS grants
            RETURN it.name AS name, it.item_type AS item_type, it.rarity AS rarity,
                   it.description AS description, r.valid_from_chapter AS acquired_chapter,
                   grants
            ORDER BY r.valid_from_chapter
            """,
            {"name": character_name, "chapter": chapter},
        )

    async def get_chapter_changes(
        self, character_name: str, book_id: str, chapter: int
    ) -> list[dict[str, Any]]:
        """Get all StateChange records for a specific chapter."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id AND sc.chapter = $chapter
            RETURN sc.category AS category, sc.name AS name, sc.action AS action,
                   sc.value_delta AS value_delta, sc.value_after AS value_after,
                   sc.detail AS detail, sc.chapter AS chapter
            ORDER BY sc.category, sc.name
            """,
            {"name": character_name, "book_id": book_id, "chapter": chapter},
        )

    async def get_character_info(
        self, character_name: str, book_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get basic character info (role, species, description, aliases)."""
        rows = await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})
            RETURN ch.canonical_name AS canonical_name,
                   ch.name AS name,
                   ch.role AS role,
                   ch.species AS species,
                   ch.description AS description,
                   ch.aliases AS aliases
            LIMIT 1
            """,
            {"name": character_name},
        )
        return rows[0] if rows else None

    async def get_total_chapters(self, book_id: str) -> int:
        """Get total chapter count for a book."""
        rows = await self.execute_read(
            """
            MATCH (c:Chapter {book_id: $book_id})
            RETURN count(c) AS total
            """,
            {"book_id": book_id},
        )
        return rows[0]["total"] if rows else 0

    async def get_progression_milestones(
        self,
        character_name: str,
        book_id: str,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated progression milestones.

        Returns (milestones, total_count).
        """
        category_filter = "AND sc.category = $category" if category else ""

        count_rows = await self.execute_read(
            f"""
            MATCH (ch:Character {{canonical_name: $name}})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id {category_filter}
            RETURN count(sc) AS total
            """,
            {"name": character_name, "book_id": book_id, "category": category},
        )
        total = count_rows[0]["total"] if count_rows else 0

        rows = await self.execute_read(
            f"""
            MATCH (ch:Character {{canonical_name: $name}})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id {category_filter}
            RETURN sc.chapter AS chapter, sc.category AS category,
                   sc.name AS name, sc.action AS action,
                   sc.value_delta AS value_delta, sc.value_after AS value_after,
                   sc.detail AS detail
            ORDER BY sc.chapter, sc.category, sc.name
            SKIP $offset LIMIT $limit
            """,
            {
                "name": character_name,
                "book_id": book_id,
                "category": category,
                "offset": offset,
                "limit": limit,
            },
        )

        return rows, total

    async def get_changes_between_chapters(
        self,
        character_name: str,
        book_id: str,
        from_chapter: int,
        to_chapter: int,
    ) -> list[dict[str, Any]]:
        """Get all StateChanges between two chapters (exclusive from, inclusive to)."""
        return await self.execute_read(
            """
            MATCH (ch:Character {canonical_name: $name})-[:STATE_CHANGED]->(sc:StateChange)
            WHERE sc.book_id = $book_id
              AND sc.chapter > $from_chapter
              AND sc.chapter <= $to_chapter
            RETURN sc.chapter AS chapter, sc.category AS category,
                   sc.name AS name, sc.action AS action,
                   sc.value_delta AS value_delta, sc.value_after AS value_after,
                   sc.detail AS detail
            ORDER BY sc.chapter, sc.category
            """,
            {
                "name": character_name,
                "book_id": book_id,
                "from_chapter": from_chapter,
                "to_chapter": to_chapter,
            },
        )
