import { useEffect, useState } from 'react';
import { CARDS } from '../data/cards.js';
import { RotateCcw } from 'lucide-react';

/* ── Confetti ─────────────────────────────────────────────── */
const CONFETTI_COLORS = ['#2f5fd0','#4ecca9','#f59e0b','#ff6b6b','#a8c4ff','#8b86a8','#fff'];
function Confetti() {
  const pieces = Array.from({ length: 60 }, (_, i) => ({
    id: i,
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
    left: `${(i * 17 + 3) % 100}%`,
    delay: `${(i * 0.08) % 2}s`,
    duration: `${2.5 + (i % 5) * 0.4}s`,
    size: 6 + (i % 4) * 3,
    rotate: i * 43,
  }));
  return (
    <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden', zIndex: 50 }}>
      {pieces.map(p => (
        <div key={p.id} style={{
          position: 'absolute', top: '-10px', left: p.left,
          width: p.size, height: p.size,
          background: p.color, borderRadius: p.size > 10 ? '50%' : 2,
          animation: `fall ${p.duration} ${p.delay} ease-in forwards`,
          transform: `rotate(${p.rotate}deg)`,
          opacity: 0.85,
        }} />
      ))}
      <style>{`
        @keyframes fall {
          0%   { top: -10px; transform: rotate(0deg) translateX(0); opacity: 1; }
          80%  { opacity: 0.8; }
          100% { top: 105vh; transform: rotate(720deg) translateX(${Math.random() > 0.5 ? '' : '-'}40px); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

/* ── Time bar comparison ─────────────────────────────────── */
function TimeBar({ humanMs, aiMs }) {
  const [animated, setAnimated] = useState(false);
  useEffect(() => { const t = setTimeout(() => setAnimated(true), 300); return () => clearTimeout(t); }, []);

  const max = Math.max(humanMs || 0, aiMs || 0, 1000);
  const humanPct = humanMs ? (humanMs / max) * 100 : 0;
  const aiPct    = aiMs    ? (aiMs    / max) * 100 : 0;
  const fmt = ms => { if (!ms) return 'N/A'; const s = Math.floor(ms/1000); return s >= 60 ? `${Math.floor(s/60)}m ${s%60}s` : `${s}s`; };

  return (
    <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '16px 20px', marginBottom: 20 }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
        Time comparison
      </div>
      {[
        { label: '🧑 Human', ms: humanMs, color: '#2f5fd0', pct: humanPct },
        { label: '🤖 AI',    ms: aiMs,    color: '#4ecca9', pct: aiPct },
      ].map(row => (
        <div key={row.label} style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#fff', fontWeight: 600 }}>{row.label}</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: row.color, fontWeight: 700 }}>{fmt(row.ms)}</span>
          </div>
          <div style={{ height: 10, background: 'rgba(255,255,255,0.08)', borderRadius: 5, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 5, background: row.color,
              width: animated ? `${row.pct}%` : '0%',
              transition: 'width 1s cubic-bezier(0.4,0,0.2,1)',
              boxShadow: `0 0 10px ${row.color}88`,
            }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Answer column ───────────────────────────────────────── */
function AnswerCol({ emoji, label, timeMs, answer, tools, isAI, faster }) {
  const TOOL_LABELS = { vector_search: { icon: '🔍', color: '#2f5fd0' }, hybrid_search: { icon: '⚡', color: '#8b86a8' }, knowledge_graph: { icon: '🕸', color: '#2a9d6c' }, search: { icon: '🔍', color: '#2f5fd0' } };
  const fmt = ms => { if (!ms) return 'N/A'; const s = Math.floor(ms/1000); return s >= 60 ? `${Math.floor(s/60)}m ${s%60}s` : `${s}s`; };

  return (
    <div style={{
      flex: 1,
      background: isAI ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.06)',
      border: `2px solid ${faster ? (isAI ? 'rgba(42,157,108,0.6)' : 'rgba(47,95,208,0.6)') : 'rgba(255,255,255,0.1)'}`,
      borderRadius: 14, overflow: 'hidden',
      animation: 'slideUp 0.5s cubic-bezier(0.34,1.56,0.64,1) both',
      animationDelay: isAI ? '0.1s' : '0s',
      position: 'relative',
    }}>
      {faster && (
        <div style={{
          position: 'absolute', top: 12, right: 12,
          background: 'rgba(42,157,108,0.2)', color: '#4ecca9',
          border: '1px solid rgba(42,157,108,0.4)', borderRadius: 999,
          padding: '3px 10px', fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
          animation: 'popIn 0.4s 0.6s cubic-bezier(0.34,1.56,0.64,1) both',
        }}>
          🏆 Faster
        </div>
      )}

      <div style={{
        padding: '14px 18px',
        borderBottom: `1px solid ${isAI ? 'rgba(47,95,208,0.15)' : 'rgba(255,255,255,0.08)'}`,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{ fontSize: 26 }}>{emoji}</span>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: '#fff' }}>{label}</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: isAI ? '#4ecca9' : '#a8c4ff', fontWeight: 700, marginTop: 1 }}>
            ⏱ {fmt(timeMs)}
          </div>
        </div>
      </div>

      <div style={{ padding: '14px 18px' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8.5, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 7 }}>Answer given</div>
        <div style={{
          fontSize: 13, lineHeight: 1.65, color: 'rgba(255,255,255,0.82)',
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 8, padding: '10px 12px', whiteSpace: 'pre-wrap',
          maxHeight: 180, overflowY: 'auto',
        }}>
          {answer || <span style={{ opacity: 0.35 }}>No answer given</span>}
        </div>
        {isAI && tools?.length > 0 && (
          <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {tools.map((t, i) => {
              const name = t.tool_name || t.name || 'search';
              const cfg = TOOL_LABELS[name] || { icon: '🛠', color: '#8b86a8' };
              return (
                <span key={i} style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9.5,
                  background: `${cfg.color}22`, color: cfg.color,
                  border: `1px solid ${cfg.color}44`, borderRadius: 999, padding: '2px 8px',
                }}>
                  {cfg.icon} {name}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ResultsScreen({ question, shuffledCards, manualState, aiState, onReset }) {
  const [showConfetti, setShowConfetti] = useState(true);
  useEffect(() => { const t = setTimeout(() => setShowConfetti(false), 4000); return () => clearTimeout(t); }, []);

  const sourceCard    = CARDS.find(c => c.id === question.sourceCardId);
  const cardIndex     = shuffledCards?.findIndex(c => c.id === question.sourceCardId);
  const cardNumber    = cardIndex != null && cardIndex >= 0 ? cardIndex + 1 : null;
  const humanFaster = manualState.submittedAt != null &&
    (aiState.completedAt == null || manualState.submittedAt < aiState.completedAt);
  const aiFaster = aiState.completedAt != null &&
    (manualState.submittedAt == null || aiState.completedAt < manualState.submittedAt);

  const winner = humanFaster ? '🧑 Human wins!' : aiFaster ? '🤖 AI wins!' : "🤝 It's a tie!";
  const winnerColor = humanFaster ? '#a8c4ff' : aiFaster ? '#4ecca9' : '#f59e0b';

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(160deg, #0b1120 0%, #1b2436 100%)',
      padding: '28px 32px', overflowY: 'auto',
    }}>
      {showConfetti && <Confetti />}

      {/* Winner banner */}
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <div style={{ fontSize: 42, marginBottom: 6 }}>🏁</div>
        <h1 style={{
          fontSize: 42, fontWeight: 900, color: winnerColor, letterSpacing: '-0.02em',
          marginBottom: 4, textShadow: `0 0 40px ${winnerColor}66`,
          animation: 'popIn 0.5s cubic-bezier(0.34,1.56,0.64,1)',
        }}>
          {winner}
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13, maxWidth: 500, margin: '0 auto' }}>
          {question.text}
        </p>
      </div>

      {/* Time comparison bar */}
      <TimeBar humanMs={manualState.submittedAt} aiMs={aiState.completedAt} />

      {/* Side-by-side answers */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 20, alignItems: 'flex-start' }}>
        <AnswerCol emoji="🧑" label="Manual Search" timeMs={manualState.submittedAt} answer={manualState.answer} faster={humanFaster} isAI={false} />
        <AnswerCol emoji="🤖" label="AI Search"     timeMs={aiState.completedAt}     answer={aiState.answer || aiState.error} tools={aiState.toolsUsed} faster={aiFaster} isAI={true} />
      </div>

      {/* Expected answer */}
      <div style={{
        background: 'rgba(42,157,108,0.1)', border: '1px solid rgba(42,157,108,0.3)',
        borderRadius: 12, padding: '16px 20px', marginBottom: 16,
        animation: 'slideUp 0.4s 0.3s ease both',
      }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#4ecca9', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 7 }}>
          ✓ Expected Answer
        </div>
        <p style={{ fontSize: 15, color: '#fff', fontWeight: 700, lineHeight: 1.5 }}>
          {question.expectedAnswer}
        </p>
        {sourceCard && (
          <div style={{ marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>
            📖 {sourceCard.cpg} — {sourceCard.section}
          </div>
        )}
      </div>

      {/* Answer card reveal */}
      {sourceCard && (
        <div style={{
          marginBottom: 16,
          border: '2px solid #f59e0b',
          borderRadius: 14, overflow: 'hidden',
          boxShadow: '0 0 32px rgba(245,158,11,0.25)',
          animation: 'slideUp 0.4s 0.6s ease both',
        }}>
          {/* Header */}
          <div style={{
            background: 'rgba(245,158,11,0.15)',
            padding: '12px 18px',
            display: 'flex', alignItems: 'center', gap: 10,
            borderBottom: '1px solid rgba(245,158,11,0.3)',
          }}>
            <span style={{ fontSize: 22 }}>🃏</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#f59e0b', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 2 }}>
                The answer was on Card #{cardNumber}
              </div>
              <div style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>
                {sourceCard.cpg}
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.5)', marginTop: 1 }}>
                {sourceCard.section}
              </div>
            </div>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: 'rgba(245,158,11,0.25)', border: '2px solid #f59e0b',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 900, color: '#f59e0b',
            }}>
              {cardNumber}
            </div>
          </div>
          {/* Paragraph with key phrase bolded */}
          <div style={{ padding: '14px 18px', background: 'rgba(245,158,11,0.06)' }}>
            <p style={{ fontSize: 12.5, color: 'rgba(255,255,255,0.75)', lineHeight: 1.7 }}>
              {sourceCard.paragraph}
            </p>
          </div>
        </div>
      )}

      {/* RAG teaching point */}
      <div style={{
        background: 'rgba(47,95,208,0.08)', border: '1px solid rgba(47,95,208,0.22)',
        borderRadius: 12, padding: '14px 18px', marginBottom: 24,
        animation: 'slideUp 0.4s 0.45s ease both',
      }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: '#a8c4ff', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>
          💡 Why was the AI so fast?
        </div>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', lineHeight: 1.65 }}>
          The AI didn't memorise the answer — it <strong style={{ color: '#a8c4ff' }}>retrieved</strong> it
          from the same guidelines on those 10 cards. That's{' '}
          <strong style={{ color: '#a8c4ff' }}>Retrieval-Augmented Generation (RAG)</strong>:{' '}
          the agent searched a vector database of guideline text, pulled the most relevant paragraphs,
          then wrote its answer grounded in real evidence. Every claim traces back to a real CPG.
        </p>
      </div>

      <div style={{ textAlign: 'center' }}>
        <button
          onClick={onReset}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '14px 44px', fontSize: 15, fontWeight: 800,
            background: 'linear-gradient(135deg, #2f5fd0, #1c3c8c)', color: '#fff',
            border: 'none', borderRadius: 999, cursor: 'pointer',
            boxShadow: '0 0 28px rgba(47,95,208,0.4)',
            transition: 'transform 0.15s, box-shadow 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.04)'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)'; }}
        >
          <RotateCcw size={16} /> Play Again
        </button>
      </div>

      <style>{`
        @keyframes popIn   { from{transform:scale(0.6);opacity:0} to{transform:scale(1);opacity:1} }
        @keyframes slideUp { from{transform:translateY(20px);opacity:0} to{transform:none;opacity:1} }
      `}</style>
    </div>
  );
}
