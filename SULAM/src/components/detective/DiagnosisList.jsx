export default function DiagnosisList({ differentials, cpgsMatched }) {
  if (!differentials || differentials.length === 0) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <div className="mono-label" style={{ marginBottom: 8 }}>Differential Diagnoses</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {differentials.slice(0, 5).map((d, i) => (
          <div key={d.id} style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '9px 12px',
            borderRadius: 'var(--r-md)',
            background: i === 0 ? 'var(--primary-soft)' : 'var(--surface-soft)',
            border: `1px solid ${i === 0 ? 'var(--primary)' : 'var(--line)'}`,
          }}>
            {/* probability bar */}
            <div style={{ flex: '0 0 44px', position: 'relative', height: 6, background: 'var(--line)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                position: 'absolute', left: 0, top: 0, height: '100%',
                width: `${d.probability}%`,
                background: i === 0 ? 'var(--primary)' : 'var(--heath)',
                borderRadius: 3,
                transition: 'width 0.6s ease',
              }} />
            </div>

            <div style={{ flex: 1 }}>
              <div style={{
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                fontWeight: i === 0 ? 600 : 400,
                color: i === 0 ? 'var(--primary-ink)' : 'var(--ink)',
              }}>
                {d.name}
                {i === 0 && (
                  <span style={{
                    marginLeft: 8,
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: 'var(--primary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                  }}>
                    Prime Suspect
                  </span>
                )}
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-soft)', marginTop: 1 }}>
                {d.icdCode}
              </div>
            </div>

            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              fontWeight: 600,
              color: i === 0 ? 'var(--primary)' : 'var(--ink-soft)',
            }}>
              {d.probability}%
            </div>
          </div>
        ))}
      </div>

      {cpgsMatched && cpgsMatched.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="mono-label" style={{ marginBottom: 6 }}>Guidelines Activated</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {cpgsMatched.map((cpg, i) => (
              <span key={i} className="chip chip-primary" style={{
                animation: `fadeSlideIn 0.3s ease both`,
                animationDelay: `${i * 80}ms`,
              }}>
                📖 {cpg}
              </span>
            ))}
          </div>
        </div>
      )}
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
