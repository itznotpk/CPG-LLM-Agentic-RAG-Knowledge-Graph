import React from 'react';
import {
  LayoutDashboard,
  Users,
  Stethoscope,
  Settings,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

const navItems = [
  { id: 'dashboard', label: 'Home', icon: LayoutDashboard },
  { id: 'patients', label: 'My Patients', icon: Users },
  { id: 'consultation', label: 'Consultation', icon: Stethoscope },
  { id: 'settings', label: 'Settings', icon: Settings },
];

const Sidebar = ({ currentView, onNavigate, isCollapsed, onToggleCollapse, profile }) => {
  const { isDark, accent } = useTheme();

  // Get initials from name
  const getInitials = (name) => {
    if (!name) return 'U';
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return parts[0][0] + parts[1][0];
    }
    return name[0];
  };

  return (
    <aside
      className={`fixed left-0 top-0 h-full transition-all duration-300 z-50 flex flex-col
        ${isDark
          ? 'bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 border-r border-white/10'
          : 'bg-white border-r border-slate-200 shadow-lg'
        }
        ${isCollapsed ? 'w-20' : 'w-64'}`}
    >
      {/* Logo Section */}
      <div className={`p-4 flex items-center ${isCollapsed ? 'justify-center' : 'gap-3'} ${isDark ? 'border-b border-white/10' : 'border-b border-slate-200'}`}>
        <img
          src="/MHNexus.png"
          alt="MHNexus Logo"
          className="w-14 h-14 object-contain flex-shrink-0"
        />
        {!isCollapsed && (
          <div className="flex flex-col min-w-0">
            <span className={`font-bold text-lg leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>CPG LLM</span>
            <span className={`text-[10px] leading-tight ${accent.text} whitespace-nowrap`}>Connecting Values in Healthcare</span>
          </div>
        )}
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 p-3 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200
                ${isActive
                  ? isDark
                    ? `bg-[var(--accent-primary)]/10 border border-[var(--accent-primary)]/20 ${accent.text}`
                    : `bg-gradient-to-r from-[var(--accent-primary)]/20 to-[var(--accent-secondary)]/20 border border-[var(--accent-primary)]/30 ${accent.text} shadow-lg ${accent.shadow}`
                  : isDark
                    ? 'text-slate-300 hover:bg-white/5 hover:text-white'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }
                ${isCollapsed ? 'justify-center' : ''}`}
              title={isCollapsed ? item.label : ''}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? accent.text : ''}`} />
              {!isCollapsed && (
                <span className="font-medium text-sm">{item.label}</span>
              )}
              {!isCollapsed && isActive && (
                <div className={`ml-auto w-1.5 h-8 bg-gradient-to-b ${accent.gradient} rounded-full`} />
              )}
            </button>
          );
        })}
      </nav>

      {/* Collapse Toggle */}
      <div className={`p-3 ${isDark ? 'border-t border-white/10' : 'border-t border-slate-200'}`}>
        <button
          onClick={onToggleCollapse}
          className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg transition-all
            ${isDark ? 'text-slate-400 hover:bg-white/5 hover:text-white' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'}`}
        >
          {isCollapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <>
              <ChevronLeft className="w-5 h-5" />
              <span className="text-sm">Collapse</span>
            </>
          )}
        </button>
      </div>

      {/* User Profile Section */}
      {!isCollapsed && (
        <div className={`p-4 ${isDark ? 'border-t border-white/10' : 'border-t border-slate-200'}`}>
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${accent.gradient}
              flex items-center justify-center text-white font-bold text-sm`}>
              {getInitials(profile?.name)}
            </div>
            <div className="flex flex-col">
              <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{profile?.name || 'User'}</span>
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{profile?.specialty || 'Medical Professional'}</span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
