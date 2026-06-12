import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
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
import { getAllPatients, getAllPatientConsultations, downloadCarePlanPDF, getLatestVitals } from '../../lib/supabase';

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
function NextReviewDisplay({ patientNric, patientStatus, consultations, isDark }) {
  // Only show next review date for follow-up required patients
  if (patientStatus !== 'follow-up') {
    return <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>—</span>;
  }

  const consultation = consultations[patientNric];

  // Not loaded yet / no consultation / no next review - show dash
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

  // Urgency-coloured chip so overdue/due-soon reviews pop out of the list
  const chip = tcaDays < 0
    ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
    : tcaDays <= 3
      ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
      : 'bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20';

  return (
    <div className="flex flex-col items-start gap-1">
      <span className={`text-sm font-medium ds-numeric ${isDark ? 'text-white' : 'text-slate-800'}`}>{formattedDate}</span>
      <span className={`inline-flex px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wide border ${chip}`}>
        {tcaDays < 0 ? `Overdue ${Math.abs(tcaDays)}d` : tcaDays === 0 ? 'Due today' : `TCA ${tcaDays}d`}
      </span>
    </div>
  );
}

// Helper component to display latest consultation date
function LatestConsultDisplay({ patientNric, consultations, isDark }) {
  const consultation = consultations[patientNric];

  // Not loaded yet
  if (consultation === undefined) {
    return (
      <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'} flex items-center gap-1.5`}>
        <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" />
      </span>
    );
  }

  // No consultation
  if (!consultation || !consultation.consultationTime) {
    return <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No visits</span>;
  }

  // Format date for display
  const dateObj = new Date(consultation.consultationTime);
  const formattedDate = dateObj.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });

  // Relative recency ("Today" / "Yesterday" / "12d ago") — quicker to scan than a
  // raw timestamp when triaging which patients were seen recently.
  const startOfDay = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
  const daysAgo = Math.round((startOfDay(new Date()) - startOfDay(dateObj)) / 86400000);
  const relative = daysAgo <= 0 ? 'Today' : daysAgo === 1 ? 'Yesterday' : `${daysAgo}d ago`;

  return (
    <div className="flex flex-col items-start">
      <span className={`text-sm font-medium ds-numeric ${isDark ? 'text-white' : 'text-slate-800'}`}>{formattedDate}</span>
      <span className={`text-[11px] mt-0.5 font-medium ${daysAgo <= 1 ? 'text-teal-500' : isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        {relative} · {dateObj.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  );
}

// BMI chip for the patient banner. Pulls the latest live_vitals row (weight +
// height) and derives BMI = kg / m². Renders nothing when the patient has no
// weight/height recorded, so it's additive — the meta row stays clean otherwise.
function PatientBmiBadge({ nric, isDark }) {
  const [bmi, setBmi] = React.useState(null);

  React.useEffect(() => {
    let cancelled = false;
    if (!nric) { setBmi(null); return; }
    getLatestVitals(nric).then(({ vitals }) => {
      if (cancelled) return;
      const w = Number(vitals?.weight), h = Number(vitals?.height);
      if (w > 0 && h > 0) {
        const m = h / 100;
        setBmi(+(w / (m * m)).toFixed(1));
      } else {
        setBmi(null);
      }
    }).catch(() => { if (!cancelled) setBmi(null); });
    return () => { cancelled = true; };
  }, [nric]);

  if (bmi == null) return null;

  // BMI category → label + colour (Asian-population cutoffs are stricter, but the
  // standard WHO bands keep this consistent with the rest of the UI).
  const cat = bmi < 18.5 ? { label: 'Underweight', c: 'text-amber-500' }
    : bmi < 25 ? { label: 'Normal', c: 'text-emerald-500' }
    : bmi < 30 ? { label: 'Overweight', c: 'text-amber-500' }
    : { label: 'Obese', c: 'text-red-500' };

  return (
    <>
      <span className={`w-px h-3.5 ${isDark ? 'bg-white/15' : 'bg-slate-300'}`} />
      <span className="inline-flex items-center gap-1">
        <span className={`font-semibold ${cat.c}`}>BMI {bmi}</span>
        <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>· {cat.label}</span>
      </span>
    </>
  );
}

// Parse free-text clinical notes into structured blocks for readable rendering.
// Recognises bracket sections ("[Severity/Staging]" + "- key: value" lines) and
// inline labelled fields ("CC:", "HPI:", "PE/Labs:" …). Anything else is plain text.
function parseClinicalNotes(raw) {
  const blocks = [];
  let group = null; // active bracket section accumulating "- key: value" items
  for (const line of raw.split('\n')) {
    const t = line.trim();
    if (!t) { group = null; continue; }

    const bracket = t.match(/^\[(.+)\]$/);
    if (bracket) {
      group = { type: 'group', title: bracket[1].trim(), items: [] };
      blocks.push(group);
      continue;
    }

    const bullet = t.match(/^[-•]\s*(.+)$/);
    if (bullet && group) {
      const kv = bullet[1].match(/^(.+?):\s*(.+)$/);
      group.items.push(kv ? { k: kv[1].trim(), v: kv[2].trim() } : { k: null, v: bullet[1].trim() });
      continue;
    }

    const field = t.match(/^([A-Za-z][A-Za-z/ &]{0,24}):\s*(.*)$/);
    if (field) {
      group = null;
      blocks.push({ type: 'field', label: field[1].trim(), value: field[2].trim() });
      continue;
    }

    // continuation / loose prose — fold into the previous field or text block
    const last = blocks[blocks.length - 1];
    if (last && (last.type === 'field' || last.type === 'text')) {
      last.value = `${last.value} ${t}`.trim();
    } else {
      blocks.push({ type: 'text', value: t });
    }
    group = null;
  }
  return blocks;
}

// Split a medication entry into a bold drug name + secondary detail line.
function parseMedication(med) {
  const text = (med && typeof med === 'object'
    ? (med.name || med.medication || 'Unknown')
    : String(med || '')).trim();
  const extra = (med && typeof med === 'object')
    ? [med.dose, med.frequency].filter(Boolean).join(' · ')
    : '';

  // Drug name = text up to the first dose number or "(…)" qualifier.
  const idxs = [];
  const dose = text.match(/\s(?=\d)/);
  if (dose) idxs.push(dose.index);
  const paren = text.indexOf(' (');
  if (paren > 0) idxs.push(paren);
  const splitIdx = idxs.length ? Math.min(...idxs) : text.length;

  let name = text.slice(0, splitIdx).replace(/[,;:\-\s]+$/, '').trim();
  let detail = text.slice(splitIdx).trim();
  if (!name || name.length > 45) {
    const words = text.split(/\s+/);
    name = words.slice(0, 3).join(' ');
    detail = words.slice(3).join(' ');
  }
  if (extra) detail = detail ? `${detail} · ${extra}` : extra;
  return { name, detail };
}

// Clinical notes for a patient, with a dropdown to switch between past visits.
// Consumes the already-fetched `selectedPatientConsultations` list (newest-first)
// — no extra round-trip — and structures the selected visit's notes.
function ClinicalNotesDisplay({ consultations, loading, isDark }) {
  const list = Array.isArray(consultations) ? consultations : [];
  const withNotes = list.filter(c => c && c.clinicalNotes && String(c.clinicalNotes).trim());
  const [selectedId, setSelectedId] = React.useState(null);

  // Default to the most recent visit that has notes; re-sync when the list changes.
  React.useEffect(() => {
    if (withNotes.length === 0) { setSelectedId(null); return; }
    setSelectedId(prev => (withNotes.some(c => c.id === prev) ? prev : withNotes[0].id));
  }, [list]);

  // Visit number is derived from position in the FULL list so it matches the
  // Consultation History numbering (which counts visits without notes too).
  const labelFor = (c) => {
    const idxInAll = list.findIndex(x => x.id === c.id);
    const visitNo = idxInAll >= 0 ? list.length - idxInAll : '?';
    const d = c.consultationTime
      ? new Date(c.consultationTime).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      : '';
    return `Visit ${visitNo}${d ? ` · ${d}` : ''}`;
  };

  const Header = ({ children }) => (
    <div className="flex items-center justify-between gap-2 mb-3">
      <p className="text-xs font-bold uppercase tracking-wider text-blue-500">Clinical Notes</p>
      {children}
    </div>
  );

  if (loading) {
    return (
      <>
        <Header />
        <div className="flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-slate-400" strokeWidth={1.5} />
          <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Loading clinical notes...</span>
        </div>
      </>
    );
  }

  if (withNotes.length === 0) {
    return (
      <>
        <Header />
        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>No clinical notes recorded</p>
      </>
    );
  }

  const selected = withNotes.find(c => c.id === selectedId) || withNotes[0];
  const consultDate = selected.consultationTime ? new Date(selected.consultationTime).toLocaleString() : 'Unknown date';
  const blocks = parseClinicalNotes(selected.clinicalNotes);

  return (
    <>
      <Header>
        {withNotes.length > 1 && (
          <select
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(Number(e.target.value))}
            className={`text-xs rounded-md px-2 py-1 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500/30 ${isDark ? 'bg-white/10 text-slate-200 ring-1 ring-white/10' : 'bg-white text-slate-600 ring-1 ring-slate-200'}`}
          >
            {withNotes.map(c => (
              <option key={c.id} value={c.id}>{labelFor(c)}</option>
            ))}
          </select>
        )}
      </Header>
      <div className="max-h-36 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
      <div className={`p-3 rounded-lg space-y-3 ${isDark ? 'bg-white/5' : 'bg-slate-50'}`}>
        {blocks.map((b, i) => {
          if (b.type === 'group') {
            return (
              <div key={i}>
                <p className={`text-[10px] font-semibold uppercase tracking-wide mb-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{b.title}</p>
                <div className="flex flex-wrap gap-1.5">
                  {b.items.map((it, j) => (
                    <span key={j} className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-md ${isDark ? 'bg-white/10 text-slate-300' : 'bg-white text-slate-700 border border-slate-200'}`}>
                      {it.k && <span className="font-semibold">{it.k}</span>}
                      <span className="ds-numeric">{it.v}</span>
                    </span>
                  ))}
                </div>
              </div>
            );
          }
          if (b.type === 'field') {
            return (
              <div key={i} className="flex gap-2.5">
                <span className="text-[10px] font-bold uppercase tracking-wide text-blue-500 mt-1 flex-shrink-0 w-16">{b.label}</span>
                <p className={`text-sm leading-snug ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{b.value}</p>
              </div>
            );
          }
          return <p key={i} className={`text-sm leading-snug ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{b.value}</p>;
        })}
      </div>
      </div>
      <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        Last updated: {consultDate}
      </p>
    </>
  );
}

const MyPatients = ({ onViewChart, onNewPatient }) => {
  const { isDark, accent } = useTheme();
  const location = useLocation();
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

  // Handle automatic selection and expansion of patient based on navigation state (from Home tab follow-ups)
  useEffect(() => {
    const selectedNric = location.state?.selectPatientNric;
    const requestedStatusFilter = location.state?.statusFilter;

    if (!selectedNric) return;

    if (searchTerm) {
      setSearchTerm('');
      return;
    }

    if (requestedStatusFilter && statusFilter !== requestedStatusFilter) {
      setStatusFilter(requestedStatusFilter);
      return;
    }

    if (!loading && patients.length > 0) {
      const patientToSelect = patients.find(p => p.nsn === selectedNric);
      if (patientToSelect) {
        setSelectedPatient(patientToSelect);
        refreshPatientConsultation(patientToSelect.nsn);
        fetchPatientConsultations(patientToSelect.nsn);

        // Clear router history state to prevent repeating selection on tab switches
        window.history.replaceState({}, document.title);

        // Smoothly scroll the expanded patient details into view
        setTimeout(() => {
          const detailElement = document.getElementById(`patient-detail-${patientToSelect.nsn}`);
          const rowElement = document.getElementById(`patient-row-${patientToSelect.nsn}`);
          (detailElement || rowElement)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 350);
      }
    }
  }, [loading, patients, location.state, searchTerm, statusFilter]);

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

  // Get consistent color based on gender: Male (blue), Female (pink), default is teal
  const getAvatarColor = (gender) => {
    const isFemale = typeof gender === 'string' && gender.toLowerCase().startsWith('f');
    const isMale = typeof gender === 'string' && gender.toLowerCase().startsWith('m');

    if (isFemale) {
      return 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200';
    } else if (isMale) {
      return 'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200';
    } else {
      return 'bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-200';
    }
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

  // Sort patients by latest consultation time (newest first), falling back to name
  const sortedPatients = useMemo(() => {
    let list = [...patients];
    return list.sort((a, b) => {
      const consultA = patientConsultations[a.nsn];
      const consultB = patientConsultations[b.nsn];

      const timeA = consultA?.consultationTime ? new Date(consultA.consultationTime).getTime() : 0;
      const timeB = consultB?.consultationTime ? new Date(consultB.consultationTime).getTime() : 0;

      if (timeA !== timeB) {
        return timeB - timeA;
      }
      return (a.name || '').localeCompare(b.name || '');
    });
  }, [patients, patientConsultations]);

  // Use sorted patient registry list
  const filteredPatients = sortedPatients;

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
          New Patient
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
              { key: 'follow-up', label: 'Follow-up Required' }
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
          <table className="w-full table-fixed">
            <colgroup>
              <col className="w-10" />
              <col className="w-[26%]" />
              <col className="w-[15%]" />
              <col className="w-[42%]" />
              <col className="w-[17%]" />
            </colgroup>
            <thead>
              <tr className={`border-b ${isDark ? 'border-white/10 bg-white/[0.02]' : 'border-slate-200 bg-slate-50/60'}`}>
                <th className="w-10 p-4"></th>
                <th className={`text-left p-4 text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Patient</th>
                <th className={`text-left p-4 text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Latest Consult</th>
                <th className={`text-left p-4 text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Diagnoses</th>
                <th className={`text-left p-4 text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Next Review (TCA)</th>
              </tr>
            </thead>
            <tbody>
              {/* Loading State */}
              {loading && (
                <tr>
                  <td colSpan="5" className="p-8 text-center">
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
                  <td colSpan="5" className="p-8 text-center">
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
                  <td colSpan="5" className="p-8 text-center">
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
                    id={`patient-row-${patient.nsn}`}
                    onClick={() => handlePatientExpand(patient)}
                    className={`border-b cursor-pointer transition-colors border-l-[3px]
                      ${patient.status === 'follow-up' ? 'border-l-amber-400/70' : 'border-l-transparent'}
                      ${selectedPatient?.id === patient.id
                        ? isDark ? 'bg-[var(--accent-primary)]/10 border-white/5' : 'bg-[var(--accent-primary)]/5 border-slate-100'
                        : isDark ? 'border-white/5 hover:bg-white/5' : 'border-slate-100 hover:bg-slate-50'
                      }`}
                  >
                    {/* Dropdown Toggle Button */}
                    <td className="p-4 w-10">
                      <button
                        onClick={(e) => { e.stopPropagation(); handlePatientExpand(patient); }}
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
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${getAvatarColor(patient.gender)} font-semibold text-sm`}>
                          {getInitials(patient.name || '')}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className={`font-semibold truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient.name || 'Unknown'}</p>
                            {patient.status === 'follow-up' && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-500 border border-amber-500/20 flex-shrink-0">
                                Follow-up
                              </span>
                            )}
                          </div>
                          <p className={`text-xs ds-numeric mt-0.5 truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                            {patient.nsn || '—'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="p-4">
                      <LatestConsultDisplay
                        patientNric={patient.nsn}
                        consultations={patientConsultations}
                        isDark={isDark}
                      />
                    </td>
                    <td className="p-4">
                      <div className="min-w-0 flex flex-wrap items-center gap-1.5">
                        {(() => {
                          // Get diagnoses ONLY from the latest consultation
                          const consultation = patientConsultations[patient.nsn];
                          const consultDiagnoses = consultation?.diagnoses || [];
                          const displayDiagnoses = consultDiagnoses.map(d => (typeof d === 'object' ? d.name : d));
                          // No fallback to comorbidities - diagnoses come ONLY from consultations.diagnoses

                          if (displayDiagnoses.length === 0) {
                            return <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No diagnoses</span>;
                          }

                          // Pills are far more scannable + differentiable than bullet lines;
                          // primary diagnosis gets the accent tint, the rest stay neutral.
                          const MAX_PILLS = 2;
                          const extra = displayDiagnoses.length - MAX_PILLS;
                          return (
                            <>
                              {displayDiagnoses.slice(0, MAX_PILLS).map((dx, i) => (
                                <span
                                  key={i}
                                  title={dx}
                                  className={`inline-flex max-w-full px-2.5 py-1 rounded-lg text-xs font-medium border truncate
                                    ${i === 0
                                      ? isDark
                                        ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border-[var(--accent-primary)]/25'
                                        : 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border-[var(--accent-primary)]/20'
                                      : isDark
                                        ? 'bg-white/5 text-slate-300 border-white/10'
                                        : 'bg-slate-100 text-slate-600 border-slate-200'
                                    }`}
                                >
                                  {dx}
                                </span>
                              ))}
                              {extra > 0 && (
                                <span
                                  title={displayDiagnoses.slice(MAX_PILLS).join(' · ')}
                                  className={`inline-flex px-2 py-1 rounded-lg text-xs font-semibold border
                                    ${isDark ? 'bg-white/5 text-slate-400 border-white/10' : 'bg-slate-50 text-slate-500 border-slate-200'}`}
                                >
                                  +{extra} more
                                </span>
                              )}
                            </>
                          );
                        })()}
                      </div>
                    </td>
                    <td className="p-4">
                      <NextReviewDisplay
                        patientNric={patient.nsn}
                        patientStatus={patient.status}
                        consultations={patientConsultations}
                        isDark={isDark}
                      />
                    </td>
                  </tr>

                  {/* Expandable Detail Row — Redesigned Premium Layout */}
                  {selectedPatient?.id === patient.id && (
                    <tr>
                      <td colSpan="5" className="p-0">
                        <div
                          id={`patient-detail-${patient.nsn}`}
                          className={`mx-3 my-3 px-6 py-5 rounded-3xl backdrop-blur-2xl ring-1 ${
                            isDark
                              ? 'bg-slate-900/40 ring-white/10 shadow-2xl shadow-black/40'
                              : 'bg-white/55 ring-slate-900/[0.06] shadow-xl shadow-slate-400/20'
                          }`}
                        >

                          {/* ═══ HEADER BAR: Avatar + Demographics + Badges ═══ */}
                          <div className={`flex items-center gap-4 px-5 py-4 rounded-xl mb-5 ${isDark ? 'bg-white/[0.04] ring-1 ring-white/[0.06]' : 'bg-white/60 ring-1 ring-slate-200/60'}`}>
                            {/* Large Avatar */}
                            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${getAvatarColor(patient.gender)} font-bold text-lg flex-shrink-0`}>
                              {getInitials(patient.name || '')}
                            </div>

                            {/* Name & Demographics */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2.5 flex-wrap">
                                <h3 className={`text-lg font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                  {patient.name || 'Unknown Patient'}
                                </h3>
                                {getStatusBadge(patient.status)}
                              </div>
                              <div className={`flex items-center gap-3 mt-2 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                <span className="font-medium tracking-tight">{patient.nsn || '—'}</span>
                                <span className={`w-px h-3.5 ${isDark ? 'bg-white/15' : 'bg-slate-300'}`} />
                                <span>{patient.age ? `${patient.age} yrs` : '—'}</span>
                                <span className={`w-px h-3.5 ${isDark ? 'bg-white/15' : 'bg-slate-300'}`} />
                                <span>{patient.gender || '—'}</span>
                                <span className={`w-px h-3.5 ${isDark ? 'bg-white/15' : 'bg-slate-300'}`} />
                                <span>{patient.race || '—'}</span>
                                <PatientBmiBadge nric={patient.nsn} isDark={isDark} />
                              </div>
                            </div>
                          </div>

                          {/* ═══ TWO-COLUMN BODY ═══ */}
                          {/* items-stretch (grid default) makes both columns equal height;
                              the History card flex-fills the left column so its lower border
                              lines up with the Current Medications card on the right. */}
                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                            {/* ─── LEFT COLUMN (50%) ─── */}
                            <div className="lg:col-span-1 flex flex-col gap-5 min-h-0">
                              {/* Comorbidities Tags */}
                              <div className={`p-4 rounded-xl ${isDark ? 'bg-white/[0.03] ring-1 ring-white/[0.06]' : 'bg-white/55 ring-1 ring-slate-200/60'}`}>
                                <p className="text-xs font-bold uppercase tracking-wider text-violet-700 mb-3">Comorbidities</p>
                                <div className="flex flex-wrap gap-2">
                                  {patient.comorbidities && patient.comorbidities.length > 0 ? (
                                    (Array.isArray(patient.comorbidities) ? patient.comorbidities : [String(patient.comorbidities)]).map((c, i) => (
                                      <span key={i} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${isDark ? 'bg-violet-500/15 text-violet-300 border border-violet-500/20' : 'bg-violet-50 text-violet-700 border border-violet-200'}`}>
                                        <span className="w-1.5 h-1.5 rounded-full bg-violet-500 flex-shrink-0" />
                                        {typeof c === 'object' ? c.name || JSON.stringify(c) : c}
                                      </span>
                                    ))
                                  ) : (
                                    <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>N/A</span>
                                  )}
                                </div>
                              </div>

                              {/* Consultation History Timeline */}
                              <div className={`p-4 rounded-xl flex-1 flex flex-col min-h-0 ${isDark ? 'bg-white/[0.03] ring-1 ring-white/[0.06]' : 'bg-white/55 ring-1 ring-slate-200/60'}`}>
                                <div className="flex items-center justify-between mb-3">
                                  <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Consultation History</p>
                                  {selectedPatientConsultations.length > 0 && (
                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>
                                      {selectedPatientConsultations.length} record{selectedPatientConsultations.length > 1 ? 's' : ''}
                                    </span>
                                  )}
                                </div>

                                {(() => {
                                  if (loadingHistory) {
                                    return (
                                      <div className="flex items-center gap-2.5 py-6 justify-center">
                                        <Loader2 className={`w-5 h-5 animate-spin ${accent.text}`} />
                                        <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Loading consultation history...</span>
                                      </div>
                                    );
                                  }

                                  if (selectedPatientConsultations.length > 0) {
                                    return (
                                      // relative + flex-1 with an absolutely-positioned scroll layer:
                                      // the inner list does not contribute to column height, so the card
                                      // stays bounded to the (taller) right column and scrolls like the
                                      // Current Medications card instead of overflowing past it.
                                      <div className="relative flex-1 min-h-0">
                                        <div className="absolute inset-0 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                                          <div className="relative">
                                            {/* Timeline line */}
                                            <div className={`absolute left-[11px] top-2 bottom-2 w-px ${isDark ? 'bg-white/10' : 'bg-slate-200'}`} />

                                            <div className="space-y-3">
                                          {selectedPatientConsultations.map((consult, index) => {
                                            const dateObj = consult.consultationTime ? new Date(consult.consultationTime) : new Date(consult.createdAt || 0);
                                            const dateToDisplay = dateObj.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Singapore' });
                                            const timeToDisplay = dateObj.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Singapore' });
                                            const diagnoses = consult.diagnoses || [];
                                            // Chronological visit number (list is newest-first); prefer the
                                            // DB consultation_number when present, else derive from position.
                                            const visitNo = consult.consultationNumber ?? consult.consultation_number ?? (selectedPatientConsultations.length - index);
                                            const dlLabel = consult.reportPdfUrl ? 'Download care plan PDF' : 'Download diagnosis report';

                                            return (
                                              <div key={consult.id || index} className="flex gap-3 relative">
                                                {/* Timeline dot */}
                                                <div className={`w-[22px] h-[22px] rounded-full flex items-center justify-center flex-shrink-0 mt-3 z-10 ${index === 0 ? `bg-[var(--accent-primary)]/20 border-2 border-[var(--accent-primary)]` : isDark ? 'bg-white/10 border-2 border-white/20' : 'bg-slate-100 border-2 border-slate-300'}`}>
                                                  <div className={`w-2 h-2 rounded-full ${index === 0 ? 'bg-[var(--accent-primary)]' : isDark ? 'bg-white/40' : 'bg-slate-400'}`} />
                                                </div>

                                                {/* Consultation card */}
                                                <div className={`flex-1 p-3.5 rounded-xl ring-1 transition-colors group ${isDark ? 'bg-white/[0.03] ring-white/10 hover:ring-[var(--accent-primary)]/30' : 'bg-white/70 ring-slate-200 hover:ring-[var(--accent-primary)]/40'}`}>
                                                  {/* Row 1 — visit badges + download */}
                                                  <div className="flex items-start justify-between gap-2">
                                                    <div className="flex items-center gap-1.5 flex-wrap">
                                                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider ${index === 0 ? `bg-[var(--accent-primary)]/20 ${accent.text}` : isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-200 text-slate-500'}`}>
                                                        Visit {visitNo}
                                                      </span>
                                                      {index === 0 && (
                                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider ${isDark ? 'bg-emerald-500/15 text-emerald-400' : 'bg-emerald-50 text-emerald-600'}`}>
                                                          Latest
                                                        </span>
                                                      )}
                                                    </div>
                                                    {/* Download with hover tooltip */}
                                                    <div className="relative group/dl flex-shrink-0">
                                                      <button
                                                        aria-label={dlLabel}
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
                                                        className={`p-2 rounded-lg transition-all opacity-60 group-hover:opacity-100 ${isDark ? 'hover:bg-white/10 text-slate-400 hover:text-white' : 'hover:bg-slate-200 text-slate-400 hover:text-teal-600'} active:scale-90`}
                                                      >
                                                        <Download className="w-3.5 h-3.5" strokeWidth={2} />
                                                      </button>
                                                      <span className={`pointer-events-none absolute right-0 top-full mt-1 z-20 whitespace-nowrap rounded-md px-2 py-1 text-[10px] font-medium opacity-0 translate-y-1 group-hover/dl:opacity-100 group-hover/dl:translate-y-0 transition-all duration-150 shadow-lg ${isDark ? 'bg-slate-800 text-slate-100 ring-1 ring-white/10' : 'bg-slate-800 text-white'}`}>
                                                        {dlLabel}
                                                      </span>
                                                    </div>
                                                  </div>

                                                  {/* Row 2 — date / time meta */}
                                                  <div className={`flex items-center gap-1.5 mt-2 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                                    <Calendar className="w-3.5 h-3.5" strokeWidth={1.8} />
                                                    <span className={`font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{dateToDisplay}</span>
                                                    <span className={`w-px h-3 ${isDark ? 'bg-white/15' : 'bg-slate-300'}`} />
                                                    <Clock className="w-3.5 h-3.5" strokeWidth={1.8} />
                                                    <span>{timeToDisplay}</span>
                                                  </div>

                                                  {/* Row 3 — diagnoses + ICD-11 codes */}
                                                  {diagnoses.length > 0 ? (
                                                    <div className={`mt-3 pt-3 border-t space-y-1.5 ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                                                      {diagnoses.map((dx, i) => {
                                                        const dxName = typeof dx === 'object' ? dx.name : dx;
                                                        const code = typeof dx === 'object' ? dx.icdCode : null;
                                                        return (
                                                          <div key={i} className="flex items-start justify-between gap-2">
                                                            <p className={`text-sm leading-snug ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{dxName}</p>
                                                            {code && (
                                                              <span className={`flex-shrink-0 w-20 text-center text-[10px] font-mono px-1.5 py-0.5 rounded ${isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-100 text-slate-500 ring-1 ring-slate-200'}`}>
                                                                {code}
                                                              </span>
                                                            )}
                                                          </div>
                                                        );
                                                      })}
                                                    </div>
                                                  ) : (
                                                    <p className={`text-xs mt-2 italic ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No diagnoses recorded</p>
                                                  )}
                                                </div>
                                              </div>
                                            );
                                          })}
                                            </div>
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  } else {
                                    return (
                                      <div className={`text-center py-8 rounded-xl ${isDark ? 'bg-white/[0.02]' : 'bg-slate-50'}`}>
                                        <Stethoscope className={`w-8 h-8 mx-auto mb-2 ${isDark ? 'text-slate-600' : 'text-slate-300'}`} strokeWidth={1.2} />
                                        <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No past consultations recorded</p>
                                      </div>
                                    );
                                  }
                                })()}
                              </div>
                            </div>

                            {/* ─── RIGHT COLUMN (50%) ─── */}
                            <div className="lg:col-span-1 flex flex-col gap-5">

                              {/* Allergies + Recent Vitals — Side by Side */}
                              <div className="grid grid-cols-2 gap-4">
                                {/* Allergies Box */}
                                <div className={`p-4 rounded-xl flex flex-col ${isDark ? 'bg-white/[0.03] ring-1 ring-white/[0.06]' : 'bg-white/55 ring-1 ring-slate-200/60'}`}>
                                  <p className="text-xs font-bold uppercase tracking-wider text-red-500 mb-3">Allergies</p>
                                  {patient.allergies ? (
                                    <p className="text-sm font-semibold text-red-500 leading-snug">
                                      {Array.isArray(patient.allergies) ? patient.allergies.join(', ') : String(patient.allergies)}
                                    </p>
                                  ) : (
                                    <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>N/A</span>
                                  )}
                                </div>

                                {/* Recent Vital Signs Box */}
                                <div className={`p-4 rounded-xl ${isDark ? 'bg-white/[0.03] ring-1 ring-white/[0.06]' : 'bg-white/55 ring-1 ring-slate-200/60'}`}>
                                  <p className="text-xs font-bold uppercase tracking-wider text-amber-800 mb-3">Recent Vitals</p>
                                  <Button
                                    variant="primary"
                                    size="sm"
                                    icon={FileText}
                                    onClick={() => onViewChart && onViewChart(patient)}
                                    className="!bg-amber-700 hover:!bg-amber-600 active:!bg-amber-800 focus:!ring-amber-600/50"
                                  >
                                    View chart
                                  </Button>
                                </div>
                              </div>

                              {/* Clinical Notes */}
                              <div className={`p-4 rounded-xl ${isDark ? 'bg-white/[0.03] ring-1 ring-white/[0.06]' : 'bg-white/55 ring-1 ring-slate-200/60'}`}>
                                <ClinicalNotesDisplay
                                  consultations={selectedPatientConsultations}
                                  loading={loadingHistory}
                                  isDark={isDark}
                                />
                              </div>

                              {/* Current Medications */}
                              <div className={`p-4 rounded-xl flex flex-col ${isDark ? 'bg-white/[0.03] ring-1 ring-white/[0.06]' : 'bg-white/55 ring-1 ring-slate-200/60'}`}>
                                <p className="text-xs font-bold uppercase tracking-wider text-amber-500 mb-3">Current Medications</p>
                                <div className="max-h-48 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                                  {patient.currentMeds && patient.currentMeds.length > 0 ? (
                                    <div className="space-y-1.5">
                                      {patient.currentMeds.map((med, idx) => {
                                        const { name, detail } = parseMedication(med);
                                        return (
                                          <div key={idx} className={`flex items-start gap-2.5 p-2 rounded-lg ${isDark ? 'bg-white/[0.03]' : 'bg-slate-50'}`}>
                                            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 bg-amber-500" />
                                            <div className="min-w-0">
                                              <p className={`text-sm font-semibold leading-snug ${isDark ? 'text-white' : 'text-slate-800'}`}>{name}</p>
                                              {detail && <p className={`text-xs leading-snug mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{detail}</p>}
                                            </div>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  ) : (
                                    <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
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
                <div className={`w-12 h-12 rounded-full ${getAvatarColor(historyPatient.gender)}
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
