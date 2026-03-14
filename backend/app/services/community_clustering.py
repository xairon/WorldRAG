"""Leiden community clustering for Graphiti Knowledge Graph.

Runs after Graphiti ingestion to detect communities via Neo4j GDS Leiden
algorithm, generate LLM summaries per community, and store results as
:Community nodes.

Usage:
    from app.services.community_clustering import run_community_clustering

    result = await run_community_clustering(neo4j_driver, saga_id="saga-001")
    # result = {"communities_found": 12, "saga_id": "saga-001"}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)


async def run_community_clustering(driver: AsyncDriver, saga_id: str) -> dict[str, Any]:
    """Run Leiden on Graphiti entities, generate LLM summaries, store as :Community nodes.

    Steps:
    1. Project in-memory graph via GDS (Entity nodes + RELATES_TO edges).
    2. Run Leiden algorithm — writes community_id property on each Entity node.
    3. Fetch communities with ≥2 members.
    4. For each community: call LLM to summarize, then MERGE a :Community node.
    5. Drop GDS projection.

    On any failure: attempt cleanup, return error dict (never raises).
    """
    try:
        async with driver.session() as session:
            # 1. Project graph via GDS
            await session.run("""
                CALL gds.graph.project('saga-community',
                    { Entity: { properties: ['group_id'] } },
                    { RELATES_TO: { orientation: 'UNDIRECTED' } }
                )
            """)

            # 2. Run Leiden
            await session.run("""
                CALL gds.leiden.write('saga-community', {
                    writeProperty: 'community_id',
                    includeIntermediateCommunities: false
                })
            """)

            # 3. Fetch communities (≥2 members)
            result = await session.run("""
                MATCH (n:Entity {group_id: $saga_id})
                WHERE n.community_id IS NOT NULL
                WITH n.community_id AS cid, collect(n.name) AS names, collect(n.summary) AS summaries
                WHERE size(names) >= 2
                RETURN cid AS community_id, names, summaries
                ORDER BY size(names) DESC
            """, saga_id=saga_id)
            communities = await result.data()

            # 4. Summarize + store each community
            for community in communities:
                summary = await _summarize_community(community["names"], community["summaries"])
                await session.run("""
                    MERGE (c:Community {community_id: $cid, saga_id: $saga_id})
                    SET c.summary = $summary, c.member_count = $count, c.members = $members
                """,
                    cid=community["community_id"],
                    saga_id=saga_id,
                    summary=summary,
                    count=len(community["names"]),
                    members=community["names"][:20],
                )

            # 5. Drop GDS projection
            await session.run("CALL gds.graph.drop('saga-community', false)")

            logger.info(
                "community_clustering_complete",
                saga_id=saga_id,
                communities_found=len(communities),
            )
            return {"communities_found": len(communities), "saga_id": saga_id}

    except Exception as e:
        logger.warning(
            "community_clustering_failed",
            saga_id=saga_id,
            error=str(e),
            exc_info=True,
        )
        # Best-effort cleanup: drop the projection if it was created
        try:
            async with driver.session() as session:
                await session.run("CALL gds.graph.drop('saga-community', false)")
        except Exception:
            pass
        return {"communities_found": 0, "saga_id": saga_id, "error": str(e)}


async def _summarize_community(names: list[str], summaries: list[str]) -> str:
    """Generate an LLM summary for a community of fiction entities.

    Falls back to a simple concatenation if the LLM call fails.
    """
    # Import inside function body to avoid circular imports at module load
    from app.config import settings
    from app.llm.providers import get_llm

    entities_text = "\n".join(
        f"- {n}: {s}" for n, s in zip(names, summaries) if s
    )
    prompt = f"Summarize this group of fiction entities in 2-3 sentences:\n\n{entities_text}"

    try:
        llm = get_llm(settings.llm_generation)
        response = await llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        logger.warning(
            "community_summary_llm_failed",
            entity_count=len(names),
            exc_info=True,
        )
        return f"Community of {len(names)} entities: {', '.join(names[:5])}"
