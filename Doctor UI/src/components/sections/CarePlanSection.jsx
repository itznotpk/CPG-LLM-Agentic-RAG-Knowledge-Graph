import React, { useState } from 'react';
import { getTodayUTC8 } from '../../utils/timezone';
import {
  ClipboardList,
  Stethoscope,
  Pill,
  Activity,
  Calendar,
  BookOpen,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Heart,
  TrendingUp,
  Send,
  Shield,
  LayoutGrid,
  Clock,
} from 'lucide-react';
import {
  GlassCard,
  Button,
  Badge,
  WorkflowActions,
  WORKFLOW_STATES,
  TextToSpeechButton,
} from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { PipelineProgress } from './PipelineProgress';
import { SafetyReviewBanner } from './SafetyReviewBanner';
import { GraphNavigatorPanel } from './GraphNavigatorPanel';

/* ============================================================
   Section card (collapsible) — used inside each tab
   ============================================================ */
function Section({ title, icon: Icon, children, defaultOpen = true, rightAction, count, kind, noCollapse = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const { isDark } = useTheme();
  const isRedFlag = kind === 'red-flags';
  const open = noCollapse ? true : isOpen;

  return (
    <GlassCard className={`overflow-hidden ${isRedFlag ? (isDark ? 'border border-red-500/30' : 'border border-red-200') : ''}`}>
      <div
        className={`flex items-center justify-between p-4 ${!noCollapse ? `cursor-pointer ${isDark ? 'hover:bg-white/5' : 'hover:bg-white/10'}` : ''}`}
        onClick={noCollapse ? undefined : () => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-3 flex-1">
          <div className={`p-2 rounded-xl ${isRedFlag
            ? (isDark ? 'bg-red-500/20 text-red-300' : 'bg-red-100 text-red-700')
            : 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)]'}`}>
            <Icon className="w-4 h-4" strokeWidth={1.6} />
          </div>
          <h3 className={`text-base font-semibold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>{title}</h3>
          {count != null && (
            <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full ${isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>{count}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {rightAction}
          {!noCollapse && (open
            ? <ChevronUp className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`} strokeWidth={1.5} />
            : <ChevronDown className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`} strokeWidth={1.5} />)}
        </div>
      </div>
      {open && <div className="px-4 pb-4">{children}</div>}
    </GlassCard>
  );
}

/* ============================================================
   Clinical Summary — hero card
   ============================================================ */
function ClinicalSummary({ summary, readSummaryButton }) {
  const { isDark } = useTheme();
  return (
    <GlassCard className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-[0.08em] font-semibold text-[var(--accent-primary)] mb-2">Clinical Summary</div>
          <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{summary}</p>
        </div>
        {readSummaryButton}
      </div>
    </GlassCard>
  );
}

/* ============================================================
   Medications table — one consolidated table, action-tagged
   ============================================================ */
const ACTION_STYLES = {
  stop:     { label: 'STOP',     light: 'bg-red-100 text-red-700',         dark: 'bg-red-500/20 text-red-300' },
  start:    { label: 'START',    light: 'bg-emerald-100 text-emerald-700', dark: 'bg-emerald-500/20 text-emerald-300' },
  change:   { label: 'CHANGE',   light: 'bg-amber-100 text-amber-700',     dark: 'bg-amber-500/20 text-amber-300' },
  continue: { label: 'CONTINUE', light: 'bg-blue-100 text-blue-700',       dark: 'bg-blue-500/20 text-blue-300' },
};
function ActionTag({ action }) {
  const { isDark } = useTheme();
  const s = ACTION_STYLES[action];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${isDark ? s.dark : s.light}`}>{s.label}</span>
  );
}
function MedicationRow({ med, action }) {
  const { isDark } = useTheme();
  return (
    <tr className={`border-b ${isDark ? 'border-white/5' : 'border-slate-100'} last:border-b-0`}>
      <td className="py-3 pr-4 align-top w-[80px]"><ActionTag action={action} /></td>
      <td className="py-3 pr-4 align-top">
        <div className={`font-semibold text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</div>
        <div className={`mt-0.5 text-xs font-mono ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {action === 'change' ? (
            <>
              <span className="line-through opacity-60">{med.previousDose}</span>
              <span className="mx-1.5">→</span>
              <span className={`font-semibold ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>{med.newDose}</span>
            </>
          ) : (
            <span>{med.dose}</span>
          )}
        </div>
      </td>
      <td className="py-3 pr-4 align-top">
        {med.reason && <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{med.reason}</p>}
        {med.instructions && (
          <p className={`mt-1 inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded ${isDark ? 'bg-amber-500/15 text-amber-300' : 'bg-amber-100 text-amber-700'}`}>
            <AlertCircle className="w-3 h-3" strokeWidth={1.7} /> {med.instructions}
          </p>
        )}
        {med.kiv && (
          <p className={`mt-1 inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded ${isDark ? 'bg-blue-500/15 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>{med.kiv}</p>
        )}
      </td>
      <td className="py-3 align-top w-[140px]">
        {med.cpgRef && <span className={`text-[11px] font-mono ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>{med.cpgRef}</span>}
      </td>
    </tr>
  );
}
function MedicationsTable({ medications }) {
  const { isDark } = useTheme();
  const ordered = [
    ...(medications.stop || []).map((m) => ({ med: m, action: 'stop' })),
    ...(medications.start || []).map((m) => ({ med: m, action: 'start' })),
    ...(medications.change || []).map((m) => ({ med: m, action: 'change' })),
    ...(medications.continue || []).map((m) => ({ med: m, action: 'continue' })),
  ];
  if (ordered.length === 0) return <p className="text-sm text-slate-500">No medication changes.</p>;
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-left">
        <thead>
          <tr className={isDark ? 'text-slate-500' : 'text-slate-500'}>
            <th className="py-2 pr-4 text-[10px] uppercase tracking-wider font-semibold">Action</th>
            <th className="py-2 pr-4 text-[10px] uppercase tracking-wider font-semibold">Medication</th>
            <th className="py-2 pr-4 text-[10px] uppercase tracking-wider font-semibold">Reason &amp; instructions</th>
            <th className="py-2 text-[10px] uppercase tracking-wider font-semibold">CPG</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map(({ med, action }) => <MedicationRow key={`${action}-${med.id}`} med={med} action={action} />)}
        </tbody>
      </table>
    </div>
  );
}

/* ============================================================
   Red flag row — title/subtitle split on " — ", collapsible detail
   ============================================================ */
function RedFlagRow({ text }) {
  const { isDark } = useTheme();
  const dashIdx = text ? text.indexOf(' — ') : -1;
  const flagTitle = dashIdx !== -1 ? text.slice(0, dashIdx).trim() : text;
  const flagSub   = dashIdx !== -1 ? text.slice(dashIdx + 3).trim() : null;
  return (
    <div className={`py-2.5 border-b last:border-b-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${isDark ? 'bg-red-500/20 text-red-300' : 'bg-red-100 text-red-700'}`}>
          <Check className="w-3 h-3" strokeWidth={2.4} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-semibold leading-snug ${isDark ? 'text-red-400' : 'text-red-600'}`}>{flagTitle}</div>
          {flagSub && (
            <div className={`text-xs mt-0.5 leading-snug ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>{flagSub}</div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   List row — Interventions / Monitoring / Lifestyle / Referrals / Red flags
   ============================================================ */
function ListRow({ bulletTone = 'ok', title, sub, tag, tagTone, noCollapse = false, scheduleBelow = false }) {
  const { isDark } = useTheme();
  const [expanded, setExpanded] = useState(false);
  const bulletColor = {
    ok:     isDark ? 'bg-emerald-500/20 text-emerald-300' : 'bg-emerald-100 text-emerald-700',
    info:   isDark ? 'bg-blue-500/20 text-blue-300'       : 'bg-blue-100 text-blue-700',
    warn:   isDark ? 'bg-amber-500/20 text-amber-300'     : 'bg-amber-100 text-amber-700',
    danger: isDark ? 'bg-red-500/20 text-red-300'         : 'bg-red-100 text-red-700',
  }[bulletTone];
  const tagColor = {
    default: isDark ? 'bg-white/10 text-slate-300' : 'bg-slate-100 text-slate-600',
    accent:  isDark ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]' : 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]',
    warn:    isDark ? 'bg-amber-500/15 text-amber-300' : 'bg-amber-100 text-amber-700',
    danger:  isDark ? 'bg-red-500/15 text-red-300' : 'bg-red-100 text-red-700',
  }[tagTone || 'default'];
  return (
    <div className={`py-2.5 border-b last:border-b-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${bulletColor}`}>
          <Check className="w-3 h-3" strokeWidth={2.4} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-medium leading-snug ${isDark ? 'text-white' : 'text-slate-800'}`}>{title}</div>
          {scheduleBelow && tag && (
            <div className="mt-1 flex items-center gap-1.5">
              <Clock className="w-3 h-3 flex-shrink-0 text-[var(--accent-primary)]" strokeWidth={2} />
              <span className="text-[11px] font-medium text-[var(--accent-primary)] leading-snug">{tag}</span>
            </div>
          )}
        </div>
        {!scheduleBelow && (
          <div className="flex items-center gap-2 flex-shrink-0">
            {tag && (
              <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${tagColor}`}>{tag}</span>
            )}
            {sub && !noCollapse && (
              <button
                onClick={() => setExpanded(v => !v)}
                className={`p-0.5 rounded transition-colors ${isDark ? 'text-slate-400 hover:bg-white/10' : 'text-slate-400 hover:bg-black/5'}`}
                aria-label={expanded ? 'Collapse' : 'Expand'}
              >
                {expanded ? <ChevronUp className="w-3.5 h-3.5" strokeWidth={2} /> : <ChevronDown className="w-3.5 h-3.5" strokeWidth={2} />}
              </button>
            )}
          </div>
        )}
      </div>
      {(noCollapse ? sub : (expanded && sub)) && (
        <div className={`mt-1.5 ml-8 text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {sub}
        </div>
      )}
    </div>
  );
}

function MedListRow({ bulletTone = 'ok', drugName, dose, description, tag, tagTone }) {
  const { isDark } = useTheme();
  const [expanded, setExpanded] = useState(false);

  const bulletColor = {
    ok:     isDark ? 'bg-emerald-500/20 text-emerald-300' : 'bg-emerald-100 text-emerald-700',
    info:   isDark ? 'bg-blue-500/20 text-blue-300'       : 'bg-blue-100 text-blue-700',
    warn:   isDark ? 'bg-amber-500/20 text-amber-300'     : 'bg-amber-100 text-amber-700',
    danger: isDark ? 'bg-red-500/20 text-red-300'         : 'bg-red-100 text-red-700',
  }[bulletTone];
  const tagColor = {
    default: isDark ? 'bg-white/10 text-slate-300' : 'bg-slate-100 text-slate-600',
    accent:  isDark ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]' : 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]',
    warn:    isDark ? 'bg-amber-500/15 text-amber-300' : 'bg-amber-100 text-amber-700',
    danger:  isDark ? 'bg-red-500/15 text-red-300' : 'bg-red-100 text-red-700',
  }[tagTone || 'default'];
  const nameColor = {
    ok:     isDark ? 'text-emerald-300' : 'text-emerald-700',
    warn:   isDark ? 'text-amber-300'   : 'text-amber-700',
    danger: isDark ? 'text-red-400'     : 'text-red-600',
    info:   isDark ? 'text-blue-300'    : 'text-blue-700',
  }[bulletTone] || (isDark ? 'text-white' : 'text-slate-800');

  return (
    <div className={`py-2.5 border-b last:border-b-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${bulletColor}`}>
          <Check className="w-3 h-3" strokeWidth={2.4} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-semibold leading-snug ${nameColor}`}>{drugName}</div>
          {dose && (
            <div className={`text-xs mt-0.5 leading-snug ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
              {dose}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {tag && (
            <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${tagColor}`}>{tag}</span>
          )}
          {description && (
            <button
              onClick={() => setExpanded(v => !v)}
              className={`p-0.5 rounded hover:bg-black/5 transition-colors ${isDark ? 'text-slate-400 hover:bg-white/10' : 'text-slate-400'}`}
              aria-label={expanded ? 'Collapse' : 'Expand'}
            >
              {expanded
                ? <ChevronUp className="w-3.5 h-3.5" strokeWidth={2} />
                : <ChevronDown className="w-3.5 h-3.5" strokeWidth={2} />
              }
            </button>
          )}
        </div>
      </div>
      {expanded && description && (
        <div className={`mt-2 ml-8 text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {description}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Follow-up timeline + TCA/status card
   ============================================================ */
function parseSuggestedDate(instruction) {
  if (!instruction) return null;
  const text = instruction.toLowerCase();
  const match = text.match(/(\d+)\s*(day|week|month|year)/);
  if (!match) return null;
  const n = parseInt(match[1], 10);
  const unit = match[2];
  const d = new Date();
  if (unit === 'day')   d.setDate(d.getDate() + n);
  if (unit === 'week')  d.setDate(d.getDate() + n * 7);
  if (unit === 'month') d.setMonth(d.getMonth() + n);
  if (unit === 'year')  d.setFullYear(d.getFullYear() + n);
  return d.toISOString().split('T')[0];
}
function FollowUpItem({ timeline, body, isDark }) {
  return (
    <div className="relative py-2">
      <div className={`absolute -left-[18px] top-3 w-3 h-3 rounded-full border-2 ${isDark ? 'bg-slate-900 border-[var(--accent-primary)]' : 'bg-white border-[var(--accent-primary)]'}`} />
      <div className="text-[11px] font-mono font-semibold uppercase tracking-wider text-[var(--accent-primary)]">{timeline}</div>
      {body && (
        <p className={`text-sm leading-relaxed mt-0.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{body}</p>
      )}
    </div>
  );
}

function FollowUpBlock({ followUp }) {
  const { isDark } = useTheme();
  const { state, dispatch } = useApp();
  const currentStatus = state.patientStatus || 'active';
  const nextReviewDate = state.nextReviewDate || '';

  const items = Array.isArray(followUp) ? followUp : followUp ? [followUp] : [];
  const suggestedDate = items.reduce((earliest, it) => {
    const d = parseSuggestedDate(it);
    if (!d) return earliest;
    return !earliest || d < earliest ? d : earliest;
  }, null);

  const statusOptions = [
    { value: 'active', label: 'Active' },
    { value: 'follow-up', label: 'Follow-up' },
    { value: 'discharged', label: 'Discharged' },
  ];

  const parseInstruction = (text) => {
    const colonIdx = text.indexOf(':');
    if (colonIdx === -1) return { timeline: '—', body: text };
    return { timeline: text.slice(0, colonIdx).trim(), body: text.slice(colonIdx + 1).trim() };
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="relative pl-7">
        <div className={`absolute left-2 top-2 bottom-2 w-px ${isDark ? 'bg-white/10' : 'bg-slate-200'}`} />
        {items.map((it, idx) => {
          const { timeline, body } = parseInstruction(it);
          return (
            <FollowUpItem key={idx} timeline={timeline} body={body} isDark={isDark} />
          );
        })}
      </div>

      <div className={`rounded-xl p-4 border ${isDark ? 'bg-[var(--accent-primary)]/10 border-[var(--accent-primary)]/30' : 'bg-[var(--accent-primary)]/5 border-[var(--accent-primary)]/20'}`}>
        <div className="flex items-center gap-2 mb-2">
          <Calendar className="w-4 h-4 text-[var(--accent-primary)]" strokeWidth={1.6} />
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent-primary)]">Next Review (TCA)</span>
        </div>
        <input
          type="date"
          value={nextReviewDate || suggestedDate || ''}
          onChange={(e) => dispatch({ type: 'SET_NEXT_REVIEW_DATE', payload: e.target.value })}
          min={getTodayUTC8()}
          className={`w-full px-3 py-2 rounded-lg border text-sm transition-all focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/40
            ${isDark ? 'bg-white/10 border-white/20 text-white' : 'bg-white border-slate-200 text-slate-800'}`}
        />
        {suggestedDate && !nextReviewDate && (
          <p className="text-[11px] mt-1.5 text-[var(--accent-primary)]/80">Suggested from CPG follow-up plan — adjust as needed</p>
        )}
        <div className={`mt-4 text-[10px] font-bold uppercase tracking-wider mb-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Patient Status</div>
        <div className="flex gap-1.5">
          {statusOptions.map((opt) => {
            const active = currentStatus === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => dispatch({ type: 'SET_PATIENT_STATUS', payload: opt.value })}
                className={`flex-1 px-2 py-1.5 text-xs font-semibold rounded-lg border transition-colors
                  ${active
                    ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]'
                    : isDark
                      ? 'bg-white/5 border-white/10 text-slate-400 hover:bg-white/10'
                      : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab bar
   ============================================================ */
function TabBar({ tabs, active, onChange }) {
  const { isDark } = useTheme();
  return (
    <div className={`flex gap-1 p-1 rounded-xl border overflow-x-auto ${isDark ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'}`}>
      {tabs.map((t) => {
        const on = t.key === active;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={`flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold whitespace-nowrap transition-all
              ${on
                ? (isDark ? 'bg-slate-900 text-white shadow' : 'bg-white text-slate-800 shadow-sm')
                : (isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700')}`}
          >
            {t.label}
            {t.count != null && (
              <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full
                ${on
                  ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]'
                  : (isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-200 text-slate-600')}`}>
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ============================================================
   MAIN — Care Plan section (Tabbed layout)
   ============================================================ */
export function CarePlanSection() {
  const { state, finalizePlan, goToStep } = useApp();
  const { isDark } = useTheme();
  const { carePlan, patientData, diagnosis, mpisData, vitals, safetyReport, clinicalPlanResponse } = state;
  const graphNavigatorRules = clinicalPlanResponse?.graph_navigator_rules || [];

  const selectedIds = diagnosis?.selectedDiagnosisIds?.length > 0
    ? diagnosis.selectedDiagnosisIds
    : [diagnosis?.differentials?.[0]?.id].filter(Boolean);
  const selectedDiagnoses = diagnosis?.differentials?.filter((d) => selectedIds.includes(d.id)) || [];

  const [workflowStatus, setWorkflowStatus] = useState(WORKFLOW_STATES.DRAFT);
  const [workflowHistory, setWorkflowHistory] = useState([]);
  const [traceCollapsed, setTraceCollapsed] = useState(true);
  const [safetyAcknowledged, setSafetyAcknowledged] = useState(false);
  const [tab, setTab] = useState('overview');

  const safetyBlocksApprove = safetyReport && !safetyReport.safe_to_proceed && !safetyAcknowledged;

  if (!carePlan) return null;

  const handleBack = () => goToStep(2);

  const handleStatusChange = (newStatus, comment) => {
    setWorkflowStatus(newStatus);
    setWorkflowHistory((prev) => [
      { status: newStatus, action: newStatus === WORKFLOW_STATES.REVIEWED ? 'Marked as Reviewed' : 'Approved', user: 'Dr. Current User', timestamp: new Date().toLocaleString(), comment },
      ...prev,
    ]);
  };
  const handleReject = (comment) => {
    setWorkflowStatus(WORKFLOW_STATES.DRAFT);
    setWorkflowHistory((prev) => [
      { status: WORKFLOW_STATES.DRAFT, action: 'Sent back for revision', user: 'Dr. Current User', timestamp: new Date().toLocaleString(), comment },
      ...prev,
    ]);
  };
  const handleRegenerate = async (feedback) => {
    console.log('Regenerating with feedback:', feedback);
    await new Promise((resolve) => setTimeout(resolve, 1500));
  };

  const generateCarePlanSummary = () => {
    let summary = `Care Plan for ${patientData?.patientName || 'Patient'}. `;
    const diagnosisNames = selectedDiagnoses.map((d) => d.name).join(', ') || 'Not specified';
    summary += `${selectedDiagnoses.length > 1 ? 'Diagnoses' : 'Primary Diagnosis'}: ${diagnosisNames}. `;
    summary += `Clinical Summary: ${carePlan.clinicalSummary}. `;
    if (carePlan.medications.start.length > 0) summary += `New Medications to Start: ${carePlan.medications.start.map((m) => m.name).join(', ')}. `;
    if (carePlan.medications.stop.length > 0)  summary += `Medications to Stop: ${carePlan.medications.stop.map((m) => m.name).join(', ')}. `;
    summary += `Follow-up: ${(Array.isArray(carePlan.followUp) ? carePlan.followUp.join('; ') : carePlan.followUp) || 'As needed'}.`;
    return summary;
  };

  // Allergies
  let allergiesList = [];
  if (mpisData?.allergies) {
    if (Array.isArray(mpisData.allergies)) {
      allergiesList = mpisData.allergies;
    } else if (typeof mpisData.allergies === 'string' && mpisData.allergies.toLowerCase() !== 'none known') {
      allergiesList = mpisData.allergies.split(',').map((s) => s.trim()).filter(Boolean);
    }
  }

  // Tab counts
  const medsCount =
    (carePlan.medications?.stop?.length || 0) +
    (carePlan.medications?.start?.length || 0) +
    (carePlan.medications?.change?.length || 0) +
    (carePlan.medications?.continue?.length || 0);
  const careCount =
    (carePlan.interventions?.length || 0) +
    (carePlan.monitoring?.length || 0) +
    (carePlan.lifestyle?.length || 0);
  const followupCount =
    (carePlan.referrals?.length || 0) +
    (carePlan.redFlags?.length || 0) +
    (Array.isArray(carePlan.followUp) ? carePlan.followUp.length : carePlan.followUp ? 1 : 0);
  const refsCount = carePlan.cpgReferences?.length || 0;

  const tabs = [
    { key: 'overview', label: 'Overview',          icon: LayoutGrid },
    { key: 'meds',     label: 'Medications',       icon: Pill,         count: medsCount },
    { key: 'care',     label: 'Care & Monitoring', icon: Activity,     count: careCount },
    { key: 'followup', label: 'Follow-up & Safety', icon: Calendar,    count: followupCount },
    { key: 'refs',     label: 'References',        icon: BookOpen,     count: refsCount },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Page header */}
      <div className="mb-6">
        <span className="ds-eyebrow">STEP 3 OF 4</span>
        <h2 className={`text-2xl font-semibold tracking-tight mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>
          Recommended Care Plan
        </h2>
        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Review and accept the AI's recommended interventions before finalizing.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ============ LEFT PANEL: Reference Context ============ */}
        <div className="lg:col-span-4 space-y-4">
          <GlassCard className="p-4 border-l-4 border-[var(--accent-primary)] sticky top-4">
            <h3 className={`text-base font-semibold mb-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Reference Context</h3>

            <div className="space-y-4">
              <div>
                <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Confirmed Diagnosis</span>
                {selectedDiagnoses.length > 0 ? (
                  <div className="mt-1 space-y-2">
                    {selectedDiagnoses.map((d) => (
                      <div key={d.id} className="p-2 rounded bg-[var(--accent-primary)]/10">
                        <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{d.name}</p>
                        {d.icdCode && (
                          <p className={`text-xs ${isDark ? 'text-[var(--accent-primary)]' : 'text-blue-600'}`}>ICD-11: {d.icdCode}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className={`text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>None selected</p>
                )}
              </div>

              <div>
                <span className={`text-xs font-medium mb-1 block ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Known Allergies</span>
                {allergiesList.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {allergiesList.map((a, idx) => (
                      <span key={idx} className="bg-red-100 text-red-700 border border-red-300 rounded-full px-2 py-0.5 text-xs font-semibold">{a}</span>
                    ))}
                  </div>
                ) : (
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>No known allergies</span>
                )}
              </div>

              {(() => {
                const v = vitals;
                const abnormals = [];
                if (v?.bpSystolic && parseInt(v.bpSystolic) > 140) abnormals.push({ label: 'SBP', value: `${v.bpSystolic} mmHg ↑`, color: 'text-red-500' });
                if (v?.bpDiastolic && parseInt(v.bpDiastolic) > 90) abnormals.push({ label: 'DBP', value: `${v.bpDiastolic} mmHg ↑`, color: 'text-red-500' });
                if (v?.hr && parseInt(v.hr) > 100) abnormals.push({ label: 'HR', value: `${v.hr} bpm ↑`, color: 'text-amber-500' });
                if (v?.spo2 && parseInt(v.spo2) < 95) abnormals.push({ label: 'SpO₂', value: `${v.spo2}% ↓`, color: 'text-red-500' });
                if (v?.temp && parseFloat(v.temp) > 37.5) abnormals.push({ label: 'Temp', value: `${v.temp} °C ↑`, color: 'text-amber-500' });
                if (abnormals.length === 0) return null;
                return (
                  <div>
                    <span className={`text-xs font-medium mb-1 flex items-center gap-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      <TrendingUp className="w-3 h-3 text-red-400" strokeWidth={1.5} /> Critical Vitals
                    </span>
                    <div className={`p-2 rounded-lg grid grid-cols-2 gap-x-3 gap-y-1 ${isDark ? 'bg-red-900/20 border border-red-500/20' : 'bg-red-50 border border-red-100'}`}>
                      {abnormals.map((a, i) => (
                        <div key={i} className="flex items-baseline gap-1">
                          <span className={`text-[10px] font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{a.label}</span>
                          <span className={`text-xs font-bold ${a.color}`}>{a.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              <PipelineProgress
                pipelineEvents={state.pipelineEvents}
                pipelineThinking={state.pipelineThinking}
                summary={state.pipelineSummary}
                isLive={false}
                resynthOverride={state.resynthOverride}
                collapsed={traceCollapsed}
                onToggle={() => setTraceCollapsed((prev) => !prev)}
              />

              {carePlan?.unresolvedQuestions?.length > 0 && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
                  <p className="text-amber-500 text-sm font-medium mb-1">⚠ Unresolved Questions</p>
                  <ul className={`text-xs space-y-1 pl-3 list-disc ${isDark ? 'text-amber-200/80' : 'text-amber-700/80'}`}>
                    {carePlan.unresolvedQuestions.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </GlassCard>
        </div>

        {/* ============ RIGHT PANEL: Tabbed Actionable Plan ============ */}
        <div className="lg:col-span-8 space-y-4">
          <SafetyReviewBanner
            report={safetyReport}
            acknowledged={safetyAcknowledged}
            onAcknowledge={() => setSafetyAcknowledged(true)}
          />
          <GraphNavigatorPanel rules={graphNavigatorRules} />

          <TabBar tabs={tabs} active={tab} onChange={setTab} />

          {/* ── OVERVIEW ───────────────────────────────────────── */}
          {tab === 'overview' && (
            <>
              <ClinicalSummary
                summary={carePlan.clinicalSummary}
                readSummaryButton={<TextToSpeechButton text={generateCarePlanSummary()} label="Read" />}
              />

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Section title="Medication changes" icon={Pill} count={
                  (carePlan.medications.stop?.length || 0) +
                  (carePlan.medications.start?.length || 0) +
                  (carePlan.medications.change?.length || 0)
                }>
                  <div>
                    {[
                      ...(carePlan.medications.stop || []).map((m) => ({ ...m, _action: 'stop' })),
                      ...(carePlan.medications.start || []).map((m) => ({ ...m, _action: 'start' })),
                      ...(carePlan.medications.change || []).map((m) => ({ ...m, _action: 'change' })),
                    ].map((m) => (
                      <MedListRow
                        key={`${m._action}-${m.id}`}
                        bulletTone={m._action === 'stop' ? 'danger' : m._action === 'start' ? 'ok' : 'warn'}
                        drugName={m._action === 'change' ? `${m.name} (${m.previousDose} → ${m.newDose})` : m.name}
                        dose={m._action !== 'change' ? m.dose : null}
                        description={m.reason}
                        tag={m._action.toUpperCase()}
                        tagTone={m._action === 'stop' ? 'danger' : m._action === 'start' ? 'accent' : 'warn'}
                      />
                    ))}
                    <button
                      onClick={() => setTab('meds')}
                      className="mt-2 text-xs font-semibold text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                    >
                      View full medication table <ArrowRight className="w-3 h-3" strokeWidth={2} />
                    </button>
                  </div>
                </Section>

                <Section title="Red Flags" icon={AlertCircle} count={carePlan.redFlags?.length || 0} kind="red-flags">
                  <div>
                    {(carePlan.redFlags || []).map((f, i) => <RedFlagRow key={i} text={f} />)}
                  </div>
                </Section>
              </div>

              <Section title="Follow-up Plan" icon={Calendar}>
                <FollowUpBlock followUp={carePlan.followUp} />
              </Section>
            </>
          )}

          {/* ── MEDICATIONS ────────────────────────────────────── */}
          {tab === 'meds' && (
            <Section title="Medications" icon={Pill} count={medsCount}>
              <MedicationsTable medications={carePlan.medications} />
            </Section>
          )}

          {/* ── CARE & MONITORING ──────────────────────────────── */}
          {tab === 'care' && (
            <>
              <Section title="Procedures & Interventions" icon={Stethoscope} count={carePlan.interventions?.length || 0} noCollapse>
                <div>
                  {(carePlan.interventions || []).map((i) => (
                    <ListRow
                      key={i.id}
                      bulletTone="ok"
                      title={i.name}
                      sub={i.rationale}
                      tag={i.urgency}
                      tagTone={i.urgency === 'Today' ? 'danger' : 'accent'}
                    />
                  ))}
                </div>
              </Section>
              <Section title="Monitoring & Testing" icon={Activity} count={carePlan.monitoring?.length || 0}>
                <div>
                  {(carePlan.monitoring || []).map((i) => (
                    <ListRow
                      key={i.id}
                      bulletTone="info"
                      title={i.parameter || i.task}
                      sub={i.target ? `Target: ${i.target}` : i.cpgRef}
                      tag={i.schedule}
                      tagTone="accent"
                      noCollapse
                      scheduleBelow
                    />
                  ))}
                </div>
              </Section>
              <Section title="Lifestyle & Self-Management" icon={Heart} count={carePlan.lifestyle?.length || 0} noCollapse>
                <div>
                  {(carePlan.lifestyle || []).map((i) => <ListRow key={i.id} bulletTone="ok" title={i.goal} tag={i.category} />)}
                </div>
              </Section>
            </>
          )}

          {/* ── FOLLOW-UP & SAFETY ─────────────────────────────── */}
          {tab === 'followup' && (
            <>
              <Section title="Follow-up Plan" icon={Calendar}>
                <FollowUpBlock followUp={carePlan.followUp} />
              </Section>
              <Section title="Referrals" icon={Send} count={carePlan.referrals?.length || 0}>
                <div>
                  {(carePlan.referrals || []).map((r, idx) => (
                    <ListRow key={idx} bulletTone="info" title={r.specialty} sub={r.reason} tag={r.urgency} tagTone="warn" />
                  ))}
                </div>
              </Section>
              <Section title="Red Flags — Return Immediately" icon={AlertCircle} count={carePlan.redFlags?.length || 0} kind="red-flags">
                <div>
                  {(carePlan.redFlags || []).map((f, i) => <RedFlagRow key={i} text={f} />)}
                </div>
              </Section>
            </>
          )}

          {/* ── REFERENCES ─────────────────────────────────────── */}
          {tab === 'refs' && (
            <Section title="CPG References" icon={BookOpen} count={refsCount}>
              <div className="flex flex-col gap-2">
                {(carePlan.cpgReferences || []).map((ref, idx) => (
                  <button
                    key={idx}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-2 transition-colors self-start
                      ${isDark
                        ? 'bg-[var(--accent-primary)]/15 hover:bg-[var(--accent-primary)]/25 text-slate-200'
                        : 'bg-[var(--accent-primary)]/10 hover:bg-[var(--accent-primary)]/20 text-slate-700'}`}
                  >
                    <BookOpen className="w-3 h-3 text-[var(--accent-primary)]" strokeWidth={1.7} />
                    <span>{ref.title}</span>
                    {ref.page && <span className="text-[10px] font-mono opacity-60">p.{ref.page}</span>}
                  </button>
                ))}
              </div>
            </Section>
          )}

          {/* Approval workflow — stays visible across all tabs */}
          <div className="mt-6">
            <WorkflowActions
              currentStatus={workflowStatus}
              onStatusChange={handleStatusChange}
              onReject={handleReject}
              onRegenerate={handleRegenerate}
              history={workflowHistory}
              disabled={safetyBlocksApprove}
            />
          </div>
        </div>
      </div>

      {/* Footer action buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-6">
        <Button variant="secondary" size="lg" icon={ArrowLeft} onClick={handleBack}>Back</Button>
        <Button
          variant="primary"
          size="lg"
          icon={Check}
          onClick={finalizePlan}
          disabled={workflowStatus !== WORKFLOW_STATES.APPROVED}
          glow={workflowStatus === WORKFLOW_STATES.APPROVED}
          className="min-w-[250px]"
        >
          {workflowStatus === WORKFLOW_STATES.APPROVED ? 'Generate Report' : 'Approval Required'}
        </Button>
      </div>

      {workflowStatus !== WORKFLOW_STATES.APPROVED && (
        <p className="text-center text-sm text-slate-500">Approve the care plan above to generate report</p>
      )}
    </div>
  );
}
