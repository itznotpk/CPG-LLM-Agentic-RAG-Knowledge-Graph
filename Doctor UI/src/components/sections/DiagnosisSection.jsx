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

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between gap-6 mb-6">
        <div>
          <span className="ds-eyebrow">STEP 2 OF 4</span>
          <h2 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Diagnosis
          </h2>
          <p className={isDark ? 'text-slate-400' : 'text-slate-600'}>
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
          <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Differential Diagnosis</h3>
        </div>

        {diagnosis?.cpgsMatched?.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mb-3">
            <span className="ds-eyebrow">CPGs consulted</span>
            {diagnosis.cpgsMatched.map(name => (
              <Badge key={name} variant="info" size="sm">{name}</Badge>
            ))}
          </div>
        )}

        <div className="space-y-2">
          {sortedDifferentials.map((diff, idx) => {
            const isSelected = selectedIds.includes(diff.id);
            const isTopSuggestion = idx === 0;
            const riskColors = {
              low: 'bg-emerald-500',
              medium: 'bg-amber-500',
              high: 'bg-rose-500',
            };

            return (
              <button
                key={diff.id}
                onClick={() => handleSelectDiagnosis(diff.id)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-all duration-200 flex items-center justify-between border-l-3 ${
                  isSelected
                    ? `border-l-[var(--accent-primary)] ${isDark ? 'bg-[var(--accent-primary)]/20' : 'bg-[var(--accent-primary)]/10'}`
                    : `border-l-transparent ${isDark ? 'hover:bg-white/5' : 'hover:bg-white/20'}`
                }`}
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <span className={`ds-numeric text-sm font-mono font-semibold shrink-0 ${
                    isSelected ? 'text-[var(--accent-primary)]' : isDark ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  <span className={`font-medium truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>
                    {diff.name}
                  </span>
                  <span className={`text-xs font-mono shrink-0 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                    ICD-11 · {diff.icdCode}
                  </span>
                  <span className="text-slate-400 text-sm shrink-0">•</span>
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${riskColors[diff.risk] || riskColors.medium}`} />
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {diff.risk}
                  </span>
                  {isTopSuggestion && (
                    <span className={`text-xs font-medium shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      · AI top pick
                    </span>
                  )}
                  {diff.probability != null && (
                    <span className={`text-xs font-mono shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      · {Math.round(diff.probability * 100)}%
                    </span>
                  )}
                </div>
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
