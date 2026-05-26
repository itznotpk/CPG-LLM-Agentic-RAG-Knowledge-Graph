import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Search,
  LayoutDashboard,
  Users,
  Stethoscope,
  BarChart3,
  Settings,
  ClipboardList,
  Microscope,
  HeartPulse,
  FileCheck2,
  CornerDownLeft,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

/**
 * Notion-style Cmd+K command palette.
 *
 * Self-contained: owns its own open state + global key listener so it can be
 * dropped in with a single <CommandPalette .../>. Actions are grouped and
 * filtered by a simple case-insensitive substring match over label + keywords.
 */
export default function CommandPalette({ onNavigate, onGoToStep }) {
  const { isDark } = useTheme();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const commands = useMemo(
    () => [
      { id: 'go-dashboard', group: 'Navigate', label: 'Go to Home', keywords: 'dashboard start overview', icon: LayoutDashboard, run: () => onNavigate('dashboard') },
      { id: 'go-patients', group: 'Navigate', label: 'My Patients', keywords: 'patient list roster', icon: Users, run: () => onNavigate('patients') },
      { id: 'go-consult', group: 'Navigate', label: 'Open Consultation', keywords: 'consult encounter visit', icon: Stethoscope, run: () => onNavigate('consultation') },
      { id: 'go-analytics', group: 'Navigate', label: 'Performance Monitoring', keywords: 'analytics metrics dashboard performance monitoring live real-time', icon: BarChart3, run: () => onNavigate('analytics') },
      { id: 'go-settings', group: 'Navigate', label: 'Settings', keywords: 'preferences profile theme', icon: Settings, run: () => onNavigate('settings') },
      { id: 'step-data', group: 'Consultation steps', label: 'Step 1 · Data Input', keywords: 'vitals demographics notes intake', icon: ClipboardList, run: () => { onNavigate('consultation'); onGoToStep?.(1); } },
      { id: 'step-dx', group: 'Consultation steps', label: 'Step 2 · Diagnosis', keywords: 'differential assessment dx', icon: Microscope, run: () => { onNavigate('consultation'); onGoToStep?.(2); } },
      { id: 'step-plan', group: 'Consultation steps', label: 'Step 3 · Care Plan', keywords: 'treatment medications plan', icon: HeartPulse, run: () => { onNavigate('consultation'); onGoToStep?.(3); } },
      { id: 'step-complete', group: 'Consultation steps', label: 'Step 4 · Complete', keywords: 'soap note output sign export', icon: FileCheck2, run: () => { onNavigate('consultation'); onGoToStep?.(4); } },
    ],
    [onNavigate, onGoToStep]
  );

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) => (c.label + ' ' + c.keywords).toLowerCase().includes(q)
    );
  }, [commands, query]);

  // Global open shortcut: Cmd/Ctrl+K
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Reset + focus when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIdx(0);
      // focus after paint
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Keep active index in range as results shrink
  useEffect(() => {
    setActiveIdx((i) => Math.min(i, Math.max(0, results.length - 1)));
  }, [results.length]);

  const exec = (cmd) => {
    if (!cmd) return;
    cmd.run();
    setOpen(false);
  };

  const onListKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      exec(results[activeIdx]);
    }
  };

  if (!open) return null;

  // Render with simple group headers, tracking a flat index for keyboard nav.
  let flatIdx = -1;
  let lastGroup = null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[18vh] animate-fadeIn"
      onMouseDown={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className={`absolute inset-0 ${isDark ? 'bg-black/50' : 'bg-slate-900/30'} backdrop-blur-sm`} />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={onListKeyDown}
        className={`relative w-full max-w-xl overflow-hidden border shadow-2xl
          ${isDark ? 'bg-slate-800 border-white/10' : 'bg-white border-slate-200'}`}
        style={{ borderRadius: 'var(--radius-lg)' }}
      >
        {/* Search row */}
        <div className={`flex items-center gap-3 px-4 ${isDark ? 'border-b border-white/10' : 'border-b border-slate-200'}`}>
          <Search className={`w-5 h-5 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-400'}`} strokeWidth={1.5} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to a page or consultation step…"
            className={`flex-1 bg-transparent py-4 text-base outline-none
              ${isDark ? 'text-white placeholder:text-slate-500' : 'text-slate-800 placeholder:text-slate-400'}`}
          />
          <kbd className={`text-[11px] px-1.5 py-0.5 rounded ds-mono ${isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto py-2">
          {results.length === 0 && (
            <div className={`px-4 py-8 text-center text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              No matches for “{query}”.
            </div>
          )}
          {results.map((cmd) => {
            flatIdx += 1;
            const idx = flatIdx;
            const Icon = cmd.icon;
            const isActive = idx === activeIdx;
            const showHeader = cmd.group !== lastGroup;
            lastGroup = cmd.group;
            return (
              <React.Fragment key={cmd.id}>
                {showHeader && (
                  <div className={`px-4 pt-3 pb-1 text-[10px] uppercase tracking-wider font-semibold ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    {cmd.group}
                  </div>
                )}
                <button
                  type="button"
                  onMouseEnter={() => setActiveIdx(idx)}
                  onClick={() => exec(cmd)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left
                    ${isActive
                      ? (isDark ? 'bg-white/10' : 'bg-slate-100')
                      : 'bg-transparent'}`}
                >
                  <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-[var(--accent-primary)]' : (isDark ? 'text-slate-400' : 'text-slate-500')}`} strokeWidth={1.5} />
                  <span className={`flex-1 text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{cmd.label}</span>
                  {isActive && (
                    <CornerDownLeft className={`w-3.5 h-3.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} strokeWidth={1.5} />
                  )}
                </button>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
