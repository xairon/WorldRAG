"""Tests for app.api.routes.characters — Character State API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.main import create_app

BOOK_ID = "book-uuid-001"
CHARACTER = "Jake Thayne"


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def mock_repo():
    """Return a fully mocked CharacterStateRepository instance."""
    repo = AsyncMock()

    # Default: character exists
    repo.get_character_info.return_value = {
        "canonical_name": CHARACTER,
        "name": "Jake",
        "role": "protagonist",
        "species": "Human",
        "description": "An archer with arcane powers",
        "aliases": ["Thayne", "Chosen of the Malefic Viper"],
    }
    repo.get_total_chapters.return_value = 142
    repo.get_stats_at_chapter.return_value = [
        {"stat_name": "Perception", "value": 200, "last_changed_chapter": 42},
    ]
    repo.get_level_at_chapter.return_value = {
        "level": 88,
        "realm": "D-grade",
        "since_chapter": 42,
    }
    repo.get_skills_at_chapter.return_value = [
        {
            "name": "Arcane Powershot",
            "rank": "Legendary",
            "skill_type": "Active",
            "description": "A powerful arcane shot",
            "acquired_chapter": 5,
        },
    ]
    repo.get_classes_at_chapter.return_value = [
        {
            "name": "Arcane Hunter",
            "tier": 3,
            "description": "A hunter class",
            "acquired_chapter": 3,
        },
    ]
    repo.get_titles_at_chapter.return_value = [
        {
            "name": "Hydra Slayer",
            "description": "Slew a hydra",
            "effects": ["+10% damage vs hydras"],
            "acquired_chapter": 42,
        },
    ]
    repo.get_items_at_chapter.return_value = [
        {
            "name": "Nanoblade",
            "item_type": "Weapon",
            "rarity": "Legendary",
            "description": "A legendary blade",
            "acquired_chapter": 7,
            "grants": ["Shadow Strike"],
        },
    ]
    repo.get_chapter_changes.return_value = [
        {
            "chapter": 42,
            "category": "stat",
            "name": "Perception",
            "action": "gain",
            "value_delta": 5,
            "value_after": None,
            "detail": "",
        },
    ]
    repo.get_progression_milestones.return_value = ([], 15)
    repo.get_changes_between_chapters.return_value = []
    return repo


@pytest.fixture
def app(mock_repo):
    """Create a test app with mocked Neo4j driver and repository."""
    test_app = create_app()

    # Override lifespan by injecting a mock driver into app state
    mock_driver = AsyncMock()
    test_app.state.neo4j_driver = mock_driver

    # Patch CharacterStateRepository so it returns our mock
    with patch(
        "app.api.routes.characters.CharacterStateRepository",
        return_value=mock_repo,
    ):
        yield test_app


@pytest.fixture
async def client(app):
    """Async HTTP client for testing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# -- GET /{name}/at/{chapter} ------------------------------------------------


class TestGetCharacterStateAtChapter:
    async def test_404_for_unknown_character(self, mock_repo):
        """Returns 404 when character does not exist."""
        mock_repo.get_character_info.return_value = None

        test_app = create_app()
        test_app.state.neo4j_driver = AsyncMock()

        with patch(
            "app.api.routes.characters.CharacterStateRepository",
            return_value=mock_repo,
        ):
            transport = httpx.ASGITransport(app=test_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get(f"/api/characters/UnknownChar/at/10?book_id={BOOK_ID}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_200_with_correct_snapshot_shape(self, client, mock_repo):
        """Returns 200 with full snapshot structure."""
        resp = await client.get(f"/api/characters/{CHARACTER}/at/42?book_id={BOOK_ID}")

        assert resp.status_code == 200
        data = resp.json()

        # Top-level fields
        assert data["character_name"] == "Jake"
        assert data["canonical_name"] == CHARACTER
        assert data["book_id"] == BOOK_ID
        assert data["as_of_chapter"] == 42
        assert data["total_chapters_in_book"] == 142
        assert data["role"] == "protagonist"
        assert data["species"] == "Human"

        # Level
        assert data["level"]["level"] == 88
        assert data["level"]["realm"] == "D-grade"

        # Stats
        assert len(data["stats"]) == 1
        assert data["stats"][0]["name"] == "Perception"
        assert data["stats"][0]["value"] == 200

        # Skills
        assert len(data["skills"]) == 1
        assert data["skills"][0]["name"] == "Arcane Powershot"

        # Classes
        assert len(data["classes"]) == 1
        assert data["classes"][0]["name"] == "Arcane Hunter"

        # Titles
        assert len(data["titles"]) == 1
        assert data["titles"][0]["name"] == "Hydra Slayer"

        # Items
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Nanoblade"
        assert data["items"][0]["grants"] == ["Shadow Strike"]

        # Chapter changes
        assert len(data["chapter_changes"]) == 1
        assert data["chapter_changes"][0]["category"] == "stat"

        # Aliases
        assert "Thayne" in data["aliases"]

    async def test_calls_repo_methods_in_parallel(self, client, mock_repo):
        """Verifies all repo methods are called with correct params."""
        await client.get(f"/api/characters/{CHARACTER}/at/42?book_id={BOOK_ID}")

        mock_repo.get_character_info.assert_called_once_with(CHARACTER)
        mock_repo.get_stats_at_chapter.assert_called_once_with(CHARACTER, BOOK_ID, 42)
        mock_repo.get_level_at_chapter.assert_called_once_with(CHARACTER, BOOK_ID, 42)
        mock_repo.get_skills_at_chapter.assert_called_once_with(CHARACTER, BOOK_ID, 42)
        mock_repo.get_classes_at_chapter.assert_called_once_with(CHARACTER, BOOK_ID, 42)
        mock_repo.get_titles_at_chapter.assert_called_once_with(CHARACTER, BOOK_ID, 42)
        mock_repo.get_items_at_chapter.assert_called_once_with(CHARACTER, BOOK_ID, 42)
        mock_repo.get_chapter_changes.assert_called_once_with(CHARACTER, BOOK_ID, 42)
        mock_repo.get_total_chapters.assert_called_once_with(BOOK_ID)


# -- GET /{name}/progression --------------------------------------------------


class TestGetCharacterProgression:
    async def test_returns_empty_milestones(self, client, mock_repo):
        """Returns 200 with empty milestones list."""
        mock_repo.get_progression_milestones.return_value = ([], 0)

        resp = await client.get(f"/api/characters/{CHARACTER}/progression?book_id={BOOK_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["character_name"] == CHARACTER
        assert data["milestones"] == []
        assert data["total"] == 0

    async def test_returns_milestones_with_pagination(self, client, mock_repo):
        """Returns paginated milestones."""
        mock_repo.get_progression_milestones.return_value = (
            [
                {
                    "chapter": 5,
                    "category": "skill",
                    "name": "Arcane Powershot",
                    "action": "gain",
                    "value_delta": None,
                    "value_after": None,
                    "detail": "Acquired from tutorial",
                },
            ],
            10,
        )

        resp = await client.get(
            f"/api/characters/{CHARACTER}/progression?book_id={BOOK_ID}&offset=0&limit=5"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["milestones"]) == 1
        assert data["total"] == 10
        assert data["offset"] == 0
        assert data["limit"] == 5

    async def test_passes_category_filter(self, client, mock_repo):
        """Passes category filter to the repo."""
        await client.get(f"/api/characters/{CHARACTER}/progression?book_id={BOOK_ID}&category=stat")

        mock_repo.get_progression_milestones.assert_called_once_with(
            CHARACTER, BOOK_ID, category="stat", offset=0, limit=50
        )


# -- GET /{name}/compare -----------------------------------------------------


class TestCompareCharacterState:
    async def test_returns_comparison(self, client, mock_repo):
        """Returns 200 with comparison structure."""
        mock_repo.get_stats_at_chapter.side_effect = [
            [{"stat_name": "Strength", "value": 100, "last_changed_chapter": 5}],
            [{"stat_name": "Strength", "value": 150, "last_changed_chapter": 10}],
        ]
        mock_repo.get_level_at_chapter.side_effect = [
            {"level": 50, "realm": "E-grade", "since_chapter": 3},
            {"level": 88, "realm": "D-grade", "since_chapter": 42},
        ]
        mock_repo.get_changes_between_chapters.return_value = [
            {
                "chapter": 8,
                "category": "skill",
                "name": "Shadow Step",
                "action": "gain",
                "value_delta": None,
                "value_after": None,
                "detail": "",
            },
        ]

        resp = await client.get(
            f"/api/characters/{CHARACTER}/compare?book_id={BOOK_ID}&from=5&to=42"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["character_name"] == CHARACTER
        assert data["from_chapter"] == 5
        assert data["to_chapter"] == 42
        assert data["level_from"] == 50
        assert data["level_to"] == 88

        # Stat diffs
        assert len(data["stat_diffs"]) == 1
        assert data["stat_diffs"][0]["name"] == "Strength"
        assert data["stat_diffs"][0]["delta"] == 50

        # Skill gained
        assert "Shadow Step" in data["skills"]["gained"]
        assert data["total_changes"] == 1

    async def test_no_diffs_when_same_chapter(self, client, mock_repo):
        """When from == to, no stat diffs should appear."""
        same_stats = [{"stat_name": "Strength", "value": 100, "last_changed_chapter": 5}]
        mock_repo.get_stats_at_chapter.side_effect = [same_stats, same_stats]
        mock_repo.get_level_at_chapter.side_effect = [
            {"level": 50, "realm": "", "since_chapter": 5},
            {"level": 50, "realm": "", "since_chapter": 5},
        ]
        mock_repo.get_changes_between_chapters.return_value = []

        resp = await client.get(
            f"/api/characters/{CHARACTER}/compare?book_id={BOOK_ID}&from=5&to=5"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["stat_diffs"] == []
        assert data["total_changes"] == 0


# -- GET /{name}/summary -----------------------------------------------------


class TestGetCharacterSummary:
    async def test_404_for_unknown_character(self, mock_repo):
        """Returns 404 when character does not exist."""
        mock_repo.get_character_info.return_value = None

        test_app = create_app()
        test_app.state.neo4j_driver = AsyncMock()

        with patch(
            "app.api.routes.characters.CharacterStateRepository",
            return_value=mock_repo,
        ):
            transport = httpx.ASGITransport(app=test_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/characters/UnknownChar/summary")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_returns_summary_without_chapter(self, client, mock_repo):
        """Returns 200 with basic summary when no chapter specified."""
        resp = await client.get(f"/api/characters/{CHARACTER}/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Jake"
        assert data["canonical_name"] == CHARACTER
        assert data["role"] == "protagonist"
        assert data["species"] == "Human"
        assert data["level"] is None  # No chapter specified
        assert data["active_class"] is None
        assert data["top_skills"] == []

    async def test_returns_summary_with_chapter(self, client, mock_repo):
        """Returns 200 with temporal data when chapter and book_id provided."""
        resp = await client.get(f"/api/characters/{CHARACTER}/summary?book_id={BOOK_ID}&chapter=42")

        assert resp.status_code == 200
        data = resp.json()
        assert data["level"] == 88
        assert data["realm"] == "D-grade"
        assert data["active_class"] == "Arcane Hunter"
        assert "Arcane Powershot" in data["top_skills"]
