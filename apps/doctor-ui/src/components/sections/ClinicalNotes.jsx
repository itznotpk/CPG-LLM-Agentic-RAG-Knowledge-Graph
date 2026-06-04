import React from 'react';
import { GlassCard, VoiceInputButton } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { sampleClinicalNotes } from '../../data/sampleData';

export function ClinicalNotes() {
  const { state, dispatch } = useApp();
  const { isDark } = useTheme();
  const { clinicalNotes } = state;
  const [savedAt, setSavedAt] = React.useState(null);
  const debounceRef = React.useRef(null);

  const persist = (value) => {
    dispatch({ type: 'SET_CLINICAL_NOTES', payload: value });
    setSavedAt(new Date());
  };

  const handleChange = (e) => {
    const value = e.target.value;
    // Optimistic local update (context is source of truth; debounce the "Saved" timestamp)
    dispatch({ type: 'SET_CLINICAL_NOTES', payload: value });
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSavedAt(new Date()), 500);
  };

  const handleBlur = () => {
    clearTimeout(debounceRef.current);
    if (clinicalNotes?.trim()) setSavedAt(new Date());
  };

  const handleVoiceTranscript = (transcript) => {
    const next = clinicalNotes ? clinicalNotes + '\n\n' + transcript : transcript;
    persist(next);
  };

  const handleSampleFill = () => {
    // EVALUATION_FRAMEWORK_README.md Case 11 — Stable CAD + T2DM + Obesity + ED.
    persist(sampleClinicalNotes.history);
  };

  const wordCount = clinicalNotes?.trim()
    ? clinicalNotes.trim().split(/\s+/).length
    : 0;

  const savedTime = savedAt
    ? savedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  const textareaCls = `w-full px-4 py-3 rounded-xl border text-sm leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 ${
    isDark
      ? 'bg-white/5 border-white/10 text-white placeholder-slate-500'
      : 'bg-white border-slate-200 text-slate-800 placeholder-slate-400'
  }`;

  return (
    <GlassCard className="p-5">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className={`text-lg font-semibold tracking-tight leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Clinical notes
          </h3>
          <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            HPI · Exam · pertinent positives &amp; negatives
          </p>
        </div>
        <div className="flex items-center gap-2">
          <VoiceInputButton mode="consultation" onTranscript={handleVoiceTranscript} />
          <button
            onClick={handleSampleFill}
            className={`text-sm font-medium px-3 py-1.5 rounded-lg border transition-colors ${
              isDark
                ? 'border-white/20 text-slate-400 hover:bg-white/10'
                : 'border-slate-300 text-slate-500 hover:bg-slate-50'
            }`}
          >
            Sample
          </button>
        </div>
      </div>

      {/* Textarea */}
      <textarea
        rows={7}
        placeholder="CC: …&#10;&#10;HPI: …&#10;&#10;PE: …"
        value={clinicalNotes || ''}
        onChange={handleChange}
        onBlur={handleBlur}
        className={textareaCls}
      />

      {/* Footer */}
      <div className={`flex items-center justify-between mt-2 text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        <span className="flex items-center gap-1.5">
          {savedTime && clinicalNotes?.trim() ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
              Saved · {savedTime}
            </>
          ) : (
            <span className="opacity-0 select-none">·</span>
          )}
        </span>
        <span className="flex items-center gap-2">
          {wordCount > 0 ? `${wordCount} words` : ''}
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
            isDark ? 'bg-white/5 text-slate-500' : 'bg-slate-100 text-slate-400'
          }`}>
            <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a7 7 0 0 1 7 7v4a7 7 0 0 1-14 0V9a7 7 0 0 1 7-7Z" />
              <path d="M8 21h8" /><path d="M12 17v4" />
            </svg>
            Google STT
          </span>
        </span>
      </div>
    </GlassCard>
  );
}
