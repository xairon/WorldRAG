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
        ExtractedRelation(source="jake", target="Shadow Step", relation_type="HAS_SKILL", valid_from_chapter=5),
    ],
    ended_relations=[
        RelationEnd(source="jake", target="Old Skill", relation_type="HAS_SKILL", ended_at_chapter=5),
    ],
)


def _onto():
    from app.core.ontology_loader import OntologyLoader
    return OntologyLoader.from_layers(genre="litrpg", series="")


@pytest.mark.asyncio
async def test_extract_relations_node():
    state = {
        "chapter_text": "Jake acquit Shadow Step.",
        "chapter_number": 5,
        "entities": ENTITIES,
        "source_language": "en",
        "model_override": None,
        "ontology": _onto(),
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=MOCK_RESULT):
        result = await extract_relations_node(state)
    assert len(result["relations"]) == 1
    assert len(result["ended_relations"]) == 1
    assert result["relations"][0]["relation_type"] == "HAS_SKILL"
    assert result["relations"][0]["valid_from_chapter"] == 5


@pytest.mark.asyncio
async def test_sets_valid_from_chapter_if_missing():
    mock_result = RelationExtractionResult(
        relations=[ExtractedRelation(source="a", target="b", relation_type="RELATES_TO")],
    )
    state = {
        "chapter_text": "text",
        "chapter_number": 42,
        "entities": [],
        "source_language": "en",
        "model_override": None,
        "ontology": _onto(),
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=mock_result):
        result = await extract_relations_node(state)
    assert result["relations"][0]["valid_from_chapter"] == 42


@pytest.mark.asyncio
async def test_empty_entities_still_extracts_relations():
    """Relations node with an empty entities list should not raise and should return results."""
    mock_result = RelationExtractionResult(
        relations=[ExtractedRelation(source="x", target="y", relation_type="RELATES_TO", valid_from_chapter=3)],
        ended_relations=[],
    )
    state = {
        "chapter_text": "X met Y.",
        "chapter_number": 3,
        "entities": [],
        "source_language": "en",
        "model_override": None,
        "ontology": _onto(),
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=mock_result):
        result = await extract_relations_node(state)
    assert len(result["relations"]) == 1
    assert result["ended_relations"] == []


@pytest.mark.asyncio
async def test_ended_relations_extracted():
    """RelationEnd objects are serialized and returned in ended_relations."""
    mock_result = RelationExtractionResult(
        relations=[],
        ended_relations=[
            RelationEnd(source="jake", target="Old Skill", relation_type="HAS_SKILL", ended_at_chapter=7, reason="skill replaced"),
            RelationEnd(source="jake", target="Iron Guild", relation_type="MEMBER_OF", ended_at_chapter=7),
        ],
    )
    state = {
        "chapter_text": "Jake left the guild and lost his old skill.",
        "chapter_number": 7,
        "entities": ENTITIES,
        "source_language": "en",
        "model_override": None,
        "ontology": _onto(),
    }
    with patch("app.services.extraction.relations._call_instructor_relations", new_callable=AsyncMock, return_value=mock_result):
        result = await extract_relations_node(state)
    assert result["relations"] == []
    assert len(result["ended_relations"]) == 2
    ended = result["ended_relations"]
    assert ended[0]["source"] == "jake"
    assert ended[0]["relation_type"] == "HAS_SKILL"
    assert ended[0]["ended_at_chapter"] == 7
    assert ended[0]["reason"] == "skill replaced"
    assert ended[1]["target"] == "Iron Guild"
    assert ended[1]["relation_type"] == "MEMBER_OF"
