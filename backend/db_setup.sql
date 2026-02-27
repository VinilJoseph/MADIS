-- ============================================================
-- Agentic RAG Chatbot — Supabase pgvector Schema
-- Run this in your Supabase project SQL editor
-- ============================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────
-- site_pages: stores all indexed content chunks
-- (PDF documents + crawled web pages)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS site_pages (
    id          BIGSERIAL PRIMARY KEY,
    url         VARCHAR   NOT NULL,
    chunk_number INTEGER  NOT NULL,
    title       VARCHAR   NOT NULL,
    summary     VARCHAR   NOT NULL,
    content     TEXT      NOT NULL,
    -- metadata includes: source ("pdf"|"web"), filename, thread_id, crawled_at
    metadata    JSONB     NOT NULL DEFAULT '{}'::JSONB,
    -- 768-dim Gemini text-embedding-004
    embedding   VECTOR(768),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (url, chunk_number)
);

-- Vector similarity search index (cosine distance)
CREATE INDEX IF NOT EXISTS site_pages_embedding_idx
    ON site_pages USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- JSONB metadata index for fast filtering by thread_id / source
CREATE INDEX IF NOT EXISTS site_pages_metadata_idx
    ON site_pages USING GIN (metadata);

-- ─────────────────────────────────────────────────────────────
-- match_site_pages RPC: vector similarity search function
-- Supports optional JSONB metadata filter (e.g. thread_id, source)
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION match_site_pages (
    query_embedding  VECTOR(768),
    match_count      INT     DEFAULT 5,
    filter           JSONB   DEFAULT '{}'::JSONB
)
RETURNS TABLE (
    id          BIGINT,
    url         VARCHAR,
    chunk_number INTEGER,
    title       VARCHAR,
    summary     VARCHAR,
    content     TEXT,
    metadata    JSONB,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
BEGIN
    RETURN QUERY
    SELECT
        sp.id,
        sp.url,
        sp.chunk_number,
        sp.title,
        sp.summary,
        sp.content,
        sp.metadata,
        1 - (sp.embedding <=> query_embedding) AS similarity
    FROM site_pages sp
    WHERE sp.metadata @> filter
    ORDER BY sp.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ─────────────────────────────────────────────────────────────
-- Row Level Security (for Supabase)
-- ─────────────────────────────────────────────────────────────
ALTER TABLE site_pages ENABLE ROW LEVEL SECURITY;

-- Allow public read (needed for anon key access)
CREATE POLICY "Allow public read"
    ON site_pages FOR SELECT TO public USING (true);

-- Allow service role to insert/update/delete
CREATE POLICY "Allow service role write"
    ON site_pages FOR ALL TO service_role USING (true);
