import React, { useMemo } from 'react';
import { Activity, Heart, Thermometer, Wind, Droplets, Scale, Ruler, Zap } from 'lucide-react';
import { GlassCard, Input, Badge } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';

export function VitalsGrid() {
  const { state, dispatch, calculateBMI } = useApp();
  const { isDark } = useTheme();
  const { vitals } = state;

  const handleChange = (field, value) => {
    dispatch({ type: 'SET_VITALS', payload: { [field]: value } });
  };

  const bmi = useMemo(() => calculateBMI(), [vitals.weight, vitals.height]);

  const getBMICategory = (bmi) => {
    if (!bmi) return null;
    const bmiValue = parseFloat(bmi);
    if (bmiValue < 18.5) return { label: 'Underweight', variant: 'warning' };
    if (bmiValue < 25) return { label: 'Normal', variant: 'success' };
    if (bmiValue < 30) return { label: 'Overweight', variant: 'warning' };
    return { label: 'Obese', variant: 'danger' };
  };

  const bmiCategory = getBMICategory(bmi);

  const vitalFields = [
    {
      id: 'bp',
      label: 'Blood Pressure',
      icon: Heart,
      unit: 'mmHg',
      dual: true,
      fields: [
        { key: 'bpSystolic', placeholder: 'Sys' },
        { key: 'bpDiastolic', placeholder: 'Dia' },
      ],
    },
    {
      id: 'hr',
      label: 'Heart Rate',
      icon: Activity,
      unit: 'bpm',
      key: 'hr',
      placeholder: 'HR',
    },
    {
      id: 'temp',
      label: 'Temperature',
      icon: Thermometer,
      unit: '°C',
      key: 'temp',
      placeholder: 'Temp',
      step: '0.1',
    },
    {
      id: 'rr',
      label: 'Respiratory Rate',
      icon: Wind,
      unit: '/min',
      key: 'rr',
      placeholder: 'RR',
    },
    {
      id: 'spo2',
      label: 'SpO2',
      icon: Droplets,
      unit: '%',
      key: 'spo2',
      placeholder: 'SpO2',
    },
    {
      id: 'weight',
      label: 'Weight',
      icon: Scale,
      unit: 'kg',
      key: 'weight',
      placeholder: 'Weight',
      step: '0.1',
    },
    {
      id: 'height',
      label: 'Height',
      icon: Ruler,
      unit: 'cm',
      key: 'height',
      placeholder: 'Height',
    },
  ];

  const handleDemoFill = () => {
    dispatch({
      type: 'SET_VITALS',
      payload: {
        bpSystolic: '120',
        bpDiastolic: '80',
        hr: '72',
        temp: '36.8',
        rr: '14',
        spo2: '99',
        weight: '70',
        height: '170'
      }
    });
  };

  return (
    <GlassCard className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
            <Activity className="w-5 h-5 text-[var(--accent-primary)]" />
          </div>
          <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Vital Signs</h3>
        </div>
        <button
          onClick={handleDemoFill}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
            ${isDark
              ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30'
              : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
            }`}
          title="Fill with demo data"
        >
          <Zap className="w-4 h-4" />
          Demo Fill
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {vitalFields.map((vital) => (
          <div key={vital.id} className="space-y-1">
            <label className={`flex items-center gap-1.5 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <vital.icon className="w-4 h-4 text-[var(--accent-primary)]" />
              {vital.label}
            </label>
            {vital.dual ? (
              <div className="flex items-center gap-1">
                {vital.fields.map((field, idx) => (
                  <React.Fragment key={field.key}>
                    <input
                      type="number"
                      placeholder={field.placeholder}
                      value={vitals[field.key] || ''}
                      onChange={(e) => handleChange(field.key, e.target.value)}
                      className={`w-full px-3 py-2 backdrop-blur-sm border rounded-lg text-sm
                        ${isDark 
                          ? 'bg-white/10 border-white/20 text-white placeholder-slate-400' 
                          : 'bg-white/80 border-slate-300 text-slate-800 placeholder-slate-400'
                        } focus:ring-2 focus:ring-[var(--accent-primary)]/50`}
                    />
                    {idx === 0 && <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>/</span>}
                  </React.Fragment>
                ))}
              </div>
            ) : (
              <div className="relative">
                <input
                  type="number"
                  step={vital.step || '1'}
                  placeholder={vital.placeholder}
                  value={vitals[vital.key] || ''}
                  onChange={(e) => handleChange(vital.key, e.target.value)}
                  className={`w-full px-3 py-2 backdrop-blur-sm border rounded-lg text-sm
                    ${isDark 
                      ? 'bg-white/10 border-white/20 text-white placeholder-slate-400' 
                      : 'bg-white/80 border-slate-300 text-slate-800 placeholder-slate-400'
                    } focus:ring-2 focus:ring-[var(--accent-primary)]/50`}
                />
                <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {vital.unit}
                </span>
              </div>
            )}
          </div>
        ))}

        {/* BMI Display */}
        <div className="space-y-1">
          <label className={`flex items-center gap-1.5 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            <Scale className="w-4 h-4 text-[var(--accent-primary)]" />
            BMI (Calculated)
          </label>
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${isDark ? 'bg-[var(--accent-primary)]/20' : 'bg-[var(--accent-primary)]/10'}`}>
            <span className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>
              {bmi || '--'}
            </span>
            {bmiCategory && (
              <Badge variant={bmiCategory.variant} size="sm">
                {bmiCategory.label}
              </Badge>
            )}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
