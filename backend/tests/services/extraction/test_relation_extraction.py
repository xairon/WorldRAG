import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.extraction_v4 import (
    RelationExtractionResult, ExtractedRelation, RelationEnd,
)
from app.services.extraction.relations import extract_relations_node

ENTITIES = [
    {"entity_type": "character", "name": "Jake", "canonical_name": "jake", "extraction_text": "Jake"},
    {"entity_type": "skill", "name": "Shadow Step", "owner": "jake", "extraction_text": "Shadow Step"},
]

MOCK_RESULT = RelationExtractionResult(
    relations=[
        ExtractedRelation(source="jake", target="Shadow Step", relation_type="OWNS", valid_from_chapter=5),
    ],
    ended_relations=[
        RelationEnd(source="jake", target="Old Skill", relation_type="OWNS", ended_at_chapter=5),
    ],
)


@pytest.mark.asyncio
async def test_extract_relations_node():
    state = {
        "chapter_text": "Jake acquit Shadow Step.",
        "chapter_number": 5,
        "entities": ENTITIES,
        "source_language": "fr",
        "model_override": None,
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_relations_node(state)
    assert len(result["relations"]) == 1
    assert len(result["ended_relations"]) == 1
    assert result["relations"][0]["relation_type"] == "OWNS"
    assert result["relations"][0]["valid_from_chapter"] == 5


@pytest.mark.asyncio
async def test_sets_valid_from_chapter_if_missing():
    mock_result = RelationExtractionResult(
        relations=[ExtractedRelation(source="a", target="b", relation_type="KNOWS")],
    )
    state = {
        "chapter_text": "text",
        "chapter_number": 42,
        "entities": [],
        "source_language": "fr",
        "model_override": None,
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=mock_result):
        result = await extract_relations_node(state)
    assert result["relations"][0]["valid_from_chapter"] == 42
