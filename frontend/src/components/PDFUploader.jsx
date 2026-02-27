import React, { useState, useRef, useCallback } from 'react';
import { Upload, FileText, CheckCircle, Loader2, AlertTriangle, Brain, ChevronDown, ChevronRight, Sparkles, Layers, BookOpen, Lightbulb } from 'lucide-react';

const STAGES = [
  { key: 'uploading', label: 'Uploading PDF', progress: 15 },
  { key: 'extracting', label: 'Extracting text', progress: 35 },
  { key: 'embedding', label: 'Building vector index', progress: 65 },
  { key: 'analyzing', label: 'Running AI analysis', progress: 85 },
  { key: 'done', label: 'Analysis complete!', progress: 100 },
];

function StageProgress({ stage, embedProgress }) {
  const idx = STAGES.findIndex(s => s.key === stage);

  // During embedding: interpolate progress between 35% and 65% based on chunks done
  let pct = idx >= 0 ? STAGES[idx].progress : 0;
  let label = idx >= 0 ? STAGES[idx].label : '';
  if (stage === 'embedding' && embedProgress?.total > 0) {
    const frac = embedProgress.current / embedProgress.total;
    pct = Math.round(35 + frac * 30);  // 35% → 65%
    label = `Building vector index (${embedProgress.current}/${embedProgress.total})`;
  }

  return (
    <div style={{ padding: '24px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13 }}>
        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{label}</span>
        <span style={{ color: 'var(--text-accent)' }}>{pct}%</span>
      </div>
      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${pct}%`, transition: 'width 0.4s ease' }} />
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
        {STAGES.slice(0, idx + 1).map(s => (
          <span key={s.key} className="badge badge-success" style={{ fontSize: 10 }}>
            <CheckCircle size={10} /> {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function SectionCard({ name, content }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="glass-card" style={{ padding: '14px 18px', cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 500, fontSize: 13, color: 'var(--text-primary)' }}>{name}</span>
        {open ? <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}
      </div>
      {open && (
        <p style={{ marginTop: 10, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          {typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
        </p>
      )}
    </div>
  );
}

export default function PDFUploader({ onAnalysisComplete }) {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [stage, setStage] = useState(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [embedProgress, setEmbedProgress] = useState(null); // { current, total }
  const fileInputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault(); setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f?.type === 'application/pdf') {
      console.log('[PDFUploader] File dropped: %s (%.2f MB)', f.name, f.size / 1024 / 1024);
      setFile(f); setError(null);
    } else {
      console.warn('[PDFUploader] Invalid file type dropped');
      setError('Please drop a PDF file.');
    }
  }, []);

  const handleSelect = (e) => {
    const f = e.target.files?.[0];
    if (f?.type === 'application/pdf') {
      console.log('[PDFUploader] File selected: %s (%.2f MB)', f.name, f.size / 1024 / 1024);
      setFile(f); setError(null);
    } else {
      console.warn('[PDFUploader] Invalid file type selected');
      setError('Please select a PDF file.');
    }
  };

  const handleIngest = async () => {
    if (!file) return;
    console.log('[PDFUploader] Starting ingest (SSE) for file: %s', file.name);
    setError(null); setResult(null); setStage('uploading');

    const threadId = `thread-${Date.now()}`;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('thread_id', threadId);

    try {
      const resp = await fetch('/ingest-pdf', { method: 'POST', body: formData });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `Server error ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let data = null;
      let streamDone = false;

      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            console.log('[PDFUploader] SSE event:', evt);

            if (evt.stage === 'extracting' || evt.stage === 'extracted') {
              setStage('extracting');
            } else if (evt.stage === 'embedding') {
              // Update label with chunk progress
              setStage('embedding');
              // We update STAGES label dynamically below via stageLabel state
              setEmbedProgress({ current: evt.chunk, total: evt.total });
            } else if (evt.stage === 'embedded') {
              setStage('analyzing');
            } else if (evt.stage === 'analyzing') {
              setStage('analyzing');
            } else if (evt.stage === 'done') {
              data = evt.data;
              setStage('done');
              streamDone = true;
            } else if (evt.stage === 'error') {
              throw new Error(evt.message || 'Processing failed');
            }
          } catch (parseErr) {
            if (parseErr.message && parseErr.message !== 'Unexpected end of JSON input') {
              throw parseErr;
            }
          }
        }
      }

      if (!data) throw new Error('No result received from server');
      setResult(data);
      console.log('[PDFUploader] Done: doc_type=%s chunks=%d', data.document_type, data.chunks_indexed);
      onAnalysisComplete?.(data);
    } catch (err) {
      console.error('[PDFUploader] Ingest failed:', err.message);
      setError(err.message || 'Upload failed. Check backend is running.');
      setStage(null);
    }
  };


  const typeColors = {
    'Contract': '#f59e0b', 'Research Paper': '#5b72ff', 'Technical Report': '#14b8a6',
    'Legal Document': '#f472b6', 'Resume': '#8b5cf6', 'Invoice': '#10b981',
    'Academic Paper': '#5b72ff', 'Manual': '#f59e0b',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Upload card */}
      <div className="glass-card" style={{ padding: 28 }}>
        <h2 style={{ fontFamily: 'var(--font-head)', fontSize: 16, fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Upload size={18} style={{ color: 'var(--accent-blue)' }} /> Upload Document
        </h2>

        {/* Drop zone */}
        <div
          className={`upload-zone${isDragging ? ' drag-active' : ''}${file ? ' has-file' : ''}`}
          onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input type="file" ref={fileInputRef} accept=".pdf" style={{ display: 'none' }} onChange={handleSelect} />
          {file ? (
            <div style={{ textAlign: 'center' }}>
              <FileText size={40} style={{ color: 'var(--accent-teal)', margin: '0 auto 10px' }} />
              <p style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)' }}>{file.name}</p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB · Click to change
              </p>
            </div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              <Upload size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
              <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-secondary)' }}>Drop your PDF here</p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>or click to browse · PDF files only</p>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="badge badge-error" style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, display: 'flex', gap: 6, fontSize: 13 }}>
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {/* Progress */}
        {stage && stage !== 'done' && <StageProgress stage={stage} embedProgress={embedProgress} />}

        {/* Ingest button */}
        {!stage && (
          <button
            className="btn btn-primary"
            onClick={handleIngest}
            disabled={!file}
            style={{ width: '100%', marginTop: 16, justifyContent: 'center', padding: '13px' }}
          >
            <Brain size={17} /> Analyze & Index Document
          </button>
        )}
      </div>

      {/* Results */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeInUp 0.4s ease' }}>
          {/* Doc type badge */}
          <div className="glass-card" style={{ padding: '18px 22px', display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ padding: '8px 10px', borderRadius: 10, background: `${typeColors[result.document_type] || '#5b72ff'}22`, border: `1px solid ${typeColors[result.document_type] || '#5b72ff'}44` }}>
              <Layers size={20} style={{ color: typeColors[result.document_type] || '#5b72ff' }} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>Document Type</div>
              <div style={{ fontFamily: 'var(--font-head)', fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
                {result.document_type}
              </div>
            </div>
            <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Chunks indexed</div>
              <div style={{ fontFamily: 'var(--font-head)', fontSize: 18, fontWeight: 700, color: 'var(--accent-teal)' }}>{result.chunks_indexed}</div>
            </div>
          </div>

          {/* Summary */}
          <div className="glass-card" style={{ padding: '20px 22px' }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
              <BookOpen size={14} /> Summary
            </h3>
            <p style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text-primary)' }}>{result.summary}</p>
          </div>

          {/* Key Sections */}
          {Object.keys(result.key_sections || {}).length > 0 && (
            <div className="glass-card" style={{ padding: '20px 22px' }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
                <Layers size={14} /> Key Sections
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(result.key_sections).map(([k, v]) => (
                  <SectionCard key={k} name={k} content={v} />
                ))}
              </div>
            </div>
          )}

          {/* Insights */}
          {result.insights?.length > 0 && (
            <div className="glass-card" style={{ padding: '20px 22px' }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
                <Lightbulb size={14} /> AI Insights
              </h3>
              {result.insights.map((ins, i) => <div key={i} className="insight-item">{ins}</div>)}
            </div>
          )}

          {/* Chat CTA */}
          <div className="glass-card" style={{ padding: '18px 22px', textAlign: 'center', background: 'linear-gradient(135deg, rgba(91,114,255,0.08) 0%, rgba(139,92,246,0.06) 100%)', borderColor: 'var(--border-accent)' }}>
            <Sparkles size={24} style={{ color: 'var(--accent-blue)', margin: '0 auto 8px' }} />
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Document indexed! Switch to <strong style={{ color: 'var(--text-accent)' }}>RAG Chat</strong> to start asking questions.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
