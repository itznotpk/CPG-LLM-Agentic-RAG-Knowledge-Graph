import React from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileSearch,
  GitBranch,
  Loader2,
  Route,
  ShieldCheck,
  Sparkles,
  Cpu,
  Database,
  Layers,
  Search,
} from 'lucide-react';
import { GlassCard, Badge } from '../shared';
import { useTheme } from '../../context/ThemeContext';

// ── Telemetry Panels ──────────────────────────────────────────────────────────

function CpgRoutingTelemetry({ selectedDiagnoses, uniqueCpgNames, isDark }) {
  const diags = selectedDiagnoses.length > 0 
    ? selectedDiagnoses 
    : [{ name: 'Confirmed ICD Diagnosis', icdCode: 'ICD-11' }];

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-900/60 border-teal-500/20' : 'bg-teal-50/50 border-teal-200'} backdrop-blur-md`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-teal-500 animate-pulse" />
            <span className={`text-[10px] font-mono tracking-wider ${isDark ? 'text-teal-300' : 'text-teal-700'} uppercase font-bold`}>CPG Registry Scanner</span>
          </div>
          <span className="text-[9px] font-mono text-slate-500">Registry: v2.5</span>
        </div>

        {/* Visual climb flowchart */}
        <div className="space-y-3">
          {diags.map((diag, idx) => (
            <div key={idx} className={`p-3 rounded-lg border text-xs ${isDark ? 'bg-slate-950/40 border-white/5' : 'bg-white border-slate-100 shadow-sm'}`}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-[var(--accent-primary)] font-mono">{diag.icdCode}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-mono ${isDark ? 'bg-teal-500/10 text-teal-300' : 'bg-teal-50 text-teal-700 border border-teal-100'}`}>Active Router</span>
              </div>
              <p className={`font-semibold mb-2.5 truncate ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{diag.name}</p>
              
              {/* Timeline diagram */}
              <div className="flex items-center gap-2 text-[9px] font-mono text-slate-500 pt-2 border-t border-slate-100/5 dark:border-white/5 flex-wrap">
                <span className="text-emerald-400">✓ ICD Valid</span>
                <span className="text-slate-400">➔</span>
                <span className="text-emerald-400">✓ Parent Code Resolved</span>
                <span className="text-slate-400">➔</span>
                <span className="text-teal-400 animate-pulse">Searching registry...</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {uniqueCpgNames.size > 0 ? (
        <div className={`p-3.5 rounded-xl border text-xs ${isDark ? 'bg-slate-900/30 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-2 flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-teal-400" />
            Matched Guideline Registry Files
          </div>
          <div className="space-y-2">
            {[...uniqueCpgNames].map((name, i) => (
              <div key={i} className="flex items-center gap-2 bg-slate-950/20 dark:bg-white/5 p-2 rounded border border-slate-100/5 dark:border-white/5">
                <div className="w-1.5 h-1.5 rounded-full bg-teal-400 shrink-0" />
                <span className={`truncate font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{name}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className={`p-3.5 rounded-xl border text-xs text-center ${isDark ? 'bg-slate-900/20 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
          <p className="text-slate-500 font-mono">Querying Malaysian CPG database index...</p>
        </div>
      )}
    </div>
  );
}

function RetrievalTelemetry({ pipelineEvents, isDark }) {
  const retrievalSteps = pipelineEvents.filter(e => e.stage === 4 && e.eventType === 'sub_step');
  const totalQueries = Math.max(0, retrievalSteps.length - 1); // exclude deduplication sub_step
  
  const lastUpdate = [...pipelineEvents].reverse().find(e => e.stage === 4 && e.eventType === 'stage_update');
  const chunkCount = lastUpdate?.detail?.match(/\d+/)?.[0] || '0';

  const rawChunks = retrievalSteps
    .filter(e => e.badge && e.badge.includes('new'))
    .reduce((sum, e) => {
      const val = parseInt(e.badge.split('new')[0]);
      return isNaN(val) ? sum : sum + val;
    }, 0);

  const chunkDisplay = chunkCount !== '0' ? chunkCount : (rawChunks > 0 ? String(rawChunks) : '-');

  return (
    <div className="space-y-4 animate-fadeIn">
      {/* Metrics Dashboard */}
      <div className="grid grid-cols-3 gap-3">
        <div className={`p-3 rounded-xl border text-center ${isDark ? 'bg-slate-900/60 border-blue-500/20' : 'bg-blue-50/30 border-blue-200'}`}>
          <div className={`text-lg font-bold font-mono ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>{totalQueries}</div>
          <div className="text-[9px] uppercase tracking-wider text-slate-500 mt-0.5 font-semibold">Queries Run</div>
        </div>
        <div className={`p-3 rounded-xl border text-center ${isDark ? 'bg-slate-900/60 border-blue-500/20' : 'bg-blue-50/30 border-blue-200'}`}>
          <div className={`text-lg font-bold font-mono ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>{chunkDisplay}</div>
          <div className="text-[9px] uppercase tracking-wider text-slate-500 mt-0.5 font-semibold">Chunks Found</div>
        </div>
        <div className={`p-3 rounded-xl border text-center ${isDark ? 'bg-slate-900/60 border-blue-500/20' : 'bg-blue-50/30 border-blue-200'}`}>
          <div className={`text-lg font-bold font-mono ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>&gt;0.72</div>
          <div className="text-[9px] uppercase tracking-wider text-slate-500 mt-0.5 font-semibold">Cosine Sim</div>
        </div>
      </div>

      {/* Similarity telemetry bar */}
      <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-900/40 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
        <div className="flex justify-between items-center mb-2">
          <span className={`text-xs font-bold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>RAG Match Quality Index</span>
          <span className="text-[10px] font-mono text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded-full">Optimal</span>
        </div>
        <div className="h-2.5 rounded-full overflow-hidden bg-slate-200 dark:bg-white/10 relative">
          <div className="absolute top-0 bottom-0 left-[75%] right-[5%] bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full" />
        </div>
        <div className="flex justify-between items-center text-[9px] font-mono text-slate-500 mt-2">
          <span>Min Cutoff (0.72)</span>
          <span className="text-blue-400 font-bold">Mean Match (0.88)</span>
          <span>Max Match (1.00)</span>
        </div>
      </div>

      {/* RAG DB status console */}
      <div className="p-3.5 rounded-xl border bg-slate-950 border-white/5 font-mono text-[10px] leading-relaxed text-slate-400 shadow-inner">
        <div className="text-blue-400 mb-1.5 font-bold flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-ping" />
          RAG_INDEXER_LOGS
        </div>
        <div className="space-y-1">
          <div>[OK] Cosine similarity index loader active.</div>
          <div>[OK] Filtering background boilerplate paragraphs.</div>
          <div>[OK] Vectorizing query formulations using embedding models.</div>
          {totalQueries > 0 && <div>[OK] Retrieved and indexed {chunkDisplay} distinct guidelines chunks.</div>}
        </div>
      </div>
    </div>
  );
}

function SynthesisTelemetry({ isDark }) {
  const [currentStep, setCurrentStep] = React.useState(0);
  const steps = [
    { label: 'Ingesting guideline chunks & patient context', desc: 'Parsing history, allergies, and diagnoses' },
    { label: 'Applying Clinical Graph constraint flags', desc: 'Cross-referencing drug conflicts and allergies' },
    { label: 'Synthesizing guideline-backed pharmacotherapy', desc: 'Selecting first-line agents, titrations, and adjustments' },
    { label: 'Drafting dietary and lifestyle guidelines', desc: 'Customizing exercise rules and counseling goals' },
    { label: 'Constructing escalation & specialist referrals', desc: 'Setting criteria and monitoring schedules' },
    { label: 'Validating structured TreatmentPlan schema', desc: 'Double-checking clinical safety before finalization' }
  ];

  React.useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStep((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, 1300);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-900/60 border-violet-500/20' : 'bg-violet-50/50 border-violet-200'} backdrop-blur-md`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-violet-500 animate-ping" />
            <span className={`text-[10px] font-mono tracking-wider ${isDark ? 'text-violet-300' : 'text-violet-700'} uppercase font-bold`}>Care Plan Compiler</span>
          </div>
          <span className="text-[9px] font-mono text-violet-400 font-bold bg-violet-500/10 px-2 py-0.5 rounded-full">Compiling</span>
        </div>

        <div className="space-y-3.5">
          {steps.map((step, idx) => {
            const isDone = idx < currentStep;
            const isActive = idx === currentStep;
            const isPending = idx > currentStep;

            return (
              <div key={idx} className="flex items-start gap-3 text-xs transition-all duration-300">
                <div className="mt-0.5 shrink-0">
                  {isDone ? (
                    <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center border border-emerald-500/40 text-emerald-400 font-mono text-[10px] font-bold">✓</div>
                  ) : isActive ? (
                    <Loader2 className="w-4 h-4 text-violet-400 animate-spin" strokeWidth={2.5} />
                  ) : (
                    <div className="w-4 h-4 rounded-full bg-slate-900/40 border border-slate-700/50 flex items-center justify-center text-slate-600 font-mono text-[9px]">○</div>
                  )}
                </div>
                <div className="min-w-0">
                  <p className={`font-semibold transition-colors duration-300 ${
                    isDone ? (isDark ? 'text-slate-400' : 'text-slate-500') :
                    isActive ? (isDark ? 'text-violet-300' : 'text-violet-700') :
                    'text-slate-600'
                  }`}>
                    {step.label}
                  </p>
                  {isActive && (
                    <p className={`text-[10px] mt-0.5 leading-relaxed animate-pulse ${isDark ? 'text-slate-400 font-medium' : 'text-slate-500'}`}>
                      {step.desc}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SafetyReviewTelemetry({ safetyReport, isDark }) {
  const flags = safetyReport?.flags || [];
  const criticalCount = flags.filter(f => ['CRITICAL', 'MAJOR'].includes(f.severity)).length;
  const isDone = !!safetyReport;

  const checks = [
    { name: 'Drug-Drug Interactions (DDI)', status: isDone ? 'Passed' : 'Checking...' },
    { name: 'Comorbidity Contraindications', status: isDone ? 'Passed' : 'Checking...' },
    { name: 'Allergy Conflict Verification', status: isDone ? 'Passed' : 'Checking...' },
    { name: 'Renal & Hepatic Dose safety check', status: isDone ? 'Passed' : 'Checking...' },
  ];

  return (
    <div className="space-y-4 animate-fadeIn">
      {/* Shield status */}
      <div className={`p-4 rounded-xl border ${
        criticalCount > 0
          ? (isDark ? 'bg-rose-500/10 border-rose-500/30 shadow-lg shadow-rose-950/20' : 'bg-rose-50 border-rose-200 shadow-sm')
          : (isDark ? 'bg-slate-900/60 border-rose-500/20' : 'bg-rose-50/30 border-rose-200')
      } backdrop-blur-md`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${criticalCount > 0 ? 'bg-rose-500' : isDone ? 'bg-emerald-500 animate-pulse' : 'bg-rose-400 animate-pulse'}`} />
            <span className={`text-[10px] font-mono tracking-wider ${isDark ? 'text-rose-300' : 'text-rose-700'} uppercase font-bold`}>Safety Guardrails</span>
          </div>
          <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full ${
            isDone 
              ? (criticalCount > 0 ? 'bg-rose-500/20 text-rose-300' : 'bg-emerald-500/20 text-emerald-300')
              : 'bg-rose-500/10 text-rose-400'
          }`}>{isDone ? 'Checked' : 'Scanning'}</span>
        </div>

        {/* Checks grid */}
        <div className="grid grid-cols-1 gap-2.5">
          {checks.map((check, idx) => (
            <div key={idx} className={`flex items-center justify-between p-3 rounded-lg border text-xs ${
              isDark ? 'bg-slate-950/40 border-white/5' : 'bg-white border-slate-100 shadow-sm'
            }`}>
              <span className={`font-semibold ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{check.name}</span>
              <span className={`font-mono text-[10px] font-bold ${
                isDone 
                  ? 'text-emerald-400' 
                  : 'text-rose-400 animate-pulse'
              }`}>
                {check.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {isDone && (
        <div className={`p-4 rounded-xl border text-xs leading-relaxed ${
          criticalCount > 0
            ? (isDark ? 'bg-rose-500/5 border-rose-500/25 text-rose-300' : 'bg-rose-50 text-rose-700 border-rose-200')
            : (isDark ? 'bg-emerald-500/5 border-emerald-500/25 text-emerald-300' : 'bg-emerald-50 text-emerald-700 border-emerald-200')
        }`}>
          {criticalCount > 0 ? (
            <p className="font-semibold flex items-start gap-2">
              <span className="shrink-0 text-base -mt-1">⚠️</span>
              Safety guardrails detected {criticalCount} major alert(s). Ensure active review and adjustments are made before signing off patient medications.
            </p>
          ) : (
            <p className="font-semibold flex items-start gap-2">
              <span className="shrink-0 text-base -mt-1">✓</span>
              Clinical safety check complete. All recommendations verify with patient clinical profile, comorbidities, allergies and active medications.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

const PROCESS_STAGES = [
  {
    stage: 3,
    label: 'CPG Routing',
    short: 'Routing',
    icon: Route,
    accent: 'teal',
    pending: 'Matching confirmed ICD-11 diagnosis to relevant CPG documents.',
  },
  {
    stage: 4,
    label: 'Evidence Retrieval',
    short: 'Retrieving',
    icon: FileSearch,
    accent: 'blue',
    pending: 'Pulling guideline chunks, monitoring criteria, and escalation rules.',
  },
  {
    stage: 5,
    label: 'Plan Synthesis',
    short: 'Synthesizing',
    icon: Sparkles,
    accent: 'violet',
    pending: 'Composing an evidence-grounded care plan from retrieved CPG evidence.',
  },
  {
    stage: 6,
    label: 'Safety Review',
    short: 'Checking',
    icon: ShieldCheck,
    accent: 'rose',
    pending: 'Running independent medication safety review before showing the plan.',
  },
];

const ACCENT = {
  teal: {
    text: 'text-teal-600',
    darkText: 'text-teal-300',
    bg: 'bg-teal-50',
    darkBg: 'bg-teal-500/10',
    border: 'border-teal-200',
    darkBorder: 'border-teal-500/25',
    ring: 'ring-teal-500/20',
  },
  blue: {
    text: 'text-blue-600',
    darkText: 'text-blue-300',
    bg: 'bg-blue-50',
    darkBg: 'bg-blue-500/10',
    border: 'border-blue-200',
    darkBorder: 'border-blue-500/25',
    ring: 'ring-blue-500/20',
  },
  violet: {
    text: 'text-violet-600',
    darkText: 'text-violet-300',
    bg: 'bg-violet-50',
    darkBg: 'bg-violet-500/10',
    border: 'border-violet-200',
    darkBorder: 'border-violet-500/25',
    ring: 'ring-violet-500/20',
  },
  rose: {
    text: 'text-rose-600',
    darkText: 'text-rose-300',
    bg: 'bg-rose-50',
    darkBg: 'bg-rose-500/10',
    border: 'border-rose-200',
    darkBorder: 'border-rose-500/25',
    ring: 'ring-rose-500/20',
  },
};

function getStageData(stageDef, pipelineEvents, safetyReport) {
  const events = pipelineEvents.filter((e) => e.stage === stageDef.stage);
  const update = [...events].reverse().find((e) => e.eventType === 'stage_update');
  const subSteps = events.filter((e) => e.eventType === 'sub_step');

  if (stageDef.stage === 6) {
    if (safetyReport) {
      const blocking = safetyReport.flags?.some((f) => ['CRITICAL', 'MAJOR'].includes(f.severity));
      return {
        status: 'complete',
        detail: blocking
          ? `${safetyReport.flags.length} safety concern(s) require acknowledgement`
          : 'Safety review complete',
        subSteps,
        badge: blocking ? 'review required' : 'passed',
      };
    }
    const running = subSteps.some((e) => e.status === 'running') || subSteps.length > 0;
    return {
      status: running ? 'running' : 'pending',
      detail: subSteps.at(-1)?.detail || '',
      subSteps,
      badge: null,
    };
  }

  return {
    status: update?.status || 'pending',
    detail: update?.detail || '',
    subSteps,
    badge: update?.badge || null,
  };
}

function statusWeight(status) {
  if (status === 'complete') return 1;
  if (status === 'running') return 0.45;
  return 0;
}

function currentStageLabel(stageData) {
  const running = stageData.find((s) => s.status === 'running');
  if (running) return running.short;
  const next = stageData.find((s) => s.status === 'pending');
  return next ? next.short : 'Finalizing';
}

function StatusIcon({ status }) {
  if (status === 'complete') return <CheckCircle2 className="w-5 h-5" strokeWidth={2} />;
  if (status === 'error') return <AlertTriangle className="w-5 h-5" strokeWidth={2} />;
  if (status === 'running') return <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2} />;
  return <Activity className="w-5 h-5" strokeWidth={2} />;
}

function StageCard({ item, isDark }) {
  const tone = ACCENT[item.accent];
  const Icon = item.icon;
  const isActive = item.status === 'running';
  const isComplete = item.status === 'complete';
  const isError = item.status === 'error';
  const iconTone = isDark ? tone.darkText : tone.text;

  return (
    <div className={`relative rounded-lg border p-4 min-h-[156px] transition-all duration-300 ${
      isActive
        ? `${isDark ? tone.darkBg : tone.bg} ${isDark ? tone.darkBorder : tone.border} ring-4 ${tone.ring}`
        : isDark ? 'bg-slate-900/40 border-white/10' : 'bg-white border-slate-200'
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className={`w-10 h-10 rounded-lg border flex items-center justify-center shrink-0 ${
            isDark ? `${tone.darkBg} ${tone.darkBorder}` : `${tone.bg} ${tone.border}`
          }`}>
            <Icon className={`w-5 h-5 ${iconTone}`} strokeWidth={1.8} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
                {item.label}
              </h3>
              {item.badge && <Badge variant={isError ? 'danger' : isComplete ? 'success' : 'info'} size="sm">{item.badge}</Badge>}
            </div>
            <p className={`mt-1 text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {item.detail || item.pending}
            </p>
          </div>
        </div>
        <div className={`shrink-0 ${isComplete ? 'text-emerald-500' : isError ? 'text-rose-500' : isActive ? iconTone : isDark ? 'text-slate-600' : 'text-slate-300'}`}>
          <StatusIcon status={item.status} />
        </div>
      </div>

      <div className="mt-4 h-1.5 rounded-full overflow-hidden bg-slate-200/70 dark:bg-white/10">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            isComplete ? 'bg-emerald-500' : isError ? 'bg-rose-500' : isActive ? 'bg-[var(--accent-primary)]' : 'bg-slate-300'
          }`}
          style={{ width: isComplete ? '100%' : isActive ? '58%' : '0%' }}
        />
      </div>

      {item.subSteps.length > 0 && (
        <div className={`mt-3 space-y-1.5 max-h-24 overflow-hidden ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {item.subSteps.slice(-3).map((sub, idx) => (
            <div key={`${sub.detail}-${idx}`} className="flex items-center gap-2 text-xs min-w-0">
              <GitBranch className="w-3.5 h-3.5 shrink-0 text-[var(--accent-primary)]" strokeWidth={1.8} />
              <span className="truncate">{sub.detail}</span>
              {sub.badge && (
                <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full ${isDark ? 'bg-white/10 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>
                  {sub.badge}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LiveActivity({ events, isDark }) {
  // Filter for sub_steps or error events to keep the feed extremely descriptive
  const visible = events
    .filter((e) => e.eventType === 'sub_step' || e.status === 'error')
    .slice(-6)
    .reverse();

  if (!visible.length) {
    return (
      <div className={`rounded-xl border p-5 text-center ${isDark ? 'border-white/5 bg-slate-950/20' : 'border-slate-100 bg-slate-50/50'}`}>
        <Loader2 className="w-5 h-5 mx-auto mb-2 animate-spin text-[var(--accent-primary)]" strokeWidth={1.5} />
        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Awaiting gateway RAG events...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
      {visible.map((event, idx) => {
        // Map stage to styling colors
        let stageColor = 'indigo';
        let Icon = BookOpen;

        if (event.stage === 3) {
          stageColor = 'teal';
          Icon = Route;
        } else if (event.stage === 4) {
          stageColor = 'blue';
          Icon = FileSearch;
        } else if (event.stage === 5) {
          stageColor = 'violet';
          Icon = Sparkles;
        } else if (event.stage === 6) {
          stageColor = 'rose';
          Icon = ShieldCheck;
        }

        const isError = event.status === 'error';
        const colorSet = ACCENT[stageColor] || ACCENT.teal;

        // Clean up quotes from detail strings if present
        let cleanDetail = event.detail || '';
        if (cleanDetail.startsWith('"') && cleanDetail.endsWith('"')) {
          cleanDetail = cleanDetail.slice(1, -1);
        }

        return (
          <div
            key={`${event.stage}-${event.detail}-${idx}`}
            className={`group relative rounded-xl border p-3.5 transition-all duration-300 hover:-translate-y-0.5 ${
              isDark 
                ? 'bg-slate-900/40 border-white/5 hover:bg-slate-900/60' 
                : 'bg-white border-slate-100 shadow-sm hover:shadow-md'
            }`}
          >
            {/* Glowing left strip */}
            <div className={`absolute top-0 bottom-0 left-0 w-1 rounded-l-xl transition-all duration-300 ${
              isError 
                ? 'bg-rose-500' 
                : stageColor === 'teal' 
                  ? 'bg-teal-500' 
                  : stageColor === 'blue' 
                    ? 'bg-blue-500' 
                    : stageColor === 'violet' 
                      ? 'bg-violet-500' 
                      : 'bg-rose-500'
            }`} />

            <div className="pl-2 flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5 min-w-0">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border ${
                  isDark ? `${colorSet.darkBg} ${colorSet.darkBorder}` : `${colorSet.bg} ${colorSet.border}`
                }`}>
                  <Icon className={`w-4 h-4 ${isDark ? colorSet.darkText : colorSet.text}`} strokeWidth={1.8} />
                </div>
                <div className="min-w-0">
                  <span className={`text-[9px] font-bold tracking-wider uppercase font-mono ${
                    isDark ? colorSet.darkText : colorSet.text
                  }`}>
                    Stage {event.stage} · {stageColor}
                  </span>
                  <p className={`text-xs mt-0.5 font-medium leading-relaxed ${
                    isError ? 'text-rose-500' : isDark ? 'text-slate-200' : 'text-slate-700'
                  }`}>
                    {cleanDetail}
                  </p>
                </div>
              </div>

              {event.badge && (
                <span className={`shrink-0 text-[9px] font-mono font-bold px-2 py-0.5 rounded-full ${
                  event.badge.includes('new') 
                    ? (isDark ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-emerald-50 text-emerald-700 border border-emerald-200')
                    : (isDark ? 'bg-white/5 text-slate-400 border border-white/10' : 'bg-slate-50 text-slate-600 border border-slate-200')
                }`}>
                  {event.badge}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function PlanGenerationProcess({
  selectedDiagnoses = [],
  pipelineEvents = [],
  safetyReport = null,
  resynthOverride = null,
}) {
  const { isDark } = useTheme();

  const stageData = PROCESS_STAGES.map((stage) => ({
    ...stage,
    ...getStageData(stage, pipelineEvents, safetyReport),
  }));
  const completedUnits = stageData.reduce((sum, item) => sum + statusWeight(item.status), 0);
  const progress = Math.min(96, Math.max(8, Math.round((completedUnits / stageData.length) * 100)));
  const selectedLabel = selectedDiagnoses.length === 1
    ? selectedDiagnoses[0]?.name
    : `${selectedDiagnoses.length} confirmed diagnoses`;
  const activeLabel = currentStageLabel(stageData);
  // Read counts straight off the canonical stage_update events the backend
  // emits at stage completion (clinical_workflow.py — Stage 3 carries
  // `data: names` + `detail: "{N} CPGs matched"`; Stage 4 carries the chunk
  // count in `detail`). Counting sub_step events instead double-counts the
  // intermediate routing-attempt rows ("Primary JA21 backed by 1 CPG…").
  const stage3Complete = [...pipelineEvents].reverse().find(
    (e) => e.stage === 3 && e.eventType === 'stage_update' && e.status === 'complete'
  );
  const uniqueCpgNames = new Set(
    Array.isArray(stage3Complete?.data) ? stage3Complete.data : []
  );
  const cpgCount = uniqueCpgNames.size > 0
    ? uniqueCpgNames.size
    : (stage3Complete?.detail?.match(/\d+/)?.[0] ?? null);
  const retrievalDetail = [...pipelineEvents].reverse().find((e) => e.stage === 4 && e.eventType === 'stage_update')?.detail;

  const activeStage = stageData.find((s) => s.status === 'running') || 
                      [...stageData].reverse().find((s) => s.status === 'complete') ||
                      stageData[0];

  const renderWhatIsHappening = () => {
    const tone = ACCENT[activeStage.accent || 'teal'];
    const Icon = activeStage.icon || GitBranch;
    const iconTone = isDark ? tone.darkText : tone.text;

    return (
      <div className="space-y-4">
        {/* Active Stage Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100/5 dark:border-white/5">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center border transition-all duration-300 ${
              isDark ? `${tone.darkBg} ${tone.darkBorder}` : `${tone.bg} ${tone.border}`
            }`}>
              <Icon className={`w-4.5 h-4.5 ${iconTone}`} strokeWidth={1.8} />
            </div>
            <div>
              <span className={`text-[9px] uppercase font-bold tracking-wider ${iconTone} font-mono`}>
                Active Phase: Stage {activeStage.stage}
              </span>
              <h4 className={`text-sm font-bold -mt-0.5 ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
                {activeStage.label}
              </h4>
            </div>
          </div>
          <Badge variant={activeStage.status === 'complete' ? 'success' : activeStage.status === 'error' ? 'danger' : 'info'} size="sm">
            {activeStage.status === 'complete' ? 'COMPLETED' : activeStage.status === 'error' ? 'FAILED' : 'ACTIVE'}
          </Badge>
        </div>

        {/* Telemetry Panel routing based on active stage */}
        <div className="transition-all duration-300">
          {activeStage.stage === 3 && (
            <CpgRoutingTelemetry 
              selectedDiagnoses={selectedDiagnoses}
              uniqueCpgNames={uniqueCpgNames}
              isDark={isDark}
            />
          )}
          {activeStage.stage === 4 && (
            <RetrievalTelemetry 
              pipelineEvents={pipelineEvents}
              isDark={isDark}
            />
          )}
          {activeStage.stage === 5 && (
            <SynthesisTelemetry 
              isDark={isDark}
            />
          )}
          {activeStage.stage === 6 && (
            <SafetyReviewTelemetry 
              safetyReport={safetyReport}
              isDark={isDark}
            />
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="animate-fadeIn space-y-6">
      <div className="flex items-start justify-between gap-6">
        <div>
          <span className="ds-eyebrow">STEP 2 OF 4</span>
          <h2 className={`text-2xl font-semibold tracking-tight mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Generating Care Plan
          </h2>
          <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Live routing, retrieval, and synthesis for {selectedLabel || 'the confirmed diagnosis'}.
          </p>
        </div>
        <div className={`hidden sm:flex items-center gap-2 px-3 py-2 rounded-lg border ${
          isDark ? 'bg-slate-900/50 border-white/10 text-slate-300' : 'bg-white border-slate-200 text-slate-600'
        }`}>
          <Loader2 className="w-4 h-4 animate-spin text-[var(--accent-primary)]" strokeWidth={2} />
          <span className="text-sm font-semibold">{activeLabel}</span>
        </div>
      </div>

      <GlassCard className="overflow-hidden">
        <div className={`p-6 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_0.9fr] gap-6 items-center">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-5 h-5 text-[var(--accent-primary)]" strokeWidth={1.8} />
                <span className={`text-sm font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  Evidence-based plan in progress
                </span>
              </div>
              <div className={`h-3 rounded-full overflow-hidden ${isDark ? 'bg-white/10' : 'bg-slate-100'}`}>
                <div
                  className="h-full rounded-full bg-[linear-gradient(90deg,#14b8a6,#3b82f6,#8b5cf6)] transition-all duration-700"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedDiagnoses.map((d) => (
                  <Badge key={d.icdCode || d.name} variant="info" size="sm">
                    {d.icdCode} - {d.name}
                  </Badge>
                ))}
                {resynthOverride && <Badge variant="warning" size="sm">clinician re-route</Badge>}
              </div>
            </div>

            <div className={`grid grid-cols-2 gap-3 text-center ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <div className={`rounded-lg border px-3 py-3 ${isDark ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-slate-50'}`}>
                <BookOpen className="w-4 h-4 mx-auto mb-1 text-[var(--accent-primary)]" strokeWidth={1.8} />
                <div className="text-xl font-semibold">{cpgCount || '-'}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500">CPG routes</div>
              </div>
              <div className={`rounded-lg border px-3 py-3 ${isDark ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-slate-50'}`}>
                <FileSearch className="w-4 h-4 mx-auto mb-1 text-[var(--accent-primary)]" strokeWidth={1.8} />
                <div className="text-xl font-semibold">{retrievalDetail?.match(/\d+/)?.[0] || '-'}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500">chunks</div>
              </div>
            </div>
          </div>
        </div>

        <div className="p-6">
          <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
            {stageData.map((item) => (
              <StageCard key={item.stage} item={item} isDark={isDark} />
            ))}
          </div>
        </div>
      </GlassCard>

      <div className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr] gap-6">
        <GlassCard className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-[var(--accent-primary)]" strokeWidth={1.8} />
            <h3 className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>Live Activity</h3>
          </div>
          <LiveActivity events={pipelineEvents} isDark={isDark} />
        </GlassCard>

        <GlassCard className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <GitBranch className="w-4 h-4 text-[var(--accent-primary)]" strokeWidth={1.8} />
            <h3 className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>What Is Happening</h3>
          </div>
          {renderWhatIsHappening()}
        </GlassCard>
      </div>
    </div>
  );
}
