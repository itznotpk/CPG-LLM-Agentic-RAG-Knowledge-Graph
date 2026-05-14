import React from 'react';
import { useTheme } from '../../context/ThemeContext';

export function GlassCard({ children, className = '', variant = 'default', ...props }) {
  const { isDark } = useTheme();
  
  const variants = {
    default: isDark
      ? 'bg-slate-800 border-white/10 text-white'
      : 'bg-white border-slate-200 text-slate-800',
    dark: isDark
      ? 'bg-slate-800 border-white/10 text-white'
      : 'bg-slate-800 border-white/10 text-white',
    light: isDark
      ? 'bg-slate-800 border-white/10 text-white'
      : 'bg-white border-white/40 text-slate-800',
    success: isDark
      ? 'bg-green-900/50 border-green-500/40 text-green-100'
      : 'bg-green-50/80 border-green-400/40 text-green-800',
    danger: isDark
      ? 'bg-red-900/50 border-red-500/40 text-red-100'
      : 'bg-red-50/80 border-red-400/40 text-red-800',
    warning: isDark
      ? 'bg-amber-900/50 border-amber-500/40 text-amber-100'
      : 'bg-amber-50/80 border-amber-400/40 text-amber-800',
  };

  return (
    <div
      className={`
        ${variants[variant]}
        border
        shadow-lg
        transition-all
        duration-300
        hover:shadow-xl
        ${isDark ? 'hover:border-[var(--accent-primary)]/40' : 'hover:border-slate-300'}
        ${className}
      `}
      style={{ borderRadius: 'var(--radius-lg)' }}
      {...props}
    >
      {children}
    </div>
  );
}

export function GlassPanel({ children, className = '', ...props }) {
  const { isDark } = useTheme();

  return (
    <div
      className={`
        ${isDark ? 'bg-slate-800 border-white/10' : 'bg-white border-slate-200'}
        border
        shadow-xl
        p-6
        transition-all
        duration-300
        ${isDark ? 'hover:shadow-2xl hover:bg-slate-800 hover:border-white/10' : 'hover:shadow-2xl hover:bg-white'}
        ${className}
      `}
      style={{ borderRadius: 'var(--radius-xl)' }}
      {...props}
    >
      {children}
    </div>
  );
}
