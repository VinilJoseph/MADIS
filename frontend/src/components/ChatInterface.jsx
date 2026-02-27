import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Bot, User, Zap, Globe, Database, Calculator, TrendingUp, ChevronDown, ChevronUp } from 'lucide-react';

const TOOL_META = {
  rag_tool: { icon: Database, label: 'RAG Search', color: '#5b72ff' },
  web_search_tool: { icon: Globe, label: 'Web Search', color: '#14b8a6' },
  crawl_url_tool: { icon: Globe, label: 'Web Crawl', color: '#8b5cf6' },
  calculator: { icon: Calculator, label: 'Calculate', color: '#f59e0b' },
  get_stock_price: { icon: TrendingUp, label: 'Stock Price', color: '#f472b6' },
};

function ToolIndicator({ tool, active, input }) {
  const meta = TOOL_META[tool] || { icon: Zap, label: tool, color: '#8892b0' };
  const Icon = meta.icon;
  return (
    <div className={`tool-indicator${active ? ' active' : ''}`} style={{ borderColor: active ? meta.color + '60' : undefined, color: active ? meta.color : undefined }}>
      <Icon size={11} />
      <span>{meta.label}</span>
      {input && <span style={{ opacity: 0.6, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>— {input}</span>}
      {active && <span className="pulse-dot" style={{ background: meta.color }} />}
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  const [showRaw, setShowRaw] = useState(false);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start', gap: 6 }}>
      {/* Role label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
        {isUser ? <User size={12} /> : <Bot size={12} />}
        {isUser ? 'You' : 'Assistant'}
      </div>

      {/* Tool calls before bubble */}
      {msg.toolCalls?.map((tc, i) => (
        <ToolIndicator key={i} tool={tc.tool} active={false} input={tc.input} />
      ))}

      {/* Bubble */}
      {msg.content && (
        <div className={`message-bubble ${isUser ? 'user' : 'ai'}`}>
          <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
        </div>
      )}
    </div>
  );
}

function StreamingBubble({ content, activeTool, activeInput }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
        <Bot size={12} /> Assistant
        <span className="pulse-dot" />
      </div>
      {activeTool && <ToolIndicator tool={activeTool} active={true} input={activeInput} />}
      {content && (
        <div className="message-bubble ai">
          <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
          <span style={{ display: 'inline-block', width: 2, height: 14, background: 'var(--accent-blue)', marginLeft: 2, animation: 'pulse 0.8s infinite', verticalAlign: 'middle' }} />
        </div>
      )}
      {!content && !activeTool && (
        <div className="message-bubble ai" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Loader2 size={14} className="spinner" style={{ color: 'var(--accent-blue)' }} />
          <span style={{ color: 'var(--text-muted)' }}>Thinking...</span>
        </div>
      )}
    </div>
  );
}

export default function ChatInterface({ threadId, sessionId, indexedSources = [], initialMessages = null, onMessageCountChange, sessionSidebar }) {
  const [messages, setMessages] = useState(initialMessages || []);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState('');
  const [activeTool, setActiveTool] = useState(null);
  const [activeInput, setActiveInput] = useState('');
  const [pendingToolCalls, setPendingToolCalls] = useState([]);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  // Hydrate messages when session is restored from localStorage or user switches sessions
  useEffect(() => {
    if (initialMessages) {
      setMessages(initialMessages);
      onMessageCountChange?.(initialMessages.filter(m => m.role === 'user').length);
    }
  }, [initialMessages]);

  // Reset chat when threadId changes (new session or session switch)
  useEffect(() => {
    if (!initialMessages) {
      setMessages([]);
      onMessageCountChange?.(0);
    }
    setStreamContent('');
    setActiveTool(null);
  }, [threadId]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming || !threadId) return;

    setInput('');
    setIsStreaming(true);
    setStreamContent('');
    setActiveTool(null);
    setPendingToolCalls([]);

    const userMsg = { role: 'user', content: text, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    console.log('[ChatInterface] sendMessage: thread_id=%s msg=%r', threadId, text.slice(0, 60));

    let fullContent = '';
    let toolCallsForMsg = [];

    try {
      const resp = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId, session_id: sessionId }),
      });

      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let streamDone = false;

      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'token') {
              fullContent += data.content;
              setStreamContent(fullContent);
              setActiveTool(null);
            } else if (data.type === 'tool_start') {
              console.log('[ChatInterface] tool_start: tool=%s input=%s', data.tool, String(data.input || '').slice(0, 60));
              setActiveTool(data.tool);
              setActiveInput(data.input || '');
              toolCallsForMsg = [...toolCallsForMsg, { tool: data.tool, input: data.input }];
              setPendingToolCalls(toolCallsForMsg);
            } else if (data.type === 'tool_end') {
              console.log('[ChatInterface] tool_end: tool=%s', data.tool);
              setActiveTool(null);
            } else if (data.type === 'done') {
              console.log('[ChatInterface] stream done. total chars=%d tool_calls=%d', fullContent.length, toolCallsForMsg.length);
              streamDone = true;
              break;
            } else if (data.type === 'error') {
              console.error('[ChatInterface] server error:', data.message);
              fullContent = `Error: ${data.message}`;
              setStreamContent(fullContent);
              streamDone = true;
              break;
            }
          } catch { }
        }
      }
    } catch (err) {
      console.error('[ChatInterface] Network error:', err.message);
      fullContent = `Network error: ${err.message}`;
      setStreamContent(fullContent);
    }

    setMessages(prev => {
      const updated = [...prev, { role: 'ai', content: fullContent, toolCalls: toolCallsForMsg, id: Date.now() }];
      onMessageCountChange?.(updated.filter(m => m.role === 'user').length);
      return updated;
    });
    setIsStreaming(false);
    setStreamContent('');
    setActiveTool(null);
  }, [input, isStreaming, threadId, sessionId]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const hasThread = !!threadId;
  const placeholderText = !hasThread
    ? 'Upload a PDF first to start chatting...'
    : 'Ask anything about your documents... (Shift+Enter for new line)';

  return (
    <div style={{ height: '100%', display: 'flex', gap: 0, overflow: 'hidden' }}>

      {/* Session sidebar panel */}
      {sessionSidebar && (
        <div style={{ width: 200, minWidth: 180, borderRight: '1px solid var(--border)', padding: '16px 12px', overflowY: 'auto', flexShrink: 0 }}>
          {sessionSidebar}
        </div>
      )}

      {/* Main chat column */}
      <div className="chat-container" style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Source pills */}
        {indexedSources.length > 0 && (
          <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 4 }}>Indexed:</span>
            {indexedSources.map((s, i) => (
              <span key={i} className={`source-chip ${s.type || 'pdf'}`}>{s.name || s}</span>
            ))}
          </div>
        )}

        {/* Messages */}
        <div className="chat-messages">
          {messages.length === 0 && !isStreaming && (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
              <Bot size={48} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
              <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-secondary)' }}>
                {hasThread ? 'Ask me anything about your documents' : 'Upload a PDF to get started'}
              </p>
              <p style={{ fontSize: 13, marginTop: 6 }}>
                I can search your documents, browse the web, crawl URLs, and more.
              </p>
            </div>
          )}

          {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
          {isStreaming && (
            <StreamingBubble content={streamContent} activeTool={activeTool} activeInput={activeInput} />
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="chat-input-area">
          <textarea
            ref={textareaRef}
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholderText}
            disabled={isStreaming || !hasThread}
            rows={1}
            style={{ height: 'auto' }}
            onInput={e => {
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
            }}
          />
          <button
            className="btn btn-primary"
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming || !hasThread}
            style={{ height: 48, width: 48, padding: 0, justifyContent: 'center' }}
          >
            {isStreaming
              ? <Loader2 size={18} className="spinner" />
              : <Send size={18} />
            }
          </button>
        </div>
      </div>
    </div>
  );
}
