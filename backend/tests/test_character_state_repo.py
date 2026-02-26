"""Tests for app.repositories.character_state_repo — Character state ledger queries."""

from __future__ import annotations

from unittest.mock import AsyncMock

from app.repositories.character_state_repo import CharacterStateRepository

BOOK_ID = "book-uuid-001"
CHARACTER = "Jake Thayne"


class TestGetStatsAtChapter:
    async def test_returns_empty_list(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_stats_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert result == []

    async def test_returns_aggregated_stats(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[
                {"stat_name": "Agility", "value": 150, "last_changed_chapter": 8},
                {"stat_name": "Strength", "value": 200, "last_changed_chapter": 10},
            ],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_stats_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert len(result) == 2
        assert result[0]["stat_name"] == "Agility"
        assert result[1]["value"] == 200

    async def test_passes_correct_params(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        await repo.get_stats_at_chapter(CHARACTER, BOOK_ID, chapter=5)
        call_args = mock_neo4j_session.run.call_args
        params = call_args[0][1]
        assert params["name"] == CHARACTER
        assert params["book_id"] == BOOK_ID
        assert params["chapter"] == 5


class TestGetLevelAtChapter:
    async def test_returns_default_when_empty(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_level_at_chapter(CHARACTER, BOOK_ID, chapter=1)
        assert result == {"level": None, "realm": "", "since_chapter": None}

    async def test_returns_level_data(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[{"level": 88, "realm": "D-grade", "since_chapter": 42}],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_level_at_chapter(CHARACTER, BOOK_ID, chapter=42)
        assert result["level"] == 88
        assert result["realm"] == "D-grade"
        assert result["since_chapter"] == 42


class TestGetSkillsAtChapter:
    async def test_returns_empty_list(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_skills_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert result == []

    async def test_returns_skills(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "name": "Arcane Powershot",
                    "rank": "Legendary",
                    "skill_type": "Active",
                    "description": "A powerful arcane shot",
                    "acquired_chapter": 5,
                },
            ],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_skills_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert len(result) == 1
        assert result[0]["name"] == "Arcane Powershot"


class TestGetClassesAtChapter:
    async def test_returns_empty_list(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_classes_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert result == []

    async def test_returns_classes(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "name": "Arcane Hunter",
                    "tier": "C-grade",
                    "description": "A hunter class",
                    "acquired_chapter": 3,
                },
            ],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_classes_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert len(result) == 1
        assert result[0]["name"] == "Arcane Hunter"


class TestGetTitlesAtChapter:
    async def test_returns_empty_list(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_titles_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert result == []

    async def test_returns_titles(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "name": "Hydra Slayer",
                    "description": "Slew a hydra",
                    "effects": "+10% damage vs hydras",
                    "acquired_chapter": 42,
                },
            ],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_titles_at_chapter(CHARACTER, BOOK_ID, chapter=42)
        assert len(result) == 1
        assert result[0]["name"] == "Hydra Slayer"


class TestGetItemsAtChapter:
    async def test_returns_empty_list(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_items_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert result == []

    async def test_returns_items_with_grants(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "name": "Nanoblade",
                    "item_type": "Weapon",
                    "rarity": "Legendary",
                    "description": "A legendary blade",
                    "acquired_chapter": 7,
                    "grants": ["Shadow Strike"],
                },
            ],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_items_at_chapter(CHARACTER, BOOK_ID, chapter=10)
        assert len(result) == 1
        assert result[0]["grants"] == ["Shadow Strike"]


class TestGetChapterChanges:
    async def test_returns_empty_list(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_chapter_changes(CHARACTER, BOOK_ID, chapter=42)
        assert result == []

    async def test_returns_changes(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "category": "level",
                    "name": "level",
                    "action": "set",
                    "value_delta": None,
                    "value_after": 88,
                    "detail": "D-grade",
                    "chapter": 42,
                },
                {
                    "category": "stat",
                    "name": "Perception",
                    "action": "add",
                    "value_delta": 5,
                    "value_after": None,
                    "detail": None,
                    "chapter": 42,
                },
            ],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_chapter_changes(CHARACTER, BOOK_ID, chapter=42)
        assert len(result) == 2
        assert result[0]["category"] == "level"
        assert result[1]["name"] == "Perception"


class TestGetCharacterInfo:
    async def test_returns_none_when_empty(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_character_info(CHARACTER)
        assert result is None

    async def test_returns_character_data(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "canonical_name": CHARACTER,
                    "name": "Jake",
                    "role": "protagonist",
                    "species": "Human",
                    "description": "An archer with arcane powers",
                    "aliases": ["Thayne", "Chosen of the Malefic Viper"],
                },
            ],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_character_info(CHARACTER)
        assert result is not None
        assert result["canonical_name"] == CHARACTER
        assert result["role"] == "protagonist"


class TestGetTotalChapters:
    async def test_returns_zero_when_empty(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_total_chapters(BOOK_ID)
        assert result == 0

    async def test_returns_count(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        mock_neo4j_session.run.return_value.data = AsyncMock(
            return_value=[{"total": 142}],
        )
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_total_chapters(BOOK_ID)
        assert result == 142


class TestGetProgressionMilestones:
    async def test_returns_empty_tuple_when_empty(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        rows, total = await repo.get_progression_milestones(CHARACTER, BOOK_ID)
        assert rows == []
        assert total == 0

    async def test_passes_category_filter(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        await repo.get_progression_milestones(CHARACTER, BOOK_ID, category="level")
        # Both count and data queries should have been called
        assert mock_neo4j_session.run.call_count == 2

    async def test_passes_pagination_params(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        await repo.get_progression_milestones(CHARACTER, BOOK_ID, offset=10, limit=25)
        # Second call is the data query with offset/limit
        data_call = mock_neo4j_session.run.call_args_list[1]
        params = data_call[0][1]
        assert params["offset"] == 10
        assert params["limit"] == 25


class TestGetChangesBetweenChapters:
    async def test_returns_empty_list(
        self,
        mock_neo4j_driver_with_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        result = await repo.get_changes_between_chapters(
            CHARACTER, BOOK_ID, from_chapter=5, to_chapter=10
        )
        assert result == []

    async def test_passes_chapter_range_params(
        self,
        mock_neo4j_driver_with_session,
        mock_neo4j_session,
    ):
        repo = CharacterStateRepository(mock_neo4j_driver_with_session)
        await repo.get_changes_between_chapters(CHARACTER, BOOK_ID, from_chapter=5, to_chapter=10)
        call_args = mock_neo4j_session.run.call_args
        params = call_args[0][1]
        assert params["from_chapter"] == 5
        assert params["to_chapter"] == 10
        assert params["name"] == CHARACTER
        assert params["book_id"] == BOOK_ID
