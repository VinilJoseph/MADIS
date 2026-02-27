"""
memory.py — Short-term and long-term memory management.

Short-term:  SqliteSaver LangGraph checkpointer (full message history per thread).
Long-term:   Supabase pgvector (chunked documents, searchable via RAG).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger("core.memory")

from core.vector_store import list_indexed_sources

# ── AsyncSQLite checkpointer (short-term) ─────────────────────────────────────

DB_PATH = os.getenv("SQLITE_DB_PATH", "chatbot.db")

_checkpointer: Optional[AsyncSqliteSaver] = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """Return a singleton AsyncSqliteSaver checkpointer backed by aiosqlite."""
    global _checkpointer
    if _checkpointer is None:
        logger.info("Initializing AsyncSqliteSaver checkpointer at %s", DB_PATH)
        conn = await aiosqlite.connect(DB_PATH)
        _checkpointer = AsyncSqliteSaver(conn=conn)
    return _checkpointer


async def retrieve_all_threads() -> List[str]:
    """List all thread IDs that have checkpointed state."""
    logger.info("retrieve_all_threads: scanning all checkpoints")
    cp = await get_checkpointer()
    threads: set[str] = set()
    try:
        async for checkpoint in cp.alist(None):
            threads.add(checkpoint.config["configurable"]["thread_id"])
    except Exception:
        logger.warning("retrieve_all_threads: error listing checkpoints", exc_info=True)
    logger.debug("retrieve_all_threads: found %d threads", len(threads))
    return list(threads)


async def get_thread_messages(thread_id: str) -> List[Dict[str, Any]]:
    """
    Return simplified message history for a thread (for frontend memory viewer).
    Reads the latest checkpoint for the thread.
    """
    cp = await get_checkpointer()
    logger.debug("get_thread_messages: reading thread_id=%s", thread_id)
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await cp.aget(config)
        if not state or not state.channel_values:
            return []
        msgs: List[BaseMessage] = state.channel_values.get("messages", [])
        result = []
        for m in msgs:
            if isinstance(m, HumanMessage):
                result.append({"role": "human", "content": str(m.content)})
            elif isinstance(m, AIMessage):
                # Strip tool call noise for display
                content = m.content
                if isinstance(content, list):
                    content = " ".join(
                        p.get("text", "") for p in content if isinstance(p, dict)
                    )
                result.append({"role": "ai", "content": str(content)})
        return result
    except Exception as e:
        logger.exception("get_thread_messages error for thread %s: %s", thread_id, e)
        return []


def summarize_old_messages(messages: List[BaseMessage], keep_last: int = 10) -> tuple[str, List[BaseMessage]]:
    """
    Compress messages older than `keep_last` into a text summary.
    Returns (summary_text, recent_messages).
    Called by the graph when conversation grows long.
    """
    if len(messages) <= keep_last:
        return ("", messages)

    older = messages[:-keep_last]
    recent = messages[-keep_last:]

    summary_lines = []
    for m in older:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        content = m.content if isinstance(m.content, str) else str(m.content)
        summary_lines.append(f"{role}: {content[:200]}")

    summary = "Earlier conversation summary:\n" + "\n".join(summary_lines)
    return (summary, recent)


# ── Long-term memory helpers ──────────────────────────────────────────────────

async def get_memory_overview(thread_id: str) -> Dict[str, Any]:
    logger.info("get_memory_overview: thread_id=%s", thread_id)
    """
    Returns combined short-term + long-term memory info for a thread.
    Used by GET /memory/{thread_id} endpoint.
    """
    short_term = await get_thread_messages(thread_id)
    long_term_sources = await list_indexed_sources(thread_id)

    return {
        "thread_id": thread_id,
        "short_term": {
            "message_count": len(short_term),
            "messages": short_term[-20:],   # last 20 for display
        },
        "long_term": {
            "source_count": len(long_term_sources),
            "sources": long_term_sources,
        },
    }
