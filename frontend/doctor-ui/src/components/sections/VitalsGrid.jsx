import React, { useMemo, useState } from 'react';
import { Scan } from 'lucide-react';
import { GlassCard, Badge } from '../shared';
import { RPPGScanModal } from '../shared/RPPGScanModal';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { sampleVitals } from '../../data/sampleData';

const GROUPS = [
  {
    id: 'haemo',
    label: 'Haemodynamic',
    cols: 'grid-cols-2',
    fields: [
      {
        id: 'bp', label: 'Blood Pressure (mmHg)', dual: true,
        fields: [
          { key: 'bpSystolic', placeholder: '—' },
          { key: 'bpDiastolic', placeholder: '—' },
        ],
      },
      { id: 'hr', label: 'Heart Rate (bpm)', key: 'hr', placeholder: '—' },
    ],
  },
  {
    id: 'resp',
    label: 'Respiratory',
    cols: 'grid-cols-3',
    fields: [
      { id: 'rr',   label: 'RR (/min)',  key: 'rr',   placeholder: '—' },
      { id: 'spo2', label: 'SpO₂ (%)',   key: 'spo2', placeholder: '—' },
      { id: 'temp', label: 'Temp (°C)',  key: 'temp', placeholder: '—', step: '0.1' },
    ],
  },
  {
    id: 'anthro',
    label: 'Anthropometry',
    cols: 'grid-cols-3',
    fields: [
      { id: 'weight', label: 'Weight (kg)', key: 'weight', placeholder: '—', step: '0.1' },
      { id: 'height', label: 'Height (cm)', key: 'height', placeholder: '—' },
      { id: 'bmi',    label: 'BMI',         bmiDisplay: true },
    ],
  },
];

const inputCls = (isDark) =>
  `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 ${
    isDark
      ? 'bg-white/10 border-white/20 text-white placeholder-slate-500'
      : 'bg-white border-slate-300 text-slate-800 placeholder-slate-400'
  }`;

export function VitalsGrid() {
  const { state, dispatch, calculateBMI } = useApp();
  const { isDark } = useTheme();
  const { vitals } = state;
  const [showScanner, setShowScanner] = useState(false);

  const handleChange = (field, value) =>
    dispatch({ type: 'SET_VITALS', payload: { [field]: value } });

  const bmi = useMemo(() => calculateBMI(), [vitals.weight, vitals.height]);

  const getBMICategory = (bmi) => {
    if (!bmi) return null;
    const v = parseFloat(bmi);
    if (v < 18.5) return { label: 'Under', variant: 'warning' };
    if (v < 25)   return { label: 'Normal', variant: 'success' };
    if (v < 30)   return { label: 'Over',   variant: 'warning' };
    return           { label: 'Obese',  variant: 'danger' };
  };

  const bmiCategory = getBMICategory(bmi);

  const handleDemoFill = () =>
    // EVALUATION_FRAMEWORK_README.md Case 08 vitals: BP 128/76 · HR 82 · SpO2 97
    // · Weight 98 · Height 175 · Temp 36.8 (BMI 32.0 → Obesity).
    dispatch({
      type: 'SET_VITALS',
      payload: {
        bpSystolic: String(sampleVitals.bpSystolic),
        bpDiastolic: String(sampleVitals.bpDiastolic),
        hr: String(sampleVitals.hr),
        temp: String(sampleVitals.temp),
        rr: String(sampleVitals.rr),
        spo2: String(sampleVitals.spo2),
        weight: String(sampleVitals.weight),
        height: String(sampleVitals.height),
      },
    });

  const divider = (
    <div className={`h-px w-full my-3 ${isDark ? 'bg-white/10' : 'bg-slate-200'}`} />
  );

  return (
    <>
      {showScanner && <RPPGScanModal onClose={() => setShowScanner(false)} />}
      <GlassCard className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-1">
          <div>
            <h3 className={`text-lg font-semibold tracking-tight leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
              Vital signs
            </h3>
            <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              8 measurements · BMI auto-calculated
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* rPPG — primary teal */}
            <button
              onClick={() => setShowScanner(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-teal-600 text-white hover:bg-teal-700 transition-colors"
            >
              <Scan className="w-4 h-4" strokeWidth={1.5} />
              rPPG scan
            </button>
            {/* Sample data — ghost */}
            <button
              onClick={handleDemoFill}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                isDark
                  ? 'border-white/20 text-slate-400 hover:bg-white/10'
                  : 'border-slate-300 text-slate-500 hover:bg-slate-50'
              }`}
              title="Fill with sample data"
            >
              Sample data
            </button>
          </div>
        </div>

        {/* Groups */}
        {GROUPS.map((group, gi) => (
          <React.Fragment key={group.id}>
            {/* Group divider + label */}
            <div className="flex items-center gap-3 mt-4 mb-3">
              <span className={`text-[10px] font-semibold tracking-widest uppercase ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                {group.label}
              </span>
              <div className={`flex-1 h-px ${isDark ? 'bg-white/10' : 'bg-slate-200'}`} />
            </div>

            <div className={`grid ${group.cols} gap-4`}>
              {group.fields.map((vital) => {
                // BMI display cell
                if (vital.bmiDisplay) {
                  return (
                    <div key="bmi" className="space-y-1">
                      <label className={`block text-[10px] font-semibold tracking-widest uppercase ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        BMI
                      </label>
                      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${isDark ? 'bg-[var(--accent-primary)]/15 border border-[var(--accent-primary)]/20' : 'bg-teal-50 border border-teal-200'}`}>
                        <span className={`text-sm font-semibold ds-numeric ${isDark ? 'text-white' : 'text-slate-800'}`}>
                          {bmi || '—'}
                        </span>
                        {bmiCategory && (
                          <span className={`text-xs font-medium ${
                            bmiCategory.variant === 'success' ? (isDark ? 'text-emerald-400' : 'text-emerald-600') :
                            bmiCategory.variant === 'danger'  ? (isDark ? 'text-red-400'     : 'text-red-600')     :
                                                                (isDark ? 'text-amber-400'   : 'text-amber-600')
                          }`}>
                            {bmiCategory.label}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                }

                return (
                  <div key={vital.id} className="space-y-1">
                    <label className={`block text-[10px] font-semibold tracking-widest uppercase ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      {vital.label}
                    </label>
                    {vital.dual ? (
                      <div className="flex items-center gap-1.5">
                        {vital.fields.map((f, idx) => (
                          <React.Fragment key={f.key}>
                            <input
                              type="number"
                              placeholder={f.placeholder}
                              value={vitals[f.key] || ''}
                              onChange={(e) => handleChange(f.key, e.target.value)}
                              className={inputCls(isDark)}
                            />
                            {idx === 0 && (
                              <span className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>/</span>
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    ) : (
                      <input
                        type="number"
                        step={vital.step || '1'}
                        placeholder={vital.placeholder}
                        value={vitals[vital.key] || ''}
                        onChange={(e) => handleChange(vital.key, e.target.value)}
                        className={inputCls(isDark)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </React.Fragment>
        ))}
      </GlassCard>
    </>
  );
}
