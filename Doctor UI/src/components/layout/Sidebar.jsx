import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Users,
  Stethoscope,
  Settings,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  LogOut,
  ArrowRight
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';

const navStagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05, delayChildren: 0.1 } },
};
const navItem = {
  hidden: { opacity: 0, x: -12 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.22, ease: 'easeOut' } },
};

const navItems = [
  { id: 'dashboard', label: 'Home', icon: LayoutDashboard },
  { id: 'patients', label: 'My Patients', icon: Users },
  { id: 'consultation', label: 'Consultation', icon: Stethoscope },
  { id: 'analytics', label: 'AI Performance', icon: BarChart3 },
  { id: 'settings', label: 'Settings', icon: Settings },
];

const Sidebar = ({ currentView, onNavigate, isCollapsed, onToggleCollapse, profile, consultProcessing = false }) => {
  const { isDark, accent } = useTheme();
  const { signOut } = useAuth();

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
    <motion.aside
      animate={{ width: isCollapsed ? 80 : 256 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className={`fixed left-0 top-0 h-full z-50 flex flex-col overflow-hidden
        ${isDark
          ? 'bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 border-r border-white/10'
          : 'bg-white border-r border-slate-200 shadow-lg'
        }`}
    >
      {/* Logo Section */}
      <div className={`p-4 flex items-center ${isCollapsed ? 'justify-center' : 'gap-3'} ${isDark ? 'border-b border-white/10' : 'border-b border-slate-200'}`}>
        <img
          src="/MHNexus.png"
          alt="MHNexus Logo"
          className={`object-contain flex-shrink-0 ${isCollapsed ? 'w-12 h-12' : 'w-20 h-20'}`}
        />
        {!isCollapsed && (
          <div className="flex flex-col min-w-0">
            <span
              className="leading-none tracking-tight"
              style={{
                fontFamily: "var(--font-display)",
                fontStyle: 'italic',
                fontSize: '28px',
                color: 'var(--primary-700)',
                letterSpacing: '-0.02em',
              }}
            >
              ClearPath<span style={{ color: 'var(--primary-500)' }}>.</span>
            </span>
          </div>
        )}
      </div>

      {/* Navigation Items */}
      <motion.nav
        variants={navStagger}
        initial="hidden"
        animate="visible"
        className="flex-1 p-3 space-y-2"
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          const isProcessing = consultProcessing && item.id === 'consultation';

          return (
            <motion.div key={item.id} variants={navItem}>
            <button
              onClick={() => onNavigate(item.id)}
              className={`hover-reveal w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200
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
              <span className="relative flex-shrink-0">
                <Icon className={`w-5 h-5 ${isActive ? accent.text : ''}`} />
                {/* Collapsed: corner pulse so background work is visible without labels */}
                {isCollapsed && isProcessing && (
                  <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--accent-primary)] opacity-75 animate-ping" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--accent-primary)]" />
                  </span>
                )}
              </span>
              {!isCollapsed && (
                <span className="font-medium text-sm">{item.label}</span>
              )}
              {/* Background-processing indicator takes priority over arrow/active bar */}
              {!isCollapsed && isProcessing && (
                <span className="ml-auto flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--accent-primary)] opacity-75 animate-ping" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--accent-primary)]" />
                  </span>
                  <span className="text-[10px] font-medium text-[var(--accent-primary)]">Running</span>
                </span>
              )}
              {!isCollapsed && !isProcessing && isActive && (
                <div className={`ml-auto w-1.5 h-8 bg-gradient-to-b ${accent.gradient} rounded-full`} />
              )}
              {!isCollapsed && !isProcessing && !isActive && (
                <ArrowRight
                  className={`hover-reveal-item ml-auto w-4 h-4 ${isDark ? 'text-slate-400' : 'text-slate-400'}`}
                  strokeWidth={1.5}
                />
              )}
            </button>
            </motion.div>
          );
        })}
      </motion.nav>

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
            <div className={`w-10 h-10 rounded-full bg-teal-500/20 border border-teal-500/30
              flex items-center justify-center text-teal-400 font-semibold text-sm`}>
              {getInitials(profile?.name)}
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <span className={`text-sm font-medium truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>{profile?.name || 'User'}</span>
              {profile?.specialty && (
                <span className={`text-xs truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{profile.specialty}</span>
              )}
            </div>
            <button
              onClick={signOut}
              title="Sign out"
              className={`flex-shrink-0 p-1.5 rounded-lg transition-colors
                ${isDark ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'}`}
            >
              <LogOut className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
        </div>
      )}

      {/* Collapsed sign-out */}
      {isCollapsed && (
        <div className={`p-3 ${isDark ? 'border-t border-white/10' : 'border-t border-slate-200'}`}>
          <button
            onClick={signOut}
            title="Sign out"
            className={`w-full flex items-center justify-center p-2 rounded-lg transition-colors
              ${isDark ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'}`}
          >
            <LogOut className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>
      )}
    </motion.aside>
  );
};

export default Sidebar;
