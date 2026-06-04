export default function CPGCard({ card, index, isFlipped, onFlip, disabled }) {
  return (
    <div
      onClick={() => !disabled && !isFlipped && onFlip(card.id)}
      style={{
        perspective: 1000,
        height: 155,
        cursor: disabled ? 'default' : isFlipped ? 'default' : 'pointer',
      }}
    >
      <div style={{
        position: 'relative', width: '100%', height: '100%',
        transformStyle: 'preserve-3d',
        transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
      }}>

        {/* ── Front ── */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          background: 'var(--surface)',
          border: '2px solid var(--line)',
          borderRadius: 12, padding: '12px 14px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          boxShadow: '0 2px 8px rgba(27,36,54,0.07)',
          transition: 'border-color 0.15s, box-shadow 0.15s, transform 0.15s',
        }}
          onMouseEnter={e => {
            if (!isFlipped && !disabled) {
              e.currentTarget.style.borderColor = 'var(--primary)';
              e.currentTarget.style.boxShadow = '0 0 0 3px rgba(47,95,208,0.12), 0 4px 16px rgba(27,36,54,0.12)';
              e.currentTarget.style.transform = 'translateY(-3px)';
            }
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = 'var(--line)';
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(27,36,54,0.07)';
            e.currentTarget.style.transform = 'translateY(0)';
          }}
        >
          {/* Card number badge */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <div style={{
              width: 24, height: 24, borderRadius: 6, flexShrink: 0,
              background: 'var(--primary-soft)', color: 'var(--primary-ink)',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 800,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {index + 1}
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 9,
              color: 'var(--primary)', letterSpacing: '0.06em',
              textTransform: 'uppercase', opacity: 0.7,
            }}>
              📖 CPG
            </div>
          </div>

          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.3, marginBottom: 3 }}>
              {card.cpg}
            </div>
            <div style={{ fontSize: 11, color: 'var(--ink-soft)' }}>
              {card.section}
            </div>
          </div>

          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
            padding: '5px', background: 'var(--primary-soft)', borderRadius: 8,
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--primary-ink)', fontWeight: 600,
          }}>
            Click to flip ↓
          </div>
        </div>

        {/* ── Back ── */}
        <div style={{
          position: 'absolute', inset: 0,
          backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
          transform: 'rotateY(180deg)',
          background: '#f0f4ff',
          border: '2px solid var(--primary)',
          borderRadius: 12, padding: '10px 12px',
          overflowY: 'auto',
          boxShadow: '0 0 0 3px rgba(47,95,208,0.1)',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 8.5,
            color: 'var(--primary)', letterSpacing: '0.07em',
            textTransform: 'uppercase', marginBottom: 5, fontWeight: 700,
          }}>
            {card.section}
          </div>
          <p style={{ fontSize: 11.5, color: 'var(--ink)', lineHeight: 1.65 }}>
            {card.summary ?? card.paragraph}
          </p>
        </div>
      </div>
    </div>
  );
}
