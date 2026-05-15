import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeft, Clock } from 'lucide-react';
import { QUESTIONS } from '../data/questions.js';
import CPGCard from './CPGCard.jsx';

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

export default function ManualQuiz({ questionId, onAnswer, onBack }) {
  const q = QUESTIONS.find(x => x.id === questionId);
  const [flipped, setFlipped] = useState({});
  const [selected, setSelected] = useState(null);
  const [locked, setLocked] = useState(false);
  const { ms, stop } = useStopwatch();

  if (!q) return null;

  const handleFlip = (cardId) => setFlipped(f => ({ ...f, [cardId]: true }));

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
          🃏 Manual · {q.topic}
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
          borderRadius: 14, padding: '22px 24px', marginBottom: 24,
          boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--primary)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8, fontWeight: 700 }}>
            Clinical Question
          </div>
          <p style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.5 }}>{q.text}</p>
          {q.hint && (
            <p style={{ marginTop: 10, fontSize: 12, color: 'var(--ink-soft)', fontStyle: 'italic' }}>
              💡 Hint: {q.hint}
            </p>
          )}
        </div>

        {/* Cards grid */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink-soft)', marginBottom: 12, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            📖 CPG Summary Cards — flip to reveal
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {q.cards.map((card, i) => (
              <CPGCard
                key={card.id}
                card={card}
                index={i}
                isFlipped={!!flipped[card.id]}
                onFlip={handleFlip}
                disabled={locked}
              />
            ))}
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
    </div>
  );
}
