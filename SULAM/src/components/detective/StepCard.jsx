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
      padding: '16px 18px',
      transition: 'all 0.3s ease',
      opacity: status === 'pending' ? 0.55 : 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontWeight: 600, fontSize: 15, color: 'var(--ink)' }}>{title}</span>
            <Icon
              size={15}
              color={cfg.color}
              style={{ animation: isRunning ? 'spin 1.2s linear infinite' : 'none', flexShrink: 0 }}
            />
            <span className="chip" style={{
              marginLeft: 'auto',
              background: cfg.bg,
              color: cfg.color,
              border: `1px solid ${cfg.color}`,
              fontSize: 10,
            }}>
              {cfg.label}
            </span>
          </div>

          {/* Caption / agentic label */}
          {caption && (
            <div className="mono-label" style={{ marginBottom: 8, color: 'var(--heath)' }}>
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
