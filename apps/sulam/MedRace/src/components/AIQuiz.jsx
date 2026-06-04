import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeft, Clock, Send } from 'lucide-react';
import { QUESTIONS } from '../data/questions.js';
import { streamAIAnswer } from '../lib/medRaceApi.js';

function useStopwatch() {
  const [ms, setMs] = useState(0);
  const intervalRef = useRef(null);
  const startRef = useRef(null);

  useEffect(() => {
    startRef.current = Date.now();
    intervalRef.current = setInterval(() => setMs(Date.now() - startRef.current), 100);
    return () => clearInterval(intervalRef.current);
  }, []);

  const stop = useCallback(() => {
    clearInterval(intervalRef.current);
    return Date.now() - startRef.current;
  }, []);

  return { ms, stop };
}

function fmtTime(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const ss = String(s % 60).padStart(2, '0');
  const ds = String(Math.floor((ms % 1000) / 100));
  return m > 0 ? `${m}:${ss}.${ds}` : `${s % 60}.${ds}s`;
}

const TOOL_META = {
  vector_search:    { label: 'Vector Search',    color: '#2f5fd0', bg: '#dce6fb' },
  hybrid_search:    { label: 'Hybrid Search',    color: '#2a9d6c', bg: '#e8f7f1' },
  knowledge_graph:  { label: 'Knowledge Graph',  color: '#8b86a8', bg: '#e7e4ef' },
};

export default function AIQuiz({ questionId, onAnswer, onBack }) {
  const q = QUESTIONS.find(x => x.id === questionId);
  const [query, setQuery] = useState('');
  const [output, setOutput] = useState('');
  const [tools, setTools] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [locked, setLocked] = useState(false);
  const outputRef = useRef(null);
  const { ms, stop } = useStopwatch();

  useEffect(() => {
    if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [output]);

  if (!q) return null;

  const handleSend = async () => {
    const trimmed = query.trim();
    if (!trimmed || streaming) return;
    setOutput('');
    setTools([]);
    setError(null);
    setStreaming(true);
    try {
      await streamAIAnswer(
        trimmed,
        (chunk) => setOutput(prev => prev + chunk),
        (t) => {
          const names = (Array.isArray(t) ? t : [t]).map(x => x.tool_name || x.name || String(x));
          setTools(prev => [...new Set([...prev, ...names])]);
        },
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setStreaming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleSelect = (optId) => {
    if (locked) return;
    setLocked(true);
    setSelected(optId);
    const elapsed = stop();
    setTimeout(() => onAnswer(optId, elapsed), 320);
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        background: 'var(--sidebar)', padding: '14px 24px',
        display: 'flex', alignItems: 'center', gap: 14,
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button onClick={onBack} style={{
          background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 8, color: '#fff', padding: '6px 12px',
          display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer',
        }}>
          <ChevronLeft size={15} /> Back
        </button>
        <div style={{ flex: 1, color: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
          🤖 AI Assistant · {q.topic}
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontFamily: 'var(--font-mono)', fontSize: 14, color: '#a8c4ff', fontWeight: 700,
        }}>
          <Clock size={14} /> {fmtTime(ms)}
        </div>
      </div>

      <div style={{ flex: 1, maxWidth: 820, width: '100%', margin: '0 auto', padding: '28px 24px' }}>
        {/* Question */}
        <div style={{
          background: 'var(--surface)', border: '1.5px solid var(--line)',
          borderRadius: 14, padding: '20px 24px', marginBottom: 20,
          boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--primary)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8, fontWeight: 700 }}>
            Clinical Question
          </div>
          <p style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.5 }}>{q.text}</p>
        </div>

        {/* Terminal */}
        <div style={{
          background: '#0d1117', borderRadius: 14, overflow: 'hidden',
          border: '1.5px solid rgba(255,255,255,0.1)', marginBottom: 20,
          boxShadow: 'var(--shadow-md)',
        }}>
          {/* macOS title bar */}
          <div style={{
            background: '#1c2333', padding: '10px 14px',
            display: 'flex', alignItems: 'center', gap: 6,
            borderBottom: '1px solid rgba(255,255,255,0.07)',
          }}>
            {['#ff5f57','#febc2e','#28c840'].map(c => (
              <div key={c} style={{ width: 11, height: 11, borderRadius: '50%', background: c }} />
            ))}
            <span style={{ marginLeft: 8, fontSize: 11, color: 'rgba(255,255,255,0.35)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
              agentic-rag — clinical assistant
            </span>
          </div>

          {/* Query input */}
          <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <span style={{ fontFamily: 'var(--font-mono)', color: '#4ecca9', fontSize: 13, paddingTop: 2, flexShrink: 0 }}>$</span>
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask the AI about the clinical guidelines…"
              rows={2}
              disabled={streaming}
              style={{
                flex: 1, background: 'transparent', border: 'none', outline: 'none', resize: 'none',
                fontFamily: 'var(--font-mono)', fontSize: 13, color: '#e6edf3', lineHeight: 1.6,
                caretColor: '#4ecca9',
              }}
            />
            <button onClick={handleSend} disabled={streaming || !query.trim()} style={{
              background: streaming ? 'rgba(78,204,169,0.12)' : 'rgba(78,204,169,0.18)',
              border: '1px solid rgba(78,204,169,0.3)', borderRadius: 8,
              color: '#4ecca9', padding: '6px 10px', cursor: streaming ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, flexShrink: 0,
            }}>
              <Send size={13} /> {streaming ? 'Thinking…' : 'Ask'}
            </button>
          </div>

          {/* Tool badges */}
          {tools.length > 0 && (
            <div style={{ padding: '8px 14px', display: 'flex', flexWrap: 'wrap', gap: 6, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              {tools.map((t, i) => {
                const meta = TOOL_META[t] || { label: t, color: '#fff', bg: 'rgba(255,255,255,0.1)' };
                return (
                  <span key={i} style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700,
                    padding: '2px 8px', borderRadius: 999,
                    background: meta.bg, color: meta.color,
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                  }}>
                    ⚙ {meta.label}
                  </span>
                );
              })}
            </div>
          )}

          {/* Output */}
          <div ref={outputRef} style={{
            padding: '14px', minHeight: 120, maxHeight: 320, overflowY: 'auto',
            fontFamily: 'var(--font-mono)', fontSize: 13, color: '#c9d1d9', lineHeight: 1.75,
            whiteSpace: 'pre-wrap',
          }}>
            {output ? (
              <>
                <span style={{ color: 'rgba(255,255,255,0.3)', marginRight: 8 }}>{'>'}</span>
                {output}
                {streaming && <span style={{ animation: 'blink 1s step-end infinite', color: '#4ecca9' }}>▋</span>}
              </>
            ) : (
              <span style={{ color: 'rgba(255,255,255,0.2)', fontStyle: 'italic' }}>
                {streaming ? 'Querying clinical knowledge base…' : 'Type a question above and press Ask or Enter'}
              </span>
            )}
            {error && <div style={{ color: '#ff6b6b', marginTop: 8 }}>✗ {error}</div>}
          </div>
        </div>

        {/* MCQ */}
        <div style={{
          background: 'var(--surface)', border: '1.5px solid var(--line)',
          borderRadius: 14, padding: '20px 24px',
          boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--ink-soft)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 14, fontWeight: 700 }}>
            Pick your answer
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {q.options.map(opt => {
              const isSel = selected === opt.id;
              return (
                <button key={opt.id} onClick={() => handleSelect(opt.id)} disabled={locked}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '13px 16px', borderRadius: 10, textAlign: 'left',
                    background: isSel ? 'var(--primary-soft)' : 'var(--surface-soft)',
                    border: `1.5px solid ${isSel ? 'var(--primary)' : 'var(--line)'}`,
                    cursor: locked ? 'default' : 'pointer',
                    transition: 'all 0.15s', width: '100%',
                    opacity: locked && !isSel ? 0.5 : 1,
                  }}
                  onMouseEnter={e => { if (!locked) e.currentTarget.style.borderColor = 'var(--primary)'; }}
                  onMouseLeave={e => { if (!locked) e.currentTarget.style.borderColor = isSel ? 'var(--primary)' : 'var(--line)'; }}
                >
                  <div style={{
                    width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                    background: isSel ? 'var(--primary)' : 'var(--line)',
                    color: isSel ? '#fff' : 'var(--ink-soft)',
                    fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 800,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {opt.id}
                  </div>
                  <span style={{ fontSize: 14, color: 'var(--ink)', fontWeight: isSel ? 600 : 400 }}>{opt.text}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>
    </div>
  );
}
