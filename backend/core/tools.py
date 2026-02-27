"""
tools.py — All LangChain @tool definitions for the RAG chat agent.

Tools available to the LLM:
 1. rag_tool          — semantic search over Supabase pgvector (PDFs + web)
 2. web_search_tool   — DuckDuckGo live search
 3. crawl_url_tool    — crawl a URL with crawl4AI, index it, return summary
 4. calculator        — basic arithmetic
 5. get_stock_price   — Alpha Vantage stock quote (optional)
"""

from __future__ import annotations

import contextvars
import logging
import os
from typing import Optional

logger = logging.getLogger("core.tools")

import requests
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from dotenv import load_dotenv

from core.vector_store import similarity_search, upsert_chunks

load_dotenv()

# ── Thread-id context (set by chat_node before LLM invocation) ──────────────
# This avoids relying on the LLM to pass thread_id as a tool argument.
_current_thread_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_thread_id", default=None
)

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")

# ── DuckDuckGo web search ─────────────────────────────────────────────────────
_ddg = DuckDuckGoSearchRun(region="us-en")


@tool
async def web_search_tool(query: str) -> str:
    """
    Search the web for up-to-date information using DuckDuckGo.
    Use for current events, recent news, or facts not in indexed documents.
    """
    import asyncio
    logger.info("web_search_tool: query=%r", query[:80])
    try:
        result = await asyncio.to_thread(_ddg.run, query)
        logger.debug("web_search_tool: returned %d chars", len(result))
        return result
    except Exception as e:
        logger.exception("web_search_tool: failed for query %r: %s", query[:80], e)
        return f"Web search failed: {e}"


# ── RAG retrieval from Supabase ───────────────────────────────────────────────

@tool
async def rag_tool(query: str) -> str:
    """
    Retrieve relevant information from indexed documents (PDFs and crawled web pages).
    Always call this first when a user asks about uploaded documents or any indexed content.
    """
    # Read thread_id from context (set by chat_node before LLM is called)
    thread_id = _current_thread_id.get()
    logger.info("rag_tool: query=%r thread_id=%s", query[:80], thread_id)

    results = await similarity_search(query=query, thread_id=thread_id, k=5)

    if not results:
        logger.warning("rag_tool: no results found for query=%r thread_id=%s", query[:80], thread_id)
        return "No relevant documents found. Make sure a PDF has been uploaded or a URL has been crawled."

    logger.info("rag_tool: returning %d results", len(results))

    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append(
            f"[Chunk {i}] Source: {r.get('title', 'Unknown')} | "
            f"Similarity: {r.get('similarity', 0):.2f}\n{r.get('content', '')}"
        )
    return "\n\n---\n\n".join(formatted)


# ── crawl4AI web ingestion ────────────────────────────────────────────────────

@tool
async def crawl_url_tool(url: str) -> str:
    """
    Crawl a web URL using crawl4AI, extract the content, and index it into the
    knowledge base so it can be retrieved via rag_tool.
    Returns a summary of what was indexed.
    Use this when the user wants to add a website to the knowledge base.
    """
    from core.crawler import crawl_and_ingest_url
    thread_id = _current_thread_id.get()
    logger.info("crawl_url_tool: url=%s thread_id=%s", url, thread_id)

    result = await crawl_and_ingest_url(url=url, thread_id=thread_id or "default")

    if result.get("success"):
        logger.info("crawl_url_tool: success url=%s chunks=%d", url, result['chunks_inserted'])
        return (
            f"Crawled and indexed: {url}\n"
            f"Chunks indexed: {result['chunks_inserted']}\n"
            f"Content preview: {result['preview']}"
        )
    logger.warning("crawl_url_tool: failed url=%s error=%s", url, result.get('error', 'Unknown error'))
    return f"Crawl failed for {url}: {result.get('error', 'Unknown error')}"


# ── Calculator ────────────────────────────────────────────────────────────────

@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform basic arithmetic: add, sub, mul, div.
    Use for any numerical calculations the user asks for.
    """
    logger.debug("calculator: %s %s %s", first_num, operation, second_num)
    try:
        ops = {
            "add": lambda a, b: a + b,
            "sub": lambda a, b: a - b,
            "mul": lambda a, b: a * b,
            "div": lambda a, b: a / b if b != 0 else None,
        }
        if operation not in ops:
            return {"error": f"Unsupported operation '{operation}'"}
        result = ops[operation](first_num, second_num)
        if result is None:
            return {"error": "Division by zero"}
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}


# ── Stock price (optional) ────────────────────────────────────────────────────

@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch the latest stock price for a ticker symbol (e.g. AAPL, TSLA).
    Requires ALPHAVANTAGE_API_KEY in .env.
    """
    logger.info("get_stock_price: symbol=%s", symbol)
    if not ALPHA_VANTAGE_API_KEY:
        return {"error": "ALPHAVANTAGE_API_KEY not configured"}
    try:
        url = (
            f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE"
            f"&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Tool registry ─────────────────────────────────────────────────────────────

ALL_TOOLS = [rag_tool, web_search_tool, crawl_url_tool, calculator, get_stock_price]
