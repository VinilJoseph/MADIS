"""
main.py — FastAPI application entry point.

Endpoints:
  POST /ingest-pdf   — Upload PDF, chunk, embed, upsert Supabase, run analysis graph
  POST /chat         — RAG chat (streaming SSE)
  POST /crawl        — Crawl URL(s) and ingest to Supabase
  GET  /sessions     — List all chat thread IDs
  GET  /memory/{thread_id} — Short-term + long-term memory overview
  GET  /analytics/sessions — Recent analytics sessions
  GET  /analytics/summary  — Aggregate analytics stats
  /mcp               — FastMCP SSE endpoint
"""

from __future__ import annotations

import logging
import warnings
import sys
import io
# Suppress noisy deprecation warnings on startup
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*google.generativeai.*", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*chardet.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*RunnableConfig.*", category=UserWarning)

# Fix Windows console encoding — prevents 'charmap' errors when printing emoji (✅ ❌ etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")
import os
import uuid
import tempfile
import asyncio
from typing import AsyncGenerator, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.db import (
    init_db,
    save_analysis,
    save_analytics_session,
    get_analytics_sessions,
    get_analytics_summary,
)
from core.analytics import AnalyticsSession
from core.graph import analysis_graph, get_chat_graph
from core.memory import retrieve_all_threads, get_memory_overview
from core.pdf import extract_text_from_pdf, chunk_text
from core.vector_store import upsert_chunks, list_indexed_sources
from core.crawler import crawl_and_ingest_url, crawl_and_ingest_sitemap
from core.mcp_server import mcp
from core.state import AgentState

load_dotenv()

# ── LangSmith tracing ─────────────────────────────────────────────────────────
os.environ.setdefault("LANGCHAIN_TRACING_V2", os.getenv("LANGCHAIN_TRACING_V2", "false"))
os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "Agentic-RAG-Chatbot"))

# ── App setup ─────────────────────────────────────────────────────────────────
init_db()

app = FastAPI(
    title="Agentic RAG Chatbot",
    version="2.0",
    description="Multi-agent document intelligence with RAG, memory, MCP, and web crawling.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP server at /mcp (fastmcp 3.x uses http_app())
# app.mount("/mcp", mcp.http_app())


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class IngestPDFResponse(BaseModel):
    session_id: str
    thread_id: str
    filename: str
    chunks_indexed: int
    document_type: str
    summary: str
    key_sections: dict
    insights: List[str]
    agent_trace: List[str]
    analytics: Optional[dict] = None


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    session_id: Optional[str] = None


class CrawlRequest(BaseModel):
    url: str
    thread_id: str
    is_sitemap: bool = False
    max_pages: int = 30


class CrawlResponse(BaseModel):
    success: bool
    url: str
    thread_id: str
    pages_crawled: Optional[int] = None
    chunks_inserted: int
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# PDF Ingest
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/ingest-pdf", response_model=IngestPDFResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    thread_id: Optional[str] = Form(None),
):
    """
    Upload a PDF:
    1. Extract text
    2. Chunk + embed + upsert to Supabase (long-term memory)
    3. Run analysis graph (classify → extract ‖ summarize → insights)
    4. Save to SQLite analytics DB
    Returns full analysis + confirmation that RAG is ready.
    """
    logger.info("POST /ingest-pdf — filename=%s", file.filename)
    session_id = str(uuid.uuid4())
    t_id = thread_id or str(uuid.uuid4())

    analytics_session = AnalyticsSession(session_id)
    analytics_session.set_metadata(filename=file.filename)

    try:
        logger.debug("Reading file bytes for %s", file.filename)
        content = await file.read()
        raw_text = extract_text_from_pdf(content)

        if not raw_text:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from PDF. It may be empty or image-only.",
            )

        logger.debug("Extracted %d chars from PDF; chunking...", len(raw_text))
        text_chunks = chunk_text(raw_text)

        # ── Index into Supabase for long-term RAG ────────────────────────────
        chunks_inserted = await upsert_chunks(
            chunks=text_chunks,
            source_name=file.filename,
            source_type="pdf",
            thread_id=t_id,
            url=f"local://{file.filename}",
        )

        # ── Run analysis graph ────────────────────────────────────────────────
        initial_state: AgentState = {
            "messages": [],
            "thread_id": t_id,
            "session_id": session_id,
            "raw_text": raw_text,
            "chunks": text_chunks,
            "document_metadata": {
                "filename": file.filename,
                "text_length": len(raw_text),
                "chunk_count": len(text_chunks),
            },
            "document_type": None,
            "extracted_sections": {},
            "summary": None,
            "insights": [],
            "indexed_sources": [file.filename],
            "conversation_summary": None,
            "agent_logs": [f"System: Received '{file.filename}' ({len(raw_text):,} chars, {len(text_chunks)} chunks)"],
            "_token_tracker": analytics_session.token_tracker,
            "_agent_tracker": analytics_session.agent_tracker,
        }

        logger.info("Invoking analysis_graph for session=%s thread=%s", session_id, t_id)
        result_state = analysis_graph.invoke(initial_state)
        analytics_report = analytics_session.get_full_report()

        response_data = {
            "session_id": session_id,
            "thread_id": t_id,
            "filename": file.filename,
            "chunks_indexed": chunks_inserted,
            "document_type": result_state.get("document_type", "Unknown"),
            "summary": result_state.get("summary", ""),
            "key_sections": result_state.get("extracted_sections", {}),
            "insights": result_state.get("insights", []),
            "agent_trace": result_state.get("agent_logs", []),
            "analytics": analytics_report,
        }

        # Persist to SQLite
        logger.info("Saving analysis result for session=%s", session_id)
        save_analysis(file.filename, response_data, session_id)
        save_analytics_session(analytics_report)

        return IngestPDFResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled error in /ingest-pdf: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# RAG Chat (Streaming SSE)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Send a message to the RAG chat agent.
    Returns a Server-Sent Events stream of the response.
    Short-term memory:  SqliteSaver checkpointer (thread_id scoped)
    Long-term memory:   Retrieved from Supabase via rag_tool (called by LLM)
    """
    from langchain_core.messages import HumanMessage

    logger.info("POST /chat — thread_id=%s", req.thread_id)
    config = {
        "configurable": {"thread_id": req.thread_id},
        "run_name": "rag_chat",
        "tags": ["rag-chat"],
    }

    # Get current indexed sources for system prompt context
    sources = await list_indexed_sources(req.thread_id)
    source_names = [s.get("filename") or s.get("url", "") for s in sources]

    # Build initial input — checkpointer auto-replays all prior messages
    inp: dict = {
        "messages": [HumanMessage(content=req.message)],
        "thread_id": req.thread_id,
        "session_id": req.session_id or str(uuid.uuid4()),
        "indexed_sources": source_names,
        "agent_logs": [],
    }

    async def event_stream() -> AsyncGenerator[str, None]:
        logger.debug("Starting SSE event stream for thread_id=%s", req.thread_id)
        try:
            # Lazily initialise the async chat graph (AsyncSqliteSaver requires await)
            chat_graph = await get_chat_graph()
            # Use astream_events v2 for fine-grained streaming
            async for event in chat_graph.astream_events(inp, config=config, version="v2"):
                kind = event.get("event", "")

                # Stream LLM text tokens
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        if isinstance(content, str):
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                # Notify when a tool is invoked
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "tool")
                    inputs = event.get("data", {}).get("input", {})
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'input': str(inputs)[:200]})}\n\n"

                # Notify when tool finishes
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "tool")
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.exception("Error in chat event stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────────────────
# Web Crawler
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/crawl", response_model=CrawlResponse)
async def crawl(req: CrawlRequest):
    logger.info("POST /crawl — url=%s is_sitemap=%s", req.url, req.is_sitemap)
    """
    Crawl a URL (or sitemap) and ingest it into Supabase long-term memory.
    After crawling, the content is immediately available via rag_tool.
    """
    try:
        if req.is_sitemap:
            result = await crawl_and_ingest_sitemap(
                sitemap_url=req.url,
                thread_id=req.thread_id,
                max_pages=req.max_pages,
            )
            return CrawlResponse(
                success=result["success"],
                url=req.url,
                thread_id=req.thread_id,
                pages_crawled=result.get("pages_crawled", 0),
                chunks_inserted=result.get("chunks_inserted", 0),
                message=(
                    f"Crawled {result.get('pages_crawled', 0)} pages, "
                    f"indexed {result.get('chunks_inserted', 0)} chunks."
                    if result["success"]
                    else result.get("error", "Crawl failed")
                ),
            )
        else:
            result = await crawl_and_ingest_url(url=req.url, thread_id=req.thread_id)
            return CrawlResponse(
                success=result["success"],
                url=req.url,
                thread_id=req.thread_id,
                pages_crawled=1 if result["success"] else 0,
                chunks_inserted=result.get("chunks_inserted", 0),
                message=(
                    f"Indexed {result.get('chunks_inserted', 0)} chunks from {req.url}."
                    if result["success"]
                    else result.get("error", "Crawl failed")
                ),
            )
    except Exception as e:
        logger.exception("Unhandled error in /crawl: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Sessions & Memory
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/sessions")
async def get_sessions():
    """List all chat thread IDs with persisted state."""
    logger.info("GET /sessions")
    threads = await retrieve_all_threads()
    return {"sessions": threads, "count": len(threads)}


@app.get("/memory/{thread_id}")
async def get_memory(thread_id: str):
    logger.info("GET /memory/%s", thread_id)
    """
    Get combined memory overview for a thread:
    - short_term: recent conversation messages (from SqliteSaver)
    - long_term:  list of indexed sources (from Supabase)
    """
    return await get_memory_overview(thread_id)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics (kept from v1)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/analytics/sessions")
async def analytics_sessions(limit: int = 10):
    sessions = get_analytics_sessions(limit)
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "filename": s.filename,
                "start_timestamp": s.start_timestamp.isoformat() if s.start_timestamp else None,
                "total_tokens": s.total_tokens,
                "estimated_cost_usd": s.estimated_cost_usd,
                "total_duration_seconds": s.total_duration_seconds,
                "successful_agents": s.successful_agents,
                "failed_agents": s.failed_agents,
            }
            for s in sessions
        ]
    }


@app.get("/analytics/summary")
async def analytics_summary():
    return get_analytics_summary()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0"}


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
