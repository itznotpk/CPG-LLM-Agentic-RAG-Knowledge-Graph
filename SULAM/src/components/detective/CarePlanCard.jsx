function CpgBadge({ source }) {
  if (!source) return null;
  return (
    <div style={{
      marginTop: 4,
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      color: 'var(--primary)',
      display: 'flex',
      alignItems: 'center',
      gap: 4,
    }}>
      📖 <span style={{ color: 'var(--ink-soft)' }}>{source}</span>
    </div>
  );
}

function Section({ title, items, renderItem }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginBottom: 18 }}>
      <div className="mono-label" style={{ marginBottom: 8, color: 'var(--heath-ink)' }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map((item, i) => renderItem(item, i))}
      </div>
    </div>
  );
}

export default function CarePlanCard({ carePlan }) {
  if (!carePlan) return null;

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      padding: '20px 22px',
      marginTop: 12,
      animation: 'fadeIn 0.4s ease',
    }}>
      {/* Summary */}
      {carePlan.summary && (
        <div style={{
          padding: '12px 14px',
          background: 'var(--surface-soft)',
          borderRadius: 'var(--r-md)',
          marginBottom: 18,
          fontFamily: 'var(--font-body)',
          fontSize: 14,
          color: 'var(--ink)',
          lineHeight: 1.6,
          borderLeft: '3px solid var(--primary)',
        }}>
          {carePlan.summary}
        </div>
      )}

      <Section
        title="Medications"
        items={carePlan.medications}
        renderItem={(m, i) => (
          <div key={i} style={{ padding: '10px 12px', background: 'var(--surface-soft)', borderRadius: 'var(--r-md)', border: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                textTransform: 'uppercase',
                padding: '2px 7px',
                borderRadius: 999,
                background: m.action === 'start' ? 'var(--ok-soft)' : m.action === 'stop' ? 'var(--err-soft)' : 'var(--heath-soft)',
                color: m.action === 'start' ? 'var(--primary-ink)' : m.action === 'stop' ? 'var(--err)' : 'var(--heath-ink)',
              }}>
                {m.action}
              </span>
              <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>{m.name}</span>
            </div>
            {m.rationale && <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>{m.rationale}</div>}
            <CpgBadge source={m.cpgSource} />
          </div>
        )}
      />

      <Section
        title="Lifestyle Advice"
        items={carePlan.lifestyle}
        renderItem={(l, i) => (
          <div key={i} style={{ padding: '10px 12px', background: 'var(--surface-soft)', borderRadius: 'var(--r-md)', border: '1px solid var(--line)' }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>🥗 {l.goal}</div>
            {l.rationale && <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>{l.rationale}</div>}
            <CpgBadge source={l.cpgSource} />
          </div>
        )}
      />

      <Section
        title="Referrals"
        items={carePlan.referrals}
        renderItem={(r, i) => (
          <div key={i} style={{ padding: '10px 12px', background: 'var(--surface-soft)', borderRadius: 'var(--r-md)', border: '1px solid var(--line)' }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>🏥 {r.specialty}</div>
            {r.reason && <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>{r.reason}</div>}
            <CpgBadge source={r.cpgSource} />
          </div>
        )}
      />

      <Section
        title="Investigations"
        items={carePlan.investigations}
        renderItem={(inv, i) => (
          <div key={i} style={{ padding: '10px 12px', background: 'var(--surface-soft)', borderRadius: 'var(--r-md)', border: '1px solid var(--line)' }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>🔬 {inv.name}</div>
            {inv.rationale && <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>{inv.rationale}</div>}
            <CpgBadge source={inv.cpgSource} />
          </div>
        )}
      />

      {carePlan.redFlags && carePlan.redFlags.length > 0 && (
        <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--err-soft)', borderRadius: 'var(--r-md)', border: '1px solid rgba(192,67,63,0.2)' }}>
          <div className="mono-label" style={{ color: 'var(--err)', marginBottom: 6 }}>⚠ Red Flags</div>
          {carePlan.redFlags.map((flag, i) => (
            <div key={i} style={{ fontSize: 13, color: 'var(--err)', marginBottom: 2 }}>• {flag}</div>
          ))}
        </div>
      )}

      <style>{`@keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }`}</style>
    </div>
  );
}
