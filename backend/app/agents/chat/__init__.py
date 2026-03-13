"""Chat/RAG LangGraph agent.

Exports the compiled chat graph for use by ChatService and LangGraph Studio.
"""

from app.agents.chat.graph import build_chat_graph

__all__ = ["build_chat_graph"]
