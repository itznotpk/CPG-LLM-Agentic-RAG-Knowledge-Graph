import React from 'react';
import {
  Brain,
  AlertCircle,
  CheckCircle,
  ArrowLeft,
  Sparkles,
  Target,
  Check,
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

export function DiagnosisSection() {
  const { state, confirmDiagnosis, goToStep, selectDiagnosis } = useApp();
  const { isDark } = useTheme();
  const { diagnosis, isGeneratingPlan } = state;

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
      <div className="text-center mb-8">
        <h2 className={`text-2xl font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
          AI Risk Assessment & Diagnosis
        </h2>
        <p className={isDark ? 'text-slate-400' : 'text-slate-600'}>
          Review and select the diagnosis to proceed with care plan generation
        </p>
      </div>

      {/* AI Suggested Diagnosis - Shows selected diagnoses */}
      <GlassCard className="p-6 border-[var(--accent-primary)]/50 border-2">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-[var(--accent-primary)]/20 rounded-xl">
              <Brain className="w-6 h-6 text-[var(--accent-primary)]" />
            </div>
            <div>
              <span className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Selected Diagnos{selectedDiagnoses.length === 1 ? 'is' : 'es'} ({selectedDiagnoses.length})
              </span>
              <div className="space-y-1">
                {selectedDiagnoses.map((diag, idx) => (
                  <h3 key={diag.id} className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>
                    {idx + 1}. {diag.name}
                  </h3>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 mb-4">
          {selectedDiagnoses.map((diag) => (
            <React.Fragment key={diag.id}>
              <CodeBadge code={`ICD-11: ${diag.icdCode}`} />
              <RiskBadge risk={diag.risk || 'medium'} />
            </React.Fragment>
          ))}
        </div>

        <div className={`p-4 border rounded-xl ${isDark ? 'bg-amber-900/30 border-amber-500/30' : 'bg-amber-50/50 border-amber-200/50'}`}>
          <div className="flex items-start gap-3">
            <AlertCircle className={`w-5 h-5 mt-0.5 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
            <div>
              <p className={`font-medium ${isDark ? 'text-amber-300' : 'text-amber-800'}`}>Clinical Correlation Required</p>
              <p className={`text-sm mt-1 ${isDark ? 'text-amber-200/80' : 'text-amber-700'}`}>
                This AI-generated diagnosis should be reviewed and confirmed by the treating clinician.
                You may select multiple diagnoses from the list below by clicking on them.
              </p>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Differential Diagnosis - Selectable */}
      <GlassCard className="p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
            <Target className="w-5 h-5 text-[var(--accent-primary)]" />
          </div>
          <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Differential Diagnosis</h3>
        </div>

        <div className="space-y-3">
          {sortedDifferentials.map((diff, idx) => {
            const isSelected = selectedIds.includes(diff.id);
            const isTopSuggestion = idx === 0;

            return (
              <button
                key={diff.id}
                onClick={() => handleSelectDiagnosis(diff.id)}
                className={`w-full text-left p-4 rounded-xl transition-all duration-200 border-2 ${isSelected
                  ? isDark
                    ? 'bg-[var(--accent-primary)]/20 border-[var(--accent-primary)] shadow-md'
                    : 'bg-[var(--accent-primary)]/10 border-[var(--accent-primary)] shadow-md'
                  : isDark
                    ? 'bg-white/5 border-transparent hover:bg-white/10 hover:border-[var(--accent-primary)]/50'
                    : 'bg-white/30 border-transparent hover:bg-white/50 hover:border-[var(--accent-primary)]/50'
                  }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-6 h-6 flex items-center justify-center rounded-full text-sm font-bold ${isSelected
                        ? 'bg-[var(--accent-primary)] text-white'
                        : isDark ? 'bg-[var(--accent-primary)]/30 text-slate-300' : 'bg-[var(--accent-primary)]/20 text-slate-700'
                        }`}
                    >
                      {isSelected ? <Check className="w-4 h-4" /> : idx + 1}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{diff.name}</span>
                        {isTopSuggestion && (
                          <Badge variant="primary" size="sm">
                            AI Recommended
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <CodeBadge code={`ICD-11: ${diff.icdCode}`} />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <RiskBadge risk={diff.risk} />
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </GlassCard>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
        <Button
          variant="secondary"
          size="lg"
          icon={ArrowLeft}
          onClick={handleBack}
        >
          Back
        </Button>
        <Button
          variant="primary"
          size="lg"
          icon={isGeneratingPlan ? null : CheckCircle}
          iconPosition="left"
          loading={isGeneratingPlan}
          onClick={handleConfirm}
          glow={!isGeneratingPlan}
          className="min-w-[280px]"
        >
          {isGeneratingPlan ? 'Generating Care Plan...' : `Generate Care Plan${selectedDiagnoses.length > 1 ? ` (${selectedDiagnoses.length} diagnoses)` : ''}`}
        </Button>
      </div>

      {isGeneratingPlan && (
        <div className="flex flex-col items-center gap-4 py-6 animate-fadeIn">
          <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
            <Sparkles className="w-5 h-5 animate-pulse text-[var(--accent-primary)]" />
            <span>AI is generating evidence-based care plan for {selectedDiagnoses.length === 1 ? selectedDiagnoses[0]?.name : `${selectedDiagnoses.length} diagnoses`}...</span>
          </div>
        </div>
      )}
    </div>
  );
}
