"""Node functions for the chat v2 pipeline.

All nodes are defined as closures inside build_chat_v2_graph()
to capture graphiti/neo4j_driver dependencies without globals.
"""

from __future__ import annotations
