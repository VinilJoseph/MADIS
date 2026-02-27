import React, { useState } from 'react';
import { Globe, Link, Loader2, CheckCircle, AlertTriangle, List, Search } from 'lucide-react';

export default function WebCrawler({ threadId, onCrawlComplete }) {
  const [url, setUrl] = useState('');
  const [isSitemap, setIsSitemap] = useState(false);
  const [maxPages, setMaxPages] = useState(20);
  const [status, setStatus] = useState(null); // null | 'crawling' | 'done' | 'error'
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [crawledList, setCrawledList] = useState([]);
  const [showList, setShowList] = useState(false);

  const handleCrawl = async () => {
    if (!url.trim() || !threadId) return;
    console.log('[WebCrawler] Starting crawl: url=%s isSitemap=%s maxPages=%d thread=%s', url, isSitemap, maxPages, threadId);
    setStatus('crawling'); setError(null); setResult(null); setCrawledList([]);

    try {
      const resp = await fetch('/crawl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim(), thread_id: threadId, is_sitemap: isSitemap, max_pages: maxPages }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || resp.statusText);
      setResult(data);
      setCrawledList(data.crawled_urls || []);
      setStatus(data.success ? 'done' : 'error');
      if (data.success) {
        console.log('[WebCrawler] Crawl success: pages=%d chunks=%d', data.pages_crawled, data.chunks_inserted);
        onCrawlComplete?.({ name: new URL(url).hostname, type: 'web', url });
      }
    } catch (err) {
      console.error('[WebCrawler] Crawl failed:', err.message);
      setError(err.message);
      setStatus('error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Input card */}
      <div className="glass-card" style={{ padding: 28 }}>
        <h2 style={{ fontFamily: 'var(--font-head)', fontSize: 16, fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Globe size={18} style={{ color: 'var(--accent-teal)' }} /> Web Crawler
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20, lineHeight: 1.6 }}>
          Crawl any website or documentation page and index it into your knowledge base.
          After crawling, you can ask questions about the content in RAG Chat.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label className="form-label">URL to Crawl</label>
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                className="form-input"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://example.com or https://example.com/sitemap.xml"
                onKeyDown={e => e.key === 'Enter' && handleCrawl()}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={isSitemap}
                onChange={e => setIsSitemap(e.target.checked)}
                style={{ accentColor: 'var(--accent-teal)', width: 15, height: 15 }}
              />
              Sitemap / bulk crawl
            </label>

            {isSitemap && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label className="form-label" style={{ margin: 0, whiteSpace: 'nowrap' }}>Max pages:</label>
                <input
                  type="number" min={1} max={100}
                  className="form-input"
                  style={{ width: 70 }}
                  value={maxPages}
                  onChange={e => setMaxPages(Number(e.target.value))}
                />
              </div>
            )}
          </div>

          {!threadId && (
            <div className="badge badge-warning" style={{ padding: '8px 12px', borderRadius: 8 }}>
              <AlertTriangle size={13} /> Upload a PDF first to create a thread before crawling
            </div>
          )}

          <button
            className="btn btn-teal"
            onClick={handleCrawl}
            disabled={!url.trim() || status === 'crawling' || !threadId}
            style={{ justifyContent: 'center', padding: 13 }}
          >
            {status === 'crawling'
              ? <><Loader2 size={16} className="spinner" /> Crawling...</>
              : <><Search size={16} /> {isSitemap ? 'Crawl Sitemap' : 'Crawl URL'}</>
            }
          </button>
        </div>
      </div>

      {/* Crawling progress */}
      {status === 'crawling' && (
        <div className="glass-card" style={{ padding: 24, textAlign: 'center', animation: 'fadeInUp 0.3s ease' }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', border: '3px solid var(--border)', borderTopColor: 'var(--accent-teal)', margin: '0 auto 16px', animation: 'spin 0.9s linear infinite' }} />
          <p style={{ color: 'var(--text-secondary)' }}>
            {isSitemap ? `Crawling sitemap, up to ${maxPages} pages...` : 'Crawling and indexing page...'}
          </p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>This may take a moment for large sites.</p>
        </div>
      )}

      {/* Result */}
      {status === 'done' && result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, animation: 'fadeInUp 0.3s ease' }}>
          <div className="glass-card" style={{ padding: 20, borderColor: 'rgba(20,184,166,0.3)', background: 'rgba(20,184,166,0.05)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <CheckCircle size={20} style={{ color: 'var(--accent-green)' }} />
              <span style={{ fontFamily: 'var(--font-head)', fontWeight: 600, fontSize: 15 }}>Crawl Complete</span>
            </div>
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
              {result.pages_crawled != null && (
                <div className="stat-card" style={{ padding: 14 }}>
                  <div className="stat-value" style={{ fontSize: 22 }}>{result.pages_crawled}</div>
                  <div className="stat-label">Pages crawled</div>
                </div>
              )}
              <div className="stat-card" style={{ padding: 14 }}>
                <div className="stat-value" style={{ fontSize: 22 }}>{result.chunks_inserted}</div>
                <div className="stat-label">Chunks indexed</div>
              </div>
              <div className="stat-card" style={{ padding: 14 }}>
                <div className="stat-value" style={{ fontSize: 22, background: 'var(--gradient-teal)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>✓</div>
                <div className="stat-label">RAG ready</div>
              </div>
            </div>
          </div>

          {crawledList.length > 0 && (
            <div className="glass-card" style={{ padding: 20 }}>
              <button
                className="btn btn-secondary btn-sm"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => setShowList(x => !x)}
              >
                <List size={13} /> {showList ? 'Hide' : 'Show'} {crawledList.length} indexed URLs
              </button>
              {showList && (
                <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 240, overflowY: 'auto' }}>
                  {crawledList.map((u, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 6, background: 'var(--bg-glass)', fontSize: 12, color: 'var(--text-secondary)' }}>
                      <Link size={10} style={{ flexShrink: 0, color: 'var(--accent-teal)' }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {status === 'error' && error && (
        <div className="glass-card" style={{ padding: 20, borderColor: 'rgba(239,68,68,0.3)', animation: 'fadeInUp 0.3s ease' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <AlertTriangle size={18} style={{ color: 'var(--accent-red)', flexShrink: 0, marginTop: 1 }} />
            <div>
              <p style={{ fontWeight: 600, color: 'var(--accent-red)', marginBottom: 4 }}>Crawl Failed</p>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{error}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
