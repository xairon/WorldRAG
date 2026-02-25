"""Run full extraction + embedding pipeline directly (no arq worker needed).

Usage:
    cd backend
    GEMINI_API_KEY=<key> uv run python scripts/run_full_pipeline.py <book_id>
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from neo4j import AsyncGraphDatabase

from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.repositories.book_repo import BookRepository
from app.services.graph_builder import build_book_graph


async def main(book_id: str) -> None:
    setup_logging(log_level="INFO", log_format="console")
    logger = get_logger(__name__)

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )

    try:
        book_repo = BookRepository(driver)

        # 1. Load book and chapters
        book = await book_repo.get_book(book_id)
        if not book:
            print(f"Book {book_id!r} not found")
            return

        chapters = await book_repo.get_chapters_for_extraction(book_id)
        if not chapters:
            print(f"No chapters found for book {book_id!r}")
            return

        chapter_regex = await book_repo.get_chapter_regex_json(book_id)
        print(f"\n{'='*60}")
        print(f"Book: {book.get('title', book_id)}")
        print(f"Chapters: {len(chapters)}")
        print(f"Regex matches: {sum(1 for v in (chapter_regex or {}).values() if v != '[]')}")
        print(f"{'='*60}\n")

        # 2. Run extraction pipeline
        t0 = time.time()
        result = await build_book_graph(
            driver=driver,
            book_repo=book_repo,
            book_id=book_id,
            chapters=chapters,
            genre=book.get("genre", "litrpg"),
            series_name=book.get("series_name", ""),
            chapter_regex_matches=chapter_regex,
        )
        extraction_time = time.time() - t0

        print(f"\n{'='*60}")
        print(f"EXTRACTION COMPLETE ({extraction_time:.1f}s)")
        print(f"  Chapters processed: {result['chapters_processed']}")
        print(f"  Chapters failed:    {result['chapters_failed']}")
        print(f"  Total entities:     {result['total_entities']}")
        print(f"  Status:             {result['status']}")
        if result['failed_chapters']:
            print(f"  Failed chapters:    {result['failed_chapters']}")
        print(f"{'='*60}\n")

        # 3. Run embedding pipeline
        print("Starting embedding pipeline...")
        chunks = await book_repo.get_chunks_for_embedding(book_id)
        if chunks:
            await book_repo.update_book_status(book_id, "embedding")

            from app.services.embedding_pipeline import embed_book_chunks

            t1 = time.time()
            embed_result = await embed_book_chunks(
                driver=driver,
                book_id=book_id,
                chunks=chunks,
            )
            embed_time = time.time() - t1

            if embed_result.failed == 0:
                await book_repo.update_book_status(book_id, "embedded")

            print(f"\n{'='*60}")
            print(f"EMBEDDING COMPLETE ({embed_time:.1f}s)")
            print(f"  Chunks embedded: {embed_result.embedded}")
            print(f"  Chunks failed:   {embed_result.failed}")
            print(f"  Total tokens:    {embed_result.total_tokens}")
            print(f"{'='*60}\n")
        else:
            print("No chunks to embed.")

        # 4. Final stats
        async with driver.session() as s:
            r = await s.run("""
                MATCH (n) WHERE n:Character OR n:Skill OR n:Class OR n:Title
                    OR n:Event OR n:Location OR n:Item OR n:Creature
                    OR n:Faction OR n:Concept
                RETURN labels(n)[0] AS label, count(n) AS cnt
                ORDER BY cnt DESC
            """)
            records = await r.data()
            print("Final KG entity counts:")
            total = 0
            for rec in records:
                print(f"  {rec['label']}: {rec['cnt']}")
                total += rec['cnt']
            print(f"  TOTAL: {total}")

    finally:
        await driver.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/run_full_pipeline.py <book_id>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
