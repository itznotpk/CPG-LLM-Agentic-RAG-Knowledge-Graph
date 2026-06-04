import { Search, Network, FlaskConical } from 'lucide-react';

const ICONS = {
  detective:    Search,
  architecture: Network,
  graph:        FlaskConical,
};

const TAB_ICONS = { detective: Search, architecture: Network, graph: FlaskConical };

export default function Sidebar({ tabs, activeTab, onTabChange }) {
  return (
    <aside style={{
      width: 220,
      minWidth: 220,
      background: 'var(--sidebar)',
      display: 'flex',
      flexDirection: 'column',
      padding: '28px 0',
      gap: 4,
    }}>
      {/* Logo area */}
      <div style={{ padding: '0 20px 28px' }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 22,
          fontWeight: 700,
          color: '#fff',
          letterSpacing: '-0.01em',
        }}>
          SULAM
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.38)',
          marginTop: 3,
        }}>
          Medical AI Demo
        </div>
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, padding: '0 10px' }}>
        {tabs.map(tab => {
          const Icon = TAB_ICONS[tab.id] || Search;
          const active = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 'var(--r-md)',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-body)',
                fontSize: 14,
                fontWeight: active ? 600 : 400,
                color: active ? 'var(--primary-soft)' : 'rgba(255,255,255,0.55)',
                background: active ? 'rgba(47,95,208,0.18)' : 'transparent',
                transition: 'all 0.15s',
                textAlign: 'left',
                width: '100%',
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
            >
              <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div style={{ padding: '0 20px', marginTop: 'auto' }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'rgba(255,255,255,0.22)',
          letterSpacing: '0.06em',
        }}>
          Agentic RAG · CPG-LLM
        </div>
      </div>
    </aside>
  );
}
