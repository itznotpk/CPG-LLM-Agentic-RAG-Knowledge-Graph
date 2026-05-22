import React, { useState, useEffect, useMemo } from 'react';
import {
  Clock,
  Play,
  ChevronRight,
  ChevronDown,
  Bell,
  Eye,
  UserCheck,
  BookOpen,
  Timer,
  TrendingUp,
  TrendingDown,
  Minus,
  FileCheck,
  ArrowRight
} from 'lucide-react';
import { todaySchedule, patientRegistry } from '../../data/scheduleData';
import { getAllPatients } from '../../lib/supabase';
import { GlassCard } from '../shared/GlassCard';
import { Button } from '../shared/Button';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../shared/Notification';
import { useAuth } from '../../context/AuthContext';
import PatientQuickView from '../shared/PatientQuickView';

const sampleNotifications = [
  { id: 1, type: 'urgent', title: 'Critical Lab Result', message: 'Wong Kin Meng - HbA1c at 8.5%', time: '5 min ago', read: false },
  { id: 2, type: 'alert', title: 'Appointment Reminder', message: 'Siti Nurhaliza scheduled in 30 minutes', time: '10 min ago', read: false },
  { id: 3, type: 'info', title: 'MPIS Sync Complete', message: 'Patient records successfully updated', time: '1 hour ago', read: true },
  { id: 4, type: 'success', title: 'Care Plan Approved', message: 'Siti Nurhaliza care plan approved by specialist', time: '2 hours ago', read: true },
];

// Static impact metrics (in production: derived from care-plan pipeline)
const agenticImpact = {
  timeSavedMin: 47,
  cpgAligned: { count: 12, total: 14 },
  citations: 38,
  referrals: { count: 3, cpgJustified: 3 },
  // Yesterday baseline for trend calculation
  yesterday: {
    timeSavedMin: 39,
    cpgAlignedPct: 79,
    citations: 31,
    referrals: 3,
  },
};

// Trend badge: shows ▲/▼/– delta vs yesterday
const TrendBadge = ({ current, previous, suffix = '' }) => {
  const delta = current - previous;
  const pct = previous > 0 ? Math.round((delta / previous) * 100) : 0;
  if (delta === 0) return (
    <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-slate-400">
      <Minus className="w-3 h-3" strokeWidth={2} /> same as yesterday
    </span>
  );
  const up = delta > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${up ? 'text-emerald-500' : 'text-rose-400'
      }`}>
      {up
        ? <TrendingUp className="w-3 h-3" strokeWidth={2.5} />
        : <TrendingDown className="w-3 h-3" strokeWidth={2.5} />}
      {up ? '+' : ''}{pct}%{suffix} vs yesterday
    </span>
  );
};

const Home = ({ onStartConsult, onViewChart }) => {
  const { isDark, accent } = useTheme();
  const { profile } = useAuth();
  const toast = useToast();
  const [currentTime, setCurrentTime] = useState(new Date());
  const [schedule, setSchedule] = useState(todaySchedule);
  const [isScheduleExpanded, setIsScheduleExpanded] = useState(true);

  const avatarColors = [
    'bg-teal-100 text-teal-800',
    'bg-slate-200 text-slate-800',
    'bg-sky-100 text-sky-800',
    'bg-amber-100 text-amber-800',
    'bg-rose-100 text-rose-800',
    'bg-indigo-100 text-indigo-800',
  ];
  const darkAvatarColors = [
    'bg-teal-900/50 text-teal-200',
    'bg-slate-800 text-slate-200',
    'bg-sky-900/50 text-sky-200',
    'bg-amber-900/50 text-amber-200',
    'bg-rose-900/50 text-rose-200',
    'bg-indigo-900/50 text-indigo-200',
  ];

  const getInitials = (name) => {
    if (!name) return 'P';
    const parts = name.split(' ');
    return parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : name.substring(0, 2).toUpperCase();
  };

  const getAvatarColor = (name, dark) => {
    const palette = dark ? darkAvatarColors : avatarColors;
    if (!name) return palette[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return palette[Math.abs(hash) % palette.length];
  };

  const [patientRiskMap, setPatientRiskMap] = useState({});

  useEffect(() => {
    getAllPatients({}).then(({ patients }) => {
      const map = {};
      patients.forEach(p => { map[p.nsn] = p.riskLevel || 'low'; });
      setPatientRiskMap(map);
    });
  }, []);

  const getRiskLevel = (nric) => patientRiskMap[nric] || 'low';
  const isEmergency = (nric) => getRiskLevel(nric) === 'critical';
  const isHighRisk = (nric) => getRiskLevel(nric) === 'high';

  // Overdue follow-ups from registry (tcaDays ≤ 5 and status=follow-up, not on today's schedule)
  const overdueFollowUps = useMemo(() => {
    const scheduledNsns = new Set(todaySchedule.map(a => a.patient.nsn));
    return patientRegistry.filter(
      p => p.status === 'follow-up' && p.tcaDays != null && p.tcaDays <= 5 && !scheduledNsns.has(p.nsn)
    );
  }, []);

  // Next two scheduled patients still waiting
  const upcomingPatients = useMemo(() => {
    return [...schedule]
      .filter(a => a.status === 'waiting')
      .sort((a, b) => a.time.localeCompare(b.time))
      .slice(0, 2);
  }, [schedule]);

  // First critical patient
  const criticalPatient = useMemo(() => {
    return schedule.find(a => isEmergency(a.patient.nsn));
  }, [schedule, patientRiskMap]);

  const [categoryFilter, setCategoryFilter] = useState('all');

  const [selectedPatient, setSelectedPatient] = useState(null);
  const [selectedTriage, setSelectedTriage] = useState(null);
  const [isQuickViewOpen, setIsQuickViewOpen] = useState(false);

  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState(sampleNotifications);
  const unreadCount = notifications.filter(n => !n.read).length;

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  const getGreeting = () => {
    const h = currentTime.getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Welcome';
    return 'Good evening';
  };

  const formatDate = () =>
    currentTime.toLocaleDateString('en-MY', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  const formatTime = () =>
    currentTime.toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit' });

  const getStatusBadge = (status) => {
    const styles = {
      waiting: 'bg-amber-500/20 text-amber-600 border-amber-400/30',
      'in-progress': 'bg-blue-500/20 text-blue-500 border-blue-400/30',
      done: 'bg-emerald-500/20 text-emerald-600 border-emerald-400/30'
    };
    const labels = { waiting: 'Waiting', 'in-progress': 'In Consult', done: 'Completed' };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${styles[status] || ''}`}>
        {labels[status] || status}
      </span>
    );
  };

  const filteredSchedule = useMemo(() => {
    let filtered = [...schedule];
    if (categoryFilter === 'emergency') filtered = filtered.filter(a => isEmergency(a.patient.nsn));
    else if (categoryFilter === 'highRisk') filtered = filtered.filter(a => isHighRisk(a.patient.nsn) && !isEmergency(a.patient.nsn));
    return filtered.sort((a, b) => a.time.localeCompare(b.time));
  }, [schedule, categoryFilter, patientRiskMap]);

  const handleStartConsultClick = (appointment) => {
    setSchedule(prev => prev.map(a => a.id === appointment.id ? { ...a, status: 'in-progress' } : a));
    toast.success(`Started consultation for ${appointment.patient.name}`);
    onStartConsult(appointment.patient, appointment.triage);
  };

  const handleQuickView = (appointment) => {
    setSelectedPatient(appointment.patient);
    setSelectedTriage(appointment.triage);
    setIsQuickViewOpen(true);
  };

  const handleCloseQuickView = () => {
    setIsQuickViewOpen(false);
    setSelectedPatient(null);
    setSelectedTriage(null);
  };

  const cpgPct = Math.round((agenticImpact.cpgAligned.count / agenticImpact.cpgAligned.total) * 100);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className={`text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
            {getGreeting()},{' '}
            <span className={accent.text}>{profile?.full_name || profile?.name || 'Doctor'}</span>
          </h1>
          <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            {formatDate()} &nbsp;·&nbsp; <span className="ds-numeric font-medium">{formatTime()}</span>
          </p>
        </div>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            aria-label="Notifications"
            className={`p-3 rounded-xl transition-colors relative focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none
              ${isDark
                ? 'bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white focus-visible:ring-white/50'
                : 'bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-600 hover:text-slate-800 focus-visible:ring-slate-400'}`}
          >
            <Bell aria-hidden="true" className="w-5 h-5" strokeWidth={1.5} />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>
          {showNotifications && (
            <div className={`absolute right-0 top-full mt-2 w-80 rounded-xl shadow-2xl z-50 overflow-hidden
              ${isDark ? 'bg-slate-800 border border-white/10' : 'bg-white border border-slate-200'}`}>
              <div className={`p-4 border-b ${isDark ? 'border-white/10' : 'border-slate-100'}`}>
                <div className="flex items-center justify-between">
                  <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Notifications</h3>
                  {unreadCount > 0 && (
                    <button
                      onClick={() => setNotifications(prev => prev.map(n => ({ ...n, read: true })))}
                      className="text-xs text-[var(--accent-primary)] hover:underline"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {notifications.map((notif) => (
                  <div
                    key={notif.id}
                    onClick={() => setNotifications(prev => prev.map(n => n.id === notif.id ? { ...n, read: true } : n))}
                    className={`p-4 border-b cursor-pointer transition-colors
                      ${isDark ? 'border-white/5 hover:bg-white/5' : 'border-slate-50 hover:bg-slate-50'}
                      ${!notif.read ? (isDark ? 'bg-white/10' : 'bg-blue-50') : ''}`}
                  >
                    <div className="flex gap-3">
                      <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0
                        ${notif.type === 'urgent' ? 'bg-red-500' :
                          notif.type === 'alert' ? 'bg-amber-500' :
                            notif.type === 'success' ? 'bg-emerald-500' : 'bg-blue-500'}`}
                      />
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{notif.title}</p>
                        <p className={`text-xs mt-0.5 truncate ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{notif.message}</p>
                        <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{notif.time}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Today's Pulse strip */}
      <div>
        <p className="ds-eyebrow mb-3">
          Today's pulse
        </p>
        <GlassCard className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
          <div className={`divide-y ${isDark ? 'divide-white/5' : 'divide-slate-100'}`}>

            {/* Critical cue */}
            {criticalPatient ? (
              <div className={`flex items-center gap-4 px-5 py-3.5 border-l-2 border-rose-500 ${isDark ? 'bg-rose-500/8' : 'bg-rose-50/70'}`}>
                <div className="w-2 h-2 rounded-full bg-rose-500 flex-shrink-0 animate-pulse" />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${isDark ? 'text-rose-300' : 'text-rose-700'}`}>
                    {criticalPatient.patient.name} needs you now
                  </p>
                  <p className={`text-xs mt-0.5 ${isDark ? 'text-rose-400/70' : 'text-rose-500/80'}`}>
                    {criticalPatient.triage.chiefComplaint} · arrived {criticalPatient.time}
                  </p>
                </div>
                <Button
                  variant="danger"
                  size="sm"
                  icon={ArrowRight}
                  iconPosition="right"
                  onClick={() => handleStartConsultClick(criticalPatient)}
                  className="flex-shrink-0"
                >
                  See now
                </Button>
              </div>
            ) : (
              <div className={`flex items-center gap-4 px-5 py-3.5 border-l-2 border-emerald-500`}>
                <div className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>No critical patients at this time</p>
              </div>
            )}

            {/* Overdue follow-ups cue */}
            {overdueFollowUps.length > 0 && (
              <div className={`flex items-center gap-4 px-5 py-3.5 border-l-2 border-amber-400`}>
                <div className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
                    {overdueFollowUps.length} follow-up{overdueFollowUps.length > 1 ? 's' : ''} overdue
                  </p>
                  <p className={`text-xs mt-0.5 truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {overdueFollowUps.map(p => `${p.name.split(' ')[0]} (TCA ${p.tcaDays}d ago)`).join(', ')}
                  </p>
                </div>
              </div>
            )}

            {/* Next up cue */}
            {upcomingPatients.length > 0 && (
              <div className={`flex items-center gap-4 px-5 py-3.5 border-l-2 border-blue-400`}>
                <div className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    Next {upcomingPatients.length === 1 ? 'up' : `${upcomingPatients.length}`}
                  </p>
                  <p className={`text-xs mt-0.5 truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {upcomingPatients.map(a => `${a.patient.name.split(' ')[0]} ${a.time} — ${a.triage.chiefComplaint}`).join(' · ')}
                  </p>
                </div>
              </div>
            )}

          </div>
        </GlassCard>
      </div>

      {/* Agentic RAG Impact row */}
      <div>
        <p className="ds-eyebrow mb-3">
          Assistant impact today
        </p>
        <GlassCard className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
          <div className={`grid grid-cols-2 md:grid-cols-4 divide-y md:divide-y-0 md:divide-x ${isDark ? 'divide-white/10' : 'divide-slate-200'}`}>

            {/* Time reclaimed */}
            <div className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className={`p-1.5 rounded-lg ${isDark ? 'bg-teal-500/15' : 'bg-teal-50'}`}>
                  <Timer className={`w-3.5 h-3.5 ${isDark ? 'text-teal-400' : 'text-teal-600'}`} strokeWidth={2} />
                </span>
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Time reclaimed</span>
              </div>
              <p className={`text-4xl font-bold ds-numeric leading-none ${isDark ? 'text-teal-400' : 'text-teal-600'}`}>
                {agenticImpact.timeSavedMin}<span className={`text-lg font-medium ml-1 ${isDark ? 'text-teal-400/70' : 'text-teal-600/70'}`}>min</span>
              </p>
              <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>vs ~8 min/plan manual</p>
              <div className="mt-1.5">
                <TrendBadge current={agenticImpact.timeSavedMin} previous={agenticImpact.yesterday.timeSavedMin} />
              </div>
            </div>

            {/* CPG-aligned */}
            <div className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className={`p-1.5 rounded-lg ${isDark ? 'bg-violet-500/15' : 'bg-violet-50'}`}>
                  <FileCheck className={`w-3.5 h-3.5 ${isDark ? 'text-violet-400' : 'text-violet-600'}`} strokeWidth={2} />
                </span>
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>CPG-aligned</span>
              </div>
              <p className={`text-4xl font-bold ds-numeric leading-none ${isDark ? 'text-violet-400' : 'text-violet-600'}`}>
                {cpgPct}<span className={`text-lg font-medium ml-0.5 ${isDark ? 'text-violet-400/70' : 'text-violet-600/70'}`}>%</span>
              </p>
              <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                {agenticImpact.cpgAligned.count} of {agenticImpact.cpgAligned.total} plans
              </p>
              <div className="mt-1.5">
                <TrendBadge current={cpgPct} previous={agenticImpact.yesterday.cpgAlignedPct} />
              </div>
            </div>

            {/* Citations issued */}
            <div className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className={`p-1.5 rounded-lg ${isDark ? 'bg-sky-500/15' : 'bg-sky-50'}`}>
                  <BookOpen className={`w-3.5 h-3.5 ${isDark ? 'text-sky-400' : 'text-sky-600'}`} strokeWidth={2} />
                </span>
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Citations issued</span>
              </div>
              <p className={`text-4xl font-bold ds-numeric leading-none ${isDark ? 'text-sky-400' : 'text-sky-600'}`}>
                {agenticImpact.citations}
              </p>
              <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>evidence-backed decisions</p>
              <div className="mt-1.5">
                <TrendBadge current={agenticImpact.citations} previous={agenticImpact.yesterday.citations} />
              </div>
            </div>

            {/* Referrals */}
            <div className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className={`p-1.5 rounded-lg ${isDark ? 'bg-amber-500/15' : 'bg-amber-50'}`}>
                  <UserCheck className={`w-3.5 h-3.5 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} strokeWidth={2} />
                </span>
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Referrals</span>
              </div>
              <p className={`text-4xl font-bold ds-numeric leading-none ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                {agenticImpact.referrals.count}
              </p>
              <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                all {agenticImpact.referrals.cpgJustified} CPG-justified
              </p>
              <div className="mt-1.5">
                <TrendBadge current={agenticImpact.referrals.count} previous={agenticImpact.yesterday.referrals} />
              </div>
            </div>

          </div>
        </GlassCard>
      </div>

      {/* Schedule */}
      <GlassCard className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
        <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? 'border-white/10' : 'border-slate-100'}`}>
          <button
            onClick={() => setIsScheduleExpanded(!isScheduleExpanded)}
            aria-label="Toggle Schedule"
            className={`text-base font-semibold flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'} hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-lg`}
          >
            <Clock aria-hidden="true" className={`w-4 h-4 ${accent.text}`} strokeWidth={1.5} />
            Today's patients
            <ChevronDown aria-hidden="true" className={`w-4 h-4 transition-transform duration-200 ${isScheduleExpanded ? '' : '-rotate-90'}`} strokeWidth={1.5} />
          </button>
          {/* Filter pills */}
          <div className="flex items-center gap-1.5">
            {['all', 'emergency', 'highRisk'].map((f) => (
              <button
                key={f}
                onClick={() => setCategoryFilter(f)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors
                  ${categoryFilter === f
                    ? f === 'emergency'
                      ? 'bg-rose-500 text-white'
                      : f === 'highRisk'
                        ? 'bg-amber-500 text-white'
                        : (isDark ? 'bg-white/20 text-white' : 'bg-slate-800 text-white')
                    : isDark ? 'bg-white/5 text-slate-400 hover:bg-white/10' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                  }`}
              >
                {f === 'all' ? 'All' : f === 'emergency' ? 'Critical' : 'High risk'}
              </button>
            ))}
          </div>
        </div>

        {isScheduleExpanded && (
          <div className="space-y-0 divide-y divide-slate-100 dark:divide-white/5 px-5 py-3">
            {filteredSchedule.length === 0 ? (
              <div className={`text-center py-10 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                No appointments match the current filter
              </div>
            ) : filteredSchedule.map((appointment) => (
              <div
                key={appointment.id}
                className={`py-4 border-l-2 pl-4 transition-colors
                  ${isEmergency(appointment.patient.nsn)
                    ? 'border-l-rose-500 ' + (isDark ? 'bg-rose-500/5' : 'bg-rose-50/60')
                    : isHighRisk(appointment.patient.nsn)
                      ? 'border-l-amber-400 ' + (isDark ? 'bg-amber-500/5' : 'bg-amber-50/60')
                      : 'border-l-transparent hover:' + (isDark ? 'bg-white/5' : 'bg-slate-50')
                  }`}
              >
                <div className="flex items-start gap-4">
                  {/* Time */}
                  <div className="flex flex-col items-start min-w-[72px] flex-shrink-0">
                    <span className={`text-base font-semibold ds-numeric leading-none ${isDark ? 'text-white' : 'text-slate-800'}`}>{appointment.time}</span>
                    {isEmergency(appointment.patient.nsn) && (
                      <span className={`mt-1.5 text-[10px] font-bold tracking-wider uppercase ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>Critical</span>
                    )}
                    {!isEmergency(appointment.patient.nsn) && isHighRisk(appointment.patient.nsn) && (
                      <span className={`mt-1.5 text-[10px] font-bold tracking-wider uppercase ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>High risk</span>
                    )}
                  </div>

                  {/* Patient info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`w-9 h-9 rounded-full flex items-center justify-center font-semibold text-sm flex-shrink-0 ${getAvatarColor(appointment.patient.name, isDark)}`}>
                        {getInitials(appointment.patient.name)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className={`font-medium text-sm truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>{appointment.patient.name}</h3>
                          {getStatusBadge(appointment.status)}
                        </div>
                        <p className={`text-xs ds-numeric ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                          {appointment.patient.age} y/o · {appointment.patient.gender}
                        </p>
                      </div>
                    </div>
                    <div className={`ml-12 px-3 py-2 rounded-lg ${isDark ? 'bg-black/20' : 'bg-white/60'}`}>
                      <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Chief complaint</p>
                      <p className={`text-sm font-medium mt-0.5 ${isDark ? 'text-white' : 'text-slate-800'}`}>{appointment.triage.chiefComplaint}</p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col gap-2 ml-4 flex-shrink-0">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={Eye}
                      onClick={() => handleQuickView(appointment)}
                      className="min-w-[128px]"
                    >
                      Quick view
                    </Button>
                    {appointment.status === 'waiting' && (
                      <Button
                        variant="primary"
                        size="sm"
                        icon={Play}
                        onClick={() => handleStartConsultClick(appointment)}
                        className="min-w-[128px]"
                      >
                        Start consult
                      </Button>
                    )}
                    {appointment.status === 'in-progress' && (
                      <Button
                        variant="primary"
                        size="sm"
                        icon={ChevronRight}
                        iconPosition="right"
                        onClick={() => handleStartConsultClick(appointment)}
                        className="min-w-[128px]"
                      >
                        Resume
                      </Button>
                    )}
                    {appointment.status === 'done' && (
                      <span className="px-4 py-2.5 rounded-lg text-sm text-emerald-600 bg-emerald-500/10 font-medium text-center min-w-[128px]">
                        Completed
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      <PatientQuickView
        patient={selectedPatient}
        triage={selectedTriage}
        isOpen={isQuickViewOpen}
        onClose={handleCloseQuickView}
        onExportPDF={() => toast.success('Patient summary exported as PDF')}
        onExportCSV={() => toast.success('Patient data exported as CSV')}
        onViewChart={onViewChart}
      />
    </div>
  );
};

export default Home;
