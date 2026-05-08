import React, { useState, useEffect } from 'react';
import { ArrowLeft, User, Heart, Activity, Thermometer, Wind, Scale, Droplets } from 'lucide-react';
import { GlassCard, GlassPanel, Button, Badge } from '../shared';
import { VitalsLineChart } from '../shared/VitalsLineChart';
import { useTheme } from '../../context/ThemeContext';
import { useApp } from '../../context/AppContext';

// Tab configuration for vital signs
const vitalsTabs = [
    {
        id: 'bloodPressure',
        label: 'Blood Pressure',
        icon: Heart,
        metrics: [
            { key: 'bpSystolic', label: 'Systolic', unit: 'mmHg', color: '#ef4444' },
            { key: 'bpDiastolic', label: 'Diastolic', unit: 'mmHg', color: '#f97316' },
        ]
    },
    {
        id: 'heartRate',
        label: 'Heart Rate',
        icon: Activity,
        metrics: [
            { key: 'hr', label: 'Heart Rate', unit: 'bpm', color: '#8b5cf6' },
        ]
    },
    {
        id: 'oxygenation',
        label: 'SpO2',
        icon: Wind,
        metrics: [
            { key: 'spo2', label: 'Oxygen Saturation', unit: '%', color: '#3b82f6' },
        ]
    },
    {
        id: 'weight',
        label: 'Weight',
        icon: Scale,
        metrics: [
            { key: 'weight', label: 'Weight', unit: 'kg', color: '#10b981' },
        ]
    },
    {
        id: 'temperature',
        label: 'Temperature',
        icon: Thermometer,
        metrics: [
            { key: 'temp', label: 'Temperature', unit: '°C', color: '#f59e0b' },
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

    // Auto-load historical data on mount
    useEffect(() => {
        const loadData = async () => {
            setIsLoading(true);

            // Simulate brief loading for smooth UX
            await new Promise(resolve => setTimeout(resolve, 500));

            // Load historical data from patient object (Supabase only)
            const rawHistory = patient?.vitalsHistory || [];
            console.log('📊 PatientChart loading vitals for:', patientNric, 'History:', rawHistory);

            if (rawHistory.length > 0) {
                // Normalize all entries to objects
                const normalizedHistory = rawHistory.map(d => {
                    try {
                        return typeof d === 'string' ? JSON.parse(d) : d;
                    } catch (e) {
                        return d;
                    }
                });
                setVitalsData(normalizedHistory);
            } else {
                // No data available
                setVitalsData([]);
            }

            setIsLoading(false);
        };

        loadData();
    }, [patientNric, patient?.vitalsHistory]);


    const currentTabConfig = vitalsTabs.find(t => t.id === activeTab);

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
            weight: parseFloat(state.vitals.weight) || 0,
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
                        Patient Chart
                    </h1>
                    <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                        Vital Signs History
                    </p>
                </div>
            </div>

            {/* Patient Info Card */}
            <GlassCard className="p-5">
                <div className="flex items-center gap-4">
                    <div className={`w-16 h-16 rounded-full flex items-center justify-center ${isDark ? 'bg-[var(--accent-primary)]/20' : 'bg-[var(--accent-primary)]/10'
                        }`}>
                        <User className="w-8 h-8 text-[var(--accent-primary)]" />
                    </div>
                    <div className="flex-1">
                        <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                            {patient?.name || 'Unknown Patient'}
                        </h2>
                        <div className="flex flex-wrap gap-4 mt-1">
                            <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                                <strong>NRIC:</strong> {patientNric || 'N/A'}
                            </span>
                            <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                                <strong>Age:</strong> {patient?.age || 'N/A'} years
                            </span>
                            <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                                <strong>Gender:</strong> {patient?.gender || 'N/A'}
                            </span>
                        </div>
                    </div>
                    {patient?.comorbidities && patient.comorbidities.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                            {patient.comorbidities.slice(0, 3).map((condition, i) => (
                                <Badge key={i} variant="warning" size="sm">{condition}</Badge>
                            ))}
                        </div>
                    )}
                </div>
            </GlassCard>

            {/* Tabs */}
            <div className="flex gap-2 overflow-x-auto pb-2">
                {vitalsTabs.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;

                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm whitespace-nowrap transition-all ${isActive
                                ? 'bg-[var(--accent-primary)] text-white shadow-lg'
                                : isDark
                                    ? 'bg-white/10 text-slate-300 hover:bg-white/20'
                                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                }`}
                        >
                            <Icon className="w-4 h-4" />
                            {tab.label}
                        </button>
                    );
                })}
            </div>

            {/* Two-Column Layout: Chart Left, Stats Right */}
            <div className="flex flex-col lg:flex-row gap-6">
                {/* Left: Vital Signs Chart */}
                <GlassPanel className="p-6 flex-1 lg:w-2/3">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
                                {currentTabConfig && <currentTabConfig.icon className="w-5 h-5 text-[var(--accent-primary)]" />}
                            </div>
                            <div>
                                <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                    {currentTabConfig?.label} Trends
                                </h3>
                                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                    {isLoading
                                        ? 'Loading historical data...'
                                        : `${vitalsData.length} data points`
                                    }
                                </p>
                            </div>
                        </div>
                    </div>

                    {isLoading ? (
                        <div className="flex items-center justify-center h-48">
                            <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--accent-primary)] border-t-transparent" />
                        </div>
                    ) : (
                        <VitalsLineChart
                            data={historyToDisplay}
                            metrics={currentTabConfig?.metrics || []}
                            height={250}
                        />
                    )}
                </GlassPanel>

                {/* Right: Quick Stats */}
                {!isLoading && latestVitals && currentTabConfig && (
                    <div className="lg:w-1/3 space-y-4">
                        {currentTabConfig.metrics.map((metric) => {
                            const values = historyToDisplay.map(d => d[metric.key]).filter(v => v !== undefined && !isNaN(v));
                            const latest = latestVitals[metric.key];
                            const min = values.length > 0 ? Math.min(...values) : null;
                            const max = values.length > 0 ? Math.max(...values) : null;
                            const avg = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;

                            return (
                                <GlassCard key={metric.key} className="p-4">
                                    <h4 className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                                        {metric.label}
                                    </h4>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="text-center">
                                            <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Latest</div>
                                            <div className="text-xl font-bold" style={{ color: metric.color }}>
                                                {latest != null ? latest.toFixed(metric.key === 'temp' ? 1 : 0) : '-'}
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Average</div>
                                            <div className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                                                {avg != null ? avg.toFixed(metric.key === 'temp' ? 1 : 0) : '-'}
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Min</div>
                                            <div className="text-xl font-bold text-green-500">
                                                {min != null ? min.toFixed(metric.key === 'temp' ? 1 : 0) : '-'}
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Max</div>
                                            <div className="text-xl font-bold text-red-500">
                                                {max != null ? max.toFixed(metric.key === 'temp' ? 1 : 0) : '-'}
                                            </div>
                                        </div>
                                    </div>
                                    <div className={`text-xs text-center mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                                        {metric.unit}
                                    </div>
                                </GlassCard>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}

export default PatientChart;
