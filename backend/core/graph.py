"""
graph.py — Two LangGraph compiled graphs:

1. analysis_graph  — one-shot PDF analysis (parallel fan-out)
   START → classifier → [extractor ‖ summarizer] → insight_generator → END

2. chat_graph      — persistent RAG chat loop
   START → chat_node → (conditional: tools? → tools → chat_node) → END
   Checkpointer: AsyncSqliteSaver (per thread_id, full message history)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("core.graph")

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from core.state import AgentState
from core.agents import (
    document_classifier_agent,
    content_extraction_agent,
    summarization_agent,
    insight_generator_agent,
    chat_node,
)
from core.tools import ALL_TOOLS
from core.memory import get_checkpointer


# ─────────────────────────────────────────────────────────────────────────────
# 1. PDF Analysis Graph (Parallel Fan-out)
# ─────────────────────────────────────────────────────────────────────────────
# Topology:
#   START → classifier → extractor  ─┐
#                      → summarizer  ─┤→ insight_generator → END
#
# extractor and summarizer run in parallel (both depend only on classifier output).
# insight_generator waits for both (LangGraph joins naturally when both edges arrive).

def create_analysis_graph() -> any:
    logger.info("Creating analysis_graph (PDF analysis pipeline)")
    g = StateGraph(AgentState)

    g.add_node("classifier", document_classifier_agent)
    g.add_node("extractor", content_extraction_agent)
    g.add_node("summarizer", summarization_agent)
    g.add_node("insight_generator", insight_generator_agent)

    # Entry point
    g.add_edge(START, "classifier")

    # Parallel fan-out after classification
    g.add_edge("classifier", "extractor")
    g.add_edge("classifier", "summarizer")

    # Both converge into insight generator
    g.add_edge("extractor", "insight_generator")
    g.add_edge("summarizer", "insight_generator")

    g.add_edge("insight_generator", END)

    compiled = g.compile()
    logger.info("analysis_graph compiled successfully")
    return compiled


# ─────────────────────────────────────────────────────────────────────────────
# 2. RAG Chat Graph (Persistent Loop, Lazy Async Init)
# ─────────────────────────────────────────────────────────────────────────────
# Topology:
#   START → chat_node → tools_condition:
#       - if tool_calls → tools → chat_node (loop)
#       - if no tool_calls → END
#
# The graph is NOT compiled at import time because the checkpointer
# (AsyncSqliteSaver) requires an async connection (aiosqlite.connect).
# Instead, get_chat_graph() is called on first /chat request.

_chat_graph: Optional[any] = None


async def get_chat_graph() -> any:
    """
    Return the compiled chat graph, initialising it on first call.
    Must be awaited because AsyncSqliteSaver requires an async DB connection.
    """
    global _chat_graph
    if _chat_graph is None:
        logger.info("Creating chat_graph (RAG chat loop)")
        g = StateGraph(AgentState)

        g.add_node("chat_node", chat_node)
        g.add_node("tools", ToolNode(ALL_TOOLS))

        g.add_edge(START, "chat_node")
        g.add_conditional_edges("chat_node", tools_condition)
        g.add_edge("tools", "chat_node")

        # AsyncSqliteSaver checkpointer — persists full message history per thread_id
        checkpointer = await get_checkpointer()
        _chat_graph = g.compile(checkpointer=checkpointer)
        logger.info("chat_graph compiled successfully with AsyncSqliteSaver checkpointer")

    return _chat_graph


# ── Analysis graph compiled once at import time (sync, no checkpointer) ───────
analysis_graph = create_analysis_graph()
