"""Tests for app.repositories.base — Neo4j base repository."""

from __future__ import annotations

from unittest.mock import AsyncMock

from app.repositories.base import Neo4jRepository


class TestExecuteRead:
    async def test_calls_session_run(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        repo = Neo4jRepository(mock_neo4j_driver_with_session)
        await repo.execute_read("MATCH (n) RETURN n", {"id": 1})
        mock_neo4j_session.run.assert_called_once_with(
            "MATCH (n) RETURN n",
            {"id": 1},
        )

    async def test_returns_data(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[{"n": "test"}],
        )
        repo = Neo4jRepository(mock_neo4j_driver_with_session)
        result = await repo.execute_read("MATCH (n) RETURN n")
        assert result == [{"n": "test"}]


class TestExecuteWrite:
    async def test_calls_consume(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        repo = Neo4jRepository(mock_neo4j_driver_with_session)
        await repo.execute_write("CREATE (n:Test)")
        mock_neo4j_session.run.return_value.consume.assert_called_once()


class TestExecuteBatch:
    async def test_uses_transaction(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        repo = Neo4jRepository(mock_neo4j_driver_with_session)
        queries = [("QUERY 1", {"a": 1}), ("QUERY 2", {"b": 2})]
        await repo.execute_batch(queries)
        mock_neo4j_session.begin_transaction.assert_called_once()


class TestCount:
    async def test_count_returns_int(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[{"count": 42}],
        )
        repo = Neo4jRepository(mock_neo4j_driver_with_session)
        result = await repo.count("Character")
        assert result == 42


class TestExists:
    async def test_exists_returns_bool(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[{"exists": True}],
        )
        repo = Neo4jRepository(mock_neo4j_driver_with_session)
        result = await repo.exists("Character", "name", "Jake")
        assert result is True
