"""Test vector search and chat service directly."""

from __future__ import annotations

import asyncio

from neo4j import AsyncGraphDatabase

from app.config import settings
from app.core.logging import setup_logging
from app.llm.embeddings import LocalEmbedder


async def main() -> None:
    setup_logging(log_level="INFO", log_format="console")
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    embedder = LocalEmbedder()

    try:
        # 1. Embed query
        qe = await embedder.embed_query("Qui est Jake ?")
        print(f"Query embedding: {len(qe)} dims")

        # 2. Raw vector search (no filters)
        async with driver.session() as s:
            r = await s.run(
                """
                CALL db.index.vector.queryNodes('chunk_embedding', 5, $embedding)
                YIELD node AS chunk, score
                RETURN chunk.chapter_id AS cid, score,
                       left(chunk.text, 100) AS preview
                """,
                {"embedding": qe},
            )
            data = await r.data()
            print(f"\nRaw vector search: {len(data)} results")
            for d in data:
                print(f"  score={d['score']:.4f} cid={d['cid']} | {d['preview']}...")

        # 3. With book filter
        async with driver.session() as s:
            r2 = await s.run(
                """
                CALL db.index.vector.queryNodes('chunk_embedding', 5, $embedding)
                YIELD node AS chunk, score
                MATCH (chap:Chapter)-[:HAS_CHUNK]->(chunk)
                WHERE chap.book_id = $book_id
                RETURN chap.number AS num, chap.title AS title, score,
                       left(chunk.text, 100) AS preview
                """,
                {"embedding": qe, "book_id": "c55f36a8"},
            )
            data2 = await r2.data()
            print(f"\nFiltered search: {len(data2)} results")
            for d in data2:
                print(f"  Ch{d['num']} ({d['title']}) score={d['score']:.4f} | {d['preview']}...")

        # 4. Test full chat service
        from app.services.chat_service import ChatService

        chat = ChatService(driver)
        resp = await chat.query("Qui est Jake ?", "c55f36a8")
        print("\nChat response:")
        print(f"  chunks_retrieved: {resp.chunks_retrieved}")
        print(f"  chunks_after_rerank: {resp.chunks_after_rerank}")
        print(f"  entities: {len(resp.related_entities)}")
        print(f"  answer: {resp.answer[:300]}...")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
