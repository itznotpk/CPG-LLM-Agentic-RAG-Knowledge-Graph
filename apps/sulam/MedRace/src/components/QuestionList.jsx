import { QUESTIONS } from '../data/questions.js';
import { ChevronLeft, BookOpen, Bot } from 'lucide-react';

const TOPIC_COLORS = {
  Hypertension:  { bg: '#fce8e8', ink: '#c0433f', border: '#f5b8b8' },
  Dyslipidaemia: { bg: '#fff7e6', ink: '#b4843a', border: '#f5d898' },
  'Heart Failure':{ bg: '#e8f0fe', ink: '#2f5fd0', border: '#b4c8f8' },
};

function topicColor(topic) {
  for (const key of Object.keys(TOPIC_COLORS)) {
    if (topic.startsWith(key)) return TOPIC_COLORS[key];
  }
  return { bg: '#eef1f8', ink: '#5b6273', border: '#e3e6ee' };
}

export default function QuestionList({ mode, onSelectQuestion, onBack }) {
  const Icon = mode === 'ai' ? Bot : BookOpen;
  const modeLabel = mode === 'ai' ? 'AI Assistant' : 'Manual';
  const modeColor = mode === 'ai' ? '#8b86a8' : '#2f5fd0';

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        background: 'var(--sidebar)', padding: '16px 28px',
        display: 'flex', alignItems: 'center', gap: 16,
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button onClick={onBack} style={{
          background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 8, color: '#fff', padding: '6px 12px',
          display: 'flex', alignItems: 'center', gap: 6, fontSize: 13,
          cursor: 'pointer', transition: 'background 0.15s',
        }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.14)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
        >
          <ChevronLeft size={15} /> Back
        </button>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 2 }}>
            MedRace · Question Bank
          </div>
          <div style={{ color: '#fff', fontWeight: 700, fontSize: 17 }}>
            Pick a question
          </div>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 999, padding: '5px 12px',
          fontSize: 12, color: 'rgba(255,255,255,0.7)',
        }}>
          <Icon size={13} color={modeColor} />
          {modeLabel} mode
        </div>
      </div>

      {/* List */}
      <div style={{ flex: 1, maxWidth: 780, width: '100%', margin: '0 auto', padding: '28px 24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {QUESTIONS.map((q, i) => {
            const tc = topicColor(q.topic);
            return (
              <button
                key={q.id}
                onClick={() => onSelectQuestion(q.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 16,
                  background: 'var(--surface)', border: '1.5px solid var(--line)',
                  borderRadius: 12, padding: '16px 20px', textAlign: 'left',
                  cursor: 'pointer', transition: 'all 0.18s', width: '100%',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--primary)';
                  e.currentTarget.style.boxShadow = '0 0 0 3px rgba(47,95,208,0.1), 0 4px 16px rgba(27,36,54,0.1)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--line)';
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.transform = 'none';
                }}
              >
                {/* Number */}
                <div style={{
                  width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                  background: 'var(--primary-soft)', color: 'var(--primary-ink)',
                  fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 800,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {i + 1}
                </div>

                {/* Text */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', lineHeight: 1.4, marginBottom: 5 }}>
                    {q.text}
                  </div>
                  <div style={{
                    display: 'inline-block',
                    fontSize: 10, fontWeight: 700,
                    fontFamily: 'var(--font-mono)', letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    background: tc.bg, color: tc.ink,
                    border: `1px solid ${tc.border}`,
                    borderRadius: 6, padding: '2px 8px',
                  }}>
                    {q.topic}
                  </div>
                </div>

                <div style={{ color: 'var(--primary)', fontSize: 18, flexShrink: 0, opacity: 0.5 }}>›</div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
