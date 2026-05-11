import React, { useState } from 'react';
import { WifiOff, CameraOff, CheckCircle } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { useRPPGStream } from '../../hooks/useRPPGStream';
import { supabase } from '../../lib/supabase';

function fmt(val, decimals = 0) {
  if (val == null || isNaN(val)) return '--';
  return decimals ? Number(val).toFixed(decimals) : String(Math.round(val));
}

export function LiveVitalsWidget() {
  const { dispatch, state } = useApp();
  const { isDark }          = useTheme();
  const { vitals, connected, status, start, stop } = useRPPGStream({ autoStart: true });
  const [saved, setSaved] = useState(false);

  const isStreaming  = status === 'streaming';
  const isRequesting = status === 'requesting';
  const isError      = status === 'error';
  const bufferPct    = vitals?.buffer_pct ?? 0;
  const quality      = vitals?.quality    ?? 0;
  const faceDetected = vitals?.face_detected ?? false;
  // Show values as soon as face is detected (same as rPPG POC website)
  const hasData      = connected && faceDetected;
  const isEsp32      = vitals?.esp32?.hr > 0;

  const applyVitals = async () => {
    if (!vitals) return;
    const esp32 = vitals.esp32 || {};
    const hr    = esp32.hr   > 0 ? esp32.hr   : vitals.hr;
    const spo2  = esp32.spo2 > 0 ? esp32.spo2 : vitals.spo2;
    const temp  = esp32.temp > 0 ? (esp32.temp + 3) : null;

    const payload = {};
    if (vitals.sbp != null) payload.bpSystolic  = String(Math.round(vitals.sbp));
    if (vitals.dbp != null) payload.bpDiastolic = String(Math.round(vitals.dbp));
    if (hr         != null) payload.hr          = String(Math.round(hr));
    if (temp       != null) payload.temp        = temp.toFixed(1);
    if (vitals.rr  != null) payload.rr          = String(Math.round(vitals.rr));
    if (spo2       != null) payload.spo2        = String(Math.round(spo2));

    // Apply to vitals form
    dispatch({ type: 'SET_VITALS', payload });

    // Upsert one row to live_vitals — one row per patient, replaced each time
    const nric = state.patient?.nsn;
    const name = state.patient?.name;
    if (nric) {
      const { error } = await supabase
        .from('live_vitals')
        .upsert({
          patient_nric: nric,
          patient_name: name || '',
          source:       'rppg',
          hr:           payload.hr          ? Number(payload.hr)          : null,
          spo2:         payload.spo2        ? Number(payload.spo2)        : null,
          sbp:          payload.bpSystolic  ? Number(payload.bpSystolic)  : null,
          dbp:          payload.bpDiastolic ? Number(payload.bpDiastolic) : null,
          rr:           payload.rr          ? Number(payload.rr)          : null,
          temp:         payload.temp        ? Number(payload.temp)        : null,
          quality:      vitals.quality      ? +vitals.quality.toFixed(1)  : null,
          updated_at:   new Date().toISOString(),
        }, { onConflict: 'patient_nric' });

      if (!error) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    }
  };

  return (
    <div className={`flex items-center justify-between px-4 py-2 rounded-xl border mb-3 transition-colors ${
      hasData
        ? isDark ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-emerald-50 border-emerald-200'
        : isError
          ? isDark ? 'bg-red-500/10 border-red-500/30' : 'bg-red-50 border-red-200'
          : isDark ? 'bg-slate-700/40 border-slate-600/30' : 'bg-slate-50 border-slate-200'
    }`}>

      {/* Left: status + vitals */}
      <div className="flex items-center gap-2 min-w-0 flex-1">
        {hasData ? (
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
        ) : isRequesting ? (
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse shrink-0" />
        ) : isError ? (
          <CameraOff className="w-4 h-4 text-red-400 shrink-0" />
        ) : (
          <WifiOff className="w-4 h-4 text-slate-400 shrink-0" />
        )}

        <span className={`text-xs font-semibold shrink-0 ${
          hasData      ? isDark ? 'text-emerald-400' : 'text-emerald-700'
          : isRequesting ? isDark ? 'text-amber-400' : 'text-amber-600'
          : isError     ? isDark ? 'text-red-400'    : 'text-red-600'
          :               isDark ? 'text-slate-500'  : 'text-slate-500'
        }`}>
          {hasData                        ? 'rPPG Live'
           : isRequesting                  ? 'Starting camera…'
           : isError                       ? 'Camera error'
           : isStreaming && faceDetected   ? `Buffering ${Math.round(bufferPct)}%…`
           : isStreaming                   ? 'Show your face…'
           : 'rPPG Off'}
        </span>

        {hasData && (
          <span className={`text-xs truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            HR <strong className={isDark ? 'text-white' : 'text-slate-800'}>{fmt(isEsp32 ? vitals.esp32.hr : vitals.hr)}</strong> bpm
            &nbsp;&middot;&nbsp;SpO&#x2082; <strong className={isDark ? 'text-white' : 'text-slate-800'}>{fmt(isEsp32 ? vitals.esp32.spo2 : vitals.spo2)}</strong>%
            &nbsp;&middot;&nbsp;BP <strong className={isDark ? 'text-white' : 'text-slate-800'}>{fmt(vitals.sbp)}/{fmt(vitals.dbp)}</strong>
            &nbsp;&middot;&nbsp;RR <strong className={isDark ? 'text-white' : 'text-slate-800'}>{fmt(vitals.rr)}</strong>
            &nbsp;&middot;&nbsp;Q {fmt(quality, 1)}%
            {bufferPct < 100 && (
              <span className="ml-1.5 text-amber-400">buf {Math.round(bufferPct)}%</span>
            )}
            {isEsp32 && (
              <span className="ml-1.5 px-1 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 align-middle">
                ESP32
              </span>
            )}
          </span>
        )}
      </div>

      {/* Right: toggle + apply */}
      <div className="flex items-center gap-2 ml-2 shrink-0">
        {(isStreaming || isError) && (
          <button
            onClick={isError ? start : stop}
            title={isError ? 'Retry camera' : 'Stop camera'}
            className={`text-xs px-2 py-1 rounded-lg transition-colors ${
              isDark ? 'bg-white/10 text-slate-400 hover:bg-white/20' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
            }`}
          >
            {isError ? 'Retry' : 'Stop'}
          </button>
        )}
        {status === 'idle' && (
          <button
            onClick={start}
            className={`text-xs px-2 py-1 rounded-lg transition-colors ${
              isDark ? 'bg-white/10 text-slate-400 hover:bg-white/20' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
            }`}
          >
            Start
          </button>
        )}
        {hasData && (
          <button
            onClick={applyVitals}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-lg transition-colors ${
              saved
                ? isDark ? 'bg-emerald-500/40 text-emerald-300' : 'bg-emerald-200 text-emerald-800'
                : isDark ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                         : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
            }`}
          >
            {saved ? <><CheckCircle className="w-3.5 h-3.5" /> Saved!</> : 'Apply to Vitals'}
          </button>
        )}
      </div>
    </div>
  );
}
