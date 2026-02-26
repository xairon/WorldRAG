"""Retry extraction for a single chapter.

Usage: uv run python scripts/retry_chapter.py <book_id> <chapter_number>
"""

from __future__ import annotations

import asyncio
import sys

from neo4j import AsyncGraphDatabase

from app.config import settings
from app.core.logging import setup_logging
from app.repositories.book_repo import BookRepository
from app.schemas.book import ChapterData
from app.services.graph_builder import build_chapter_graph


async def main(book_id: str, chapter_number: int) -> None:
    setup_logging(log_level="INFO", log_format="console")

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )

    try:
        book_repo = BookRepository(driver)

        # Get chapter text from Neo4j
        results = await book_repo.execute_read(
            """
            MATCH (b:Book {id: $book_id})-[:HAS_CHAPTER]->(c:Chapter {number: $num})
            OPTIONAL MATCH (c)-[:HAS_CHUNK]->(ck:Chunk)
            WITH c, collect(ck.text) AS chunk_texts
            RETURN c.number AS number,
                   c.title AS title,
                   c.word_count AS word_count,
                   reduce(s = '', t IN chunk_texts | s + t + '\n') AS text
            """,
            {"book_id": book_id, "num": chapter_number},
        )

        if not results:
            print(f"Chapter {chapter_number} not found for book {book_id!r}")
            return

        row = results[0]
        chapter = ChapterData(
            number=row["number"],
            title=row["title"] or "",
            text=row["text"],
            word_count=row["word_count"] or 0,
        )
        print(f"Chapter {chapter.number}: {len(chapter.text)} chars")

        # Get regex matches
        regex_results = await book_repo.execute_read(
            """
            MATCH (b:Book {id: $book_id})-[:HAS_CHAPTER]->(c:Chapter {number: $num})
            RETURN c.regex_matches_json AS regex_json
            """,
            {"book_id": book_id, "num": chapter_number},
        )
        regex_json = regex_results[0].get("regex_json", "[]") if regex_results else "[]"

        # Run extraction
        stats = await build_chapter_graph(
            driver=driver,
            book_repo=book_repo,
            book_id=book_id,
            chapter=chapter,
            genre="litrpg",
            series_name="",
            regex_matches_json=regex_json or "[]",
        )

        print(f"Chapter {chapter_number} extraction completed: {stats}")

    finally:
        await driver.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: uv run python scripts/retry_chapter.py <book_id> <chapter_number>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
