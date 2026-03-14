"""Chat v2 LangGraph: 8-node Graphiti-based retrieval pipeline.

Nodes
-----
1. router          — classify intent → route field
2. graphiti_search — call GraphitiClient.search()
3. cypher_lookup   — direct Neo4j MATCH for entity names
4. direct          — pass-through (conversational, no retrieval)
5. context_assembly — join context facts into text
6. generate        — LLM answer generation
7. faithfulness    — lightweight score (real NLI wired later)

Edges
-----
router → graphiti_search | cypher_lookup | direct   (conditional)
graphiti_search → context_assembly
cypher_lookup   → context_assembly
direct          → context_assembly
context_assembly → generate
generate         → faithfulness
faithfulness     → END (score ≥ 0.6 or retries ≥ 2) | graphiti_search (retry)
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.chat_v2.state import ChatV2State
from app.core.logging import get_logger

logger = get_logger(__name__)

FAITHFULNESS_THRESHOLD = 0.6
MAX_RETRIES = 2

# --------------------------------------------------------------------------- #
# Keywords used by the router to classify intent                               #
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


def _classify_route(query: str) -> str:
    """Classify a query into one of three route strings.

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
        """Classify the user query and write the route field."""
        query: str = state.get("query", "")
        if not query:
            # Try to extract from last human message
            from langchain_core.messages import HumanMessage

            messages = state.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    query = str(msg.content)
                    break

        route = _classify_route(query)
        logger.info("chat_v2_router", query=query[:120], route=route)
        return {"route": route, "query": query, "original_query": query}

    # ------------------------------------------------------------------ #
    # Node 2: graphiti_search                                              #
    # ------------------------------------------------------------------ #

    async def graphiti_search(state: dict[str, Any]) -> dict[str, Any]:
        """Call GraphitiClient.search() and return raw context list."""
        query: str = state.get("query", "")
        saga_id: str = state.get("saga_id", "")

        logger.info("chat_v2_graphiti_search", query=query[:120], saga_id=saga_id)
        try:
            results: list[Any] = await graphiti.search(query=query, saga_id=saga_id)
        except Exception:
            logger.warning("chat_v2_graphiti_search_failed", exc_info=True)
            results = []

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
        query: str = state.get("query", "")

        # Extract hint: last word(s) after keywords like "list skills", "what class"
        q_lower = query.lower()
        query_hint = query  # default: use full query as hint

        cypher = (
            "MATCH (n:Entity {group_id: $saga_id}) "
            "WHERE toLower(n.name) CONTAINS toLower($query_hint) "
            "RETURN n.name AS name, n.summary AS summary, labels(n) AS labels "
            "LIMIT 20"
        )

        logger.info("chat_v2_cypher_lookup", saga_id=saga_id, query_hint=query_hint[:120])

        context: list[dict[str, Any]] = []
        try:
            async with neo4j_driver.session() as session:
                result = await session.run(
                    cypher,
                    saga_id=saga_id,
                    query_hint=query_hint,
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
                    lines.append(f"[{source} → {target}] {fact}")
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
        """Lightweight faithfulness check (real NLI wired later).

        Scoring rules:
        - If context is empty AND route is not "direct" → score 0.3
          (answer may be hallucinated — no grounding available)
        - Otherwise → score 0.8
          (context was present, assume acceptable grounding)
        """
        route: str = state.get("route", "graphiti_search")
        entity_summaries: list[dict[str, Any]] = state.get("entity_summaries", [])
        context_text = "\n".join(s.get("text", "") for s in entity_summaries).strip()

        if not context_text and route != "direct":
            score = 0.3
            reasoning = "No context retrieved for a non-direct query — possible hallucination."
        else:
            score = 0.8
            reasoning = "Context was available; answer assumed faithful."

        logger.info("chat_v2_faithfulness", score=score, route=route)
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

    # Faithfulness: pass → END, fail → retry via graphiti_search
    builder.add_conditional_edges(
        "faithfulness",
        _route_after_faithfulness,
        {END: END, "graphiti_search": "graphiti_search"},
    )

    return builder
