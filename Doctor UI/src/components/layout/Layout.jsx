import React from 'react';
import { Menu, Bell, Settings, User, LogOut } from 'lucide-react';
import { Button } from '../shared';
import { useTheme } from '../../context/ThemeContext';

export function Header() {
  const { isDark } = useTheme();
  
  return (
    <header className={`sticky top-0 z-50 border-b backdrop-blur-lg ${isDark ? 'bg-slate-900/80 border-white/10' : 'bg-white/80 border-slate-200'}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <img 
              src="/MHNexus.png" 
              alt="MHNexus Logo" 
              className="h-10 w-auto"
            />
            <div>
              <h1 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>CPG LLM</h1>
              <p className={`text-xs -mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Connecting Values in Healthcare</p>
            </div>
          </div>

          {/* Right Actions */}
          <div className="flex items-center gap-3">
            <button className={`p-2 rounded-lg transition-all duration-200 hover:scale-110 ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-100'}`}>
              <Bell className={`w-5 h-5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`} />
            </button>
            <button className={`p-2 rounded-lg transition-all duration-200 hover:scale-110 ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-100'}`}>
              <Settings className={`w-5 h-5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`} />
            </button>
            <div className={`flex items-center gap-2 pl-3 border-l ${isDark ? 'border-slate-600' : 'border-slate-300'}`}>
              <div className="w-8 h-8 bg-[var(--accent-primary)] rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-white" />
              </div>
              <span className={`text-sm font-medium hidden sm:block ${isDark ? 'text-white' : 'text-slate-800'}`}>
                Dr. Ahmad
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="mt-auto py-4">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      </div>
    </footer>
  );
}
