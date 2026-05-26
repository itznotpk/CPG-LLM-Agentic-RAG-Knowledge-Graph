import React from 'react';
import {
  Brain,
  AlertCircle,
  CheckCircle,
  ArrowLeft,
  Sparkles,
  Target,
  Check,
  BrainCircuit,
  ChevronRight,
} from 'lucide-react';
import {
  GlassCard,
  Button,
  Badge,
  RiskBadge,
  CodeBadge,
} from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { PipelineProgress } from './PipelineProgress';
import { PlanGenerationProcess } from './PlanGenerationProcess';

export function DiagnosisSection() {
  const { state, confirmDiagnosis, goToStep, selectDiagnosis } = useApp();
  const { isDark } = useTheme();
  const { diagnosis, isGeneratingPlan } = state;
  const [traceCollapsed, setTraceCollapsed] = React.useState(true);

  if (!diagnosis) return null;

  // Sort differentials by probability (highest first)
  const sortedDifferentials = [...diagnosis.differentials].sort(
    (a, b) => b.probability - a.probability
  );

  // Get the selected diagnoses (or default to highest probability)
  const selectedIds = diagnosis.selectedDiagnosisIds?.length > 0
    ? diagnosis.selectedDiagnosisIds
    : [sortedDifferentials[0]?.id].filter(Boolean);
  const selectedDiagnoses = sortedDifferentials.filter((d) => selectedIds.includes(d.id));

  // Detect if clinician selection differs from AI routing set (top-2 DDx codes)
  const aiTopCodes = new Set(
    (state.clinicalPlanResponse?.ddx || []).slice(0, 2).map((d) => d.code)
  );
  const willResynth = selectedDiagnoses.some((d) => !aiTopCodes.has(d.icdCode));

  const handleConfirm = () => {
    confirmDiagnosis();
  };

  const handleBack = () => {
    goToStep(1);
  };

  const handleSelectDiagnosis = (diagnosisId) => {
    selectDiagnosis(diagnosisId);
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
            onClick={handleConfirm}
            glow={!isGeneratingPlan}
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
        <div className="lg:col-span-7 space-y-6">

      {/* Clinical Correlation note — single line */}
      <div className={`flex items-center gap-2 text-sm px-4 py-3 rounded-lg
        ${isDark ? 'bg-amber-900/20 text-amber-300 border border-amber-500/20'
                 : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
        <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.5} />
        <span>Clinical correlation required. You may select multiple diagnoses from the list below.</span>
      </div>

      {/* Differential Diagnosis - Selectable */}
      <GlassCard className="p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
            <Target className="w-5 h-5 text-[var(--accent-primary)]" strokeWidth={1.5} />
          </div>
          <h3 className={`text-xl font-semibold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>Differential Diagnosis</h3>
        </div>

        {diagnosis?.cpgsMatched?.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mb-3">
            <span className="ds-eyebrow">CPGs consulted</span>
            {diagnosis.cpgsMatched.map(name => (
              <Badge key={name} variant="info" size="sm">{name}</Badge>
            ))}
          </div>
        )}

        <div className="space-y-3">
          {sortedDifferentials.map((diff, idx) => {
            const isSelected = selectedIds.includes(diff.id);
            const isTopSuggestion = idx === 0;
            // probability is already 0–100 (mapped from similarity*100 in clinicalMappers.js)
            const pct = diff.probability != null ? Math.round(diff.probability) : null;

            // Canonical MHNexus colors from 19-probability.html
            const barFill =
              pct == null   ? '#94a3b8'
              : pct >= 70   ? '#ef4444'
              : pct >= 40   ? '#f59e0b'
              : '#22c55e';

            const riskDotColor = {
              low:    'bg-emerald-500',
              medium: 'bg-amber-500',
              high:   'bg-rose-500',
            }[diff.risk] ?? 'bg-amber-500';

            return (
              <button
                key={diff.id}
                onClick={() => handleSelectDiagnosis(diff.id)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-all duration-200 border-2 ${
                  isSelected
                    ? `border-[var(--accent-primary)] ${isDark ? 'bg-[var(--accent-primary)]/15 shadow-[0_0_0_1px_var(--accent-primary)]' : 'bg-[var(--accent-primary)]/8 shadow-[0_0_0_1px_var(--accent-primary)]'}`
                    : `border-transparent ${isDark ? 'hover:bg-white/5 hover:border-white/10' : 'hover:bg-slate-50 hover:border-slate-200'}`
                }`}
              >
                {/* Row 1: name · ICD · badges · percentage — matches 19-probability.html .head */}
                <div className="flex items-center gap-2 mb-1.5">
                  {/* Selected checkmark / index number */}
                  {isSelected ? (
                    <span className="w-5 h-5 rounded-full bg-[var(--accent-primary)] flex items-center justify-center shrink-0">
                      <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
                      </svg>
                    </span>
                  ) : (
                    <span className={`font-mono text-xs font-semibold shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                  )}
                  {/* .nm — font-weight 500, var(--slate-700) */}
                  <span
                    className="flex-1 text-sm truncate"
                    style={{ fontWeight: isSelected ? 600 : 500, color: isSelected ? 'var(--accent-primary)' : isDark ? '#e2e8f0' : 'var(--slate-700)' }}
                  >
                    {diff.name}
                  </span>
                  <span className={`text-[11px] font-mono shrink-0 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    ICD-11 · {diff.icdCode}
                  </span>
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${riskDotColor}`} />
                  {isTopSuggestion && (
                    <span className="text-[10px] font-semibold text-[var(--accent-primary)] bg-[var(--accent-primary)]/10 px-1.5 py-0.5 rounded shrink-0">
                      AI top pick
                    </span>
                  )}
                  {/* .pc — font-weight 700, tabular-nums, var(--slate-900) */}
                  {pct != null && (
                    <span
                      className="font-mono text-sm shrink-0"
                      style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: isDark ? '#f1f5f9' : 'var(--slate-900)' }}
                    >
                      {pct}%
                    </span>
                  )}
                </div>

                {/* Row 2: probability bar — 10px height, 6px radius, 0.7s CSS transition */}
                {pct != null && (
                  <div
                    style={{
                      height: 10,
                      borderRadius: 6,
                      background: isDark ? 'rgba(255,255,255,0.08)' : 'var(--slate-100)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        borderRadius: 6,
                        background: barFill,
                        width: `${pct}%`,
                        transition: 'width 0.7s cubic-bezier(0.4,0,0.2,1)',
                      }}
                    />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </GlassCard>

      {/* Re-synthesis notice */}
      {willResynth && !isGeneratingPlan && (
        <div className={`flex items-center gap-2 text-xs px-4 py-2 rounded-lg
          ${isDark ? 'bg-amber-900/20 text-amber-300 border border-amber-500/20'
                   : 'bg-amber-50    text-amber-700 border border-amber-200'}`}>
          <AlertCircle className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
          Your selection differs from the AI recommendation — the care plan will be
          re-generated specifically for{' '}
          <strong>{selectedDiagnoses.map(d => d.name).join(', ')}</strong>.
        </div>
      )}


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
