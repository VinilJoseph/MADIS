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

@app.post("/ingest-pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    thread_id: Optional[str] = Form(None),
):
    """
    Upload a PDF and stream real-time progress via SSE.
    Events: extracting → embedding (N/M) → analyzing → done
    The final 'done' event carries the full analysis JSON.
    """
    logger.info("POST /ingest-pdf — filename=%s (SSE streaming)", file.filename)
    session_id = str(uuid.uuid4())
    t_id = thread_id or str(uuid.uuid4())
    content = await file.read()
    filename = file.filename

    async def progress_stream() -> AsyncGenerator[str, None]:
        def evt(obj: dict) -> str:
            return f"data: {json.dumps(obj)}\n\n"

        analytics_session = AnalyticsSession(session_id)
        analytics_session.set_metadata(filename=filename)

        try:
            # Stage 1: Extract text
            yield evt({"stage": "extracting", "message": "Extracting text from PDF..."})
            await asyncio.sleep(0)  # flush
            raw_text = extract_text_from_pdf(content)
            if not raw_text:
                yield evt({"stage": "error", "message": "Could not extract text. PDF may be empty or image-only."})
                return

            text_chunks = chunk_text(raw_text)
            total_chunks = len(text_chunks)
            logger.debug("Extracted %d chars, %d chunks", len(raw_text), total_chunks)
            yield evt({"stage": "extracted", "chars": len(raw_text), "chunks": total_chunks})
            await asyncio.sleep(0)

            # Stage 2: Embed + upsert chunks (emit progress per chunk)
            from core.vector_store import _ensure_supabase_connected, embed_text
            import asyncio as _asyncio

            sb = await _ensure_supabase_connected()
            inserted = 0

            for i, chunk in enumerate(text_chunks):
                yield evt({"stage": "embedding", "chunk": i + 1, "total": total_chunks,
                           "message": f"Embedding chunk {i+1}/{total_chunks}..."})
                await asyncio.sleep(0)

                if not chunk.strip() or sb is None:
                    continue
                embedding = await embed_text(chunk)
                if all(v == 0.0 for v in embedding):
                    logger.warning("Zero embedding for chunk %d — skipping upsert", i)
                    continue

                from datetime import datetime, timezone as _tz
                row = {
                    "url": f"local://{filename}",
                    "chunk_number": i,
                    "title": filename,
                    "summary": chunk[:200],
                    "content": chunk,
                    "metadata": {
                        "source": "pdf",
                        "filename": filename,
                        "thread_id": t_id,
                        "chunk_size": len(chunk),
                        "crawled_at": datetime.now(_tz.utc).isoformat(),
                    },
                    "embedding": embedding,
                }
                try:
                    await asyncio.to_thread(
                        lambda r=row: sb.table("site_pages").upsert(r, on_conflict="url,chunk_number").execute()
                    )
                    inserted += 1
                except Exception as ue:
                    logger.error("Upsert error chunk %d: %s", i, ue)

            yield evt({"stage": "embedded", "inserted": inserted, "total": total_chunks})
            await asyncio.sleep(0)

            # Stage 3: Analysis graph
            yield evt({"stage": "analyzing", "message": "Running AI analysis pipeline..."})
            await asyncio.sleep(0)

            initial_state: AgentState = {
                "messages": [],
                "thread_id": t_id,
                "session_id": session_id,
                "raw_text": raw_text,
                "chunks": text_chunks,
                "document_metadata": {
                    "filename": filename,
                    "text_length": len(raw_text),
                    "chunk_count": len(text_chunks),
                },
                "document_type": None,
                "extracted_sections": {},
                "summary": None,
                "insights": [],
                "indexed_sources": [filename],
                "conversation_summary": None,
                "agent_logs": [f"System: Received '{filename}' ({len(raw_text):,} chars, {len(text_chunks)} chunks)"],
                "_token_tracker": analytics_session.token_tracker,
                "_agent_tracker": analytics_session.agent_tracker,
            }

            result_state = await asyncio.to_thread(analysis_graph.invoke, initial_state)
            analytics_report = analytics_session.get_full_report()

            response_data = {
                "session_id": session_id,
                "thread_id": t_id,
                "filename": filename,
                "chunks_indexed": inserted,
                "document_type": result_state.get("document_type", "Unknown"),
                "summary": result_state.get("summary", ""),
                "key_sections": result_state.get("extracted_sections", {}),
                "insights": result_state.get("insights", []),
                "agent_trace": result_state.get("agent_logs", []),
                "analytics": analytics_report,
            }

            save_analysis(filename, response_data, session_id)
            save_analytics_session(analytics_report)

            # Stage 4: Done — send full result
            yield evt({"stage": "done", "data": response_data})

        except Exception as e:
            logger.exception("Error in /ingest-pdf SSE stream: %s", e)
            yield evt({"stage": "error", "message": str(e)})

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


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
            chat_graph = await get_chat_graph()

            from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

            # Track seen message IDs to avoid replaying history from checkpointer.
            # astream(stream_mode="messages") yields ALL messages in state, not just new ones.
            seen_ids: set = set()

            async for msg_chunk, metadata in chat_graph.astream(
                inp, config=config, stream_mode="messages"
            ):
                msg_id = getattr(msg_chunk, "id", None)
                if msg_id and msg_id in seen_ids:
                    continue   # skip replayed history messages
                if msg_id:
                    seen_ids.add(msg_id)

                # Only process messages from the chat_node (not tool results etc.)
                node_name = metadata.get("langgraph_node", "")

                if isinstance(msg_chunk, (AIMessage, AIMessageChunk)):
                    content = msg_chunk.content

                    # Collect tool calls on this message
                    tool_calls = (
                        getattr(msg_chunk, "tool_call_chunks", None) or
                        getattr(msg_chunk, "tool_calls", None) or []
                    )
                    has_tool_calls = bool(tool_calls)

                    # Notify frontend of any tool about to be called
                    for tc in tool_calls:
                        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        if name:
                            yield f"data: {json.dumps({'type': 'tool_start', 'tool': name, 'input': ''})}\n\n"

                    # Suppress text from messages that also have tool_calls.
                    # These are just LLM preamble ("I'll check the PDF...") that
                    # the LLM repeats in the final answer, causing duplicate text.
                    # Only the final AIMessage (tool_calls=[]) emits its text.
                    if not has_tool_calls:
                        if isinstance(content, str) and content.strip():
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                        elif isinstance(content, list):
                            text = "".join(
                                p.get("text", "") if isinstance(p, dict) else str(p)
                                for p in content
                            ).strip()
                            if text:
                                yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

                elif isinstance(msg_chunk, ToolMessage):
                    # Tool has finished — notify the frontend
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': msg_chunk.name or 'tool'})}\n\n"

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
    """List all chat sessions with metadata for the session switcher UI."""
    logger.info("GET /sessions")
    from core.memory import get_thread_messages
    from core.vector_store import list_indexed_sources
    threads = await retrieve_all_threads()

    sessions = []
    for tid in threads:
        msgs = await get_thread_messages(tid)
        # Find the last non-empty AI message for preview
        preview = ""
        timestamp = None
        for m in reversed(msgs):
            if m["role"] == "ai" and m["content"].strip():
                preview = m["content"][:80]
                break
        # Try to get indexed sources for this thread
        try:
            sources = await list_indexed_sources(tid)
        except Exception:
            sources = []
        sessions.append({
            "thread_id": tid,
            "message_count": len(msgs),
            "last_message_preview": preview,
            "sources": [s.get("filename", s.get("url", "")) for s in sources],
        })

    # Sort: sessions with most messages first
    sessions.sort(key=lambda s: s["message_count"], reverse=True)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/chat/history/{thread_id}")
async def get_chat_history(thread_id: str):
    """
    Return the full message history for a thread in chat-display format.
    Used by the frontend to hydrate messages after a page refresh.
    """
    logger.info("GET /chat/history/%s", thread_id)
    from core.memory import get_thread_messages
    from core.vector_store import list_indexed_sources

    msgs = await get_thread_messages(thread_id)
    try:
        sources = await list_indexed_sources(thread_id)
    except Exception:
        sources = []

    # Filter: only return messages that have actual text content
    displayable = [m for m in msgs if m.get("content", "").strip()]
    return {
        "thread_id": thread_id,
        "messages": displayable,
        "sources": [s.get("filename", s.get("url", "")) for s in sources],
        "message_count": len(displayable),
    }


@app.get("/memory/{thread_id}")
async def get_memory(thread_id: str):
    """Get combined memory overview (short-term SQLite + long-term Supabase)."""
    logger.info("GET /memory/%s", thread_id)
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
