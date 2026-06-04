export default function CaseCard({ caseData, isSelected, isDisabled, onClick }) {
  return (
    <button
      onClick={() => !isDisabled && onClick(caseData)}
      style={{
        width: '100%',
        background: isSelected ? 'var(--primary-soft)' : 'var(--surface)',
        border: `2px solid ${isSelected ? 'var(--primary)' : 'var(--line)'}`,
        borderRadius: 'var(--r-lg)',
        padding: '16px 18px',
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        textAlign: 'left',
        transition: 'all 0.18s',
        opacity: isDisabled ? 0.6 : 1,
        boxShadow: isSelected ? '0 0 0 3px rgba(47,95,208,0.15)' : 'var(--shadow-sm)',
      }}
      onMouseEnter={e => { if (!isSelected && !isDisabled) e.currentTarget.style.borderColor = 'var(--primary)'; }}
      onMouseLeave={e => { if (!isSelected && !isDisabled) e.currentTarget.style.borderColor = 'var(--line)'; }}
    >
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 17,
        fontWeight: 700,
        color: isSelected ? 'var(--primary-ink)' : 'var(--ink)',
        marginBottom: 4,
      }}>
        {caseData.displayName}
      </div>

      <div style={{ marginBottom: 8 }}>
        <span className="chip chip-heath" style={{ fontSize: 10 }}>
          {caseData.tag}
        </span>
      </div>

      <div style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        color: isSelected ? 'var(--primary-ink)' : 'var(--ink-soft)',
        lineHeight: 1.4,
      }}>
        {caseData.blurb}
      </div>

      {isSelected && (
        <div style={{
          marginTop: 10,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--primary)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}>
          ● Investigating…
        </div>
      )}
    </button>
  );
}
