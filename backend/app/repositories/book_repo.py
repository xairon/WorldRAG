"""Neo4j repository for books, chapters, and chunks.

Handles CRUD operations for the bibliographic layer of the KG:
Series → Book → Chapter → Chunk.
All writes use MERGE with batch_id for rollback capability.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository
from app.schemas.book import ChapterData, ParagraphData

if TYPE_CHECKING:
    from app.schemas.book import ChunkData, RegexMatch

logger = get_logger(__name__)


class BookRepository(Neo4jRepository):
    """Repository for book, chapter, and chunk operations in Neo4j."""

    # --- Book operations ---

    async def create_book(
        self,
        title: str,
        series_name: str | None = None,
        order_in_series: int | None = None,
        author: str | None = None,
        genre: str = "litrpg",
    ) -> str:
        """Create or merge a book node. Returns the actual book_id from the DB."""
        new_id = str(uuid.uuid4())[:8]
        batch_id = str(uuid.uuid4())

        result = await self.execute_write(
            """
            MERGE (b:Book {title: $title})
            ON CREATE SET
                b.id = $new_id,
                b.order_in_series = $order_in_series,
                b.author = $author,
                b.genre = $genre,
                b.total_chapters = 0,
                b.status = 'pending',
                b.chapters_processed = 0,
                b.batch_id = $batch_id,
                b.created_at = timestamp()
            ON MATCH SET
                b.status = 'pending',
                b.chapters_processed = 0
            RETURN b.id AS id
            """,
            {
                "title": title,
                "new_id": new_id,
                "order_in_series": order_in_series,
                "author": author,
                "genre": genre,
                "batch_id": batch_id,
            },
        )

        # Use the actual ID from the DB (handles ON MATCH case)
        book_id = result[0]["id"] if result else new_id

        # Link to series if provided
        if series_name:
            await self.execute_write(
                """
                MERGE (s:Series {name: $series_name})
                ON CREATE SET s.author = $author, s.genre = $genre
                WITH s
                MATCH (b:Book {title: $title})
                MERGE (s)-[:CONTAINS_WORK {position: $order}]->(b)
                """,
                {
                    "series_name": series_name,
                    "author": author,
                    "genre": genre,
                    "title": title,
                    "order": order_in_series or 1,
                },
            )

        logger.info("book_created", book_id=book_id, title=title)
        return book_id

    async def get_book(self, book_id: str) -> dict[str, Any] | None:
        """Get book info by ID."""
        result = await self.execute_read(
            "MATCH (b:Book {id: $id}) RETURN b",
            {"id": book_id},
        )
        if result:
            return dict(result[0]["b"])
        return None

    async def list_books(self) -> list[dict[str, Any]]:
        """List all books with basic info."""
        return await self.execute_read(
            """
            MATCH (b:Book)
            OPTIONAL MATCH (b)-[:HAS_CHAPTER]->(c:Chapter)
            RETURN b, count(c) AS chapter_count
            ORDER BY b.created_at DESC
            """
        )

    async def update_book_status(self, book_id: str, status: str) -> None:
        """Update book processing status."""
        await self.execute_write(
            "MATCH (b:Book {id: $id}) SET b.status = $status",
            {"id": book_id, "status": status},
        )

    async def update_book_chapter_count(self, book_id: str, total: int) -> None:
        """Update total chapter count after ingestion."""
        await self.execute_write(
            "MATCH (b:Book {id: $id}) SET b.total_chapters = $total",
            {"id": book_id, "total": total},
        )

    async def delete_book(self, book_id: str) -> int:
        """Delete a book and all its chapters, chunks, and extracted entities."""
        # First: delete all extracted entities with this book_id
        await self.execute_write(
            """
            MATCH (n {book_id: $id})
            WHERE NOT n:Book AND NOT n:Chapter AND NOT n:Chunk
            DETACH DELETE n
            """,
            {"id": book_id},
        )

        # Then: delete book, chapters, and chunks
        result = await self.execute_write(
            """
            MATCH (b:Book {id: $id})
            OPTIONAL MATCH (b)-[:HAS_CHAPTER]->(ch:Chapter)
            OPTIONAL MATCH (ch)-[:HAS_CHUNK]->(ck:Chunk)
            OPTIONAL MATCH (ch)-[:HAS_PARAGRAPH]->(p:Paragraph)
            DETACH DELETE p, ck, ch, b
            RETURN count(DISTINCT ch) AS chapters_deleted
            """,
            {"id": book_id},
        )
        count = result[0]["chapters_deleted"] if result else 0
        logger.info("book_deleted", book_id=book_id, chapters_deleted=count)
        return count

    # --- Chapter operations ---

    async def create_chapters(
        self,
        book_id: str,
        chapters: list[ChapterData],
    ) -> int:
        """Bulk create chapter nodes linked to a book.

        Uses UNWIND for efficient batch insertion.
        Returns number of chapters created.
        """
        batch_id = str(uuid.uuid4())

        chapter_data = [
            {
                "number": ch.number,
                "title": ch.title,
                "word_count": ch.word_count,
                "summary": "",
                "batch_id": batch_id,
            }
            for ch in chapters
        ]

        await self.execute_write(
            """
            MATCH (b:Book {id: $book_id})
            UNWIND $chapters AS ch
            MERGE (c:Chapter {book_id: $book_id, number: ch.number})
            ON CREATE SET
                c.title = ch.title,
                c.word_count = ch.word_count,
                c.summary = ch.summary,
                c.status = 'pending',
                c.batch_id = ch.batch_id,
                c.regex_matches = 0,
                c.entity_count = 0
            MERGE (b)-[:HAS_CHAPTER {position: ch.number}]->(c)
            """,
            {"book_id": book_id, "chapters": chapter_data},
        )

        logger.info("chapters_created", book_id=book_id, count=len(chapters))
        return len(chapters)

    async def get_chapter(self, book_id: str, chapter_number: int) -> dict[str, Any] | None:
        """Get chapter info."""
        result = await self.execute_read(
            "MATCH (c:Chapter {book_id: $book_id, number: $number}) RETURN c",
            {"book_id": book_id, "number": chapter_number},
        )
        if result:
            return dict(result[0]["c"])
        return None

    async def list_chapters(self, book_id: str) -> list[dict[str, Any]]:
        """List all chapters for a book."""
        return await self.execute_read(
            """
            MATCH (b:Book {id: $book_id})-[:HAS_CHAPTER]->(c:Chapter)
            OPTIONAL MATCH (c)-[:HAS_CHUNK]->(ck:Chunk)
            RETURN c, count(ck) AS chunk_count
            ORDER BY c.number
            """,
            {"book_id": book_id},
        )

    async def update_chapter_status(self, book_id: str, chapter_number: int, status: str) -> None:
        """Update chapter processing status."""
        await self.execute_write(
            """
            MATCH (c:Chapter {book_id: $book_id, number: $number})
            SET c.status = $status
            """,
            {"book_id": book_id, "number": chapter_number, "status": status},
        )

    # --- Paragraph operations ---

    async def create_paragraphs(
        self,
        book_id: str,
        chapter_number: int,
        paragraphs: list[ParagraphData],
    ) -> int:
        """Bulk create Paragraph nodes linked to a Chapter via HAS_PARAGRAPH.

        Uses UNWIND for efficient batch insertion.
        Returns number of paragraphs created.
        """
        if not paragraphs:
            return 0

        para_data = [
            {
                "index": p.index,
                "type": p.type.value,
                "text": p.text,
                "html": p.html,
                "char_start": p.char_start,
                "char_end": p.char_end,
                "speaker": p.speaker,
                "sentence_count": p.sentence_count,
                "word_count": p.word_count,
            }
            for p in paragraphs
        ]

        await self.execute_write(
            """
            UNWIND $paragraphs AS p
            MATCH (c:Chapter {book_id: $book_id, number: $chapter_number})
            MERGE (para:Paragraph {
                book_id: $book_id,
                chapter_number: $chapter_number,
                index: p.index
            })
            ON CREATE SET
                para.type = p.type,
                para.text = p.text,
                para.html = p.html,
                para.char_start = p.char_start,
                para.char_end = p.char_end,
                para.speaker = p.speaker,
                para.sentence_count = p.sentence_count,
                para.word_count = p.word_count
            ON MATCH SET
                para.type = p.type,
                para.text = p.text,
                para.html = p.html,
                para.char_start = p.char_start,
                para.char_end = p.char_end,
                para.speaker = p.speaker,
                para.sentence_count = p.sentence_count,
                para.word_count = p.word_count
            MERGE (c)-[:HAS_PARAGRAPH {position: p.index}]->(para)
            """,
            {
                "book_id": book_id,
                "chapter_number": chapter_number,
                "paragraphs": para_data,
            },
        )

        logger.info(
            "paragraphs_created",
            book_id=book_id,
            chapter=chapter_number,
            count=len(paragraphs),
        )
        return len(paragraphs)

    async def get_paragraphs(
        self,
        book_id: str,
        chapter_number: int,
    ) -> list[dict[str, Any]]:
        """Get all paragraphs for a chapter, ordered by index."""
        return await self.execute_read(
            """
            MATCH (c:Chapter {book_id: $book_id, number: $chapter_number})
                  -[:HAS_PARAGRAPH]->(p:Paragraph)
            RETURN p.index AS index,
                   p.type AS type,
                   p.text AS text,
                   p.html AS html,
                   p.char_start AS char_start,
                   p.char_end AS char_end,
                   p.speaker AS speaker,
                   p.sentence_count AS sentence_count,
                   p.word_count AS word_count
            ORDER BY p.index
            """,
            {"book_id": book_id, "chapter_number": chapter_number},
        )

    # --- Chunk operations ---

    async def create_chunks(
        self,
        book_id: str,
        chunks: list[ChunkData],
    ) -> int:
        """Bulk create chunk nodes linked to their chapter.

        Uses UNWIND for efficient batch insertion.
        """
        if not chunks:
            return 0

        batch_id = str(uuid.uuid4())

        chunk_data = [
            {
                "text": ck.text,
                "position": ck.position,
                "chapter_number": ck.chapter_number,
                "token_count": ck.token_count,
                "char_offset_start": ck.char_offset_start,
                "char_offset_end": ck.char_offset_end,
                "batch_id": batch_id,
            }
            for ck in chunks
        ]

        await self.execute_write(
            """
            UNWIND $chunks AS ck
            MATCH (c:Chapter {book_id: $book_id, number: ck.chapter_number})
            CREATE (chunk:Chunk {
                text: ck.text,
                position: ck.position,
                chapter_id: $book_id + '-ch' + toString(ck.chapter_number),
                token_count: ck.token_count,
                char_offset_start: ck.char_offset_start,
                char_offset_end: ck.char_offset_end,
                batch_id: ck.batch_id
            })
            MERGE (c)-[:HAS_CHUNK {position: ck.position}]->(chunk)
            """,
            {"book_id": book_id, "chunks": chunk_data},
        )

        logger.info("chunks_created", book_id=book_id, count=len(chunks))
        return len(chunks)

    async def get_chunks_for_embedding(self, book_id: str) -> list[dict[str, Any]]:
        """Fetch all chunks for a book that lack embeddings.

        Returns list of {chapter_id, position, text} dicts used by
        the embedding pipeline to compute and write back vectors.
        """
        return await self.execute_read(
            """
            MATCH (c:Chapter {book_id: $book_id})-[:HAS_CHUNK]->(ck:Chunk)
            WHERE ck.embedding IS NULL
            RETURN ck.chapter_id AS chapter_id,
                   ck.position AS position,
                   ck.text AS text
            ORDER BY ck.chapter_id, ck.position
            """,
            {"book_id": book_id},
        )

    # --- Regex match operations ---

    async def store_regex_matches(
        self,
        book_id: str,
        matches: list[RegexMatch],
    ) -> int:
        """Store regex extraction results as properties on chapter nodes.

        Regex matches are stored as JSON on the chapter for later use
        by the LLM extraction passes.
        """
        if not matches:
            return 0

        import json

        # Group matches by chapter
        by_chapter: dict[int, list[RegexMatch]] = {}
        for m in matches:
            by_chapter.setdefault(m.chapter_number, []).append(m)

        for chapter_num, chapter_matches in by_chapter.items():
            matches_json = json.dumps(
                [m.model_dump() for m in chapter_matches],
                default=str,
            )
            await self.execute_write(
                """
                MATCH (c:Chapter {book_id: $book_id, number: $number})
                SET c.regex_matches_data = $matches_json,
                    c.regex_matches = $count
                """,
                {
                    "book_id": book_id,
                    "number": chapter_num,
                    "matches_json": matches_json,
                    "count": len(chapter_matches),
                },
            )

        total = len(matches)
        logger.info("regex_matches_stored", book_id=book_id, total=total)
        return total

    # --- Chapter text & regex retrieval (for LLM extraction) ---

    async def get_chapters_for_extraction(
        self,
        book_id: str,
    ) -> list[ChapterData]:
        """Retrieve all chapter texts for a book, ordered by number.

        Returns ChapterData objects suitable for the extraction pipeline.
        """
        results = await self.execute_read(
            """
            MATCH (b:Book {id: $book_id})-[:HAS_CHAPTER]->(c:Chapter)
            OPTIONAL MATCH (c)-[:HAS_CHUNK]->(ck:Chunk)
            WITH c, collect(ck.text) AS chunk_texts
            ORDER BY c.number
            RETURN c.number AS number,
                   c.title AS title,
                   c.word_count AS word_count,
                   reduce(s = '', t IN chunk_texts | s + t + '\n') AS text
            """,
            {"book_id": book_id},
        )
        return [
            ChapterData(
                number=row["number"],
                title=row.get("title", ""),
                text=row.get("text", "").strip(),
                word_count=row.get("word_count", 0),
            )
            for row in results
            if row.get("text", "").strip()
        ]

    async def get_chapter_regex_json(
        self,
        book_id: str,
    ) -> dict[int, str]:
        """Get regex matches JSON keyed by chapter number.

        Returns dict mapping chapter_number -> regex_matches_json string.
        """
        results = await self.execute_read(
            """
            MATCH (c:Chapter {book_id: $book_id})
            WHERE c.regex_matches_data IS NOT NULL
            RETURN c.number AS number, c.regex_matches_data AS regex_json
            ORDER BY c.number
            """,
            {"book_id": book_id},
        )
        return {row["number"]: row["regex_json"] for row in results if row.get("regex_json")}

    # --- Series operations ---

    async def get_series(self, series_name: str) -> dict[str, Any] | None:
        """Get series info by name."""
        result = await self.execute_read(
            """
            MATCH (s:Series {name: $name})
            OPTIONAL MATCH (s)-[r:CONTAINS_WORK]->(b:Book)
            WITH s, b ORDER BY r.position
            RETURN s.name AS name, s.author AS author, s.genre AS genre,
                   collect({
                       id: b.id, title: b.title, status: b.status,
                       order_in_series: r.position, total_chapters: b.total_chapters
                   }) AS books
            """,
            {"name": series_name},
        )
        return result[0] if result else None

    async def list_series(self) -> list[dict[str, Any]]:
        """List all series."""
        return await self.execute_read(
            """
            MATCH (s:Series)
            OPTIONAL MATCH (s)-[:CONTAINS_WORK]->(b:Book)
            RETURN s.name AS name, s.author AS author, s.genre AS genre,
                   count(b) AS book_count
            ORDER BY s.name
            """
        )

    # --- Stats ---

    async def get_book_stats(self, book_id: str) -> dict[str, Any]:
        """Get statistics for a book."""
        result = await self.execute_read(
            """
            MATCH (b:Book {id: $book_id})
            OPTIONAL MATCH (b)-[:HAS_CHAPTER]->(c:Chapter)
            OPTIONAL MATCH (c)-[:HAS_CHUNK]->(ck:Chunk)
            RETURN
                b.title AS title,
                b.status AS status,
                count(DISTINCT c) AS chapters,
                count(DISTINCT ck) AS chunks,
                sum(c.word_count) AS total_words,
                sum(c.regex_matches) AS regex_matches,
                sum(c.entity_count) AS entities
            """,
            {"book_id": book_id},
        )
        return result[0] if result else {}
