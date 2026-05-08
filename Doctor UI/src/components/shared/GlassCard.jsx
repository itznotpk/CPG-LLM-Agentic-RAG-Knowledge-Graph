import React from 'react';
import { useTheme } from '../../context/ThemeContext';

export function GlassCard({ children, className = '', variant = 'default', ...props }) {
  const { isDark } = useTheme();
  
  const variants = {
    default: isDark 
      ? 'bg-[var(--accent-primary)]/5 border-[var(--accent-primary)]/20 text-white' 
      : 'bg-white/60 border-slate-200 text-slate-800',
    dark: isDark 
      ? 'bg-[var(--accent-primary)]/5 border-[var(--accent-primary)]/20 text-white'
      : 'bg-slate-800/90 border-white/10 text-white',
    light: isDark 
      ? 'bg-[var(--accent-primary)]/5 border-[var(--accent-primary)]/20 text-white'
      : 'bg-white/60 border-white/40 text-slate-800',
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
        backdrop-blur-xl
        border
        rounded-2xl
        shadow-lg
        transition-all
        duration-300
        hover:shadow-xl
        ${isDark ? 'hover:border-[var(--accent-primary)]/40' : 'hover:border-slate-300'}
        ${className}
      `}
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
        ${isDark ? 'bg-[var(--accent-primary)]/5 border-[var(--accent-primary)]/20' : 'bg-white/40 border-slate-200'}
        backdrop-blur-lg
        border
        rounded-3xl
        shadow-xl
        p-6
        transition-all
        duration-300
        ${isDark ? 'hover:shadow-2xl hover:bg-[var(--accent-primary)]/10 hover:border-[var(--accent-primary)]/30' : 'hover:shadow-2xl hover:bg-white/50'}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}
