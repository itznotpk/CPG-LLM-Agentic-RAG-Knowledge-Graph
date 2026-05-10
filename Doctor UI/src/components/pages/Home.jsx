import React, { useState, useEffect, useMemo } from 'react';
import {
  Calendar,
  Clock,
  Users,
  AlertTriangle,
  Play,
  Activity,
  ChevronRight,
  ChevronDown,
  Bell,
  Eye
} from 'lucide-react';
import { todaySchedule, dashboardStats } from '../../data/scheduleData';
import { GlassCard } from '../shared/GlassCard';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../shared/Notification';
import PatientQuickView from '../shared/PatientQuickView';

// Sample notifications data
const sampleNotifications = [
  { id: 1, type: 'urgent', title: 'Critical Lab Result', message: 'Raj Kumar - HbA1c at 12.5%', time: '5 min ago', read: false },
  { id: 2, type: 'alert', title: 'Appointment Reminder', message: 'Ahmad bin Abdullah scheduled in 30 minutes', time: '10 min ago', read: false },
  { id: 3, type: 'info', title: 'MPIS Sync Complete', message: 'Patient records successfully updated', time: '1 hour ago', read: true },
  { id: 4, type: 'success', title: 'Care Plan Approved', message: 'Siti Nurhaliza care plan approved by specialist', time: '2 hours ago', read: true },
  { id: 5, type: 'alert', title: 'Medication Refill', message: 'Mohammad Faiz prescription expires in 3 days', time: '3 hours ago', read: true },
];

const Home = ({ onStartConsult, onViewChart }) => {
  const { isDark, accent } = useTheme();
  const toast = useToast();
  const [currentTime, setCurrentTime] = useState(new Date());
  const [schedule, setSchedule] = useState(todaySchedule);
  const [stats, setStats] = useState(dashboardStats);
  const [isScheduleExpanded, setIsScheduleExpanded] = useState(true);

  // Avatar color palette for patients
  const avatarColors = [
    'from-cyan-500 to-blue-500',
    'from-emerald-500 to-teal-500',
    'from-purple-500 to-pink-500',
    'from-orange-500 to-amber-500',
    'from-rose-500 to-red-500',
    'from-indigo-500 to-violet-500',
    'from-lime-500 to-green-500',
    'from-fuchsia-500 to-purple-500',
  ];

  // Get initials from name
  const getInitials = (name) => {
    if (!name) return 'P';
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  // Get consistent color based on name
  const getAvatarColor = (name) => {
    if (!name) return avatarColors[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return avatarColors[Math.abs(hash) % avatarColors.length];
  };

  // Category filter state for stats
  const [categoryFilter, setCategoryFilter] = useState('all'); // all, waiting, emergency, highRisk

  // Patient quick view modal state
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [selectedTriage, setSelectedTriage] = useState(null);
  const [isQuickViewOpen, setIsQuickViewOpen] = useState(false);

  // Notifications state
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState(sampleNotifications);
  const unreadCount = notifications.filter(n => !n.read).length;

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  const getGreeting = () => {
    return 'Welcome';
  };

  const formatDate = () => {
    return currentTime.toLocaleDateString('en-MY', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const formatTime = () => {
    return currentTime.toLocaleTimeString('en-MY', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (status) => {
    const styles = {
      waiting: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      'in-progress': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      done: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
    };
    const labels = {
      waiting: 'Waiting',
      'in-progress': 'In Progress',
      done: 'Done'
    };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${styles[status]}`}>
        {labels[status]}
      </span>
    );
  };

  const getBPColor = (status) => {
    const colors = {
      normal: 'text-emerald-500',
      high: 'text-amber-500',
      critical: 'text-red-600 font-bold'
    };
    return colors[status] || (isDark ? 'text-white' : 'text-slate-800');
  };

  // Filter the schedule
  const filteredSchedule = useMemo(() => {
    let filtered = [...schedule];

    // Apply category filter from stat cards
    if (categoryFilter === 'waiting') {
      filtered = filtered.filter(apt => apt.status === 'waiting');
    } else if (categoryFilter === 'emergency') {
      filtered = filtered.filter(apt => apt.isEmergency);
    } else if (categoryFilter === 'highRisk') {
      filtered = filtered.filter(apt => apt.isHighRisk && !apt.isEmergency);
    }

    // Sort by time
    filtered.sort((a, b) => {
      const timeA = a.time.replace(':', '');
      const timeB = b.time.replace(':', '');
      return parseInt(timeA) - parseInt(timeB);
    });

    return filtered;
  }, [schedule, categoryFilter]);

  const handleStartConsultClick = (appointment) => {
    // Update status to in-progress
    setSchedule(prev => prev.map(apt =>
      apt.id === appointment.id ? { ...apt, status: 'in-progress' } : apt
    ));
    toast.success(`Started consultation for ${appointment.patient.name}`);
    // Navigate to consultation with patient data
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

  const handleExportPDF = () => {
    toast.success('Patient summary exported as PDF');
  };

  const handleExportCSV = () => {
    toast.success('Patient data exported as CSV');
  };



  return (
    <div className="space-y-6">
      {/* Header - Greeting & Date */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>
            {getGreeting()}, <span className={accent.text}>Dr. Tay</span>
          </h1>
          <div className={`flex items-center gap-4 mt-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
            <span className="flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              {formatDate()}
            </span>
            <span className="flex items-center gap-2">
              <Clock className="w-4 h-4" />
              {formatTime()}
            </span>
          </div>
        </div>

        {/* Notifications Button */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            aria-label="Notifications"
            className={`p-3 rounded-xl transition-colors relative focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none
              ${isDark ? 'bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white focus-visible:ring-white/50'
                : 'bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-600 hover:text-slate-800 focus-visible:ring-slate-400'}`}
          >
            <Bell aria-hidden="true" className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {showNotifications && (
            <div className={`absolute right-0 top-full mt-2 w-80 rounded-xl shadow-2xl z-50 overflow-hidden
              ${isDark ? 'bg-slate-800 border border-white/10' : 'bg-white border border-slate-200'}`}
            >
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
                        <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>
                          {notif.title}
                        </p>
                        <p className={`text-xs mt-0.5 truncate ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                          {notif.message}
                        </p>
                        <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                          {notif.time}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Daily Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <GlassCard
          className={`p-4 cursor-pointer transition-transform ${categoryFilter === 'all' ? 'ring-2 ring-blue-500' : 'hover:scale-[1.02]'} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400`}
          variant={isDark ? 'dark' : 'light'}
          onClick={() => setCategoryFilter('all')}
          tabIndex={0}
          role="button"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setCategoryFilter('all'); }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Total Appointments</p>
              <p className={`text-3xl font-bold mt-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>{stats.totalAppointments}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
              <Calendar aria-hidden="true" className="w-6 h-6 text-blue-400" />
            </div>
          </div>
        </GlassCard>

        <GlassCard
          className={`p-4 cursor-pointer transition-transform ${categoryFilter === 'waiting' ? 'ring-2 ring-amber-500' : 'hover:scale-[1.02]'} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400`}
          variant={isDark ? 'dark' : 'light'}
          onClick={() => setCategoryFilter(categoryFilter === 'waiting' ? 'all' : 'waiting')}
          tabIndex={0}
          role="button"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setCategoryFilter(categoryFilter === 'waiting' ? 'all' : 'waiting'); }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Patients Waiting</p>
              <p className="text-3xl font-bold text-amber-500 mt-1">{stats.patientsWaiting}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center">
              <Users aria-hidden="true" className="w-6 h-6 text-amber-500" />
            </div>
          </div>
        </GlassCard>

        <GlassCard
          className={`p-4 cursor-pointer transition-transform ${categoryFilter === 'emergency' ? 'ring-2 ring-red-500' : 'hover:scale-[1.02]'} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400`}
          variant={isDark ? 'dark' : 'light'}
          onClick={() => setCategoryFilter(categoryFilter === 'emergency' ? 'all' : 'emergency')}
          tabIndex={0}
          role="button"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setCategoryFilter(categoryFilter === 'emergency' ? 'all' : 'emergency'); }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Emergency Cases</p>
              <p className="text-3xl font-bold text-red-500 mt-1">{stats.emergencyCases}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-red-500/20 flex items-center justify-center">
              <AlertTriangle aria-hidden="true" className="w-6 h-6 text-red-500" />
            </div>
          </div>
        </GlassCard>

        <GlassCard
          className={`p-4 cursor-pointer transition-transform ${categoryFilter === 'highRisk' ? 'ring-2 ring-orange-500' : 'hover:scale-[1.02]'} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400`}
          variant={isDark ? 'dark' : 'light'}
          onClick={() => setCategoryFilter(categoryFilter === 'highRisk' ? 'all' : 'highRisk')}
          tabIndex={0}
          role="button"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setCategoryFilter(categoryFilter === 'highRisk' ? 'all' : 'highRisk'); }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>High Risk</p>
              <p className="text-3xl font-bold text-orange-500 mt-1">{stats.highRiskCases}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-orange-500/20 flex items-center justify-center">
              <Activity aria-hidden="true" className="w-6 h-6 text-orange-500" />
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Main Content */}
      <div>
        {/* Schedule Timeline */}
        <GlassCard className="p-6" variant={isDark ? 'dark' : 'light'}>
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setIsScheduleExpanded(!isScheduleExpanded)}
              aria-label="Toggle Schedule"
              className={`text-xl font-semibold flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'} hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-lg px-2 py-1 -ml-2`}
            >
              <Clock aria-hidden="true" className={`w-5 h-5 ${accent.text}`} />
              Today's Schedule
              <ChevronDown aria-hidden="true" className={`w-5 h-5 transition-transform duration-200 ${isScheduleExpanded ? '' : '-rotate-90'}`} />
            </button>
          </div>

          {isScheduleExpanded && <div className="space-y-4">
            {filteredSchedule.length === 0 ? (
              <div className={`text-center py-8 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                No appointments match the current filter
              </div>
            ) : filteredSchedule.map((appointment, index) => (
              <div
                key={appointment.id}
                className={`p-4 rounded-xl border transition-colors
                  ${appointment.isEmergency
                    ? 'bg-red-500/10 border-red-500/30 hover:bg-red-500/15'
                    : appointment.isHighRisk
                      ? 'bg-orange-500/10 border-orange-500/30 hover:bg-orange-500/15'
                      : isDark
                        ? 'bg-white/5 border-white/10 hover:bg-white/10'
                        : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                  }`}
              >
                <div className="flex items-start gap-4">
                  {/* Time Column */}
                  <div className="flex flex-col items-center min-w-[80px]">
                    <span className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{appointment.time}</span>
                    {appointment.isEmergency && (
                      <span className="mt-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-500 text-white">
                        URGENT
                      </span>
                    )}
                    {!appointment.isEmergency && appointment.isHighRisk && (
                      <span className="mt-1 px-2 py-0.5 rounded-full text-xs font-bold bg-orange-500 text-white">
                        HIGH RISK
                      </span>
                    )}
                  </div>

                  {/* Patient Info */}
                  <div className="flex-1 min-w-0">
                    {/* Name row with avatar */}
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-br ${getAvatarColor(appointment.patient.name)} text-white font-bold text-sm flex-shrink-0`}>
                        {getInitials(appointment.patient.name)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className={`font-medium truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>{appointment.patient.name}</h3>
                          {getStatusBadge(appointment.status)}
                        </div>
                        <p className={`text-sm truncate ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                          {appointment.patient.age} y/o • {appointment.patient.gender} • {appointment.patient.nsn}
                        </p>
                      </div>
                    </div>
                    {/* Chief Complaint - Below name row */}
                    <div className={`ml-13 px-3 py-2 rounded-lg ${isDark ? 'bg-black/20' : 'bg-slate-100'}`} style={{ marginLeft: '52px' }}>
                      <p className={`text-xs uppercase mb-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Chief Complaint</p>
                      <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{appointment.triage.chiefComplaint}</p>
                    </div>
                  </div>

                  {/* Action Buttons - Right side */}
                  <div className="flex flex-col gap-2 ml-4 flex-shrink-0">
                    {/* Quick View Button */}
                    <button
                      onClick={() => handleQuickView(appointment)}
                      className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors min-w-[130px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400
                          ${isDark
                          ? 'bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white border border-white/10'
                          : 'bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-800 border border-slate-200'}`}
                    >
                      <Eye aria-hidden="true" className="w-4 h-4" />
                      Quick View
                    </button>
                    {appointment.status === 'waiting' && (
                      <button
                        onClick={() => handleStartConsultClick(appointment)}
                        className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium min-w-[130px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]
                            bg-gradient-to-r ${accent.gradient} text-white
                            hover:${accent.gradientHover} shadow-lg ${accent.shadow}`}
                      >
                        <Play aria-hidden="true" className="w-4 h-4" />
                        Start Consult
                      </button>
                    )}
                    {appointment.status === 'in-progress' && (
                      <button
                        onClick={() => handleStartConsultClick(appointment)}
                        className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium min-w-[130px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400
                            bg-blue-500/20 border border-blue-500/30 text-blue-500
                            hover:bg-blue-500/30`}
                      >
                        Continue
                        <ChevronRight aria-hidden="true" className="w-4 h-4" />
                      </button>
                    )}
                    {appointment.status === 'done' && (
                      <span className="px-4 py-2.5 rounded-lg text-sm text-emerald-500 bg-emerald-500/10 font-medium text-center min-w-[130px]">
                        ✓ Completed
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>}
        </GlassCard>
      </div>

      {/* Patient Quick View Modal */}
      < PatientQuickView
        patient={selectedPatient}
        triage={selectedTriage}
        isOpen={isQuickViewOpen}
        onClose={handleCloseQuickView}
        onExportPDF={handleExportPDF}
        onExportCSV={handleExportCSV}
        onViewChart={onViewChart}
      />
    </div >
  );
};

export default Home;
