import React from 'react';
import { CheckCircle, XCircle, Cpu, Layers, BookOpen, Lightbulb, Settings } from 'lucide-react';

const NODE_META = {
  classifier:        { icon: '🔍', label: 'Classifier',       dotClass: 'classifier' },
  extractor:         { icon: '📋', label: 'Extractor',        dotClass: 'extractor' },
  summarizer:        { icon: '📖', label: 'Summarizer',       dotClass: 'summarizer' },
  insight_generator: { icon: '💡', label: 'Insight Generator',dotClass: 'insight' },
  default:           { icon: '⚙️', label: 'System',           dotClass: 'system' },
};

function parseLogEntry(log) {
  // Parse "✅ Classifier Agent: ..." or "❌ ..." into agent key + text
  if (log.startsWith('✅ Classifier') || log.includes('Classifier')) return { key: 'classifier', ok: !log.includes('❌') };
  if (log.startsWith('✅ Extractor') || log.includes('Extractor')) return { key: 'extractor', ok: !log.includes('❌') };
  if (log.startsWith('✅ Summariz') || log.includes('Summariz')) return { key: 'summarizer', ok: !log.includes('❌') };
  if (log.startsWith('✅ Insight') || log.includes('Insight')) return { key: 'insight_generator', ok: !log.includes('❌') };
  return { key: 'default', ok: !log.includes('❌') };
}

export default function AgentTrace({ logs = [], analytics }) {
  if (!logs || logs.length === 0) return (
    <div className="glass-card" style={{ padding: 28, textAlign: 'center' }}>
      <Cpu size={36} style={{ color: 'var(--text-muted)', margin: '0 auto 10px', opacity: 0.4 }} />
      <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No agent trace available yet.</p>
      <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>Upload a PDF to see the agent execution timeline.</p>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Analytics mini-stats */}
      {analytics && (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-value">{analytics.token_usage?.total_tokens?.toLocaleString?.() ?? '—'}</div>
            <div className="stat-label">Total tokens</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{analytics.total_duration_seconds?.toFixed?.(1) ?? '—'}s</div>
            <div className="stat-label">Duration</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ fontSize: 20 }}>
              {analytics.agent_execution?.successful_agents ?? '—'}/{analytics.agent_execution?.total_agents ?? '—'}
            </div>
            <div className="stat-label">Agents ok</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ fontSize: 18 }}>
              ${analytics.token_usage?.estimated_cost_usd?.toFixed?.(5) ?? '0.00000'}
            </div>
            <div className="stat-label">Est. cost</div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="glass-card" style={{ padding: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 18, display: 'flex', alignItems: 'center', gap: 7, color: 'var(--text-secondary)' }}>
          <Cpu size={15} /> Agent Execution Timeline
        </h3>
        <div className="trace-timeline">
          {logs.map((log, i) => {
            const { key, ok } = parseLogEntry(log);
            const meta = NODE_META[key] || NODE_META.default;
            return (
              <div key={i} className="trace-item">
                <div className={`trace-dot ${meta.dotClass}`}>
                  {ok
                    ? <CheckCircle size={12} />
                    : <XCircle size={12} style={{ color: 'var(--accent-red)' }} />
                  }
                </div>
                <div className="trace-body">
                  <div className="trace-label">{meta.icon} {meta.label}</div>
                  <div className="trace-text">{log.replace(/^[✅❌]\s*/, '')}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Raw JSON analytics accordion */}
      {analytics && (
        <details className="glass-card" style={{ padding: 20 }}>
          <summary style={{ cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 7 }}>
            <Settings size={13} /> Raw Analytics JSON
          </summary>
          <pre style={{ marginTop: 14, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', overflowX: 'auto', lineHeight: 1.6 }}>
            {JSON.stringify(analytics, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
