# Agentic RAG Chatbot — Integration Implementation Plan

## Goal

Transform the existing `Agentic-AI-PDF-Analyzer` into a **production-quality, portfolio-showcase Agentic RAG Chatbot** that:

- Ingests & reasons over **PDF documents** (existing strength)
- Provides a **RAG-powered chat** interface with both **short-term** (conversation) and **long-term** (Supabase pgvector) memory
- Integrates **crawl4AI** as a live web-knowledge tool that can crawl any URL and add it to the knowledge base
- Exposes an **MCP server** that LLM hosts can call externally
- Traces every agent run through **LangSmith**
- Delivers a **stunning React frontend** with dark glassmorphism UI, live streaming, agent trace, and memory viewer
- Everything orchestrated by a **LangGraph state machine** using conditional routing, parallel fan-out, and checkpointed persistence

---

## User Review Required

> [!IMPORTANT]
> **Vector Database Choice**: The crawl4AI-agent uses **Supabase** (hosted Postgres + pgvector). You need a Supabase project with the `site_pages` table (SQL already in [crawl4AI-agent/site_pages.sql](file:///D:/Vinil/crawl4AI-agent/site_pages.sql)). The PDF RAG will also use Supabase (replacing in-memory FAISS for persistence). Make sure you have `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in your [.env](file:///D:/Vinil/crawl4AI-agent/.env).

> [!IMPORTANT]
> **LLM Choice**: The MemoryFlow used **Groq** (`moonshotai/kimi-k2-instruct-0905` / `llama-3.3-70b-versatile`) and the current backend uses **OpenRouter** (`google/gemini-2.0-flash-001`). The plan standardizes on **Groq** (free tier) for chat + **Gemini** for embeddings (free tier), keeping the option to switch via [.env](file:///D:/Vinil/crawl4AI-agent/.env). Confirm if you want a different LLM.

> [!IMPORTANT]
> **MCP Server Port**: The current [langgraph_mcp_backend.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langgraph_mcp_backend.py) connects to MCP at `http://localhost:8000/mcp`. The new backend main app will run on `8000` and expose `/mcp` via FastMCP mounted on the same app. No extra port needed.

> [!WARNING]
> **Breaking Change**: The existing `/analyze-pdf` endpoint will be replaced by two new endpoints: `/ingest-pdf` (builds vector index) and `/chat` (streaming RAG conversation). The old "one-shot analysis" flow becomes the initial analysis step inside the chat graph. All old API contracts change.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   React Frontend                          │
│  [PDF Upload] [RAG Chat + Stream] [Web Crawl] [Analytics]│
└────────────────────┬────────────────────────────────────┘
                     │ REST / SSE
┌────────────────────▼────────────────────────────────────┐
│              FastAPI (port 8000)                         │
│  POST /ingest-pdf  POST /chat  POST /crawl  GET /sessions│
│  GET  /memory/{thread_id}    /mcp (FastMCP SSE)          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│           LangGraph Agentic Core                         │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐    │
│  │ Classify │───▶│ Extract  │───▶│ Summarize+Insight│    │
│  └──────────┘    └──────────┘    └──────────────────┘    │
│        (one-time PDF analysis — fan-out parallel)         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │          RAG Chat Node (main loop)               │    │
│  │  LLM ↔ ToolNode (RAG | WebSearch | Crawl4AI |   │    │
│  │                    Calculator | MCP tools)        │    │
│  │  Checkpointer → SQLite (short-term memory)       │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Long-term Memory: Supabase pgvector                     │
│  (PDF chunks + crawled web pages, persisted per source)  │
└──────────────────────────────────────────────────────────┘
                     │
           LangSmith Tracing (@traceable)
```

---

## Proposed Changes

### Backend Core

#### [MODIFY] [state.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/state.py)
Expand [DocumentState](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/state.py#3-16) → new unified `AgentState`:
- `messages: Annotated[list[BaseMessage], add_messages]` — full message history
- `thread_id: str` — for checkpointing
- `document_metadata: dict` — filename, chunks count, etc.
- `analysis_result: dict` — one-time analysis (type, summary, sections, insights)
- `short_term_memory: list[str]` — recent conversation summaries (last N turns)
- `long_term_memory_sources: list[str]` — list of indexed sources (PDFs + crawled URLs)
- `agent_logs: list[str]` — execution trace
- `_token_tracker / _agent_tracker` — analytics (kept from existing)

---

#### [NEW] [backend/core/memory.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/memory.py)
Handles both memory tiers:
- **Short-term**: `SqliteSaver` checkpointer (from MemoryFlow's [langraph_rag_backend.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langraph_rag_backend.py)), stores full message history per `thread_id` in [chatbot.db](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/chatbot.db)
- **Long-term**: Supabase pgvector via `ingest_document(chunks, source, thread_id)` and `retrieve_from_memory(query, thread_id, k=5)` using Gemini embeddings (768-dim from crawl4AI agent pattern)
- Exposes `get_thread_memory_summary(thread_id)` for frontend memory viewer

---

#### [NEW] [backend/core/vector_store.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/vector_store.py)
Supabase pgvector client:
- `upsert_chunks(chunks: list[dict])` → inserts into `site_pages` table
- `similarity_search(query_embedding, filter, k)` → calls `match_site_pages` RPC
- Gemini `text-embedding-004` for all embeddings (consistent with crawl4AI pattern)

---

#### [MODIFY] [backend/core/tools.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/tools.py) *(currently toolless — new file)*
LangChain `@tool` definitions:
1. **[rag_tool(query, thread_id)](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langraph_rag_backend.py#151-174)** — queries Supabase pgvector for relevant chunks from PDFs + crawled pages indexed for this thread
2. **`web_search_tool(query)`** — DuckDuckGoSearchRun (from MemoryFlow)
3. **[calculator(first_num, second_num, operation)](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langraph_rag_backend.py#109-137)** — from MemoryFlow's RAG backend
4. **`crawl_url_tool(url, thread_id)`** — calls crawl4AI AsyncWebCrawler, chunks result, embeds, upserts to Supabase, returns summary
5. **[get_stock_price(symbol)](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langraph_rag_backend.py#140-149)** — from MemoryFlow (optional, shows tool diversity)

---

#### [MODIFY] [backend/core/agents.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/agents.py)
Refactor to:
- **[document_classifier_agent](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/agents.py#30-99)** — kept, uses `@traceable` decorator (from langsmith-workflow)
- **[content_extraction_agent](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/agents.py#101-179)** — runs in **parallel** with summarizer (fan-out pattern from langsmith-workflow [5_langgraph.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/langsmith-workflow/5_langgraph.py))
- **[summarization_agent](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/agents.py#181-257)** — parallel with extractor
- **[insight_generator_agent](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/agents.py#259-334)** — aggregation node after fan-out (like [final_evaluation](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/langsmith-workflow/5_langgraph.py#83-95) in langsmith-workflow)
- **[chat_node(state, config)](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langraph_rag_backend.py#189-208)** — primary RAG chat node. Uses `llm_with_tools.ainvoke()`. Same pattern as MemoryFlow [langgraph_mcp_backend.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langgraph_mcp_backend.py)'s [chat_node](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langraph_rag_backend.py#189-208). Injects system prompt with current thread context + available sources
- All nodes decorated with `@traceable` and tagged by function

---

#### [MODIFY] [backend/core/graph.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/graph.py)
Two sub-graphs compiled together:

**Analysis sub-graph** (one-shot, no loop):
```
START → classifier → [extractor ‖ summarizer] → insight_generator → END
```

**Chat graph** (persistent loop):
```
START → chat_node ↔ tools → (loop until no tool call) → END
Checkpointer: SqliteSaver (thread_id = session_id)
```

MCP tools loaded via `MultiServerMCPClient` (same as MemoryFlow [langgraph_mcp_backend.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langgraph_mcp_backend.py)) and merged with local tools.

---

#### [NEW] [backend/core/mcp_server.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/mcp_server.py)
FastMCP server exposing:
- `analyze_pdf_tool(session_id)` — runs analysis graph on already-ingested PDF
- `get_memory_tool(thread_id)` — returns thread memory summary
- `list_sources_tool(thread_id)` — lists all indexed sources

Mounted on FastAPI app at `/mcp` (same app, no extra port).

---

#### [NEW] [backend/core/crawler.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/crawler.py)
Adapted from [crawl4AI-agent/crawl_pydantic_ai_docs.py](file:///D:/Vinil/crawl4AI-agent/crawl_pydantic_ai_docs.py):
- `async crawl_and_ingest(url, thread_id)` — crawls URL → chunks → Gemini embed → Supabase upsert
- Used by `crawl_url_tool` and the new `/crawl` API endpoint
- Rate-limit retry logic (exponential backoff) preserved from original

---

#### [MODIFY] [backend/main.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/main.py)
New endpoints:
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest-pdf` | Upload PDF → extract text → chunk → embed → upsert Supabase → run analysis sub-graph → return analysis |
| POST | `/chat` | Send message → run chat graph with checkpointer → stream response via SSE |
| POST | `/crawl` | Submit URL → run crawl4AI → ingest to Supabase → return status |
| GET | `/sessions` | List all chat thread IDs |
| GET | `/memory/{thread_id}` | Get short + long-term memory summary for thread |
| GET | `/analytics/sessions` | Kept from existing |
| GET | `/analytics/summary` | Kept from existing |
| GET | `/mcp` | FastMCP SSE endpoint (MCP server) |

---

#### [MODIFY] [backend/requirements.txt](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/requirements.txt)
New dependencies added:
```
# Existing kept:
fastapi, uvicorn, python-multipart, pypdf, langchain, langgraph, sqlalchemy, pydantic, python-dotenv, httpx, openai

# New additions:
langchain-groq          # Groq LLM
langchain-community     # DuckDuckGo, FAISS fallback
langchain-huggingface   # HuggingFace embeddings fallback
langchain-mcp-adapters  # MCP client
langsmith               # Tracing
crawl4ai                # Web crawler
supabase                # Vector DB client
google-generativeai     # Gemini embeddings
aiosqlite               # Async SQLite checkpointer
mcp[cli]                # FastMCP server
fastmcp                 # MCP framework
```

---

#### [NEW] [backend/db_setup.sql](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/db_setup.sql)
Combined schema for Supabase:
- `site_pages` table (from crawl4AI-agent, for web crawled content)
- `document_knowledge` table (for PDF chunks, same schema but different `source` in metadata)
- `match_site_pages` RPC function with 768-dim Gemini vector search (updated from the 1536-dim OpenAI original)

---

### Frontend Rebuild

#### [MODIFY] [frontend/src/index.css](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/index.css)
Complete redesign:
- Dark glassmorphism theme (deep navy/purple bg, glass cards with `backdrop-filter`)
- CSS custom properties for color tokens
- Google Fonts: `Inter` (body) + `Space Grotesk` (headings)
- Smooth transitions, hover lift effects
- Scrollbar styling, animated gradient borders

#### [MODIFY] [frontend/src/App.jsx](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/App.jsx)
New layout:
- **Left Sidebar**: Navigation (PDF Analyzer, RAG Chat, Web Crawler, Analytics, Memory)
- **Main Area**: Routed content based on active nav item
- Global state: `sessionId`, `threadId`, `indexedSources`

#### [NEW] [frontend/src/components/ChatInterface.jsx](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/components/ChatInterface.jsx)
- Message bubbles (user/assistant) with markdown rendering
- **Streaming** via `EventSource` / SSE from `/chat`
- Tool call indicators (shows which tool was called with animated icon)
- Agent trace collapsible panel
- "Memory context" pill showing active sources

#### [NEW] [frontend/src/components/PDFUploader.jsx](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/components/PDFUploader.jsx)
- Drag-and-drop PDF upload
- Progress: uploading → extracting → embedding → analyzing
- Shows analysis results (document type, summary, key sections, insights) in collapsible cards
- "Start Chatting" CTA that switches to Chat tab with PDF source active

#### [NEW] [frontend/src/components/WebCrawler.jsx](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/components/WebCrawler.jsx)
- URL input with sitemap support
- Crawl progress: pages found → crawling → embedding → indexing
- List of indexed pages with status badges

#### [NEW] [frontend/src/components/AgentTrace.jsx](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/components/AgentTrace.jsx)
- Timeline visualization of agent node executions
- Color-coded by agent type
- Token count + duration per node

#### [NEW] [frontend/src/components/MemoryViewer.jsx](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/components/MemoryViewer.jsx)
- Short-term memory: last N conversation turns
- Long-term memory: indexed sources table (name, type, chunks, date)
- Session switcher

#### [MODIFY] [frontend/src/AnalyticsDashboard.jsx](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/frontend/src/AnalyticsDashboard.jsx)
- Keep existing token/agent analytics
- Add new panels: sessions over time, tool usage breakdown, crawled URLs count

---

## LangSmith Integration

All agent nodes in [agents.py](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/agents.py) will be wrapped with:
```python
from langsmith import traceable

@traceable(name="document_classifier", tags=["pdf-analysis", "classifier"])
def document_classifier_agent(state): ...
```

[.env](file:///D:/Vinil/crawl4AI-agent/.env) additions:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your_langsmith_key>
LANGCHAIN_PROJECT=Agentic-RAG-Chatbot
```

---

## Environment Variables ([.env](file:///D:/Vinil/crawl4AI-agent/.env) additions)

```env
# LLM (Groq — free tier)
GROQ_API_KEY=<your_groq_key>
LLM_MODEL=llama-3.3-70b-versatile

# Embeddings (Gemini — free tier)
GEMINI_API_KEY=<your_gemini_key>
GEMINI_EMBED_MODEL=models/text-embedding-004

# Vector DB (Supabase)
SUPABASE_URL=<your_supabase_url>
SUPABASE_SERVICE_KEY=<your_supabase_service_key>

# LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your_langsmith_key>
LANGCHAIN_PROJECT=Agentic-RAG-Chatbot

# Alpha Vantage (optional stock tool)
ALPHAVANTAGE_API_KEY=<optional>
```

---

## Verification Plan

### Automated / Semi-automated Tests

There are **no existing tests** in the project. The plan is to verify via API calls and browser UI.

#### 1. Backend API Tests (run with `uvicorn backend.main:app --reload`)

```powershell
# Test 1: PDF Ingest
curl -X POST http://localhost:8000/ingest-pdf -F "file=@test.pdf" -F "thread_id=test-thread-1"
# Expected: 200 OK with {document_type, summary, key_sections, insights, session_id}

# Test 2: RAG Chat (basic message)
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "What is this document about?", "thread_id": "test-thread-1"}'
# Expected: streaming SSE response with AI answer referencing PDF content

# Test 3: Web Crawl
curl -X POST http://localhost:8000/crawl `
  -H "Content-Type: application/json" `
  -d '{"url": "https://example.com", "thread_id": "test-thread-1"}'
# Expected: 200 OK with {pages_crawled, chunks_indexed, sources}

# Test 4: Memory retrieval
curl http://localhost:8000/memory/test-thread-1
# Expected: {short_term: [...messages], long_term_sources: [...]}

# Test 5: Sessions list
curl http://localhost:8000/sessions
# Expected: {sessions: [...thread_ids]}
```

#### 2. LangSmith Traces
After running the above tests, log into [smith.langchain.com](https://smith.langchain.com) and verify:
- Project `Agentic-RAG-Chatbot` exists
- Each API call creates a traced run with named nodes ([document_classifier](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/backend/core/agents.py#30-99), [chat_node](file:///D:/Vinil/Agentic-AI-PDF-Analyzer/MemoryFlow/langraph_rag_backend.py#189-208), etc.)

#### 3. MCP Server Test
```powershell
# Start backend, then use MCP inspector:
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
# Expected: MCP tools listed: analyze_pdf_tool, get_memory_tool, list_sources_tool
```

### Manual UI Verification (browser)

1. Start backend: `cd backend && python -m uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173`
4. **PDF Analyzer flow**: Drag a PDF → verify analysis cards appear with type/summary/insights
5. **Chat flow**: Click "Start Chatting" → ask "Summarize the key findings" → verify streaming response cites PDF
6. **Web Crawler flow**: Enter a URL → verify crawl progress and indexed pages list
7. **Memory Viewer**: Switch to Memory tab → verify short-term messages and long-term sources appear
8. **Analytics**: Switch to Analytics tab → verify session data, token counts
