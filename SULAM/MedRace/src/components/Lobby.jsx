import { useState } from 'react';
import { QUESTIONS } from '../data/questions.js';
import { Zap } from 'lucide-react';

export default function Lobby({ onStart }) {
  const [selected, setSelected] = useState(null);
  const [hovered, setHovered] = useState(null);

  const COLORS = ['#2f5fd0','#8b86a8','#2a9d6c','#b4843a','#c0433f'];

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0b1120 0%, #1b2436 60%, #22304d 100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '32px 24px',
    }}>
      {/* Animated background dots */}
      <div style={{ position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
        {[...Array(12)].map((_, i) => (
          <div key={i} style={{
            position: 'absolute',
            width: 3, height: 3, borderRadius: '50%',
            background: `rgba(47,95,208,${0.15 + (i % 3) * 0.1})`,
            left: `${(i * 37 + 11) % 100}%`,
            top: `${(i * 53 + 7) % 100}%`,
            animation: `floatDot ${4 + (i % 4)}s ease-in-out ${i * 0.4}s infinite alternate`,
          }} />
        ))}
      </div>

      {/* Logo */}
      <div style={{ textAlign: 'center', marginBottom: 40, position: 'relative', zIndex: 1 }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: 'rgba(47,95,208,0.15)', border: '1px solid rgba(47,95,208,0.35)',
          borderRadius: 999, padding: '5px 16px', marginBottom: 18,
          fontFamily: 'var(--font-mono)', fontSize: 10, color: '#a8c4ff',
          letterSpacing: '0.12em', textTransform: 'uppercase',
        }}>
          <Zap size={11} fill="#a8c4ff" /> Agentic RAG · Interactive Session
        </div>

        <h1 style={{ fontSize: 72, fontWeight: 900, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1, marginBottom: 10 }}>
          Med<span style={{ color: '#2f5fd0', textShadow: '0 0 40px rgba(47,95,208,0.6)' }}>Race</span>
        </h1>

        <p style={{ fontSize: 18, color: 'rgba(255,255,255,0.5)', marginBottom: 4 }}>
          Human vs AI — who finds the answer faster?
        </p>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.28)', maxWidth: 460, margin: '0 auto' }}>
          Left player hunts through 10 clinical guideline cards.
          Right player watches the AI search the same guidelines live.
        </p>
      </div>

      {/* Question selector */}
      <div style={{ width: '100%', maxWidth: 660, position: 'relative', zIndex: 1 }}>
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.35)',
          letterSpacing: '0.12em', textTransform: 'uppercase', textAlign: 'center', marginBottom: 12,
        }}>
          Choose a question to race on
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {QUESTIONS.map((q, i) => {
            const isSel = selected?.id === q.id;
            const isHov = hovered === q.id;
            const accent = COLORS[i];
            return (
              <button
                key={q.id}
                onClick={() => setSelected(q)}
                onMouseEnter={() => setHovered(q.id)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  background: isSel ? 'rgba(47,95,208,0.2)' : isHov ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.04)',
                  border: `1.5px solid ${isSel ? 'rgba(47,95,208,0.65)' : isHov ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: 12, padding: '13px 18px',
                  textAlign: 'left', color: '#fff',
                  transition: 'all 0.18s', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 14,
                  transform: isHov && !isSel ? 'translateX(4px)' : 'none',
                }}
              >
                <div style={{
                  width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                  background: isSel ? accent : 'rgba(255,255,255,0.1)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 800, color: '#fff',
                  transition: 'background 0.18s',
                  boxShadow: isSel ? `0 0 14px ${accent}66` : 'none',
                }}>
                  {i + 1}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 9,
                    color: isSel ? '#a8c4ff' : 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3,
                    transition: 'color 0.18s',
                  }}>
                    {q.topic}
                  </div>
                  <div style={{ fontSize: 13.5, color: isSel ? '#fff' : 'rgba(255,255,255,0.7)', lineHeight: 1.4 }}>
                    {q.text}
                  </div>
                </div>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                  background: isSel ? '#2f5fd0' : 'transparent',
                  border: `2px solid ${isSel ? '#2f5fd0' : 'rgba(255,255,255,0.2)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, transition: 'all 0.18s',
                }}>
                  {isSel && '✓'}
                </div>
              </button>
            );
          })}
        </div>

        {/* Start */}
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <button
            disabled={!selected}
            onClick={() => selected && onStart(selected)}
            style={{
              padding: '16px 64px', fontSize: 17, fontWeight: 800,
              background: selected
                ? 'linear-gradient(135deg, #2f5fd0, #1c3c8c)'
                : 'rgba(255,255,255,0.07)',
              color: selected ? '#fff' : 'rgba(255,255,255,0.25)',
              border: 'none', borderRadius: 999,
              cursor: selected ? 'pointer' : 'not-allowed',
              transition: 'all 0.2s', letterSpacing: '0.03em',
              boxShadow: selected ? '0 0 40px rgba(47,95,208,0.45), 0 4px 16px rgba(0,0,0,0.3)' : 'none',
              transform: selected ? 'scale(1)' : 'scale(0.98)',
            }}
            onMouseEnter={e => { if (selected) { e.currentTarget.style.transform = 'scale(1.04)'; e.currentTarget.style.boxShadow = '0 0 56px rgba(47,95,208,0.6), 0 6px 20px rgba(0,0,0,0.4)'; } }}
            onMouseLeave={e => { if (selected) { e.currentTarget.style.transform = 'scale(1)'; e.currentTarget.style.boxShadow = '0 0 40px rgba(47,95,208,0.45), 0 4px 16px rgba(0,0,0,0.3)'; } }}
          >
            {selected ? '⚡ Start Race' : 'Select a question first'}
          </button>
          {selected && (
            <div style={{ marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.28)' }}>
              A 3-second countdown will begin for both players
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes floatDot {
          from { transform: translateY(0) scale(1); }
          to   { transform: translateY(-18px) scale(1.5); }
        }
      `}</style>
    </div>
  );
}
