import React, { useState, useEffect, useCallback } from 'react';
import { formatDateUTC8 } from '../../utils/timezone';
import {
  Search,
  Filter,
  UserPlus,
  FileText,
  Calendar,
  ChevronRight,
  User,
  Phone,
  Mail,
  AlertCircle,
  Clock,
  CheckCircle,
  XCircle,
  RotateCcw,
  History,
  Pill,
  Activity,
  X,
  Stethoscope,
  TestTube,
  AlertTriangle,
  Loader2,
  Download
} from 'lucide-react';
import { GlassCard } from '../shared/GlassCard';
import { Button } from '../shared/Button';
import { useTheme } from '../../context/ThemeContext';
import { getAllPatients, getPatientConsultation, getAllPatientConsultations, downloadCarePlanPDF } from '../../lib/supabase';

// Download a single diagnosis record as a plain-text report
function downloadDiagnosisReport(dx, patient, dateToDisplay, timeToDisplay) {
  const name = typeof dx === 'object' ? dx.name : dx;
  const icd = typeof dx === 'object' && dx.icdCode ? dx.icdCode : '—';
  const lines = [
    'DIAGNOSIS REPORT',
    '================',
    `Patient   : ${patient?.name || patient?.nsn || '—'}`,
    `NRIC/NSN  : ${patient?.nsn || '—'}`,
    `Date      : ${dateToDisplay || '—'}  ${timeToDisplay || ''}`.trim(),
    '',
    `Diagnosis : ${name}`,
    `ICD-11    : ${icd}`,
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `diagnosis_${(name || 'report').replace(/\s+/g, '_').slice(0, 40)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// Helper component to display next review date from consultations
function NextReviewDisplay({ patientNric, consultations, isDark, accent }) {
  const consultation = consultations[patientNric];

  // Not loaded yet - show dash
  if (consultation === undefined) {
    return <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>—</span>;
  }

  // No consultation or no next review
  if (!consultation || !consultation.nextReview) {
    return <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>—</span>;
  }

  // Calculate days until TCA
  const reviewDate = new Date(consultation.nextReview);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  reviewDate.setHours(0, 0, 0, 0);
  const tcaDays = Math.ceil((reviewDate - today) / (1000 * 60 * 60 * 24));

  // Format date for display
  const formattedDate = reviewDate.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });

  return (
    <div className="flex items-center justify-center gap-2">
      <Calendar className={`w-4 h-4 ${accent.text}`} strokeWidth={1.5} />
      <div>
        <p className={`text-sm ds-numeric ${isDark ? 'text-white' : 'text-slate-800'}`}>{formattedDate}</p>
        <p className={`text-xs font-medium ${tcaDays <= 3 ? 'text-amber-500' : tcaDays < 0 ? 'text-red-500' : isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {tcaDays < 0 ? `Overdue: ${Math.abs(tcaDays)} ${Math.abs(tcaDays) === 1 ? 'Day' : 'Days'}` : `TCA: ${tcaDays} ${tcaDays === 1 ? 'Day' : 'Days'}`}
        </p>
      </div>
    </div>
  );
}

// Helper component to display clinical notes for a patient
function ClinicalNotesDisplay({ patientNric, consultations, setConsultations, loadingNric, setLoadingNric, isDark }) {
  const [localLoading, setLocalLoading] = React.useState(false);

  React.useEffect(() => {
    // If we already have data cached, don't fetch again
    if (consultations[patientNric] !== undefined) return;

    const fetchConsultation = async () => {
      setLocalLoading(true);
      setLoadingNric(patientNric);

      try {
        const result = await getPatientConsultation(patientNric);
        setConsultations(prev => ({
          ...prev,
          [patientNric]: result.found ? result.consultation : null
        }));
      } catch (err) {
        console.error('Error fetching consultation:', err);
        setConsultations(prev => ({
          ...prev,
          [patientNric]: null
        }));
      } finally {
        setLocalLoading(false);
        setLoadingNric(null);
      }
    };

    fetchConsultation();
  }, [patientNric, consultations, setConsultations, setLoadingNric]);

  const consultation = consultations[patientNric];
  const isLoading = loadingNric === patientNric || localLoading;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-slate-400" strokeWidth={1.5} />
        <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Loading clinical notes...</span>
      </div>
    );
  }

  if (!consultation || !consultation.clinicalNotes) {
    return (
      <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
        No clinical notes recorded
      </p>
    );
  }

  // Format the date
  const consultDate = consultation.consultationTime
    ? new Date(consultation.consultationTime).toLocaleString()
    : 'Unknown date';

  return (
    <div>
      <div className={`p-3 rounded-lg ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
        <p className={`text-sm whitespace-pre-wrap ${isDark ? 'text-white' : 'text-slate-800'}`}>
          {consultation.clinicalNotes}
        </p>
      </div>
      <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        Last updated: {consultDate}
      </p>
    </div>
  );
}

const MyPatients = ({ onViewChart, onNewPatient }) => {
  const { isDark, accent } = useTheme();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // all, active, discharged, follow-up
  const [patients, setPatients] = useState([]); // Only database patients
  const [allPatients, setAllPatients] = useState([]); // Keep all patients for counts
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [showMedicalHistory, setShowMedicalHistory] = useState(false);
  const [historyPatient, setHistoryPatient] = useState(null);
  const [patientConsultations, setPatientConsultations] = useState({}); // Cache consultations by NRIC
  const [loadingConsultation, setLoadingConsultation] = useState(null);
  const [selectedPatientConsultations, setSelectedPatientConsultations] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Fetch all past consultations for a patient
  const fetchPatientConsultations = async (patientNric) => {
    setLoadingHistory(true);
    try {
      const result = await getAllPatientConsultations(patientNric, 50); // Fetch up to 50 past consultations
      if (result.consultations) {
        setSelectedPatientConsultations(result.consultations);
      } else {
        setSelectedPatientConsultations([]);
      }
    } catch (err) {
      console.error('Failed to fetch patient consultations:', err);
      setSelectedPatientConsultations([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Fetch patients from Supabase only
  const fetchPatients = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Get patients from Supabase only
      const { patients: supabasePatients, error: supabaseError } = await getAllPatients({});

      console.log('Supabase fetch result:', { supabasePatients, supabaseError }); // Debug log

      if (supabaseError) {
        setError('Failed to load patients from database');
        setAllPatients([]);
        setPatients([]);
        setLoading(false);
        return;
      }

      setAllPatients(supabasePatients);

      // Apply search/status filters
      let filtered = supabasePatients;
      if (searchTerm) {
        // Normalize search term (remove dashes for NRIC matching)
        const normalizedSearch = searchTerm.toLowerCase().replace(/-/g, '');
        filtered = filtered.filter(p => {
          const name = (p.name || '').toLowerCase();
          const nsn = (p.nsn || '').toLowerCase();
          return name.includes(searchTerm.toLowerCase()) ||
            nsn.includes(searchTerm.toLowerCase()) ||
            nsn.replace(/-/g, '').includes(normalizedSearch);
        });
      }
      if (statusFilter !== 'all') {
        filtered = filtered.filter(p => p.status === statusFilter);
      }

      setPatients(filtered);

    } catch (err) {
      console.error('Exception fetching patients:', err);
      setError('Failed to load patients');
      setAllPatients([]);
      setPatients([]);
    }

    setLoading(false);
  }, [searchTerm, statusFilter]);

  // Initial load and when filters change
  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  // Fetch latest consultation for all patients to display Next Review dates and Diagnoses
  // Always fetch fresh data to ensure sync with database
  useEffect(() => {
    const fetchAllConsultations = async () => {
      if (allPatients.length === 0) return;

      // Fetch consultations for all patients in parallel
      const results = await Promise.all(
        allPatients.map(async (patient) => {
          try {
            // Get the latest consultation for this patient (limit 1)
            const result = await getAllPatientConsultations(patient.nsn, 1);
            if (result.consultations && result.consultations.length > 0) {
              return {
                nric: patient.nsn,
                consultation: result.consultations[0]
              };
            }
            return { nric: patient.nsn, consultation: null };
          } catch {
            return { nric: patient.nsn, consultation: null };
          }
        })
      );

      // Update state with all results
      const newConsultations = {};
      results.forEach(r => {
        newConsultations[r.nric] = r.consultation;
      });
      setPatientConsultations(newConsultations); // Replace entire cache with fresh data
    };

    fetchAllConsultations();
  }, [allPatients]);


  // Debounce search - wait 300ms after user stops typing
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPatients();
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  const avatarColors = [
    'bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-200',
    'bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200',
    'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200',
    'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
    'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200',
    'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-200',
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

  // Refresh consultation data for a specific patient (for dynamic sync)
  // Fetches the latest consultation
  const refreshPatientConsultation = async (patientNric) => {
    try {
      const result = await getAllPatientConsultations(patientNric, 1);
      if (result.consultations && result.consultations.length > 0) {
        setPatientConsultations(prev => ({
          ...prev,
          [patientNric]: result.consultations[0]
        }));
      }
    } catch (err) {
      console.error('Failed to refresh consultation:', err);
    }
  };

  // Handle patient row expansion - refresh data when expanding
  const handlePatientExpand = (patient) => {
    if (selectedPatient?.id === patient.id) {
      setSelectedPatient(null); // Collapse
      setSelectedPatientConsultations([]);
    } else {
      setSelectedPatient(patient); // Expand
      // Refresh consultation data for this patient to ensure sync
      refreshPatientConsultation(patient.nsn);
      // Fetch all past consultations for this patient
      fetchPatientConsultations(patient.nsn);
    }
  };

  // Since we're fetching filtered data from Supabase, we just use patients directly
  const filteredPatients = patients;

  const getStatusBadge = (status) => {
    const config = {
      active: { bg: 'bg-emerald-500/20', text: 'text-emerald-500', border: 'border-emerald-500/30', icon: CheckCircle, label: 'Active' },
      discharged: { bg: 'bg-slate-500/20', text: isDark ? 'text-slate-300' : 'text-slate-600', border: 'border-slate-500/30', icon: XCircle, label: 'Discharged' },
      'follow-up': { bg: 'bg-amber-500/20', text: 'text-amber-500', border: 'border-amber-500/30', icon: RotateCcw, label: 'Follow-up Required' }
    };
    const cfg = config[status] || config['active']; // Default to active if status is unknown
    const Icon = cfg.icon;
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
        <Icon className="w-3 h-3" strokeWidth={1.5} />
        {cfg.label}
      </span>
    );
  };

  const getRiskBadge = (level) => {
    const config = {
      low: { bg: 'bg-emerald-500/20', text: 'text-emerald-500' },
      moderate: { bg: 'bg-amber-500/20', text: 'text-amber-500' },
      high: { bg: 'bg-orange-500/20', text: 'text-orange-500' },
      critical: { bg: 'bg-red-500/20', text: 'text-red-600 font-bold' }
    };
    const cfg = config[level] || config['low']; // Default to low if level is unknown
    const displayLevel = level || 'low';
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${cfg.bg} ${cfg.text}`}>
        {displayLevel.charAt(0).toUpperCase() + displayLevel.slice(1)} Risk
      </span>
    );
  };

  const statusCounts = {
    all: allPatients.length,
    active: allPatients.filter(p => p.status === 'active').length,
    'follow-up': allPatients.filter(p => p.status === 'follow-up').length,
    discharged: allPatients.filter(p => p.status === 'discharged').length
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className={`text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>My Patients</h1>
          <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Your patient panel and clinical history</p>
        </div>
        <Button variant="primary" icon={UserPlus} onClick={onNewPatient}>
          Walk-in Consult
        </Button>
      </div>

      {/* Search and Filter Bar */}
      <GlassCard className="p-4" variant={isDark ? 'dark' : 'light'}>
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} strokeWidth={1.5} />
            <input
              type="text"
              name="patient-search"
              autoComplete="off"
              spellCheck={false}
              placeholder="Search by name or NRIC…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={`w-full pl-10 pr-4 py-2.5 rounded-xl border transition-colors
                ${isDark
                  ? 'bg-white/5 border-white/10 text-white placeholder-slate-500 focus-visible:border-[var(--accent-primary)]/50'
                  : 'bg-white border-slate-200 text-slate-800 placeholder-slate-400 focus-visible:border-[var(--accent-primary)]'
                } focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/20`}
            />
          </div>

          {/* Status Filter Tabs */}
          <div className="flex items-center gap-2">
            {[
              { key: 'all', label: 'All' },
              { key: 'active', label: 'Active' },
              { key: 'follow-up', label: 'Follow-up' },
              { key: 'discharged', label: 'Discharged' }
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setStatusFilter(tab.key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]
                  ${statusFilter === tab.key
                    ? `bg-[var(--accent-primary)]/20 ${accent.text} border border-[var(--accent-primary)]/30`
                    : isDark
                      ? 'bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white border border-transparent'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-800 border border-transparent'
                  }`}
              >
                {tab.label} ({statusCounts[tab.key]})
              </button>
            ))}
          </div>
        </div>
      </GlassCard>

      {/* Patient List */}
      <GlassCard className="overflow-hidden" variant={isDark ? 'dark' : 'light'}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className={`border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                <th className="w-12 p-4"></th>
                <th className={`text-center p-4 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Patient</th>
                <th className={`text-center p-4 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Status</th>
                <th className={`text-center p-4 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Diagnoses</th>
                <th className={`text-center p-4 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Next Review (TCA)</th>
                <th className={`text-center p-4 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Risk</th>
              </tr>
            </thead>
            <tbody>
              {/* Loading State */}
              {loading && (
                <tr>
                  <td colSpan="6" className="p-8 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <Loader2 className={`w-8 h-8 animate-spin ${accent.text}`} strokeWidth={1.5} />
                      <p className={`${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Loading patients...</p>
                    </div>
                  </td>
                </tr>
              )}

              {/* Error State */}
              {!loading && error && (
                <tr>
                  <td colSpan="6" className="p-8 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <AlertCircle className="w-8 h-8 text-red-500" strokeWidth={1.5} />
                      <p className="text-red-500">{error}</p>
                      <Button variant="ghost" size="sm" icon={RotateCcw} onClick={fetchPatients}>
                        Try Again
                      </Button>
                    </div>
                  </td>
                </tr>
              )}

              {/* Empty State */}
              {!loading && !error && filteredPatients.length === 0 && (
                <tr>
                  <td colSpan="6" className="p-8 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <User className={`w-8 h-8 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} strokeWidth={1.5} />
                      <p className={`${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {searchTerm ? `No patients found matching "${searchTerm}"` : 'No patients found'}
                      </p>
                    </div>
                  </td>
                </tr>
              )}

              {/* Patient Rows */}
              {!loading && !error && filteredPatients.map((patient) => (
                <React.Fragment key={patient.id}>
                  <tr
                    className={`border-b transition-colors
                      ${selectedPatient?.id === patient.id
                        ? isDark ? 'bg-[var(--accent-primary)]/10' : 'bg-[var(--accent-primary)]/5'
                        : isDark ? 'border-white/5 hover:bg-white/5' : 'border-slate-100 hover:bg-slate-50'
                      }`}
                  >
                    {/* Dropdown Toggle Button */}
                    <td className="p-4 w-12">
                      <button
                        onClick={() => handlePatientExpand(patient)}
                        aria-label="Expand Patient Details"
                        aria-expanded={selectedPatient?.id === patient.id}
                        className={`p-2 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-200'}`}
                      >
                        <ChevronRight
                          aria-hidden="true"
                          className={`w-5 h-5 transition-transform duration-200 ${isDark ? 'text-slate-400' : 'text-slate-500'}
                            ${selectedPatient?.id === patient.id ? 'rotate-90' : ''}`}
                          strokeWidth={1.5}
                        />
                      </button>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${getAvatarColor(patient.name || '')} font-semibold text-sm`}>
                          {getInitials(patient.name || '')}
                        </div>
                        <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient.name || 'Unknown'}</p>
                      </div>
                    </td>
                    <td className="p-4 text-center">
                      {getStatusBadge(patient.status)}
                    </td>
                    <td className="p-4">
                      <div className="max-w-[200px]">
                        {(() => {
                          // Get diagnoses ONLY from the latest consultation
                          const consultation = patientConsultations[patient.nsn];
                          const consultDiagnoses = consultation?.diagnoses || [];

                          let displayDiagnoses = [];

                          if (consultDiagnoses.length > 0) {
                            displayDiagnoses = consultDiagnoses.map(d => typeof d === 'object' ? d.name : d);
                          }
                          // No fallback to comorbidities - diagnoses come ONLY from consultations.diagnoses

                          return displayDiagnoses.length > 0 ? (
                            displayDiagnoses.map((dx, i) => (
                              <p key={i} className={`text-sm ${i > 0 ? 'mt-1' : ''} ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                • {typeof dx === 'object' ? dx.name : dx}
                              </p>
                            ))
                          ) : (
                            <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>No diagnoses</p>
                          );
                        })()}
                      </div>
                    </td>
                    <td className="p-4 text-center">
                      <NextReviewDisplay
                        patientNric={patient.nsn}
                        consultations={patientConsultations}
                        isDark={isDark}
                        accent={accent}
                      />
                    </td>
                    <td className="p-4 text-center">
                      {getRiskBadge(patient.riskLevel)}
                    </td>
                  </tr>

                  {/* Expandable Detail Row */}
                  {selectedPatient?.id === patient.id && (
                    <tr>
                      <td colSpan="6" className={`p-0 ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
                        <div className="p-6">
                          <div className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-white'} border ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                            <h3 className={`text-base font-semibold mb-4 ${isDark ? 'text-white' : 'text-slate-800'}`}>
                              Patient details
                            </h3>

                            {/* Basic Info Grid */}
                            <div className={`grid grid-cols-2 md:grid-cols-4 text-sm mb-6 divide-y md:divide-y-0 md:divide-x ${isDark ? 'divide-white/10' : 'divide-slate-200'} border rounded-xl overflow-hidden ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                              {[
                                { label: 'Name', value: patient.name || '—', cls: '' },
                                { label: 'NRIC', value: patient.nsn || '—', cls: 'ds-mono' },
                                { label: 'Age', value: patient.age ? `${patient.age} years` : '—', cls: 'ds-numeric' },
                                { label: 'Gender', value: patient.gender || '—', cls: '' },
                              ].map(({ label, value, cls }) => (
                                <div key={label} className={`px-4 py-3 ${isDark ? 'bg-white/3' : 'bg-white'}`}>
                                  <p className="ds-eyebrow mb-1">{label}</p>
                                  <p className={`font-medium text-sm ${cls} ${isDark ? 'text-white' : 'text-slate-800'}`}>{value}</p>
                                </div>
                              ))}
                              <div className={`px-4 py-3 ${isDark ? 'bg-white/3' : 'bg-white'} md:border-t-0 ${isDark ? 'border-t border-white/10' : 'border-t border-slate-200'}`}>
                                <p className="ds-eyebrow mb-1">Race</p>
                                <p className={`font-medium text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient.race || '—'}</p>
                              </div>
                              <div className={`px-4 py-3 ${isDark ? 'bg-white/3' : 'bg-white'} md:border-t-0 ${isDark ? 'border-t border-white/10' : 'border-t border-slate-200'}`}>
                                <p className="ds-eyebrow mb-1">Allergies</p>
                                <p className={`font-medium text-sm ${patient.allergies ? 'text-red-500' : isDark ? 'text-white' : 'text-slate-800'}`}>
                                  {patient.allergies
                                    ? (Array.isArray(patient.allergies) ? patient.allergies.join(', ') : String(patient.allergies))
                                    : 'No known allergies'}
                                </p>
                              </div>
                              <div className={`col-span-2 px-4 py-3 ${isDark ? 'bg-white/3' : 'bg-white'} md:border-t-0 ${isDark ? 'border-t border-white/10' : 'border-t border-slate-200'}`}>
                                <p className="ds-eyebrow mb-1">Comorbidities</p>
                                <p className={`font-medium text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                  {patient.comorbidities && patient.comorbidities.length > 0
                                    ? (Array.isArray(patient.comorbidities) ? patient.comorbidities.join(', ') : String(patient.comorbidities))
                                    : 'None recorded'}
                                </p>
                              </div>
                            </div>

                            {/* Diagnoses */}
                            <div className={`mb-6 pb-4 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                              <p className="ds-eyebrow mb-3">Diagnoses / medical history (Past consultations & care plans)</p>
                              {(() => {
                                if (loadingHistory) {
                                  return (
                                    <div className="flex items-center gap-2 py-4">
                                      <Loader2 className={`w-4 h-4 animate-spin ${accent.text}`} />
                                      <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Loading history & care plans...</span>
                                    </div>
                                  );
                                }

                                if (selectedPatientConsultations.length > 0) {
                                  const MAX_VISIBLE = 2;
                                  const hasMore = selectedPatientConsultations.length > MAX_VISIBLE;

                                  return (
                                    <div>
                                      {/* Scrollable container with max height */}
                                      <div className={`space-y-3 ${hasMore ? 'max-h-60 overflow-y-auto pr-2' : ''}`} style={hasMore ? { scrollbarWidth: 'thin' } : {}}>
                                        {selectedPatientConsultations.map((consult, index) => {
                                          const dateObj = consult.consultationTime ? new Date(consult.consultationTime) : new Date(consult.createdAt || 0);
                                          const dateToDisplay = dateObj ? dateObj.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Singapore' }) : 'Unknown Date';
                                          const timeToDisplay = dateObj ? dateObj.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Singapore' }) : '';
                                          const diagnoses = consult.diagnoses || [];

                                          return (
                                            <div key={consult.id || index} className={`p-3 rounded-xl border ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-50 border-slate-200'} flex items-center justify-between gap-4 hover:border-[var(--accent-primary)]/40 transition-colors`}>
                                              <div className="min-w-0">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--accent-primary)]/20 ${accent.text} uppercase tracking-wider`}>
                                                    Consultation
                                                  </span>
                                                  <span className={`text-xs font-semibold ds-numeric ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                                                    {dateToDisplay} {timeToDisplay && `at ${timeToDisplay}`}
                                                  </span>
                                                </div>

                                                {/* Diagnoses for this specific consultation */}
                                                <div className="mt-2 space-y-1">
                                                  {diagnoses.length > 0 ? (
                                                    diagnoses.map((dx, i) => (
                                                      <p key={i} className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-800'}`}>
                                                        • <span className="font-medium">{typeof dx === 'object' ? dx.name : dx}</span>
                                                        {typeof dx === 'object' && dx.icdCode && (
                                                          <span className={`ml-2 text-xs font-mono px-1.5 py-0.5 rounded ${isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-200/80 text-slate-500'}`}>
                                                            {dx.icdCode}
                                                          </span>
                                                        )}
                                                      </p>
                                                    ))
                                                  ) : (
                                                    <p className={`text-xs italic ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>• No specific diagnoses recorded</p>
                                                  )}
                                                </div>
                                              </div>

                                              {/* Download button for this specific care plan */}
                                              <button
                                                title={consult.reportPdfUrl ? 'Download Care Plan PDF' : 'Download Diagnosis Text Report'}
                                                onClick={() => {
                                                  if (consult.reportPdfUrl) {
                                                    const fileName = `CarePlan_${(patient.name || 'Patient').replace(/\s+/g, '_')}_${dateToDisplay.replace(/\s+/g, '_')}.pdf`;
                                                    downloadCarePlanPDF(consult.reportPdfUrl, fileName);
                                                  } else {
                                                    const firstDx = diagnoses[0] || 'No_Diagnosis';
                                                    const dxName = typeof firstDx === 'object' ? firstDx.name : firstDx;
                                                    downloadDiagnosisReport(dxName, patient, dateToDisplay, timeToDisplay);
                                                  }
                                                }}
                                                className={`flex-shrink-0 p-2.5 rounded-xl transition-all shadow-sm flex items-center justify-center text-white bg-teal-600 hover:bg-teal-700 active:scale-95`}
                                              >
                                                <Download className="w-4 h-4" strokeWidth={2.5} />
                                              </button>
                                            </div>
                                          );
                                        })}
                                      </div>

                                      {/* Show count indicator if scrollable */}
                                      {hasMore && (
                                        <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                                          Showing all {selectedPatientConsultations.length} past consultations (scroll to view)
                                        </p>
                                      )}
                                    </div>
                                  );
                                } else {
                                  return (
                                    <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                      No past consultations or care plans recorded
                                    </p>
                                  );
                                }
                              })()}
                            </div>

                            {/* Three-column grid for Vital Signs, Clinical Notes, Current Medications */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                              {/* Recent Vital Signs */}
                              <div className={`p-4 rounded-xl border-l-2 border-[var(--accent-primary)] ${isDark ? 'bg-[var(--accent-primary)]/5 border border-[var(--accent-primary)]/20' : 'bg-[var(--accent-primary)]/5 border border-[var(--accent-primary)]/20'}`}>
                                <p className="ds-eyebrow mb-3">Recent vital signs</p>
                                <Button
                                  variant="primary"
                                  size="sm"
                                  icon={FileText}
                                  onClick={() => onViewChart && onViewChart(patient)}
                                >
                                  View chart
                                </Button>
                              </div>

                              {/* Clinical Notes */}
                              <div className={`p-4 rounded-xl border-l-2 border-blue-400 ${isDark ? 'bg-blue-500/5 border border-blue-500/20' : 'bg-blue-50/60 border border-blue-200'}`}>
                                <p className="ds-eyebrow mb-3" style={{ color: 'rgb(59,130,246)' }}>Clinical notes</p>
                                <div className="max-h-32 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                                  <ClinicalNotesDisplay
                                    patientNric={patient.nsn}
                                    consultations={patientConsultations}
                                    setConsultations={setPatientConsultations}
                                    loadingNric={loadingConsultation}
                                    setLoadingNric={setLoadingConsultation}
                                    isDark={isDark}
                                  />
                                </div>
                              </div>

                              {/* Current Medications */}
                              <div className={`p-4 rounded-xl border-l-2 border-amber-400 ${isDark ? 'bg-amber-500/5 border border-amber-500/20' : 'bg-amber-50/60 border border-amber-200'}`}>
                                <p className="ds-eyebrow mb-3" style={{ color: 'rgb(245,158,11)' }}>Current medications</p>
                                <div className="max-h-32 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                                  {patient.currentMeds && patient.currentMeds.length > 0 ? (
                                    <div className="space-y-1">
                                      {patient.currentMeds.map((med, idx) => (
                                        <p key={idx} className={`text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                          • {typeof med === 'object'
                                            ? `${med.name || med.medication || 'Unknown'} ${med.dose || ''} ${med.frequency || ''}`.trim()
                                            : String(med)}
                                        </p>
                                      ))}
                                    </div>
                                  ) : (
                                    <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                      No medications recorded
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Medical History Modal */}
      {showMedicalHistory && historyPatient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowMedicalHistory(false)} />
          <div className={`relative w-full max-w-4xl max-h-[85vh] rounded-2xl shadow-2xl overflow-hidden
            ${isDark ? 'bg-slate-900' : 'bg-white'}`}>

            {/* Modal Header */}
            <div className={`flex items-center justify-between p-6 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-full ${getAvatarColor(historyPatient.name)} 
                  flex items-center justify-center font-semibold`}>
                  {getInitials(historyPatient.name)}
                </div>
                <div>
                  <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                    Medical History
                  </h2>
                  <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {historyPatient.name} • {historyPatient.nsn}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowMedicalHistory(false)}
                className={`p-2 rounded-lg transition-colors ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-100'}`}
              >
                <X className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} strokeWidth={1.5} />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(85vh-100px)]">
              {historyPatient.medicalHistory ? (
                <div className="space-y-6">
                  {/* Allergies Alert */}
                  {historyPatient.medicalHistory.allergies?.length > 0 && (
                    <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30">
                      <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" strokeWidth={1.5} />
                      <div>
                        <p className="text-sm font-medium text-red-500">Allergies</p>
                        <p className={`text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>
                          {historyPatient.medicalHistory.allergies.join(', ')}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Conditions */}
                  <div>
                    <h3 className={`flex items-center gap-2 text-sm font-semibold uppercase mb-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                      <Stethoscope className="w-4 h-4" strokeWidth={1.5} /> Medical Conditions
                    </h3>
                    <div className={`rounded-xl overflow-hidden border ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                      <table className="w-full">
                        <thead className={isDark ? 'bg-white/5' : 'bg-slate-50'}>
                          <tr>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Condition</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Diagnosed</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {historyPatient.medicalHistory.conditions.map((cond, i) => (
                            <tr key={i} className={`border-t ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                              <td className={`p-3 text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>{cond.name}</td>
                              <td className={`p-3 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{cond.diagnosedDate}</td>
                              <td className="p-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium
                                  ${cond.status === 'Active' ? 'bg-emerald-500/20 text-emerald-500' : 'bg-slate-500/20 text-slate-400'}`}>
                                  {cond.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Medications */}
                  <div>
                    <h3 className={`flex items-center gap-2 text-sm font-semibold uppercase mb-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                      <Pill className="w-4 h-4" strokeWidth={1.5} /> Medications
                    </h3>
                    <div className={`rounded-xl overflow-hidden border ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                      <table className="w-full">
                        <thead className={isDark ? 'bg-white/5' : 'bg-slate-50'}>
                          <tr>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Medication</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Dosage</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Start Date</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {historyPatient.medicalHistory.medications.map((med, i) => (
                            <tr key={i} className={`border-t ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                              <td className={`p-3 text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</td>
                              <td className={`p-3 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{med.dosage}</td>
                              <td className={`p-3 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{med.startDate}</td>
                              <td className="p-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium
                                  ${med.status === 'Current' ? 'bg-blue-500/20 text-blue-500' : 'bg-slate-500/20 text-slate-400'}`}>
                                  {med.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Lab Results */}
                  <div>
                    <h3 className={`flex items-center gap-2 text-sm font-semibold uppercase mb-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                      <TestTube className="w-4 h-4" strokeWidth={1.5} /> Recent Lab Results
                    </h3>
                    <div className={`rounded-xl overflow-hidden border ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                      <table className="w-full">
                        <thead className={isDark ? 'bg-white/5' : 'bg-slate-50'}>
                          <tr>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Test</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Result</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Date</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {historyPatient.medicalHistory.labResults.map((lab, i) => (
                            <tr key={i} className={`border-t ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                              <td className={`p-3 text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>{lab.test}</td>
                              <td className={`p-3 text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{lab.value}</td>
                              <td className={`p-3 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{lab.date}</td>
                              <td className="p-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium
                                  ${lab.status === 'Normal' ? 'bg-emerald-500/20 text-emerald-500'
                                    : lab.status === 'High' ? 'bg-red-500/20 text-red-500'
                                      : 'bg-amber-500/20 text-amber-500'}`}>
                                  {lab.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Procedures */}
                  <div>
                    <h3 className={`flex items-center gap-2 text-sm font-semibold uppercase mb-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                      <Activity className="w-4 h-4" strokeWidth={1.5} /> Procedures & Tests
                    </h3>
                    <div className={`rounded-xl overflow-hidden border ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                      <table className="w-full">
                        <thead className={isDark ? 'bg-white/5' : 'bg-slate-50'}>
                          <tr>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Procedure</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Date</th>
                            <th className={`text-left p-3 text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Result</th>
                          </tr>
                        </thead>
                        <tbody>
                          {historyPatient.medicalHistory.procedures.map((proc, i) => (
                            <tr key={i} className={`border-t ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                              <td className={`p-3 text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>{proc.name}</td>
                              <td className={`p-3 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{proc.date}</td>
                              <td className={`p-3 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{proc.result}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <History className={`w-12 h-12 mx-auto mb-4 ${isDark ? 'text-slate-600' : 'text-slate-300'}`} strokeWidth={1.5} />
                  <p className={`text-lg font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    No medical history available
                  </p>
                  <p className={`text-sm mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    Medical records for this patient have not been uploaded yet.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MyPatients;
