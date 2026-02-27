# MADIS: Multi-Agent Document Intelligence System (Agentic RAG)

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6F00)](https://www.langchain.com/langgraph)
[![VectorDB](https://img.shields.io/badge/VectorDB-Supabase_pgvector-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)

**MADIS** is a production-grade **Agentic RAG (Retrieval-Augmented Generation)** ecosystem designed to transform static PDF documents and web data into actionable, searchable intelligence. It leverages a sophisticated **Multi-Agent Orchestration** layer to handle complex reasoning, long-term memory, and real-time web discovery.

---

## 🚀 Key Technical Features (Job-Market Keywords)

- **Agentic Orchestration**: Built with **LangGraph**, utilizing **State Machines**, **Conditional Routing**, and **Parallel Fan-out/Fan-in** patterns for robust agent coordination.
- **Advanced RAG Pipeline**: Implementing **Semantic Search** with **Gemini Embeddings** and **Supabase pgvector** for high-performance long-term memory.
- **Multi-Tier Memory**:
  - **Short-term**: Persistent conversation state using **SQLite Checkpointers**.
  - **Long-term**: Vectorized document and web knowledge base.
- **Autonomous Web Discovery**: Integrated **crawl4AI** agent for real-time URL/Sitemap crawling and automated indexing.
- **Tool-Augmented Reasoning**: LLM access to a custom toolset including **Mathematical Calculators**, **Web Search**, and **External Knowledge APIs**.
- **Model Context Protocol (MCP)**: Custom **FastMCP Server** implementation, allowing external LLM hosts to interact with MADIS tools and memory.
- **Observability & Tracing**: Full execution transparency via **LangSmith** integration for debugging complex agent chains.
- **Modern UI/UX**: High-performance **React** frontend featuring a **Dark Glassmorphism** design, **Server-Sent Events (SSE)** for real-time streaming, and interactive **Agent Trace** visualizations.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **LLMs & AI** | Groq (Llama 3.3 70B), Google Gemini (Embeddings) |
| **Backend** | FastAPI, Python 3.10+, Uvicorn |
| **Agent Core** | LangGraph, LangChain, Pydantic AI |
| **Database** | Supabase (PostgreSQL + pgvector), SQLite (Local Persistence) |
| **Frontend** | React 18, Vite, Vanilla CSS (Glassmorphism), Lucide Icons |
| **Tools** | crawl4AI, FastMCP, DuckDuckGo Search |
| **Monitoring** | LangSmith |

---

## 🏗️ System Architecture

MADIS operates on a dual-graph architecture:
1.  **Analysis Sub-graph**: A one-shot pipeline that classifies, extracts, and generates insights from uploaded PDFs in parallel.
2.  **Chat Sub-graph**: A persistent loop allowing iterative tool usage, retrieval from vector memory, and human-like interaction.

---

## 🏁 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- Supabase Account (with pgvector enabled)

### Backend Setup
1. Navigate to `/backend`:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```
2. Configure `.env` with:
   - `GROQ_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `LANGCHAIN_API_KEY`
3. Run the server:
   ```bash
   python main.py
   ```

### Frontend Setup
1. Navigate to `/frontend`:
   ```bash
   npm install
   npm run dev
   ```

---

## 📊 Analytics & Monitoring
The system tracks token usage, agent latencies, and total costs, providing a business-centric view of AI operations. All agent logs are visible in the **Agent Trace** panel, making the "Black Box" of AI completely transparent.

---

## 📄 License
Created for technical portfolio demonstration. All rights reserved.
