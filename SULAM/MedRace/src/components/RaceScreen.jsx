import { useEffect, useState, useRef } from 'react';
import ManualSide from './ManualSide.jsx';
import AISide from './AISide.jsx';

/* ── Countdown overlay ───────────────────────────────────── */
function Countdown({ onDone }) {
  const [count, setCount] = useState(3);

  useEffect(() => {
    if (count === 0) { onDone(); return; }
    const t = setTimeout(() => setCount(c => c - 1), 900);
    return () => clearTimeout(t);
  }, [count]);

  const isGo = count === 0;
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100,
      background: 'rgba(11,17,32,0.92)',
      backdropFilter: 'blur(8px)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: 16,
    }}>
      <div style={{
        fontSize: isGo ? 100 : 120,
        fontWeight: 900, lineHeight: 1,
        color: isGo ? '#4ecca9' : '#fff',
        textShadow: isGo
          ? '0 0 60px rgba(42,157,108,0.8)'
          : '0 0 40px rgba(255,255,255,0.3)',
        animation: 'countPop 0.4s cubic-bezier(0.34,1.56,0.64,1)',
        key: count,
      }}>
        {count === 0 ? 'GO!' : count}
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 13,
        color: 'rgba(255,255,255,0.4)', letterSpacing: '0.12em', textTransform: 'uppercase',
      }}>
        {count > 0 ? 'Get ready…' : 'Race started!'}
      </div>
      <style>{`@keyframes countPop { from{transform:scale(0.4);opacity:0} to{transform:scale(1);opacity:1} }`}</style>
    </div>
  );
}

/* ── Timer hook ─────────────────────────────────────────── */
function useElapsed(startTime, active) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!active || !startTime) return;
    const id = setInterval(() => setElapsed(Date.now() - startTime), 200);
    return () => clearInterval(id);
  }, [startTime, active]);
  return elapsed;
}

function fmt(ms) {
  if (!ms && ms !== 0) return '00:00';
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

export default function RaceScreen({
  phase, question, cards, startTime,
  manualState, aiState,
  onCountdownEnd,
  onFlipCard, onManualAnswer, onSubmitManual, onUseHint,
  onAIText, onAITools, onAIDone, onAIError,
  onShowResults,
}) {
  const elapsed   = useElapsed(startTime, phase === 'racing');
  const orangeAt  = 90_000;   // 1.5 min
  const redAt     = 150_000;  // 2.5 min
  const timerColor = elapsed > redAt ? '#ef4444' : elapsed > orangeAt ? '#f59e0b' : '#a8c4ff';
  const timerPulse = elapsed > redAt;

  const bothDone  = manualState.submitted && (aiState.completedAt != null || aiState.error);
  const manDone   = manualState.submitted;
  const aiDone    = aiState.completedAt != null || !!aiState.error;

  /* Auto-show results 1.5 s after both done */
  const autoRef = useRef(null);
  useEffect(() => {
    if (bothDone && !autoRef.current) {
      autoRef.current = setTimeout(onShowResults, 1500);
    }
    return () => clearTimeout(autoRef.current);
  }, [bothDone]);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {phase === 'countdown' && <Countdown onDone={onCountdownEnd} />}

      {/* Top bar */}
      <div style={{
        background: 'var(--sidebar)',
        padding: '10px 20px',
        display: 'flex', alignItems: 'center', gap: 16,
        flexShrink: 0,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        {/* Timer */}
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 900,
          color: timerColor, flexShrink: 0, minWidth: 80, letterSpacing: '0.04em',
          animation: timerPulse ? 'timerPulse 0.8s ease-in-out infinite' : 'none',
          transition: 'color 0.5s',
        }}>
          {fmt(elapsed)}
        </div>

        {/* Question */}
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.3)',
            letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 3,
          }}>
            {question.topic}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#fff', lineHeight: 1.4 }}>
            {question.text}
          </div>
        </div>

        {/* Status + Results */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <div style={{
            display: 'flex', gap: 4, alignItems: 'center',
            fontFamily: 'var(--font-mono)', fontSize: 10,
          }}>
            <span style={{ color: manDone ? '#4ecca9' : '#f59e0b' }}>{manDone ? '✓' : '○'}</span>
            <span style={{ color: 'rgba(255,255,255,0.4)' }}>Human</span>
            <span style={{ color: 'rgba(255,255,255,0.2)', margin: '0 4px' }}>|</span>
            <span style={{ color: aiDone ? '#4ecca9' : '#f59e0b' }}>{aiDone ? '✓' : '○'}</span>
            <span style={{ color: 'rgba(255,255,255,0.4)' }}>AI</span>
          </div>

          <button
            onClick={onShowResults}
            style={{
              padding: '7px 16px',
              background: bothDone ? 'var(--primary)' : 'rgba(255,255,255,0.07)',
              color: bothDone ? '#fff' : 'rgba(255,255,255,0.25)',
              border: 'none', borderRadius: 999,
              fontSize: 12, fontWeight: 700,
              cursor: bothDone ? 'pointer' : 'default',
              boxShadow: bothDone ? '0 0 20px rgba(47,95,208,0.5)' : 'none',
              animation: bothDone ? 'glowPulse 1.2s ease-in-out infinite' : 'none',
              transition: 'all 0.3s',
            }}
          >
            {bothDone ? '🏁 Results!' : 'Waiting…'}
          </button>
        </div>
      </div>

      {/* Arena */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Left */}
        <div style={{
          flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column',
          borderRight: '1px solid rgba(255,255,255,0.06)',
          opacity: phase === 'countdown' ? 0.4 : 1,
          transition: 'opacity 0.5s',
        }}>
          <ManualSide
            cards={cards}
            manualState={manualState}
            question={question}
            onFlipCard={onFlipCard}
            onAnswer={onManualAnswer}
            onSubmit={onSubmitManual}
            onUseHint={onUseHint}
          />
        </div>

        {/* VS divider */}
        <div style={{
          width: 32, flexShrink: 0,
          background: 'var(--sidebar)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'linear-gradient(135deg, #2f5fd0, #1c3c8c)',
            color: '#fff', fontFamily: 'var(--font-mono)', fontSize: 9,
            fontWeight: 900, padding: '8px 3px', borderRadius: 6,
            letterSpacing: '0.08em', writingMode: 'vertical-rl',
            boxShadow: '0 0 16px rgba(47,95,208,0.5)',
            animation: 'vsGlow 2s ease-in-out infinite alternate',
          }}>
            VS
          </div>
        </div>

        {/* Right */}
        <div style={{
          flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column',
          opacity: phase === 'countdown' ? 0.4 : 1,
          transition: 'opacity 0.5s',
        }}>
          {phase === 'racing' && (
            <AISide
              question={question}
              aiState={aiState}
              onText={onAIText}
              onTools={onAITools}
              onDone={onAIDone}
              onError={onAIError}
            />
          )}
          {phase === 'countdown' && (
            <div style={{ flex: 1, background: '#0b1120', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'rgba(255,255,255,0.2)' }}>
                AI ready…
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes timerPulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
        @keyframes glowPulse  { 0%,100%{box-shadow:0 0 20px rgba(47,95,208,0.5)} 50%{box-shadow:0 0 36px rgba(47,95,208,0.9)} }
        @keyframes vsGlow     { from{box-shadow:0 0 8px rgba(47,95,208,0.4)} to{box-shadow:0 0 22px rgba(47,95,208,0.8)} }
      `}</style>
    </div>
  );
}
