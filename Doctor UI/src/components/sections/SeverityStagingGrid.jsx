import React, { useMemo } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { GlassCard } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';

// CKD-EPI 2021 (race-free) — requires serum creatinine (mg/dL), age, sex
function calcEGFR(creatinine, age, sex) {
  if (!creatinine || !age || !sex) return null;
  const scr = parseFloat(creatinine);
  const a = parseInt(age);
  if (isNaN(scr) || isNaN(a) || scr <= 0 || a <= 0) return null;

  const isFemale = sex === 'F' || sex === 'Female';
  const kappa = isFemale ? 0.7 : 0.9;
  const alpha = isFemale ? -0.241 : -0.302;
  const sexFactor = isFemale ? 1.012 : 1.0;

  const ratio = scr / kappa;
  const eGFR =
    142 *
    Math.pow(Math.min(ratio, 1), alpha) *
    Math.pow(Math.max(ratio, 1), -1.2) *
    Math.pow(0.9938, a) *
    sexFactor;

  return Math.round(eGFR);
}

const stagingFields = [
  {
    key: 'NYHA',
    label: 'NYHA Class',
    type: 'select',
    options: ['I', 'II', 'III', 'IV'],
  },
  {
    key: 'WHO_FC',
    label: 'WHO Functional Class (PAH)',
    type: 'select',
    options: ['I', 'II', 'III', 'IV'],
  },
  {
    key: 'WHO_pregnancy_class',
    label: 'WHO Pregnancy Risk Class (mWHO)',
    type: 'select',
    options: ['I', 'II', 'II-III', 'III', 'IV'],
  },
  {
    key: 'CKD_stage',
    label: 'CKD Stage',
    type: 'select',
    options: ['1', '2', '3a', '3b', '4', '5'],
  },
  {
    key: 'HbA1c',
    label: 'HbA1c %',
    type: 'text',
    placeholder: '9.2',
  },
  {
    key: 'LVEF',
    label: 'LVEF %',
    type: 'text',
    placeholder: '35',
  },
  {
    key: 'eGFR',
    label: 'eGFR',
    type: 'text',
    placeholder: '42',
  },
];

export function SeverityStagingGrid() {
  const { state, dispatch } = useApp();
  const { isDark } = useTheme();
  const [expanded, setExpanded] = React.useState(false);

  const severityStaging = state.severityStaging || {};
  const { vitals, patient } = state;

  // Auto-calculate eGFR from creatinine in vitals (if present)
  const autoEGFR = useMemo(() => {
    const creatinine = vitals?.creatinine;
    if (!creatinine) return null;
    return calcEGFR(creatinine, patient?.age, patient?.gender || state.patient?.sex);
  }, [vitals?.creatinine, patient?.age, patient?.gender, state.patient?.sex]);

  const isAutoEGFR =
    autoEGFR !== null && !severityStaging.eGFR;

  const handleChange = (key, value) => {
    const updated = { ...severityStaging };
    if (value === '' || value === null) {
      delete updated[key];
    } else {
      updated[key] = value;
    }
    dispatch({ type: 'SET_SEVERITY_STAGING', payload: updated });
  };

  const filledCount = Object.keys(severityStaging).length + (isAutoEGFR ? 1 : 0);

  const inputClass = (isDark) =>
    `w-full px-3 py-2 backdrop-blur-sm border rounded-lg text-sm focus:ring-2 focus:ring-[var(--accent-primary)]/50 ${
      isDark
        ? 'bg-white/10 border-white/20 text-white placeholder-slate-400'
        : 'bg-white/80 border-slate-300 text-slate-800 placeholder-slate-400'
    }`;

  return (
    <GlassCard className="p-5">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between"
        type="button"
      >
        <div className="text-left">
          <p className={`text-[10px] font-semibold tracking-widest uppercase mb-0.5 ${isDark ? 'text-violet-400' : 'text-violet-600'}`}>Staging</p>
          <h3 className={`text-xl font-semibold tracking-tight leading-none ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Severity Staging
          </h3>
          <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            {filledCount > 0
              ? `${filledCount} field${filledCount > 1 ? 's' : ''} entered`
              : 'Optional — improves CPG query precision'}
          </p>
        </div>
        <div className={`p-1.5 rounded-lg ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-100'}`}>
          {expanded
            ? <ChevronUp className={`w-5 h-5 ${isDark ? 'text-slate-300' : 'text-slate-600'}`} />
            : <ChevronDown className={`w-5 h-5 ${isDark ? 'text-slate-300' : 'text-slate-600'}`} />
          }
        </div>
      </button>

      {expanded && (
        <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-4">
          {stagingFields.map((field) => {
            const isEGFR = field.key === 'eGFR';
            const displayValue = isEGFR && isAutoEGFR
              ? String(autoEGFR)
              : severityStaging[field.key] || '';

            return (
              <div key={field.key} className="space-y-1">
                <label
                  className={`flex items-center gap-1 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}
                >
                  {field.label}
                  {isEGFR && isAutoEGFR && (
                    <span className={`text-xs font-normal ml-1 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                      (auto)
                    </span>
                  )}
                </label>

                {field.type === 'select' ? (
                  <select
                    value={severityStaging[field.key] || ''}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    className={inputClass(isDark)}
                  >
                    <option value="">—</option>
                    {field.options.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    placeholder={isEGFR && isAutoEGFR ? String(autoEGFR) : field.placeholder}
                    value={severityStaging[field.key] || ''}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    className={inputClass(isDark)}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </GlassCard>
  );
}
