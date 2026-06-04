import { useEffect, useRef } from 'react';

export default function ThinkingBox({ text, isActive }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [text]);

  if (!text && !isActive) return null;

  return (
    <div style={{
      background: '#0f1520',
      border: '1px solid rgba(47,95,208,0.25)',
      borderRadius: 'var(--r-md)',
      padding: '12px 14px',
      marginTop: 10,
      maxHeight: 180,
      overflowY: 'auto',
    }} ref={scrollRef}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'rgba(255,255,255,0.35)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        marginBottom: 6,
      }}>
        AI Reasoning
      </div>
      <pre style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: '#a8c4ff',
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        margin: 0,
      }}>
        {text}
        {isActive && <span style={{ animation: 'blink 1s step-end infinite' }}>▋</span>}
      </pre>
      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
}
