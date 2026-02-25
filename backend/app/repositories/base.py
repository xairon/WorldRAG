"""Base repository for Neo4j data access.

All repositories inherit from this base class which provides:
- Async session management
- Parameterized query execution
- Batch operations
- Transaction support
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.core.resilience import retry_neo4j_write

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)


_VALID_LABELS = frozenset(
    {
        "Book",
        "Chapter",
        "Chunk",
        "Series",
        "Character",
        "Skill",
        "Class",
        "Title",
        "Event",
        "Location",
        "Item",
        "Creature",
        "Faction",
        "Concept",
    }
)

_VALID_PROPERTIES = frozenset(
    {
        "name",
        "canonical_name",
        "id",
        "book_id",
        "title",
        "number",
        "position",
        "status",
    }
)


class Neo4jRepository:
    """Base class for Neo4j repositories.

    Provides common query execution patterns with automatic
    session management and error logging.
    """

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    @staticmethod
    def _validate_label(label: str) -> str:
        """Validate a Neo4j label against the whitelist to prevent injection."""
        if label not in _VALID_LABELS:
            raise ValueError(f"Invalid Neo4j label: {label!r}")
        return label

    @staticmethod
    def _validate_property(prop: str) -> str:
        """Validate a property name against the whitelist to prevent injection."""
        if prop not in _VALID_PROPERTIES:
            raise ValueError(f"Invalid Neo4j property: {prop!r}")
        return prop

    async def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read query and return results as list of dicts.

        Args:
            query: Cypher query string with $param placeholders.
            parameters: Query parameters.

        Returns:
            List of record dictionaries.
        """
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            logger.debug(
                "neo4j_read",
                query=query[:100],
                param_count=len(parameters) if parameters else 0,
                result_count=len(records),
            )
            return records

    @retry_neo4j_write(max_attempts=4)
    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a write query within a transaction.

        Args:
            query: Cypher query string with $param placeholders.
            parameters: Query parameters.

        Returns:
            List of record dictionaries (if any RETURN clause).
        """
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            summary = await result.consume()
            logger.info(
                "neo4j_write",
                query=query[:100],
                nodes_created=summary.counters.nodes_created,
                relationships_created=summary.counters.relationships_created,
                properties_set=summary.counters.properties_set,
            )
            return records

    @retry_neo4j_write(max_attempts=4)
    async def execute_batch(
        self,
        queries: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Execute multiple queries in a single transaction.

        Args:
            queries: List of (query, parameters) tuples.
        """
        async with self.driver.session() as session:
            async with session.begin_transaction() as tx:
                for query, params in queries:
                    await tx.run(query, params)
                await tx.commit()
            logger.info("neo4j_batch", query_count=len(queries))

    async def count(self, label: str) -> int:
        """Count nodes with a given label.

        Label is validated against a whitelist to prevent Cypher injection.
        """
        safe_label = self._validate_label(label)
        result = await self.execute_read(
            f"MATCH (n:{safe_label}) RETURN count(n) AS count",
        )
        return result[0]["count"] if result else 0

    async def exists(self, label: str, property_name: str, value: Any) -> bool:
        """Check if a node exists with a given property value.

        Label and property_name are validated against whitelists
        to prevent Cypher injection.
        """
        safe_label = self._validate_label(label)
        safe_prop = self._validate_property(property_name)
        result = await self.execute_read(
            f"MATCH (n:{safe_label} {{{safe_prop}: $value}}) RETURN count(n) > 0 AS exists",
            {"value": value},
        )
        return result[0]["exists"] if result else False
