function CpgBadge({ source, grade }) {
  if (!source && !grade) return null;
  return (
    <div style={{
      marginTop: 4,
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      color: 'var(--primary)',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      flexWrap: 'wrap',
    }}>
      {source && <span>📖 <span style={{ color: 'var(--ink-soft)' }}>{source}</span></span>}
      {grade && <span style={{ padding: '1px 6px', borderRadius: 999, background: 'var(--heath-soft)', color: 'var(--heath-ink)' }}>Grade {grade}</span>}
    </div>
  );
}

function SectionHeader({ n, title }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: 'var(--primary)',
        padding: '2px 7px',
        borderRadius: 999,
        background: 'var(--primary-soft, var(--surface-soft))',
        border: '1px solid var(--line)',
      }}>
        SECTION {n}
      </span>
      <span className="mono-label" style={{ color: 'var(--heath-ink)' }}>{title}</span>
    </div>
  );
}

function SectionWrapper({ n, title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <SectionHeader n={n} title={title} />
      {children}
    </div>
  );
}

function ItemCard({ children }) {
  return (
    <div style={{
      padding: '10px 12px',
      background: 'var(--surface-soft)',
      borderRadius: 'var(--r-md)',
      border: '1px solid var(--line)',
    }}>
      {children}
    </div>
  );
}

function ActionPill({ action }) {
  const tone =
    action === 'start' ? { bg: 'var(--ok-soft)', fg: 'var(--primary-ink)' } :
    action === 'stop' || action === 'contraindicated' ? { bg: 'var(--err-soft)', fg: 'var(--err)' } :
    { bg: 'var(--heath-soft)', fg: 'var(--heath-ink)' };
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      textTransform: 'uppercase',
      padding: '2px 7px',
      borderRadius: 999,
      background: tone.bg,
      color: tone.fg,
    }}>
      {action}
    </span>
  );
}

function RecommendationGroup({ label, icon, items, renderTitle }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        textTransform: 'uppercase',
        color: 'var(--ink-soft)',
        marginBottom: 6,
        letterSpacing: '0.04em',
      }}>
        {icon} {label}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((item, i) => (
          <ItemCard key={i}>
            {renderTitle(item)}
            {item.rationale && (
              <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>{item.rationale}</div>
            )}
            <CpgBadge source={item.cpgSource} grade={item.evidenceGrade} />
          </ItemCard>
        ))}
      </div>
    </div>
  );
}

export default function CarePlanCard({ carePlan }) {
  if (!carePlan) return null;

  const hasRecommendations =
    (carePlan.medications?.length || 0) +
    (carePlan.lifestyle?.length || 0) +
    (carePlan.referrals?.length || 0) +
    (carePlan.investigations?.length || 0) > 0;

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      padding: '20px 22px',
      marginTop: 12,
      animation: 'fadeIn 0.4s ease',
    }}>
      {/* SECTION 1 — Clinical Assessment */}
      <SectionWrapper n={1} title="Clinical Assessment">
        {carePlan.summary ? (
          <div style={{
            padding: '12px 14px',
            background: 'var(--surface-soft)',
            borderRadius: 'var(--r-md)',
            fontFamily: 'var(--font-body)',
            fontSize: 14,
            color: 'var(--ink)',
            lineHeight: 1.6,
            borderLeft: '3px solid var(--primary)',
          }}>
            {carePlan.summary}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No assessment summary returned.</div>
        )}
      </SectionWrapper>

      {/* SECTION 2 — Recommendations */}
      <SectionWrapper n={2} title="Recommendations">
        {hasRecommendations ? (
          <>
            <RecommendationGroup
              label="Pharmacological"
              icon="💊"
              items={carePlan.medications}
              renderTitle={(m) => (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <ActionPill action={m.action || 'start'} />
                  <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>{m.name}</span>
                </div>
              )}
            />
            <RecommendationGroup
              label="Investigations & Procedures"
              icon="🔬"
              items={carePlan.investigations}
              renderTitle={(inv) => (
                <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>{inv.name}</div>
              )}
            />
            <RecommendationGroup
              label="Lifestyle"
              icon="🥗"
              items={carePlan.lifestyle}
              renderTitle={(l) => (
                <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>{l.goal}</div>
              )}
            />
            <RecommendationGroup
              label="Referrals"
              icon="🏥"
              items={carePlan.referrals}
              renderTitle={(r) => (
                <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>{r.specialty}</div>
              )}
            />
          </>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No recommendations returned.</div>
        )}
      </SectionWrapper>

      {/* SECTION 3 — Monitoring */}
      <SectionWrapper n={3} title="Monitoring">
        {carePlan.monitoring && carePlan.monitoring.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {carePlan.monitoring.map((m, i) => (
              <ItemCard key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>📊 {m.parameter}</div>
                  {m.schedule && (
                    <span className="chip" style={{ fontSize: 11 }}>{m.schedule}</span>
                  )}
                </div>
                {m.target && (
                  <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>Target: {m.target}</div>
                )}
                <CpgBadge source={m.cpgRef} />
              </ItemCard>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No monitoring parameters retrieved.</div>
        )}
      </SectionWrapper>

      {/* SECTION 4 — Red Flags */}
      <SectionWrapper n={4} title="Red Flags">
        {carePlan.redFlags && carePlan.redFlags.length > 0 ? (
          <div style={{
            padding: '10px 14px',
            background: 'var(--err-soft)',
            borderRadius: 'var(--r-md)',
            border: '1px solid rgba(192,67,63,0.2)',
          }}>
            {carePlan.redFlags.map((flag, i) => (
              <div key={i} style={{ fontSize: 13, color: 'var(--err)', marginBottom: 2 }}>⚠ {flag}</div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No escalation criteria retrieved.</div>
        )}
      </SectionWrapper>

      {/* SECTION 5 — Follow-up */}
      <SectionWrapper n={5} title="Follow-up">
        {carePlan.followUp && carePlan.followUp.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {carePlan.followUp.map((f, i) => {
              const colonIdx = f.indexOf(':');
              const timeline = colonIdx >= 0 ? f.slice(0, colonIdx).trim() : null;
              const body = colonIdx >= 0 ? f.slice(colonIdx + 1).trim() : f;
              return (
                <ItemCard key={i}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    {timeline && (
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        padding: '2px 7px',
                        borderRadius: 999,
                        background: 'var(--heath-soft)',
                        color: 'var(--heath-ink)',
                        flexShrink: 0,
                        marginTop: 2,
                      }}>
                        🗓 {timeline}
                      </span>
                    )}
                    <span style={{ fontSize: 13, color: 'var(--ink)' }}>{body}</span>
                  </div>
                </ItemCard>
              );
            })}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No follow-up plan returned.</div>
        )}
      </SectionWrapper>

      {/* SECTION 6 — Unresolved Questions */}
      <SectionWrapper n={6} title="Unresolved Questions">
        {carePlan.unresolvedQuestions && carePlan.unresolvedQuestions.length > 0 ? (
          <ul style={{
            margin: 0,
            paddingLeft: 18,
            fontSize: 13,
            color: 'var(--ink-soft)',
            lineHeight: 1.6,
          }}>
            {carePlan.unresolvedQuestions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>None — all clinical decisions were grounded in retrieved evidence.</div>
        )}
      </SectionWrapper>

      <style>{`@keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }`}</style>
    </div>
  );
}
