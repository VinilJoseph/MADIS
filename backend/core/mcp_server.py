"""
mcp_server.py — FastMCP server exposing PDF analysis and memory tools.

Mounted on the main FastAPI app at /mcp.
External MCP clients (Claude Desktop, etc.) can connect and call these tools.
"""

from __future__ import annotations

import os
from typing import Optional

from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Agentic RAG Chatbot MCP Server")


@mcp.tool()
async def analyze_pdf_tool(session_id: str) -> dict:
    """
    Run or retrieve PDF analysis for a given session.
    Returns document_type, summary, key_sections, insights.
    """
    from core.db import get_analysis_by_session
    result = get_analysis_by_session(session_id)
    if not result:
        return {"error": f"No analysis found for session_id: {session_id}"}
    return result


@mcp.tool()
async def get_memory_tool(thread_id: str) -> dict:
    """
    Return the combined short-term (conversation history) and long-term
    (indexed source list) memory for a given thread.
    """
    from core.memory import get_memory_overview
    return get_memory_overview(thread_id)


@mcp.tool()
async def list_sources_tool(thread_id: str) -> dict:
    """
    List all documents and web pages indexed in long-term memory for a thread.
    """
    from core.vector_store import list_indexed_sources
    sources = await list_indexed_sources(thread_id)
    return {"thread_id": thread_id, "sources": sources}


@mcp.tool()
async def rag_search_tool(query: str, thread_id: Optional[str] = None) -> dict:
    """
    Perform a semantic search over indexed documents for a thread.
    Returns the top matching chunks with their source and similarity score.
    """
    from core.vector_store import similarity_search
    results = await similarity_search(query=query, thread_id=thread_id, k=5)
    return {"query": query, "results": results}
