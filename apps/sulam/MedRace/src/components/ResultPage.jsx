import { useState, useEffect } from 'react';
import { QUESTIONS } from '../data/questions.js';

const CONF_COLORS = ['#2f5fd0','#4ecca9','#f59e0b','#ff6b6b','#a8c4ff','#8b86a8','#fff'];

function Confetti({ active }) {
  const [pieces] = useState(() =>
    [...Array(70)].map((_, i) => ({
      id: i,
      color: CONF_COLORS[i % CONF_COLORS.length],
      left: `${Math.random() * 100}%`,
      delay: `${Math.random() * 0.8}s`,
      duration: `${2.4 + Math.random() * 1.2}s`,
      size: 6 + Math.random() * 6,
      rotate: Math.random() * 720,
    }))
  );

  if (!active) return null;
  return (
    <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 999, overflow: 'hidden' }}>
      {pieces.map(p => (
        <div key={p.id} style={{
          position: 'absolute', top: '-20px', left: p.left,
          width: p.size, height: p.size,
          background: p.color, borderRadius: 2,
          animation: `confFall ${p.duration} ${p.delay} ease-in forwards`,
          transform: `rotate(${p.rotate}deg)`,
        }} />
      ))}
      <style>{`
        @keyframes confFall {
          0%   { transform: translateY(0) rotate(0deg) scale(1); opacity: 1; }
          80%  { opacity: 1; }
          100% { transform: translateY(110vh) rotate(720deg) scale(0.6); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

function WrongFlash({ active }) {
  if (!active) return null;
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(192,67,63,0.25)',
      zIndex: 998, pointerEvents: 'none',
      animation: 'wrongFlash 0.7s ease-out forwards',
    }}>
      <style>{`@keyframes wrongFlash { 0%{opacity:1} 100%{opacity:0} }`}</style>
    </div>
  );
}

function fmtTime(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const ss = String(s % 60).padStart(2, '0');
  const ds = String(Math.floor((ms % 1000) / 100));
  return m > 0 ? `${m}:${ss}.${ds}` : `${s % 60}.${ds}s`;
}

export default function ResultPage({ questionId, mode, selectedOption, elapsedMs, onBackToList, onBackToLobby }) {
  const q = QUESTIONS.find(x => x.id === questionId);
  const [showConf, setShowConf] = useState(false);
  const [showFlash, setShowFlash] = useState(false);

  const correct = selectedOption === q?.correctOption;

  useEffect(() => {
    if (correct) {
      setShowConf(true);
      const t = setTimeout(() => setShowConf(false), 4000);
      return () => clearTimeout(t);
    } else {
      setShowFlash(true);
      const t = setTimeout(() => setShowFlash(false), 700);
      return () => clearTimeout(t);
    }
  }, [correct]);

  if (!q) return null;

  const correctOpt = q.options.find(o => o.id === q.correctOption);
  const selectedOpt = q.options.find(o => o.id === selectedOption);

  return (
    <div style={{
      minHeight: '100vh',
      background: correct
        ? 'linear-gradient(135deg, #0b1120 0%, #0d2a1c 60%, #1b3628 100%)'
        : 'linear-gradient(135deg, #0b1120 0%, #2a0d0d 60%, #3b1414 100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'flex-start', padding: '48px 24px',
    }}>
      <Confetti active={showConf} />
      <WrongFlash active={showFlash} />

      <div style={{ maxWidth: 640, width: '100%', position: 'relative', zIndex: 1 }}>
        {/* Result badge */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            width: 80, height: 80, borderRadius: '50%', margin: '0 auto 20px',
            background: correct ? 'rgba(42,157,108,0.2)' : 'rgba(192,67,63,0.2)',
            border: `3px solid ${correct ? '#2a9d6c' : '#c0433f'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 38,
            animation: correct ? 'spinIn 0.5s cubic-bezier(0.175,0.885,0.32,1.275)' : 'wobble 0.5s ease',
          }}>
            {correct ? '✓' : '✗'}
          </div>

          <h1 style={{
            fontSize: 36, fontWeight: 900, color: '#fff',
            letterSpacing: '-0.03em', marginBottom: 8,
            animation: 'resultPop 0.4s 0.1s cubic-bezier(0.175,0.885,0.32,1.275) both',
          }}>
            {correct ? 'Correct! 🎉' : 'Not quite!'}
          </h1>

          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 999, padding: '6px 18px',
            fontSize: 14, color: 'rgba(255,255,255,0.7)',
          }}>
            ⏱ {fmtTime(elapsedMs)} · {mode === 'ai' ? '🤖 AI mode' : '🃏 Manual mode'}
          </div>
        </div>

        {/* Question recap */}
        <div style={{
          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 14, padding: '18px 22px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'rgba(255,255,255,0.4)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
            Question
          </div>
          <p style={{ fontSize: 15, color: 'rgba(255,255,255,0.85)', lineHeight: 1.55 }}>{q.text}</p>
        </div>

        {/* Answer reveal */}
        <div style={{
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 14, padding: '18px 22px', marginBottom: 16,
        }}>
          {!correct && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#ff6b6b', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>
                Your answer
              </div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                background: 'rgba(192,67,63,0.12)', border: '1px solid rgba(192,67,63,0.3)',
                borderRadius: 10, padding: '10px 14px',
              }}>
                <div style={{
                  width: 26, height: 26, borderRadius: 7, flexShrink: 0,
                  background: '#c0433f', color: '#fff',
                  fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 800,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {selectedOption}
                </div>
                <span style={{ fontSize: 14, color: '#ffa0a0' }}>{selectedOpt?.text}</span>
              </div>
            </div>
          )}

          <div>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#2a9d6c', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>
              {correct ? 'Your answer (correct!)' : 'Correct answer'}
            </div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: 'rgba(42,157,108,0.12)', border: '1px solid rgba(42,157,108,0.3)',
              borderRadius: 10, padding: '10px 14px',
            }}>
              <div style={{
                width: 26, height: 26, borderRadius: 7, flexShrink: 0,
                background: '#2a9d6c', color: '#fff',
                fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 800,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {q.correctOption}
              </div>
              <span style={{ fontSize: 14, color: '#a8e6cc' }}>{correctOpt?.text}</span>
            </div>
          </div>
        </div>

        {/* Why / Explanation */}
        {!correct && q.expectedAnswer && (
          <div style={{
            background: 'rgba(168,196,255,0.08)', border: '1px solid rgba(168,196,255,0.2)',
            borderRadius: 14, padding: '18px 22px', marginBottom: 16,
          }}>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#a8c4ff', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
              📚 Why?
            </div>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.75)', lineHeight: 1.65 }}>
              {q.expectedAnswer}
            </p>
          </div>
        )}

        {/* AI RAG teaching panel */}
        {mode === 'ai' && q.cards?.[0] && (
          <div style={{
            background: 'rgba(139,134,168,0.1)', border: '1px solid rgba(139,134,168,0.2)',
            borderRadius: 14, padding: '18px 22px', marginBottom: 16,
          }}>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#8b86a8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
              🤖 RAG Source
            </div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
              {q.cards[0].cpg} · {q.cards[0].section}
            </div>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.65)', lineHeight: 1.6 }}>{q.cards[0].summary}</p>
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
          <button onClick={onBackToList} style={{
            flex: 2, padding: '14px 20px', borderRadius: 12,
            background: correct ? '#2a9d6c' : '#2f5fd0',
            border: 'none', color: '#fff', fontWeight: 700, fontSize: 15,
            cursor: 'pointer', transition: 'opacity 0.15s',
          }}
            onMouseEnter={e => e.currentTarget.style.opacity = '0.88'}
            onMouseLeave={e => e.currentTarget.style.opacity = '1'}
          >
            Next question →
          </button>
          <button onClick={onBackToLobby} style={{
            flex: 1, padding: '14px 20px', borderRadius: 12,
            background: 'rgba(255,255,255,0.08)',
            border: '1px solid rgba(255,255,255,0.15)',
            color: 'rgba(255,255,255,0.7)', fontWeight: 600, fontSize: 14,
            cursor: 'pointer', transition: 'background 0.15s',
          }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.14)'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
          >
            Main menu
          </button>
        </div>
      </div>

      <style>{`
        @keyframes spinIn   { from{transform:scale(0) rotate(-180deg);opacity:0} to{transform:scale(1) rotate(0deg);opacity:1} }
        @keyframes wobble   { 0%{transform:translateX(0)} 20%{transform:translateX(-8px)} 40%{transform:translateX(8px)} 60%{transform:translateX(-5px)} 80%{transform:translateX(5px)} 100%{transform:translateX(0)} }
        @keyframes resultPop{ from{transform:scale(0.85);opacity:0} to{transform:scale(1);opacity:1} }
      `}</style>
    </div>
  );
}
