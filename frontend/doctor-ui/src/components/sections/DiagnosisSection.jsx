import React from 'react';
import {
  AlertCircle,
  CheckCircle,
  ArrowLeft,
  Sparkles,
  Target,
  RefreshCw,
  PencilLine,
} from 'lucide-react';
import {
  GlassCard,
  Button,
  Badge,
  TierSegmentedControl,
} from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { saveHumanSignal } from '../../lib/supabase';
import { PipelineProgress } from './PipelineProgress';
import { PlanGenerationProcess } from './PlanGenerationProcess';

const OVERRIDE_KEY_MAP = {
  'red_flag_cant_miss': "Red Flag (Can't Miss)",
  'specificity_over_generic': 'Specificity over Generic',
  'clinical_contradiction': 'Clinical Contradiction',
  'clinical_contradiction_rule': 'Clinical Contradiction Rule',
  'presentation_fit': 'Presentation Fit',
  'age_gender_compat': 'Demographic Compatibility',
  'sex_compat': 'Sex Compatibility'
};

function parseOverrideReason(reason) {
  if (!reason) return [];
  const parts = reason.includes(';') ? reason.split(';') : [reason];
  return parts.map(part => {
    const colonIdx = part.indexOf(':');
    if (colonIdx !== -1) {
      const key = part.slice(0, colonIdx).trim();
      const val = part.slice(colonIdx + 1).trim();
      const prettyKey = OVERRIDE_KEY_MAP[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      return { key: prettyKey, val };
    }
    return { key: null, val: part.trim().replace(/_/g, ' ') };
  });
}

export function DiagnosisSection() {
  const { state, dispatch, confirmDiagnosis, confirmManualDiagnosis, goToStep, regenerateDDx } = useApp();
  const { isDark } = useTheme();
  const { user, profile } = useAuth();
  const clinicianName = profile?.full_name || user?.email || 'Unknown clinician';
  const { diagnosis, isGeneratingPlan, isRegeneratingDdx, ddxExcludedCodes, ddxRegenExhausted, internationalGuidanceCheckEnabled } = state;
  const [traceCollapsed, setTraceCollapsed] = React.useState(true);
  const [expandedWhy, setExpandedWhy] = React.useState({});
  const [sortBy, setSortBy] = React.useState('rank');
  // Step-2 regeneration: collapsible panel + optional guidance text.
  const [regenOpen, setRegenOpen] = React.useState(false);
  const [regenFeedback, setRegenFeedback] = React.useState('');
  // Manual-diagnosis escape hatch: clinician's intended diagnosis isn't in the
  // AI's top-5, so they type it and route directly (no regeneration).
  const [manualOpen, setManualOpen] = React.useState(false);
  const [manualName, setManualName] = React.useState('');
  const [manualError, setManualError] = React.useState(null);

  // Card interaction is locked both during plan generation and a regeneration run.
  const locked = isGeneratingPlan || isRegeneratingDdx;

  const handleRegenerate = async () => {
    const feedback = regenFeedback;   // capture before the success path clears it
    try {
      await regenerateDDx({ feedback });
      // Log the regeneration to the Layer-3 feedback ecosystem (human_signals).
      // Best-effort + non-blocking: a failed insert must never disrupt the UI.
      // No CPGs are routed at the DDx stage, so cpg_references is null.
      saveHumanSignal({
        consultationId: state.currentConsultationId,
        nric: state.patient?.nsn,
        action: 'regenerate',
        comment: feedback,
        clinicianId: profile?.id,
        clinicianName,
        cpgReferences: null,
        requestId: state.clinicalPlanResponse?.request_id || null,
      }).catch((err) => console.error('human_signals capture failed:', err));
      setRegenFeedback('');
      setRegenOpen(false);
    } catch {
      // regenerateDDx logs + the pipeline trace surfaces the error; keep the panel open.
    }
  };

  const handleManualRoute = async () => {
    const name = manualName.trim();
    if (!name) { setManualError('Enter a diagnosis name.'); return; }
    setManualError(null);
    try {
      await confirmManualDiagnosis({ name });
      // Log to the human_signals feedback ecosystem — best-effort, non-blocking.
      saveHumanSignal({
        consultationId: state.currentConsultationId,
        nric: state.patient?.nsn,
        action: 'manual_diagnosis',
        comment: name,
        clinicianId: profile?.id,
        clinicianName,
        cpgReferences: null,
        requestId: state.clinicalPlanResponse?.request_id || null,
      }).catch((err) => console.error('human_signals capture failed:', err));
      setManualName('');
      setManualOpen(false);
    } catch (err) {
      // Resolution failure (no ICD match) or synthesis error surfaces here —
      // keep the panel open so the clinician can refine the name and retry.
      console.error('Manual diagnosis routing failed:', err);
      setManualError(err?.message || 'Could not route this diagnosis. Try a more specific name.');
    }
  };

  if (!diagnosis) return null;

  // Keep differentials in their final LLM re-ranked order from the backend
  const sortedDifferentials = [...diagnosis.differentials];

  const [tiers, setTiers] = React.useState(() =>
    Object.fromEntries(sortedDifferentials.map((d) => [d.icdCode, 'off']))
  );

  React.useEffect(() => {
    setTiers(Object.fromEntries(sortedDifferentials.map((d) => [d.icdCode, 'off'])));
  }, [diagnosis]);

  const selectedCodes = Object.entries(tiers)
    .filter(([, tier]) => tier !== 'off')
    .map(([code]) => code);
  const majorCode = Object.entries(tiers).find(([, tier]) => tier === 'major')?.[0] || null;
  const selectedDiagnoses = sortedDifferentials.filter((d) => selectedCodes.includes(d.icdCode));
  const canConfirm = !!majorCode && !isGeneratingPlan;

  // Detect if clinician selection differs from AI routing set (top-2 DDx codes)
  const aiTopCodes = new Set(
    (state.clinicalPlanResponse?.ddx || []).slice(0, 2).map((d) => d.code)
  );
  const willResynth = selectedDiagnoses.some((d) => !aiTopCodes.has(d.icdCode));

  const [confirmError, setConfirmError] = React.useState(null);
  // Only surfaced AFTER the user clicks Confirm without marking a Major — the
  // reminder is not shown upfront.
  const [showSelectReminder, setShowSelectReminder] = React.useState(false);
  const handleConfirm = async () => {
    if (!majorCode) { setShowSelectReminder(true); return; }
    setShowSelectReminder(false);
    setConfirmError(null);
    try {
      await confirmDiagnosis({ selectedCodes, majorCode });
    } catch (err) {
      // confirmDiagnosis swallows most errors internally and resets the
      // loading state, leaving the user stranded on this page. Show whatever
      // surfaces here as a banner so the failure isn't silent.
      console.error('confirmDiagnosis threw:', err);
      setConfirmError(err?.message || 'Failed to generate the care plan. Check the API server and try again.');
    }
  };

  const toggleInternationalComparison = () => {
    if (!majorCode || locked) return;
    const enabled = !internationalGuidanceCheckEnabled;
    dispatch({ type: 'SET_INTERNATIONAL_GUIDANCE_CHECK', payload: enabled });
    dispatch({ type: 'SET_INTERNATIONAL_GUIDANCE_DECISION', payload: enabled ? 'compare' : 'malaysia_only' });
    dispatch({ type: 'SET_INTERNATIONAL_GUIDANCE_RATIONALE', payload: '' });
  };

  // Tap the card itself to cycle Off → Minor → Major → Off. Pill / hint
  // button onClick handlers stop propagation so a direct pill click still
  // sets the exact state without re-cycling.
  const cycleTier = (code) => {
    const current = tiers[code] || 'off';
    const next = current === 'off' ? 'minor' : current === 'minor' ? 'major' : 'off';
    setTier(code, next);
  };

  // P5: clinician picks Major + (0–4) Minors via the segmented tier panel.
  // The override is routed through the same confirmDiagnosis path so all the
  // downstream DB save / risk calculation / plan generation logic still fires.
  const handleBack = () => {
    goToStep(1);
  };

  const setTier = (code, nextTier) => {
    setTiers((prev) => {
      const updated = { ...prev };
      if (nextTier === 'major') {
        for (const [existingCode, tier] of Object.entries(updated)) {
          if (existingCode !== code && tier === 'major') {
            updated[existingCode] = 'minor';
          }
        }
      }
      updated[code] = nextTier;
      return updated;
    });
  };

  if (isGeneratingPlan) {
    return (
      <PlanGenerationProcess
        selectedDiagnoses={selectedDiagnoses}
        pipelineEvents={state.pipelineEvents}
        safetyReport={state.safetyReport}
        resynthOverride={state.resynthOverride}
      />
    );
  }

  // Risk label badge colors
  const getRiskBadge = (pct) => {
    if (pct == null) return null;
    if (pct >= 70) return { label: 'High', dot: 'bg-rose-500', bg: isDark ? 'bg-emerald-500/15 text-emerald-400' : 'bg-emerald-50 text-emerald-700 border border-emerald-200' };
    if (pct >= 40) return { label: 'Moderate', dot: 'bg-amber-500', bg: isDark ? 'bg-amber-500/15 text-amber-400' : 'bg-amber-50 text-amber-700 border border-amber-200' };
    return { label: 'Low', dot: 'bg-slate-400', bg: isDark ? 'bg-slate-500/15 text-slate-400' : 'bg-slate-100 text-slate-600 border border-slate-200' };
  };

  // Tier badge for selected cards
  const getTierBadge = (tier) => {
    if (tier === 'major') return { label: 'Major', classes: isDark ? 'bg-amber-500 text-white' : 'bg-amber-500 text-white' };
    if (tier === 'minor') return { label: 'Minor', classes: isDark ? 'bg-teal-500 text-white' : 'bg-teal-500 text-white' };
    return null;
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between gap-6 mb-6">
        <div>
          <span className="ds-eyebrow">STEP 2 OF 4</span>
          <h2 className={`text-xl font-semibold tracking-tight mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Diagnosis
          </h2>
          <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Confirm the AI's working diagnosis, or pick differentials to re-route.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-center justify-end gap-3 flex-shrink-0">
          <button
            type="button"
            onClick={toggleInternationalComparison}
            disabled={!majorCode || locked}
            role="switch"
            aria-checked={internationalGuidanceCheckEnabled}
            title={majorCode ? 'Compare curated international guidance after generating the Malaysian CPG plan' : 'Select a Major diagnosis first'}
            className={`inline-flex items-center gap-2.5 rounded-xl border px-3 py-2 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
              internationalGuidanceCheckEnabled
                ? (isDark ? 'border-emerald-400/50 bg-emerald-500/15 text-emerald-100 shadow-[0_0_20px_rgba(16,185,129,0.22)]' : 'border-emerald-400 bg-emerald-50 text-emerald-800 shadow-sm')
                : (isDark ? 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-600' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300')
            }`}
          >
            <span>Compare international guidance</span>
            <span className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${internationalGuidanceCheckEnabled ? 'bg-emerald-500' : (isDark ? 'bg-slate-600' : 'bg-slate-300')}`}>
              <span className="absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-out" style={{ transform: internationalGuidanceCheckEnabled ? 'translateX(20px)' : 'translateX(0)' }} />
            </span>
            <span className="w-5 text-left font-bold tabular-nums">{internationalGuidanceCheckEnabled ? 'ON' : 'OFF'}</span>
          </button>
          <Button
            variant="secondary"
            size="sm"
            icon={ArrowLeft}
            onClick={handleBack}
          >
            Back
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={isGeneratingPlan ? null : CheckCircle}
            loading={isGeneratingPlan}
            disabled={isGeneratingPlan}
            onClick={handleConfirm}
            glow={canConfirm}
            title={canConfirm ? undefined : 'Mark one diagnosis as Major to continue'}
          >
            {isGeneratingPlan ? 'Generating…' : 'Confirm'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT PANEL: AI Reasoning Summary */}
        <div className="lg:col-span-5">
          <div className="sticky top-4">
            <PipelineProgress
              pipelineEvents={state.pipelineEvents}
              pipelineThinking={state.pipelineThinking}
              summary={state.pipelineSummary}
              isLive={isGeneratingPlan}
              resynthOverride={state.resynthOverride}
              collapsed={traceCollapsed}
              onToggle={() => setTraceCollapsed((prev) => !prev)}
            />
          </div>
        </div>

        {/* RIGHT PANEL: Decision & DDx */}
        <div className="lg:col-span-7 space-y-4">

      {/* Status banner — "Ready to confirm" once a Major is marked; the
          "select a Major" reminder only appears after a Confirm attempt with none. */}
      {(majorCode || showSelectReminder) && (
        <div className={`flex items-center gap-2.5 px-4 py-3 rounded-xl ${
          majorCode
            ? (isDark ? 'bg-emerald-900/20 text-emerald-300 border border-emerald-500/20' : 'bg-emerald-50 text-emerald-700 border border-emerald-200')
            : (isDark ? 'bg-amber-900/20 text-amber-300 border border-amber-500/20' : 'bg-amber-50 text-amber-700 border border-amber-200')
        }`}>
          {majorCode
            ? <CheckCircle className="w-5 h-5 shrink-0" strokeWidth={1.5} />
            : <AlertCircle className="w-5 h-5 shrink-0" strokeWidth={1.5} />}
          <div>
            <span className="font-semibold text-sm">
              {majorCode ? 'Ready to confirm.' : 'Select one diagnosis as Major to proceed.'}
            </span>
            <span className={`text-xs block mt-0.5 ${
              majorCode
                ? (isDark ? 'text-emerald-400/70' : 'text-emerald-600/70')
                : (isDark ? 'text-amber-400/70' : 'text-amber-600/70')
            }`}>
              {majorCode
                ? `Major: ${sortedDifferentials.find(d => d.icdCode === majorCode)?.name || majorCode}. ${selectedCodes.length - 1} minor(s) selected.`
                : 'You can adjust the priority of each diagnosis based on clinical judgement.'}
            </span>
          </div>
        </div>
      )}

      {confirmError && (
        <div className={`flex items-start gap-2 text-sm px-4 py-3 rounded-xl
          ${isDark ? 'bg-rose-900/30 text-rose-200 border border-rose-500/30'
                   : 'bg-rose-50    text-rose-800 border border-rose-200'}`}>
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} />
          <div className="flex-1">
            <div className="font-semibold mb-1">Confirm failed — care plan could not be generated</div>
            <div className="text-xs">{confirmError}</div>
            <div className="text-[11px] mt-1 opacity-75">
              Check the API server is running on <code>localhost:8058</code> and look in the browser console for details.
            </div>
          </div>
          <button
            type="button"
            onClick={() => setConfirmError(null)}
            className="text-xs underline opacity-80 hover:opacity-100"
          >
            dismiss
          </button>
        </div>
      )}

      {/* Differential Diagnosis - Card-based Design */}
      <GlassCard className="p-6">
        {/* Header with icon + title + candidate count */}
        <div className="flex items-center gap-3 mb-5">
          <div className={`p-2 rounded-xl ${isDark ? 'bg-teal-500/20' : 'bg-teal-50'}`}>
            <Target className="w-5 h-5 text-teal-500" strokeWidth={1.5} />
          </div>
          <div className="flex items-center gap-2.5">
            <h3 className={`text-xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>Differential Diagnosis</h3>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-100 text-slate-500'}`}>
              {sortedDifferentials.length} candidates
            </span>
          </div>
        </div>

        {diagnosis?.cpgsMatched?.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mb-4">
            <span className="ds-eyebrow">CPGs consulted</span>
            {diagnosis.cpgsMatched.map(name => (
              <Badge key={name} variant="info" size="sm">{name}</Badge>
            ))}
          </div>
        )}

        {/* DDx Cards */}
        <div className="space-y-3">
          {sortedDifferentials.map((diff, idx) => {
            const tier = tiers[diff.icdCode] || 'off';
            const isSelected = tier !== 'off';
            const isMajor = tier === 'major';
            const isTopSuggestion = idx === 0;
            const isMajorHint = state.ddxSuggestion?.headless_default_major === diff.icdCode;
            const isMinorHint = state.ddxSuggestion?.headless_default_minors?.includes(diff.icdCode);
            // probability is already 0–100 (mapped from final_score*100 or similarity*100 in clinicalMappers.js)
            const pct = diff.probability != null ? Math.round(diff.probability) : null;
            const riskBadge = getRiskBadge(pct);
            const tierBadge = getTierBadge(tier);

            // Card border and background based on tier selection
            const cardBorderColor = isMajor
              ? (isDark ? 'border-amber-400/70' : 'border-amber-400')
              : isSelected
              ? (isDark ? 'border-teal-400/60' : 'border-teal-400')
              : (isDark ? 'border-slate-700/60' : 'border-slate-200');

            const cardBg = isMajor
              ? (isDark ? 'bg-amber-500/5' : 'bg-amber-50/50')
              : isSelected
              ? (isDark ? 'bg-teal-500/5' : 'bg-teal-50/30')
              : (isDark ? 'bg-slate-800/40' : 'bg-white');

            return (
              <div
                key={diff.id}
                role="button"
                tabIndex={locked ? -1 : 0}
                onClick={() => !locked && cycleTier(diff.icdCode)}
                onKeyDown={(e) => {
                  if (locked) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    cycleTier(diff.icdCode);
                  }
                }}
                aria-pressed={isSelected}
                aria-label={`${diff.name} — current tier ${tier}. Click to cycle Off, Minor, Major.`}
                className={`w-full text-left rounded-xl transition-all duration-200 border-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-400/50
                  ${cardBorderColor} ${cardBg}
                  ${!isSelected && !isDark ? 'hover:border-slate-300 hover:shadow-md' : ''}
                  ${!isSelected && isDark ? 'hover:border-slate-600 hover:bg-slate-800/60' : ''}
                  ${isSelected ? 'shadow-md' : 'shadow-sm'}
                  ${locked ? 'cursor-not-allowed opacity-70' : ''}`}
                style={{ overflow: 'hidden' }}
              >
                {/* Main content area */}
                <div className="px-4 py-4">
                  {/* Row 1: Number + Name + ICD + Risk badge + tier controls */}
                  <div className="flex items-start justify-between gap-3 mb-1">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      {/* Numbered circle */}
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm font-bold mt-0.5
                        ${isMajor
                          ? 'bg-amber-500 text-white'
                          : isSelected
                          ? 'bg-teal-500 text-white'
                          : isDark
                          ? 'bg-slate-700/50 text-slate-400 border border-slate-600/50'
                          : 'bg-slate-100 text-slate-500 border border-transparent'
                        }`}>
                        {idx + 1}
                      </div>

                      <div className="flex-1 min-w-0">
                        {/* Diagnosis name */}
                        <h4 className={`text-sm font-semibold leading-snug ${isDark ? 'text-white' : 'text-slate-800'}`}>
                          {diff.name}
                        </h4>

                        {/* System suggestion hint badge */}
                        {(isMajorHint || isMinorHint) && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setTier(diff.icdCode, isMajorHint ? 'major' : 'minor');
                            }}
                            className={`inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full border transition-colors mt-1.5
                              ${isMajorHint
                                ? (isDark ? 'border-amber-400/60 text-amber-300 bg-amber-500/10 hover:bg-amber-500/20' : 'border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100')
                                : (isDark ? 'border-teal-400/60 text-teal-300 bg-teal-500/10 hover:bg-teal-500/20' : 'border-teal-300 text-teal-700 bg-teal-50 hover:bg-teal-100')
                              }`}
                          >
                            <Sparkles className="w-3 h-3" />
                            {isMajorHint ? 'System suggests Major' : 'System suggests Minor'}
                          </button>
                        )}

                        {/* Why this rank? link */}
                        {(() => {
                          const hasRankDelta = diff.mathRank && diff.mathRank !== (idx + 1);
                          const hasOverride = !!diff.overrideReason;
                          if (!hasRankDelta && !hasOverride) return null;
                          const isExpanded = !!expandedWhy[diff.icdCode];
                          return (
                            <div
                              className="mt-1.5"
                              onClick={(e) => e.stopPropagation()}
                              onKeyDown={(e) => e.stopPropagation()}
                            >
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setExpandedWhy((prev) => ({ ...prev, [diff.icdCode]: !prev[diff.icdCode] }));
                                }}
                                className={`text-[11px] underline-offset-2 hover:underline flex items-center gap-1 ${
                                  isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'
                                }`}
                              >
                                {isExpanded ? 'Hide details ∧' : 'Show details ∨'}
                              </button>
                            </div>
                          );
                        })()}
                      </div>
                    </div>

                    {/* Right side: ICD code + risk dot + risk badge + tier badge + segmented control */}
                    <div className="flex flex-col items-end gap-2 shrink-0"
                         onClick={(e) => e.stopPropagation()}
                         onKeyDown={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-2">
                        {tierBadge && (
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${tierBadge.classes}`}>
                            {tierBadge.label}
                          </span>
                        )}
                        <span className={`text-[11px] font-mono ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                          ICD-11: {diff.icdCode}
                        </span>
                        <div className={`w-2 h-2 rounded-full shrink-0 ${riskBadge?.dot || 'bg-amber-500'}`} />
                        {isTopSuggestion && (
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                            isDark ? 'text-amber-400' : 'text-amber-600'
                          }`}>
                            AI top pick
                          </span>
                        )}
                        {riskBadge && (
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md ${riskBadge.bg}`}>
                            {riskBadge.label}
                          </span>
                        )}
                      </div>
                      <TierSegmentedControl
                        value={tier}
                        onChange={(next) => setTier(diff.icdCode, next)}
                        disabled={locked}
                        ariaLabel={`Tier for ${diff.icdCode} ${diff.name}`}
                      />
                    </div>
                  </div>

                  {/* Expanded "Why?" details — two-column gray box */}
                  {expandedWhy[diff.icdCode] && (() => {
                    const hasRankDelta = diff.mathRank && diff.mathRank !== (idx + 1);
                    const hasOverride = !!diff.overrideReason;
                    if (!hasRankDelta && !hasOverride && pct == null) return null;
                    return (
                      <div
                        className={`mt-3 rounded-lg p-4 ${
                          isDark ? 'bg-slate-800/60 border border-slate-700/50' : 'bg-slate-50 border border-slate-200'
                        }`}
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => e.stopPropagation()}
                      >
                        <div className={`grid gap-4 ${hasRankDelta && hasOverride ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1'}`}>
                          {/* Left column: Reranked */}
                          {hasRankDelta && (
                            <div>
                              <div className={`text-[11px] font-medium mb-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                Reranked
                              </div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                                  isDark ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                                         : 'bg-amber-50 text-amber-700 border border-amber-200'
                                }`}>
                                  from #{diff.mathRank} → #{idx + 1} ({diff.rankDelta > 0 ? `↑${diff.rankDelta}` : `↓${Math.abs(diff.rankDelta)}`})
                                </span>
                                <span className={`text-[10px] font-semibold px-2 py-1 rounded-full ${
                                  isDark ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                         : 'bg-amber-100 text-amber-800 border border-amber-200'
                                }`}>
                                  Clinical Override
                                </span>
                              </div>
                            </div>
                          )}

                          {/* Right column: Clinical Override Reason */}
                          {hasOverride && (
                            <div>
                              <div className={`text-[11px] font-medium mb-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                Clinical Override Reason
                              </div>
                              <div className="space-y-1">
                                {parseOverrideReason(diff.overrideReason).map((item, i) => (
                                  <div key={i} className={`text-xs leading-relaxed ${
                                    isDark ? 'text-slate-200' : 'text-slate-700'
                                  }`}>
                                    {item.key && (
                                      <span className={`font-semibold ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                                        {item.key}:{' '}
                                      </span>
                                    )}
                                    {item.val}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                        {pct != null && (
                          <div className={`mt-3 pt-3 text-[11px] ${
                            hasRankDelta || hasOverride ? `border-t ${isDark ? 'border-slate-700/50' : 'border-slate-200'}` : ''
                          } ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                            Model match score: <span className="font-mono">{(pct / 100).toFixed(2)}</span>
                            <span className="opacity-70"> — retrieval similarity, not a probability of the disease</span>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </div>
            );
          })}
        </div>

        {/* Regenerate differentials — re-runs Stage 2 with the prior top-5 excluded
            (accumulated across presses) and optional clinician guidance. */}
        <div className={`mt-4 pt-4 border-t ${isDark ? 'border-slate-700/50' : 'border-slate-200'}`}>
          {!regenOpen ? (
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <button
                type="button"
                onClick={() => setRegenOpen(true)}
                disabled={locked}
                className={`inline-flex items-center gap-1.5 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                  ${isDark ? 'text-slate-300 hover:text-white' : 'text-slate-600 hover:text-slate-900'}`}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRegeneratingDdx ? 'animate-spin' : ''}`} strokeWidth={1.5} />
                Not quite right? Regenerate differentials
              </button>
              {ddxExcludedCodes?.length > 0 && (
                <span className={`text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {ddxExcludedCodes.length} earlier suggestion{ddxExcludedCodes.length === 1 ? '' : 's'} excluded
                </span>
              )}
            </div>
          ) : (
            <div className="space-y-2.5">
              <label className={`block text-xs font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                Add guidance <span className="font-normal opacity-70">(optional)</span>
              </label>
              <textarea
                value={regenFeedback}
                onChange={(e) => setRegenFeedback(e.target.value)}
                disabled={isRegeneratingDdx}
                rows={2}
                placeholder="e.g. consider endocrine causes, patient is pregnant, rule out infection…"
                className={`w-full text-sm rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-teal-400/50 disabled:opacity-60
                  ${isDark ? 'bg-slate-800/60 border border-slate-700 text-slate-100 placeholder-slate-500'
                           : 'bg-white border border-slate-200 text-slate-800 placeholder-slate-400'}`}
              />
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <span className={`text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  The current top {Math.min(5, sortedDifferentials.length)} will be excluded from the new ranking.
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => { setRegenOpen(false); setRegenFeedback(''); }}
                    disabled={isRegeneratingDdx}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    icon={isRegeneratingDdx ? null : RefreshCw}
                    loading={isRegeneratingDdx}
                    disabled={isRegeneratingDdx}
                    onClick={handleRegenerate}
                  >
                    {isRegeneratingDdx ? 'Regenerating…' : 'Regenerate'}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Manual diagnosis — clinician's intended diagnosis isn't in the top-5,
              so they type it and route CPGs directly (server resolves the ICD-11
              code) instead of regenerating the whole list. */}
          {!manualOpen ? (
            <div className="mt-2.5">
              <button
                type="button"
                onClick={() => { setManualOpen(true); setManualError(null); }}
                disabled={locked}
                className={`inline-flex items-center gap-1.5 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                  ${isDark ? 'text-slate-300 hover:text-white' : 'text-slate-600 hover:text-slate-900'}`}
              >
                <PencilLine className="w-3.5 h-3.5" strokeWidth={1.5} />
                Diagnosis not listed? Enter it directly
              </button>
            </div>
          ) : (
            <div className="mt-3 space-y-2.5">
              <label className={`block text-xs font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                Your diagnosis
              </label>
              <input
                type="text"
                value={manualName}
                onChange={(e) => { setManualName(e.target.value); if (manualError) setManualError(null); }}
                onKeyDown={(e) => { if (e.key === 'Enter' && !locked) { e.preventDefault(); handleManualRoute(); } }}
                disabled={locked}
                placeholder="e.g. Acute pericarditis"
                className={`w-full text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-400/50 disabled:opacity-60
                  ${isDark ? 'bg-slate-800/60 border border-slate-700 text-slate-100 placeholder-slate-500'
                           : 'bg-white border border-slate-200 text-slate-800 placeholder-slate-400'}`}
              />
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <span className={`text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  We'll match this to an ICD-11 code and route the relevant CPGs.
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => { setManualOpen(false); setManualName(''); setManualError(null); }}
                    disabled={locked}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    icon={locked ? null : PencilLine}
                    loading={isGeneratingPlan}
                    disabled={locked || !manualName.trim()}
                    onClick={handleManualRoute}
                  >
                    {isGeneratingPlan ? 'Routing…' : 'Route diagnosis'}
                  </Button>
                </div>
              </div>
              {manualError && (
                <div className={`flex items-start gap-2 text-xs px-3 py-2 rounded-lg
                  ${isDark ? 'bg-rose-900/30 text-rose-200 border border-rose-500/30'
                           : 'bg-rose-50 text-rose-800 border border-rose-200'}`}>
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" strokeWidth={1.5} />
                  <span>{manualError}</span>
                </div>
              )}
            </div>
          )}

          {ddxRegenExhausted && !isRegeneratingDdx && (
            <div className={`mt-3 flex items-start gap-2 text-xs px-3 py-2 rounded-lg
              ${isDark ? 'bg-slate-800/60 text-slate-300 border border-slate-700/50'
                       : 'bg-slate-50 text-slate-600 border border-slate-200'}`}>
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" strokeWidth={1.5} />
              <span>No further distinct diagnoses to suggest — showing the previous ranking.</span>
            </div>
          )}
        </div>
      </GlassCard>

      {isGeneratingPlan && (
        <div className="flex flex-col items-center gap-4 py-6 animate-fadeIn">
          <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
            <Sparkles className="w-5 h-5 animate-pulse text-[var(--accent-primary)]" strokeWidth={1.5} />
            <span>
              {willResynth 
                ? `AI is re-synthesizing evidence-based care plan for ${selectedDiagnoses.length === 1 ? selectedDiagnoses[0]?.name : `${selectedDiagnoses.length} diagnoses`}...`
                : `AI is generating evidence-based care plan for ${selectedDiagnoses.length === 1 ? selectedDiagnoses[0]?.name : `${selectedDiagnoses.length} diagnoses`}...`
              }
            </span>
          </div>
          <p className={`text-sm ${isDark ? 'text-indigo-400' : 'text-indigo-600'}`}>
            Watch the AI Reasoning Trace panel for live progress
          </p>
        </div>
      )}
        </div>
      </div>
    </div>
  );
}
