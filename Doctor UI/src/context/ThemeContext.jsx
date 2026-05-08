import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

// Available accent colors with their Tailwind classes
export const accentColors = {
  cyan: {
    name: 'Cyan',
    primary: 'rgb(6, 182, 212)',      // cyan-500
    primaryHover: 'rgb(34, 211, 238)', // cyan-400
    secondary: 'rgb(59, 130, 246)',    // blue-500
    gradient: 'from-cyan-500 to-blue-500',
    gradientHover: 'from-cyan-400 to-blue-400',
    text: 'text-cyan-400',
    textLight: 'text-cyan-700',
    bg: 'bg-cyan-500',
    bgHover: 'hover:bg-cyan-400',
    lightBg: 'bg-cyan-100',
    lightBgHover: 'hover:bg-cyan-200',
    lightBgDark: 'bg-cyan-500/20',
    lightBgDarkHover: 'hover:bg-cyan-500/30',
    lightBorder: 'border-cyan-200',
    lightBorderDark: 'border-cyan-500/30',
    border: 'border-cyan-500',
    shadow: 'shadow-cyan-500/20',
    ring: 'ring-cyan-500',
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
  purple: {
    name: 'Purple',
    primary: 'rgb(168, 85, 247)',
    primaryHover: 'rgb(192, 132, 252)',
    secondary: 'rgb(236, 72, 153)',
    gradient: 'from-purple-500 to-pink-500',
    gradientHover: 'from-purple-400 to-pink-400',
    text: 'text-purple-400',
    textLight: 'text-purple-700',
    bg: 'bg-purple-500',
    bgHover: 'hover:bg-purple-400',
    lightBg: 'bg-purple-100',
    lightBgHover: 'hover:bg-purple-200',
    lightBgDark: 'bg-purple-500/20',
    lightBgDarkHover: 'hover:bg-purple-500/30',
    lightBorder: 'border-purple-200',
    lightBorderDark: 'border-purple-500/30',
    border: 'border-purple-500',
    shadow: 'shadow-purple-500/20',
    ring: 'ring-purple-500',
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

  const [accentColor, setAccentColor] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('mhnexus-accent') || 'cyan';
    }
    return 'cyan';
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

  const accent = accentColors[accentColor];

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
