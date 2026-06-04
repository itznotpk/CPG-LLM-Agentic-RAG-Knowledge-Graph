import React from 'react';
import { useTheme } from '../../context/ThemeContext';

export function Input({
  label,
  id,
  type = 'text',
  error,
  helper,
  className = '',
  ...props
}) {
  const { isDark } = useTheme();
  
  return (
    <div className={`space-y-1 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className={`block text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}
        >
          {label}
        </label>
      )}
      <input
        type={type}
        id={id}
        className={`
          w-full px-4 py-2.5
          backdrop-blur-sm
          border ${error ? 'border-red-400' : isDark ? 'border-white/20' : 'border-slate-300'}
          rounded-xl
          ${isDark ? 'bg-white/10 text-white placeholder-slate-400' : 'bg-white/80 text-slate-800 placeholder-slate-400'}
          transition-all duration-200 ease-out
          focus:ring-2 focus:ring-[var(--accent-primary)]/50 focus:border-[var(--accent-primary)]
          ${isDark ? 'hover:bg-white/15 hover:border-white/30' : 'hover:bg-white hover:border-slate-400'} hover:shadow-md
        `}
        {...props}
      />
      {helper && !error && (
        <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{helper}</p>
      )}
      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}

export function TextArea({
  label,
  id,
  rows = 4,
  error,
  helper,
  className = '',
  ...props
}) {
  const { isDark } = useTheme();
  
  return (
    <div className={`space-y-1 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className={`block text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}
        >
          {label}
        </label>
      )}
      <textarea
        id={id}
        rows={rows}
        className={`
          w-full px-4 py-3
          backdrop-blur-sm
          border ${error ? 'border-red-400' : isDark ? 'border-white/20' : 'border-slate-300'}
          rounded-xl
          ${isDark ? 'bg-white/10 text-white placeholder-slate-400' : 'bg-white/80 text-slate-800 placeholder-slate-400'}
          transition-all duration-200 ease-out
          focus:ring-2 focus:ring-[var(--accent-primary)]/50 focus:border-[var(--accent-primary)]
          ${isDark ? 'hover:bg-white/15 hover:border-white/30' : 'hover:bg-white hover:border-slate-400'} hover:shadow-md
          resize-none
        `}
        {...props}
      />
      {helper && !error && (
        <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{helper}</p>
      )}
      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}

export function Select({
  label,
  id,
  options = [],
  placeholder = 'Select...',
  error,
  className = '',
  ...props
}) {
  const { isDark } = useTheme();
  
  return (
    <div className={`space-y-1 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className={`block text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}
        >
          {label}
        </label>
      )}
      <select
        id={id}
        className={`
          w-full px-4 py-2.5
          backdrop-blur-sm
          border ${error ? 'border-red-400' : isDark ? 'border-white/20' : 'border-slate-300'}
          rounded-xl
          ${isDark ? 'bg-white/10 text-white' : 'bg-white/80 text-slate-800'}
          transition-all duration-200 ease-out
          focus:ring-2 focus:ring-[var(--accent-primary)]/50 focus:border-[var(--accent-primary)]
          ${isDark ? 'hover:bg-white/15 hover:border-white/30' : 'hover:bg-white hover:border-slate-400'} hover:shadow-md
          cursor-pointer
        `}
        {...props}
      >
        <option value="" className={isDark ? 'bg-slate-800' : 'bg-white'}>{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value} className={isDark ? 'bg-slate-800' : 'bg-white'}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
