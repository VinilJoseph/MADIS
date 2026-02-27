import React, { useEffect, useState } from 'react';
import { MessageSquare, Plus, Clock, FileText, Trash2, RefreshCw } from 'lucide-react';

function timeAgo(iso) {
  // sessions don't store timestamps yet, so we skip for now
  return '';
}

export default function SessionSidebar({ activeThreadId, onSelectSession, onNewSession }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const res = await fetch('/sessions');
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      console.warn('[SessionSidebar] Failed to fetch sessions:', e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSessions(); }, [activeThreadId]);

  const shortId = (tid) => tid ? tid.slice(-8) : '—';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
          Sessions
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={fetchSessions}
            title="Refresh sessions"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 2, borderRadius: 4, display: 'flex', alignItems: 'center' }}
          >
            <RefreshCw size={11} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          </button>
          <button
            onClick={onNewSession}
            title="New session"
            style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', padding: 2, borderRadius: 4, display: 'flex', alignItems: 'center' }}
          >
            <Plus size={13} />
          </button>
        </div>
      </div>

      {/* Session cards */}
      {sessions.length === 0 && !loading && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '8px 0', textAlign: 'center' }}>
          No past sessions yet
        </div>
      )}

      {sessions.map((s) => {
        const isActive = s.thread_id === activeThreadId;
        const sourceName = s.sources?.[0] || null;
        return (
          <button
            key={s.thread_id}
            onClick={() => onSelectSession(s)}
            style={{
              background: isActive ? 'rgba(91,114,255,0.12)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${isActive ? 'rgba(91,114,255,0.4)' : 'rgba(255,255,255,0.06)'}`,
              borderRadius: 8,
              padding: '8px 10px',
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'all 0.15s ease',
              width: '100%',
            }}
            onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
            onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
          >
            {/* Source name */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
              {sourceName
                ? <FileText size={10} style={{ color: 'var(--accent-teal)', flexShrink: 0 }} />
                : <MessageSquare size={10} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              }
              <span style={{
                fontSize: 11, fontWeight: 600,
                color: isActive ? 'var(--accent-blue)' : 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140,
              }}>
                {sourceName ? sourceName.replace(/\.[^.]+$/, '') : `Thread …${shortId(s.thread_id)}`}
              </span>
            </div>

            {/* Preview */}
            {s.last_message_preview && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 3 }}>
                {s.last_message_preview}
              </div>
            )}

            {/* Stats */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'var(--text-muted)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <MessageSquare size={9} /> {s.message_count} msgs
              </span>
              {isActive && (
                <span style={{ color: 'var(--accent-teal)', fontWeight: 600, fontSize: 9, textTransform: 'uppercase' }}>active</span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
