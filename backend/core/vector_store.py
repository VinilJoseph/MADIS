"""
vector_store.py — Supabase pgvector client for long-term memory.

Stores chunked documents (PDFs and crawled web pages) with Gemini embeddings.
Uses the same `site_pages` table schema as crawl4AI-agent (site_pages.sql),
extended with thread_id in metadata for per-session filtering.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("core.vector_store")

import google.generativeai as genai
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# ── Gemini embeddings (768-dim, free tier) ────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")
EMBED_DIM = 768

# ── Supabase client ───────────────────────────────────────────────────────────
_supabase: Optional[Client] = None
_supabase_enabled: bool = False
_supabase_checked: bool = False   # Sentinel: once checked, don't retry


def _supabase_config_ok() -> bool:
    """Fast config validation — no network calls."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key or "your-project" in url:
        return False
    if key.startswith("sb_publishable_"):
        logger.warning("sb_publishable_ is the anon key. Use service_role (Secret) key.")
        return False
    return True


def get_supabase() -> Optional[Client]:
    """Return cached Supabase client, or None. Never makes network calls."""
    return _supabase if _supabase_enabled else None


async def _ensure_supabase_connected() -> Optional[Client]:
    """Async one-shot Supabase connection init. Runs network call in thread pool."""
    global _supabase, _supabase_enabled, _supabase_checked
    if _supabase_checked:
        return _supabase
    _supabase_checked = True

    if not _supabase_config_ok():
        logger.warning("Supabase not configured — vector storage disabled.")
        return None

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

    def _connect_sync():
        import socket as _s
        _s.setdefaulttimeout(6)
        client = create_client(url, key)
        # Quick ping to verify table exists
        client.table("site_pages").select("id").limit(0).execute()
        return client

    try:
        client = await asyncio.wait_for(
            asyncio.to_thread(_connect_sync),
            timeout=8.0
        )
        _supabase = client
        _supabase_enabled = True
        logger.info("Supabase connected OK → %s", url)
    except asyncio.TimeoutError:
        logger.warning("Supabase connection timed out (>8s) — vector storage disabled.")
    except Exception as e:
        msg = str(e)
        if "525" in msg or "ssl" in msg.lower() or "handshake" in msg.lower():
            logger.warning("Supabase SSL/525 error (project may be paused) — vector storage disabled.")
        else:
            logger.error("Supabase error: %s — vector storage disabled.", msg[:120])
    return _supabase



# ── Embedding helpers ─────────────────────────────────────────────────────────

async def embed_text(text: str, task_type: str = "retrieval_document") -> List[float]:
    """Get Gemini embedding, returns zero-vector on failure."""
    try:
        result = await asyncio.to_thread(
            genai.embed_content,
            model=GEMINI_EMBED_MODEL,
            content=text,
            task_type=task_type,
        )
        return result["embedding"]
    except Exception as e:
        logger.exception("Embedding error: %s", e)
        return [0.0] * EMBED_DIM


async def embed_query(text: str) -> List[float]:
    return await embed_text(text, task_type="retrieval_query")


# ── Upsert ────────────────────────────────────────────────────────────────────

async def upsert_chunks(
    chunks: List[str],
    source_name: str,
    source_type: str,
    thread_id: str,
    url: Optional[str] = None,
) -> int:
    """Embed and upsert chunks into Supabase. Returns 0 if Supabase unavailable."""
    logger.info("upsert_chunks: source='%s' type='%s' chunks=%d thread=%s", source_name, source_type, len(chunks), thread_id)
    sb = await _ensure_supabase_connected()
    if sb is None:
        logger.warning("Supabase unavailable — skipping upsert of %d chunks", len(chunks))
        return 0

    inserted = 0
    base_url = url or f"local://{source_name}"

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        embedding = await embed_text(chunk)
        if all(v == 0.0 for v in embedding):
            continue

        row = {
            "url": base_url,
            "chunk_number": i,
            "title": source_name,
            "summary": chunk[:200],
            "content": chunk,
            "metadata": {
                "source": source_type,
                "filename": source_name,
                "thread_id": thread_id,
                "chunk_size": len(chunk),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            },
            "embedding": embedding,
        }
        try:
            await asyncio.to_thread(
                lambda r=row: sb.table("site_pages").upsert(r, on_conflict="url,chunk_number").execute()
            )
            inserted += 1
        except Exception as e:
            logger.error("Upsert error on chunk %d: %s", i, e)
        await asyncio.sleep(0.2)

    logger.info("upsert_chunks: inserted %d/%d chunks", inserted, len(chunks))
    return inserted


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def similarity_search(
    query: str,
    thread_id: Optional[str] = None,
    k: int = 5,
    source_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Semantic search over indexed chunks. Returns [] if Supabase unavailable."""
    logger.info("similarity_search: query=%r thread_id=%s k=%d", query[:80], thread_id, k)
    sb = await _ensure_supabase_connected()
    if sb is None:
        logger.warning("similarity_search: Supabase unavailable, returning empty")
        return []
    query_embedding = await embed_query(query)

    meta_filter: Dict[str, Any] = {}
    if thread_id:
        meta_filter["thread_id"] = thread_id
    if source_type:
        meta_filter["source"] = source_type

    try:
        result = await asyncio.to_thread(
            lambda: sb.rpc(
                "match_site_pages",
                {"query_embedding": query_embedding, "match_count": k, "filter": meta_filter},
            ).execute()
        )
        return [
            {
                "title": row.get("title", ""),
                "content": row.get("content", ""),
                "url": row.get("url", ""),
                "similarity": row.get("similarity", 0.0),
            }
            for row in (result.data or [])
        ]
    except Exception as e:
        logger.exception("similarity_search error: %s", e)
        return []

# ── Source listing ────────────────────────────────────────────────────────────

async def list_indexed_sources(thread_id: str) -> List[Dict[str, Any]]:
    """Return all unique sources indexed for a given thread. Returns [] if Supabase not configured."""
    sb = await _ensure_supabase_connected()
    if sb is None:
        return []
    try:
        result = await asyncio.to_thread(
            lambda: sb.table("site_pages")
            .select("url, title, metadata, chunk_number")
            .execute()
        )
        sources: Dict[str, Dict] = {}
        for row in result.data or []:
            meta = row.get("metadata", {})
            if meta.get("thread_id") != thread_id:
                continue
            key = row["url"]
            if key not in sources:
                sources[key] = {
                    "url": key,
                    "title": row.get("title", key),
                    "source_type": meta.get("source", "unknown"),
                    "filename": meta.get("filename", ""),
                    "chunks": 0,
                    "indexed_at": meta.get("crawled_at", ""),
                }
            sources[key]["chunks"] += 1
        return list(sources.values())
    except Exception as e:
        logger.exception("list_indexed_sources error: %s", e)
        return []
