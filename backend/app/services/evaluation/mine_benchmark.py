"""MINE Benchmark — Measure of Information in Nodes and Edges.

Adapted from KGGen (NeurIPS 2025) for WorldRAG KG quality evaluation.

Algorithm:
    1. For N chapters, generate K ground-truth facts (via LLM or manual)
    2. For each fact:
       a. Embed the fact with S-BERT
       b. Retrieve top-k most similar nodes in the KG
       c. Expand to all nodes within 2 hops
       d. LLM judges: can this fact be inferred from the subgraph? (0/1)
    3. Score = % of facts scored as inferable, averaged across chapters

Usage:
    score = await evaluate_mine(driver, book_id, n_chapters=10, k_facts=10)
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def generate_chapter_facts(
    chapter_text: str,
    chapter_number: int,
    k: int = 10,
) -> list[str]:
    """Generate K ground-truth facts from chapter text using LLM.

    Returns list of factual statements that should be inferable from a
    good KG of this chapter.
    """
    from app.llm.providers import get_instructor_for_task

    try:
        client, model = get_instructor_for_task("summary")
    except Exception:
        logger.warning("mine_no_llm_for_facts")
        return []

    response = await client.chat.completions.create(
        model=model,
        response_model=None,
        messages=[
            {
                "role": "system",
                "content": (
                    f"Extract exactly {k} SPECIFIC factual statements from this fiction chapter. "
                    "Each fact MUST mention at least one named entity (character, location, item, skill). "
                    "Facts should be concrete and verifiable, NOT vague ('Jake is a character'). "
                    "Good: 'Jake used Shadow Step to dodge the attack in the Tutorial arena.' "
                    "Bad: 'A character fought.' "
                    f"Return ONLY the {k} facts, one per line, numbered 1-{k}."
                ),
            },
            {"role": "user", "content": chapter_text[:8000]},
        ],
        max_tokens=500,
    )

    text = response.choices[0].message.content.strip() if response.choices else ""
    facts = []
    for line in text.split("\n"):
        line = line.strip()
        if line and len(line) > 10:
            # Strip numbering
            for prefix in [
                "1.",
                "2.",
                "3.",
                "4.",
                "5.",
                "6.",
                "7.",
                "8.",
                "9.",
                "10.",
                "1)",
                "2)",
                "3)",
                "4)",
                "5)",
                "6)",
                "7)",
                "8)",
                "9)",
                "10)",
            ]:
                if line.startswith(prefix):
                    line = line[len(prefix) :].strip()
                    break
            if line:
                facts.append(line)

    return facts[:k]


async def score_fact_against_kg(
    driver,
    fact: str,
    book_id: str,
    top_k: int = 5,
) -> bool:
    """Score whether a fact is inferable from the KG subgraph.

    1. Hybrid retrieval: fulltext keyword search + entity name matching
    2. Expand to 2-hop neighborhood
    3. LLM judges inferability
    """
    from app.llm.providers import get_instructor_for_task

    # Step 1: Hybrid retrieval — fulltext + entity name extraction
    async with driver.session() as session:
        # Extract key terms: all capitalized words (likely entity names) + first 10 words
        words = fact.split()
        entity_candidates = [w.strip(".,;:!?'\"") for w in words if w[0:1].isupper() and len(w) > 2]
        search_terms = " ".join(entity_candidates) if entity_candidates else " ".join(words[:10])
        # Escape Lucene special chars
        for char in r'\+-&|!(){}[]^"~*?:/':
            search_terms = search_terms.replace(char, f"\\{char}")

        result = await session.run(
            """
            CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
            YIELD node, score
            WHERE node.book_id = $book_id OR node.book_id IS NULL
            RETURN elementId(node) AS nid, node.name AS name,
                   labels(node)[0] AS label, node.description AS desc,
                   score
            ORDER BY score DESC
            LIMIT $k
            """,
            {"query": search_terms, "book_id": book_id, "k": top_k},
        )
        seed_nodes = [r async for r in result]

    if not seed_nodes:
        return False

    # Step 2: Expand to 2-hop neighborhood
    seed_names = [n["name"] for n in seed_nodes if n.get("name")]
    async with driver.session() as session:
        result = await session.run(
            """
            UNWIND $names AS name
            MATCH (seed {name: name})-[r1]-(hop1)-[r2]-(hop2)
            WHERE NOT hop1:Chunk AND NOT hop1:Chapter AND NOT hop1:Book
              AND NOT hop2:Chunk AND NOT hop2:Chapter AND NOT hop2:Book
              AND type(r1) <> 'MENTIONED_IN' AND type(r2) <> 'MENTIONED_IN'
            RETURN DISTINCT
                seed.name AS seed, type(r1) AS r1_type,
                hop1.name AS hop1_name, labels(hop1)[0] AS hop1_label,
                type(r2) AS r2_type,
                hop2.name AS hop2_name, labels(hop2)[0] AS hop2_label
            LIMIT 50
            """,
            {"names": seed_names},
        )
        subgraph = [r async for r in result]

    # Build text representation of subgraph
    sg_lines = []
    for n in seed_nodes:
        sg_lines.append(f"- {n['label']}: {n['name']} — {n.get('desc') or 'no description'}")
    for edge in subgraph:
        sg_lines.append(
            f"- {edge['seed']} → {edge['r1_type']} → {edge['hop1_name']} ({edge['hop1_label']}) "
            f"→ {edge['r2_type']} → {edge['hop2_name']} ({edge['hop2_label']})"
        )
    subgraph_text = "\n".join(sg_lines[:30])

    # Step 3: LLM judge
    try:
        client, model = get_instructor_for_task("summary")
    except Exception:
        return False

    response = await client.chat.completions.create(
        model=model,
        response_model=None,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a knowledge graph evaluator. Given a fact and a subgraph, "
                    "determine if the fact can be INFERRED from the subgraph information. "
                    "Respond with exactly '1' if inferable or '0' if not."
                ),
            },
            {
                "role": "user",
                "content": f"Fact: {fact}\n\nSubgraph:\n{subgraph_text}",
            },
        ],
        max_tokens=5,
    )

    answer = response.choices[0].message.content.strip() if response.choices else "0"
    return answer.startswith("1")


async def evaluate_mine(
    driver,
    book_id: str,
    n_chapters: int = 10,
    k_facts: int = 10,
) -> dict[str, Any]:
    """Run MINE benchmark on a book's KG.

    Args:
        driver: Neo4j async driver
        book_id: Book to evaluate
        n_chapters: Number of chapters to sample (evenly spaced)
        k_facts: Facts per chapter

    Returns:
        Dict with overall score, per-chapter scores, and metadata.
    """
    # Get chapter texts (evenly spaced sample)
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (ch:Chapter {book_id: $book_id})-[:HAS_CHUNK]->(c:Chunk)
            WITH ch.number AS chapter, collect(c.text) AS chunks
            ORDER BY chapter
            RETURN chapter, reduce(s = '', t IN chunks | s + t + ' ') AS text
            """,
            {"book_id": book_id},
        )
        all_chapters = [r async for r in result]

    if not all_chapters:
        return {"score": 0.0, "error": "no chapters found"}

    # Sample evenly spaced chapters
    step = max(1, len(all_chapters) // n_chapters)
    sampled = all_chapters[::step][:n_chapters]

    chapter_scores: list[dict[str, Any]] = []
    total_inferable = 0
    total_facts = 0

    for chapter_data in sampled:
        chapter_num = chapter_data["chapter"]
        chapter_text = chapter_data["text"]

        # Generate facts
        facts = await generate_chapter_facts(chapter_text, chapter_num, k=k_facts)
        if not facts:
            continue

        # Score each fact
        inferable = 0
        for fact in facts:
            try:
                if await score_fact_against_kg(driver, fact, book_id):
                    inferable += 1
            except Exception:
                logger.debug("mine_fact_scoring_failed", chapter=chapter_num, exc_info=True)

        score = inferable / len(facts) if facts else 0.0
        chapter_scores.append(
            {
                "chapter": chapter_num,
                "facts": len(facts),
                "inferable": inferable,
                "score": round(score, 3),
            }
        )
        total_inferable += inferable
        total_facts += len(facts)

        logger.info(
            "mine_chapter_scored",
            chapter=chapter_num,
            facts=len(facts),
            inferable=inferable,
            score=round(score, 3),
        )

    overall_score = total_inferable / total_facts if total_facts > 0 else 0.0

    result = {
        "score": round(overall_score, 3),
        "chapters_evaluated": len(chapter_scores),
        "total_facts": total_facts,
        "total_inferable": total_inferable,
        "per_chapter": chapter_scores,
    }

    logger.info(
        "mine_benchmark_completed", **{k: v for k, v in result.items() if k != "per_chapter"}
    )
    return result
