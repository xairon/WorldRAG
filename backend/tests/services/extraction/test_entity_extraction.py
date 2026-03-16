import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.extraction_v4 import (
    EntityExtractionResult, ExtractedCharacter, ExtractedSkill,
)
from app.services.extraction.entities import extract_entities_node

CHAPTER_TEXT = """Jake se leva. Il avait acquis une nouvelle compétence.
[Skill Acquired: Shadow Step - Rare]
L'archer regarda la Grande Forêt au loin."""

MOCK_RESULT = EntityExtractionResult(
    entities=[
        ExtractedCharacter(
            name="Jake", canonical_name="jake",
            extraction_text="Jake se leva",
            char_offset_start=0, char_offset_end=12,
        ),
        ExtractedSkill(
            name="Shadow Step", owner="jake", rank="rare",
            extraction_text="Shadow Step - Rare",
            char_offset_start=68, char_offset_end=86,
        ),
    ],
    chapter_number=5,
)

@pytest.fixture
def base_state():
    return {
        "book_id": "test-book",
        "chapter_number": 5,
        "chapter_text": CHAPTER_TEXT,
        "regex_matches_json": "[]",
        "genre": "litrpg",
        "series_name": "",
        "source_language": "fr",
        "model_override": None,
        "entity_registry": {},
    }

@pytest.mark.asyncio
async def test_extract_entities_node_returns_entities(base_state):
    with patch("app.services.extraction.entities._call_instructor", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_entities_node(base_state)
    assert "entities" in result
    assert len(result["entities"]) == 2
    assert result["entities"][0]["entity_type"] == "character"
    assert result["total_entities"] == 2

@pytest.mark.asyncio
async def test_extract_entities_validates_grounding(base_state):
    with patch("app.services.extraction.entities._call_instructor", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_entities_node(base_state)
    assert len(result["grounded_entities"]) == 2
    for ge in result["grounded_entities"]:
        assert ge["alignment_status"] in ("exact", "fuzzy", "unaligned")
        assert ge["confidence"] > 0
