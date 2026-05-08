import React, { useState } from 'react';
import {
  User,
  Bell,
  Shield,
  Palette,
  Globe,
  Database,
  Save,
  Camera,
  Mail,
  Phone,
  Building,
  Award,
  Clock,
  Moon,
  Sun,
  Monitor,
  Check,
  Edit3,
  CheckCircle
} from 'lucide-react';
import { GlassCard } from '../shared/GlassCard';
import { useTheme, accentColors } from '../../context/ThemeContext';

const Settings = ({ profile, setProfile }) => {
  const { theme, setTheme, accentColor, setAccentColor, effectiveTheme, isDark, accent } = useTheme();
  const [activeTab, setActiveTab] = useState('profile');
  const [notifications, setNotifications] = useState({
    email: true,
    push: true,
    sms: false,
    emergencyAlerts: true
  });

  const [isProfileEditing, setIsProfileEditing] = useState(false);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);

  const handleSaveProfile = () => {
    setIsProfileEditing(false);
    setShowSuccessMessage(true);
    setTimeout(() => setShowSuccessMessage(false), 3000);
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'system', label: 'System', icon: Database }
  ];

  // Get initials from name
  const getInitials = (name) => {
    if (!name) return 'U';
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return parts[0][0] + parts[1][0];
    }
    return name[0];
  };

  const renderProfileSettings = () => (
    <div className="space-y-6">
      <div className="flex items-start gap-6">
        <div className="relative">
          <div className={`w-24 h-24 rounded-full bg-gradient-to-br ${accent.gradient} 
            flex items-center justify-center text-white text-2xl font-bold`}>
            {getInitials(profile?.name)}
          </div>
          {isProfileEditing && (
            <button className={`absolute bottom-0 right-0 w-8 h-8 rounded-full 
              border-2 flex items-center justify-center text-white
              transition-colors ${isDark ? 'bg-slate-700 border-slate-800 hover:bg-slate-600' : 'bg-slate-500 border-slate-600 hover:bg-slate-400'}`}>
              <Camera className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{profile.name}</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{profile.specialty}</p>
            </div>
            {!isProfileEditing && (
              <button
                onClick={() => setIsProfileEditing(true)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all
                  ${isDark
                    ? 'bg-white/10 hover:bg-white/20 text-white border border-white/10'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'}`}
              >
                <Edit3 className="w-4 h-4" />
                Edit Profile
              </button>
            )}
          </div>
          {isProfileEditing && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={`block text-sm mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Full Name</label>
                <input
                  type="text"
                  value={profile.name}
                  onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                  className={`w-full px-4 py-2.5 rounded-xl border 
                    focus:outline-none focus:border-cyan-500/50 transition-all
                    ${isDark ? 'bg-white/5 border-white/10 text-white' : 'bg-slate-100 border-slate-200 text-slate-800'}`}
                />
              </div>
              <div>
                <label className={`block text-sm mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Specialty</label>
                <input
                  type="text"
                  value={profile.specialty}
                  onChange={(e) => setProfile({ ...profile, specialty: e.target.value })}
                  className={`w-full px-4 py-2.5 rounded-xl border 
                    focus:outline-none focus:border-cyan-500/50 transition-all
                    ${isDark ? 'bg-white/5 border-white/10 text-white' : 'bg-slate-100 border-slate-200 text-slate-800'}`}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {isProfileEditing && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={`block text-sm mb-2 flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              <Mail className="w-4 h-4" /> Email
            </label>
            <input
              type="email"
              value={profile.email}
              onChange={(e) => setProfile({ ...profile, email: e.target.value })}
              className={`w-full px-4 py-2.5 rounded-xl border 
                focus:outline-none focus:border-cyan-500/50 transition-all
                ${isDark ? 'bg-white/5 border-white/10 text-white' : 'bg-slate-100 border-slate-200 text-slate-800'}`}
            />
          </div>
          <div>
            <label className={`block text-sm mb-2 flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              <Phone className="w-4 h-4" /> Phone
            </label>
            <input
              type="tel"
              value={profile.phone}
              onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
              className={`w-full px-4 py-2.5 rounded-xl border 
                focus:outline-none focus:border-cyan-500/50 transition-all
                ${isDark ? 'bg-white/5 border-white/10 text-white' : 'bg-slate-100 border-slate-200 text-slate-800'}`}
            />
          </div>
          <div>
            <label className={`block text-sm mb-2 flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              <Award className="w-4 h-4" /> Medical License
            </label>
            <input
              type="text"
              value={profile.license}
              onChange={(e) => setProfile({ ...profile, license: e.target.value })}
              className={`w-full px-4 py-2.5 rounded-xl border 
                focus:outline-none focus:border-cyan-500/50 transition-all
                ${isDark ? 'bg-white/5 border-white/10 text-white' : 'bg-slate-100 border-slate-200 text-slate-800'}`}
            />
          </div>
          <div>
            <label className={`block text-sm mb-2 flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              <Building className="w-4 h-4" /> Facility
            </label>
            <input
              type="text"
              value={profile.facility}
              onChange={(e) => setProfile({ ...profile, facility: e.target.value })}
              className={`w-full px-4 py-2.5 rounded-xl border 
                focus:outline-none focus:border-cyan-500/50 transition-all
                ${isDark ? 'bg-white/5 border-white/10 text-white' : 'bg-slate-100 border-slate-200 text-slate-800'}`}
            />
          </div>
        </div>
      )}

      {/* View-only mode info display */}
      {!isProfileEditing && (
        <div className="grid grid-cols-2 gap-4">
          <div className={`p-3 rounded-xl ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Email</p>
            <p className={`text-sm font-medium flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
              <Mail className="w-4 h-4" /> {profile.email}
            </p>
          </div>
          <div className={`p-3 rounded-xl ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Phone</p>
            <p className={`text-sm font-medium flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
              <Phone className="w-4 h-4" /> {profile.phone}
            </p>
          </div>
          <div className={`p-3 rounded-xl ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Medical License</p>
            <p className={`text-sm font-medium flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
              <Award className="w-4 h-4" /> {profile.license}
            </p>
          </div>
          <div className={`p-3 rounded-xl ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Facility</p>
            <p className={`text-sm font-medium flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
              <Building className="w-4 h-4" /> {profile.facility}
            </p>
          </div>
        </div>
      )}
    </div>
  );

  const renderNotificationSettings = () => (
    <div className="space-y-6">
      <p className={`${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Configure how you receive notifications and alerts.</p>

      <div className="space-y-4">
        {[
          { key: 'email', label: 'Email Notifications', desc: 'Receive updates via email' },
          { key: 'push', label: 'Push Notifications', desc: 'Browser push notifications' },
          { key: 'sms', label: 'SMS Alerts', desc: 'Text message notifications' },
          { key: 'emergencyAlerts', label: 'Emergency Alerts', desc: 'Critical patient alerts (always on)' }
        ].map((item) => (
          <div key={item.key} className={`flex items-center justify-between p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
            <div>
              <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{item.label}</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{item.desc}</p>
            </div>
            <button
              onClick={() => setNotifications({ ...notifications, [item.key]: !notifications[item.key] })}
              className={`w-12 h-6 rounded-full transition-all relative
                ${notifications[item.key] ? 'bg-cyan-500' : 'bg-slate-600'}`}
            >
              <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-all
                ${notifications[item.key] ? 'left-7' : 'left-1'}`}
              />
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  const renderAppearanceSettings = () => (
    <div className="space-y-6">
      <p className={`${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
        Customize the appearance of your workspace. Changes are applied immediately and saved automatically.
      </p>

      <div>
        <label className={`block text-sm font-medium mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
          Theme
        </label>
        <div className="grid grid-cols-3 gap-4">
          {[
            { id: 'light', label: 'Light', icon: Sun, desc: 'Bright and clean' },
            { id: 'dark', label: 'Dark', icon: Moon, desc: 'Easy on the eyes' },
            { id: 'system', label: 'System', icon: Monitor, desc: 'Match your OS' }
          ].map((t) => {
            const Icon = t.icon;
            const isActive = theme === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className={`p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-2 relative
                  ${isActive
                    ? `border-[var(--accent-primary)] bg-[var(--accent-primary)]/10`
                    : `${isDark ? 'bg-white/5 border-white/10 hover:border-white/30' : 'bg-slate-100 border-slate-200 hover:border-slate-400'}`
                  }`}
              >
                {isActive && (
                  <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-[var(--accent-primary)] flex items-center justify-center">
                    <Check className="w-3 h-3 text-white" />
                  </div>
                )}
                <Icon className={`w-8 h-8 ${isActive ? 'text-[var(--accent-primary)]' : isDark ? 'text-slate-400' : 'text-slate-500'}`} />
                <span className={`text-sm font-semibold ${isActive ? 'text-[var(--accent-primary)]' : isDark ? 'text-white' : 'text-slate-800'}`}>
                  {t.label}
                </span>
                <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>{t.desc}</span>
              </button>
            );
          })}
        </div>
        <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
          Current: {effectiveTheme === 'dark' ? '🌙 Dark Mode' : '☀️ Light Mode'}
        </p>
      </div>

      <div>
        <label className={`block text-sm font-medium mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
          Accent Color
        </label>
        <div className="flex flex-wrap gap-3">
          {Object.entries(accentColors).map(([key, color]) => {
            const isActive = accentColor === key;
            return (
              <button
                key={key}
                onClick={() => setAccentColor(key)}
                className={`w-12 h-12 rounded-full transition-all flex items-center justify-center
                  ring-2 ring-offset-2 ${isDark ? 'ring-offset-slate-900' : 'ring-offset-white'}
                  ${isActive ? `ring-[${color.primary}]` : 'ring-transparent hover:ring-slate-400'}
                  ${color.bg}`}
                title={color.name}
              >
                {isActive && <Check className="w-5 h-5 text-white" />}
              </button>
            );
          })}
        </div>
        <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
          Selected: {accentColors[accentColor]?.name || 'Cyan'}
        </p>
      </div>

      {/* Live Preview */}
      <div className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-slate-100'} border ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
        <p className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Preview</p>
        <div className="flex items-center gap-3">
          <button className={`px-4 py-2 rounded-lg text-white font-medium bg-gradient-to-r ${accentColors[accentColor]?.gradient}`}>
            Primary Button
          </button>
          <button className={`px-4 py-2 rounded-lg font-medium border ${accentColors[accentColor]?.text} ${accentColors[accentColor]?.border} bg-transparent`}>
            Secondary
          </button>
          <span className={`px-3 py-1 rounded-full text-sm ${accentColors[accentColor]?.bg}/20 ${accentColors[accentColor]?.text}`}>
            Badge
          </span>
        </div>
      </div>
    </div>
  );

  const renderSystemSettings = () => (
    <div className="space-y-6">
      <p className={`${isDark ? 'text-slate-400' : 'text-slate-600'}`}>System configuration and data management.</p>

      <div className="space-y-4">
        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Database className={`w-5 h-5 ${isDark ? 'text-cyan-400' : 'text-cyan-600'}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>MPIS Integration</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Malaysian Patient Information System</p>
              </div>
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-600 border border-emerald-500/30">
              Connected
            </span>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className={`w-5 h-5 ${isDark ? 'text-cyan-400' : 'text-cyan-600'}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Security</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Two-factor authentication enabled</p>
              </div>
            </div>
            <button className={`px-3 py-1.5 rounded-lg text-sm border transition-all
              ${isDark ? 'bg-white/5 text-slate-300 hover:bg-white/10 border-white/10' : 'bg-white text-slate-600 hover:bg-slate-50 border-slate-300'}`}>
              Manage
            </button>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe className={`w-5 h-5 ${isDark ? 'text-cyan-400' : 'text-cyan-600'}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Language & Region</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>English (Malaysia)</p>
              </div>
            </div>
            <button className={`px-3 py-1.5 rounded-lg text-sm border transition-all
              ${isDark ? 'bg-white/5 text-slate-300 hover:bg-white/10 border-white/10' : 'bg-white text-slate-600 hover:bg-slate-50 border-slate-300'}`}>
              Change
            </button>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Clock className={`w-5 h-5 ${isDark ? 'text-cyan-400' : 'text-cyan-600'}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Session Timeout</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Auto-logout after 30 minutes of inactivity</p>
              </div>
            </div>
            <select className={`px-3 py-1.5 rounded-lg text-sm border focus:outline-none focus:border-cyan-500/50
              ${isDark ? 'bg-white/5 text-slate-300 border-white/10' : 'bg-white text-slate-600 border-slate-300'}`}>
              <option value="15">15 mins</option>
              <option value="30" selected>30 mins</option>
              <option value="60">1 hour</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>Settings</h1>
        <p className={`mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Manage your profile and system preferences</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Tabs Sidebar */}
        <GlassCard className="p-4 lg:col-span-1 h-fit">
          <nav className="space-y-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-left
                    ${activeTab === tab.id
                      ? `bg-cyan-500/20 ${isDark ? 'text-cyan-400' : 'text-cyan-600'} border border-cyan-500/30`
                      : `${isDark ? 'text-slate-400 hover:bg-white/5 hover:text-white' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'} border border-transparent`
                    }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </GlassCard>

        {/* Settings Content */}
        <GlassCard className="p-6 lg:col-span-3">
          <div className="mb-6">
            <h2 className={`text-xl font-semibold capitalize ${isDark ? 'text-white' : 'text-slate-800'}`}>{activeTab} Settings</h2>
          </div>

          {activeTab === 'profile' && renderProfileSettings()}
          {activeTab === 'notifications' && renderNotificationSettings()}
          {activeTab === 'appearance' && renderAppearanceSettings()}
          {activeTab === 'system' && renderSystemSettings()}

          {/* Profile Edit Footer */}
          {activeTab === 'profile' && isProfileEditing && (
            <div className={`flex justify-end gap-3 mt-8 pt-6 border-t ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
              <button
                onClick={() => setIsProfileEditing(false)}
                className={`px-4 py-2 rounded-lg transition-colors ${isDark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-800'}`}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveProfile}
                className="flex items-center gap-2 px-6 py-2 rounded-lg font-medium
                  bg-gradient-to-r from-cyan-500 to-blue-500 text-white
                  hover:from-cyan-400 hover:to-blue-400 transition-all"
              >
                <Save className="w-4 h-4" />
                Save Changes
              </button>
            </div>
          )}
        </GlassCard>
      </div>

      {/* Success Message Toast */}
      {showSuccessMessage && (
        <div className="fixed bottom-6 right-6 z-50 animate-fadeIn">
          <div className={`flex items-center gap-3 px-6 py-4 rounded-xl shadow-lg
            ${isDark ? 'bg-emerald-600/90' : 'bg-emerald-500'} text-white`}>
            <CheckCircle className="w-5 h-5" />
            <span className="font-medium">Profile saved successfully!</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
