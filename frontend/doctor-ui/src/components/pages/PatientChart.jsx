import React, { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';
import { GlassCard, GlassPanel, Button } from '../shared';
import { VitalsLineChart } from '../shared/VitalsLineChart';
import { useTheme } from '../../context/ThemeContext';
import { useApp } from '../../context/AppContext';
import { getPatientVitalsHistory } from '../../lib/supabase';

// Tab configuration for vital signs. Every metric key here maps to a real
// `live_vitals` column (sbp/dbp/hr/spo2/rr/temp) so each tab plots live data.
const vitalsTabs = [
    {
        id: 'bloodPressure',
        label: 'Blood Pressure',
        metrics: [
            { key: 'bpSystolic', label: 'Systolic', unit: 'mmHg', color: 'var(--accent-primary)' },
            { key: 'bpDiastolic', label: 'Diastolic', unit: 'mmHg', color: '#94a3b8', dashed: true },
        ]
    },
    {
        id: 'heartRate',
        label: 'Heart Rate',
        metrics: [
            { key: 'hr', label: 'Heart Rate', unit: 'bpm', color: 'var(--accent-primary)' },
        ]
    },
    {
        id: 'oxygenation',
        label: 'SpO2',
        metrics: [
            { key: 'spo2', label: 'Oxygen Saturation', unit: '%', color: 'var(--accent-primary)' },
        ]
    },
    {
        id: 'respiratoryRate',
        label: 'Resp. Rate',
        metrics: [
            { key: 'rr', label: 'Respiratory Rate', unit: '/min', color: 'var(--accent-primary)' },
        ]
    },
    {
        id: 'temperature',
        label: 'Temperature',
        metrics: [
            { key: 'temp', label: 'Temperature', unit: '°C', color: 'var(--accent-primary)' },
        ]
    },
];

function PatientChart({ patient, onBack }) {
    const { isDark } = useTheme();
    const [activeTab, setActiveTab] = useState('bloodPressure');
    const [vitalsData, setVitalsData] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    // Get MPIS data for this patient if available
    const patientNric = patient?.nsn || patient?.nric;

    // Auto-load historical data on mount. Vitals are reconstructed from the
    // `live_vitals` table (one row per consultation) — NOT from a non-existent
    // patients.vitals_history column, which is why the chart used to be empty.
    useEffect(() => {
        if (!patientNric) { setVitalsData([]); setIsLoading(false); return; }

        let cancelled = false;
        const loadData = async () => {
            setIsLoading(true);
            const { vitals } = await getPatientVitalsHistory(patientNric);
            if (!cancelled) {
                setVitalsData(vitals || []);
                setIsLoading(false);
            }
        };

        loadData();
        return () => { cancelled = true; };
    }, [patientNric]);


    const currentTabConfig = vitalsTabs.find(t => t.id === activeTab);
    const initials = (patient?.name || '??').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

    // Aligned & Dynamic: Get current vitals from AppContext if this is the active patient
    const { state } = useApp();
    const isCurrentPatient = state.patient.nsn === patientNric;

    let historyToDisplay = [...vitalsData];
    if (isCurrentPatient && (state.vitals.bpSystolic || state.vitals.hr)) {
        const currentEntry = {
            date: 'Current',
            bpSystolic: parseInt(state.vitals.bpSystolic) || 0,
            bpDiastolic: parseInt(state.vitals.bpDiastolic) || 0,
            hr: parseInt(state.vitals.hr) || 0,
            temp: parseFloat(state.vitals.temp) || 0,
            spo2: parseInt(state.vitals.spo2) || 0,
            rr: parseInt(state.vitals.rr) || 0,
        };
        historyToDisplay.push(currentEntry);
    }

    const latestVitals = historyToDisplay.length > 0 ? historyToDisplay[historyToDisplay.length - 1] : null;

    // Use historyToDisplay instead of vitalsData for stats and chart

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="sm" icon={ArrowLeft} onClick={onBack}>
                    Back
                </Button>
                <div>
                    <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                        Patient Vital Chart
                    </h1>
                </div>
            </div>

            {/* 2-row × 3-col grid:
                Row 1 — patient banner (1 col) aligns level + height with the
                        parameter switcher tabs (2 cols).
                Row 2 — metric stat cards (1 col) align height with the trend graph
                        (2 cols). Grid row stretch keeps each pair the same height. */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Row 1 · Patient banner — same width as the stat cards below it */}
                <GlassCard className="lg:col-span-1 p-3.5 flex items-center">
                    <div className="flex items-center gap-3 min-w-0">
                        <div className="w-11 h-11 rounded-xl flex items-center justify-center bg-[var(--accent-primary)]/15 flex-shrink-0">
                            <span className="text-base font-bold text-[var(--accent-primary)]">{initials}</span>
                        </div>
                        <div className="min-w-0">
                            <h2 className={`text-base font-bold leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                {patient?.name || 'Unknown Patient'}
                            </h2>
                            <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                <code className="ds-mono not-italic">{patientNric || 'N/A'}</code>
                                {' • '}{patient?.age || 'N/A'} yrs
                                {' • '}{patient?.gender ? patient.gender.charAt(0).toUpperCase() + patient.gender.slice(1) : 'N/A'}
                            </p>
                        </div>
                    </div>
                </GlassCard>

                {/* Row 1 · Parameter switcher — full-width bar, level + height with banner */}
                <GlassCard className="lg:col-span-2 p-2 flex items-center">
                    <div className="flex w-full gap-1">
                        {vitalsTabs.map((tab) => {
                            const isActive = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${isActive
                                        ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]'
                                        : (isDark ? 'text-slate-400 hover:bg-white/5' : 'text-slate-500 hover:bg-slate-100')
                                        }`}
                                >
                                    {tab.label}
                                </button>
                            );
                        })}
                    </div>
                </GlassCard>

                {/* Row 2 · Metric stat cards — natural size */}
                <div className="lg:col-span-1 space-y-4">
                    {isLoading ? (
                        <GlassCard className="p-4 h-32 flex items-center justify-center">
                            <div className="animate-spin rounded-full h-6 w-6 border-2 border-[var(--accent-primary)] border-t-transparent" />
                        </GlassCard>
                    ) : (latestVitals && currentTabConfig) ? (
                        currentTabConfig.metrics.map((metric) => {
                            const values = historyToDisplay.map(d => d[metric.key]).filter(v => v !== undefined && !isNaN(v));
                            const latest = latestVitals[metric.key];
                            const min = values.length > 0 ? Math.min(...values) : null;
                            const max = values.length > 0 ? Math.max(...values) : null;
                            const avg = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
                            const fmt = (v) => (v != null ? v.toFixed(metric.key === 'temp' ? 1 : 0) : '-');

                            return (
                                <GlassCard key={metric.key} className="p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <h4 className={`text-sm font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                                            {metric.label}
                                        </h4>
                                        <span className={`text-[10px] font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{metric.unit}</span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-y-3 gap-x-2">
                                        <div>
                                            <div className={`text-[10px] uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Latest</div>
                                            <div className="text-2xl font-bold leading-tight" style={{ color: metric.color }}>{fmt(latest)}</div>
                                        </div>
                                        <div>
                                            <div className={`text-[10px] uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Average</div>
                                            <div className={`text-2xl font-bold leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>{fmt(avg)}</div>
                                        </div>
                                        <div>
                                            <div className={`text-[10px] uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Min</div>
                                            <div className="text-2xl font-bold leading-tight text-emerald-500">{fmt(min)}</div>
                                        </div>
                                        <div>
                                            <div className={`text-[10px] uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Max</div>
                                            <div className="text-2xl font-bold leading-tight text-red-500">{fmt(max)}</div>
                                        </div>
                                    </div>
                                </GlassCard>
                            );
                        })
                    ) : (
                        <GlassCard className="p-4">
                            <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>No vital signs data available</p>
                        </GlassCard>
                    )}
                </div>

                {/* Row 2 · Trend graph */}
                <GlassPanel className="lg:col-span-2 p-5">
                    <div className="mb-4">
                        <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                            {currentTabConfig?.label} Trends
                        </h3>
                        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                            {isLoading
                                ? 'Loading historical data...'
                                : `${historyToDisplay.length} data point${historyToDisplay.length === 1 ? '' : 's'}`
                            }
                        </p>
                    </div>

                    {isLoading ? (
                        <div className="flex items-center justify-center h-64">
                            <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--accent-primary)] border-t-transparent" />
                        </div>
                    ) : (
                        <VitalsLineChart
                            data={historyToDisplay}
                            metrics={currentTabConfig?.metrics || []}
                            height={300}
                        />
                    )}
                </GlassPanel>
            </div>
        </div>
    );
}

export default PatientChart;
