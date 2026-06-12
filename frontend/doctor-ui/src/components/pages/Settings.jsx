import React, { useState, useEffect } from 'react';
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
  Loader2,
  RotateCcw,
  Cpu,
  BarChart3,
  Download,
  LogOut
} from 'lucide-react';
import { GlassCard } from '../shared/GlassCard';
import { Button } from '../shared/Button';
import { useTheme, accentColors } from '../../context/ThemeContext';
import { useToast } from '../shared/Notification';
import { supabase, updateProfile } from '../../lib/supabase';
import { getEngineHealth } from '../../lib/clinicalApi';
import { safeJson } from '../../lib/helpers';
import { IDLE_TIMEOUT_KEY, DEFAULT_IDLE_MIN, getIdleTimeoutMin } from '../../hooks/useIdleLogout';

export const ANALYTICS_DAYS_KEY = 'cp_analytics_days';
export const getDefaultAnalyticsDays = () => {
  const v = Number(localStorage.getItem(ANALYTICS_DAYS_KEY));
  return [7, 30, 90].includes(v) ? v : 30;
};

const NOTIF_PREFS_KEY = 'cp_notification_prefs_v1';
const NOTIF_DEFAULTS = { email: true, push: true, sms: false, emergencyAlerts: true };

const loadNotifPrefs = () => {
  try {
    return { ...NOTIF_DEFAULTS, ...JSON.parse(localStorage.getItem(NOTIF_PREFS_KEY) || '{}'), emergencyAlerts: true };
  } catch {
    return NOTIF_DEFAULTS;
  }
};

const Settings = ({ profile, setProfile }) => {
  const { theme, setTheme, accentColor, setAccentColor, effectiveTheme, isDark, accent } = useTheme();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('profile');
  const [notifications, setNotifications] = useState(loadNotifPrefs);

  const [isProfileEditing, setIsProfileEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  // Draft edits live here, NOT on the profile prop — setProfile from App is
  // refreshProfile (a DB re-fetch), so mutating through it never persisted.
  const [form, setForm] = useState({});

  const startEditing = () => {
    setForm({
      name: profile?.name || '',
      specialty: profile?.specialty || '',
      phone: profile?.phone || '',
      license: profile?.license || '',
      facility: profile?.facility || '',
    });
    setIsProfileEditing(true);
  };

  const handleSaveProfile = async () => {
    setIsSaving(true);
    const { success, error } = await updateProfile({
      full_name: form.name,
      specialty: form.specialty,
      phone: form.phone,
      license_number: form.license,
      facility: form.facility,
    });
    setIsSaving(false);
    if (success) {
      await setProfile(); // refreshProfile — reload from DB so the whole app updates
      setIsProfileEditing(false);
      toast.success('Profile saved');
    } else {
      toast.error(error?.message || 'Failed to save profile');
    }
  };

  const persistNotif = (next) => {
    try { localStorage.setItem(NOTIF_PREFS_KEY, JSON.stringify(next)); } catch { /* no-op */ }
    setNotifications(next);
  };

  const toggleNotif = async (key) => {
    if (key === 'emergencyAlerts') return; // always on
    // Enabling push requires real browser permission — request it and only
    // turn the toggle on when granted.
    if (key === 'push' && !notifications.push && 'Notification' in window) {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        toast.warning('Browser notifications are blocked — allow them in your browser settings first');
        return;
      }
    }
    persistNotif({ ...notifications, [key]: !notifications[key] });
  };

  // ── System tab live state ──
  const [conn, setConn] = useState({ status: 'checking' });
  const checkConnection = async () => {
    setConn({ status: 'checking' });
    const t0 = performance.now();
    const { count, error } = await supabase
      .from('patients')
      .select('nric', { count: 'exact', head: true });
    if (error) setConn({ status: 'offline', detail: error.message });
    else setConn({ status: 'connected', latencyMs: Math.round(performance.now() - t0), patients: count ?? 0 });
  };
  useEffect(() => { checkConnection(); }, []);

  const [isSendingReset, setIsSendingReset] = useState(false);
  const handlePasswordReset = async () => {
    if (!profile?.email) { toast.error('No email on profile'); return; }
    setIsSendingReset(true);
    const { error } = await supabase.auth.resetPasswordForEmail(profile.email);
    setIsSendingReset(false);
    if (error) toast.error(error.message);
    else toast.success(`Password reset link sent to ${profile.email}`);
  };

  const [timeoutMin, setTimeoutMin] = useState(getIdleTimeoutMin);
  const changeTimeout = (min) => {
    setTimeoutMin(min);
    try { localStorage.setItem(IDLE_TIMEOUT_KEY, String(min)); } catch { /* no-op */ }
    toast.success(`Auto-logout set to ${min >= 60 ? `${min / 60} hour` : `${min} minutes`} of inactivity`);
  };

  // AI clinical engine (FastAPI pipeline) — live health check, like the
  // Patient Application Store row, so a clinician sees an outage BEFORE
  // starting a consultation rather than mid-pipeline.
  const [engine, setEngine] = useState({ status: 'checking' });
  const checkEngine = async () => {
    setEngine({ status: 'checking' });
    try {
      const h = await getEngineHealth();
      setEngine({ status: 'online', latencyMs: h.latencyMs });
    } catch (e) {
      setEngine({ status: 'offline', detail: e.message === 'Failed to fetch' ? 'backend unreachable' : e.message });
    }
  };
  useEffect(() => { checkEngine(); }, []);

  // Default Clinical Performance window — consumed by AnalyticsView on mount.
  const [analyticsDays, setAnalyticsDays] = useState(getDefaultAnalyticsDays);
  const changeAnalyticsDays = (d) => {
    setAnalyticsDays(d);
    try { localStorage.setItem(ANALYTICS_DAYS_KEY, String(d)); } catch { /* no-op */ }
    toast.success(`Clinical Performance now opens on the ${d}-day window`);
  };

  // Audit export: last 90 days of consultations as CSV.
  const [isExporting, setIsExporting] = useState(false);
  const exportConsultLog = async () => {
    setIsExporting(true);
    const since = new Date(Date.now() - 90 * 86400000).toISOString();
    const { data, error } = await supabase
      .from('consultations')
      .select('id, consultation_number, created_at, patient_nric, diagnoses, safety_flags, referrals, next_review')
      .gte('created_at', since)
      .order('created_at', { ascending: false });
    setIsExporting(false);
    if (error) { toast.error(error.message); return; }
    const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const rows = [['Consultation', 'Date', 'Patient NRIC', 'Diagnoses', 'Safety flags', 'Referrals', 'Next review']];
    (data || []).forEach(c => rows.push([
      c.consultation_number ?? c.id,
      new Date(c.created_at).toLocaleString('en-GB'),
      c.patient_nric,
      safeJson(c.diagnoses).map(d => (typeof d === 'object' ? d.name : d)).join('; '),
      safeJson(c.safety_flags).length,
      safeJson(c.referrals).length,
      c.next_review || '',
    ]));
    const blob = new Blob([rows.map(r => r.map(esc).join(',')).join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `consultation_log_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Exported ${data?.length || 0} consultations (last 90 days)`);
  };

  const resetDevicePrefs = () => {
    [NOTIF_PREFS_KEY, 'cp_notif_read_v1', IDLE_TIMEOUT_KEY, ANALYTICS_DAYS_KEY].forEach(k => {
      try { localStorage.removeItem(k); } catch { /* no-op */ }
    });
    setNotifications(NOTIF_DEFAULTS);
    setTimeoutMin(DEFAULT_IDLE_MIN);
    setAnalyticsDays(30);
    toast.success('Device preferences reset to defaults');
  };

  const [isSigningOutAll, setIsSigningOutAll] = useState(false);
  const handleSignOutAll = async () => {
    setIsSigningOutAll(true);
    const { error } = await supabase.auth.signOut({ scope: 'global' });
    setIsSigningOutAll(false);
    if (error) toast.error(error.message);
    // success needs no toast — the auth listener redirects to /login
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
          <div className={`w-24 h-24 rounded-full bg-teal-500/20 border-2 border-teal-500/30
            flex items-center justify-center text-teal-400 text-2xl font-semibold`}>
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
              <Button variant="secondary" size="sm" icon={Edit3} onClick={startEditing}>
                Edit Profile
              </Button>
            )}
          </div>
          {isProfileEditing && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={`block text-sm mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Full Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className={`w-full px-4 py-2.5 rounded-xl border
                focus:outline-none focus:border-[var(--accent-primary)]/50 transition-all
                ${isDark ? 'bg-white/5 border-white/10 text-white' : 'bg-slate-100 border-slate-200 text-slate-800'}`}
                />
              </div>
              <div>
                <label className={`block text-sm mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Specialty</label>
                <input
                  type="text"
                  value={form.specialty}
                  onChange={(e) => setForm({ ...form, specialty: e.target.value })}
                  className={`w-full px-4 py-2.5 rounded-xl border
                focus:outline-none focus:border-[var(--accent-primary)]/50 transition-all
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
              disabled
              title="Email is your sign-in identity and can't be changed here"
              className={`w-full px-4 py-2.5 rounded-xl border opacity-60 cursor-not-allowed
                ${isDark ? 'bg-white/5 border-white/10 text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-500'}`}
            />
          </div>
          <div>
            <label className={`block text-sm mb-2 flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              <Phone className="w-4 h-4" /> Phone
            </label>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
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
              value={form.license}
              onChange={(e) => setForm({ ...form, license: e.target.value })}
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
              value={form.facility}
              onChange={(e) => setForm({ ...form, facility: e.target.value })}
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
      <p className={`${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
        Configure how you receive notifications and alerts. Preferences are saved on this device.
      </p>

      <div className="space-y-4">
        {[
          { key: 'email', label: 'Email Notifications', desc: 'Receive updates via email' },
          { key: 'push', label: 'Push Notifications', desc: 'Browser push notifications' },
          { key: 'sms', label: 'SMS Alerts', desc: 'Text message notifications' },
          { key: 'emergencyAlerts', label: 'Emergency Alerts', desc: 'Critical patient alerts (always on)', locked: true }
        ].map((item) => (
          <div key={item.key} className={`flex items-center justify-between p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
            <div>
              <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{item.label}</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{item.desc}</p>
            </div>
            <button
              onClick={() => toggleNotif(item.key)}
              disabled={item.locked}
              title={item.locked ? 'Emergency alerts cannot be disabled' : ''}
              className={`w-12 h-6 rounded-full transition-all relative
                ${item.locked ? 'cursor-not-allowed opacity-70' : ''}
                ${notifications[item.key] ? 'bg-[var(--accent-primary)]' : isDark ? 'bg-slate-700' : 'bg-slate-300'}`}
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
              <Database className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Patient Application Store</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {conn.status === 'connected'
                    ? `Patient registry reachable · ${conn.patients} records · ${conn.latencyMs} ms`
                    : conn.status === 'offline'
                      ? `Connection failed: ${conn.detail}`
                      : 'Checking connection…'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {conn.status === 'connected' && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-600 border border-emerald-500/30">
                  Connected
                </span>
              )}
              {conn.status === 'offline' && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-rose-500/20 text-rose-600 border border-rose-500/30">
                  Offline
                </span>
              )}
              {conn.status === 'checking' && (
                <Loader2 className={`w-4 h-4 animate-spin ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
              )}
              <Button variant="secondary" size="sm" icon={RotateCcw} onClick={checkConnection} disabled={conn.status === 'checking'}>
                Re-test
              </Button>
            </div>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Cpu className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>AI Clinical Engine</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {engine.status === 'online'
                    ? `CPG pipeline reachable · ${engine.latencyMs} ms`
                    : engine.status === 'offline'
                      ? `Unavailable: ${engine.detail} — consultations cannot run`
                      : 'Checking pipeline…'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {engine.status === 'online' && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-600 border border-emerald-500/30">
                  Online
                </span>
              )}
              {engine.status === 'offline' && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-rose-500/20 text-rose-600 border border-rose-500/30">
                  Offline
                </span>
              )}
              {engine.status === 'checking' && (
                <Loader2 className={`w-4 h-4 animate-spin ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
              )}
              <Button variant="secondary" size="sm" icon={RotateCcw} onClick={checkEngine} disabled={engine.status === 'checking'}>
                Re-test
              </Button>
            </div>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Security</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Send a password reset link to {profile?.email || 'your email'}
                </p>
              </div>
            </div>
            <Button variant="secondary" size="sm" onClick={handlePasswordReset} disabled={isSendingReset}>
              {isSendingReset ? 'Sending…' : 'Reset password'}
            </Button>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Language & Region</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>English (Malaysia)</p>
              </div>
            </div>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Clock className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Session Timeout</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Auto-logout after {timeoutMin >= 60 ? `${timeoutMin / 60} hour` : `${timeoutMin} minutes`} of inactivity
                </p>
              </div>
            </div>
            <select
              value={timeoutMin}
              onChange={(e) => changeTimeout(Number(e.target.value))}
              className={`px-3 py-1.5 rounded-lg text-sm border focus:outline-none focus:border-[var(--accent-primary)]/50
              ${isDark ? 'bg-white/5 text-slate-300 border-white/10' : 'bg-white text-slate-600 border-slate-300'}`}
            >
              <option value="15">15 mins</option>
              <option value="30">30 mins</option>
              <option value="60">1 hour</option>
            </select>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BarChart3 className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Default Performance Window</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Clinical Performance opens on the last {analyticsDays} days
                </p>
              </div>
            </div>
            <select
              value={analyticsDays}
              onChange={(e) => changeAnalyticsDays(Number(e.target.value))}
              className={`px-3 py-1.5 rounded-lg text-sm border focus:outline-none focus:border-[var(--accent-primary)]/50
              ${isDark ? 'bg-white/5 text-slate-300 border-white/10' : 'bg-white text-slate-600 border-slate-300'}`}
            >
              <option value="7">7 days</option>
              <option value="30">30 days</option>
              <option value="90">90 days</option>
            </select>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Download className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Export Consultation Log</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Last 90 days as CSV — diagnoses, safety flags, referrals, reviews
                </p>
              </div>
            </div>
            <Button variant="secondary" size="sm" icon={isExporting ? Loader2 : Download} onClick={exportConsultLog} disabled={isExporting}>
              {isExporting ? 'Exporting…' : 'Export CSV'}
            </Button>
          </div>
        </div>

        <div className={`p-4 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <RotateCcw className={`w-5 h-5 ${accent.text}`} />
              <div>
                <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>This Device</p>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Reset local preferences, or sign out of every signed-in device
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={resetDevicePrefs}>
                Reset preferences
              </Button>
              <Button variant="secondary" size="sm" icon={LogOut} onClick={handleSignOutAll} disabled={isSigningOutAll}>
                {isSigningOutAll ? 'Signing out…' : 'Sign out all devices'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className={`text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>Settings</h1>
        <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Manage your profile and system preferences</p>
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
                      ? `bg-[var(--accent-primary)]/10 ${accent.text} border border-[var(--accent-primary)]/20`
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
              <Button variant="ghost" onClick={() => setIsProfileEditing(false)} disabled={isSaving}>
                Cancel
              </Button>
              <Button variant="primary" icon={isSaving ? Loader2 : Save} onClick={handleSaveProfile} disabled={isSaving}>
                {isSaving ? 'Saving…' : 'Save Changes'}
              </Button>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
};

export default Settings;
