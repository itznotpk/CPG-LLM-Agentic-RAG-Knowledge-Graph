import React, { useState, useEffect } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useParams,
} from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Login from './pages/Login';
import Landing from './pages/Landing';
import { AuthProvider, useAuth } from './context/AuthContext';
import { resolveRoute } from './lib/routeGuard';
import { AppProvider, useApp } from './context/AppContext';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { ToastProvider } from './components/shared/Notification';
import SplashScreen from './components/shared/SplashScreen';
import Sidebar from './components/layout/Sidebar';
import {
  DataInputSection,
  DiagnosisSection,
  CarePlanSection,
  OutputSection,
  DashboardSection,
} from './components/sections';
import FeedbackInsightsSection from './components/sections/FeedbackInsightsSection';
import { StepIndicator, PatientBanner, CommandPalette } from './components/shared';
import Home from './components/pages/Home';
import { useIdleLogout } from './hooks/useIdleLogout';
import MyPatients from './components/pages/MyPatients';
import Settings, { getDefaultAnalyticsDays } from './components/pages/Settings';
import PatientChart from './components/pages/PatientChart';
import CarePlanChat from './components/sections/CarePlanChat';

const steps = [
  { id: 1, label: 'Data input' },
  { id: 2, label: 'Diagnosis' },
  { id: 3, label: 'Care plan' },
  { id: 4, label: 'Complete' },
];

// APP_VIEWS now lives in lib/routeGuard.js alongside the gate logic.

// Analytics ("Clinical Performance") view — owns the shared time window so the
// dashboard and the feedback-insights panel stay in sync from one control.
// Two swappable categories behind a segmented control.
const ANALYTICS_TABS = [
  { id: 'performance', label: 'Clinical Performance' },
  { id: 'feedback', label: 'Feedback & System Health' },
];

function AnalyticsView() {
  const { isDark } = useTheme();
  // Initial window comes from Settings → System → Default Performance Window.
  const [days, setDays] = useState(getDefaultAnalyticsDays);
  const [tab, setTab] = useState('performance');
  const windows = [7, 30, 90];
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className={`inline-flex items-center gap-1 p-1 rounded-xl border
          ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
          {ANALYTICS_TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors
                ${tab === t.id
                  ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]'
                  : isDark ? 'text-slate-400 hover:bg-white/5' : 'text-slate-500 hover:bg-white'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`text-xs mr-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Window</span>
          {windows.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border
                ${days === d
                  ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)] border-[var(--accent-primary)]/25'
                  : isDark ? 'text-slate-400 hover:bg-white/5 border-transparent' : 'text-slate-500 hover:bg-slate-50 border-transparent'}`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>
      {/* Both panels stay mounted (CSS-hidden) so switching is instant — no
          refetch/loading flash — and realtime subs keep the hidden one fresh. */}
      <div className={tab === 'performance' ? '' : 'hidden'}>
        <DashboardSection days={days} />
      </div>
      <div className={tab === 'feedback' ? '' : 'hidden'}>
        <FeedbackInsightsSection days={days} />
      </div>
    </div>
  );
}

function AppContent({ view }) {
  const { state, dispatch, goToStep } = useApp();
  const { isDark } = useTheme();
  const { profile: authProfile, signOut, refreshProfile } = useAuth();
  // Auto-logout after the inactivity window configured in Settings → System.
  useIdleLogout(signOut);
  const { currentStep } = state;
  const navigate = useNavigate();
  // 'chart' is a transient sub-view layered over the routed views.
  const [chartPatient, setChartPatient] = useState(null);
  const [showChart, setShowChart] = useState(false);
  const currentView = showChart ? 'chart' : view;
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

  const profile = authProfile ? {
    name:       authProfile.full_name      || 'Clinician',
    email:      authProfile.email          || '',
    phone:      authProfile.phone          || '',
    specialty:  authProfile.specialty      || '',
    license:    authProfile.license_number || '',
    facility:   authProfile.facility       || '',
    department: authProfile.department     || '',
    avatarUrl:  authProfile.avatar_url     || null,
    role:       authProfile.role           || 'doctor',
  } : null;

  // A consultation is "active" if work is running or partial results exist.
  // We must NOT reset it when the clinician navigates back to the tab — that
  // would destroy a pipeline still streaming in the background.
  const hasActiveConsult =
    state.isAnalyzing ||
    state.isGeneratingPlan ||
    state.currentStep > 1 ||
    !!state.diagnosis ||
    !!state.carePlan;

  const handleNavigate = (nextView) => {
    // Returning to the consultation tab: keep an in-progress/active consult
    // intact so background work survives. Only reset a stale, idle one so the
    // tab opens fresh when nothing is happening.
    if (nextView === 'consultation' && !hasActiveConsult) {
      dispatch({ type: 'RESET' });
    }
    setShowChart(false);
    navigate(`/${nextView}`);
  };

  const handleStartConsult = (patient, triage) => {
    // Reset to step 1 first (clears previous patient data)
    dispatch({ type: 'RESET' });

    // Then pre-fill patient data
    dispatch({
      type: 'SET_PATIENT',
      payload: {
        name: patient.name,
        age: patient.age,
        gender: patient.gender,
        nsn: patient.nsn,
        dob: '', // Can be calculated from age if needed
        // Add vitalsHistory to patient state for chart trend data
        vitalsHistory: patient.vitalsHistory || []
      }
    });

    // Set vitals from triage if available
    if (triage?.vitals) {
      const [systolic, diastolic] = triage.vitals.bp.split('/');
      dispatch({
        type: 'SET_VITALS',
        payload: {
          bpSystolic: systolic,
          bpDiastolic: diastolic,
          hr: triage.vitals.hr?.toString() || '',
          temp: triage.vitals.temp?.toString() || '',
          spo2: triage.vitals.spo2?.toString() || '',
          rr: triage.vitals.rr?.toString() || '',
          weight: '',
          height: '',
        }
      });
    }

    // Set clinical notes from chief complaint
    if (triage?.chiefComplaint) {
      dispatch({
        type: 'SET_CLINICAL_NOTES',
        payload: `Chief Complaint: ${triage.chiefComplaint}\n\n${triage.notes || ''}`
      });
    }

    // Navigate to consultation
    setShowChart(false);
    navigate('/consultation');
  };

  const handleNewPatient = () => {
    dispatch({ type: 'RESET' });
    setShowChart(false);
    navigate('/consultation');
  };

  const handleViewChart = (patient) => {
    setChartPatient(patient);
    setShowChart(true);
  };

  const renderCurrentSection = () => {
    switch (currentStep) {
      case 1:
        return <DataInputSection onViewChart={handleViewChart} />;
      case 2:
        return <DiagnosisSection />;
      case 3:
        return <CarePlanSection />;
      case 4:
        return <OutputSection />;
      default:
        return <DataInputSection onViewChart={handleViewChart} />;
    }
  };

  const renderMainContent = () => {
    switch (currentView) {
      case 'dashboard':
        return <Home onStartConsult={handleStartConsult} onViewChart={handleViewChart} />;
      case 'patients':
        return <MyPatients onViewChart={handleViewChart} onNewPatient={handleNewPatient} />;
      case 'consultation':
        return (
          <>
            {/* Page header — standardized to match the other tabs (ds-h1) */}
            <div className="mb-6 print:hidden">
              <h1 className={`text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>Consultation</h1>
              <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                AI-assisted clinical workflow, step by step
              </p>
            </div>

            {/* Persistent Patient Banner */}
            <div className="print:hidden">
              <PatientBanner />
            </div>

            {/* Step Indicator */}
            <div className="mb-6 print:hidden">
              <StepIndicator
                steps={steps}
                currentStep={currentStep}
                isProcessing={state.isAnalyzing || state.isGeneratingPlan}
              />
            </div>

            {/* Main Content Area */}
            <div className="min-h-[600px]">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentStep}
                  initial={{ opacity: 0, x: 24 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -24, transition: { duration: 0.15 } }}
                  transition={{ duration: 0.25, ease: 'easeOut' }}
                >
                  {renderCurrentSection()}
                </motion.div>
              </AnimatePresence>
            </div>
          </>
        );
      case 'settings':
        return <Settings profile={profile} setProfile={refreshProfile} />;
      case 'analytics':
        return <AnalyticsView />;
      case 'chart':
        return <PatientChart patient={chartPatient} onBack={() => setShowChart(false)} />;
      default:
        return <Home onStartConsult={handleStartConsult} onViewChart={handleViewChart} />;
    }
  };

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark
      ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900'
      : 'bg-gradient-to-br from-slate-100 via-white to-slate-100'
      }`}>
      {/* Cmd/Ctrl+K command palette (self-contained; owns its own open state) */}
      <CommandPalette onNavigate={handleNavigate} onGoToStep={goToStep} />

      {/* Sidebar */}
      <Sidebar
        currentView={currentView}
        onNavigate={handleNavigate}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        profile={profile}
        consultProcessing={state.isAnalyzing || state.isGeneratingPlan}
      />

      {/* Main Content Area */}
      <motion.main
        animate={{ marginLeft: sidebarCollapsed ? 80 : 256 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="min-h-screen"
      >
        <div className="p-6 lg:p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentView}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10, transition: { duration: 0.15 } }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
            >
              {renderMainContent()}
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.main>

      {/* Care-plan chatbox — always visible; panel explains when no plan is loaded yet */}
      <CarePlanChat
        consultationId={state.consultationId ?? null}
        recommendations={state.carePlan?.recommendations ?? []}
        hasCarePlan={!!state.carePlan}
        inlinePlan={state.clinicalPlanResponse?.treatment_plan ?? null}
        patientInfo={{ name: state.patient?.name, gender: state.patient?.gender }}
      />
    </div>
  );
}

/* ── Route: marketing landing (public) ── */
function LandingRoute() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const decision = resolveRoute({ route: 'landing', session });
  if (decision.action === 'redirect') return <Navigate to={decision.to} replace />;
  return <Landing onSignIn={() => navigate('/login')} />;
}

/* ── Route: login (public) ── */
function LoginRoute() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const decision = resolveRoute({ route: 'login', session });
  if (decision.action === 'redirect') return <Navigate to={decision.to} replace />;
  return <Login onBackToLanding={() => navigate('/')} />;
}

/* ── Route: authenticated app shell ── */
function AppShell() {
  const { session } = useAuth();
  const { view } = useParams();

  // Unauthenticated → /login (same as sign-out); unknown slug → dashboard.
  const decision = resolveRoute({ route: 'app', session, view });
  if (decision.action === 'redirect') return <Navigate to={decision.to} replace />;

  return (
    <ThemeProvider>
      <AppProvider>
        <ToastProvider>
          <AppContent view={view} />
        </ToastProvider>
      </AppProvider>
    </ThemeProvider>
  );
}

function Gate() {
  const { loading } = useAuth();

  if (loading) {
    return <SplashScreen />;
  }

  return (
    <Routes>
      <Route path="/" element={<LandingRoute />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/:view" element={<AppShell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Gate />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
