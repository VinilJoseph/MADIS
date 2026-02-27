import React, { useState, useEffect } from 'react';
import { Brain, MessageSquare, Database, RefreshCw, Loader2, FileText, Globe } from 'lucide-react';

export default function MemoryViewer({ threadId }) {
  const [memory, setMemory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchMemory = async () => {
    if (!threadId) return;
    console.log('[MemoryViewer] Fetching memory for thread_id=%s', threadId);
    setLoading(true); setError(null);
    try {
      const resp = await fetch(`/memory/${threadId}`);
      if (!resp.ok) throw new Error(resp.statusText);
      const data = await resp.json();
      console.log('[MemoryViewer] Memory fetched: short_term_msgs=%d long_term_sources=%d',
        data.short_term?.message_count ?? 0,
        data.long_term?.source_count ?? 0,
      );
      setMemory(data);
    } catch (e) {
      console.error('[MemoryViewer] Failed to fetch memory:', e.message);
      setError(e.message);
    }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchMemory(); }, [threadId]);

  if (!threadId) return (
    <div className="glass-card" style={{ padding: 40, textAlign: 'center' }}>
      <Brain size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 10px', opacity: 0.3 }} />
      <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No active session. Upload a PDF to create one.</p>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Thread: {threadId}</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={fetchMemory} disabled={loading}>
          {loading ? <Loader2 size={13} className="spinner" /> : <RefreshCw size={13} />} Refresh
        </button>
      </div>

      {error && <div className="badge badge-error" style={{ padding: '10px 14px', borderRadius: 8, fontSize: 13 }}>{error}</div>}

      {loading && !memory && (
        <div className="glass-card" style={{ padding: 32, textAlign: 'center' }}>
          <Loader2 size={28} className="spinner" style={{ color: 'var(--accent-blue)', margin: '0 auto' }} />
        </div>
      )}

      {memory && (
        <>
          {/* Short-term memory */}
          <div className="glass-card" style={{ padding: 22 }}>
            <div className="memory-header">
              <div style={{ padding: '6px 8px', borderRadius: 8, background: 'rgba(91,114,255,0.12)', border: '1px solid rgba(91,114,255,0.25)' }}>
                <MessageSquare size={14} style={{ color: 'var(--accent-blue)' }} />
              </div>
              Short-Term Memory
              <span className="badge badge-info" style={{ marginLeft: 'auto' }}>
                {memory.short_term?.message_count ?? 0} messages
              </span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14, lineHeight: 1.5 }}>
              Full conversation history stored via SQLite checkpointer. Automatically reloaded on each request.
            </p>
            {memory.short_term?.messages?.length > 0 ? (
              <div style={{ maxHeight: 320, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {memory.short_term.messages.map((m, i) => (
                  <div key={i} className={`memory-message ${m.role}`}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: m.role === 'human' ? 'var(--accent-blue)' : 'var(--accent-teal)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      {m.role === 'human' ? 'You' : 'AI'}
                    </span>
                    <p style={{ marginTop: 4, fontSize: 13, lineHeight: 1.6 }}>{m.content}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0' }}>No conversation history yet.</p>
            )}
          </div>

          {/* Long-term memory */}
          <div className="glass-card" style={{ padding: 22 }}>
            <div className="memory-header">
              <div style={{ padding: '6px 8px', borderRadius: 8, background: 'rgba(20,184,166,0.12)', border: '1px solid rgba(20,184,166,0.25)' }}>
                <Database size={14} style={{ color: 'var(--accent-teal)' }} />
              </div>
              Long-Term Memory (Supabase pgvector)
              <span className="badge badge-success" style={{ marginLeft: 'auto' }}>
                {memory.long_term?.source_count ?? 0} sources
              </span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14, lineHeight: 1.5 }}>
              Vectorized knowledge base — retrieved semantically by the RAG tool during chat.
            </p>
            {memory.long_term?.sources?.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {memory.long_term.sources.map((src, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', background: 'var(--bg-glass)', borderRadius: 8, border: '1px solid var(--border)' }}>
                    <div style={{ flexShrink: 0 }}>
                      {src.source_type === 'pdf'
                        ? <FileText size={16} style={{ color: 'var(--accent-amber)' }} />
                        : <Globe size={16} style={{ color: 'var(--accent-teal)' }} />
                      }
                    </div>
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                      <p style={{ fontWeight: 500, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{src.title || src.filename || src.url}</p>
                      <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{src.chunks} chunks · {src.indexed_at ? new Date(src.indexed_at).toLocaleString() : ''}</p>
                    </div>
                    <span className={`source-chip ${src.source_type}`}>{src.source_type}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0' }}>
                No documents indexed yet. Upload a PDF or crawl a URL.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
