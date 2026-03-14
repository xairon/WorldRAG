"""generate_cot node: chain-of-thought generation for analytical/timeline routes.

Standalone CoT generation node for use in the full 6-route topology (Task 18).
The current generate node already dispatches to CoT mode for these routes,
so this node is a thin wrapper for explicit graph routing in the rewired graph.
"""

from __future__ import annotations

from typing import Any

from app.agents.chat.nodes.generate import generate_answer


async def generate_cot(state: dict[str, Any]) -> dict[str, Any]:
    """Chain-of-thought generation for analytical and timeline routes.

    Delegates to generate_answer which uses GENERATOR_COT_SYSTEM for these routes.
    Kept as a separate node so the full 6-route graph can route directly to it
    without passing through the route-dispatch logic in generate_answer.
    """
    return await generate_answer(state)
