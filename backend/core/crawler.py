"""
crawler.py — crawl4AI integration for on-demand web ingestion.

Adapted from crawl4AI-agent/crawl_pydantic_ai_docs.py:
 - Crawls a single URL or a full sitemap
 - Chunks the markdown content
 - Embeds with Gemini
 - Upserts to Supabase via vector_store
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from xml.etree import ElementTree

logger = logging.getLogger("core.crawler")

import requests
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from dotenv import load_dotenv

from core.vector_store import upsert_chunks

load_dotenv()

# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_markdown(text: str, chunk_size: int = 4000) -> List[str]:
    """Split markdown into semantically-aware chunks."""
    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = start + chunk_size
        if end >= length:
            chunks.append(text[start:].strip())
            break
        chunk = text[start:end]
        # Try to break at code block boundary
        code_pos = chunk.rfind("```")
        if code_pos != -1 and code_pos > chunk_size * 0.3:
            end = start + code_pos
        elif "\n\n" in chunk:
            last_break = chunk.rfind("\n\n")
            if last_break > chunk_size * 0.3:
                end = start + last_break
        elif ". " in chunk:
            last_period = chunk.rfind(". ")
            if last_period > chunk_size * 0.3:
                end = start + last_period + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(start + 1, end)

    return [c for c in chunks if c]


# ── Sitemap fetching ──────────────────────────────────────────────────────────

def fetch_sitemap_urls(sitemap_url: str) -> List[str]:
    """Recursively fetch all page URLs from a sitemap (or sitemap index)."""
    urls: List[str] = []
    try:
        resp = requests.get(sitemap_url, timeout=15)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        # Sitemap index
        submaps = root.findall(".//ns:sitemap/ns:loc", ns)
        if submaps:
            for sm in submaps:
                urls.extend(fetch_sitemap_urls(sm.text))
        else:
            urls = [loc.text for loc in root.findall(".//ns:url/ns:loc", ns)]
    except Exception as e:
        logger.exception("Sitemap fetch error for %s: %s", sitemap_url, e)
    return urls


# ── Core crawl + ingest ───────────────────────────────────────────────────────

async def crawl_and_ingest_url(url: str, thread_id: str) -> Dict[str, Any]:
    """
    Crawl a single URL, chunk its markdown content, and ingest into Supabase.
    Returns result summary dict.
    """
    logger.info("crawl_and_ingest_url: starting for url=%s thread=%s", url, thread_id)
    browser_cfg = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
    )
    crawl_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    try:
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            logger.debug("crawl_and_ingest_url: running crawler for %s", url)
            result = await crawler.arun(url=url, config=crawl_cfg)

        if not result.success:
            return {"success": False, "error": result.error_message or "Crawl failed"}

        markdown = result.markdown_v2.raw_markdown if result.markdown_v2 else result.markdown
        if not markdown:
            return {"success": False, "error": "No markdown content extracted"}

        chunks = chunk_markdown(markdown)
        if not chunks:
            return {"success": False, "error": "No content chunks generated"}

        domain = urlparse(url).netloc or url
        inserted = await upsert_chunks(
            chunks=chunks,
            source_name=domain,
            source_type="web",
            thread_id=thread_id,
            url=url,
        )

        logger.info("crawl_and_ingest_url: success url=%s total_chunks=%d inserted=%d", url, len(chunks), inserted)
        return {
            "success": True,
            "url": url,
            "total_chunks": len(chunks),
            "chunks_inserted": inserted,
            "preview": chunks[0][:300] if chunks else "",
        }

    except Exception as e:
        logger.exception("crawl_and_ingest_url: failed for %s: %s", url, e)
        return {"success": False, "error": str(e)}


async def crawl_and_ingest_sitemap(sitemap_url: str, thread_id: str, max_pages: int = 50) -> Dict[str, Any]:
    """
    Crawl all pages from a sitemap and ingest them.
    Returns aggregated result.
    """
    urls = fetch_sitemap_urls(sitemap_url)
    if not urls:
        return {"success": False, "error": "No URLs found in sitemap"}

    urls = urls[:max_pages]  # safety cap
    logger.info("crawl_and_ingest_sitemap: found %d URLs, crawling up to %d", len(urls), max_pages)

    browser_cfg = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
    )
    crawl_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    total_inserted = 0
    crawled_pages: List[str] = []
    failed_pages: List[str] = []
    semaphore = asyncio.Semaphore(3)  # max 3 concurrent crawls

    async def process_url(url: str):
        nonlocal total_inserted
        async with semaphore:
            try:
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(url=url, config=crawl_cfg)
                if not result.success:
                    failed_pages.append(url)
                    return
                markdown = result.markdown_v2.raw_markdown if result.markdown_v2 else result.markdown
                if not markdown:
                    failed_pages.append(url)
                    return
                chunks = chunk_markdown(markdown)
                domain = urlparse(url).netloc or url
                inserted = await upsert_chunks(
                    chunks=chunks,
                    source_name=domain,
                    source_type="web",
                    thread_id=thread_id,
                    url=url,
                )
                total_inserted += inserted
                crawled_pages.append(url)
            except Exception as e:
                logger.exception("crawl_and_ingest_sitemap: error processing %s: %s", url, e)
                failed_pages.append(url)

    await asyncio.gather(*[process_url(u) for u in urls])

    return {
        "success": True,
        "sitemap_url": sitemap_url,
        "pages_found": len(urls),
        "pages_crawled": len(crawled_pages),
        "pages_failed": len(failed_pages),
        "chunks_inserted": total_inserted,
        "crawled_urls": crawled_pages,
        "failed_urls": failed_pages,
    }
