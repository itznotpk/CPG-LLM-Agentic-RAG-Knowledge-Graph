import { useEffect, useRef, useState } from 'react';
import { streamAIAnswer } from '../lib/medRaceApi.js';

/* Typewriter queue — renders text char-by-char for drama */
function useTypewriter(fullText) {
  const [displayed, setDisplayed] = useState('');
  const queueRef = useRef('');
  const timerRef = useRef(null);

  useEffect(() => {
    const incoming = fullText.slice(queueRef.current.length);
    queueRef.current = fullText;

    if (!incoming) return;

    let i = 0;
    const flush = () => {
      const batch = incoming.slice(i, i + 3); // 3 chars per tick → fast enough
      i += batch.length;
      setDisplayed(prev => prev + batch);
      if (i < incoming.length) {
        timerRef.current = setTimeout(flush, 12);
      }
    };
    timerRef.current = setTimeout(flush, 12);
    return () => clearTimeout(timerRef.current);
  }, [fullText]);

  return displayed;
}

const TOOL_LABELS = {
  vector_search:  { icon: '🔍', label: 'Vector DB search',   color: '#2f5fd0' },
  hybrid_search:  { icon: '⚡', label: 'Hybrid search',      color: '#8b86a8' },
  knowledge_graph:{ icon: '🕸', label: 'Knowledge Graph',    color: '#2a9d6c' },
  search:         { icon: '🔍', label: 'Search',             color: '#2f5fd0' },
};

export default function AISide({ question, aiState, onText, onTools, onDone, onError }) {
  const scrollRef  = useRef(null);
  const startedRef = useRef(false);
  const displayed  = useTypewriter(aiState.answer);

  /* Auto-start stream once */
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    streamAIAnswer(question.text, onText, onTools)
      .then(onDone)
      .catch(err => onError(err.message || 'Connection failed'));
  }, []);

  /* Auto-scroll */
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [displayed]);

  const { toolsUsed, isStreaming, completedAt, error } = aiState;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#0b1120' }}>

      {/* Header */}
      <div style={{
        padding: '12px 18px 10px',
        background: '#0f1a2e',
        borderBottom: '1px solid rgba(47,95,208,0.2)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 20 }}>🤖</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>AI Search</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>
                {isStreaming ? 'Searching guidelines…'
                  : completedAt != null ? 'Answer ready'
                  : error ? 'Error' : 'Waiting'}
              </div>
            </div>
          </div>
          {completedAt != null && (
            <div style={{
              background: 'rgba(42,157,108,0.2)', color: '#4ecca9',
              border: '1px solid rgba(42,157,108,0.45)', borderRadius: 999,
              padding: '4px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
              animation: 'popIn 0.3s cubic-bezier(0.34,1.56,0.64,1)',
            }}>
              ✓ Complete
            </div>
          )}
          {isStreaming && (
            <div style={{ display: 'flex', gap: 4 }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 7, height: 7, borderRadius: '50%', background: '#a8c4ff',
                  animation: `bounce 0.9s ease-in-out ${i * 0.15}s infinite`,
                }} />
              ))}
            </div>
          )}
        </div>

        {/* Tool steps — appear one by one as retrieved */}
        {toolsUsed.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {toolsUsed.map((t, i) => {
              const name = t.tool_name || t.name || 'search';
              const cfg = TOOL_LABELS[name] || { icon: '🛠', label: name, color: '#8b86a8' };
              return (
                <span key={i} style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9.5,
                  background: `${cfg.color}22`, color: cfg.color,
                  border: `1px solid ${cfg.color}44`, borderRadius: 999,
                  padding: '2px 9px', fontWeight: 600,
                  animation: 'slideIn 0.35s cubic-bezier(0.34,1.56,0.64,1) both',
                  animationDelay: `${i * 0.1}s`,
                }}>
                  {cfg.icon} {cfg.label}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Response */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 18px 12px' }}>
        {error ? (
          <div style={{
            padding: 16, background: 'rgba(192,67,63,0.1)',
            border: '1px solid rgba(192,67,63,0.3)', borderRadius: 10,
            color: '#ff8a85', fontSize: 13, lineHeight: 1.5,
          }}>
            <strong>Connection error:</strong> {error}
            <br /><br />
            <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12 }}>
              Make sure the backend is running on port 8058.
            </span>
          </div>
        ) : (
          <>
            {isStreaming && !aiState.answer && (
              <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 12, color: 'rgba(255,255,255,0.35)',
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span style={{ animation: 'pulse 1.2s ease-in-out infinite', color: '#a8c4ff' }}>●</span>
                Searching clinical guidelines…
              </div>
            )}

            {displayed && (
              <div style={{
                background: 'rgba(47,95,208,0.08)',
                border: '1px solid rgba(47,95,208,0.2)',
                borderRadius: 12, padding: '14px 16px',
              }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 8.5,
                  color: 'rgba(168,196,255,0.6)', textTransform: 'uppercase',
                  letterSpacing: '0.08em', marginBottom: 8,
                }}>
                  🤖 AI Response
                </div>
                <p style={{
                  fontSize: 13, color: 'rgba(255,255,255,0.85)',
                  lineHeight: 1.75, whiteSpace: 'pre-wrap', fontFamily: 'inherit',
                }}>
                  {displayed}
                  {isStreaming && (
                    <span style={{ animation: 'blink 0.8s step-end infinite', color: '#a8c4ff' }}>▋</span>
                  )}
                </p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '8px 18px',
        borderTop: '1px solid rgba(47,95,208,0.12)',
        fontFamily: 'var(--font-mono)', fontSize: 9,
        color: 'rgba(255,255,255,0.18)', flexShrink: 0,
      }}>
        Powered by Agentic RAG · POST /chat/stream · same guidelines as the cards
      </div>

      <style>{`
        @keyframes bounce  { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
        @keyframes pulse   { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes blink   { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes popIn   { from{transform:scale(0.7);opacity:0} to{transform:scale(1);opacity:1} }
        @keyframes slideIn { from{transform:translateX(-8px) scale(0.9);opacity:0} to{transform:none;opacity:1} }
      `}</style>
    </div>
  );
}
