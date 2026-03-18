import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    ExtractedCharacter,
    ExtractedGenreEntity,
    RelationExtractionResult,
    ExtractedRelation,
)


CHAPTER_TEXT = "Jake se leva et utilisa Shadow Step."

MOCK_ENTITIES = EntityExtractionResult(
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
            extraction_text="Shadow Step",
            char_offset_start=25,
            char_offset_end=36,
        ),
    ],
    chapter_number=1,
)

MOCK_RELATIONS = RelationExtractionResult(
    relations=[
        ExtractedRelation(
            source="jake",
            target="Shadow Step",
            relation_type="HAS_SKILL",
            valid_from_chapter=1,
        ),
    ],
)


@pytest.mark.asyncio
async def test_v4_graph_end_to_end():
    """V4 graph should run 4 nodes and produce expected state keys."""
    with (
        patch(
            "app.services.extraction.entities._call_instructor",
            new_callable=AsyncMock,
            return_value=MOCK_ENTITIES,
        ),
        patch(
            "app.services.extraction.relations._call_instructor_relations",
            new_callable=AsyncMock,
            return_value=MOCK_RELATIONS,
        ),
        patch(
            "app.services.extraction.reconciler.reconcile_flat_entities",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
        )

    assert "entities" in result
    assert "relations" in result
    assert "grounded_entities" in result
    assert "alias_map" in result
    assert "entity_registry" in result
    assert len(result["entities"]) == 2
    assert len(result["relations"]) == 1
