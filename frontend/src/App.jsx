import React, { useState, useEffect } from 'react';
import {
  Brain, FileText, MessageSquare, Globe, Activity, Database,
  BarChart2, ChevronRight, Sparkles, Cpu, Server
} from 'lucide-react';

import PDFUploader from './components/PDFUploader';
import ChatInterface from './components/ChatInterface';
import WebCrawler from './components/WebCrawler';
import AgentTrace from './components/AgentTrace';
import MemoryViewer from './components/MemoryViewer';

// ── Page metadata ─────────────────────────────────────────────────────────────
const PAGES = [
  {
    id: 'pdf',
    label: 'PDF Analyzer',
    icon: FileText,
    title: 'PDF Analyzer',
    subtitle: 'Upload and analyze documents with multi-agent AI',
  },
  {
    id: 'chat',
    label: 'RAG Chat',
    icon: MessageSquare,
    title: 'RAG Chat',
    subtitle: 'Ask questions — powered by short + long-term memory',
  },
  {
    id: 'crawler',
    label: 'Web Crawler',
    icon: Globe,
    title: 'Web Crawler',
    subtitle: 'Crawl any URL and add it to your knowledge base',
  },
  {
    id: 'memory',
    label: 'Memory',
    icon: Database,
    title: 'Memory Viewer',
    subtitle: 'Inspect short-term (SQLite) and long-term (Supabase) memory',
  },
  {
    id: 'trace',
    label: 'Agent Trace',
    icon: Cpu,
    title: 'Agent Trace',
    subtitle: 'Live LangGraph execution timeline and analytics',
  },
];

function Sidebar({ activePage, onNavigate, indexedCount, messageCount }) {
  return (
    <nav className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Brain size={20} color="white" />
        </div>
        <div>
          <div className="sidebar-logo-text">RAG Agent</div>
          <div className="sidebar-logo-sub">Agentic AI Platform</div>
        </div>
      </div>

      <div className="nav-section-label">Core</div>

      {PAGES.map(p => {
        const Icon = p.icon;
        const badge =
          p.id === 'memory' && indexedCount > 0 ? indexedCount :
          p.id === 'chat'   && messageCount > 0  ? messageCount :
          null;
        return (
          <button
            key={p.id}
            className={`nav-item${activePage === p.id ? ' active' : ''}`}
            onClick={() => onNavigate(p.id)}
          >
            <Icon className="nav-icon" size={17} />
            {p.label}
            {badge != null && <span className="nav-badge">{badge}</span>}
          </button>
        );
      })}

      {/* Footer */}
      <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border)' }}>
        <div style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Server size={11} /> <span>LangGraph + MCP</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Database size={11} /> <span>Supabase pgvector</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Activity size={11} /> <span>LangSmith tracing</span>
          </div>
        </div>
      </div>
    </nav>
  );
}

// ── Welcome overlay (first load) ─────────────────────────────────────────────

function WelcomeBanner({ onStart }) {
  const features = [
    { icon: FileText,     color: '#f59e0b', label: 'PDF Analysis',    desc: 'Multi-agent parallel analysis' },
    { icon: MessageSquare,color: '#5b72ff', label: 'RAG Chat',         desc: 'Short + long-term memory' },
    { icon: Globe,        color: '#14b8a6', label: 'Web Crawling',     desc: 'crawl4AI + Supabase pgvector' },
    { icon: Cpu,          color: '#8b5cf6', label: 'LangGraph',        desc: 'Agentic orchestration' },
    { icon: Activity,     color: '#f472b6', label: 'LangSmith',        desc: 'Full trace observability' },
    { icon: Server,       color: '#10b981', label: 'MCP Server',       desc: 'External tool integration' },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40, textAlign: 'center' }}>
      {/* Glow ring */}
      <div style={{ position: 'relative', marginBottom: 32 }}>
        <div style={{ width: 80, height: 80, borderRadius: '50%', background: 'var(--gradient-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 60px rgba(91,114,255,0.4)', animation: 'glow-pulse 3s ease-in-out infinite' }}>
          <Brain size={36} color="white" />
        </div>
      </div>

      <h1 style={{ fontFamily: 'var(--font-head)', fontSize: 34, fontWeight: 700, marginBottom: 12, background: 'linear-gradient(135deg, #e8eaf6 0%, var(--accent-blue) 60%, var(--accent-purple) 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
        Agentic RAG Chatbot
      </h1>
      <p style={{ fontSize: 16, color: 'var(--text-secondary)', maxWidth: 520, lineHeight: 1.7, marginBottom: 40 }}>
        A full-stack AI platform combining LangGraph agents, RAG, multi-tier memory,
        web crawling, and MCP — built to showcase production-grade agentic AI.
      </p>

      {/* Feature grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, maxWidth: 580, marginBottom: 40 }}>
        {features.map((f, i) => {
          const Icon = f.icon;
          return (
            <div key={i} className="glass-card" style={{ padding: '16px 14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, animation: `fadeInUp 0.4s ease ${i * 0.06}s both` }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: `${f.color}22`, border: `1px solid ${f.color}44`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Icon size={17} style={{ color: f.color }} />
              </div>
              <div style={{ fontWeight: 600, fontSize: 12.5 }}>{f.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>{f.desc}</div>
            </div>
          );
        })}
      </div>

      <button className="btn btn-primary" onClick={onStart} style={{ padding: '14px 32px', fontSize: 15 }}>
        <Sparkles size={17} /> Get Started — Upload a PDF
      </button>
    </div>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [activePage, setActivePage] = useState('welcome');
  const [threadId, setThreadId] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [indexedSources, setIndexedSources] = useState([]);  // [{name, type}]
  const [lastTrace, setLastTrace] = useState({ logs: [], analytics: null });
  const [messageCount, setMessageCount] = useState(0);

  // Called by PDFUploader when analysis is complete
  const handleAnalysisComplete = (data) => {
    console.log('[App] handleAnalysisComplete: thread_id=%s session_id=%s filename=%s', data.thread_id, data.session_id, data.filename);
    setThreadId(data.thread_id);
    setSessionId(data.session_id);
    setIndexedSources(prev => [
      ...prev,
      { name: data.filename, type: 'pdf' }
    ]);
    setLastTrace({ logs: data.agent_trace || [], analytics: data.analytics });
  };

  // Called by WebCrawler when crawl is complete
  const handleCrawlComplete = (src) => {
    console.log('[App] handleCrawlComplete: source=%o', src);
    setIndexedSources(prev => [...prev, src]);
  };

  const onNavigate = (pageId) => {
    console.log('[App] navigating to page: %s', pageId);
    setActivePage(pageId);
  };

  const currentPage = PAGES.find(p => p.id === activePage);

  const renderPage = () => {
    switch (activePage) {
      case 'welcome':
        return <WelcomeBanner onStart={() => setActivePage('pdf')} />;
      case 'pdf':
        return (
          <div className="page-body">
            <PDFUploader onAnalysisComplete={handleAnalysisComplete} />
          </div>
        );
      case 'chat':
        return (
          <ChatInterface
            threadId={threadId}
            sessionId={sessionId}
            indexedSources={indexedSources}
          />
        );
      case 'crawler':
        return (
          <div className="page-body">
            <WebCrawler threadId={threadId} onCrawlComplete={handleCrawlComplete} />
          </div>
        );
      case 'memory':
        return (
          <div className="page-body">
            <MemoryViewer threadId={threadId} />
          </div>
        );
      case 'trace':
        return (
          <div className="page-body">
            <AgentTrace logs={lastTrace.logs} analytics={lastTrace.analytics} />
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        indexedCount={indexedSources.length}
        messageCount={messageCount}
      />

      {/* Main */}
      <div className="main-content">
        {/* Status bar when thread is active */}
        {threadId && activePage !== 'welcome' && (
          <div style={{ background: 'rgba(20,184,166,0.06)', borderBottom: '1px solid rgba(20,184,166,0.2)', padding: '8px 24px', display: 'flex', alignItems: 'center', gap: 12, fontSize: 12 }}>
            <span className="pulse-dot" />
            <span style={{ color: 'var(--accent-teal)', fontWeight: 500 }}>Session active</span>
            <span style={{ color: 'var(--text-muted)' }}>Thread: <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{threadId.slice(0, 24)}...</code></span>
            <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>
              {indexedSources.length} source{indexedSources.length !== 1 ? 's' : ''} indexed
            </span>
          </div>
        )}

        {/* Page header (not for welcome or full-screen chat) */}
        {activePage !== 'welcome' && activePage !== 'chat' && currentPage && (
          <div className="page-header">
            <h1 className="page-title">{currentPage.title}</h1>
            <p className="page-subtitle">{currentPage.subtitle}</p>
          </div>
        )}

        {/* Chat gets full height */}
        {activePage === 'chat' && (
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {currentPage && (
              <div className="page-header" style={{ paddingBottom: 14 }}>
                <h1 className="page-title">{currentPage.title}</h1>
                <p className="page-subtitle">{currentPage.subtitle}</p>
              </div>
            )}
            <div style={{ flex: 1, overflow: 'hidden' }}>
              {renderPage()}
            </div>
          </div>
        )}

        {/* All other pages */}
        {activePage !== 'chat' && renderPage()}
      </div>
    </div>
  );
}
