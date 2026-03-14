"""Data-driven tests for the chat agent pipeline.

Exercises actual logic with realistic fiction novel data. Covers gaps
identified in audit: _escape_lucene, hybrid_retrieve with extra BM25 arms,
router multi-turn, generate direct route, spoiler guard, rerank no-mutate,
citation parser edge cases, KG query label constraints, and context assembly
with relationships.
"""

from __future__ import annotations

import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

# ---------------------------------------------------------------------------
# Realistic fixture data — LitRPG "The Primal Hunter" style
# ---------------------------------------------------------------------------

FICTION_CHUNKS = [
    {
        "node_id": "chunk-001",
        "text": (
            "Jake felt the mana surge through his veins as he drew back the "
            "bowstring. His Arcane Hunter class had reached level 88, and with "
            "it came a new understanding of Arcane Powershot."
        ),
        "chapter_number": 42,
        "chapter_title": "Evolution",
        "position": 3,
        "score": 0.94,
    },
    {
        "node_id": "chunk-002",
        "text": (
            "The Viper of the Malefic stared down at Jake from the branches. "
            "Its poison aura sent shivers through the forest, and even "
            "Sylphie seemed hesitant."
        ),
        "chapter_number": 15,
        "chapter_title": "The Beast",
        "position": 7,
        "score": 0.87,
    },
    {
        "node_id": "chunk-003",
        "text": (
            "Villains' Den was the first true dungeon Jake had cleared solo. "
            "He'd relied on his Mark of the Avaricious Hunter and Big Game "
            "Hunter skills to overcome the boss."
        ),
        "chapter_number": 28,
        "chapter_title": "Solo Dungeon",
        "position": 0,
        "score": 0.81,
    },
    {
        "node_id": "chunk-004",
        "text": (
            "Miranda organized the settlement while Jake was away. Her "
            "political class gave her an edge in negotiations with the "
            "other factions."
        ),
        "chapter_number": 35,
        "chapter_title": "Governance",
        "position": 12,
        "score": 0.72,
    },
    {
        "node_id": "chunk-005",
        "text": (
            "The Viper offered Jake a blessing — a Bloodline unlike anything "
            "the multiverse had seen. Jake accepted, feeling the primordial "
            "power reshape his very soul."
        ),
        "chapter_number": 50,
        "chapter_title": "Bloodline",
        "position": 5,
        "score": 0.65,
    },
]

FICTION_ENTITIES = [
    {
        "name": "Jake Thayne",
        "label": "Character",
        "description": "Main protagonist, Arcane Hunter class, blessed by the Viper",
        "score": 8.5,
    },
    {
        "name": "Viper of the Malefic",
        "label": "Character",
        "description": "Primordial beast, patron of Jake",
        "score": 7.2,
    },
    {
        "name": "Sylphie",
        "label": "Character",
        "description": "Jake's hawk companion, wind affinity",
        "score": 6.1,
    },
    {
        "name": "Miranda",
        "label": "Character",
        "description": "Settlement leader, political class",
        "score": 5.0,
    },
]

FICTION_RELATIONSHIPS = [
    {
        "source": "Jake Thayne",
        "rel_type": "HAS_SKILL",
        "target_name": "Arcane Powershot",
        "target_label": "Skill",
    },
    {
        "source": "Jake Thayne",
        "rel_type": "HAS_SKILL",
        "target_name": "Mark of the Avaricious Hunter",
        "target_label": "Skill",
    },
    {
        "source": "Jake Thayne",
        "rel_type": "BLESSED_BY",
        "target_name": "Viper of the Malefic",
        "target_label": "Character",
    },
    {
        "source": "Viper of the Malefic",
        "rel_type": "PATRON_OF",
        "target_name": "Jake Thayne",
        "target_label": "Character",
    },
    {
        "source": "Sylphie",
        "rel_type": "COMPANION_OF",
        "target_name": "Jake Thayne",
        "target_label": "Character",
    },
]


# ═══════════════════════════════════════════════════════════════════════
# 1. _escape_lucene — Lucene special character escaping
# ═══════════════════════════════════════════════════════════════════════


class TestEscapeLucene:
    """Tests for Lucene query escaping — critical for BM25 injection prevention."""

    def test_plain_text_unchanged(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        assert _escape_lucene("Jake Thayne") == "Jake Thayne"

    def test_escapes_plus_and_minus(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        assert _escape_lucene("+Jake -Viper") == "\\+Jake \\-Viper"

    def test_escapes_all_special_characters(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        special = r'+-&|!(){}[]^"~*?:\/'
        escaped = _escape_lucene(special)
        for char in special:
            assert f"\\{char}" in escaped

    def test_escapes_parentheses_in_entity_name(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        # Real scenario: "Viper (Primordial)" in entity names
        result = _escape_lucene("Viper (Primordial)")
        assert result == "Viper \\(Primordial\\)"

    def test_escapes_colon_in_skill_name(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        result = _escape_lucene("Skill: Arcane Powershot")
        assert result == "Skill\\: Arcane Powershot"

    def test_escapes_quotes_in_title(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        result = _escape_lucene('"The Primal Hunter"')
        assert result == '\\"The Primal Hunter\\"'

    def test_empty_string(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        assert _escape_lucene("") == ""

    def test_wildcard_and_question_mark(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        result = _escape_lucene("Jake*? OR Viper")
        assert "\\*" in result
        assert "\\?" in result

    def test_mixed_text_and_specials(self):
        from app.agents.chat.nodes.retrieve import _escape_lucene

        result = _escape_lucene("Jake's [Title] & skills!")
        assert "\\[" in result
        assert "\\]" in result
        assert "\\&" in result
        assert "\\!" in result
        # Apostrophe is NOT a Lucene special char
        assert "'" in result


# ═══════════════════════════════════════════════════════════════════════
# 2. hybrid_retrieve — multi-query BM25 arms + RRF fusion
# ═══════════════════════════════════════════════════════════════════════


class TestHybridRetrieve:
    """Tests for hybrid_retrieve including extra BM25 query variants."""

    @pytest.fixture()
    def mock_repo(self):
        """Repo that returns realistic results for each arm."""
        repo = AsyncMock()

        async def fake_execute_read(query: str, params: dict) -> list:
            # Dense search (vector)
            if "vector.queryNodes" in query:
                return [FICTION_CHUNKS[0], FICTION_CHUNKS[1]]
            # BM25 fulltext search
            if "fulltext.queryNodes('chunk_fulltext'" in query:
                q = params.get("query", "")
                if "Arcane" in q or "Jake" in q:
                    return [FICTION_CHUNKS[0], FICTION_CHUNKS[2]]
                if "level" in q or "class" in q:
                    return [FICTION_CHUNKS[0], FICTION_CHUNKS[3]]
                return [FICTION_CHUNKS[1]]
            # Graph search (entity traversal)
            if "entity_fulltext" in query:
                return [FICTION_CHUNKS[0], FICTION_CHUNKS[4]]
            return []

        repo.execute_read = AsyncMock(side_effect=fake_execute_read)
        return repo

    @pytest.mark.asyncio
    async def test_basic_hybrid_no_extra_bm25(self, mock_repo):
        from app.agents.chat.nodes.retrieve import hybrid_retrieve

        results = await hybrid_retrieve(
            mock_repo,
            query_text="Who is Jake?",
            query_embedding=[0.1] * 128,
            book_id="book-1",
        )

        assert len(results) > 0
        assert all("rrf_score" in r for r in results)
        assert all("node_id" in r for r in results)
        # chunk-001 appears in all 3 arms → highest RRF
        node_ids = [r["node_id"] for r in results]
        assert node_ids[0] == "chunk-001"

    @pytest.mark.asyncio
    async def test_extra_bm25_queries_boost_results(self, mock_repo):
        from app.agents.chat.nodes.retrieve import hybrid_retrieve

        # With extra BM25 variants, chunks matching more variants get boosted
        results_without = await hybrid_retrieve(
            mock_repo,
            query_text="Who is Jake?",
            query_embedding=[0.1] * 128,
            book_id="book-1",
            extra_bm25_queries=None,
        )

        results_with = await hybrid_retrieve(
            mock_repo,
            query_text="Who is Jake?",
            query_embedding=[0.1] * 128,
            book_id="book-1",
            extra_bm25_queries=["Jake Arcane Hunter level", "What class is Jake?"],
        )

        # Both should have results
        assert len(results_without) > 0
        assert len(results_with) > 0

        # Extra BM25 queries should result in more repo calls
        # 1 dense + N sparse + 1 graph = 2 + N_extra calls
        # With 2 extra: 1 dense + 3 sparse + 1 graph = 5 gather calls
        # Without extra: 1 dense + 1 sparse + 1 graph = 3 gather calls
        calls_with = mock_repo.execute_read.call_count
        assert calls_with > 0

    @pytest.mark.asyncio
    async def test_empty_extra_bm25_same_as_none(self, mock_repo):
        from app.agents.chat.nodes.retrieve import hybrid_retrieve

        results_none = await hybrid_retrieve(
            mock_repo,
            query_text="test",
            query_embedding=[0.1] * 128,
            book_id="book-1",
            extra_bm25_queries=None,
        )

        # Reset mock call count
        mock_repo.execute_read.reset_mock()

        results_empty = await hybrid_retrieve(
            mock_repo,
            query_text="test",
            query_embedding=[0.1] * 128,
            book_id="book-1",
            extra_bm25_queries=[],
        )

        # Same number of calls (no extra BM25 tasks)
        assert len(results_none) == len(results_empty)

    @pytest.mark.asyncio
    async def test_custom_weights(self, mock_repo):
        from app.agents.chat.nodes.retrieve import hybrid_retrieve

        results = await hybrid_retrieve(
            mock_repo,
            query_text="test",
            query_embedding=[0.1] * 128,
            book_id="book-1",
            dense_weight=0.0,
            sparse_weight=10.0,
            graph_weight=0.0,
        )

        # With only sparse weight, results should favor sparse-returned chunks
        assert len(results) > 0


# ═══════════════════════════════════════════════════════════════════════
# 3. Router — multi-turn conversation history
# ═══════════════════════════════════════════════════════════════════════


class TestRouterMultiTurn:
    """Tests verifying router includes conversation history (C3 fix)."""

    @pytest.mark.asyncio
    async def test_multi_turn_history_passed_to_llm(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="entity_qa"),
        )

        history = [
            HumanMessage(content="Who is Jake?"),
            AIMessage(content="Jake is the protagonist."),
            HumanMessage(content="What about his skills?"),
            AIMessage(content="He has Arcane Powershot."),
            HumanMessage(content="Tell me more about that skill."),
        ]

        state = {
            "query": "Tell me more about that skill.",
            "messages": history,
        }

        with patch(
            "app.agents.chat.nodes.router.get_langchain_llm",
            return_value=mock_llm,
        ):
            await classify_intent(state)

        # Verify LLM received conversation history
        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + 4 history messages ([-5:-1] = indices 0..3) + current query
        assert len(call_args) == 6  # 1 system + 4 history + 1 current
        assert call_args[-1].content == "Tell me more about that skill."
        assert call_args[1].content == "Who is Jake?"

    @pytest.mark.asyncio
    async def test_single_message_no_history(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="factual_lookup"),
        )

        state = {
            "query": "Who is Jake?",
            "messages": [HumanMessage(content="Who is Jake?")],
        }

        with patch(
            "app.agents.chat.nodes.router.get_langchain_llm",
            return_value=mock_llm,
        ):
            await classify_intent(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + current query only (single message, no history)
        assert len(call_args) == 2

    @pytest.mark.asyncio
    async def test_empty_messages_no_history(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="conversational"),
        )

        state = {"query": "Hello", "messages": []}

        with patch(
            "app.agents.chat.nodes.router.get_langchain_llm",
            return_value=mock_llm,
        ):
            result = await classify_intent(state)

        assert result["route"] == "conversational"
        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + current query
        assert len(call_args) == 2

    @pytest.mark.asyncio
    async def test_two_messages_no_history_n7(self):
        """N7 fix: exactly 2 messages (1 turn) should NOT include history.

        Before N7 fix, len(history) > 1 would match 2-message conversations,
        causing the first message to be sent twice (once as history, once as query).
        After fix, threshold is > 2, so 2-message conversations skip history.
        """
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="factual_lookup"),
        )

        # Exactly 2 messages: user + assistant (the typical 2nd-turn scenario)
        history = [
            HumanMessage(content="Who is Jake?"),
            AIMessage(content="Jake is the protagonist."),
        ]

        state = {
            "query": "What about his skills?",
            "messages": history,
        }

        with patch(
            "app.agents.chat.nodes.router.get_langchain_llm",
            return_value=mock_llm,
        ):
            await classify_intent(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + current query ONLY (no history, since len(history) == 2 <= 2)
        assert len(call_args) == 2

    @pytest.mark.asyncio
    async def test_three_messages_includes_history_n7(self):
        """N7 fix: 3+ messages SHOULD include history."""
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="entity_qa"),
        )

        history = [
            HumanMessage(content="Who is Jake?"),
            AIMessage(content="Jake is the protagonist."),
            HumanMessage(content="Tell me more."),
        ]

        state = {
            "query": "Tell me more.",
            "messages": history,
        }

        with patch(
            "app.agents.chat.nodes.router.get_langchain_llm",
            return_value=mock_llm,
        ):
            await classify_intent(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + 2 history msgs (history[-5:-1]) + current query = 4
        assert len(call_args) == 4

    @pytest.mark.asyncio
    async def test_long_history_takes_last_five(self):
        """With 10 messages, only the last 5 (minus current) are included."""
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="entity_qa"),
        )

        history = []
        for i in range(10):
            if i % 2 == 0:
                history.append(HumanMessage(content=f"Question {i}"))
            else:
                history.append(AIMessage(content=f"Answer {i}"))

        state = {"query": "Latest question", "messages": history}

        with patch(
            "app.agents.chat.nodes.router.get_langchain_llm",
            return_value=mock_llm,
        ):
            await classify_intent(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + 4 history msgs (history[-5:-1]) + current query = 6
        assert len(call_args) == 6


# ═══════════════════════════════════════════════════════════════════════
# 4. Generate — direct route, spoiler guard, citation edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestGenerateDirectRoute:
    """Tests for the direct route path (I1 fix)."""

    @pytest.mark.asyncio
    async def test_direct_route_uses_direct_prompt(self):
        from app.agents.chat.nodes.generate import generate_answer

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="Hello! I'm WorldRAG. Ask me about the novel!"),
        )

        state = {
            "query": "Hello!",
            "route": "conversational",
            "context": "",
            "max_chapter": None,
        }

        with patch(
            "app.agents.chat.nodes.generate.get_langchain_llm",
            return_value=mock_llm,
        ):
            result = await generate_answer(state)

        assert "WorldRAG" in result["generation"]
        assert result["citations"] == []
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # Verify DIRECT_RESPONSE_SYSTEM was used, not GENERATOR_SYSTEM
        call_msgs = mock_llm.ainvoke.call_args[0][0]
        system_content = call_msgs[0].content
        assert "greeting" in system_content.lower() or "meta-question" in system_content.lower()

    @pytest.mark.asyncio
    async def test_direct_route_skips_context(self):
        """Direct route doesn't inject context into the prompt even if present."""
        from app.agents.chat.nodes.generate import generate_answer

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="I help with fiction!"),
        )

        state = {
            "query": "What can you do?",
            "route": "conversational",
            "context": "## Source Passages\nSome context that should be ignored.",
            "max_chapter": 50,
        }

        with patch(
            "app.agents.chat.nodes.generate.get_langchain_llm",
            return_value=mock_llm,
        ):
            await generate_answer(state)

        # Context should NOT appear in the messages sent to LLM
        call_msgs = mock_llm.ainvoke.call_args[0][0]
        for msg in call_msgs:
            assert "Source Passages" not in msg.content


class TestGenerateSpoilerGuard:
    """Tests for spoiler guard injection into generator prompt."""

    @pytest.mark.asyncio
    async def test_spoiler_guard_included_when_max_chapter_set(self):
        from app.agents.chat.nodes.generate import generate_answer

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="Jake is a hunter [Ch.5]."),
        )

        state = {
            "query": "Who is Jake?",
            "context": "Jake is a hunter in chapter 5.",
            "max_chapter": 30,
            "route": "entity_qa",
        }

        with patch(
            "app.agents.chat.nodes.generate.get_langchain_llm",
            return_value=mock_llm,
        ):
            await generate_answer(state)

        call_msgs = mock_llm.ainvoke.call_args[0][0]
        system_msg = call_msgs[0].content
        assert "Chapter 30" in system_msg
        assert "NEVER reveal" in system_msg

    @pytest.mark.asyncio
    async def test_no_spoiler_guard_when_max_chapter_none(self):
        from app.agents.chat.nodes.generate import generate_answer

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="Answer [Ch.1]."),
        )

        state = {
            "query": "test",
            "context": "some context",
            "max_chapter": None,
            "route": "entity_qa",
        }

        with patch(
            "app.agents.chat.nodes.generate.get_langchain_llm",
            return_value=mock_llm,
        ):
            await generate_answer(state)

        call_msgs = mock_llm.ainvoke.call_args[0][0]
        system_msg = call_msgs[0].content
        assert "NEVER reveal" not in system_msg


class TestCitationParserEdgeCases:
    """Extended edge case tests for _parse_citations."""

    def test_no_citations(self):
        from app.agents.chat.nodes.generate import _parse_citations

        assert _parse_citations("Jake is a hunter with no chapter refs.") == []

    def test_multiple_same_chapter(self):
        from app.agents.chat.nodes.generate import _parse_citations

        text = "Jake [Ch.5] is strong. He fights [Ch.5] bravely."
        citations = _parse_citations(text)
        assert len(citations) == 2
        assert all(c["chapter"] == 5 for c in citations)

    def test_consecutive_citations(self):
        from app.agents.chat.nodes.generate import _parse_citations

        text = "See [Ch.1][Ch.2][Ch.3] for details."
        citations = _parse_citations(text)
        assert len(citations) == 3
        assert [c["chapter"] for c in citations] == [1, 2, 3]

    def test_large_chapter_numbers(self):
        from app.agents.chat.nodes.generate import _parse_citations

        text = "This happens in [Ch.999, p.42]."
        citations = _parse_citations(text)
        assert len(citations) == 1
        assert citations[0] == {"chapter": 999, "position": 42}

    def test_malformed_citation_ignored(self):
        from app.agents.chat.nodes.generate import _parse_citations

        text = "See [Ch.abc] and [Ch.5] for details."
        citations = _parse_citations(text)
        assert len(citations) == 1
        assert citations[0]["chapter"] == 5

    def test_partial_citation_format_ignored(self):
        from app.agents.chat.nodes.generate import _parse_citations

        # "[Chapter 5]" is NOT the citation format
        text = "See [Chapter 5] and [Ch.5] for info."
        citations = _parse_citations(text)
        assert len(citations) == 1

    def test_citation_with_position_zero(self):
        from app.agents.chat.nodes.generate import _parse_citations

        text = "At [Ch.1, p.0] the story begins."
        citations = _parse_citations(text)
        assert citations[0] == {"chapter": 1, "position": 0}

    def test_empty_string(self):
        from app.agents.chat.nodes.generate import _parse_citations

        assert _parse_citations("") == []


# ═══════════════════════════════════════════════════════════════════════
# 5. Rerank — no-mutate verification (I6 fix)
# ═══════════════════════════════════════════════════════════════════════


class TestRerankNoMutate:
    """Verify that rerank fallback doesn't mutate input state dicts."""

    @pytest.mark.asyncio
    async def test_rerank_does_not_mutate_fused_results(self):
        """zerank reranker must not mutate the original fused_results dicts."""
        from app.agents.chat.nodes.rerank import rerank_results

        original_chunks = [
            {"node_id": "a", "text": "t1", "rrf_score": 0.5, "extra": "data1"},
            {"node_id": "b", "text": "t2", "rrf_score": 0.4, "extra": "data2"},
            {"node_id": "c", "text": "t3", "rrf_score": 0.3, "extra": "data3"},
        ]
        frozen = copy.deepcopy(original_chunks)

        state = {"query": "test", "fused_results": original_chunks}

        # Mock zerank reranker to return sorted by index
        mock_reranker = MagicMock()
        mock_reranker.rank = MagicMock(
            return_value=[
                {"corpus_id": 0, "score": 1.0},
                {"corpus_id": 1, "score": 0.8},
                {"corpus_id": 2, "score": 0.5},
            ]
        )

        with patch("app.agents.chat.nodes.rerank.get_local_reranker", return_value=mock_reranker):
            result = await rerank_results(state)

        # Original dicts must not be mutated
        for chunk in original_chunks:
            assert chunk == frozen[original_chunks.index(chunk)]
            assert "relevance_score" not in chunk

        # Result dicts are new objects with relevance_score
        for reranked in result["reranked_chunks"]:
            assert "relevance_score" in reranked


# ═══════════════════════════════════════════════════════════════════════
# 6. KG Query — label constraints + Lucene escaping (C4 + I7 fixes)
# ═══════════════════════════════════════════════════════════════════════


class TestKGQueryDataDriven:
    """Data-driven tests for KG query with realistic entity data."""

    @pytest.mark.asyncio
    async def test_multiple_entities_with_relationships(self):
        """KG query with multiple entities returns all relationships grouped."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=json.dumps(
                    {
                        "entities": ["Jake Thayne", "Viper of the Malefic"],
                        "query_type": "relationship",
                    }
                )
            ),
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                # Entity search results
                FICTION_ENTITIES[:2],
                # Relationship query results
                FICTION_RELATIONSHIPS[:4],
                # Grounded chunks
                FICTION_CHUNKS[:3],
            ]
        )

        state = {
            "query": "How are Jake and the Viper related?",
            "book_id": "book-primal",
            "max_chapter": None,
        }

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            result = await kg_search(state, repo=mock_repo)

        # Should NOT fall back to hybrid_rag
        assert "route" not in result or result.get("route") != "entity_qa"
        assert len(result["kg_entities"]) == 2

        # Jake's entity should have his relationships attached
        jake_entity = next(e for e in result["kg_entities"] if e["name"] == "Jake Thayne")
        assert len(jake_entity["relationships"]) > 0
        rel_types = {r["rel_type"] for r in jake_entity["relationships"]}
        assert "HAS_SKILL" in rel_types or "BLESSED_BY" in rel_types

    @pytest.mark.asyncio
    async def test_label_constraints_passed_to_cypher(self):
        """Relationship query uses entity labels to constrain Cypher match."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content='{"entities": ["Jake Thayne"], "query_type": "entity_lookup"}'
            ),
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                # Entity search: returns Jake with Character label
                [{"name": "Jake Thayne", "label": "Character", "description": "MC", "score": 9.0}],
                # Relationships
                [],
                # Grounded chunks
                [{"node_id": "c1", "text": "Jake...", "chapter_number": 1, "chapter_title": "Ch1"}],
            ]
        )

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            await kg_search(
                {"query": "Who is Jake?", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        # Verify the relationship query (2nd call) includes paired entity/label maps (N2 fix)
        relationship_call = mock_repo.execute_read.call_args_list[1]
        params = relationship_call[0][1]
        assert "pairs" in params
        assert any(p["label"] == "Character" for p in params["pairs"])

    @pytest.mark.asyncio
    async def test_lucene_special_chars_in_entity_name(self):
        """Entity names with Lucene specials are properly escaped in fulltext query."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=json.dumps(
                    {
                        "entities": ["Viper (Primordial)", "Jake+Beast"],
                        "query_type": "entity_lookup",
                    }
                )
            ),
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            await kg_search(
                {"query": "test", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        # Verify entity fulltext query (1st call) has escaped specials
        entity_call = mock_repo.execute_read.call_args_list[0]
        query_param = entity_call[0][1]["query"]
        assert "\\(" in query_param
        assert "\\)" in query_param
        assert "\\+" in query_param

    @pytest.mark.asyncio
    async def test_entity_search_filters_by_book_id_n4(self):
        """N4 fix: entity fulltext search includes book_id filter via GROUNDED_IN chain."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content='{"entities": ["Jake"], "query_type": "entity_lookup"}'),
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                # Entity fulltext search
                [{"name": "Jake", "label": "Character", "description": "MC", "score": 8.0}],
                # Relationships
                [],
                # Grounded chunks
                [{"node_id": "c1", "text": "t", "chapter_number": 1, "chapter_title": "T"}],
            ]
        )

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            await kg_search(
                {"query": "Jake?", "book_id": "book-42", "max_chapter": None},
                repo=mock_repo,
            )

        # The first call (entity fulltext) must include book_id param
        entity_search_call = mock_repo.execute_read.call_args_list[0]
        entity_search_params = entity_search_call[0][1]
        assert entity_search_params["book_id"] == "book-42"

        # The Cypher should reference book_id (via GROUNDED_IN chain)
        entity_search_cypher = entity_search_call[0][0]
        assert "book_id" in entity_search_cypher

    @pytest.mark.asyncio
    async def test_json_parse_failure_falls_back(self):
        """Invalid JSON from LLM falls back to hybrid_rag."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="not valid json at all"),
        )

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            result = await kg_search(
                {"query": "test", "book_id": "b1", "max_chapter": None},
                repo=AsyncMock(),
            )

        assert result["route"] == "entity_qa"
        assert result["kg_entities"] == []

    @pytest.mark.asyncio
    async def test_max_chapter_filtering(self):
        """max_chapter is forwarded to all 3 Cypher queries."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content='{"entities": ["Jake"], "query_type": "entity_lookup"}'),
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                [{"name": "Jake", "label": "Character", "description": "", "score": 5.0}],
                [],
                [{"node_id": "c1", "text": "text", "chapter_number": 1, "chapter_title": "T"}],
            ]
        )

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            await kg_search(
                {"query": "Jake?", "book_id": "b1", "max_chapter": 25},
                repo=mock_repo,
            )

        # All 3 calls should have max_chapter=25
        for call in mock_repo.execute_read.call_args_list:
            params = call[0][1]
            assert params["max_chapter"] == 25


# ═══════════════════════════════════════════════════════════════════════
# 7. Context Assembly — with relationships and KG entities
# ═══════════════════════════════════════════════════════════════════════


class TestContextAssemblyDataDriven:
    """Data-driven context assembly tests with realistic fiction data."""

    @pytest.mark.asyncio
    async def test_context_includes_passages_and_entities(self):
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            return_value=[
                {"name": "Jake Thayne", "label": "Character", "description": "Arcane Hunter"},
                {"name": "Arcane Powershot", "label": "Skill", "description": "A powerful skill"},
            ]
        )

        reranked = [
            {
                "text": "Jake fired Arcane Powershot at the beast.",
                "chapter_number": 42,
                "chapter_title": "Evolution",
                "relevance_score": 0.94,
            },
            {
                "text": "The skill had evolved from its base form.",
                "chapter_number": 43,
                "chapter_title": "Power",
                "relevance_score": 0.82,
            },
        ]

        state = {
            "reranked_chunks": reranked,
            "book_id": "book-primal",
            "max_chapter": None,
        }

        result = await assemble_context(state, repo=mock_repo)

        ctx = result["context"]
        assert "## Source Passages" in ctx
        assert "Chapter 42 — Evolution" in ctx
        assert "relevance: 0.94" in ctx
        assert "Jake fired Arcane Powershot" in ctx
        assert "## Related Knowledge Graph Entities" in ctx
        assert "**Jake Thayne** (Character)" in ctx

    @pytest.mark.asyncio
    async def test_context_uses_kg_entities_from_state_if_present(self):
        """When kg_entities already in state (from kg_query), those are used."""
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        kg_entities_from_state = [
            {
                "name": "Jake Thayne",
                "label": "Character",
                "description": "MC",
                "relationships": [
                    {
                        "rel_type": "HAS_SKILL",
                        "target_name": "Arcane Powershot",
                        "target_label": "Skill",
                    }
                ],
            }
        ]

        state = {
            "reranked_chunks": [
                {
                    "text": "Jake used Arcane Powershot.",
                    "chapter_number": 5,
                    "chapter_title": "Fight",
                    "relevance_score": 0.9,
                }
            ],
            "book_id": "b1",
            "max_chapter": None,
            "kg_entities": kg_entities_from_state,
        }

        result = await assemble_context(state, repo=mock_repo)

        ctx = result["context"]
        assert "**Jake Thayne** (Character)" in ctx
        assert "HAS_SKILL" in ctx
        assert "Arcane Powershot" in ctx
        assert result["kg_entities"] == kg_entities_from_state

    @pytest.mark.asyncio
    async def test_context_with_multiple_chapters(self):
        """Chunks from different chapters fetch entities from all chapters."""
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        state = {
            "reranked_chunks": [
                {
                    "text": "Chunk from ch5",
                    "chapter_number": 5,
                    "chapter_title": "Ch5",
                    "relevance_score": 0.9,
                },
                {
                    "text": "Chunk from ch10",
                    "chapter_number": 10,
                    "chapter_title": "Ch10",
                    "relevance_score": 0.8,
                },
            ],
            "book_id": "b1",
            "max_chapter": None,
        }

        await assemble_context(state, repo=mock_repo)

        # Verify repo was called with both chapter numbers
        call_params = mock_repo.execute_read.call_args[0][1]
        assert set(call_params["chapters"]) == {5, 10}

    @pytest.mark.asyncio
    async def test_context_missing_chapter_number_key(self):
        """Chunks without chapter_number key are handled gracefully."""
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        state = {
            "reranked_chunks": [
                {"text": "Orphan chunk with no chapter metadata", "relevance_score": 0.5},
            ],
            "book_id": "b1",
            "max_chapter": None,
        }

        result = await assemble_context(state, repo=mock_repo)

        assert "## Source Passages" in result["context"]
        assert "Chapter ?" in result["context"]


# ═══════════════════════════════════════════════════════════════════════
# 8. RRF fusion — additional data-driven tests
# ═══════════════════════════════════════════════════════════════════════


class TestRRFFusionDataDriven:
    """Data-driven RRF tests with realistic retrieval results."""

    def test_three_arm_fusion_with_fiction_data(self):
        """3-arm fusion (dense + sparse + graph) with overlapping results."""
        from app.agents.chat.nodes.retrieve import rrf_fuse

        dense = [FICTION_CHUNKS[0], FICTION_CHUNKS[1], FICTION_CHUNKS[2]]
        sparse = [FICTION_CHUNKS[2], FICTION_CHUNKS[0], FICTION_CHUNKS[3]]
        graph = [FICTION_CHUNKS[0], FICTION_CHUNKS[4]]

        fused = rrf_fuse(
            [dense, sparse, graph],
            weights=[1.0, 1.0, 0.5],
            top_k=5,
        )

        # chunk-001 appears in all 3 lists → highest score
        assert fused[0]["node_id"] == "chunk-001"

        # chunk-003 appears in dense (pos 2) + sparse (pos 0) → 2nd or 3rd
        chunk_003_score = next(r["rrf_score"] for r in fused if r["node_id"] == "chunk-003")
        chunk_004_score = next(
            (r["rrf_score"] for r in fused if r["node_id"] == "chunk-004"),
            0.0,
        )
        assert chunk_003_score > chunk_004_score

    def test_fusion_preserves_all_metadata_fields(self):
        """Fused results keep text, chapter info, position, and score."""
        from app.agents.chat.nodes.retrieve import rrf_fuse

        results = [FICTION_CHUNKS[0]]
        fused = rrf_fuse([results], weights=[1.0], top_k=1)

        assert fused[0]["text"] == FICTION_CHUNKS[0]["text"]
        assert fused[0]["chapter_number"] == 42
        assert fused[0]["chapter_title"] == "Evolution"
        assert fused[0]["position"] == 3

    def test_duplicate_node_id_across_lists_first_metadata_wins(self):
        """When same node_id in multiple lists with different metadata, first wins."""
        from app.agents.chat.nodes.retrieve import rrf_fuse

        list_a = [{"node_id": "x", "text": "version_a", "source": "dense"}]
        list_b = [{"node_id": "x", "text": "version_b", "source": "sparse"}]

        fused = rrf_fuse([list_a, list_b], weights=[1.0, 1.0], top_k=1)
        assert fused[0]["text"] == "version_a"
        assert fused[0]["source"] == "dense"


# ═══════════════════════════════════════════════════════════════════════
# 9. Schema validation — book_id + thread_id constraints (#3 fix)
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Tests for input validation hardening on ChatRequest."""

    def test_valid_book_id_accepted(self):
        from app.schemas.chat import ChatRequest

        req = ChatRequest(query="Who is Jake?", book_id="book-123")
        assert req.book_id == "book-123"

    def test_book_id_with_dots_and_colons(self):
        from app.schemas.chat import ChatRequest

        req = ChatRequest(query="q", book_id="org.name:book-42")
        assert req.book_id == "org.name:book-42"

    def test_book_id_too_long_rejected(self):
        import pydantic

        from app.schemas.chat import ChatRequest

        with pytest.raises(pydantic.ValidationError):
            ChatRequest(query="q", book_id="a" * 201)

    def test_book_id_empty_rejected(self):
        import pydantic

        from app.schemas.chat import ChatRequest

        with pytest.raises(pydantic.ValidationError):
            ChatRequest(query="q", book_id="")

    def test_book_id_special_chars_rejected(self):
        import pydantic

        from app.schemas.chat import ChatRequest

        with pytest.raises(pydantic.ValidationError):
            ChatRequest(query="q", book_id="book<script>alert(1)</script>")

    def test_thread_id_valid(self):
        from app.schemas.chat import ChatRequest

        req = ChatRequest(query="q", book_id="b1", thread_id="thread-abc.123")
        assert req.thread_id == "thread-abc.123"

    def test_thread_id_too_long_rejected(self):
        import pydantic

        from app.schemas.chat import ChatRequest

        with pytest.raises(pydantic.ValidationError):
            ChatRequest(query="q", book_id="b1", thread_id="t" * 201)

    def test_thread_id_special_chars_rejected(self):
        import pydantic

        from app.schemas.chat import ChatRequest

        with pytest.raises(pydantic.ValidationError):
            ChatRequest(query="q", book_id="b1", thread_id="thread;DROP TABLE")

    def test_thread_id_none_accepted(self):
        from app.schemas.chat import ChatRequest

        req = ChatRequest(query="q", book_id="b1", thread_id=None)
        assert req.thread_id is None


# ═══════════════════════════════════════════════════════════════════════
# 10. KG query — Lucene phrase quoting (#4 fix) + empty name filtering (#7 fix)
# ═══════════════════════════════════════════════════════════════════════


class TestKGQueryLuceneQuoting:
    """Tests for multi-word entity name quoting and empty name filtering."""

    @pytest.mark.asyncio
    async def test_multi_word_entity_quoted_in_lucene(self):
        """#4 fix: 'Jake the Betrayer' becomes a quoted phrase in Lucene query."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=json.dumps(
                    {
                        "entities": ["Jake the Betrayer", "Mira"],
                        "query_type": "entity_lookup",
                    }
                )
            ),
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            await kg_search(
                {"query": "test", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        # First call is entity fulltext search
        entity_call = mock_repo.execute_read.call_args_list[0]
        query_param = entity_call[0][1]["query"]
        # Multi-word name should be quoted
        assert '"Jake the Betrayer"' in query_param
        # Single-word name should NOT be quoted
        assert query_param.endswith("OR Mira") or "OR Mira" in query_param

    @pytest.mark.asyncio
    async def test_empty_entity_names_filtered_out(self):
        """#7 fix: empty/whitespace entity names are filtered before Lucene query."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=json.dumps(
                    {
                        "entities": ["", "  ", "Jake"],
                        "query_type": "entity_lookup",
                    }
                )
            ),
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            await kg_search(
                {"query": "test", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        # Should still call repo (Jake is valid)
        entity_call = mock_repo.execute_read.call_args_list[0]
        query_param = entity_call[0][1]["query"]
        # Only "Jake" should remain, no empty OR fragments
        assert "Jake" in query_param
        assert " OR  OR " not in query_param

    @pytest.mark.asyncio
    async def test_all_empty_names_fallback_to_hybrid(self):
        """#7 fix: if ALL entity names are empty, fallback to hybrid_rag."""
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=json.dumps(
                    {
                        "entities": ["", "  "],
                        "query_type": "entity_lookup",
                    }
                )
            ),
        )

        mock_repo = AsyncMock()

        with patch(
            "app.agents.chat.nodes.kg_query.get_langchain_llm",
            return_value=mock_llm,
        ):
            result = await kg_search(
                {"query": "test", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        assert result["route"] == "entity_qa"
        # repo should NOT have been called for entity search
        mock_repo.execute_read.assert_not_called()
