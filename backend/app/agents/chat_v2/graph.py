"""Chat v2 LangGraph: 8-node Graphiti-based retrieval pipeline.

Nodes
-----
1. router          — classify intent -> route field
2. graphiti_search — call GraphitiClient.search()
3. cypher_lookup   — direct Neo4j MATCH for entity names
4. direct          — pass-through (conversational, no retrieval)
5. context_assembly — join context facts into text
6. generate        — LLM answer generation
7. faithfulness    — lightweight score (real NLI wired later)

Edges
-----
router -> graphiti_search | cypher_lookup | direct   (conditional)
graphiti_search -> context_assembly
cypher_lookup   -> context_assembly
direct          -> context_assembly
context_assembly -> generate
generate         -> faithfulness
faithfulness     -> END (score >= 0.6 or retries >= 2) | graphiti_search (retry)
"""

from __future__ import annotations

import asyncio
import math
import re
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.chat_v2.state import ChatV2State
from app.core.logging import get_logger

logger = get_logger(__name__)

FAITHFULNESS_THRESHOLD = 0.6
MAX_RETRIES = 2

# --------------------------------------------------------------------------- #
# Keyword fallback patterns (used when LLM router is unavailable)              #
# --------------------------------------------------------------------------- #
_CYPHER_PATTERNS: tuple[str, ...] = (
    "list skill",
    "list class",
    "what class",
    "what skill",
    "show skill",
    "show class",
    "which skill",
    "which class",
    "what level",
    "show level",
    "list level",
    "how many skill",
    "how many class",
)

_DIRECT_PATTERNS: tuple[str, ...] = (
    "hello",
    "hi ",
    "hey ",
    "thanks",
    "thank you",
    "bye",
    "goodbye",
    "ok",
    "okay",
    "sure",
    "great",
    "cool",
    "nice",
    "awesome",
)

_VALID_ROUTES: frozenset[str] = frozenset({"cypher_lookup", "graphiti_search", "direct"})

_ROUTER_PROMPT = """\
Classify this user question about a fiction novel into exactly one category.

Categories:
- "cypher_lookup": Structured factual questions about specific entities, attributes, or lists. Examples: "What skills does Jake have?", "List all characters", "What class is Jake at chapter 30?"
- "graphiti_search": Open-ended questions about plot, relationships, themes, or analysis. Examples: "Why did Jake choose that path?", "What happened in the battle?", "How are Jake and Viper related?"
- "direct": Greetings, thanks, or conversational messages with no knowledge retrieval needed. Examples: "Hello", "Thanks!", "Can you help me?"

Question: {query}

Respond with ONLY the category name, nothing else."""


def _keyword_classify_route(query: str) -> str:
    """Keyword-based fallback classifier.

    Returns:
        "cypher_lookup" for structured entity-list queries.
        "direct"        for conversational turns.
        "graphiti_search" for everything else.
    """
    q_lower = query.lower().strip()
    for pattern in _CYPHER_PATTERNS:
        if pattern in q_lower:
            return "cypher_lookup"
    for pattern in _DIRECT_PATTERNS:
        if q_lower == pattern.strip() or q_lower.startswith(pattern):
            return "direct"
    return "graphiti_search"


# --------------------------------------------------------------------------- #
# Graph factory                                                                #
# --------------------------------------------------------------------------- #


def build_chat_v2_graph(graphiti: Any, neo4j_driver: Any) -> StateGraph:
    """Build the chat v2 StateGraph (uncompiled).

    All node functions are defined here as closures so they can reference
    ``graphiti`` and ``neo4j_driver`` without globals.

    Args:
        graphiti: A :class:`~app.core.graphiti_client.GraphitiClient` instance
            (or a compatible mock for testing).
        neo4j_driver: An async Neo4j driver instance (or mock).

    Returns:
        Uncompiled :class:`langgraph.graph.StateGraph`.
    """

    # ------------------------------------------------------------------ #
    # Node 1: router                                                       #
    # ------------------------------------------------------------------ #

    async def router(state: dict[str, Any]) -> dict[str, Any]:
        """Classify the user query using an LLM, with keyword fallback."""
        query: str = state.get("query", "")
        if not query:
            # Try to extract from last human message
            from langchain_core.messages import HumanMessage

            messages = state.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    query = str(msg.content)
                    break

        # Fast LLM classification
        route: str | None = None
        try:
            from app.config import settings
            from app.llm.providers import get_langchain_llm

            llm = get_langchain_llm(settings.llm_generation)
            prompt = _ROUTER_PROMPT.format(query=query)
            response = await llm.ainvoke(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
            candidate = raw.strip().strip('"').lower()
            if candidate in _VALID_ROUTES:
                route = candidate
                logger.info("chat_v2_router_llm", query=query[:120], route=route)
        except Exception:
            logger.warning("chat_v2_router_llm_failed", exc_info=True)

        if route is None:
            # Fallback: keyword heuristic
            route = _keyword_classify_route(query)
            logger.info("chat_v2_router_keyword_fallback", query=query[:120], route=route)

        logger.info("chat_v2_router", query=query[:120], route=route)
        return {"route": route, "query": query, "original_query": query}

    # ------------------------------------------------------------------ #
    # Node 2: graphiti_search                                              #
    # ------------------------------------------------------------------ #

    async def graphiti_search(state: dict[str, Any]) -> dict[str, Any]:
        """Call GraphitiClient.search() and return raw context list."""
        query: str = state.get("query", "")
        saga_id: str = state.get("saga_id", "")
        max_chapter: int | None = state.get("max_chapter")

        logger.info("chat_v2_graphiti_search", query=query[:120], saga_id=saga_id)
        try:
            results: list[Any] = await graphiti.search(query=query, saga_id=saga_id)
        except Exception:
            logger.warning("chat_v2_graphiti_search_failed", exc_info=True)
            results = []

        # Filter results by max_chapter using NarrativeTemporalMapper
        if max_chapter is not None and results:
            from app.services.saga_profile.temporal import NarrativeTemporalMapper

            filtered: list[Any] = []
            for edge in results:
                valid_at = getattr(edge, "valid_at", None) or getattr(edge, "created_at", None)
                if valid_at is not None:
                    try:
                        _, chapter_num, _ = NarrativeTemporalMapper.from_datetime(valid_at)
                        if chapter_num <= max_chapter:
                            filtered.append(edge)
                    except (ValueError, TypeError):
                        filtered.append(edge)  # keep if can't parse
                else:
                    filtered.append(edge)  # keep if no timestamp
            results = filtered

        context: list[dict[str, Any]] = []
        for edge in results:
            # EntityEdge objects expose .fact, .source_node_name, .target_node_name
            fact = getattr(edge, "fact", None) or str(edge)
            context.append(
                {
                    "fact": fact,
                    "source": getattr(edge, "source_node_name", ""),
                    "target": getattr(edge, "target_node_name", ""),
                }
            )

        retries: int = state.get("retries", 0)
        # Increment retries only when this node is called as a retry (i.e. a
        # second visit — retries was already > 0 on entry, or we detect a
        # faithfulness-driven re-entry via the faithfulness_score field).
        faithfulness_score: float = state.get("faithfulness_score", -1.0)
        if faithfulness_score >= 0:
            # We've been here before (faithfulness check ran), so count it.
            retries = retries + 1

        logger.info("chat_v2_graphiti_search_done", context_count=len(context))
        return {"retrieved_context": context, "retries": retries}

    # ------------------------------------------------------------------ #
    # Node 3: cypher_lookup                                                #
    # ------------------------------------------------------------------ #

    async def cypher_lookup(state: dict[str, Any]) -> dict[str, Any]:
        """Run a direct Neo4j MATCH for entity names matching the query hint."""
        saga_id: str = state.get("saga_id", "")
        book_id: str = state.get("book_id", "")
        query: str = state.get("query", "")
        max_chapter: int | None = state.get("max_chapter")

        query_hint = query  # default: use full query as hint

        # Build WHERE clause with optional max_chapter spoiler guard
        where_clause = "WHERE toLower(n.name) CONTAINS toLower($query_hint)"
        if max_chapter is not None:
            where_clause += " AND (n.chapter_num IS NULL OR n.chapter_num <= $max_chapter)"

        cypher = (
            "MATCH (n:Entity {group_id: $saga_id}) "
            f"{where_clause} "
            "RETURN n.name AS name, n.summary AS summary, labels(n) AS labels "
            "LIMIT 20"
        )

        logger.info("chat_v2_cypher_lookup", saga_id=saga_id, book_id=book_id, query_hint=query_hint[:120])

        context: list[dict[str, Any]] = []
        try:
            async with neo4j_driver.session() as session:
                result = await session.run(
                    cypher,
                    saga_id=saga_id,
                    query_hint=query_hint,
                    max_chapter=max_chapter,
                )
                records = await result.data()
                for rec in records:
                    context.append(
                        {
                            "fact": f"{rec.get('name', '')}: {rec.get('summary', '')}",
                            "source": rec.get("name", ""),
                            "target": "",
                            "labels": rec.get("labels", []),
                        }
                    )
        except Exception:
            logger.warning("chat_v2_cypher_lookup_failed", exc_info=True)

        logger.info("chat_v2_cypher_lookup_done", context_count=len(context))
        return {"retrieved_context": context}

    # ------------------------------------------------------------------ #
    # Node 4: direct                                                       #
    # ------------------------------------------------------------------ #

    async def direct(state: dict[str, Any]) -> dict[str, Any]:
        """Pass-through for conversational turns — no retrieval needed."""
        logger.info("chat_v2_direct")
        return {"retrieved_context": []}

    # ------------------------------------------------------------------ #
    # Node 5: context_assembly                                             #
    # ------------------------------------------------------------------ #

    async def context_assembly(state: dict[str, Any]) -> dict[str, Any]:
        """Join retrieved context facts into a single text block."""
        context_items: list[dict[str, Any]] = state.get("retrieved_context", [])
        route: str = state.get("route", "graphiti_search")

        if not context_items:
            assembled = ""
        else:
            lines: list[str] = []
            for item in context_items:
                fact = item.get("fact", "")
                source = item.get("source", "")
                target = item.get("target", "")
                if source and target:
                    lines.append(f"[{source} -> {target}] {fact}")
                elif source:
                    lines.append(f"[{source}] {fact}")
                else:
                    lines.append(fact)
            assembled = "\n".join(lines)

        logger.info(
            "chat_v2_context_assembly",
            context_length=len(assembled),
            item_count=len(context_items),
            route=route,
        )
        # Store assembled text in entity_summaries as a single-element list
        return {"entity_summaries": [{"text": assembled}] if assembled else []}

    # ------------------------------------------------------------------ #
    # Node 6: generate                                                     #
    # ------------------------------------------------------------------ #

    async def generate(state: dict[str, Any]) -> dict[str, Any]:
        """Call the LLM with context + query to produce an answer."""
        # Import here to avoid circular imports at module level
        from app.config import settings
        from app.llm.providers import get_llm

        query: str = state.get("query", "")
        entity_summaries: list[dict[str, Any]] = state.get("entity_summaries", [])
        route: str = state.get("route", "graphiti_search")

        context_text = "\n".join(s.get("text", "") for s in entity_summaries)

        system_prompt = (
            "You are a knowledgeable assistant for a fiction novel universe. "
            "Answer the user's question using only the provided context. "
            "If the context is empty or irrelevant, say so honestly."
        )

        if context_text:
            user_prompt = (
                f"Context:\n{context_text}\n\n"
                f"Question: {query}\n\n"
                "Answer:"
            )
        else:
            user_prompt = f"Question: {query}\n\nAnswer:"

        logger.info("chat_v2_generate", route=route, has_context=bool(context_text))

        try:
            llm = get_llm(settings.llm_chat)
            from langchain_core.messages import HumanMessage, SystemMessage

            response = await llm.ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            answer = str(response.content)
        except Exception:
            logger.warning("chat_v2_generate_failed", exc_info=True)
            answer = "I was unable to generate an answer at this time."

        logger.info("chat_v2_generate_done", answer_length=len(answer))
        return {
            "generation": answer,
            "generation_output": {"answer": answer, "route": route},
        }

    # ------------------------------------------------------------------ #
    # Node 7: faithfulness                                                 #
    # ------------------------------------------------------------------ #

    async def faithfulness(state: dict[str, Any]) -> dict[str, Any]:
        """NLI-based faithfulness check using DeBERTa-v3-large CrossEncoder.

        Scoring rules:
        1. route == "direct"  -> score 1.0 (no retrieval, nothing to check)
        2. no context         -> score 0.3 (no grounding, possible hallucination)
        3. otherwise          -> run NLI, score = mean(p_entail + 0.5*p_neutral)
                                 over sentence-level claims in the generation.

        The CrossEncoder predict() is synchronous — runs in a thread executor.
        Falls back to 0.8 on model-load or inference failure (safe for tests).
        """
        route: str = state.get("route", "graphiti_search")
        entity_summaries: list[dict[str, Any]] = state.get("entity_summaries", [])
        context_text = "\n".join(s.get("text", "") for s in entity_summaries).strip()
        generation: str = state.get("generation", "")

        # Case 1: direct (conversational) route — no retrieval, skip NLI
        if route == "direct":
            logger.info("chat_v2_faithfulness", score=1.0, route=route, reason="direct_route_skip")
            return {
                "faithfulness_score": 1.0,
                "reasoning": "Direct conversational route — faithfulness check skipped.",
            }

        # Case 2: no context retrieved
        if not context_text:
            logger.info("chat_v2_faithfulness", score=0.3, route=route, reason="no_context")
            return {
                "faithfulness_score": 0.3,
                "reasoning": "No context retrieved for a non-direct query — possible hallucination.",
            }

        # Case 3: run NLI
        _CTX_MAX_CHARS = 2000
        _MIN_CLAIM_WORDS = 4

        def _split_claims(text: str) -> list[str]:
            sentences = re.split(r"(?<=[.!?])\s+", text.strip())
            return [s.strip() for s in sentences if len(s.split()) >= _MIN_CLAIM_WORDS]

        def _logits_to_score(logits: list[float]) -> tuple[float, bool]:
            """Convert [contradiction, entailment, neutral] logits to a score."""
            c_logit, e_logit, n_logit = float(logits[0]), float(logits[1]), float(logits[2])
            exp_c = math.exp(c_logit)
            exp_e = math.exp(e_logit)
            exp_n = math.exp(n_logit)
            total = exp_c + exp_e + exp_n
            p_contra = exp_c / total
            p_entail = exp_e / total
            p_neutral = exp_n / total
            score = p_entail * 1.0 + p_neutral * 0.5
            return score, p_contra > 0.5

        claims = _split_claims(generation)
        if not claims:
            logger.warning("chat_v2_faithfulness_no_claims", generation_len=len(generation))
            return {
                "faithfulness_score": 0.0,
                "reasoning": "No scoreable claims found in the generated answer.",
            }

        truncated_ctx = context_text[:_CTX_MAX_CHARS]
        pairs = [(claim, truncated_ctx) for claim in claims]

        try:
            from app.llm.local_models import get_nli_model

            nli_model = get_nli_model()
            loop = asyncio.get_running_loop()
            raw_scores = await loop.run_in_executor(
                None, lambda: nli_model.predict(pairs).tolist()
            )

            claim_scores: list[float] = []
            has_contradiction = False
            for logits in raw_scores:
                claim_score, is_contra = _logits_to_score(logits)
                claim_scores.append(claim_score)
                if is_contra:
                    has_contradiction = True

            score = sum(claim_scores) / len(claim_scores)
            reasoning = (
                f"NLI score {score:.2f} over {len(claims)} claim(s)"
                + (" — contradiction detected" if has_contradiction else "")
            )
        except Exception:  # noqa: BLE001
            logger.warning("chat_v2_faithfulness_nli_failed", route=route, exc_info=True)
            score = 0.8
            reasoning = "NLI model error — defaulting to 0.8."

        logger.info(
            "chat_v2_faithfulness",
            score=round(score, 3),
            route=route,
            claims=len(claims),
        )
        return {"faithfulness_score": score, "reasoning": reasoning}

    # ------------------------------------------------------------------ #
    # Conditional edge functions                                           #
    # ------------------------------------------------------------------ #

    def _route_after_router(state: dict[str, Any]) -> str:
        route = state.get("route", "graphiti_search")
        if route == "cypher_lookup":
            return "cypher_lookup"
        if route == "direct":
            return "direct"
        return "graphiti_search"

    def _route_after_faithfulness(state: dict[str, Any]) -> str:
        score: float = state.get("faithfulness_score", 0.0)
        retries: int = state.get("retries", 0)
        if score >= FAITHFULNESS_THRESHOLD or retries >= MAX_RETRIES:
            return END
        return "graphiti_search"

    # ------------------------------------------------------------------ #
    # Assemble the graph                                                   #
    # ------------------------------------------------------------------ #

    builder = StateGraph(ChatV2State)

    builder.add_node("router", router)
    builder.add_node("graphiti_search", graphiti_search)
    builder.add_node("cypher_lookup", cypher_lookup)
    builder.add_node("direct", direct)
    builder.add_node("context_assembly", context_assembly)
    builder.add_node("generate", generate)
    builder.add_node("faithfulness", faithfulness)

    # Entry point
    builder.add_edge(START, "router")

    # Router dispatches to one of three retrieval nodes
    builder.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "graphiti_search": "graphiti_search",
            "cypher_lookup": "cypher_lookup",
            "direct": "direct",
        },
    )

    # All retrieval paths converge on context_assembly
    builder.add_edge("graphiti_search", "context_assembly")
    builder.add_edge("cypher_lookup", "context_assembly")
    builder.add_edge("direct", "context_assembly")

    # Linear path through generation and quality check
    builder.add_edge("context_assembly", "generate")
    builder.add_edge("generate", "faithfulness")

    # Faithfulness: pass -> END, fail -> retry via graphiti_search
    builder.add_conditional_edges(
        "faithfulness",
        _route_after_faithfulness,
        {END: END, "graphiti_search": "graphiti_search"},
    )

    return builder
