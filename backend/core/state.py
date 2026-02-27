import operator
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


def _keep_last(a: Any, b: Any) -> Any:
    """Reducer that always keeps the latest value (for parallel branches writing the same field)."""
    return b if b is not None else a


class AgentState(TypedDict):
    """
    Unified state shared across all agents in the LangGraph pipeline.

    Short-term memory  → full message history persisted via SqliteSaver checkpointer.
    Long-term memory   → document/web chunks stored in Supabase pgvector, retrieved by rag_tool.

    NOTE: Fields written by PARALLEL nodes (extractor + summarizer run concurrently) must
    use Annotated reducers, otherwise LangGraph raises INVALID_CONCURRENT_GRAPH_UPDATE.
      - agent_logs  → operator.add  (accumulate all log lines from both parallel nodes)
      - document_type, extracted_sections, summary, insights → _keep_last (only one branch writes each)
    """

    # ── Chat messages (accumulated, managed by add_messages reducer) ──────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Session / thread identity ─────────────────────────────────────────────
    thread_id: Optional[str]          # checkpointer key
    session_id: str                   # unique per API call

    # ── Document ingestion ────────────────────────────────────────────────────
    raw_text: Optional[str]           # full extracted PDF text
    chunks: Optional[List[str]]       # text chunks for embedding
    document_metadata: Optional[Dict[str, Any]]  # filename, page_count, chunk_count

    # ── One-shot PDF analysis results (set once per ingest) ──────────────────
    # These are written by different parallel nodes → use _keep_last so they don't conflict
    document_type: Annotated[Optional[str], _keep_last]
    extracted_sections: Annotated[Optional[Dict[str, Any]], _keep_last]
    summary: Annotated[Optional[str], _keep_last]
    insights: Annotated[Optional[List[str]], _keep_last]

    # ── Memory context ────────────────────────────────────────────────────────
    indexed_sources: Optional[List[str]]
    conversation_summary: Optional[str]

    # ── Execution trace ───────────────────────────────────────────────────────
    # operator.add accumulates log entries from all parallel nodes safely
    agent_logs: Annotated[List[str], operator.add]

    # ── Analytics (internal, not serialized to response) ─────────────────────
    _token_tracker: Any
    _agent_tracker: Any
