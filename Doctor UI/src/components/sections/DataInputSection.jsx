import React from 'react';
import { Brain, Activity, UserPlus, X, Database, Heart, BarChart2, Wind, Scale, Thermometer, Loader2 } from 'lucide-react';
import { ClinicalNotes } from './ClinicalNotes';
import { PipelineProgress } from './PipelineProgress';
import { VitalsGrid } from './VitalsGrid';
import { SeverityStagingGrid } from './SeverityStagingGrid';
import { Button, Skeleton, SkeletonDiagnosis, GlassCard, Badge } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { VitalsLineChart } from '../shared/VitalsLineChart';
import { getPatientConsultation } from '../../lib/supabase';

// ── Medications text ⇄ structured helpers ──────────────────────────────
// DB shape is [{ name, dose, frequency }]. The UI uses a single comma-separated
// text field; we keep the full label in `name` so nothing is lost on round-trip.
function medsToText(meds) {
  if (!Array.isArray(meds)) return '';
  return meds
    .map(m => (typeof m === 'string'
      ? m
      : [m.name || m.medication, m.dose, m.frequency].filter(Boolean).join(' ')))
    .join(', ');
}
function textToMeds(text) {
  return (text || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
    .map(name => ({ name, dose: '', frequency: '' }));
}

// Analyzing Skeleton Component
function AnalyzingSkeleton() {
  const { isDark } = useTheme();

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Progress indicator */}
      <div className={`backdrop-blur-xl border rounded-2xl p-6 ${isDark ? 'bg-slate-800/80 border-white/10' : 'bg-white/60 border-slate-200'}`}>
        <div className="flex items-center gap-4 mb-4">
          <div className="p-3 bg-[var(--accent-primary)]/20 rounded-xl">
            <Brain className={`w-6 h-6 animate-pulse text-[var(--accent-primary)]`} strokeWidth={1.5} />
          </div>
          <div className="flex-1">
            <h3 className={`text-xl font-semibold tracking-tight mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>AI Analysis in Progress</h3>
            <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Processing clinical data and generating diagnosis...</p>
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
            <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
              <BarChart2 className="w-5 h-5 text-[var(--accent-primary)]" strokeWidth={1.5} />
            </div>
            <div>
              <h2 className={`text-xl font-semibold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
                Vital Signs History - {patient.name}
              </h2>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
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
            <X className="w-5 h-5" strokeWidth={1.5} />
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
                      ? 'bg-[var(--accent-primary)] text-white shadow-sm'
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

// Patient Info Display Card — read-only by default, Edit unlocks all fields
function PatientInfoCard({ patient, mpisData, onClear, onViewChart }) {
  const { isDark } = useTheme();
  const { dispatch } = useApp();

  const [isEditing, setIsEditing] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState('');
  const [savedAt, setSavedAt] = React.useState(null);
  const [draft, setDraft] = React.useState(null);

  // Track unsaved change count
  const countChanges = (d) => {
    if (!d) return 0;
    let n = 0;
    const orig = {
      name: patient?.name || '',
      gender: patient?.gender || '',
      race: mpisData?.race || '',
      allergies: (mpisData?.allergies || '').split(',').map(s => s.trim()).filter(Boolean),
      comorbidities: mpisData?.comorbidities || [],
      currentMeds: mpisData?.currentMeds || [],
    };
    if (d.name !== orig.name) n++;
    if (d.gender !== orig.gender) n++;
    if (d.race !== orig.race) n++;
    if (JSON.stringify(d.allergies) !== JSON.stringify(orig.allergies)) n++;
    if (JSON.stringify(d.comorbidities) !== JSON.stringify(orig.comorbidities)) n++;
    if (JSON.stringify(d.currentMeds) !== JSON.stringify(orig.currentMeds)) n++;
    return n;
  };

  const startEdit = () => {
    setDraft({
      name: patient?.name || '',
      gender: patient?.gender || '',
      race: mpisData?.race || '',
      allergies: (mpisData?.allergies || '').split(',').map(s => s.trim()).filter(Boolean),
      comorbidities: mpisData?.comorbidities || [],
      currentMeds: mpisData?.currentMeds ? mpisData.currentMeds.map(m => ({ ...m })) : [],
      // inline add state
      allergyInput: '',
      conditionInput: '',
      medInput: '',
    });
    setSaveError('');
    setIsEditing(true);
  };

  const cancelEdit = () => { setIsEditing(false); setDraft(null); setSaveError(''); };

  const handleSave = async () => {
    if (!patient?.nsn || !draft) return;
    setIsSaving(true); setSaveError('');
    try {
      const { updatePatientFromMPIS } = await import('../../lib/supabase');
      const payload = {
        allergies: draft.allergies.join(', ') || null,
        comorbidities: draft.comorbidities,
        currentMeds: draft.currentMeds,
      };
      const { success, error } = await updatePatientFromMPIS(patient.nsn, payload);
      if (!success || error) { setSaveError(error?.message || 'Failed to save'); return; }
      dispatch({ type: 'SET_MPIS_DATA', payload: { ...mpisData, ...payload } });
      dispatch({ type: 'SET_PATIENT', payload: { name: draft.name, gender: draft.gender } });
      setSavedAt(new Date());
      setIsEditing(false); setDraft(null);
    } catch (err) { setSaveError(err.message || 'Failed to save'); }
    finally { setIsSaving(false); }
  };

  const initials = (patient?.name || '??').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
  const savedTime = savedAt ? savedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : null;
  const unsaved = isEditing ? countChanges(draft) : 0;

  // ── shared styles ──
  const divider = `${isDark ? 'border-white/10' : 'border-slate-200'}`;
  const inputCls = `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/60 ${isDark ? 'bg-white/5 border-white/20 text-white placeholder-slate-500' : 'bg-white border-slate-300 text-slate-800 placeholder-slate-400'}`;
  const selectCls = `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/60 ${isDark ? 'bg-slate-800 border-white/20 text-white' : 'bg-white border-slate-300 text-slate-700'}`;
  const eyebrow = `text-[10px] font-semibold tracking-widest uppercase ${isDark ? 'text-slate-500' : 'text-slate-400'}`;
  const roText = `text-sm ${isDark ? 'text-white' : 'text-slate-800'}`;

  return (
    <GlassCard className="overflow-hidden">
      {/* ── Header ── */}
      <div className={`flex items-start gap-3 px-5 pt-5 pb-4 border-b ${divider}`}>
        <div className="w-10 h-10 rounded-full bg-[var(--accent-primary)]/20 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-sm font-semibold text-[var(--accent-primary)]">{initials}</span>
        </div>
        <div className="flex-1 min-w-0">
          <h3 className={`text-base font-semibold leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>{patient?.name || '—'}</h3>
          <p className={`text-xs font-mono mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            {patient?.nsn}
            {patient?.age && <> · {patient.age} {patient.gender === 'Male' ? 'M' : patient.gender === 'Female' ? 'F' : patient.gender || ''}</>}
            {mpisData?.race && <> · {mpisData.race}</>}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
            isEditing
              ? (isDark ? 'border-[var(--accent-primary)]/40 text-[var(--accent-primary)] bg-[var(--accent-primary)]/10' : 'border-teal-300 text-teal-700 bg-teal-50')
              : (isDark ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' : 'border-emerald-200 text-emerald-700 bg-emerald-50')
          }`}>
            {isEditing ? 'Editing' : 'Patient matched'}
          </span>
          {!isEditing && (
            <>
              <button onClick={startEdit} className={`text-xs px-3 py-1 rounded-lg border font-medium transition-colors ${isDark ? 'border-white/20 text-slate-300 hover:bg-white/10' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>Edit</button>
              {onViewChart && <button onClick={() => onViewChart(patient)} className={`text-xs px-3 py-1 rounded-lg border font-medium transition-colors ${isDark ? 'border-white/20 text-slate-300 hover:bg-white/10' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>Chart</button>}
            </>
          )}
        </div>
      </div>

      {/* ── Demographics ── */}
      <div className={`px-5 py-4 border-b ${divider}`}>
        <p className={`${eyebrow} mb-3`}>
          Demographics{!isEditing && <span className={`ml-2 normal-case text-[10px] font-normal ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>read-only · press Edit to change</span>}
        </p>
        <div className="space-y-3">
          {/* Full Name */}
          <div>
            <p className={`${eyebrow} mb-1`}>Full name</p>
            {isEditing
              ? <input type="text" className={inputCls} value={draft.name} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} />
              : <p className={roText}>{patient?.name || '—'}</p>
            }
          </div>
          {/* Sex + Ethnicity */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className={`${eyebrow} mb-1`}>Sex</p>
              {isEditing
                ? <select className={selectCls} value={draft.gender} onChange={e => setDraft(d => ({ ...d, gender: e.target.value }))}>
                    <option value="">—</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                : <p className={roText}>{patient?.gender || '—'}</p>
              }
            </div>
            <div>
              <p className={`${eyebrow} mb-1`}>Ethnicity</p>
              {isEditing
                ? <select className={selectCls} value={draft.race} onChange={e => setDraft(d => ({ ...d, race: e.target.value }))}>
                    <option value="">—</option>
                    <option value="Malay">Malay</option>
                    <option value="Chinese">Chinese</option>
                    <option value="Indian">Indian</option>
                    <option value="Other">Other</option>
                  </select>
                : <p className={roText}>{mpisData?.race || '—'}</p>
              }
            </div>
          </div>
        </div>
      </div>

      {/* ── Known Allergies ── */}
      <div className={`px-5 py-4 border-b ${divider}`}>
        <p className={`${eyebrow} mb-2`}>
          Known allergies{isEditing && <span className={`ml-2 normal-case text-[10px] font-normal ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>click × to remove</span>}
        </p>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {(isEditing ? draft.allergies : (mpisData?.allergies || '').split(',').map(s => s.trim()).filter(Boolean)).map((a, idx) => (
            <span key={idx} className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${isDark ? 'bg-red-500/10 text-red-400 border-red-500/30' : 'bg-red-50 text-red-600 border-red-200'}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />{a}
              {isEditing && <button onClick={() => setDraft(d => ({ ...d, allergies: d.allergies.filter((_, i) => i !== idx) }))}><X className="w-3 h-3 ml-0.5 opacity-60 hover:opacity-100" strokeWidth={2} /></button>}
            </span>
          ))}
          {!isEditing && !(mpisData?.allergies) && <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No known allergies</p>}
        </div>
        {isEditing && (
          <>
            <input
              type="text" placeholder="Add another allergy…" className={inputCls}
              value={draft.allergyInput || ''}
              onChange={e => setDraft(d => ({ ...d, allergyInput: e.target.value }))}
              onKeyDown={e => {
                if (e.key === 'Enter' && draft.allergyInput?.trim()) {
                  setDraft(d => ({ ...d, allergies: [...d.allergies, d.allergyInput.trim()], allergyInput: '' }));
                }
              }}
            />
            <div className="flex gap-2 mt-2">
              {['NSAIDs', 'Sulfa', 'Latex', 'Aspirin'].map(s => (
                <button key={s} onClick={() => setDraft(d => ({ ...d, allergies: d.allergies.includes(s) ? d.allergies : [...d.allergies, s] }))}
                  className={`text-xs px-2 py-1 rounded-md border transition-colors ${isDark ? 'border-white/20 text-slate-400 hover:bg-white/10' : 'border-slate-200 text-slate-500 hover:bg-slate-50'}`}>
                  +{s}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── Comorbidities ── */}
      <div className={`px-5 py-4 border-b ${divider}`}>
        <p className={`${eyebrow} mb-2`}>
          Comorbidities{isEditing && <span className={`ml-2 normal-case text-[10px] font-normal ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>click × to remove</span>}
        </p>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {(isEditing ? draft.comorbidities : (mpisData?.comorbidities || [])).map((c, idx) => (
            <span key={idx} className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${isDark ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border-[var(--accent-primary)]/30' : 'bg-teal-50 text-teal-700 border-teal-200'}`}>
              {c}
              {isEditing && <button onClick={() => setDraft(d => ({ ...d, comorbidities: d.comorbidities.filter((_, i) => i !== idx) }))}><X className="w-3 h-3 ml-0.5 opacity-60 hover:opacity-100" strokeWidth={2} /></button>}
            </span>
          ))}
          {!isEditing && !(mpisData?.comorbidities?.length) && <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>None recorded</p>}
        </div>
        {isEditing && (
          <input
            type="text" placeholder="Add another condition…" className={inputCls}
            value={draft.conditionInput || ''}
            onChange={e => setDraft(d => ({ ...d, conditionInput: e.target.value }))}
            onKeyDown={e => {
              if (e.key === 'Enter' && draft.conditionInput?.trim()) {
                setDraft(d => ({ ...d, comorbidities: [...d.comorbidities, d.conditionInput.trim()], conditionInput: '' }));
              }
            }}
          />
        )}
      </div>

      {/* ── Current Medications ── */}
      <div className="px-5 py-4">
        <p className={`${eyebrow} mb-3`}>
          Current medications
          {(isEditing ? draft.currentMeds : mpisData?.currentMeds)?.length > 0 && (
            <span className="ml-1.5 normal-case font-normal">
              {(isEditing ? draft.currentMeds : mpisData?.currentMeds).length} active
            </span>
          )}
          {isEditing && <span className={`ml-2 normal-case text-[10px] font-normal ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>click row to edit/stop</span>}
        </p>
        <div className="space-y-1">
          {(isEditing ? draft.currentMeds : (mpisData?.currentMeds || [])).map((med, idx) => (
            <div key={idx} className={`flex items-center justify-between text-sm py-1.5 border-b last:border-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
              <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>
                {med.name}
                {isEditing && (
                  <>
                    <button onClick={() => {/* inline edit could be added */}} className={`ml-2 text-xs font-normal ${isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-400 hover:text-slate-600'}`}>edit</button>
                    <span className={isDark ? 'text-slate-700 mx-1' : 'text-slate-300 mx-1'}>·</span>
                    <button onClick={() => setDraft(d => ({ ...d, currentMeds: d.currentMeds.filter((_, i) => i !== idx) }))} className={`text-xs font-normal ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`}>stop</button>
                  </>
                )}
              </span>
              <span className={`ds-mono text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {[med.dose, med.frequency].filter(Boolean).join(' · ')}
              </span>
            </div>
          ))}
          {!isEditing && !(mpisData?.currentMeds?.length) && <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>None recorded</p>}
          {isEditing && (
            <input
              type="text" placeholder="Add medication — e.g. Atorvastatin 20mg OD" className={`${inputCls} mt-2`}
              value={draft.medInput || ''}
              onChange={e => setDraft(d => ({ ...d, medInput: e.target.value }))}
              onKeyDown={e => {
                if (e.key === 'Enter' && draft.medInput?.trim()) {
                  setDraft(d => ({ ...d, currentMeds: [...d.currentMeds, { name: d.medInput.trim(), dose: '', frequency: '' }], medInput: '' }));
                }
              }}
            />
          )}
        </div>
      </div>

      {/* ── Footer ── */}
      <div className={`flex items-center justify-between px-5 py-3 rounded-b-2xl text-xs border-t ${divider} ${isDark ? 'bg-white/3 text-slate-500' : 'bg-slate-50 text-slate-400'}`}>
        {isEditing ? (
          <>
            <span>{unsaved > 0 ? `${unsaved} unsaved change${unsaved > 1 ? 's' : ''}` : 'No changes yet'}</span>
            <div className="flex items-center gap-2">
              {saveError && <span className="text-red-500 mr-1">{saveError}</span>}
              <button onClick={cancelEdit} className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors ${isDark ? 'border-white/20 text-slate-300 hover:bg-white/10' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>Cancel</button>
              <button onClick={handleSave} disabled={isSaving} className="text-xs px-4 py-1.5 rounded-lg bg-teal-600 text-white font-medium hover:bg-teal-700 transition-colors disabled:opacity-60">
                {isSaving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </>
        ) : (
          <>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
              Up-to-date{savedTime ? ` · last saved ${savedTime}` : ''}
            </span>
            <span>Press Edit to change</span>
          </>
        )}
      </div>
    </GlassCard>
  );
}

// New Patient — same card structure as PatientInfoCard, always in "editing" state
function NewPatientForm({ nsn, onClear }) {
  const { isDark } = useTheme();
  const { state, dispatch } = useApp();
  const { patient, mpisData } = state;

  // ── local form state (mirrors PatientInfoCard draft shape) ──
  const [allergies, setAllergies] = React.useState([]);
  const [conditions, setConditions] = React.useState([]);
  const [meds, setMeds] = React.useState([]);
  const [allergyInput, setAllergyInput] = React.useState('');
  const [conditionInput, setConditionInput] = React.useState('');
  const [medInput, setMedInput] = React.useState('');

  // Sync tags/meds back to context so StatusStrip and handleAnalyze see them
  React.useEffect(() => {
    dispatch({
      type: 'SET_MPIS_DATA',
      payload: { ...mpisData, allergies: allergies.join(', ') || null, comorbidities: conditions, currentMeds: meds },
    });
  }, [allergies, conditions, meds]);

  // Parse NRIC → DOB + age + sex on mount
  React.useEffect(() => {
    if (!nsn || patient?.dob) return;
    const clean = nsn.replace(/-/g, '');
    if (clean.length !== 12) return;
    const yy = clean.slice(0, 2), mm = clean.slice(2, 4), dd = clean.slice(4, 6);
    const cy = new Date().getFullYear() % 100;
    const fullYear = (parseInt(yy) > cy ? '19' : '20') + yy;
    const dob = `${fullYear}-${mm}-${dd}`;
    const birth = new Date(dob);
    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    if (today.getMonth() < birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) age--;

    // Pre-fill the sex based on NRIC last digit: odd = Male, even = Female
    const lastDigit = parseInt(clean.slice(-1), 10);
    const gender = lastDigit % 2 === 1 ? 'Male' : 'Female';

    dispatch({ type: 'SET_PATIENT', payload: { nsn, dob, age, gender } });
  }, [nsn]);

  // Recalculate age when DOB changes
  React.useEffect(() => {
    if (!patient?.dob) return;
    const birth = new Date(patient.dob);
    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    if (today.getMonth() < birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) age--;
    if (age >= 0 && age !== patient?.age) dispatch({ type: 'SET_PATIENT', payload: { age } });
  }, [patient?.dob]);

  const setField = (field, value) => dispatch({ type: 'SET_PATIENT', payload: { [field]: value } });
  const setMpisField = (field, value) => dispatch({ type: 'SET_MPIS_DATA', payload: { ...mpisData, [field]: value } });

  const initials = patient?.name
    ? patient.name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
    : '?';

  const divider = `${isDark ? 'border-white/10' : 'border-slate-200'}`;
  const inputCls = `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/60 ${isDark ? 'bg-white/5 border-white/20 text-white placeholder-slate-500' : 'bg-white border-slate-300 text-slate-800 placeholder-slate-400'}`;
  const selectCls = `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/60 ${isDark ? 'bg-slate-800 border-white/20 text-white' : 'bg-white border-slate-300 text-slate-700'}`;
  const eyebrow = `text-[10px] font-semibold tracking-widest uppercase ${isDark ? 'text-slate-500' : 'text-slate-400'}`;

  return (
    <GlassCard className="overflow-hidden">
      {/* ── Header ── */}
      <div className={`flex items-start gap-3 px-5 pt-5 pb-4 border-b ${divider}`}>
        <div className={`w-10 h-10 rounded-full border-2 border-dashed flex items-center justify-center flex-shrink-0 mt-0.5 ${isDark ? 'border-white/20' : 'border-slate-300'}`}>
          <span className={`text-xs font-semibold ${patient?.name ? 'text-[var(--accent-primary)]' : (isDark ? 'text-slate-500' : 'text-slate-400')}`}>
            {patient?.name ? initials : 'NEW'}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-base font-semibold leading-tight ${patient?.name ? (isDark ? 'text-white' : 'text-slate-800') : (isDark ? 'text-slate-500' : 'text-slate-400')}`}>
            {patient?.name || 'New patient'}
          </p>
          <p className={`text-xs font-mono mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            {nsn || '—'}
            {patient?.age && <> · {patient.age} yrs</>}
            {patient?.gender && <> · {patient.gender === 'Male' ? 'M' : patient.gender === 'Female' ? 'F' : patient.gender}</>}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${isDark ? 'border-[var(--accent-primary)]/40 text-[var(--accent-primary)] bg-[var(--accent-primary)]/10' : 'border-teal-300 text-teal-700 bg-teal-50'}`}>
            New patient
          </span>
          <button onClick={onClear} className={`text-xs px-3 py-1 rounded-lg border font-medium transition-colors ${isDark ? 'border-white/20 text-slate-300 hover:bg-white/10' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>
            Clear
          </button>
        </div>
      </div>

      {/* ── Demographics ── */}
      <div className={`px-5 py-4 border-b ${divider}`}>
        <p className={`${eyebrow} mb-3`}>Demographics</p>
        <div className="space-y-3">
          <div>
            <p className={`${eyebrow} mb-1`}>Full name *</p>
            <input type="text" placeholder="Full name" className={inputCls}
              value={patient?.name || ''} onChange={e => setField('name', e.target.value)} />
          </div>
          <div>
            <p className={`${eyebrow} mb-1`}>Date of birth *</p>
            <input type="date" className={inputCls}
              value={patient?.dob || ''} onChange={e => setField('dob', e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className={`${eyebrow} mb-1`}>Sex *</p>
              <select className={selectCls} value={patient?.gender || ''} onChange={e => setField('gender', e.target.value)}>
                <option value="">—</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div>
              <p className={`${eyebrow} mb-1`}>Ethnicity</p>
              <select className={selectCls} value={mpisData?.race || ''} onChange={e => setMpisField('race', e.target.value)}>
                <option value="">—</option>
                <option value="Malay">Malay</option>
                <option value="Chinese">Chinese</option>
                <option value="Indian">Indian</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* ── Known Allergies ── */}
      <div className={`px-5 py-4 border-b ${divider}`}>
        <p className={`${eyebrow} mb-2`}>Known allergies <span className={`ml-1 normal-case text-[10px] font-normal ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>click × to remove</span></p>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {allergies.map((a, idx) => (
            <span key={idx} className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${isDark ? 'bg-red-500/10 text-red-400 border-red-500/30' : 'bg-red-50 text-red-600 border-red-200'}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />{a}
              <button onClick={() => setAllergies(p => p.filter((_, i) => i !== idx))}><X className="w-3 h-3 ml-0.5 opacity-60 hover:opacity-100" strokeWidth={2} /></button>
            </span>
          ))}
          {allergies.length === 0 && <p className={`text-sm ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>None recorded</p>}
        </div>
        <input type="text" placeholder="Add another allergy…" className={inputCls}
          value={allergyInput} onChange={e => setAllergyInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && allergyInput.trim()) { setAllergies(p => [...p, allergyInput.trim()]); setAllergyInput(''); } }} />
        <div className="flex gap-2 mt-2">
          {['NSAIDs', 'Sulfa', 'Latex', 'Aspirin'].map(s => (
            <button key={s} onClick={() => { if (!allergies.includes(s)) setAllergies(p => [...p, s]); }}
              className={`text-xs px-2 py-1 rounded-md border transition-colors ${isDark ? 'border-white/20 text-slate-400 hover:bg-white/10' : 'border-slate-200 text-slate-500 hover:bg-slate-50'}`}>
              +{s}
            </button>
          ))}
        </div>
      </div>

      {/* ── Comorbidities ── */}
      <div className={`px-5 py-4 border-b ${divider}`}>
        <p className={`${eyebrow} mb-2`}>Comorbidities <span className={`ml-1 normal-case text-[10px] font-normal ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>click × to remove</span></p>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {conditions.map((c, idx) => (
            <span key={idx} className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${isDark ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border-[var(--accent-primary)]/30' : 'bg-teal-50 text-teal-700 border-teal-200'}`}>
              {c}
              <button onClick={() => setConditions(p => p.filter((_, i) => i !== idx))}><X className="w-3 h-3 ml-0.5 opacity-60 hover:opacity-100" strokeWidth={2} /></button>
            </span>
          ))}
          {conditions.length === 0 && <p className={`text-sm ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>None recorded</p>}
        </div>
        <input type="text" placeholder="Add another condition…" className={inputCls}
          value={conditionInput} onChange={e => setConditionInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && conditionInput.trim()) { setConditions(p => [...p, conditionInput.trim()]); setConditionInput(''); } }} />
      </div>

      {/* ── Current Medications ── */}
      <div className="px-5 py-4">
        <p className={`${eyebrow} mb-3`}>
          Current medications{meds.length > 0 && <span className="ml-1.5 normal-case font-normal">{meds.length} active</span>}
        </p>
        <div className="space-y-1">
          {meds.map((med, idx) => (
            <div key={idx} className={`flex items-center justify-between text-sm py-1.5 border-b last:border-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
              <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>
                {med.name}
                <button onClick={() => setMeds(p => p.filter((_, i) => i !== idx))} className={`ml-2 text-xs font-normal ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`}>remove</button>
              </span>
              <span className={`ds-mono text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {[med.dose, med.frequency].filter(Boolean).join(' · ')}
              </span>
            </div>
          ))}
          {meds.length === 0 && <p className={`text-sm ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>None recorded</p>}
          <input type="text" placeholder="Add medication — e.g. Atorvastatin 20mg OD" className={`${inputCls} mt-2`}
            value={medInput} onChange={e => setMedInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && medInput.trim()) { setMeds(p => [...p, { name: medInput.trim(), dose: '', frequency: '' }]); setMedInput(''); } }} />
        </div>
      </div>

      {/* ── Footer ── */}
      <div className={`px-5 py-3 rounded-b-2xl text-xs border-t ${divider} ${isDark ? 'bg-white/3 text-slate-500' : 'bg-slate-50 text-slate-400'}`}>
        Patient record is created automatically when you continue.
      </div>
    </GlassCard>
  );
}

// ── Status strip + Analyze button ────────────────────────────────────────────
function StatusStrip({ mpisChecked, vitals, clinicalNotes, isDark, onAnalyze }) {
  const filledVitals = [
    vitals.bpSystolic && vitals.bpDiastolic,
    vitals.hr, vitals.temp, vitals.rr, vitals.spo2, vitals.weight, vitals.height,
  ].filter(Boolean).length;
  const totalVitals = 7; // BP counts as 1

  const missingVitals = [];
  if (!vitals.bpSystolic || !vitals.bpDiastolic) missingVitals.push('BP');
  if (!vitals.hr)     missingVitals.push('Heart Rate');
  if (!vitals.rr)     missingVitals.push('RR');
  if (!vitals.temp)   missingVitals.push('Temperature');
  if (!vitals.spo2)   missingVitals.push('SpO₂');
  if (!vitals.weight) missingVitals.push('Weight');
  if (!vitals.height) missingVitals.push('Height');

  const hasMissingVitals = missingVitals.length > 0;
  const hasNotes = clinicalNotes?.trim().length > 0;

  const checks = [
    { label: 'Patient', ok: mpisChecked },
    { label: `Vitals · ${filledVitals} of ${totalVitals}`, ok: !hasMissingVitals },
    { label: hasNotes ? 'Notes · saved' : 'Notes', ok: hasNotes },
    { label: 'Staging · optional', ok: null }, // always neutral
  ];

  return (
    <div className="space-y-2 pt-2">
      {/* Strip card */}
      <div className={`flex items-center gap-1 rounded-2xl border px-4 py-3 ${isDark ? 'bg-white/5 border-white/10' : 'bg-white border-slate-200'}`}>
        {/* Dot checks */}
        <div className="flex items-center gap-4 flex-1 flex-wrap">
          {checks.map((c) => (
            <span key={c.label} className={`flex items-center gap-1.5 text-sm ${
              c.ok === null
                ? (isDark ? 'text-slate-500' : 'text-slate-400')
                : c.ok
                  ? (isDark ? 'text-slate-200' : 'text-slate-700')
                  : (isDark ? 'text-slate-400' : 'text-slate-500')
            }`}>
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                c.ok === null ? (isDark ? 'bg-slate-600' : 'bg-slate-300')
                : c.ok ? 'bg-emerald-500'
                : (isDark ? 'bg-slate-600' : 'bg-slate-300')
              }`} />
              {c.label}
            </span>
          ))}
        </div>

        {/* Analyze button — never disabled */}
        <button
          onClick={onAnalyze}
          className="ml-4 flex-shrink-0 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700 active:scale-[0.98] transition-all focus:outline-none focus:ring-2 focus:ring-teal-500/50"
        >
          Analyze assessment →
        </button>
      </div>

      {/* Thin inline hint when vitals are missing */}
      {hasMissingVitals && (
        <div className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm ${isDark ? 'bg-amber-500/5 border-amber-500/20 text-slate-300' : 'bg-white border-slate-200 text-slate-600'}`}>
          <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
          <span>
            Missing:{' '}
            {missingVitals.map((v, i) => (
              <React.Fragment key={v}>
                <strong>{v}</strong>
                {i < missingVitals.length - 1 && <span className={isDark ? 'text-slate-500' : 'text-slate-400'}> , </span>}
              </React.Fragment>
            ))}
            {'. '}
            <span className={isDark ? 'text-slate-400' : 'text-slate-400'}>Fill or click "Analyze anyway".</span>
          </span>
        </div>
      )}
    </div>
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



  const handleAnalyze = async () => {

    // For new patients: register to Supabase implicitly before analyzing
    if (!mpisFound && patient?.name && patient?.dob && patient?.gender) {
      try {
        const { registerPatient, updatePatientFromMPIS } = await import('../../lib/supabase');
        const nric = patient.nsn || nsn;
        const result = await registerPatient({
          nric,
          fullName: patient.name,
          dateOfBirth: patient.dob,
          gender: patient.gender,
          race: mpisData?.race || null,
          allergies: mpisData?.allergies || null,
          comorbidities: mpisData?.comorbidities || null,
        });
        if (!result.error && mpisData?.currentMeds?.length > 0) {
          await updatePatientFromMPIS(nric, {
            allergies: mpisData?.allergies || null,
            comorbidities: mpisData?.comorbidities || null,
            currentMeds: mpisData.currentMeds,
          });
        }
      } catch (_) {}
    }

    if (mpisFound) {
      await saveVitalsToDB();
    }
    analyzeAssessment();
  };

  // Show pipeline progress when analyzing
  if (isAnalyzing) {
    return (
      <div className="space-y-6 animate-fadeIn">
        <PipelineProgress
          pipelineEvents={state.pipelineEvents}
          pipelineThinking={state.pipelineThinking}
          summary={state.pipelineSummary}
          isLive={true}
        />
      </div>
    );
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

  // Skip lookup and go straight to registering a new patient
  const handleStartNewPatient = () => {
    setNricError('');
    setMpisChecked(true);
    setMpisFound(false);
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
      <div className="mb-6">
        <span className="ds-eyebrow">STEP 1 OF 4</span>
        <h2 className={`text-xl font-semibold tracking-tight mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
          Clinical Assessment Input
        </h2>
        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Confirm patient details and capture vitals and clinical notes.
        </p>
      </div>

      <div className={`grid grid-cols-1 ${mpisChecked ? 'xl:grid-cols-12' : ''} gap-6`}>
        {/* LEFT COLUMN: Patient Context */}
        <div className={mpisChecked ? 'xl:col-span-5 space-y-6' : 'max-w-2xl mx-auto w-full'}>
          {/* Step 1: NRIC Input — centered hero before a patient is loaded */}
          {!mpisChecked && (
            <div className="min-h-[58vh] flex flex-col items-center justify-center space-y-8">
              {/* Lookup card */}
              <GlassCard className="p-6 w-full">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
                    <Database className="w-5 h-5 text-[var(--accent-primary)]" strokeWidth={1.5} />
                  </div>
                  <div>
                    <h3 className={`text-xl font-semibold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
                      Patient Lookup
                    </h3>
                  </div>
                </div>

              <div className="flex flex-col sm:flex-row gap-4 items-stretch sm:items-end">
                <div className="flex-1">
                  <input
                    id="nsn-input"
                    name="nric"
                    type="text"
                    autoComplete="off"
                    spellCheck={false}
                    className={`w-full px-4 py-3 rounded-xl border-2 text-lg ${nricError
                      ? 'border-red-500 focus-visible:border-red-500 focus-visible:ring-red-500/20'
                      : isDark
                        ? 'bg-slate-800/50 border-white/20 text-white placeholder-slate-500 focus-visible:border-[var(--accent-primary)] focus-visible:ring-[var(--accent-primary)]/20'
                        : 'bg-white/60 border-slate-300 text-slate-800 placeholder-slate-400 focus-visible:border-[var(--accent-primary)] focus-visible:ring-[var(--accent-primary)]/20'
                      } ${isDark ? 'bg-slate-800/50 text-white placeholder-slate-500' : 'bg-white/60 text-slate-800 placeholder-slate-400'} focus:outline-none focus-visible:ring-4 transition-colors`}
                    value={nsn}
                    onChange={handleNricChange}
                    onKeyDown={e => e.key === 'Enter' && handleCheckNRIC()}
                    placeholder="e.g., 580315-08-1234…"
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
                </div>
                <Button
                  variant="primary"
                  size="lg"
                  onClick={handleCheckNRIC}
                  loading={mpisLoading}
                  disabled={!nsn.trim() || mpisLoading}
                  className="min-w-[160px]"
                >
                  {mpisLoading ? 'Searching...' : 'Continue →'}
                </Button>
              </div>

              {/* Secondary: register a new patient without a lookup */}
              <div className={`mt-5 pt-5 border-t flex items-center justify-between gap-3 flex-wrap ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>No NRIC on file?</span>
                <button
                  type="button"
                  onClick={handleStartNewPatient}
                  className="inline-flex items-center gap-2 text-sm font-medium text-[var(--accent-primary)] hover:underline"
                >
                  <UserPlus className="w-4 h-4" strokeWidth={1.5} />
                  Register a New Patient
                </button>
              </div>
              </GlassCard>

            </div>
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
              />
            )
          )}
        </div>

        {/* RIGHT COLUMN: Action & Input */}
        {mpisChecked && (
          <div className="xl:col-span-7 space-y-6">
            <VitalsGrid />
            <SeverityStagingGrid />
            <ClinicalNotes
            />

            {/* Status strip + Analyze */}
            <StatusStrip
              mpisChecked={mpisChecked}
              vitals={vitals}
              clinicalNotes={clinicalNotes}
              isDark={isDark}
              onAnalyze={handleAnalyze}
            />
          </div>
        )}
      </div>

      {/* Chart Modal */}
      <ChartModal
        patient={patient}
        isOpen={isChartModalOpen}
        onClose={() => setIsChartModalOpen(false)}
      />
    </div>
  );
}
