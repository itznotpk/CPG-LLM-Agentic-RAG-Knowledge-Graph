import React, { useState } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { ToastProvider } from './components/shared/Notification';
import Sidebar from './components/layout/Sidebar';
import {
  DataInputSection,
  DiagnosisSection,
  CarePlanSection,
  OutputSection,
} from './components/sections';
import { StepIndicator, GlassPanel } from './components/shared';
import Home from './components/pages/Home';
import MyPatients from './components/pages/MyPatients';
import Settings from './components/pages/Settings';
import PatientChart from './components/pages/PatientChart';

const steps = [
  { id: 1, label: 'Data Input' },
  { id: 2, label: 'Diagnosis' },
  { id: 3, label: 'Care Plan' },
  { id: 4, label: 'Complete' },
];

function AppContent() {
  const { state, dispatch } = useApp();
  const { isDark } = useTheme();
  const { currentStep } = state;
  const [currentView, setCurrentView] = useState('dashboard'); // dashboard, patients, consultation, settings, chart
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chartPatient, setChartPatient] = useState(null);

  // Shared profile state
  const [profile, setProfile] = useState({
    name: 'Dr. Tay',
    email: 'dr.tay@mhnexus.com',
    phone: '+60 12-345 6789',
    specialty: 'Family Medicine',
    license: 'MMC-12345',
    facility: 'Hospital Kuala Lumpur',
    department: 'Primary Care Unit'
  });

  const handleNavigate = (view) => {
    // Reset state when manually navigating to consultation (not via Start Consult)
    if (view === 'consultation') {
      dispatch({ type: 'RESET' });
    }
    setCurrentView(view);
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
    setCurrentView('consultation');
  };

  const handleNewPatient = () => {
    dispatch({ type: 'RESET' });
    setCurrentView('consultation');
  };

  const handleViewChart = (patient) => {
    setChartPatient(patient);
    setCurrentView('chart');
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
            {/* Step Indicator */}
            <div className="mb-8">
              <StepIndicator steps={steps} currentStep={currentStep} />
            </div>

            {/* Main Content Area */}
            <GlassPanel className="min-h-[600px]">
              {renderCurrentSection()}
            </GlassPanel>
          </>
        );
      case 'settings':
        return <Settings profile={profile} setProfile={setProfile} />;
      case 'chart':
        return <PatientChart patient={chartPatient} onBack={() => setCurrentView('patients')} />;
      default:
        return <Home onStartConsult={handleStartConsult} onViewChart={handleViewChart} />;
    }
  };

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark
      ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900'
      : 'bg-gradient-to-br from-slate-100 via-white to-slate-100'
      }`}>
      {/* Sidebar */}
      <Sidebar
        currentView={currentView}
        onNavigate={handleNavigate}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        profile={profile}
      />

      {/* Main Content Area */}
      <main
        className={`min-h-screen transition-all duration-300 ${sidebarCollapsed ? 'ml-20' : 'ml-64'
          }`}
      >
        <div className="p-6 lg:p-8">
          {renderMainContent()}
        </div>
      </main>
    </div>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AppProvider>
        <ToastProvider>
          <AppContent />
        </ToastProvider>
      </AppProvider>
    </ThemeProvider>
  );
}

export default App;
