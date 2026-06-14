import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTheme } from '../../context/ThemeContext';
import { explainCarePlan } from '../../lib/clinicalApi';

function MarkdownBubble({ text, fg, fgMuted, border, isDark, streaming }) {
  const accent       = '#10b981';
  const tableBg      = isDark ? 'rgba(255,255,255,0.05)' : '#f8fafc';
  const tableHeadBg  = isDark ? 'rgba(16,185,129,0.12)'  : 'rgba(16,185,129,0.08)';
  const codeInlineBg = isDark ? 'rgba(255,255,255,0.1)'  : '#e2e8f0';
  const blockquoteBg = isDark ? 'rgba(16,185,129,0.10)'  : 'rgba(16,185,129,0.07)';
  const pillBg       = isDark ? 'rgba(14,165,233,0.15)'  : 'rgba(14,165,233,0.1)';
  const pillColor    = isDark ? '#38bdf8'                 : '#0369a1';

  // Detect CPG citation patterns like [CPG HFrEF §10.1] or [Rec #1] and render as pills
  const inlineWithPills = (node) => {
    if (typeof node !== 'string') return node;
    const parts = node.split(/(\[(?:CPG|Rec)[^\]]+\])/g);
    if (parts.length === 1) return node;
    return parts.map((p, i) =>
      /^\[(?:CPG|Rec)/.test(p) ? (
        <span key={i} style={{
          display: 'inline-block',
          fontSize: 10,
          fontWeight: 600,
          padding: '1px 6px',
          borderRadius: 99,
          background: pillBg,
          color: pillColor,
          marginLeft: 3,
          verticalAlign: 'middle',
          letterSpacing: 0.2,
        }}>{p}</span>
      ) : p
    );
  };

  const renderChildren = (children) =>
    React.Children.map(children, (child) =>
      typeof child === 'string' ? inlineWithPills(child) : child
    );

  const components = {
    p: ({ children }) => (
      <p style={{ margin: '0 0 7px', lineHeight: 1.65, fontSize: 12.5 }}>
        {renderChildren(children)}
      </p>
    ),
    h1: ({ children }) => (
      <div style={{
        margin: '12px 0 6px',
        paddingLeft: 9,
        borderLeft: `3px solid ${accent}`,
        fontSize: 13,
        fontWeight: 700,
        color: fg,
        lineHeight: 1.3,
      }}>{children}</div>
    ),
    h2: ({ children }) => (
      <div style={{
        margin: '10px 0 5px',
        paddingLeft: 8,
        borderLeft: `3px solid ${accent}`,
        fontSize: 12.5,
        fontWeight: 700,
        color: fg,
        lineHeight: 1.3,
      }}>{children}</div>
    ),
    h3: ({ children }) => (
      <div style={{
        margin: '9px 0 4px',
        fontSize: 12,
        fontWeight: 700,
        color: accent,
        textTransform: 'uppercase',
        letterSpacing: 0.5,
      }}>{children}</div>
    ),
    strong: ({ children }) => (
      <strong style={{ fontWeight: 700, color: fg }}>{renderChildren(children)}</strong>
    ),
    em: ({ children }) => (
      <em style={{ fontStyle: 'italic', color: fgMuted }}>{children}</em>
    ),
    ul: ({ children }) => (
      <ul style={{ margin: '3px 0 7px', paddingLeft: 16, lineHeight: 1.65 }}>{children}</ul>
    ),
    ol: ({ children }) => (
      <ol style={{ margin: '3px 0 7px', paddingLeft: 16, lineHeight: 1.65 }}>{children}</ol>
    ),
    li: ({ children }) => (
      <li style={{ marginBottom: 3, fontSize: 12.5, paddingLeft: 2 }}>
        {renderChildren(children)}
      </li>
    ),
    blockquote: ({ children }) => (
      <div style={{
        margin: '8px 0',
        padding: '8px 12px',
        borderLeft: `3px solid ${accent}`,
        background: blockquoteBg,
        borderRadius: '0 8px 8px 0',
        fontSize: 12,
        color: fg,
      }}>{children}</div>
    ),
    code: ({ inline, children }) =>
      inline ? (
        <code style={{
          background: codeInlineBg,
          padding: '1px 5px',
          borderRadius: 4,
          fontSize: 11,
          fontFamily: 'monospace',
        }}>{children}</code>
      ) : (
        <pre style={{
          background: codeInlineBg,
          padding: '8px 10px',
          borderRadius: 6,
          fontSize: 11,
          overflowX: 'auto',
          margin: '6px 0',
        }}><code>{children}</code></pre>
      ),
    table: ({ children }) => (
      <div style={{ overflowX: 'auto', margin: '8px 0', borderRadius: 8, border: `1px solid ${border}` }}>
        <table style={{
          borderCollapse: 'collapse',
          width: '100%',
          fontSize: 12,
          lineHeight: 1.5,
          background: tableBg,
        }}>{children}</table>
      </div>
    ),
    thead: ({ children }) => (
      <thead style={{ background: tableHeadBg }}>{children}</thead>
    ),
    th: ({ children }) => (
      <th style={{
        padding: '6px 10px',
        borderBottom: `1px solid ${border}`,
        textAlign: 'left',
        fontWeight: 700,
        color: accent,
        whiteSpace: 'nowrap',
        fontSize: 11,
        textTransform: 'uppercase',
        letterSpacing: 0.4,
      }}>{children}</th>
    ),
    td: ({ children }) => (
      <td style={{
        padding: '5px 10px',
        borderBottom: `1px solid ${border}`,
        color: fg,
        fontSize: 12,
      }}>{renderChildren(children)}</td>
    ),
    hr: () => (
      <hr style={{ border: 'none', borderTop: `1px solid ${border}`, margin: '10px 0', opacity: 0.6 }} />
    ),
  };

  return (
    <div style={{ fontSize: 12.5, color: fg, lineHeight: 1.65 }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
      {streaming && <span style={{ color: fgMuted }}>▌</span>}
    </div>
  );
}

const STARTER_QUESTIONS = [
  'Why was this medication prescribed?',
  'What is the evidence grade for these recommendations?',
  'What should I monitor and how often?',
  'Are there any contraindications I should know about?',
];

/**
 * Persistent floating chatbox — always visible as a FAB.
 * Opens a panel to interrogate the current care plan.
 *
 * Props:
 *   consultationId  number|null — Supabase consultation id (null = no plan saved yet)
 *   recommendations array       — raw recommendations array from carePlan state
 *   hasCarePlan   bool        — true once a care plan has been generated in state
 *   initialRecIndex number?     — pre-select a recommendation on open
 */
export default function CarePlanChat({
  consultationId,
  recommendations = [],
  hasCarePlan = false,
  initialRecIndex = null,
  inlinePlan = null,
  patientInfo = null,
}) {
  const { isDark } = useTheme();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [recIndex, setRecIndex] = useState(initialRecIndex);
  const [sources, setSources] = useState([]);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // When the consultation is reset (both plan sources go null), clear local chat state
  useEffect(() => {
    if (!inlinePlan && !consultationId) {
      setOpen(false);
      setMessages([]);
      setInput('');
      setSources([]);
      setRecIndex(null);
    }
  }, [inlinePlan, consultationId]);

  useEffect(() => {
    if (initialRecIndex !== null) {
      setRecIndex(initialRecIndex);
      setOpen(true);
      const rec = recommendations[initialRecIndex];
      if (rec) {
        const name = rec.intervention || rec.medication || rec.goal || `Recommendation ${initialRecIndex + 1}`;
        setInput(`Why was "${name}" prescribed?`);
      }
    }
  }, [initialRecIndex]);

  const sendMessage = useCallback(async (text, recIdx) => {
    const userText = (text || input).trim();
    if (!userText || loading) return;

    if (!consultationId && !inlinePlan) {
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: userText },
        {
          role: 'assistant',
          text: 'No care plan has been generated yet. Complete the consultation workflow to generate a care plan, then I can answer questions about it.',
          error: true,
        },
      ]);
      setInput('');
      return;
    }

    setInput('');
    setSources([]);
    setMessages((prev) => [...prev, { role: 'user', text: userText }]);
    setLoading(true);
    setMessages((prev) => [...prev, { role: 'assistant', text: '', streaming: true }]);

    try {
      await explainCarePlan({
        message: userText,
        consultationId,
        sessionId,
        recommendationIndex: recIdx ?? recIndex ?? undefined,
        inlinePlan: inlinePlan ? { treatment_plan: inlinePlan, patient: patientInfo } : null,
        onToken: (chunk) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === 'assistant') {
              next[next.length - 1] = { ...last, text: last.text + chunk };
            }
            return next;
          });
        },
        onSources: (s) => setSources(s || []),
      });
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant') {
          next[next.length - 1] = { ...last, text: `Error: ${err.message}`, error: true };
        }
        return next;
      });
    } finally {
      setLoading(false);
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant') {
          next[next.length - 1] = { ...last, streaming: false };
        }
        return next;
      });
    }
  }, [input, loading, consultationId, sessionId, recIndex]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Colours ───────────────────────────────────────────────────────────────
  const bg       = isDark ? '#1e293b' : '#ffffff';
  const border   = isDark ? 'rgba(255,255,255,0.08)' : '#e2e8f0';
  const fg       = isDark ? '#e2e8f0' : '#1e293b';
  const fgMuted  = isDark ? '#94a3b8' : '#64748b';
  const accent   = '#10b981';
  const accentVar = 'var(--accent-primary, #10b981)';
  const userBubble = isDark ? 'rgba(16,185,129,0.18)' : 'rgba(16,185,129,0.1)';
  const aiBubble   = isDark ? 'rgba(255,255,255,0.05)' : '#f8fafc';

  // FAB is active when we have a plan to discuss (either in-memory or saved)
  const planReady = hasCarePlan || !!inlinePlan;

  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      right: 24,
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-end',
      gap: 10,
      fontFamily: 'inherit',
    }}>
      {/* ── Chat panel ─────────────────────────────────────────────────────── */}
      {open && (
        <div style={{
          width: 390,
          maxHeight: 580,
          display: 'flex',
          flexDirection: 'column',
          background: bg,
          border: `1px solid ${border}`,
          borderRadius: 18,
          boxShadow: isDark
            ? '0 12px 40px rgba(0,0,0,0.6)'
            : '0 12px 40px rgba(0,0,0,0.14)',
          overflow: 'hidden',
        }}>
          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '13px 16px',
            borderBottom: `1px solid ${border}`,
            background: isDark ? 'rgba(255,255,255,0.04)' : '#f1f5f9',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                background: `linear-gradient(135deg, ${accent}, #0ea5e9)`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 15, flexShrink: 0,
              }}>🩺</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: fg, lineHeight: 1.3 }}>
                  ClearPath AI Assistant
                </div>
                <div style={{ fontSize: 11, color: fgMuted }}>
                  {planReady ? 'Ask about your care plan · CPG-grounded' : 'Available after care plan is generated'}
                </div>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: fgMuted, fontSize: 20, lineHeight: 1, padding: '2px 4px',
              }}
              title="Close"
            >×</button>
          </div>

          {/* Rec selector — only when care plan has recommendations */}
          {planReady && recommendations.length > 0 && (
            <div style={{
              padding: '8px 14px',
              borderBottom: `1px solid ${border}`,
              flexShrink: 0,
            }}>
              <div style={{ fontSize: 11, color: fgMuted, marginBottom: 4 }}>
                Focus on a specific recommendation (optional):
              </div>
              <select
                value={recIndex ?? ''}
                onChange={(e) => setRecIndex(e.target.value === '' ? null : Number(e.target.value))}
                style={{
                  width: '100%', fontSize: 12, padding: '5px 8px',
                  borderRadius: 7, border: `1px solid ${border}`,
                  background: bg, color: fg, cursor: 'pointer',
                }}
              >
                <option value=''>All recommendations</option>
                {recommendations.map((r, i) => {
                  const label = r.intervention || r.medication || r.goal || `Rec ${i + 1}`;
                  return (
                    <option key={i} value={i}>
                      {i + 1}. {label.length > 58 ? label.slice(0, 58) + '…' : label}
                    </option>
                  );
                })}
              </select>
            </div>
          )}

          {/* Message area */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}>
            {/* Empty state — no plan yet */}
            {!planReady && messages.length === 0 && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', gap: 10, padding: '24px 16px', textAlign: 'center',
              }}>
                <div style={{ fontSize: 36, opacity: 0.4 }}>🩺</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: fg }}>No care plan yet</div>
                <div style={{ fontSize: 12, color: fgMuted, lineHeight: 1.5 }}>
                  Generate a care plan for a patient first. Once complete, you can ask me why any
                  recommendation was made, probe the evidence, or check contraindications.
                </div>
              </div>
            )}

            {/* Empty state — plan exists, no messages yet */}
            {planReady && messages.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 12, color: fgMuted, marginBottom: 2 }}>
                  Suggested questions:
                </div>
                {STARTER_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    style={{
                      textAlign: 'left', fontSize: 12, padding: '8px 11px',
                      borderRadius: 9, border: `1px solid ${border}`,
                      background: aiBubble, color: fg, cursor: 'pointer',
                      lineHeight: 1.45, transition: 'border-color 0.15s',
                    }}
                  >{q}</button>
                ))}
              </div>
            )}

            {/* Messages */}
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: m.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div style={{
                  maxWidth: '90%',
                  padding: '9px 13px',
                  borderRadius: m.role === 'user' ? '14px 14px 3px 14px' : '14px 14px 14px 3px',
                  background: m.role === 'user' ? userBubble : aiBubble,
                  border: m.role === 'assistant' ? `1px solid ${border}` : 'none',
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: m.error ? '#ef4444' : fg,
                  whiteSpace: m.role === 'user' ? 'pre-wrap' : 'normal',
                  wordBreak: 'break-word',
                }}>
                  {m.role === 'assistant' && !m.error ? (
                    m.text ? (
                      <MarkdownBubble text={m.text} fg={fg} fgMuted={fgMuted} border={border} isDark={isDark} streaming={m.streaming} />
                    ) : (
                      m.streaming ? <span style={{ color: fgMuted }}>▌</span> : ''
                    )
                  ) : (
                    m.text || (m.streaming ? <span style={{ color: fgMuted }}>▌</span> : '')
                  )}
                </div>
              </div>
            ))}

            {/* Sources — only show when last reply was a real clinical answer, not a refusal */}
            {sources.length > 0 && !loading && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.error && (
              <div style={{
                fontSize: 11, color: fgMuted,
                borderTop: `1px solid ${border}`,
                paddingTop: 7, marginTop: 2,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 3 }}>CPG sources used:</div>
                {sources.slice(0, 4).map((s, i) => (
                  <div key={i} style={{ marginBottom: 2 }}>
                    • {s.document_title || s.tool || 'CPG'}
                  </div>
                ))}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input footer */}
          <div style={{
            borderTop: `1px solid ${border}`,
            padding: '10px 12px',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <textarea
                ref={inputRef}
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder={
                  planReady
                    ? 'Ask why, ask for evidence, probe uncertainty… (Enter to send)'
                    : 'Generate a care plan first to ask questions…'
                }
                disabled={loading || !planReady}
                style={{
                  flex: 1, resize: 'none', fontSize: 13, padding: '8px 10px',
                  borderRadius: 8, border: `1px solid ${border}`,
                  background: isDark ? 'rgba(255,255,255,0.05)' : '#f8fafc',
                  color: fg, fontFamily: 'inherit', lineHeight: 1.4,
                  outline: 'none',
                  opacity: planReady ? 1 : 0.5,
                }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={loading || !input.trim() || !planReady}
                style={{
                  width: 38, height: 38,
                  borderRadius: 9, border: 'none', flexShrink: 0,
                  background: (loading || !input.trim() || !planReady)
                    ? (isDark ? 'rgba(255,255,255,0.08)' : '#e2e8f0')
                    : accentVar,
                  color: (loading || !input.trim() || !planReady) ? fgMuted : '#fff',
                  cursor: (loading || !input.trim() || !planReady) ? 'not-allowed' : 'pointer',
                  fontSize: 18, lineHeight: 1,
                  transition: 'background 0.15s',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >{loading ? '…' : '↑'}</button>
            </div>
            <div style={{ fontSize: 10, color: fgMuted, marginTop: 5, textAlign: 'center' }}>
              CPG-grounded · refuses &amp; escalates when uncertain
            </div>
          </div>
        </div>
      )}

      {/* ── FAB ────────────────────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen((o) => !o)}
        title={planReady ? 'Ask about this care plan' : 'AI Assistant (available after care plan is generated)'}
        style={{
          width: 54,
          height: 54,
          borderRadius: '50%',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: open ? 22 : 24,
          color: '#fff',
          background: open
            ? (isDark ? '#334155' : '#64748b')
            : planReady
              ? `linear-gradient(135deg, ${accent} 0%, #0ea5e9 100%)`
              : (isDark ? '#334155' : '#94a3b8'),
          boxShadow: planReady && !open
            ? `0 4px 18px rgba(16,185,129,0.45)`
            : '0 2px 8px rgba(0,0,0,0.2)',
          transition: 'all 0.2s ease',
          transform: open ? 'rotate(45deg)' : 'none',
        }}
      >
        {open ? '+' : '🩺'}
      </button>
    </div>
  );
}
