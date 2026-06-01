/* Option 1 — Structured tables, now organized into tabbed SUB-SECTIONS.
   One card: header + segmented control (Procedures / Monitoring / Lifestyle);
   the active sub-section renders as an aligned, column-based table. */
function CareMonitoringPanel() {
  const D = window.CM_DATA;
  const C = window.C;
  const [rev, toggle] = window.useReviewSet();
  const [active, setActive] = React.useState('proc');

  const tabs = [
    { key: 'proc', label: 'Procedures', icon: window.IStethoscope, n: D.procedures.length },
    { key: 'mon',  label: 'Monitoring', icon: window.IActivity,    n: D.monitoring.length },
    { key: 'life', label: 'Lifestyle',  icon: window.IHeart,       n: D.lifestyle.length },
  ];
  const total = D.procedures.length + D.monitoring.length + D.lifestyle.length;

  const Th = ({ children, style }) => (
    <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase',
      color: C.faint, paddingBottom: 10, ...style }}>{children}</div>
  );
  const Row = ({ children, cols, last }) => (
    <div className="cm-row" style={{ display: 'grid', gridTemplateColumns: cols, gap: 16, alignItems: 'start',
      padding: '14px 0', borderBottom: last ? 'none' : `1px solid ${C.line2}` }}>{children}</div>
  );

  const PROC_COLS = '22px 168px minmax(0,1fr) 110px 30px';
  const MON_COLS  = '22px 150px minmax(0,1fr) 172px';

  function ProcedureRow({ p, last }) {
    const [open, setOpen] = React.useState(false);
    return (
      <div style={{ borderBottom: last ? 'none' : `1px solid ${C.line2}` }}>
        <div className="cm-row" style={{ display: 'grid', gridTemplateColumns: PROC_COLS, gap: 16,
          alignItems: 'start', padding: '14px 0' }}>
          <window.ReviewBox checked={rev.has(p.id)} onClick={() => toggle(p.id)} />
          <div style={{ fontSize: 14.5, fontWeight: 600, color: C.ink, lineHeight: 1.3 }}>{p.name}</div>
          <div style={{ fontSize: 12.5, color: C.muted, lineHeight: 1.5 }}>{p.detail}</div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 1 }}>
            <window.UrgencyPill value={p.urgency} />
          </div>
          {p.note ? (
            <button onClick={() => setOpen((v) => !v)} aria-expanded={open} title="AI-suggested reason"
              style={{ width: 26, height: 26, borderRadius: 8, border: `1px solid ${open ? C.teal : C.line}`,
                background: open ? C.tealSoft : '#fff', color: open ? C.tealInk : C.faint, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', justifySelf: 'end',
                transition: 'all .15s ease' }}>
              <window.IChevronDown size={15} sw={2}
                style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .18s ease' }} />
            </button>
          ) : <div />}
        </div>
        {open && p.note && (
          <div style={{ margin: '0 0 14px 206px', padding: '11px 14px', background: '#f8fafc',
            border: `1px solid ${C.line}`, borderLeft: `2.5px solid ${C.teal}`, borderRadius: 10 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase',
              color: C.tealInk, marginBottom: 5 }}>AI-suggested reason</div>
            <div style={{ fontSize: 12.5, color: C.ink2, lineHeight: 1.55 }}>{p.note}</div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ ...window.cardStyle, maxWidth: 820, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ padding: '18px 22px 16px', borderBottom: `1px solid ${C.line}` }}>
        <window.SectionHead icon={window.IActivity} title="Care & Monitoring" count={total} />
        {/* Segmented control */}
        <div style={{ display: 'flex', gap: 4, marginTop: 16, background: C.line2, padding: 4, borderRadius: 12 }}>
          {tabs.map((t) => {
            const on = active === t.key;
            return (
              <button key={t.key} onClick={() => setActive(t.key)} style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '9px 10px', borderRadius: 9, border: 'none', cursor: 'pointer',
                background: on ? '#fff' : 'transparent',
                boxShadow: on ? '0 1px 2px rgba(15,23,42,.10)' : 'none',
                color: on ? C.ink : C.muted, fontSize: 13.5, fontWeight: 600, transition: 'all .15s ease',
              }}>
                <t.icon size={15} sw={1.8} style={{ color: on ? C.tealInk : C.faint }} />
                {t.label}
                <span style={{ fontSize: 11.5, fontWeight: 600, padding: '1px 7px', borderRadius: 999,
                  background: on ? C.tealSoft : '#fff', color: on ? C.tealInk : C.faint }}>{t.n}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active sub-section table */}
      <div style={{ padding: '14px 22px 10px' }}>
        {/* PROCEDURES */}
        {active === 'proc' && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: PROC_COLS, gap: 16, borderBottom: `1px solid ${C.line}` }}>
              <Th>{''}</Th><Th>Procedure</Th><Th>Rationale</Th><Th style={{ textAlign: 'right' }}>When</Th><Th>{''}</Th>
            </div>
            {D.procedures.map((p, i) => (
              <ProcedureRow key={p.id} p={p} last={i === D.procedures.length - 1} />
            ))}
          </>
        )}

        {/* MONITORING */}
        {active === 'mon' && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: MON_COLS, gap: 16, borderBottom: `1px solid ${C.line}` }}>
              <Th>{''}</Th><Th>Test</Th><Th>Schedule</Th><Th>Target</Th>
            </div>
            {D.monitoring.map((m, i) => (
              <Row key={m.id} cols={MON_COLS} last={i === D.monitoring.length - 1}>
                <window.ReviewBox checked={rev.has(m.id)} onClick={() => toggle(m.id)} />
                <div>
                  <div style={{ fontSize: 14.5, fontWeight: 600, color: C.ink, lineHeight: 1.3 }}>{m.test}</div>
                  {m.sub && <div style={{ fontSize: 11.5, color: C.faint, marginTop: 2 }}>{m.sub}</div>}
                </div>
                <div style={{ paddingTop: 1 }}><window.ScheduleText>{m.schedule}</window.ScheduleText></div>
                <div style={{ fontSize: 12.5, color: m.target ? C.ink2 : C.faint, lineHeight: 1.45, paddingTop: 2 }}>
                  {m.target || '—'}
                </div>
              </Row>
            ))}
          </>
        )}

        {/* LIFESTYLE — card grid */}
        {active === 'life' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, padding: '4px 0 8px' }}>
            {D.lifestyle.map((l) => {
              const Ico = window.CAT_ICON[l.category] || window.IHeart;
              const on = rev.has(l.id);
              return (
                <div key={l.id} style={{ display: 'flex', gap: 12, alignItems: 'flex-start',
                  padding: '14px 15px', background: '#fcfdfd', border: `1px solid ${on ? C.teal : C.line}`,
                  borderRadius: 14, transition: 'border-color .15s ease' }}>
                  <window.IconChip icon={Ico} tone="teal" size={32} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '.05em', textTransform: 'uppercase',
                      color: C.tealInk, marginBottom: 4 }}>{l.category}</div>
                    <div style={{ fontSize: 13, color: C.ink2, lineHeight: 1.45 }}>{l.goal}</div>
                  </div>
                  <window.ReviewBox checked={on} onClick={() => toggle(l.id)} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
window.CareMonitoringPanel = CareMonitoringPanel;
