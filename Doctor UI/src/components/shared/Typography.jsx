import React from 'react';
import { useTheme } from '../../context/ThemeContext';

/**
 * Shared typography primitives — single source of truth for the MHNexus type
 * scale so headers/titles can't drift per-tab. Matches the spec in
 * colors_and_type.css / ui_kits/doctor-ui:
 *
 *   PageHeader    — page title (H1): 30px / 700 / -0.02em  + sentence-case subtitle
 *   SectionHeader — section/step title (H3): 20px / 600    + optional icon/subtitle
 *   GroupLabel    — uppercase eyebrow: 11px / 600 / +.06em, accent or muted
 *
 * Muted text is always slate-500 (light) / slate-400 (dark) === --fg-muted.
 */

const titleColor = (isDark) => (isDark ? 'text-white' : 'text-slate-800');
const mutedColor = (isDark) => (isDark ? 'text-slate-400' : 'text-slate-500');

export function PageHeader({ title, subtitle, eyebrow, actions, className = '' }) {
  const { isDark } = useTheme();
  return (
    <div className={`flex items-start justify-between gap-6 ${className}`}>
      <div className="min-w-0">
        {eyebrow && <div className="ds-eyebrow mb-1">{eyebrow}</div>}
        <h1 className={`text-3xl font-bold tracking-tight ${titleColor(isDark)}`}>{title}</h1>
        {subtitle && <p className={`mt-1 text-sm ${mutedColor(isDark)}`}>{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}

export function SectionHeader({ title, subtitle, icon: Icon, actions, className = '' }) {
  const { isDark } = useTheme();
  return (
    <div className={`flex items-start justify-between gap-4 ${className}`}>
      <div className="flex items-start gap-3 min-w-0">
        {Icon && (
          <div className={`p-2 rounded-xl flex-shrink-0 ${isDark ? 'bg-[var(--accent-primary)]/15' : 'bg-[var(--accent-primary)]/10'}`}>
            <Icon className="w-5 h-5 text-[var(--accent-primary)]" strokeWidth={1.5} />
          </div>
        )}
        <div className="min-w-0">
          <h3 className={`text-xl font-semibold tracking-tight ${titleColor(isDark)}`}>{title}</h3>
          {subtitle && <p className={`mt-0.5 text-sm ${mutedColor(isDark)}`}>{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}

export function GroupLabel({ children, className = '' }) {
  const { isDark } = useTheme();
  return (
    <div
      className={`text-[11px] font-semibold uppercase tracking-[0.06em] ${isDark ? 'text-slate-400' : 'text-slate-500'} ${className}`}
    >
      {children}
    </div>
  );
}
