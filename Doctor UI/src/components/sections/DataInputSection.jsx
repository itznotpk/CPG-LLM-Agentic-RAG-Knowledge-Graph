import React from 'react';
import { Stethoscope, Sparkles, Brain, FileText, Activity, Search, UserPlus, CheckCircle, AlertCircle, X, Database, Heart, Pill, BarChart2, Wind, Scale, Thermometer, Loader2, ClipboardList } from 'lucide-react';
import { ClinicalNotes } from './ClinicalNotes';
import { VitalsGrid } from './VitalsGrid';
import { Button, Skeleton, SkeletonDiagnosis, GlassCard, Badge } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { VitalsLineChart } from '../shared/VitalsLineChart';
import { getPatientConsultation } from '../../lib/supabase';

// Analyzing Skeleton Component
function AnalyzingSkeleton() {
  const { isDark } = useTheme();

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Progress indicator */}
      <div className={`backdrop-blur-xl border rounded-2xl p-6 ${isDark ? 'bg-slate-800/80 border-white/10' : 'bg-white/60 border-slate-200'}`}>
        <div className="flex items-center gap-4 mb-4">
          <div className="p-3 bg-[var(--accent-primary)]/20 rounded-xl">
            <Brain className={`w-6 h-6 animate-pulse text-[var(--accent-primary)]`} />
          </div>
          <div className="flex-1">
            <h3 className={`text-lg font-semibold mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>AI Analysis in Progress</h3>
            <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Processing clinical data and generating diagnosis...</p>
          </div>
        </div>

        {/* Progress steps */}
        <div className="space-y-3">
          <AnalysisStep label="Parsing clinical notes" status="complete" />
          <AnalysisStep label="Analyzing symptoms and findings" status="active" />
          <AnalysisStep label="Cross-referencing with CPG guidelines" status="pending" />
          <AnalysisStep label="Generating differential diagnosis" status="pending" />
        </div>
      </div>

      {/* Skeleton preview of what's coming */}
      <SkeletonDiagnosis />
    </div>
  );
}

function AnalysisStep({ label, status }) {
  const { isDark } = useTheme();

  return (
    <div className="flex items-center gap-3">
      <div className={`w-6 h-6 rounded-full flex items-center justify-center ${status === 'complete' ? 'bg-green-500' :
        status === 'active' ? 'bg-[var(--accent-primary)] animate-pulse' :
          isDark ? 'bg-slate-600' : 'bg-slate-200'
        }`}>
        {status === 'complete' && (
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        )}
        {status === 'active' && (
          <div className="w-2 h-2 bg-white rounded-full" />
        )}
      </div>
      <span className={`text-sm ${status === 'complete' ? (isDark ? 'text-green-400' : 'text-green-700') + ' font-medium' :
        status === 'active' ? 'text-[var(--accent-primary)] font-medium' :
          isDark ? 'text-slate-400' : 'text-slate-500'
        }`}>
        {label}
        {status === 'active' && <span className="ml-2 animate-pulse">...</span>}
      </span>
    </div>
  );
}

// Vital metrics configuration for chart
const vitalsTabs = [
  {
    id: 'bloodPressure', label: 'Blood Pressure', icon: Heart, metrics: [
      { key: 'bpSystolic', label: 'Systolic', unit: 'mmHg', color: '#ef4444' },
      { key: 'bpDiastolic', label: 'Diastolic', unit: 'mmHg', color: '#f97316' },
    ]
  },
  {
    id: 'heartRate', label: 'Heart Rate', icon: Activity, metrics: [
      { key: 'hr', label: 'Heart Rate', unit: 'bpm', color: '#8b5cf6' },
    ]
  },
  {
    id: 'oxygenation', label: 'SpO2', icon: Wind, metrics: [
      { key: 'spo2', label: 'Oxygen Saturation', unit: '%', color: '#3b82f6' },
    ]
  },
  {
    id: 'weight', label: 'Weight', icon: Scale, metrics: [
      { key: 'weight', label: 'Weight', unit: 'kg', color: '#10b981' },
    ]
  },
  {
    id: 'temperature', label: 'Temperature', icon: Thermometer, metrics: [
      { key: 'temp', label: 'Temperature', unit: '°C', color: '#f59e0b' },
    ]
  },
];

// Chart Modal Component
function ChartModal({ patient, isOpen, onClose }) {
  const { isDark } = useTheme();
  const [activeTab, setActiveTab] = React.useState('bloodPressure');

  if (!isOpen || !patient) return null;

  // Use vitals history from patient object (Supabase only)
  const rawHistory = patient.vitalsHistory || [];

  // Normalize all entries to objects
  let history = rawHistory.map(d => {
    try {
      return typeof d === 'string' ? JSON.parse(d) : d;
    } catch (e) {
      return d;
    }
  });

  // Make it ALIGNED and DYNAMIC: Add the currently entered vitals as the latest point
  const { vitals } = useApp().state;
  if (vitals.bpSystolic || vitals.hr) {
    const currentEntry = {
      date: 'Current',
      bpSystolic: parseInt(vitals.bpSystolic) || 0,
      bpDiastolic: parseInt(vitals.bpDiastolic) || 0,
      hr: parseInt(vitals.hr) || 0,
      temp: parseFloat(vitals.temp) || 0,
      spo2: parseInt(vitals.spo2) || 0,
      weight: parseFloat(vitals.weight) || 0,
    };

    history = [...history, currentEntry];
  }

  const vitalsData = history;
  const currentTabConfig = vitalsTabs.find(t => t.id === activeTab);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className={`fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[70]
        w-full max-w-4xl max-h-[90vh] overflow-auto rounded-2xl shadow-2xl
        ${isDark ? 'bg-slate-900 border border-white/10' : 'bg-white border border-slate-200'}`}
      >
        {/* Header */}
        <div className={`sticky top-0 flex items-center justify-between p-4 border-b
          ${isDark ? 'bg-slate-900 border-white/10' : 'bg-white border-slate-200'}`}>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-xl">
              <BarChart2 className="w-5 h-5 text-emerald-500" />
            </div>
            <div>
              <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                Vital Signs History - {patient.name}
              </h2>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {vitalsData.length} historical readings from MPIS
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`p-2 rounded-lg transition-colors
              ${isDark ? 'hover:bg-white/10 text-slate-400 hover:text-white'
                : 'hover:bg-slate-100 text-slate-500 hover:text-slate-800'}`}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className={`p-4 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
          <div className="flex gap-2 overflow-x-auto">
            {vitalsTabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm whitespace-nowrap transition-all
                    ${isActive
                      ? 'bg-emerald-500 text-white'
                      : isDark ? 'bg-white/10 text-slate-300 hover:bg-white/20' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Chart */}
        <div className="p-6">
          {vitalsData.length > 0 ? (
            <VitalsLineChart
              data={vitalsData}
              metrics={currentTabConfig?.metrics || []}
              height={350}
            />
          ) : (
            <div className={`text-center py-12 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              No historical vitals data available for this patient
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// Patient Info Display Card for found patients
function PatientInfoCard({ patient, mpisData, onClear, onViewChart }) {
  const { isDark } = useTheme();
  const [previousNotes, setPreviousNotes] = React.useState(null);
  const [loadingNotes, setLoadingNotes] = React.useState(true);

  // Fetch previous clinical notes when patient is loaded
  React.useEffect(() => {
    const fetchNotes = async () => {
      if (!patient?.nsn) return;
      setLoadingNotes(true);
      try {
        const result = await getPatientConsultation(patient.nsn);
        if (result.found) {
          setPreviousNotes(result.consultation);
        } else {
          setPreviousNotes(null);
        }
      } catch (err) {
        console.error('Error fetching notes:', err);
        setPreviousNotes(null);
      } finally {
        setLoadingNotes(false);
      }
    };
    fetchNotes();
  }, [patient?.nsn]);

  return (
    <GlassCard className="p-6 border-2 border-green-500/30 bg-gradient-to-br from-green-500/10 to-emerald-500/5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-500/20 rounded-xl">
            <CheckCircle className="w-6 h-6 text-green-500" />
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
              Patient Found in MPIS
            </h3>
            <p className={`text-sm ${isDark ? 'text-green-400' : 'text-green-700'}`}>
              Data auto-populated from medical records
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onViewChart && (
            <Button
              variant="success"
              size="sm"
              icon={BarChart2}
              onClick={() => onViewChart(patient)}
            >
              View Chart
            </Button>
          )}
          <Button variant="ghost" size="sm" icon={X} onClick={onClear}>
            Clear
          </Button>
        </div>
      </div>

      {/* Patient Demographics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/60'}`}>
          <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Full Name</span>
          <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient?.name || '-'}</p>
        </div>
        <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/60'}`}>
          <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>NRIC</span>
          <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient?.nsn || '-'}</p>
        </div>
        <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/60'}`}>
          <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Date of Birth</span>
          <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient?.dob || '-'}</p>
        </div>
        <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/60'}`}>
          <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Age / Gender</span>
          <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient?.age || '-'} / {patient?.gender || '-'}</p>
        </div>
      </div>

      {/* MPIS Data */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
        <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/60'}`}>
          <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Race</span>
          <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{mpisData?.race || '-'}</p>
        </div>
        <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/60'}`}>
          <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Allergies</span>
          <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{mpisData?.allergies || 'None known'}</p>
        </div>
      </div>

      {/* Comorbidities */}
      {mpisData?.comorbidities?.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Heart className="w-4 h-4 text-[var(--accent-primary)]" />
            <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-700'}`}>Comorbidities</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {mpisData.comorbidities.map((condition, idx) => (
              <Badge key={idx} variant="warning" size="md">
                {condition}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Previous Clinical Notes */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <ClipboardList className="w-4 h-4 text-[var(--accent-primary)]" />
          <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-700'}`}>Previous Clinical Notes</span>
        </div>
        {loadingNotes ? (
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
            <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Loading...</span>
          </div>
        ) : previousNotes?.clinicalNotes ? (
          <div className={`p-3 rounded-lg ${isDark ? 'bg-white/10' : 'bg-white/60'}`}>
            <p className={`text-sm whitespace-pre-wrap ${isDark ? 'text-white' : 'text-slate-800'}`}>
              {previousNotes.clinicalNotes}
            </p>
            <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Last updated: {new Date(previousNotes.consultationTime).toLocaleString()}
              {previousNotes.doctorName && ` by ${previousNotes.doctorName}`}
            </p>
          </div>
        ) : (
          <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>No previous clinical notes</p>
        )}
      </div>

      {/* Current Medications */}
      {mpisData?.currentMeds?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Pill className="w-4 h-4 text-[var(--accent-primary)]" />
            <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-700'}`}>Current Medications</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {mpisData.currentMeds.map((med, idx) => (
              <div
                key={idx}
                className={`flex items-center justify-between p-2.5 rounded-lg ${isDark ? 'bg-white/10' : 'bg-white/60'}`}
              >
                <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</span>
                <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {med.dose} {med.frequency}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </GlassCard>
  );
}

// New Patient Registration Form
function NewPatientForm({ nsn, onClear, onPatientRegistered }) {
  const { isDark } = useTheme();
  const { state, dispatch } = useApp();
  const { patient, mpisData } = state;
  const [isRegistering, setIsRegistering] = React.useState(false);
  const [registrationError, setRegistrationError] = React.useState('');
  const [registrationSuccess, setRegistrationSuccess] = React.useState(false);

  // Parse Malaysian NRIC to extract DOB and Gender
  // Format: YYMMDD-PB-#### (e.g., 040911-07-0517)
  // - First 6 digits: YYMMDD (date of birth)
  // - Next 2 digits: PB (place of birth code)
  // - Last 4 digits: #### (last digit: odd = male, even = female)
  const parseNRIC = (nric) => {
    if (!nric || nric.length < 14) return null;

    const cleanNric = nric.replace(/-/g, '');
    if (cleanNric.length !== 12) return null;

    // Extract date components
    const yy = cleanNric.substring(0, 2);
    const mm = cleanNric.substring(2, 4);
    const dd = cleanNric.substring(4, 6);

    // Determine century: if YY > current year's last 2 digits, it's 1900s, else 2000s
    const currentYear = new Date().getFullYear();
    const currentYY = currentYear % 100;
    const century = parseInt(yy) > currentYY ? '19' : '20';
    const fullYear = century + yy;

    // Format DOB as YYYY-MM-DD for date input
    const dob = `${fullYear}-${mm}-${dd}`;

    // Calculate age
    const birthDate = new Date(dob);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }

    // Determine gender from last digit (odd = male, even = female)
    const lastDigit = parseInt(cleanNric.charAt(11));
    const gender = lastDigit % 2 === 1 ? 'Male' : 'Female';

    return { dob, age, gender };
  };

  // Auto-fill DOB on mount if we have a valid NRIC (gender is NOT auto-filled)
  React.useEffect(() => {
    if (nsn && !patient?.dob) {
      const parsed = parseNRIC(nsn);
      if (parsed) {
        dispatch({
          type: 'SET_PATIENT', payload: {
            nsn: nsn,
            dob: parsed.dob,
            age: parsed.age,
            // Gender is NOT auto-filled - user must select
          }
        });
      }
    }
  }, [nsn]);

  // Calculate age dynamically when DOB changes
  React.useEffect(() => {
    if (patient?.dob) {
      const birthDate = new Date(patient.dob);
      const today = new Date();
      let calculatedAge = today.getFullYear() - birthDate.getFullYear();
      const monthDiff = today.getMonth() - birthDate.getMonth();
      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
        calculatedAge--;
      }
      if (calculatedAge !== patient?.age && calculatedAge >= 0) {
        dispatch({ type: 'SET_PATIENT', payload: { age: calculatedAge } });
      }
    }
  }, [patient?.dob]);

  const handlePatientChange = (field, value) => {
    dispatch({ type: 'SET_PATIENT', payload: { [field]: value } });
    setRegistrationError('');
    setRegistrationSuccess(false);
  };

  const handleMpisChange = (field, value) => {
    dispatch({ type: 'SET_MPIS_DATA', payload: { ...mpisData, [field]: value } });
    setRegistrationError('');
    setRegistrationSuccess(false);
  };

  // Check if required fields are filled
  const canRegister = patient?.name && patient?.dob && patient?.gender;

  // Handle patient registration to Supabase
  const handleRegisterPatient = async () => {
    if (!canRegister) {
      setRegistrationError('Please fill in all required fields (Name, DOB, Gender)');
      return;
    }

    setIsRegistering(true);
    setRegistrationError('');

    try {
      // Import the register function
      const { registerPatient } = await import('../../lib/supabase');

      const result = await registerPatient({
        nric: patient.nsn || nsn,
        fullName: patient.name,
        dateOfBirth: patient.dob,
        gender: patient.gender,
        race: mpisData?.race || null,
        ethnicity: mpisData?.ethnicity || null,
        allergies: mpisData?.allergies || null,
        comorbidities: mpisData?.comorbidities || null,
      });

      if (result.error) {
        setRegistrationError(result.error.message || 'Failed to register patient');
      } else {
        setRegistrationSuccess(true);
        console.log('✅ Patient registered successfully:', result.patientId);
        // Important: Update parent state that patient is now in DB
        if (onPatientRegistered) {
          onPatientRegistered(result.patientId);
        }
      }
    } catch (err) {
      console.error('Registration error:', err);
      setRegistrationError(err.message || 'Failed to register patient');
    } finally {
      setIsRegistering(false);
    }
  };

  return (
    <GlassCard className="p-6 border-2 border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-orange-500/5">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-500/20 rounded-xl">
            <UserPlus className="w-6 h-6 text-amber-500" />
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
              New Patient Registration
            </h3>
            <p className={`text-sm ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
              NRIC "{nsn}" not found in MPIS. Please enter patient information.
            </p>
          </div>
        </div>
        <Button variant="ghost" size="sm" icon={X} onClick={onClear}>
          Clear
        </Button>
      </div>

      {/* Success Message */}
      {registrationSuccess && (
        <div className="mb-4 p-3 rounded-lg bg-green-500/20 border border-green-500/30 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <span className={`text-sm font-medium ${isDark ? 'text-green-400' : 'text-green-700'}`}>
            Patient registered successfully! You can now proceed with the clinical assessment.
          </span>
        </div>
      )}

      {/* Error Message */}
      {registrationError && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/20 border border-red-500/30 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className={`text-sm font-medium ${isDark ? 'text-red-400' : 'text-red-700'}`}>
            {registrationError}
          </span>
        </div>
      )}

      {/* Patient Demographics */}
      <div className="space-y-4">
        <div>
          <h4 className={`text-sm font-semibold mb-3 ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Patient Demographics
            <span className={`ml-2 text-xs font-normal ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              (Auto-filled from NRIC)
            </span>
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className={`block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Full Name *
              </label>
              <input
                type="text"
                className={`w-full px-3 py-2 rounded-lg border ${isDark
                  ? 'bg-slate-800/50 border-white/20 text-white placeholder-slate-500'
                  : 'bg-white/60 border-slate-300 text-slate-800 placeholder-slate-400'
                  } focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]`}
                placeholder="Full Name"
                value={patient?.name || ''}
                onChange={e => handlePatientChange('name', e.target.value)}
              />
            </div>
            <div>
              <label className={`block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Date of Birth * <span className="text-emerald-500">(from NRIC)</span>
              </label>
              <input
                type="date"
                className={`w-full px-3 py-2 rounded-lg border ${isDark
                  ? 'bg-slate-800/50 border-white/20 text-white'
                  : 'bg-white/60 border-slate-300 text-slate-800'
                  } focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]`}
                value={patient?.dob || ''}
                onChange={e => handlePatientChange('dob', e.target.value)}
              />
            </div>
            <div>
              <label className={`block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Age <span className="text-emerald-500">(calculated)</span>
              </label>
              <input
                type="number"
                className={`w-full px-3 py-2 rounded-lg border ${isDark
                  ? 'bg-slate-800/50 border-white/20 text-white placeholder-slate-500'
                  : 'bg-white/60 border-slate-300 text-slate-800 placeholder-slate-400'
                  } focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]`}
                placeholder="Age"
                value={patient?.age || ''}
                readOnly
              />
            </div>
            <div>
              <label className={`block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Gender * <span className="text-emerald-500">(from NRIC)</span>
              </label>
              <select
                className={`w-full px-3 py-2 rounded-lg border ${isDark
                  ? 'bg-slate-800/50 border-white/20 text-white'
                  : 'bg-white/60 border-slate-300 text-slate-800'
                  } focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]`}
                value={patient?.gender || ''}
                onChange={e => handlePatientChange('gender', e.target.value)}
              >
                <option value="">Select Gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div>
              <label className={`block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Race
              </label>
              <select
                className={`w-full px-3 py-2 rounded-lg border ${isDark
                  ? 'bg-slate-800/50 border-white/20 text-white'
                  : 'bg-white/60 border-slate-300 text-slate-800'
                  } focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]`}
                value={mpisData?.race || ''}
                onChange={e => handleMpisChange('race', e.target.value)}
              >
                <option value="">Select Race</option>
                <option value="Malay">Malay</option>
                <option value="Chinese">Chinese</option>
                <option value="Indian">Indian</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
        </div>

        {/* Medical Information */}
        <div>
          <h4 className={`text-sm font-semibold mb-3 ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Medical Information
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={`block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Known Allergies
              </label>
              <input
                type="text"
                className={`w-full px-3 py-2 rounded-lg border ${isDark
                  ? 'bg-slate-800/50 border-white/20 text-white placeholder-slate-500'
                  : 'bg-white/60 border-slate-300 text-slate-800 placeholder-slate-400'
                  } focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]`}
                placeholder="e.g., Penicillin, Sulfa drugs (or None known)"
                value={mpisData?.allergies || ''}
                onChange={e => handleMpisChange('allergies', e.target.value)}
              />
            </div>
            <div>
              <label className={`block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Comorbidities (comma-separated)
              </label>
              <input
                type="text"
                className={`w-full px-3 py-2 rounded-lg border ${isDark
                  ? 'bg-slate-800/50 border-white/20 text-white placeholder-slate-500'
                  : 'bg-white/60 border-slate-300 text-slate-800 placeholder-slate-400'
                  } focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]`}
                placeholder="e.g., Hypertension, Diabetes"
                value={mpisData?.comorbidities?.join(', ') || ''}
                onChange={e => handleMpisChange('comorbidities', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              />
            </div>
          </div>
        </div>

        {/* Register Button */}
        <div className="pt-4 border-t border-amber-500/20">
          <Button
            variant={registrationSuccess ? 'success' : 'primary'}
            size="lg"
            icon={registrationSuccess ? CheckCircle : Database}
            onClick={handleRegisterPatient}
            loading={isRegistering}
            disabled={!canRegister || isRegistering || registrationSuccess}
            className="w-full sm:w-auto"
          >
            {registrationSuccess ? 'Patient Registered' : isRegistering ? 'Registering...' : 'Register Patient to Database'}
          </Button>
          {!canRegister && (
            <p className={`mt-2 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Please fill in Full Name, Date of Birth, and Gender to register.
            </p>
          )}
        </div>
      </div>
    </GlassCard>
  );
}

export function DataInputSection({ onViewChart }) {
  const { state, dispatch, syncMPIS, analyzeAssessment, saveVitalsToDB } = useApp();
  const { isDark } = useTheme();
  const { isAnalyzing, clinicalNotes, mpisData, patient, mpisSynced, vitals } = state;
  const [nsn, setNsn] = React.useState(patient?.nsn || '');
  const [nricError, setNricError] = React.useState('');
  const [mpisLoading, setMpisLoading] = React.useState(false);
  const [mpisChecked, setMpisChecked] = React.useState(false);
  const [mpisFound, setMpisFound] = React.useState(false);
  const [isChartModalOpen, setIsChartModalOpen] = React.useState(false);
  const [notesConfirmed, setNotesConfirmed] = React.useState(false);
  const [showValidationWarning, setShowValidationWarning] = React.useState(false);

  // Auto-populate NRIC when navigating from Home page's Start Consult
  React.useEffect(() => {
    if (patient?.nsn && !nsn && !mpisChecked) {
      setNsn(patient.nsn);
    }
  }, [patient?.nsn]);

  // NRIC format validation: accepts both xxxxxx-xx-xxxx and xxxxxxxxxxxx (12 digits)
  const validateNRIC = (nric) => {
    // Remove dashes for validation
    const digitsOnly = nric.replace(/-/g, '');
    // Must be exactly 12 digits
    return /^\d{12}$/.test(digitsOnly);
  };

  // Format NRIC to standard format (xxxxxx-xx-xxxx)
  const formatNRIC = (nric) => {
    const digitsOnly = nric.replace(/-/g, '');
    if (digitsOnly.length === 12) {
      return `${digitsOnly.slice(0, 6)}-${digitsOnly.slice(6, 8)}-${digitsOnly.slice(8)}`;
    }
    return nric;
  };

  // Check if ALL vital signs fields are filled
  const hasAllVitals = vitals.bpSystolic && vitals.bpDiastolic && vitals.hr &&
    vitals.temp && vitals.rr && vitals.spo2 &&
    vitals.weight && vitals.height;
  const hasClinicaNotes = clinicalNotes.trim().length > 0 && notesConfirmed;

  // Check if any vitals are filled (for partial fill detection)
  const hasAnyVitals = vitals.bpSystolic || vitals.bpDiastolic || vitals.hr ||
    vitals.temp || vitals.rr || vitals.spo2 ||
    vitals.weight || vitals.height;
  const hasAnyClinicalNotes = clinicalNotes.trim().length > 0;

  // Determine if completely blank vs partially filled
  const isCompletelyBlank = !hasAnyVitals && !hasAnyClinicalNotes;

  // Get specific missing fields
  const getMissingVitalFields = () => {
    const missing = [];
    if (!vitals.bpSystolic || !vitals.bpDiastolic) missing.push('Blood Pressure (Systolic/Diastolic)');
    if (!vitals.hr) missing.push('Heart Rate');
    if (!vitals.temp) missing.push('Temperature');
    if (!vitals.rr) missing.push('Respiratory Rate');
    if (!vitals.spo2) missing.push('SpO2');
    if (!vitals.weight) missing.push('Weight');
    if (!vitals.height) missing.push('Height');
    return missing;
  };

  const getMissingClinicalFields = () => {
    const missing = [];
    if (!clinicalNotes.trim()) missing.push('Clinical Notes');
    else if (!notesConfirmed) missing.push('Confirm Clinical Notes (click checkbox)');
    return missing;
  };

  const canAnalyze = hasAllVitals && hasClinicaNotes && mpisChecked;

  const handleAnalyze = async () => {
    // Check validation and show warning if not ready
    if (!canAnalyze) {
      setShowValidationWarning(true);
      return;
    }

    setShowValidationWarning(false);
    // Save vitals to history before proceeding
    // We only save if the patient was found (has a record in DB)
    if (mpisFound) {
      await saveVitalsToDB();
    }
    analyzeAssessment();
  };

  // Show skeleton loader when analyzing
  if (isAnalyzing) {
    return <AnalyzingSkeleton />;
  }

  // Handler for NRIC submission
  const handleCheckNRIC = async () => {
    const trimmedNric = nsn.trim();
    if (!trimmedNric) return;

    // Validate NRIC format (accepts with or without dashes)
    if (!validateNRIC(trimmedNric)) {
      setNricError('Invalid NRIC format. Please enter 12 digits (e.g., 580315-08-1234 or 580315081234)');
      return;
    }

    // Format NRIC to standard format with dashes
    const formattedNric = formatNRIC(trimmedNric);
    setNsn(formattedNric); // Update input with formatted NRIC

    setNricError(''); // Clear any previous error
    setMpisLoading(true);
    const result = await syncMPIS(formattedNric);
    setMpisLoading(false);
    setMpisChecked(true);
    setMpisFound(result.found);
  };

  // Handler to clear and search again
  const handleClear = () => {
    setNsn('');
    setNricError('');
    setMpisChecked(false);
    setMpisFound(false);
    dispatch({ type: 'RESET' });
  };

  // Clear error when user starts typing
  const handleNricChange = (e) => {
    setNsn(e.target.value);
    if (nricError) setNricError('');
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="text-center mb-8">
        <h2 className={`text-2xl font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
          Clinical Assessment Input
        </h2>
        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          Step 1: Enter the patient's NRIC to retrieve their medical records
        </p>
      </div>

      {/* Step 1: NRIC Input */}
      {!mpisChecked && (
        <GlassCard className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
              <Database className="w-5 h-5 text-[var(--accent-primary)]" />
            </div>
            <div>
              <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                MPIS Patient Lookup
              </h3>
              <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Medical Patient Information System
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 items-stretch sm:items-end">
            <div className="flex-1">
              <label
                htmlFor="nsn-input"
                className={`block text-sm font-medium mb-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}
              >
                National Registration Identity Card (NRIC)
              </label>
              <input
                id="nsn-input"
                type="text"
                className={`w-full px-4 py-3 rounded-xl border-2 text-lg ${nricError
                  ? 'border-red-500 focus:border-red-500'
                  : isDark
                    ? 'bg-slate-800/50 border-white/20 text-white placeholder-slate-500 focus:border-[var(--accent-primary)]'
                    : 'bg-white/60 border-slate-300 text-slate-800 placeholder-slate-400 focus:border-[var(--accent-primary)]'
                  } ${isDark ? 'bg-slate-800/50 text-white placeholder-slate-500' : 'bg-white/60 text-slate-800 placeholder-slate-400'} focus:outline-none transition-colors`}
                value={nsn}
                onChange={handleNricChange}
                onKeyDown={e => e.key === 'Enter' && handleCheckNRIC()}
                placeholder="e.g., 580315-08-1234"
                disabled={mpisLoading}
              />
              {nricError && (
                <p className="text-sm mt-2 text-red-500 flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {nricError}
                </p>
              )}
              {!nricError && (
                <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  Try: 580315-08-1234, 750622-10-5678, 680910-14-9012, or 850415-07-3456
                </p>
              )}
            </div>
            <Button
              variant="primary"
              size="lg"
              icon={Search}
              onClick={handleCheckNRIC}
              loading={mpisLoading}
              disabled={!nsn.trim() || mpisLoading}
              className="min-w-[160px]"
            >
              {mpisLoading ? 'Searching...' : 'Search MPIS'}
            </Button>
          </div>
        </GlassCard>
      )}

      {/* Step 2: Show auto-filled or manual entry */}
      {mpisChecked && (
        mpisFound ? (
          <PatientInfoCard
            patient={patient}
            mpisData={mpisData}
            onClear={handleClear}
            onViewChart={() => setIsChartModalOpen(true)}
          />
        ) : (
          <NewPatientForm
            nsn={patient?.nsn || nsn}
            onClear={handleClear}
            onPatientRegistered={() => setMpisFound(true)}
          />
        )
      )}

      {/* Vitals & Clinical Notes - only show after NRIC check */}
      {mpisChecked && (
        <>
          <VitalsGrid />
          <ClinicalNotes
            isConfirmed={notesConfirmed}
            onConfirm={setNotesConfirmed}
          />
        </>
      )}

      {/* Validation Warning */}
      {showValidationWarning && !canAnalyze && mpisChecked && (
        <div className={`p-4 rounded-xl border-2 ${isDark ? 'bg-amber-500/10 border-amber-500/30' : 'bg-amber-50 border-amber-300'} animate-fadeIn`}>
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              {isCompletelyBlank ? (
                <>
                  <h4 className={`font-semibold mb-1 ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                    Please complete vital signs and clinical notes
                  </h4>
                  <p className={`text-sm ${isDark ? 'text-amber-300' : 'text-amber-600'}`}>
                    All vital signs fields and clinical notes are required before proceeding with the analysis.
                  </p>
                </>
              ) : (
                <>
                  <h4 className={`font-semibold mb-2 ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                    Please complete the following missing fields:
                  </h4>
                  {getMissingVitalFields().length > 0 && (
                    <div className="mb-2">
                      <span className={`text-xs font-medium ${isDark ? 'text-amber-400/70' : 'text-amber-600/80'}`}>Vital Signs:</span>
                      <ul className={`text-sm space-y-1 mt-1 ${isDark ? 'text-amber-300' : 'text-amber-600'}`}>
                        {getMissingVitalFields().map((field, idx) => (
                          <li key={idx} className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                            {field}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {getMissingClinicalFields().length > 0 && (
                    <div>
                      <span className={`text-xs font-medium ${isDark ? 'text-amber-400/70' : 'text-amber-600/80'}`}>Clinical Notes:</span>
                      <ul className={`text-sm space-y-1 mt-1 ${isDark ? 'text-amber-300' : 'text-amber-600'}`}>
                        {getMissingClinicalFields().map((field, idx) => (
                          <li key={idx} className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                            {field}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
            <button
              onClick={() => setShowValidationWarning(false)}
              className={`p-1 rounded-lg ${isDark ? 'hover:bg-white/10' : 'hover:bg-amber-100'}`}
            >
              <X className="w-4 h-4 text-amber-500" />
            </button>
          </div>
        </div>
      )}

      {mpisChecked && (
        <div className="flex justify-center pt-4">
          <Button
            variant="primary"
            size="xl"
            icon={Stethoscope}
            onClick={handleAnalyze}
            glow={canAnalyze}
            className="min-w-[300px]"
          >
            Analyze Clinical Assessment
          </Button>
        </div>
      )}

      {/* Chart Modal */}
      <ChartModal
        patient={patient}
        isOpen={isChartModalOpen}
        onClose={() => setIsChartModalOpen(false)}
      />
    </div>
  );
}
