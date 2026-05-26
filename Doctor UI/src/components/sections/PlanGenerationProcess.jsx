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
} from 'lucide-react';
import { GlassCard, Badge } from '../shared';
import { useTheme } from '../../context/ThemeContext';

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
  const visible = events
    .filter((e) => e.stage >= 3 && e.stage <= 6)
    .slice(-8)
    .reverse();

  if (!visible.length) {
    return (
      <div className={`rounded-lg border p-4 ${isDark ? 'border-white/10 bg-slate-900/30' : 'border-slate-200 bg-slate-50'}`}>
        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Waiting for routing events...</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {visible.map((event, idx) => (
        <div
          key={`${event.stage}-${event.detail}-${idx}`}
          className={`flex items-start gap-3 rounded-lg border px-3 py-2 ${
            isDark ? 'bg-slate-900/35 border-white/10' : 'bg-white border-slate-200'
          }`}
        >
          <div className={`mt-1 w-2 h-2 rounded-full shrink-0 ${
            event.status === 'complete' ? 'bg-emerald-500' :
            event.status === 'error' ? 'bg-rose-500' :
            event.status === 'running' ? 'bg-[var(--accent-primary)] animate-pulse' :
            'bg-slate-300'
          }`} />
          <div className="min-w-0">
            <p className={`text-xs font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              Stage {event.stage} {event.name ? `- ${event.name}` : ''}
            </p>
            <p className={`text-xs mt-0.5 truncate ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              {event.detail || event.badge || 'Processing'}
            </p>
          </div>
        </div>
      ))}
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
  const cpgEvents = pipelineEvents.filter((e) => e.stage === 3 && e.eventType === 'sub_step' && e.badge !== 'excluded');
  const uniqueCpgNames = new Set(cpgEvents.map((e) => e.detail));
  const cpgCount = uniqueCpgNames.size;
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
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center border transition-all duration-300 ${
            isDark ? `${tone.darkBg} ${tone.darkBorder}` : `${tone.bg} ${tone.border}`
          }`}>
            <Icon className={`w-4.5 h-4.5 ${iconTone}`} strokeWidth={1.8} />
          </div>
          <div>
            <span className={`text-[10px] uppercase font-bold tracking-wider ${iconTone}`}>
              Active Phase: Stage {activeStage.stage}
            </span>
            <h4 className={`text-sm font-bold -mt-0.5 ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
              {activeStage.label}
            </h4>
          </div>
        </div>

        {/* Per-stage plain-English explainer — no event mirroring (Live Activity handles that) */}
        <div className={`text-xs leading-relaxed space-y-2.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          {activeStage.stage === 3 && (
            <>
              <p>The AI is looking up which Malaysian Clinical Practice Guidelines cover your patient's confirmed diagnosis, using the ICD-11 code hierarchy to step up to broader categories when no exact match exists.</p>
              <p>Only verified, scope-matched guidelines are used. Where a parent-category match was needed, a provenance badge flags this so you know the fit isn't exact.</p>
            </>
          )}
          {activeStage.stage === 4 && (
            <>
              <p>The system is reading inside the matched guidelines for the sections that directly apply — dosing rules, monitoring intervals, contraindications, referral thresholds, and red-flag escalation criteria.</p>
              <p>Generic background text is filtered out so every recommendation in your care plan traces back to a specific, relevant guideline passage.</p>
            </>
          )}
          {activeStage.stage === 5 && (
            <>
              <p>The AI is composing your care plan — deciding which medications to start, stop, or adjust; which lifestyle changes apply; which referrals are needed; and which vitals to monitor and how often.</p>
              <p>Where the retrieved evidence doesn't clearly support a decision, the system surfaces an unresolved question rather than inventing an answer.</p>
            </>
          )}
          {activeStage.stage === 6 && (
            <>
              <p>Before the plan is shown to you, an independent safety engine re-reads every medication decision and cross-checks it against this patient's comorbidities, current drugs, allergies, and organ function.</p>
              <p>Any concern — interaction, contraindication, or dose mismatch — is flagged for your acknowledgement. Nothing is hidden or auto-resolved.</p>
            </>
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
