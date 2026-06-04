import { Loader, CheckCircle, Circle, AlertCircle } from 'lucide-react';

const STATUS_CONFIG = {
  pending:  { icon: Circle,       color: 'var(--ink-soft)',  bg: 'var(--surface)',      label: 'Waiting' },
  running:  { icon: Loader,       color: 'var(--primary)',   bg: 'var(--primary-soft)', label: 'Running' },
  complete: { icon: CheckCircle,  color: '#2a9d6c',          bg: '#e8f7f1',             label: 'Done' },
  error:    { icon: AlertCircle,  color: 'var(--err)',       bg: 'var(--err-soft)',     label: 'Error' },
};

export default function StepCard({ stepNumber, title, caption, status, detail, children }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const Icon = cfg.icon;
  const isRunning = status === 'running';

  return (
    <div style={{
      background: cfg.bg,
      border: `1px solid ${status === 'running' ? 'var(--primary)' : status === 'complete' ? '#b7e5d2' : 'var(--line)'}`,
      borderRadius: 'var(--r-lg)',
      padding: '20px 22px',
      transition: 'all 0.3s ease',
      opacity: status === 'pending' ? 0.55 : 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
        {/* Step number + icon */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flexShrink: 0, paddingTop: 2 }}>
          <div style={{
            width: 28, height: 28,
            borderRadius: '50%',
            background: status === 'pending' ? 'var(--line)' : cfg.color,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            fontWeight: 700,
            flexShrink: 0,
          }}>
            {stepNumber}
          </div>
        </div>

        <div style={{ flex: 1 }}>
          {/* Header row */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 6 }}>
            <span style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: 20,
              color: 'var(--ink)',
              lineHeight: 1.2,
              flex: 1,
            }}>{title}</span>
            <Icon
              size={16}
              color={cfg.color}
              style={{ animation: isRunning ? 'spin 1.2s linear infinite' : 'none', flexShrink: 0, marginTop: 2 }}
            />
            <span className="chip" style={{
              marginLeft: 'auto',
              background: cfg.bg,
              color: cfg.color,
              border: `1px solid ${cfg.color}`,
              fontSize: 10,
              flexShrink: 0,
            }}>
              {cfg.label}
            </span>
          </div>

          {/* Caption / agentic label */}
          {caption && (
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              fontWeight: 500,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: 'var(--heath)',
              marginBottom: 10,
              lineHeight: 1.4,
            }}>
              {caption}
            </div>
          )}

          {/* Live detail text */}
          {detail && (
            <div style={{ fontSize: 13, color: 'var(--ink-soft)', lineHeight: 1.5, marginBottom: children ? 8 : 0 }}>
              {detail}
            </div>
          )}

          {children}
        </div>
      </div>

      <style>{`@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`}</style>
    </div>
  );
}
