import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

// Available accent colors with their Tailwind classes
export const accentColors = {
  teal: {
    name: 'Teal',
    primary: 'rgb(20, 184, 166)',       // teal-500
    primaryHover: 'rgb(13, 148, 136)',  // teal-600
    secondary: 'rgb(45, 212, 191)',     // teal-400
    gradient: 'from-teal-500 to-emerald-500',
    gradientHover: 'from-teal-400 to-emerald-400',
    text: 'text-teal-500',
    textLight: 'text-teal-700',
    bg: 'bg-teal-500',
    bgHover: 'hover:bg-teal-400',
    lightBg: 'bg-teal-100',
    lightBgHover: 'hover:bg-teal-200',
    lightBgDark: 'bg-teal-500/20',
    lightBgDarkHover: 'hover:bg-teal-500/30',
    lightBorder: 'border-teal-200',
    lightBorderDark: 'border-teal-500/30',
    border: 'border-teal-500',
    shadow: 'shadow-teal-500/20',
    ring: 'ring-teal-500',
  },
  blue: {
    name: 'Blue',
    primary: 'rgb(59, 130, 246)',
    primaryHover: 'rgb(96, 165, 250)',
    secondary: 'rgb(99, 102, 241)',
    gradient: 'from-blue-500 to-indigo-500',
    gradientHover: 'from-blue-400 to-indigo-400',
    text: 'text-blue-400',
    textLight: 'text-blue-700',
    bg: 'bg-blue-500',
    bgHover: 'hover:bg-blue-400',
    lightBg: 'bg-blue-100',
    lightBgHover: 'hover:bg-blue-200',
    lightBgDark: 'bg-blue-500/20',
    lightBgDarkHover: 'hover:bg-blue-500/30',
    lightBorder: 'border-blue-200',
    lightBorderDark: 'border-blue-500/30',
    border: 'border-blue-500',
    shadow: 'shadow-blue-500/20',
    ring: 'ring-blue-500',
  },
  navy: {
    name: 'Navy',
    primary: 'rgb(59, 130, 246)',
    primaryHover: 'rgb(96, 165, 250)',
    secondary: 'rgb(14, 165, 233)',
    gradient: 'from-blue-600 to-sky-500',
    gradientHover: 'from-blue-500 to-sky-400',
    text: 'text-blue-500',
    textLight: 'text-blue-700',
    bg: 'bg-blue-600',
    bgHover: 'hover:bg-blue-500',
    lightBg: 'bg-blue-100',
    lightBgHover: 'hover:bg-blue-200',
    lightBgDark: 'bg-blue-500/20',
    lightBgDarkHover: 'hover:bg-blue-500/30',
    lightBorder: 'border-blue-200',
    lightBorderDark: 'border-blue-500/30',
    border: 'border-blue-600',
    shadow: 'shadow-blue-500/20',
    ring: 'ring-blue-600',
  },
  emerald: {
    name: 'Emerald',
    primary: 'rgb(16, 185, 129)',
    primaryHover: 'rgb(52, 211, 153)',
    secondary: 'rgb(6, 182, 212)',
    gradient: 'from-emerald-500 to-cyan-500',
    gradientHover: 'from-emerald-400 to-cyan-400',
    text: 'text-emerald-400',
    textLight: 'text-emerald-700',
    bg: 'bg-emerald-500',
    bgHover: 'hover:bg-emerald-400',
    lightBg: 'bg-emerald-100',
    lightBgHover: 'hover:bg-emerald-200',
    lightBgDark: 'bg-emerald-500/20',
    lightBgDarkHover: 'hover:bg-emerald-500/30',
    lightBorder: 'border-emerald-200',
    lightBorderDark: 'border-emerald-500/30',
    border: 'border-emerald-500',
    shadow: 'shadow-emerald-500/20',
    ring: 'ring-emerald-500',
  },
  amber: {
    name: 'Amber',
    primary: 'rgb(245, 158, 11)',
    primaryHover: 'rgb(251, 191, 36)',
    secondary: 'rgb(249, 115, 22)',
    gradient: 'from-amber-500 to-orange-500',
    gradientHover: 'from-amber-400 to-orange-400',
    text: 'text-amber-400',
    textLight: 'text-amber-700',
    bg: 'bg-amber-500',
    bgHover: 'hover:bg-amber-400',
    lightBg: 'bg-amber-100',
    lightBgHover: 'hover:bg-amber-200',
    lightBgDark: 'bg-amber-500/20',
    lightBgDarkHover: 'hover:bg-amber-500/30',
    lightBorder: 'border-amber-200',
    lightBorderDark: 'border-amber-500/30',
    border: 'border-amber-500',
    shadow: 'shadow-amber-500/20',
    ring: 'ring-amber-500',
  },
  rose: {
    name: 'Rose',
    primary: 'rgb(244, 63, 94)',
    primaryHover: 'rgb(251, 113, 133)',
    secondary: 'rgb(236, 72, 153)',
    gradient: 'from-rose-500 to-pink-500',
    gradientHover: 'from-rose-400 to-pink-400',
    text: 'text-rose-400',
    textLight: 'text-rose-700',
    bg: 'bg-rose-500',
    bgHover: 'hover:bg-rose-400',
    lightBg: 'bg-rose-100',
    lightBgHover: 'hover:bg-rose-200',
    lightBgDark: 'bg-rose-500/20',
    lightBgDarkHover: 'hover:bg-rose-500/30',
    lightBorder: 'border-rose-200',
    lightBorderDark: 'border-rose-500/30',
    border: 'border-rose-500',
    shadow: 'shadow-rose-500/20',
    ring: 'ring-rose-500',
  },
};

export const ThemeProvider = ({ children }) => {
  // Initialize from localStorage or defaults
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('mhnexus-theme') || 'light';
    }
    return 'light';
  });

  // Migration map: old accent keys → new keys
  const ACCENT_MIGRATION = { cyan: 'teal', purple: 'navy' };

  const [accentColor, setAccentColor] = useState(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('mhnexus-accent') || 'teal';
      // Migrate stale keys that no longer exist
      return ACCENT_MIGRATION[stored] || (accentColors[stored] ? stored : 'teal');
    }
    return 'teal';
  });

  // Determine effective theme (for 'system' mode)
  const [effectiveTheme, setEffectiveTheme] = useState('light');

  useEffect(() => {
    // Save to localStorage
    localStorage.setItem('mhnexus-theme', theme);

    // Determine effective theme
    if (theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      setEffectiveTheme(mediaQuery.matches ? 'dark' : 'light');

      const handler = (e) => setEffectiveTheme(e.matches ? 'dark' : 'light');
      mediaQuery.addEventListener('change', handler);
      return () => mediaQuery.removeEventListener('change', handler);
    } else {
      setEffectiveTheme(theme);
    }
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('mhnexus-accent', accentColor);

    // Apply CSS custom properties for accent color
    const accent = accentColors[accentColor];
    if (accent) {
      document.documentElement.style.setProperty('--accent-primary', accent.primary);
      document.documentElement.style.setProperty('--accent-primary-hover', accent.primaryHover);
      document.documentElement.style.setProperty('--accent-secondary', accent.secondary);
    }
  }, [accentColor]);

  useEffect(() => {
    // Apply theme class to document
    const root = document.documentElement;
    root.classList.remove('light', 'dark');
    root.classList.add(effectiveTheme);
  }, [effectiveTheme]);

  // Safety fallback — accent must never be undefined
  const accent = accentColors[accentColor] || accentColors['teal'];

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        accentColor,
        setAccentColor,
        effectiveTheme,
        accent,
        accentColors,
        isDark: effectiveTheme === 'dark'
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export default ThemeContext;
