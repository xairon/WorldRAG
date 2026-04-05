from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    ExtractedCharacter,
    ExtractedGenreEntity,
)
from app.services.extraction.entities import extract_entities_node

CHAPTER_TEXT = """Jake se leva. Il avait acquis une nouvelle compétence.
[Skill Acquired: Shadow Step - Rare]
L'archer regarda la Grande Forêt au loin."""

MOCK_RESULT = EntityExtractionResult(
    entities=[
        ExtractedCharacter(
            name="Jake",
            canonical_name="jake",
            extraction_text="Jake se leva",
            char_offset_start=0,
            char_offset_end=12,
        ),
        ExtractedGenreEntity(
            sub_type="skill",
            name="Shadow Step",
            owner="jake",
            rank="rare",
            extraction_text="Shadow Step - Rare",
            char_offset_start=68,
            char_offset_end=86,
        ),
    ],
    chapter_number=5,
)


@pytest.fixture
def base_state():
    from app.core.ontology_loader import OntologyLoader

    return {
        "book_id": "test-book",
        "chapter_number": 5,
        "chapter_text": CHAPTER_TEXT,
        "regex_matches_json": "[]",
        "genre": "litrpg",
        "series_name": "",
        "source_language": "en",
        "model_override": None,
        "entity_registry": {},
        "ontology": OntologyLoader.from_layers(genre="litrpg", series=""),
    }


@pytest.mark.asyncio
async def test_extract_entities_node_returns_entities(base_state):
    with patch(
        "app.services.extraction.entities._call_instructor",
        new_callable=AsyncMock,
        return_value=MOCK_RESULT,
    ):
        result = await extract_entities_node(base_state)
    assert "entities" in result
    assert len(result["entities"]) == 2
    assert result["entities"][0]["entity_type"] == "character"
    assert result["total_entities"] == 2


@pytest.mark.asyncio
async def test_extract_entities_validates_grounding(base_state):
    with patch(
        "app.services.extraction.entities._call_instructor",
        new_callable=AsyncMock,
        return_value=MOCK_RESULT,
    ):
        result = await extract_entities_node(base_state)
    assert len(result["grounded_entities"]) == 2
    for ge in result["grounded_entities"]:
        assert ge["alignment_status"] in ("exact", "fuzzy", "unaligned")
        assert ge["confidence"] > 0


@pytest.mark.asyncio
async def test_extract_entities_empty_result(base_state):
    """LLM returning zero entities produces a valid empty result."""
    empty_result = EntityExtractionResult(entities=[], chapter_number=5)
    with patch(
        "app.services.extraction.entities._call_instructor",
        new_callable=AsyncMock,
        return_value=empty_result,
    ):
        result = await extract_entities_node(base_state)
    assert result["entities"] == []
    assert result["total_entities"] == 0
    assert result["grounded_entities"] == []


@pytest.mark.asyncio
async def test_extract_entities_with_registry_context(base_state):
    """Passing a pre-populated entity_registry dict should not break the node."""
    from app.services.extraction.entity_registry import EntityRegistry

    registry = EntityRegistry()
    registry.add(
        name="Elara",
        entity_type="character",
        aliases=["the Huntress"],
        significance="protagonist",
        first_seen_chapter=1,
    )
    base_state["entity_registry"] = registry.to_dict()

    with patch(
        "app.services.extraction.entities._call_instructor",
        new_callable=AsyncMock,
        return_value=MOCK_RESULT,
    ):
        result = await extract_entities_node(base_state)

    # Node still works and returns entities from the (mocked) LLM result
    assert len(result["entities"]) == 2
    assert result["total_entities"] == 2


@pytest.mark.asyncio
async def test_extract_entities_unknown_type_dropped(base_state):
    """model_validate drops entities with unknown entity_type (silently)."""
    raw = {
        "entities": [
            {
                "entity_type": "custom_unknown_type",
                "name": "Mana Core",
                "extraction_text": "Mana Core",
                "char_offset_start": 0,
                "char_offset_end": 9,
            }
        ],
        "chapter_number": 5,
    }
    dropped_result = EntityExtractionResult.model_validate(raw)
    # Verify the schema-level drop happened
    assert len(dropped_result.entities) == 0
