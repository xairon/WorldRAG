"""Reader API routes — chapter text and entity annotations for the annotated reader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import require_auth
from app.api.dependencies import get_neo4j

if TYPE_CHECKING:
    from neo4j import AsyncDriver
from app.repositories.book_repo import BookRepository
from app.repositories.entity_repo import EntityRepository

router = APIRouter(prefix="/reader", tags=["reader"])


class ChapterTextResponse(BaseModel):
    """Full chapter text with metadata."""

    book_id: str
    chapter_number: int
    title: str
    text: str
    word_count: int


class EntityAnnotation(BaseModel):
    """Entity annotation with character offsets for text highlighting."""

    entity_name: str
    entity_type: str
    char_offset_start: int
    char_offset_end: int
    extraction_text: str
    mention_type: str = "langextract"
    confidence: float = 1.0


class ChapterEntitiesResponse(BaseModel):
    """All entity annotations for a chapter."""

    book_id: str
    chapter_number: int
    annotations: list[EntityAnnotation]


@router.get("/books/{book_id}/chapters/{chapter_number}/text", dependencies=[Depends(require_auth)])
async def get_chapter_text(
    book_id: str,
    chapter_number: int,
    driver: AsyncDriver = Depends(get_neo4j),
) -> ChapterTextResponse:
    """Get full chapter text reconstructed from chunks."""
    repo = BookRepository(driver)

    chapter = await repo.get_chapter(book_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")

    # Get chunks ordered by position and concatenate
    results = await repo.execute_read(
        """
        MATCH (c:Chapter {book_id: $book_id, number: $number})-[:HAS_CHUNK]->(ck:Chunk)
        RETURN ck.text AS text, ck.position AS position
        ORDER BY ck.position
        """,
        {"book_id": book_id, "number": chapter_number},
    )

    full_text = "\n".join(row["text"] for row in results if row.get("text"))

    return ChapterTextResponse(
        book_id=book_id,
        chapter_number=chapter_number,
        title=chapter.get("title", f"Chapter {chapter_number}"),
        text=full_text,
        word_count=chapter.get("word_count", 0),
    )


class ParagraphResponse(BaseModel):
    """A structured paragraph from a chapter."""

    index: int
    type: str  # narration, dialogue, blue_box, scene_break, header
    text: str
    html: str = ""
    char_start: int
    char_end: int
    speaker: str | None = None
    word_count: int = 0


class ChapterParagraphsResponse(BaseModel):
    """All paragraphs for a chapter."""

    book_id: str
    chapter_number: int
    title: str
    paragraphs: list[ParagraphResponse]
    total_words: int = 0


@router.get(
    "/books/{book_id}/chapters/{chapter_number}/paragraphs",
    dependencies=[Depends(require_auth)],
)
async def get_chapter_paragraphs(
    book_id: str,
    chapter_number: int,
    driver: AsyncDriver = Depends(get_neo4j),
) -> ChapterParagraphsResponse:
    """Get structured paragraphs for a chapter."""
    repo = BookRepository(driver)

    chapter = await repo.get_chapter(book_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")

    paragraphs_raw = await repo.get_paragraphs(book_id, chapter_number)

    paragraphs = [
        ParagraphResponse(
            index=row["index"],
            type=row["type"],
            text=row["text"],
            html=row.get("html", ""),
            char_start=row["char_start"],
            char_end=row["char_end"],
            speaker=row.get("speaker"),
            word_count=row.get("word_count", 0),
        )
        for row in paragraphs_raw
    ]

    return ChapterParagraphsResponse(
        book_id=book_id,
        chapter_number=chapter_number,
        title=chapter.get("title", f"Chapter {chapter_number}"),
        paragraphs=paragraphs,
        total_words=sum(p.word_count for p in paragraphs),
    )


@router.get(
    "/books/{book_id}/chapters/{chapter_number}/entities",
    dependencies=[Depends(require_auth)],
)
async def get_chapter_entities(
    book_id: str,
    chapter_number: int,
    driver: AsyncDriver = Depends(get_neo4j),
) -> ChapterEntitiesResponse:
    """Get all grounded entity annotations for a chapter with char offsets."""
    repo = EntityRepository(driver)

    results = await repo.execute_read(
        """
        MATCH (entity)-[m:MENTIONED_IN]->(c:Chapter {book_id: $book_id, number: $number})
        RETURN labels(entity) AS labels,
               entity.name AS name,
               entity.canonical_name AS canonical_name,
               m.char_start AS char_start,
               m.char_end AS char_end,
               m.mention_text AS mention_text,
               m.mention_type AS mention_type,
               m.confidence AS confidence
        ORDER BY m.char_start
        """,
        {"book_id": book_id, "number": chapter_number},
    )

    annotations = []
    for row in results:
        labels = row.get("labels", [])
        entity_type = "Concept"
        for label in labels:
            if label in (
                "Character", "Skill", "Class", "Title", "Event",
                "Location", "Item", "Creature", "Faction", "Concept",
            ):
                entity_type = label
                break

        name = row.get("name") or row.get("canonical_name") or ""
        char_start = row.get("char_start")
        char_end = row.get("char_end")

        if name and char_start is not None and char_end is not None:
            annotations.append(
                EntityAnnotation(
                    entity_name=name,
                    entity_type=entity_type,
                    char_offset_start=int(char_start),
                    char_offset_end=int(char_end),
                    extraction_text=row.get("mention_text", "")[:200],
                    mention_type=row.get("mention_type", "langextract"),
                    confidence=float(row.get("confidence", 1.0)),
                )
            )

    return ChapterEntitiesResponse(
        book_id=book_id,
        chapter_number=chapter_number,
        annotations=annotations,
    )
