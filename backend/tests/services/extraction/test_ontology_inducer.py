"""Tests for ontology_inducer — filtering, caps, model override, case sensitivity."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.extraction.ontology_inducer import (
    InducedEntityType,
    InducedOntology,
    InducedRelationType,
    _MAX_CHAPTERS,
    _MAX_SAMPLE_CHARS,
    induce_ontology,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _make_ontology(
    entity_names: list[str] | None = None,
    relation_names: list[str] | None = None,
) -> MagicMock:
    """Build a mock OntologyLoader."""
    mock = MagicMock()
    mock.get_node_type_names.return_value = entity_names or ["Character", "Event", "Location"]
    mock.get_relationship_type_names.return_value = relation_names or ["HAS_SKILL", "LOCATED_IN"]
    return mock


def _make_instructor_mock(induced: InducedOntology) -> tuple[AsyncMock, str]:
    """Return (mock_client, model_name) whose completions.create() returns *induced*."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=induced)
    return mock_client, "gemini-2.5-flash"


# ── Tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_induce_returns_new_types():
    """New types are returned; types already in the ontology are filtered out."""
    induced = InducedOntology(
        entity_types=[
            InducedEntityType(name="Bloodline", description="Magic lineage"),
            # "Character" already exists in ontology
            InducedEntityType(name="Character", description="A person"),
        ],
        relation_types=[
            InducedRelationType(
                name="HAS_BLOODLINE",
                source_type="Character",
                target_type="Bloodline",
                description="Character possesses a bloodline",
            ),
            # "HAS_SKILL" already exists
            InducedRelationType(
                name="HAS_SKILL",
                source_type="Character",
                target_type="Skill",
                description="Character has a skill",
            ),
        ],
    )
    mock_client, mock_model = _make_instructor_mock(induced)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, mock_model),
    ):
        result = await induce_ontology(["Some chapter text"], _make_ontology())

    node_names = [n["name"] for n in result["node_types"]]
    rel_names = [r["name"] for r in result["relationship_types"]]

    assert "Bloodline" in node_names
    assert "Character" not in node_names

    assert "HAS_BLOODLINE" in rel_names
    assert "HAS_SKILL" not in rel_names


@pytest.mark.asyncio
async def test_induce_caps_chapters():
    """Only the first _MAX_CHAPTERS chapters are sent to the LLM."""
    # Provide more chapters than the cap
    chapters = [f"Chapter {i} text." for i in range(10)]
    assert len(chapters) > _MAX_CHAPTERS

    induced = InducedOntology()
    mock_client, mock_model = _make_instructor_mock(induced)

    captured_messages: list = []

    async def _capture(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return induced

    mock_client.chat.completions.create = _capture

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, mock_model),
    ):
        await induce_ontology(chapters, _make_ontology())

    user_content = next(m["content"] for m in captured_messages if m["role"] == "user")

    # The user message should contain the first _MAX_CHAPTERS chapters only
    for i in range(_MAX_CHAPTERS):
        assert f"Chapter {i} text." in user_content

    # Chapter beyond the cap must NOT appear
    for i in range(_MAX_CHAPTERS, len(chapters)):
        assert f"Chapter {i} text." not in user_content


@pytest.mark.asyncio
async def test_induce_caps_sample_chars():
    """Text is truncated to _MAX_SAMPLE_CHARS before being sent to the LLM."""
    # One chapter much longer than the cap
    long_chapter = "x" * (_MAX_SAMPLE_CHARS * 2)

    induced = InducedOntology()
    mock_client, mock_model = _make_instructor_mock(induced)

    captured_messages: list = []

    async def _capture(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return induced

    mock_client.chat.completions.create = _capture

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, mock_model),
    ):
        await induce_ontology([long_chapter], _make_ontology())

    user_content = next(m["content"] for m in captured_messages if m["role"] == "user")
    assert len(user_content) <= _MAX_SAMPLE_CHARS


@pytest.mark.asyncio
async def test_induce_empty_chapters():
    """Empty chapter list returns empty node_types and relationship_types."""
    induced = InducedOntology()
    mock_client, mock_model = _make_instructor_mock(induced)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, mock_model),
    ):
        result = await induce_ontology([], _make_ontology())

    assert result["node_types"] == []
    assert result["relationship_types"] == []


@pytest.mark.asyncio
async def test_induce_filters_case_insensitive():
    """'character' (lowercase from LLM) is filtered when 'Character' is in ontology."""
    induced = InducedOntology(
        entity_types=[
            InducedEntityType(name="character", description="lowercase duplicate"),
            InducedEntityType(name="LOCATED_IN", description="wrong case relation as entity"),
            InducedEntityType(name="Profession", description="new type"),
        ],
        relation_types=[
            InducedRelationType(
                name="has_skill",
                source_type="Character",
                target_type="Skill",
                description="lowercase duplicate relation",
            ),
            InducedRelationType(
                name="HAS_PROFESSION",
                source_type="Character",
                target_type="Profession",
                description="brand new relation",
            ),
        ],
    )
    mock_client, mock_model = _make_instructor_mock(induced)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, mock_model),
    ):
        result = await induce_ontology(
            ["Some text"],
            _make_ontology(
                entity_names=["Character", "Event", "Location"],
                relation_names=["HAS_SKILL", "LOCATED_IN"],
            ),
        )

    node_names = [n["name"] for n in result["node_types"]]
    rel_names = [r["name"] for r in result["relationship_types"]]

    # Filtered by case-insensitive match
    assert "character" not in node_names
    assert "has_skill" not in rel_names

    # New types survive
    assert "Profession" in node_names
    assert "HAS_PROFESSION" in rel_names


@pytest.mark.asyncio
async def test_induce_model_override():
    """model_override is forwarded to get_instructor_for_extraction."""
    induced = InducedOntology()
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=induced)

    with patch(
        "app.services.extraction.ontology_inducer.get_instructor_for_extraction",
        return_value=(mock_client, "deepseek-chat-v3"),
    ) as mock_get_instructor:
        await induce_ontology(
            ["Chapter text"],
            _make_ontology(),
            model_override="openrouter:deepseek/deepseek-chat-v3-0324",
        )

    mock_get_instructor.assert_called_once_with("openrouter:deepseek/deepseek-chat-v3-0324")
