import React, { useEffect, useRef, useState } from 'react';
import { X, CheckCircle, Activity, Heart, Wind, Droplets, Thermometer, Zap, Camera } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { useRPPGStream } from '../../hooks/useRPPGStream';
import { supabase } from '../../lib/supabase';

function VitalCard({ icon: Icon, label, value, unit, color = 'emerald' }) {
  const { isDark } = useTheme();
  const colors = {
    emerald: 'text-emerald-400 bg-emerald-500/20',
    blue:    'text-blue-400 bg-blue-500/20',
    purple:  'text-purple-400 bg-purple-500/20',
    amber:   'text-amber-400 bg-amber-500/20',
    rose:    'text-rose-400 bg-rose-500/20',
  };
  const hasValue = value != null && Number(value) !== 0;

  return (
    <div className={`flex flex-col items-center justify-center p-4 rounded-2xl ${isDark ? 'bg-white/5 border border-white/10' : 'bg-white/60 border border-slate-200'}`}>
      <div className={`p-2 rounded-xl mb-2 ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <span className={`text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
      <span className={`text-2xl font-bold ${hasValue ? (isDark ? 'text-white' : 'text-slate-800') : (isDark ? 'text-slate-600' : 'text-slate-300')}`}>
        {hasValue ? (Number.isInteger(Number(value)) ? value : Number(value).toFixed(1)) : '--'}
      </span>
      <span className={`text-xs mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{unit}</span>
    </div>
  );
}

export function RPPGScanModal({ onClose }) {
  const { dispatch, state } = useApp();
  const { isDark } = useTheme();
  const { vitals, connected, status, start, stop, mediaStream } = useRPPGStream({ autoStart: true });
  const videoRef = useRef(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied]   = useState(false);

  // Attach media stream to visible video element
  useEffect(() => {
    if (videoRef.current && mediaStream) {
      videoRef.current.srcObject = mediaStream;
    }
  }, [mediaStream]);

  // Stop camera when modal closes
  useEffect(() => () => stop(), []);

  const esp32      = vitals?.esp32 || {};
  const hr         = esp32.hr   > 0 ? esp32.hr   : vitals?.hr;
  const spo2       = esp32.spo2 > 0 ? esp32.spo2 : vitals?.spo2;
  const temp       = esp32.temp > 0 ? (esp32.temp + 3) : null;
  const bufferPct  = vitals?.buffer_pct ?? 0;
  const quality    = vitals?.quality    ?? 0;
  const faceFound  = vitals?.face_detected ?? false;
  // Allow apply if face detected (camera) OR if ESP32 has real values (no face needed)
  const hasVitals  = (faceFound || esp32.hr > 0) && (hr > 0 || spo2 > 0);

  const handleApply = async () => {
    if (!vitals) return;
    setApplying(true);

    const payload = {};
    if (vitals.sbp != null) payload.bpSystolic  = String(Math.round(vitals.sbp));
    if (vitals.dbp != null) payload.bpDiastolic = String(Math.round(vitals.dbp));
    if (hr         != null) payload.hr          = String(Math.round(hr));
    if (temp       != null) payload.temp        = temp.toFixed(1);
    if (vitals.rr  != null) payload.rr          = String(Math.round(vitals.rr));
    if (spo2       != null) payload.spo2        = String(Math.round(spo2));

    // Fill vitals form
    dispatch({ type: 'SET_VITALS', payload });

    // Save one row to live_vitals with patient info
    const nric = state.patient?.nsn;
    const name = state.patient?.name;
    if (nric) {
      await supabase.from('live_vitals').insert({
        patient_nric:    nric,
        patient_name:    name || '',
        consultation_id: state.currentConsultationId || null,
        source:          'rppg',
        hr:              payload.hr          ? Number(payload.hr)          : null,
        spo2:            payload.spo2        ? Number(payload.spo2)        : null,
        sbp:             payload.bpSystolic  ? Number(payload.bpSystolic)  : null,
        dbp:             payload.bpDiastolic ? Number(payload.bpDiastolic) : null,
        rr:              payload.rr          ? Number(payload.rr)          : null,
        temp:            payload.temp        ? Number(payload.temp)        : null,
        quality:         quality             ? +quality.toFixed(1)         : null,
        updated_at:      new Date().toISOString(),
      });
    }

    setApplying(false);
    setApplied(true);
    setTimeout(() => { stop(); onClose(); }, 1200);
  };

  const statusText = status === 'requesting' ? 'Requesting camera…'
    : !connected          ? 'Connecting to rPPG server…'
    : !faceFound          ? 'Position your face in the frame'
    : bufferPct < 100     ? `Calibrating… ${Math.round(bufferPct)}%`
    : `Signal quality ${quality.toFixed(0)}%`;

  return (
    <div className="fixed inset-0 z-[80] flex flex-col" style={{ background: isDark ? '#0a0f1e' : '#f0f4ff' }}>

      {/* Header */}
      <div className={`flex items-center justify-between px-6 py-4 border-b ${isDark ? 'border-white/10 bg-slate-900/80' : 'border-slate-200 bg-white/80'} backdrop-blur-sm`}>
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/20 rounded-xl">
            <Activity className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>rPPG Vital Scanner</h2>
            {state.patient?.name && (
              <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {state.patient.name} · {state.patient.nsn}
              </p>
            )}
          </div>
        </div>
        <button onClick={() => { stop(); onClose(); }}
          className={`p-2 rounded-xl transition-colors ${isDark ? 'hover:bg-white/10 text-slate-400' : 'hover:bg-slate-100 text-slate-500'}`}>
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden gap-6 p-6">

        {/* Camera feed */}
        <div className="flex-1 flex flex-col gap-4">
          <div className={`relative flex-1 rounded-2xl overflow-hidden border-2 ${
            faceFound
              ? 'border-emerald-500/50'
              : isDark ? 'border-white/10' : 'border-slate-200'
          }`} style={{ minHeight: 0 }}>
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="w-full h-full object-cover scale-x-[-1]"
            />

            {/* Face detection overlay */}
            {faceFound && (
              <div className="absolute inset-0 border-4 border-emerald-400/40 rounded-2xl pointer-events-none" />
            )}

            {/* Status overlay */}
            <div className="absolute bottom-4 left-0 right-0 flex justify-center">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full backdrop-blur-sm text-sm font-medium ${
                faceFound && bufferPct >= 100
                  ? 'bg-emerald-500/80 text-white'
                  : 'bg-black/50 text-white'
              }`}>
                {faceFound && bufferPct >= 100
                  ? <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                  : <Camera className="w-4 h-4" />
                }
                {statusText}
              </div>
            </div>

            {/* Buffer progress bar */}
            {faceFound && bufferPct < 100 && (
              <div className="absolute top-4 left-4 right-4">
                <div className="h-1.5 rounded-full bg-white/20">
                  <div
                    className="h-full rounded-full bg-emerald-400 transition-all duration-500"
                    style={{ width: `${bufferPct}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Vitals panel */}
        <div className="w-72 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className={`text-sm font-semibold ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>LIVE MEASUREMENTS</h3>
            {esp32.hr > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-400">
                ESP32 Hardware
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 flex-1">
            <VitalCard icon={Heart}       label="Heart Rate"  value={hr}          unit="bpm"   color="rose"    />
            <VitalCard icon={Droplets}    label="SpO₂"        value={spo2}        unit="%"     color="blue"    />
            <VitalCard icon={Activity}    label="Systolic"    value={vitals?.sbp} unit="mmHg"  color="purple"  />
            <VitalCard icon={Activity}    label="Diastolic"   value={vitals?.dbp} unit="mmHg"  color="purple"  />
            <VitalCard icon={Wind}        label="Resp. Rate"  value={vitals?.rr}  unit="/min"  color="emerald" />
            <VitalCard icon={Thermometer} label="Temperature" value={temp}        unit="°C"    color="amber"   />
          </div>

          {/* Quality bar */}
          {connected && (
            <div className={`p-3 rounded-xl ${isDark ? 'bg-white/5' : 'bg-white/60'}`}>
              <div className="flex justify-between mb-1.5">
                <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Signal Quality</span>
                <span className={`text-xs font-semibold ${quality > 60 ? 'text-emerald-400' : quality > 30 ? 'text-amber-400' : 'text-red-400'}`}>
                  {quality.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-white/10">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${quality > 60 ? 'bg-emerald-400' : quality > 30 ? 'bg-amber-400' : 'bg-red-400'}`}
                  style={{ width: `${Math.min(quality, 100)}%` }}
                />
              </div>
            </div>
          )}

          {/* Apply button */}
          <button
            onClick={handleApply}
            disabled={!hasVitals || applying || applied}
            className={`w-full py-4 rounded-2xl font-bold text-base flex items-center justify-center gap-2 transition-all ${
              applied
                ? 'bg-emerald-500 text-white'
                : hasVitals
                  ? 'bg-emerald-500 hover:bg-emerald-400 text-white shadow-lg shadow-emerald-500/30'
                  : isDark ? 'bg-white/10 text-slate-500 cursor-not-allowed' : 'bg-slate-100 text-slate-400 cursor-not-allowed'
            }`}
          >
            {applied
              ? <><CheckCircle className="w-5 h-5" /> Applied! Returning…</>
              : applying
                ? 'Saving…'
                : <><Zap className="w-5 h-5" /> Apply to Consultation</>
            }
          </button>

          {!hasVitals && connected && (
            <p className={`text-xs text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Keep your face steady until values appear
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
