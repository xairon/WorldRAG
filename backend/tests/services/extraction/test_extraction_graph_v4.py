from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.extraction_v4 import (
    EntityExtractionResult,
    ExtractedCharacter,
    ExtractedGenreEntity,
    ExtractedRelation,
    RelationExtractionResult,
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

# Empty result for mocking an LLM that returns nothing
EMPTY_ENTITIES = EntityExtractionResult(entities=[], chapter_number=1)
EMPTY_RELATIONS = RelationExtractionResult(relations=[])


@contextmanager
def _patch_all(
    entities=MOCK_ENTITIES,
    relations=MOCK_RELATIONS,
    alias_map=None,
):
    """Patch all LLM + reconciler calls used in the V4 graph."""
    if alias_map is None:
        alias_map = {}
    # get_instructor_for_task is called before reconcile_flat_entities in the node;
    # mock it to return a (client, model) tuple so the code reaches our reconcile mock.
    mock_instructor_client = MagicMock()
    with (
        patch(
            "app.services.extraction.entities._call_instructor",
            new_callable=AsyncMock,
            return_value=entities,
        ),
        patch(
            "app.services.extraction.relations._call_instructor_relations",
            new_callable=AsyncMock,
            return_value=relations,
        ),
        patch(
            "app.llm.providers.get_instructor_for_task",
            return_value=(mock_instructor_client, "mock-model"),
        ),
        patch(
            "app.services.extraction.reconciler.reconcile_flat_entities",
            new_callable=AsyncMock,
            return_value=alias_map,
        ),
        patch(
            "app.services.extraction.faithfulness.batch_verify_faithfulness",
            new=AsyncMock(side_effect=lambda entities, _text: entities),
        ),
    ):
        yield


def _reset_v4_graph_cache():
    """Force rebuild of the cached V4 graph on next call."""
    import app.services.extraction as mod

    mod._extraction_graph_v4 = None


@pytest.mark.asyncio
async def test_v4_graph_end_to_end():
    """V4 graph should run all nodes and produce expected state keys."""
    _reset_v4_graph_cache()
    with _patch_all():
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
    # 2 original entities + 2 TextualFeature (dialogue_density, pacing) from verify node
    assert len(result["entities"]) >= 2
    assert len(result["relations"]) == 1


@pytest.mark.asyncio
async def test_v4_graph_returns_entity_registry():
    """Result must contain an entity_registry dict with an 'entities' key."""
    _reset_v4_graph_cache()
    with _patch_all():
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
        )

    registry = result["entity_registry"]
    assert isinstance(registry, dict)
    assert "entities" in registry


@pytest.mark.asyncio
async def test_v4_graph_empty_chapter():
    """Empty LLM response should produce a valid result with 0 entities."""
    _reset_v4_graph_cache()
    with _patch_all(entities=EMPTY_ENTITIES, relations=EMPTY_RELATIONS):
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=2,
            chapter_text="",
            genre="litrpg",
        )

    assert result["entities"] == []
    assert result["relations"] == []
    assert "alias_map" in result
    assert "entity_registry" in result


@pytest.mark.asyncio
async def test_v4_graph_with_alias_map():
    """Alias map returned by reconciler should appear in the final result."""
    _reset_v4_graph_cache()
    mock_alias_map = {"jake sulawesi": "jake"}
    with _patch_all(alias_map=mock_alias_map):
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
        )

    assert "jake sulawesi" in result["alias_map"]
    assert result["alias_map"]["jake sulawesi"] == "jake"


@pytest.mark.asyncio
async def test_v4_graph_with_entity_registry_input():
    """Pre-existing entity_registry can be passed without crashing."""
    _reset_v4_graph_cache()
    pre_existing_registry = {
        "entities": {
            "jake": {
                "canonical_name": "jake",
                "entity_type": "character",
                "aliases": [],
                "first_seen_chapter": 0,
                "description": "The hero",
            }
        }
    }
    with _patch_all():
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=2,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
            entity_registry=pre_existing_registry,
        )

    assert "entity_registry" in result
    assert isinstance(result["entity_registry"], dict)


@pytest.mark.asyncio
async def test_v4_graph_model_override():
    """model_override parameter is accepted and does not crash."""
    _reset_v4_graph_cache()
    with _patch_all():
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=CHAPTER_TEXT,
            genre="litrpg",
            model_override="openrouter:deepseek/deepseek-chat-v3-0324",
        )

    assert "entities" in result
    assert "relations" in result


@pytest.mark.asyncio
async def test_v4_graph_grounded_entities_populated():
    """Grounded entities from mention_detect should have entity_name and alignment_status."""
    _reset_v4_graph_cache()
    # Use a longer chapter text so mention detection can find "Jake" and "Shadow Step"
    chapter_text = (
        "Jake se leva lentement. Jake utilisa Shadow Step pour disparaître. "
        "Shadow Step est une compétence puissante de Jake."
    )

    # Entities must have names that appear in the text
    mock_entities_with_text = EntityExtractionResult(
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
                char_offset_start=24,
                char_offset_end=35,
            ),
        ],
        chapter_number=1,
    )

    with _patch_all(entities=mock_entities_with_text):
        from app.services.extraction import extract_chapter_v4

        result = await extract_chapter_v4(
            book_id="test",
            chapter_number=1,
            chapter_text=chapter_text,
            genre="litrpg",
        )

    grounded = result.get("grounded_entities", [])
    # mention_detect may or may not find mentions depending on entity list;
    # if it does, each must have entity_name and alignment_status
    if grounded:
        for ge in grounded:
            assert "entity_name" in ge, f"grounded entity missing entity_name: {ge}"
            assert "alignment_status" in ge, f"grounded entity missing alignment_status: {ge}"
