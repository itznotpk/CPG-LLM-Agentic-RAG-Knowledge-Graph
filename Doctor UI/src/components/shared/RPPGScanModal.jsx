import React, { useEffect, useRef, useState } from 'react';
import { X, CheckCircle, Activity, Heart, Wind, Droplets, Thermometer, Zap, Camera } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { useRPPGStream } from '../../hooks/useRPPGStream';
import { supabase } from '../../lib/supabase';

function VitalRow({ label, value, unit }) {
  const hasValue = value != null && Number(value) !== 0;
  const { isDark } = useTheme();

  return (
    <div className={`flex items-center justify-between px-3 py-2 border-b ${isDark ? 'border-white/10' : 'border-slate-100'} last:border-0`}>
      <div className="flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${hasValue ? 'bg-teal-600' : 'bg-slate-300'}`} />
        <span className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{label}</span>
      </div>
      <div>
        <span className={`font-mono font-semibold ${hasValue ? (isDark ? 'text-white' : 'text-slate-900') : (isDark ? 'text-slate-500' : 'text-slate-300')}`}>
          {hasValue ? (Number.isInteger(Number(value)) ? value : Number(value).toFixed(1)) : '—'}
        </span>
        <span className={`ml-1 text-[10px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{unit}</span>
      </div>
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

  // Count how many vitals are ready
  const readyCount = [hr, spo2, vitals?.sbp, vitals?.dbp, vitals?.rr, temp]
    .filter(v => v != null && Number(v) !== 0).length;

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
    <div className="fixed inset-0 z-[100] flex flex-col isolation-isolate" style={{ background: 'var(--bg-primary)' }}>

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

            {/* Face positioning guide — when not detected but connected */}
            {!faceFound && connected && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 pointer-events-none">
                {/* Dashed oval guide */}
                <svg width="110" height="145" viewBox="0 0 110 145" className="drop-shadow">
                  <ellipse cx="55" cy="72.5" rx="55" ry="72.5" fill="none" stroke="#14b8a6" strokeWidth="2" strokeDasharray="8 6" opacity="0.5" />
                  {/* Corner brackets */}
                  <g stroke="#14b8a6" strokeWidth="2" fill="none" opacity="0.8">
                    {/* Top-left */}
                    <line x1="0" y1="15" x2="0" y2="0" />
                    <line x1="0" y1="0" x2="15" y2="0" />
                    {/* Top-right */}
                    <line x1="110" y1="15" x2="110" y2="0" />
                    <line x1="110" y1="0" x2="95" y2="0" />
                    {/* Bottom-left */}
                    <line x1="0" y1="130" x2="0" y2="145" />
                    <line x1="0" y1="145" x2="15" y2="145" />
                    {/* Bottom-right */}
                    <line x1="110" y1="130" x2="110" y2="145" />
                    <line x1="110" y1="145" x2="95" y2="145" />
                  </g>
                </svg>
                {/* Guide text */}
                <span className="text-xs font-mono text-teal-600 tracking-wider uppercase">Position Face Inside the Guide</span>
                {/* Prep steps */}
                <div className="flex gap-4 text-xs font-mono text-slate-500">
                  <span>● Good Light</span>
                  <span>● No Glasses</span>
                  <span>● Look Straight</span>
                  <span>● ~15 SEC</span>
                </div>
              </div>
            )}

            {/* Signal quality pill — top-right */}
            {connected && (
              <div className="absolute top-4 right-4">
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full backdrop-blur-sm text-xs font-mono font-semibold ${
                  isDark ? 'bg-white/10 text-slate-300' : 'bg-black/30 text-white'
                }`}>
                  Signal · {quality.toFixed(0)}%
                </div>
              </div>
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

          <div className={`border rounded-xl overflow-hidden ${isDark ? 'bg-white/5 border-white/10' : 'bg-white border-slate-200'}`}>
            <VitalRow label="Heart Rate"  value={hr}          unit="bpm" />
            <VitalRow label="SpO₂"        value={spo2}        unit="%" />
            <VitalRow label="Systolic"    value={vitals?.sbp} unit="mmHg" />
            <VitalRow label="Diastolic"   value={vitals?.dbp} unit="mmHg" />
            <VitalRow label="Resp. Rate"  value={vitals?.rr}  unit="/min" />
            <VitalRow label="Temperature" value={temp}        unit="°C" />
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
                : <><Zap className="w-5 h-5" /> Apply {readyCount} of 6 vitals</>
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
