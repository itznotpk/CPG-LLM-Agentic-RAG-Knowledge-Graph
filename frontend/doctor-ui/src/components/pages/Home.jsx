import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play,
  ChevronRight,
  ChevronDown,
  Bell,
  Eye,
  ShieldAlert,
  BookOpen,
  Timer,
  TrendingUp,
  TrendingDown,
  Minus,
  FileCheck,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight
} from 'lucide-react';
import { todaySchedule, patientRegistry } from '../../data/scheduleData';
import { supabase, getAllPatients, getAllPatientConsultations } from '../../lib/supabase';
import { safeJson, getInitials, getAvatarColor, getPatientAvatarColor } from '../../lib/helpers';
import { GlassCard } from '../shared/GlassCard';
import { Button } from '../shared/Button';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../shared/Notification';
import { useAuth } from '../../context/AuthContext';
import PatientQuickView from '../shared/PatientQuickView';
import { useNotifications } from '../../hooks/useNotifications';



// Compact day-over-day pill. Shows the ABSOLUTE delta (+64m), not a percent —
// at single-digit daily volumes "+300%" reads as noise and misleads.
const TrendBadge = ({ current, previous, suffix = '' }) => {
  const delta = current - previous;
  if (delta === 0) return (
    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-500/10 text-slate-400">
      <Minus className="w-2.5 h-2.5" strokeWidth={2} /> vs yday
    </span>
  );
  const up = delta > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold
      ${up ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-400'}`}>
      {up
        ? <TrendingUp className="w-2.5 h-2.5" strokeWidth={2.5} />
        : <TrendingDown className="w-2.5 h-2.5" strokeWidth={2.5} />}
      {up ? '+' : ''}{delta}{suffix} vs yday
    </span>
  );
};

const Home = ({ onStartConsult, onViewChart }) => {
  const { isDark, accent } = useTheme();
  const { profile } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [currentTime, setCurrentTime] = useState(new Date());
  const [schedule, setSchedule] = useState(todaySchedule);
  const [isScheduleExpanded, setIsScheduleExpanded] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [upcomingFollowUps, setUpcomingFollowUps] = useState([]);
  const [loadingFollowUps, setLoadingFollowUps] = useState(true);
  const [isFollowUpsExpanded, setIsFollowUpsExpanded] = useState(true);
  const [followUpSearchTerm, setFollowUpSearchTerm] = useState('');


  const [impact, setImpact] = useState({
    timeSavedMin: 0,
    cpgAligned: { count: 0, total: 1 },
    completed: 0,
    started: 0,
    citations: 0,
    intercepts: 0,
    yesterday: { timeSavedMin: 0, cpgAlignedPct: 0, citations: 0, intercepts: 0 },
  });

  useEffect(() => {
    const fetchImpact = async () => {
      const todayStr = new Date().toISOString().split('T')[0];
      const yesterdayStr = new Date(Date.now() - 86400000).toISOString().split('T')[0];
      const twoDaysAgo = new Date(Date.now() - 2 * 86400000).toISOString();

      const { data } = await supabase
        .from('consultations')
        .select('created_at, updated_at, cpg_references, diagnoses, safety_flags')
        .gte('created_at', twoDaysAgo)
        .order('created_at', { ascending: false });

      if (!data) return;

      // Manual baseline = 10.5 min, the average Malaysian consultation length
      // cited in the project report's problem statement. Time saved is measured
      // per completed plan: baseline minus the consult's actual wall time
      // (created_at → last update), clamped to [0, baseline]. Abandoned
      // mid-wizard rows (no diagnoses saved) count nothing.
      const MANUAL_PLAN_BASELINE_MIN = 10.5;

      const compute = (rows) => {
        let cpgCount = 0, cites = 0, intercepts = 0, savedMin = 0, completed = 0;
        rows.forEach(c => {
          const isCompleted = safeJson(c.diagnoses).length > 0;
          const cpgRefs = safeJson(c.cpg_references);
          if (cpgRefs.length > 0) cites += cpgRefs.length;
          // Stage-6 intercepts: CRITICAL/MAJOR flags surfaced before sign-off.
          safeJson(c.safety_flags).forEach(f => {
            const sev = (f.severity || '').toUpperCase();
            if (sev === 'CRITICAL' || sev === 'MAJOR') intercepts++;
          });
          if (!isCompleted) return;
          completed++;
          if (cpgRefs.length > 0) cpgCount++;
          const durMin = (new Date(c.updated_at) - new Date(c.created_at)) / 60000;
          savedMin += Math.min(Math.max(MANUAL_PLAN_BASELINE_MIN - durMin, 0), MANUAL_PLAN_BASELINE_MIN);
        });
        return {
          timeSavedMin: Math.round(savedMin),
          cpgAligned: { count: cpgCount, total: Math.max(completed, 1) },
          completed,
          started: rows.length,
          citations: cites,
          intercepts,
        };
      };

      const todayRows = data.filter(c => c.created_at.startsWith(todayStr));
      const yestRows  = data.filter(c => c.created_at.startsWith(yesterdayStr));
      const t = compute(todayRows);
      const y = compute(yestRows);
      const yPct = Math.round((y.cpgAligned.count / y.cpgAligned.total) * 100);

      setImpact({ ...t, yesterday: { timeSavedMin: y.timeSavedMin, cpgAlignedPct: yPct, citations: y.citations, intercepts: y.intercepts } });
    };
    fetchImpact();
  }, []);

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

  // Filtered follow-up patients list
  const filteredFollowUps = useMemo(() => {
    if (!followUpSearchTerm.trim()) return upcomingFollowUps;
    const term = followUpSearchTerm.toLowerCase();
    return upcomingFollowUps.filter(item =>
      item.name.toLowerCase().includes(term) ||
      (item.nsn && item.nsn.toLowerCase().includes(term))
    );
  }, [upcomingFollowUps, followUpSearchTerm]);

  // Active consultation (if any patient is currently in-progress)
  const activeAppointment = useMemo(() => {
    return schedule.find(a => a.status === 'in-progress');
  }, [schedule]);

  const [selectedPatient, setSelectedPatient] = useState(null);
  const [selectedTriage, setSelectedTriage] = useState(null);
  const [isQuickViewOpen, setIsQuickViewOpen] = useState(false);

  const [showNotifications, setShowNotifications] = useState(false);
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications();

  // Tap a notification → mark read and jump to the patient it concerns.
  // MyPatients consumes selectPatientNric/statusFilter from location.state.
  const openNotification = (notif) => {
    markRead(notif.id);
    if (!notif.nric) return;
    setShowNotifications(false);
    navigate('/patients', {
      state: {
        selectPatientNric: notif.nric,
        ...(notif.statusFilter ? { statusFilter: notif.statusFilter } : {}),
      },
    });
  };

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
      waiting: 'bg-amber-500/20 text-amber-600 border-amber-400/30 dark:text-amber-400',
      'in-progress': 'bg-blue-500/20 text-blue-600 border-blue-400/30 dark:text-blue-400',
      done: 'bg-emerald-500/20 text-emerald-600 border-emerald-400/30 dark:text-emerald-400'
    };
    const labels = { waiting: 'Scheduled', 'in-progress': 'In Queue', done: 'Completed' };
    return (
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${styles[status] || ''}`}>
        {labels[status] || status}
      </span>
    );
  };

  // Helper to calculate initial/mock follow-ups from local registry
  const getInitialFollowUps = () => {
    return patientRegistry
      .filter(p => p.status === 'follow-up' && p.nextReview)
      .map(p => {
        const reviewDate = new Date(p.nextReview);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        reviewDate.setHours(0, 0, 0, 0);
        const tcaDays = Math.ceil((reviewDate - today) / (1000 * 60 * 60 * 24));
        return {
          id: p.id,
          name: p.name,
          nsn: p.nsn,
          gender: p.gender,
          age: p.age,
          nextReview: p.nextReview,
          tcaDays
        };
      })
      .sort((a, b) => a.nextReview.localeCompare(b.nextReview));
  };

  const calculateTcaDays = (reviewDateStr) => {
    const reviewDate = new Date(reviewDateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    reviewDate.setHours(0, 0, 0, 0);
    return Math.ceil((reviewDate - today) / (1000 * 60 * 60 * 24));
  };

  // Synchronize upcoming follow-up dates dynamically with the Patient database & consultations
  useEffect(() => {
    const loadLiveFollowUps = async () => {
      setLoadingFollowUps(true);
      try {
        const { patients, error } = await getAllPatients({});
        if (error || !patients) {
          setUpcomingFollowUps(getInitialFollowUps());
          setLoadingFollowUps(false);
          return;
        }

        // Parallel fetch of latest consultations to capture nextReview follow-up dates
        const results = await Promise.all(
          patients.map(async (patient) => {
            // ONLY select patients who are marked as requiring follow-up
            if (patient.status !== 'follow-up') {
              return null;
            }

            try {
              const res = await getAllPatientConsultations(patient.nsn, 1);
              if (res.consultations && res.consultations.length > 0) {
                const consult = res.consultations[0];
                if (consult.nextReview) {
                  return {
                    id: patient.id,
                    name: patient.name,
                    nsn: patient.nsn,
                    gender: patient.gender,
                    age: patient.age,
                    nextReview: consult.nextReview,
                    tcaDays: calculateTcaDays(consult.nextReview)
                  };
                }
              }
              if (patient.nextReview) {
                return {
                  id: patient.id,
                  name: patient.name,
                  nsn: patient.nsn,
                  gender: patient.gender,
                  age: patient.age,
                  nextReview: patient.nextReview,
                  tcaDays: calculateTcaDays(patient.nextReview)
                };
              }
              return null;
            } catch {
              if (patient.nextReview) {
                return {
                  id: patient.id,
                  name: patient.name,
                  nsn: patient.nsn,
                  gender: patient.gender,
                  age: patient.age,
                  nextReview: patient.nextReview,
                  tcaDays: calculateTcaDays(patient.nextReview)
                };
              }
              return null;
            }
          })
        );

        const filtered = results
          .filter(r => r !== null)
          .sort((a, b) => a.nextReview.localeCompare(b.nextReview));

        if (filtered.length > 0) {
          setUpcomingFollowUps(filtered);
        } else {
          setUpcomingFollowUps(getInitialFollowUps());
        }
      } catch (err) {
        console.error('Error loading live follow-ups:', err);
        setUpcomingFollowUps(getInitialFollowUps());
      } finally {
        setLoadingFollowUps(false);
      }
    };

    loadLiveFollowUps();
  }, []);

  // Filter patient schedule based on search input and status tabs
  const filteredSchedule = useMemo(() => {
    return schedule
      .filter((appointment) => {
        // Status filter
        if (statusFilter !== 'all' && appointment.status !== statusFilter) {
          return false;
        }
        // Search filter
        if (searchTerm.trim() !== '') {
          const query = searchTerm.toLowerCase();
          const nameMatch = appointment.patient.name.toLowerCase().includes(query);
          const chiefMatch = appointment.triage.chiefComplaint.toLowerCase().includes(query);
          const ageMatch = appointment.patient.age.toString().includes(query);
          const genderMatch = appointment.patient.gender.toLowerCase().startsWith(query);
          return nameMatch || chiefMatch || ageMatch || genderMatch;
        }
        return true;
      })
      .sort((a, b) => a.time.localeCompare(b.time));
  }, [schedule, statusFilter, searchTerm]);

  // Compute schedule queue count statistics for filter badges
  const counts = useMemo(() => {
    return {
      all: schedule.length,
      waiting: schedule.filter(a => a.status === 'waiting').length,
      'in-progress': schedule.filter(a => a.status === 'in-progress').length,
      done: schedule.filter(a => a.status === 'done').length,
    };
  }, [schedule]);

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

  const handleFollowUpPatientClick = (patient) => {
    navigate('/patients', {
      state: {
        selectPatientNric: patient.nsn,
        statusFilter: 'follow-up'
      }
    });
  };

  const cpgPct = Math.round((impact.cpgAligned.count / impact.cpgAligned.total) * 100);

  return (
    <div className="space-y-6">
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
          {/* Click-outside catcher */}
          {showNotifications && (
            <div className="fixed inset-0 z-40" onClick={() => setShowNotifications(false)} />
          )}
          <AnimatePresence>
            {showNotifications && (
              <motion.div
                initial={{ opacity: 0, scale: 0.92, y: -10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -6 }}
                transition={{ duration: 0.28, ease: [0.32, 0.72, 0, 1] }}
                className="absolute right-0 top-full mt-3 w-[24rem] max-w-[calc(100vw-2rem)] z-50 origin-top-right"
                style={{ borderRadius: 28 }}
              >
                {/* iOS liquid-glass stack: blur layer → glow layer → inner-highlight edge → content */}
                <div
                  className="absolute inset-0 backdrop-blur-xl"
                  style={{
                    borderRadius: 28,
                    background: isDark ? 'rgba(15, 23, 42, 0.62)' : 'rgba(255, 255, 255, 0.55)',
                  }}
                />
                <div
                  className="absolute inset-0 pointer-events-none"
                  style={{
                    borderRadius: 28,
                    boxShadow: isDark
                      ? '0 12px 32px rgba(0,0,0,0.45), 0 0 24px rgba(0,0,0,0.25), 0 0 32px rgba(255,255,255,0.04)'
                      : '0 12px 32px rgba(15,23,42,0.16), 0 0 24px rgba(15,23,42,0.06), 0 0 32px rgba(255,255,255,0.25)',
                  }}
                />
                <div
                  className="absolute inset-0 pointer-events-none"
                  style={{
                    borderRadius: 28,
                    border: isDark ? '1px solid rgba(255,255,255,0.12)' : '1px solid rgba(255,255,255,0.65)',
                    boxShadow: isDark
                      ? 'inset 1.5px 1.5px 1.5px rgba(255,255,255,0.10), inset -1.5px -1.5px 1.5px rgba(255,255,255,0.05)'
                      : 'inset 2px 2px 2px rgba(255,255,255,0.55), inset -2px -2px 2px rgba(255,255,255,0.35)',
                  }}
                />

                <div className="relative z-10 overflow-hidden" style={{ borderRadius: 28 }}>
                  {/* Header */}
                  <div className={`px-5 pt-4 pb-3 flex items-center justify-between border-b
                    ${isDark ? 'border-white/10' : 'border-white/60'}`}>
                    <div className="flex items-center gap-2">
                      <h3 className={`font-semibold text-[15px] ${isDark ? 'text-white' : 'text-slate-800'}`}>
                        Notifications
                      </h3>
                      {unreadCount > 0 && (
                        <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold
                          ${isDark ? 'bg-white/15 text-white' : 'bg-slate-800/10 text-slate-700'}`}>
                          {unreadCount} new
                        </span>
                      )}
                    </div>
                    {unreadCount > 0 && (
                      <button
                        onClick={markAllRead}
                        className="text-xs font-medium text-[var(--accent-primary)] hover:underline"
                      >
                        Mark all read
                      </button>
                    )}
                  </div>

                  {/* List */}
                  <div className="max-h-[26rem] overflow-y-auto">
                    {notifications.length === 0 ? (
                      <div className={`px-5 py-10 text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        <Bell className="w-6 h-6 mx-auto mb-2 opacity-40" strokeWidth={1.5} />
                        <p className="text-sm">You're all caught up</p>
                      </div>
                    ) : notifications.map((notif) => {
                      const meta =
                        notif.type === 'urgent' ? { Icon: ShieldAlert, chip: 'bg-rose-500/15 text-rose-500' } :
                        notif.type === 'alert' ? { Icon: AlertTriangle, chip: 'bg-amber-500/15 text-amber-500' } :
                        notif.type === 'success' ? { Icon: CheckCircle2, chip: 'bg-emerald-500/15 text-emerald-500' } :
                        { Icon: Bell, chip: 'bg-blue-500/15 text-blue-500' };
                      return (
                        <button
                          key={notif.id}
                          onClick={() => openNotification(notif)}
                          className={`w-full text-left px-4 py-3 flex gap-3 transition-colors group border-b last:border-b-0
                            ${isDark ? 'border-white/5 hover:bg-white/10' : 'border-white/50 hover:bg-white/55'}
                            ${!notif.read ? (isDark ? 'bg-white/[0.07]' : 'bg-white/40') : ''}`}
                        >
                          <span className={`w-9 h-9 rounded-2xl flex items-center justify-center flex-shrink-0 mt-0.5 ${meta.chip}`}>
                            <meta.Icon className="w-[18px] h-[18px]" strokeWidth={1.75} />
                          </span>
                          <span className="flex-1 min-w-0">
                            <span className="flex items-baseline justify-between gap-2">
                              <span className={`text-sm font-semibold truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                {notif.title}
                              </span>
                              <span className={`text-[10px] flex-shrink-0 tabular-nums ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                                {notif.time}
                              </span>
                            </span>
                            <span className={`block text-xs mt-0.5 line-clamp-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                              {notif.message}
                            </span>
                            {notif.cta && (
                              <span className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-[var(--accent-primary)] opacity-80 group-hover:opacity-100">
                                {notif.cta}
                                <ArrowUpRight className="w-3 h-3" strokeWidth={2} />
                              </span>
                            )}
                          </span>
                          {!notif.read && (
                            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)] flex-shrink-0 mt-2" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Asymmetric 2-Column Responsive Dashboard Layout */}
      <div className="flex flex-col lg:flex-row gap-6 items-start w-full">
        {/* LEFT COLUMN: Main Queue Workspace & Live Sync Pulse Alerts (55% width) */}
        <div className="w-full lg:w-[55%] space-y-6">

          {/* Patient Schedule Card */}
          <GlassCard className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
            {/* Header & Advanced Interactive Filter Panel */}
            <div className={`px-5 py-4 border-b ${isDark ? 'border-white/10' : 'border-slate-100'} space-y-4`}>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <button
                  onClick={() => setIsScheduleExpanded(!isScheduleExpanded)}
                  aria-label="Toggle Schedule"
                  className={`text-base font-semibold flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'} hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-lg`}
                >
                  Today's patients
                  <ChevronDown aria-hidden="true" className={`w-4 h-4 transition-transform duration-200 ${isScheduleExpanded ? '' : '-rotate-90'}`} strokeWidth={1.5} />
                </button>

                {/* Instant Patient Search input */}
                <div className="relative w-full sm:w-64">
                  <input
                    type="text"
                    placeholder="Search patients..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className={`w-full pl-3 pr-8 py-1.5 rounded-lg text-xs border transition-all duration-200 outline-none
                      ${isDark
                        ? 'bg-slate-900/50 border-white/10 text-white placeholder-slate-500 focus:border-teal-500/50'
                        : 'bg-slate-50 border-slate-200 text-slate-800 placeholder-slate-400 focus:border-teal-500/50'
                      }`}
                  />
                  {searchTerm && (
                    <button
                      onClick={() => setSearchTerm('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-sm font-semibold"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>

              {/* Status Tab Pills with Counters */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                {[
                  { id: 'all', label: 'All patients' },
                  { id: 'waiting', label: 'Scheduled' },
                  { id: 'in-progress', label: 'In Queue' },
                  { id: 'done', label: 'Completed' }
                ].map((tab) => {
                  const isActive = statusFilter === tab.id;
                  const count = counts[tab.id];
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setStatusFilter(tab.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 flex items-center gap-1.5 border
                        ${isActive
                          ? (isDark
                            ? 'bg-teal-500/20 text-teal-400 border-teal-500/40 shadow-sm'
                            : 'bg-teal-50 text-teal-700 border-teal-200 shadow-sm'
                          )
                          : (isDark
                            ? 'bg-transparent border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5'
                            : 'bg-transparent border-transparent text-slate-600 hover:text-slate-800 hover:bg-slate-100'
                          )
                        }`}
                    >
                      {tab.label}
                      <span className={`px-1.5 py-0.5 rounded-full text-[10px] leading-none font-bold
                        ${isActive
                          ? (isDark ? 'bg-teal-400/20 text-teal-300' : 'bg-teal-200/50 text-teal-800')
                          : (isDark ? 'bg-slate-800 text-slate-500' : 'bg-slate-200/50 text-slate-500')
                        }`}
                      >
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Patient Queue List */}
            {isScheduleExpanded && (
              <div className="divide-y divide-slate-100 dark:divide-white/5">
                {filteredSchedule.length === 0 ? (
                  <div className={`text-center py-12 px-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    No patients match your search or filter criteria
                  </div>
                ) : filteredSchedule.map((appointment) => {
                  const isPatientEmergency = isEmergency(appointment.patient.nsn);
                  const isPatientHighRisk = isHighRisk(appointment.patient.nsn);

                  return (
                    <div
                      key={appointment.id}
                      className={`p-5 transition-all duration-300 hover-lift relative border-l-4
                        ${appointment.status === 'in-progress' || appointment.status === 'waiting'
                          ? 'border-l-teal-500 bg-teal-500/5 dark:bg-teal-500/2'
                          : isPatientEmergency
                            ? 'border-l-rose-500 bg-rose-500/5 dark:bg-rose-500/2'
                            : isPatientHighRisk
                              ? 'border-l-amber-500'
                              : 'border-l-transparent'
                        }
                        ${isDark ? 'hover:bg-white/5' : 'hover:bg-slate-50'}
                      `}
                    >
                      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                        {/* Left Info Column */}
                        <div className="flex items-start gap-4 flex-1 min-w-0">
                          {/* Slot Time with live status light */}
                          <div className="flex flex-col items-start min-w-[72px] flex-shrink-0 pt-1">
                            <span className={`text-base font-semibold ds-numeric leading-none ${isDark ? 'text-white' : 'text-slate-800'}`}>
                              {appointment.time}
                            </span>
                            <div className="mt-2.5 flex items-center gap-1.5">
                              {getStatusBadge(appointment.status)}
                            </div>
                          </div>

                          {/* Patient main data block */}
                          <div className="flex-1 min-w-0 flex items-start gap-3">
                            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0 shadow-sm mt-0.5 ${getPatientAvatarColor(appointment.patient.gender)}`}>
                              {getInitials(appointment.patient.name)}
                            </div>

                            <div className="flex-1 min-w-0 max-w-xl w-full">
                              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2.5 w-full">
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <h3 className={`font-semibold text-sm truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                      {appointment.patient.name}
                                    </h3>
                                    {isPatientEmergency && (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-rose-500/10 text-rose-500 border border-rose-500/20">
                                        CRITICAL
                                      </span>
                                    )}
                                    {isPatientHighRisk && (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-500 border border-amber-500/20">
                                        HIGH RISK
                                      </span>
                                    )}
                                  </div>
                                  <p className={`text-xs ds-numeric mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                    {appointment.patient.age} y/o · {appointment.patient.gender} · ID: {appointment.patient.nsn}
                                  </p>
                                </div>

                                <div className="flex-shrink-0">
                                  {(appointment.status === 'waiting' || appointment.status === 'in-progress') && (
                                    <Button
                                      variant="primary"
                                      size="sm"
                                      icon={Play}
                                      onClick={() => handleStartConsultClick(appointment)}
                                      className="min-w-[128px] justify-center"
                                    >
                                      Start consult
                                    </Button>
                                  )}
                                  {appointment.status === 'done' && (
                                    <span className={`px-4 py-1.5 rounded-lg text-xs text-center font-medium min-w-[128px] inline-block border
                                      ${isDark
                                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                        : 'bg-emerald-50 text-emerald-600 border-emerald-100'}`}
                                    >
                                      Completed
                                    </span>
                                  )}
                                </div>
                              </div>

                              {/* Stylized Complaint box - perfectly aligned to matching container width */}
                              <div className={`px-3 py-2.5 rounded-lg border w-full ${isDark ? 'bg-slate-900/40 border-white/5' : 'bg-slate-50/80 border-slate-100'}`}>
                                <p className={`text-[10px] font-semibold tracking-wide uppercase ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Chief complaint</p>
                                <p className={`text-sm font-medium mt-0.5 ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                  {appointment.triage.chiefComplaint}
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </GlassCard>

        </div>

        {/* RIGHT COLUMN: Sidebar Control Cockpit (45% width) - Dedicated to Assistant Impact stats */}
        <div className="w-full lg:w-[45%] space-y-6">
          {/* Follow-Up Patients (moved from left column) */}
          <GlassCard className="p-5" variant={isDark ? 'dark' : 'light'}>
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b pb-3 border-slate-100 dark:border-white/5">
                <button
                  onClick={() => setIsFollowUpsExpanded(!isFollowUpsExpanded)}
                  aria-label="Toggle Follow-Ups"
                  className="flex items-center gap-2 hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-lg text-left"
                >
                  <h3 className={`text-sm font-semibold flex items-center gap-1.5 ${isDark ? 'text-white' : 'text-slate-800'}`}>
                    Follow-Up Patients
                    <ChevronDown aria-hidden="true" className={`w-3.5 h-3.5 transition-transform duration-200 ${isFollowUpsExpanded ? '' : '-rotate-90'}`} strokeWidth={1.8} />
                  </h3>
                </button>

                {/* Compact Search Input for Follow-up Patients */}
                <div className="relative w-32 sm:w-40 flex-shrink-0">
                  <input
                    type="text"
                    placeholder="Search patients..."
                    value={followUpSearchTerm}
                    onChange={(e) => setFollowUpSearchTerm(e.target.value)}
                    className={`w-full pl-2.5 pr-7 py-1 rounded-lg text-sm border transition-all duration-200 outline-none
                      ${isDark
                        ? 'bg-slate-900/50 border-white/10 text-white placeholder-slate-500 focus:border-teal-500/50'
                        : 'bg-slate-50 border-slate-200 text-slate-800 placeholder-slate-400 focus:border-teal-500/50'
                      }`}
                  />
                  {followUpSearchTerm && (
                    <button
                      onClick={() => setFollowUpSearchTerm('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-sm font-semibold"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>

              {isFollowUpsExpanded && (
                <>
                  {loadingFollowUps ? (
                    <div className="text-center py-8 text-sm text-slate-400 dark:text-slate-500 flex items-center justify-center gap-2">
                      <span className="animate-spin border-2 border-t-teal-500 rounded-full w-4 h-4 border-slate-200 dark:border-slate-800"></span>
                      Syncing follow-ups...
                    </div>
                  ) : filteredFollowUps.length === 0 ? (
                    <div className={`text-center py-8 text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      {followUpSearchTerm ? 'No matching follow-up patients' : 'No upcoming patient follow-ups'}
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {filteredFollowUps.map((item) => {
                        const formattedReviewDate = new Date(item.nextReview).toLocaleDateString('en-GB', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric'
                        });

                        const isOverdue = item.tcaDays < 0;
                        const isClose = item.tcaDays >= 0 && item.tcaDays <= 3;

                        return (
                          <button
                            type="button"
                            key={item.id || item.nsn}
                            onClick={() => handleFollowUpPatientClick(item)}
                            className={`p-3.5 rounded-xl border flex items-center justify-between gap-4 transition-all duration-200 hover-lift
                              ${isDark
                                ? 'bg-slate-900/30 border-white/5 hover:border-teal-500/20'
                                : 'bg-slate-50/50 border-slate-100 hover:border-teal-500/20'
                              } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/40 text-left w-full`}
                          >
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2.5">
                                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0 shadow-sm ${getPatientAvatarColor(item.gender)}`}>
                                  {getInitials(item.name)}
                                </div>
                                <div className="min-w-0">
                                  <h4 className={`font-semibold text-sm truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                    {item.name}
                                  </h4>
                                  <p className="text-sm text-slate-400 dark:text-slate-500 ds-numeric">
                                    {item.age} y/o · {item.gender}
                                  </p>
                                </div>
                              </div>
                            </div>

                            <div className="text-right flex-shrink-0 flex flex-col items-end gap-1.5">
                              <span className={`text-sm font-bold ds-numeric leading-none ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                {formattedReviewDate}
                              </span>
                              {isOverdue ? (
                                <span className="inline-flex px-2 py-0.5 rounded text-sm font-bold uppercase bg-rose-500/10 text-rose-500 border border-rose-500/20">
                                  Overdue {Math.abs(item.tcaDays)}d
                                </span>
                              ) : isClose ? (
                                <span className="inline-flex px-2 py-0.5 rounded text-sm font-bold uppercase bg-amber-500/10 text-amber-500 border border-amber-500/20">
                                  In {item.tcaDays}d
                                </span>
                              ) : (
                                <span className="inline-flex px-2 py-0.5 rounded text-sm font-bold uppercase bg-teal-500/10 text-teal-500 border border-teal-500/20">
                                  TCA {item.tcaDays}d
                                </span>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </div>
          </GlassCard>

          {/* AI Assistant Impact Stats (2x2 Stats Dashboard Grid) */}
          <div>
            <div className="mb-3">
              <h2 className={`text-base font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                Assistant Impact <span className={accent.text}>Today</span>
              </h2>
            </div>
            <GlassCard className={`p-4 border-l-4 ${isDark ? 'border-l-teal-400/60' : 'border-l-teal-500'}`} variant={isDark ? 'dark' : 'light'}>
              <div className="grid grid-cols-2 gap-3.5">
                {/* Time Reclaimed */}
                <div className={`p-3.5 rounded-xl border
                  ${isDark ? 'bg-slate-900/40 border-white/5' : 'bg-slate-50/50 border-slate-100'}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className={`p-1 rounded-md shrink-0 ${isDark ? 'bg-teal-500/15' : 'bg-teal-50'}`}>
                        <Timer className={`w-3 h-3 ${isDark ? 'text-teal-400' : 'text-teal-600'}`} strokeWidth={2} />
                      </span>
                      <span className={`text-[10px] font-semibold uppercase tracking-wider truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Time Saved</span>
                    </div>
                    <TrendBadge current={impact.timeSavedMin} previous={impact.yesterday.timeSavedMin} suffix="m" />
                  </div>
                  <p className={`text-3xl font-bold leading-none ds-numeric ${isDark ? 'text-teal-400' : 'text-teal-600'}`}>
                    {impact.timeSavedMin}<span className="text-base font-semibold ml-0.5">min</span>
                  </p>
                  <p className={`text-[11px] mt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>vs 10.5 min avg Malaysian consultation</p>
                </div>

                {/* CPG Aligned with circular SVG progress ring */}
                <div className={`p-3.5 rounded-xl border
                  ${isDark ? 'bg-slate-900/40 border-white/5' : 'bg-slate-50/50 border-slate-100'}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className={`p-1 rounded-md shrink-0 ${isDark ? 'bg-violet-500/15' : 'bg-violet-50'}`}>
                        <FileCheck className={`w-3 h-3 ${isDark ? 'text-violet-400' : 'text-violet-600'}`} strokeWidth={2} />
                      </span>
                      <span className={`text-[10px] font-semibold uppercase tracking-wider truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>CPG Align</span>
                    </div>
                    <TrendBadge current={cpgPct} previous={impact.yesterday.cpgAlignedPct} suffix="pp" />
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <p className={`text-3xl font-bold leading-none ds-numeric ${isDark ? 'text-violet-400' : 'text-violet-600'}`}>
                      {cpgPct}<span className="text-base font-semibold ml-0.5">%</span>
                    </p>
                    <div className="relative w-10 h-10 flex-shrink-0">
                      <svg viewBox="0 0 40 40" className="w-full h-full transform -rotate-90">
                        <circle cx="20" cy="20" r="16" className="stroke-slate-200 dark:stroke-slate-800" strokeWidth="3.5" fill="transparent" />
                        <circle
                          cx="20"
                          cy="20"
                          r="16"
                          className={isDark ? "stroke-violet-400" : "stroke-violet-500"}
                          strokeWidth="3.5"
                          strokeLinecap="round"
                          fill="transparent"
                          strokeDasharray={2 * Math.PI * 16}
                          strokeDashoffset={2 * Math.PI * 16 * (1 - cpgPct / 100)}
                        />
                      </svg>
                    </div>
                  </div>
                  <p className={`text-[11px] mt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    {impact.cpgAligned.count} of {impact.completed} completed plan{impact.completed !== 1 ? 's' : ''}
                    {impact.started > impact.completed ? ` · ${impact.started - impact.completed} incomplete excluded` : ''}
                  </p>
                </div>

                {/* Citations Issued */}
                <div className={`p-3.5 rounded-xl border
                  ${isDark ? 'bg-slate-900/40 border-white/5' : 'bg-slate-50/50 border-slate-100'}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className={`p-1 rounded-md shrink-0 ${isDark ? 'bg-sky-500/15' : 'bg-sky-50'}`}>
                        <BookOpen className={`w-3 h-3 ${isDark ? 'text-sky-400' : 'text-sky-600'}`} strokeWidth={2} />
                      </span>
                      <span className={`text-[10px] font-semibold uppercase tracking-wider truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Citations</span>
                    </div>
                    <TrendBadge current={impact.citations} previous={impact.yesterday.citations} />
                  </div>
                  <p className={`text-3xl font-bold leading-none ds-numeric ${isDark ? 'text-sky-400' : 'text-sky-600'}`}>
                    {impact.citations}
                  </p>
                  <p className={`text-[11px] mt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>guideline passages cited in plans</p>
                </div>

                {/* Safety intercepts — Stage 6 critical/major risks caught pre-sign-off */}
                <div className={`p-3.5 rounded-xl border
                  ${isDark ? 'bg-slate-900/40 border-white/5' : 'bg-slate-50/50 border-slate-100'}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className={`p-1 rounded-md shrink-0 ${isDark ? 'bg-rose-500/15' : 'bg-rose-50'}`}>
                        <ShieldAlert className={`w-3 h-3 ${isDark ? 'text-rose-400' : 'text-rose-500'}`} strokeWidth={2} />
                      </span>
                      <span className={`text-[10px] font-semibold uppercase tracking-wider truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Safety Intercepts</span>
                    </div>
                    <TrendBadge current={impact.intercepts} previous={impact.yesterday.intercepts} />
                  </div>
                  <p className={`text-3xl font-bold leading-none ds-numeric ${isDark ? 'text-rose-400' : 'text-rose-500'}`}>
                    {impact.intercepts}
                  </p>
                  <p className={`text-[11px] mt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>critical/major risks flagged before sign-off</p>
                </div>
              </div>
            </GlassCard>
          </div>
        </div>
      </div>

      {/* Patient Quick View Dialog Modal */}
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
