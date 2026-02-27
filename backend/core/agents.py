"""
agents.py — All LangGraph node functions.

PDF Analysis pipeline (one-shot, fan-out parallel):
  classifier → [extractor ‖ summarizer] → insight_generator

RAG Chat pipeline (persistent loop):
  chat_node ↔ tools

All nodes decorated with @traceable for LangSmith tracing.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger("core.agents")

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langsmith import traceable

from core.state import AgentState
from core.tools import ALL_TOOLS

load_dotenv()

# ── LLM setup ─────────────────────────────────────────────────────────────────

def get_llm(streaming: bool = False):
    return ChatGroq(
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
        streaming=streaming,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PDF Analysis Agents (one-shot on ingest)
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="document_classifier", tags=["pdf-analysis", "classifier"])
def document_classifier_agent(state: AgentState) -> dict:
    """Classify the uploaded document type from a text sample."""
    logger.info("document_classifier_agent: starting")
    start = time.time()
    agent_tracker = state.get("_agent_tracker")
    if agent_tracker:
        agent_tracker.start_agent("classifier", state)

    llm = get_llm()
    text_sample = (state.get("raw_text") or "")[:3000]
    logger.debug("document_classifier_agent: text_sample length=%d", len(text_sample))

    prompt = ChatPromptTemplate.from_template(
        """You are an expert Document Classifier Agent.
Analyze the following text sample and classify its type.

Possible types: Contract, Research Paper, Technical Report, Field Notes, Legal Document, Invoice, Resume, Academic Paper, Manual, Other.

Text Sample:
{text}

Return ONLY a JSON object with the key "document_type".
Example: {{"document_type": "Research Paper"}}"""
    )

    chain = prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke({"text": text_sample})
        doc_type = result.get("document_type", "Unknown")
        logger.info("document_classifier_agent: identified doc_type='%s' in %.2fs", doc_type, time.time() - start)
        log = f"✅ Classifier: Identified as '{doc_type}'"
        success = True
    except Exception as e:
        doc_type = "Unknown"
        logger.exception("document_classifier_agent: failed — %s", e)
        log = f"❌ Classifier failed: {e}"
        success = False

    if agent_tracker:
        agent_tracker.end_agent({"document_type": doc_type}, success=success)

    return {
        "document_type": doc_type,
        "agent_logs": state.get("agent_logs", []) + [log],
    }


@traceable(name="content_extractor", tags=["pdf-analysis", "extractor"])
def content_extraction_agent(state: AgentState) -> dict:
    """Extract key sections from the document (runs in parallel with summarizer)."""
    logger.info("content_extraction_agent: starting")
    agent_tracker = state.get("_agent_tracker")
    if agent_tracker:
        agent_tracker.start_agent("extractor", state)

    llm = get_llm()
    doc_type = state.get("document_type", "Unknown")
    text = (state.get("raw_text") or "")[:10000]
    logger.debug("content_extraction_agent: doc_type='%s', text length=%d", doc_type, len(text))

    prompt = ChatPromptTemplate.from_template(
        """You are an expert Content Extraction Agent.
Document type: {doc_type}

Extract key sections appropriate for this document type:
- Contract: parties, clauses, obligations, deadlines, penalties
- Research Paper: abstract, methodology, findings, conclusions
- Technical Report: objectives, methodology, results, recommendations
- Manual: sections, procedures, warnings

Text:
{text}

Return JSON: {{"sections": {{"Section Name": "content summary", ...}}}}"""
    )

    chain = prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke({"doc_type": doc_type, "text": text})
        sections = result.get("sections", {})
        logger.info("content_extraction_agent: found %d sections", len(sections))
        log = f"✅ Extractor: Found {len(sections)} sections"
        success = True
    except Exception as e:
        sections = {}
        logger.exception("content_extraction_agent: failed — %s", e)
        log = f"❌ Extractor failed: {e}"
        success = False

    if agent_tracker:
        agent_tracker.end_agent({"extracted_sections": sections}, success=success)

    return {
        "extracted_sections": sections,
        "agent_logs": state.get("agent_logs", []) + [log],
    }


@traceable(name="summarizer", tags=["pdf-analysis", "summarizer"])
def summarization_agent(state: AgentState) -> dict:
    """Generate a comprehensive document summary (runs in parallel with extractor)."""
    logger.info("summarization_agent: starting")
    agent_tracker = state.get("_agent_tracker")
    if agent_tracker:
        agent_tracker.start_agent("summarizer", state)

    llm = get_llm()
    text = (state.get("raw_text") or "")[:15000]

    prompt = ChatPromptTemplate.from_template(
        """You are an expert Summarization Agent.
Provide a concise, comprehensive summary. Focus on: main objectives, key findings, stakeholders, and outcomes.

Document Text:
{text}

Return JSON: {{"summary": "one paragraph summary here"}}"""
    )

    chain = prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke({"text": text})
        summary = result.get("summary", "No summary generated.")
        if isinstance(summary, (dict, list)):
            summary = json.dumps(summary)
        logger.info("summarization_agent: summary generated (%d chars)", len(summary))
        log = "✅ Summarizer: Generated summary"
        success = True
    except Exception as e:
        summary = "Summary generation failed."
        logger.exception("summarization_agent: failed — %s", e)
        log = f"❌ Summarizer failed: {e}"
        success = False

    if agent_tracker:
        agent_tracker.end_agent({"summary": summary}, success=success)

    return {
        "summary": summary,
        "agent_logs": state.get("agent_logs", []) + [log],
    }


@traceable(name="insight_generator", tags=["pdf-analysis", "aggregator"])
def insight_generator_agent(state: AgentState) -> dict:
    """Aggregate analysis results and generate strategic insights."""
    logger.info("insight_generator_agent: starting")
    agent_tracker = state.get("_agent_tracker")
    if agent_tracker:
        agent_tracker.start_agent("insight_generator", state)

    llm = get_llm()
    summary = state.get("summary", "")
    sections = state.get("extracted_sections", {})
    doc_type = state.get("document_type", "Unknown")

    prompt = ChatPromptTemplate.from_template(
        """You are an expert Insight Generator Agent.
Based on the analysis below, generate strategic insights.

1. List 3 key questions the reader should investigate further.
2. Flag any risks, missing information, or red flags.
3. Recommend 3 follow-up actions.

Document Type: {doc_type}
Summary: {summary}
Key Sections: {sections}

Return JSON: {{"insights": ["insight 1", "insight 2", ...]}}"""
    )

    chain = prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke({
            "doc_type": doc_type,
            "summary": summary,
            "sections": json.dumps(sections),
        })
        insights = result.get("insights", [])
        logger.info("insight_generator_agent: produced %d insights", len(insights))
        log = f"✅ Insight Generator: Produced {len(insights)} insights"
        success = True
    except Exception as e:
        insights = []
        logger.exception("insight_generator_agent: failed — %s", e)
        log = f"❌ Insight Generator failed: {e}"
        success = False

    if agent_tracker:
        agent_tracker.end_agent({"insights": insights}, success=success)

    return {
        "insights": insights,
        "agent_logs": state.get("agent_logs", []) + [log],
    }


# ─────────────────────────────────────────────────────────────────────────────
# RAG Chat Agent (persistent loop with memory)
# ─────────────────────────────────────────────────────────────────────────────

llm_with_tools = get_llm(streaming=True).bind_tools(ALL_TOOLS)


@traceable(name="chat_node", tags=["rag-chat", "llm"])
async def chat_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    logger.info("chat_node: invoked (message count=%d)", len(state.get('messages', [])))
    """
    Primary RAG chat node.
    - Sees full short-term message history (via SqliteSaver checkpointer)
    - Has access to rag_tool, web_search, crawl_url, calculator, stock_price
    - Injects dynamic system prompt with available indexed sources
    """
    thread_id = None
    if config and isinstance(config, dict):
        thread_id = config.get("configurable", {}).get("thread_id")

    # Set thread_id in context var so rag_tool/crawl_url_tool can read it
    # without relying on the LLM to pass it as an argument
    from core.tools import _current_thread_id
    _current_thread_id.set(thread_id)
    logger.debug("chat_node: set _current_thread_id=%s", thread_id)

    # Build dynamic system prompt
    sources_info = ""
    indexed = state.get("indexed_sources") or []
    if indexed:
        sources_info = f"\n\nCurrently indexed sources for this session:\n" + "\n".join(
            f"  - {s}" for s in indexed
        )

    conv_summary = state.get("conversation_summary", "")
    summary_section = f"\n\nEarlier conversation summary:\n{conv_summary}" if conv_summary else ""

    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %H:%M UTC")

    system_prompt = (
        f"You are an intelligent document analysis and research assistant.\n"
        f"Today's date and time: {now_str}\n\n"
        "## Tools Available\n"
        "  • rag_tool — search uploaded PDFs and crawled web pages\n"
        "  • web_search_tool — live web search for current information\n"
        "  • crawl_url_tool — crawl a URL and add to knowledge base\n"
        "  • calculator — arithmetic operations\n"
        "  • get_stock_price — live stock quotes\n\n"
        "## Critical Rules (follow strictly)\n"
        "1. **Always call rag_tool first** for any question about uploaded documents.\n"
        "2. **Never hallucinate or guess.** If the retrieved chunks do not contain "
        "the requested information, respond with: "
        "'The document does not contain information about [topic].'\n"
        "3. **Use today's date** for any age, duration, or time calculations.\n"
        "4. **Be concise and factual.** Do not repeat yourself.\n"
        "5. **Cite the source** when quoting or summarizing document content.\n"
    )

    if indexed:
        system_prompt += "\n## Indexed Sources\n" + "\n".join(f"  - {s}" for s in indexed) + "\n"

    if conv_summary:
        system_prompt += f"\n## Earlier Conversation Summary\n{conv_summary}\n"

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

    logger.debug("chat_node: calling LLM with tools")
    response = await llm_with_tools.ainvoke(messages, config=config)
    logger.info("chat_node: LLM response received — tool_calls=%d", len(getattr(response, 'tool_calls', [])))
    return {"messages": [response]}
