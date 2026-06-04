import { useState } from 'react';
import { Zap } from 'lucide-react';

export default function Lobby({ onStart }) {
  const [hovered, setHovered] = useState(null);

  const MODES = [
    { id: 'manual', icon: '🃏', title: 'Manual', desc: 'Flip clinical guideline flashcards and pick the right answer yourself.' },
    { id: 'ai',     icon: '🤖', title: 'AI Assistant', desc: 'Query the AI about the guidelines, read its response, then pick your answer.' },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0b1120 0%, #1b2436 60%, #22304d 100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '32px 24px',
    }}>
      <div style={{ position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
        {[...Array(12)].map((_, i) => (
          <div key={i} style={{
            position: 'absolute', width: 3, height: 3, borderRadius: '50%',
            background: `rgba(47,95,208,${0.15 + (i % 3) * 0.1})`,
            left: `${(i * 37 + 11) % 100}%`, top: `${(i * 53 + 7) % 100}%`,
            animation: `floatDot ${4 + (i % 4)}s ease-in-out ${i * 0.4}s infinite alternate`,
          }} />
        ))}
      </div>

      <div style={{ textAlign: 'center', marginBottom: 48, position: 'relative', zIndex: 1 }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: 'rgba(47,95,208,0.15)', border: '1px solid rgba(47,95,208,0.35)',
          borderRadius: 999, padding: '5px 16px', marginBottom: 18,
          fontFamily: 'var(--font-mono)', fontSize: 10, color: '#a8c4ff',
          letterSpacing: '0.12em', textTransform: 'uppercase',
        }}>
          <Zap size={11} fill="#a8c4ff" /> Agentic RAG · Interactive Session
        </div>
        <h1 style={{ fontSize: 72, fontWeight: 900, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1, marginBottom: 12 }}>
          Med<span style={{ color: '#2f5fd0', textShadow: '0 0 40px rgba(47,95,208,0.6)' }}>Race</span>
        </h1>
        <p style={{ fontSize: 17, color: 'rgba(255,255,255,0.5)', marginBottom: 4 }}>
          Clinical guidelines quiz — pick your mode
        </p>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.28)', maxWidth: 420, margin: '0 auto' }}>
          Choose how you want to answer questions from Malaysian clinical practice guidelines.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 16, position: 'relative', zIndex: 1, width: '100%', maxWidth: 560 }}>
        {MODES.map(m => {
          const isHov = hovered === m.id;
          return (
            <button key={m.id} onClick={() => onStart(m.id)}
              onMouseEnter={() => setHovered(m.id)} onMouseLeave={() => setHovered(null)}
              style={{
                flex: 1, padding: '28px 24px', textAlign: 'left', cursor: 'pointer',
                background: isHov ? 'rgba(47,95,208,0.18)' : 'rgba(255,255,255,0.04)',
                border: `1.5px solid ${isHov ? 'rgba(47,95,208,0.65)' : 'rgba(255,255,255,0.1)'}`,
                borderRadius: 16, color: '#fff', transition: 'all 0.2s',
                boxShadow: isHov ? '0 0 28px rgba(47,95,208,0.35)' : 'none',
                transform: isHov ? 'translateY(-3px)' : 'none',
              }}
            >
              <div style={{ fontSize: 36, marginBottom: 14 }}>{m.icon}</div>
              <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 8 }}>{m.title}</div>
              <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 1.55 }}>{m.desc}</div>
              <div style={{
                marginTop: 20, fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                color: isHov ? '#a8c4ff' : 'rgba(255,255,255,0.3)', transition: 'color 0.2s',
              }}>
                Start →
              </div>
            </button>
          );
        })}
      </div>

      <style>{`
        @keyframes floatDot { from{transform:translateY(0) scale(1)} to{transform:translateY(-18px) scale(1.5)} }
      `}</style>
    </div>
  );
}
