import { useState } from 'react';
import CPGCard from './CPGCard.jsx';

export default function ManualSide({ cards, manualState, question, onFlipCard, onAnswer, onSubmit, onUseHint }) {
  const { flippedCards, answer, submitted, hintUsed, penaltyMs } = manualState;
  const flippedCount = flippedCards.size;
  const pct = Math.round((flippedCount / cards.length) * 100);
  const [buzzing, setBuzzing] = useState(false);

  const handleBuzz = () => {
    if (!answer.trim() || submitted) return;
    setBuzzing(true);
    setTimeout(() => setBuzzing(false), 600);
    onSubmit();
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>

      {/* Header */}
      <div style={{
        padding: '12px 18px 10px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--line)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          {/* Left: title + count */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 20 }}>🧑</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--ink)' }}>Manual Search</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-soft)' }}>
                {flippedCount} of {cards.length} cards opened
              </div>
            </div>
          </div>

          {/* Right: hint button or submitted badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {!submitted && (
              <button
                onClick={onUseHint}
                disabled={hintUsed}
                style={{
                  padding: '5px 11px',
                  background: hintUsed ? '#fdf0da' : 'var(--surface-soft)',
                  color: hintUsed ? 'var(--warn)' : 'var(--ink-soft)',
                  border: `1.5px solid ${hintUsed ? 'var(--warn)' : 'var(--line)'}`,
                  borderRadius: 999, fontSize: 11, fontWeight: 600,
                  cursor: hintUsed ? 'default' : 'pointer',
                  fontFamily: 'var(--font-mono)', transition: 'all 0.15s',
                  whiteSpace: 'nowrap', maxWidth: 160,
                  overflow: 'hidden', textOverflow: 'ellipsis',
                }}
                title={hintUsed ? question?.hint : 'Use a hint — adds 10s to your time'}
              >
                {hintUsed
                  ? `💡 ${question?.hint}`
                  : '💡 Hint  +10s'}
              </button>
            )}
            {submitted && (
              <div style={{
                background: 'var(--ok-soft)', color: 'var(--ok)',
                border: '1px solid #b7e5d2', borderRadius: 999,
                padding: '4px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                animation: 'popIn 0.3s cubic-bezier(0.34,1.56,0.64,1)',
              }}>
                Buzzed in!{penaltyMs > 0 && (
                  <span style={{ fontSize: 10, opacity: 0.7 }}> (+{penaltyMs / 1000}s penalty)</span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ height: 5, background: 'var(--line)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 3,
            width: `${pct}%`,
            background: pct === 100 ? 'var(--ok)' : 'var(--primary)',
            transition: 'width 0.4s ease',
          }} />
        </div>
      </div>

      {/* Card grid */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '12px 14px',
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8,
        alignContent: 'start',
      }}>
        {cards.map((card, i) => (
          <CPGCard
            key={card.id}
            card={card}
            index={i}
            isFlipped={flippedCards.has(card.id)}
            onFlip={onFlipCard}
            disabled={submitted}
          />
        ))}
      </div>

      {/* Answer area */}
      <div style={{
        padding: '12px 14px',
        background: 'var(--surface)',
        borderTop: '1px solid var(--line)',
        flexShrink: 0,
      }}>
        {submitted ? (
          <div style={{
            padding: '12px 14px', background: 'var(--ok-soft)',
            border: '1px solid #b7e5d2', borderRadius: 10,
            fontSize: 13, color: 'var(--ok)', lineHeight: 1.5,
          }}>
            <strong>Your answer:</strong><br />{answer}
          </div>
        ) : (
          <>
            <textarea
              value={answer}
              onChange={e => onAnswer(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && answer.trim()) { e.preventDefault(); handleBuzz(); } }}
              placeholder="Found it? Type your answer here..."
              rows={2}
              style={{
                width: '100%', resize: 'none', marginBottom: 8,
                padding: '10px 12px',
                border: '1.5px solid var(--line)',
                borderRadius: 8, fontSize: 13, color: 'var(--ink)',
                background: 'var(--surface)', fontFamily: 'inherit', outline: 'none',
                transition: 'border-color 0.15s',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--primary)'}
              onBlur={e => e.target.style.borderColor = 'var(--line)'}
            />
            <button
              onClick={handleBuzz}
              disabled={!answer.trim()}
              style={{
                width: '100%', padding: '12px',
                fontSize: 15, fontWeight: 800, letterSpacing: '0.04em',
                background: answer.trim()
                  ? buzzing ? '#1c3c8c' : 'linear-gradient(135deg, #2f5fd0, #1c3c8c)'
                  : 'var(--line)',
                color: answer.trim() ? '#fff' : 'var(--ink-soft)',
                border: 'none', borderRadius: 10,
                cursor: answer.trim() ? 'pointer' : 'not-allowed',
                boxShadow: answer.trim() ? '0 4px 16px rgba(47,95,208,0.35)' : 'none',
                transform: buzzing ? 'scale(0.97)' : 'scale(1)',
                transition: 'all 0.12s',
                animation: buzzing ? 'buzzFlash 0.3s ease' : 'none',
              }}
            >
              {answer.trim() ? 'BUZZ IN!' : 'Type your answer first'}
            </button>
          </>
        )}
      </div>

      <style>{`
        @keyframes popIn     { from{transform:scale(0.7);opacity:0} to{transform:scale(1);opacity:1} }
        @keyframes buzzFlash { 0%{background:#2f5fd0;box-shadow:0 0 0 0 rgba(47,95,208,0.7)} 50%{background:#fff;box-shadow:0 0 0 12px rgba(47,95,208,0)} 100%{background:#1c3c8c;box-shadow:0 0 0 0 rgba(47,95,208,0)} }
      `}</style>
    </div>
  );
}
