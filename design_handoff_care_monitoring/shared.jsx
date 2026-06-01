/* Shared primitives + palette for all four variations. Exported to window. */
const C = {
  ink:   '#1e293b',  // slate-800 — titles
  ink2:  '#334155',  // slate-700 — body
  muted: '#64748b',  // slate-500 — de-emphasized detail
  faint: '#94a3b8',  // slate-400
  line:  '#e2e8f0',  // slate-200
  line2: '#f1f5f9',  // slate-100
  surface: '#ffffff',
  teal:  'var(--accent-primary)',
  tealInk: '#0f766e',           // teal-700 readable on white
  tealSoft: 'rgba(20,184,166,0.12)',
  red: '#dc2626', redSoft: '#fee2e2', redInk: '#b91c1c',
  amber: '#d97706', amberSoft: '#fef3c7', amberInk: '#b45309',
  slateChip: '#f1f5f9', slateChipInk: '#64748b',
};
window.C = C;

const cardStyle = {
  background: C.surface,
  border: `1px solid ${C.line}`,
  borderRadius: 'var(--radius-lg)',
  boxShadow: '0 1px 2px rgba(15,23,42,.04), 0 12px 28px -14px rgba(15,23,42,.14)',
  overflow: 'hidden',
};
window.cardStyle = cardStyle;

function IconChip({ icon: Icon, tone = 'teal', size = 34 }) {
  const tones = {
    teal: { bg: C.tealSoft, fg: C.tealInk },
    amber:{ bg: C.amberSoft, fg: C.amberInk },
    slate:{ bg: C.slateChip, fg: C.slateChipInk },
  };
  const t = tones[tone] || tones.teal;
  return (
    <div style={{ width: size, height: size, borderRadius: 11, background: t.bg, color: t.fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <Icon size={17} sw={1.7} />
    </div>
  );
}
window.IconChip = IconChip;

function CountPill({ n, tone = 'slate' }) {
  const tones = {
    slate: { bg: C.slateChip, fg: C.slateChipInk },
    teal:  { bg: C.tealSoft, fg: C.tealInk },
  };
  const t = tones[tone] || tones.slate;
  return (
    <span style={{ fontSize: 12, fontWeight: 600, padding: '2px 9px', borderRadius: 999,
      background: t.bg, color: t.fg, fontVariantNumeric: 'tabular-nums' }}>{n}</span>
  );
}
window.CountPill = CountPill;

function SectionHead({ icon, title, count, tone = 'teal', right, style }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, ...style }}>
      <IconChip icon={icon} tone={tone} />
      <h3 style={{ margin: 0, fontSize: 17, fontWeight: 600, letterSpacing: '-0.01em', color: C.ink }}>{title}</h3>
      {count != null && <CountPill n={count} />}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>{right}</div>
    </div>
  );
}
window.SectionHead = SectionHead;

/* Urgency → tone mapping for procedures */
function urgencyTone(u) {
  if (u === 'Today') return { bg: C.redSoft, fg: C.redInk, label: 'Today' };
  if (u === 'This admission') return { bg: C.amberSoft, fg: C.amberInk, label: 'This admission' };
  return { bg: C.slateChip, fg: C.slateChipInk, label: u };
}
window.urgencyTone = urgencyTone;

function UrgencyPill({ value }) {
  const t = urgencyTone(value);
  return (
    <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.02em', padding: '3px 10px',
      borderRadius: 999, background: t.bg, color: t.fg, whiteSpace: 'nowrap' }}>{t.label}</span>
  );
}
window.UrgencyPill = UrgencyPill;

/* Small teal schedule chip with clock */
function ScheduleText({ children, mono }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: C.tealInk,
      fontSize: 13, fontWeight: 500, lineHeight: 1.35 }}>
      <span>{children}</span>
    </span>
  );
}
window.ScheduleText = ScheduleText;

/* Reviewed checkbox (controlled) */
function ReviewBox({ checked, onClick }) {
  return (
    <button onClick={onClick} aria-pressed={checked} style={{
      width: 20, height: 20, borderRadius: 6, flexShrink: 0, cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0,
      border: checked ? 'none' : `1.5px solid ${C.line}`,
      background: checked ? C.teal : '#fff',
      color: '#fff', transition: 'all .15s ease',
    }}>
      {checked && <window.ICheck size={13} sw={3} />}
    </button>
  );
}
window.ReviewBox = ReviewBox;

window.useReviewSet = function (ids) {
  const [set, setSet] = React.useState(() => new Set());
  const toggle = (id) => setSet((prev) => {
    const n = new Set(prev);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });
  return [set, toggle];
};
