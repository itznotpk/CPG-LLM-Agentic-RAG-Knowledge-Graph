import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  ClipboardList,
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
  TrendingUp,
  Send,
  Shield,
  LayoutGrid,
  Clock,
  Pencil,
  Trash2,
  Plus,
  Network,
  X,
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
import { useAuth } from '../../context/AuthContext';
import { saveHumanSignal } from '../../lib/supabase';
import { PipelineProgress } from './PipelineProgress';
import { SafetyReviewBanner } from './SafetyReviewBanner';
import CareMonitoringPanel from './CareMonitoringPanel';

/* ============================================================
   Graph-verified badge — folds Graph Navigator KG edges into the
   Medications surface as per-drug verification stamps.
   Source of edges: clinicalPlanResponse.graph_navigator_rules
   (FIRST_LINE_FOR / SECOND_LINE_FOR / RECOMMENDED_FOR, CPG-scoped).
   ============================================================ */
const RELATION_LABEL = {
  FIRST_LINE_FOR: '1st-line',
  SECOND_LINE_FOR: '2nd-line',
  RECOMMENDED_FOR: 'Recommended',
};
const RELATION_RANK = { FIRST_LINE_FOR: 0, SECOND_LINE_FOR: 1, RECOMMENDED_FOR: 2 };

// Parser-error rows extracted from CPG tables — never match a real prescription.
const PARSER_ERROR_DRUGS = new Set([
  'pharmacological agent', 'pharmacological', 'drug', 'agent',
  'pharmacological treatment', 'medication', 'medications',
]);

// Drug-class → keyword/suffix tokens used to recognise a specific molecule
// (e.g., "Statin" matches "atorvastatin", "Ace Inhibitor" matches "lisinopril").
const DRUG_CLASS_KEYWORDS = {
  'ace inhibitor':                       ['pril'],
  'angiotensin receptor blocker':        ['sartan'],
  'arb':                                 ['sartan'],
  'beta-blocker':                        ['olol', 'carvedilol', 'bisoprolol'],
  'b-blocker':                           ['olol'],
  'thiazide diuretic':                   ['thiazide', 'chlorthalidone', 'indapamide', 'hydrochloro'],
  'thiazide diuretics':                  ['thiazide', 'chlorthalidone', 'indapamide', 'hydrochloro'],
  'chlorthalidone':                      ['chlorthalidone'],
  'dihydropyridine ccb':                 ['dipine'],
  'long-acting calcium channel blocker': ['dipine', 'amlodipine', 'felodipine'],
  'ccb':                                 ['dipine', 'diltiazem', 'verapamil', 'amlodipine'],
  'calcium channel blocker':             ['dipine', 'diltiazem', 'verapamil'],
  'k+ sparing diuretics':                ['spironolactone', 'amiloride', 'eplerenone'],
  'dri':                                 ['aliskiren'],
  'statin':                              ['statin'],
  'pcsk9 inhibitor':                     ['alirocumab', 'evolocumab'],
  'basal insulin':                       ['insulin glargine', 'insulin detemir', 'insulin degludec', 'lantus', 'tresiba', 'levemir'],
  'metformin':                           ['metformin'],
  'sglt2 inhibitor':                     ['flozin'],
  'sglt2':                               ['flozin'],
  'glp-1 receptor agonist':              ['glutide', 'tide'],
  'glp-1':                               ['glutide'],
  'dpp-4 inhibitor':                     ['gliptin'],
  'sulfonylurea':                        ['gliclazide', 'glimepiride', 'glipizide', 'glibenclamide'],
};

function _matchRuleToMed(medName, ruleDrug) {
  if (!medName || !ruleDrug) return false;
  const n = String(medName).toLowerCase();
  const d = String(ruleDrug).toLowerCase().trim();
  if (!d || PARSER_ERROR_DRUGS.has(d)) return false;
  // Direct substring match (≥4 chars to avoid false positives on "ccb", "arb")
  if (d.length >= 4 && (n.includes(d) || d.includes(n))) return true;
  // Class → keyword lookup
  const kws = DRUG_CLASS_KEYWORDS[d] || [];
  return kws.some((k) => n.includes(k));
}

/** Find the highest-precedence graph rule for a given medication name. */
function pickBestRuleForMed(medName, rules) {
  if (!medName || !Array.isArray(rules) || rules.length === 0) return null;
  let best = null;
  for (const r of rules) {
    if (!_matchRuleToMed(medName, r?.drug)) continue;
    if (best === null) { best = r; continue; }
    const a = RELATION_RANK[r.relation] ?? 9;
    const b = RELATION_RANK[best.relation] ?? 9;
    if (a < b) best = r;
  }
  return best;
}

function GraphVerifiedBadge({ rule }) {
  const { isDark } = useTheme();
  if (!rule) return null;
  const label = RELATION_LABEL[rule.relation] || 'Recommended';
  const title = [
    `Graph-verified: ${label} for ${rule.condition || 'condition'}`,
    rule.evidence ? `\n\nEvidence: "${rule.evidence}"` : '',
    rule.source_document ? `\nSource: ${rule.source_document}` : '',
  ].join('');
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-semibold tracking-wide ${
        isDark
          ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-700/40'
          : 'bg-emerald-50 text-emerald-700 border border-emerald-300'
      }`}
    >
      <Network className="w-2.5 h-2.5" strokeWidth={2.4} />
      {label}
    </span>
  );
}

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
            <span className={`text-[11px] font-sans px-2 py-0.5 rounded-full ${isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>{count}</span>
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
// Split a clinical-summary paragraph into individual sentences for a scannable
// bullet layout. Splits on ". " only when followed by a capital letter or "(",
// so decimals (BMI 32, LVEF 25%) and inline abbreviations stay intact.
function splitSummarySentences(text) {
  return String(text || '')
    .trim()
    .split(/(?<=\.)\s+(?=[A-Z(])/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function ClinicalSummary({ summary, readSummaryButton }) {
  const { isDark } = useTheme();
  const sentences = splitSummarySentences(summary);
  // The first sentence is the patient one-liner (who they are); the rest are the
  // assessment/plan points. Lead with the patient line, bullet the reasoning.
  const [lead, ...points] = sentences;
  return (
    <GlassCard className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.08em] font-semibold text-[var(--accent-primary)] mb-2">Clinical Summary</div>
          {sentences.length <= 1 ? (
            <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{summary}</p>
          ) : (
            <>
              <p className={`text-sm leading-relaxed font-medium mb-3 ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>{lead}</p>
              <ul className="flex flex-col gap-1.5">
                {points.map((s, i) => (
                  <li key={i} className={`flex gap-2 text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <span className="mt-[7px] shrink-0 w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)]" />
                    <span className="min-w-0">{s}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
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
  contraindicated: { label: 'CONTRAINDICATED', light: 'bg-red-100 text-red-700', dark: 'bg-red-500/20 text-red-300' },
};
const ACTION_OPTIONS = ['start', 'continue', 'change', 'stop', 'contraindicated'];

function ActionTag({ action }) {
  const { isDark } = useTheme();
  const s = ACTION_STYLES[action];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${isDark ? s.dark : s.light}`}>{s.label}</span>
  );
}

/* Editable inline text — click to edit, blur/enter to save */
export function InlineEdit({ value, onChange, className = '', multiline = false, placeholder = '', renderDisplay = null, autoEdit = false }) {
  const { isDark } = useTheme();
  const [editing, setEditing] = useState(autoEdit && !value);
  const [draft, setDraft] = useState(value || '');
  const ref = useRef(null);

  useEffect(() => { setDraft(value || ''); }, [value]);
  useEffect(() => {
    if (editing && ref.current) {
      ref.current.focus();
      // Move cursor to end
      const len = ref.current.value?.length || 0;
      ref.current.setSelectionRange(len, len);
    }
  }, [editing]);

  const commit = () => {
    setEditing(false);
    if (draft !== (value || '')) onChange(draft);
  };

  if (editing) {
    const inputCls = `w-full px-1.5 py-0.5 rounded border text-sm transition-all focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/40 ${isDark ? 'bg-white/10 border-white/20 text-white' : 'bg-white border-slate-200 text-slate-800'} ${className}`;
    if (multiline) {
      return (
        <textarea
          ref={ref}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === 'Escape') { setDraft(value || ''); setEditing(false); } }}
          className={`${inputCls} min-h-[48px] resize-y`}
          placeholder={placeholder}
          rows={2}
        />
      );
    }
    return (
      <input
        ref={ref}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { setDraft(value || ''); setEditing(false); } }}
        className={inputCls}
        placeholder={placeholder}
      />
    );
  }

  return (
    <span
      onClick={() => setEditing(true)}
      className={`group/edit cursor-pointer inline-flex ${renderDisplay && value ? 'items-start' : 'items-center'} gap-1 rounded px-1 -mx-1 transition-colors ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-100'} ${className}`}
      title="Click to edit"
    >
      <span className="min-w-0">{value ? (renderDisplay ? renderDisplay(value) : value) : <span className="italic opacity-50">{placeholder || 'Click to edit'}</span>}</span>
      <Pencil className={`w-3 h-3 flex-shrink-0 opacity-0 group-hover/edit:opacity-60 transition-opacity ${renderDisplay && value ? 'mt-1' : ''} ${isDark ? 'text-slate-400' : 'text-slate-400'}`} strokeWidth={1.7} />
    </span>
  );
}

/* Editable action dropdown — single select that shows colored label */
function ActionDropdown({ action, onChange }) {
  const { isDark } = useTheme();
  const s = ACTION_STYLES[action];
  return (
    <select
      value={action}
      onChange={(e) => onChange(e.target.value)}
      className={`appearance-none cursor-pointer px-2.5 py-1 rounded text-[10px] font-bold tracking-wider border-0 focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/40 transition-all ${isDark ? s.dark : s.light}`}
      style={{ WebkitAppearance: 'none', backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='8' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 5px center', paddingRight: '20px' }}
    >
      {ACTION_OPTIONS.map((opt) => (
        <option key={opt} value={opt}>{ACTION_STYLES[opt].label}</option>
      ))}
    </select>
  );
}

// Format a raw CPG citation for display: drop the "[chunk N]" suffix and
// rewrite the "§14.1.6.3" section marker as "[Section 14.1.6.3]".
// e.g. "CPG Diabetes and Heart Failure §14.1.6.3 [chunk 8]"
//   →  "CPG Diabetes and Heart Failure [Section 14.1.6.3]"
function formatCpgRef(raw) {
  return String(raw || '')
    .replace(/\s*\[chunk[^\]]*\]/gi, '')      // remove [chunk N]
    .replace(/§\s*([\w.]+)/g, '[Section $1]') // § X → [Section X]
    .replace(/\s{2,}/g, ' ')
    .trim();
}

// Split a packed CPG reference string into individual references (one per `;`).
function formatCpgRefs(raw) {
  return formatCpgRef(raw)
    .split(/\s*;\s*/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// Parse an interchangeable-medication string into a clean class label + options.
// Handles three shapes the synthesiser emits:
//   "Class (Agent A or Agent B)"  → { label: "Class", options: ["Agent A", "Agent B"] }
//   "Agent A or Agent B"          → { label: "",      options: ["Agent A", "Agent B"] }
//   "Single agent"                → { label: "",      options: ["Single agent"] }
// The "or" inside a parenthetical is the option separator, so we never split on
// the wrapping class name and we strip the now-redundant parentheses.
// Capitalise the first letter of a string (e.g. a drug name) without touching
// the rest — "bisoprolol 1.25mg OD" → "Bisoprolol 1.25mg OD". Leaves a string
// that already starts with a capital / non-letter (a number, "(") unchanged.
function capitalizeFirst(s) {
  return String(s || '').replace(/^(\s*)([a-z])/, (_, sp, c) => sp + c.toUpperCase());
}

function parseAgentOptions(raw) {
  const s = String(raw || '').trim();
  if (!s) return { label: '', options: [] };
  const clean = (arr) => arr.map((x) => capitalizeFirst(x.trim())).filter(Boolean);

  const open = s.indexOf('(');
  if (open !== -1) {
    const label = s.slice(0, open).trim();
    const inner = s.slice(open + 1).replace(/\)\s*$/, '').trim(); // drop trailing ")"
    if (/\s+or\s+/i.test(inner)) {
      return { label, options: clean(inner.split(/\s+or\s+/i)) };
    }
  }

  if (/\s+or\s+/i.test(s)) {
    return { label: '', options: clean(s.split(/\s+or\s+/i)) };
  }
  return { label: '', options: clean([s]) };
}

function MedicationRow({ med, action, originalAction, onFieldChange, onActionChange, onDelete, graphRule, highlighted }) {
  const { isDark } = useTheme();
  // originalAction = the category the med belongs to (determines content rendering)
  // action = the displayed action (may be overridden by user)
  return (
    <tr
      id={`med-row-${med.id}`}
      className={`border-b ${isDark ? 'border-white/5' : 'border-slate-100'} last:border-b-0 group/row transition-colors duration-700 ${
        highlighted ? (isDark ? 'bg-amber-500/10' : 'bg-amber-50') : ''
      }`}
    >
      <td className="py-3 pr-4 align-top w-[100px]">
        <ActionDropdown action={action} onChange={onActionChange} />
      </td>
      <td className="py-3 pr-4 align-top">
        {(() => {
          // The full set of interchangeable agents is preserved in `nameOptions`
          // once a pick is made, so both options stay visible and the choice is reversible.
          const optionSource = med.nameOptions || med.name || '';
          const { label: classLabel, options: opts } = parseAgentOptions(optionSource);
          if (opts.length < 2) {
            return (
              <div className={`flex items-center gap-2 flex-wrap font-semibold text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>
                <InlineEdit value={med.name} onChange={(v) => onFieldChange('name', v)} placeholder="Medication name" renderDisplay={(v) => capitalizeFirst(v)} />
                <GraphVerifiedBadge rule={graphRule} />
              </div>
            );
          }
          // Interchangeable class-equivalent agents — clinician picks one.
          // A selection has been made if `nameOptions` is set (then `name` holds the pick).
          const selected = med.nameOptions ? med.name : null;
          // Custom = a pick has been made but it isn't one of the suggested agents
          // (the clinician entered their own medication instead).
          const isCustom = med.nameOptions != null && !opts.includes(med.name);
          const ensureOptions = () => {
            if (!med.nameOptions) onFieldChange('nameOptions', med.name); // remember the original "A or B"
          };
          const pick = (opt) => { ensureOptions(); onFieldChange('name', opt); };
          const startCustom = () => { ensureOptions(); onFieldChange('name', ''); };
          return (
            <div>
              <div className={`flex items-center gap-1.5 mb-1 text-[10px] font-semibold uppercase tracking-wide ${isDark ? 'text-amber-300/80' : 'text-amber-600'}`}>
                {selected ? 'Selected — tap to switch' : 'Choose one'}
                {classLabel && <span className={`normal-case font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>· {classLabel}</span>}
                <GraphVerifiedBadge rule={graphRule} />
              </div>
              <div className="flex flex-col gap-1">
                {opts.map((opt, i) => {
                  const isSel = selected === opt;
                  return (
                    <button
                      key={i}
                      onClick={() => pick(opt)}
                      className={`flex items-center gap-2 text-left px-2.5 py-1.5 rounded-md border text-sm font-semibold transition-colors ${
                        isSel
                          ? (isDark ? 'bg-emerald-500/15 border-emerald-400/50 text-emerald-200' : 'bg-emerald-50 border-emerald-300 text-emerald-800')
                          : (isDark ? 'bg-white/[0.03] border-white/10 text-slate-200 hover:bg-amber-500/15 hover:border-amber-400/40'
                                    : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-amber-50 hover:border-amber-300')}`}
                      title={isSel ? 'Selected for the patient' : 'Select this option for the patient'}
                    >
                      <span className={`shrink-0 ${isSel ? '' : 'opacity-0'}`}>
                        <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
                      </span>
                      <span>{opt}</span>
                    </button>
                  );
                })}

                {/* Custom entry — when neither suggested agent is the clinician's choice. */}
                {isCustom ? (
                  <div className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md border text-sm font-semibold ${
                    isDark ? 'bg-emerald-500/15 border-emerald-400/50 text-emerald-200' : 'bg-emerald-50 border-emerald-300 text-emerald-800'}`}>
                    <Check className="w-3.5 h-3.5 shrink-0" strokeWidth={2.5} />
                    <InlineEdit
                      value={med.name}
                      onChange={(v) => onFieldChange('name', v)}
                      placeholder="Type medication name & dose"
                      autoEdit
                      className="flex-1"
                    />
                  </div>
                ) : (
                  <button
                    onClick={startCustom}
                    className={`flex items-center gap-2 text-left px-2.5 py-1.5 rounded-md border border-dashed text-sm font-medium transition-colors ${
                      isDark ? 'border-white/15 text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                             : 'border-slate-300 text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}
                    title="Neither option fits — enter your own medication"
                  >
                    <Plus className="w-3.5 h-3.5 shrink-0" strokeWidth={2} />
                    <span>Add my own</span>
                  </button>
                )}
              </div>
            </div>
          );
        })()}
        <div className={`mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {originalAction === 'change' ? (
            <InlineEdit
              value={`${med.previousDose || ''} → ${med.newDose || ''}`}
              onChange={(v) => {
                const parts = v.split('→').map(s => s.trim());
                if (parts.length >= 2) {
                  onFieldChange('previousDose', parts[0]);
                  onFieldChange('newDose', parts[1]);
                } else {
                  onFieldChange('dose', v);
                }
              }}
              multiline
              className={`text-xs leading-relaxed`}
              placeholder="Dose change details"
            />
          ) : (
            <InlineEdit value={med.dose} onChange={(v) => onFieldChange('dose', v)} multiline className="text-xs leading-relaxed" placeholder="Dose & details" />
          )}
        </div>
      </td>
      <td className="py-3 pr-4 align-top">
        <InlineEdit
          value={med.reason}
          onChange={(v) => onFieldChange('reason', v)}
          multiline
          className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}
          placeholder="Reason & instructions"
        />
        {med.instructions && (
          <div className={`mt-1 text-[11px] px-1.5 py-0.5 rounded ${isDark ? 'bg-amber-500/15 text-amber-300' : 'bg-amber-100 text-amber-700'}`}>
            <InlineEdit value={med.instructions} onChange={(v) => onFieldChange('instructions', v)} placeholder="Instructions" />
          </div>
        )}
        {med.kiv && (
          <div className={`mt-1 text-[11px] px-1.5 py-0.5 rounded ${isDark ? 'bg-blue-500/15 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
            <InlineEdit value={med.kiv} onChange={(v) => onFieldChange('kiv', v)} placeholder="KIV note" />
          </div>
        )}
      </td>
      <td className="py-3 align-top w-[140px]">
        <div className="flex items-start justify-between">
          {(() => {
            const refs = formatCpgRefs(med.cpgRef);
            if (refs.length === 0) return <span className="text-[11px]" />;
            if (refs.length === 1) {
              return <span className={`text-[11px] font-sans ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>{refs[0]}</span>;
            }
            return (
              <ul className={`text-[11px] font-sans space-y-0.5 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                {refs.map((r, i) => (
                  <li key={i} className="flex gap-1">
                    <span className="select-none">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            );
          })()}
          <button
            onClick={onDelete}
            className={`p-1 rounded-md opacity-0 group-hover/row:opacity-100 transition-all flex-shrink-0 ml-1
              ${isDark ? 'text-red-400 hover:bg-red-500/20 hover:text-red-300' : 'text-red-400 hover:bg-red-50 hover:text-red-600'}`}
            title="Delete medication"
          >
            <Trash2 className="w-3.5 h-3.5" strokeWidth={1.7} />
          </button>
        </div>
      </td>
    </tr>
  );
}
function MedicationsTable({ medications, dispatch, graphRules, highlightedMedId }) {
  const { isDark } = useTheme();
  const ordered = [
    ...(medications.contraindicated || []).map((m) => ({ med: m, action: 'contraindicated' })),
    ...(medications.stop || []).map((m) => ({ med: m, action: 'stop' })),
    ...(medications.start || []).map((m) => ({ med: m, action: 'start' })),
    ...(medications.change || []).map((m) => ({ med: m, action: 'change' })),
    ...(medications.continue || []).map((m) => ({ med: m, action: 'continue' })),
  ];

  const handleFieldChange = (action, medId, field, value) => {
    dispatch({ type: 'UPDATE_MEDICATION_FIELD', payload: { actionType: action, medId, field, value } });
  };

  const handleActionChange = (currentAction, medId, newAction) => {
    dispatch({ type: 'UPDATE_MEDICATION_FIELD', payload: { actionType: currentAction, medId, field: 'displayAction', value: newAction } });
  };

  const handleDelete = (action, medId) => {
    dispatch({ type: 'DELETE_MEDICATION', payload: { actionType: action, medId } });
  };

  const handleAddMedication = () => {
    dispatch({ type: 'ADD_MEDICATION' });
  };

  return (
    <div className="overflow-x-auto -mx-1">
      {ordered.length === 0 ? (
        <p className="text-sm text-slate-500 mb-4 ml-1">No medication changes.</p>
      ) : (
        <table className="w-full text-left mb-4">
          <thead>
            <tr className={isDark ? 'text-slate-500' : 'text-slate-500'}>
              <th className="py-2 pr-4 text-[10px] uppercase tracking-wider font-semibold">Action</th>
              <th className="py-2 pr-4 text-[10px] uppercase tracking-wider font-semibold">Medication</th>
              <th className="py-2 pr-4 text-[10px] uppercase tracking-wider font-semibold">Reason &amp; instructions</th>
              <th className="py-2 text-[10px] uppercase tracking-wider font-semibold">CPG</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map(({ med, action }) => (
              <MedicationRow
                key={`${action}-${med.id}`}
                med={med}
                action={med.displayAction || action}
                originalAction={action}
                onFieldChange={(field, value) => handleFieldChange(action, med.id, field, value)}
                onActionChange={(newAction) => handleActionChange(action, med.id, newAction)}
                onDelete={() => handleDelete(action, med.id)}
                graphRule={pickBestRuleForMed(med.name, graphRules)}
                highlighted={highlightedMedId === med.id}
              />
            ))}
          </tbody>
        </table>
      )}

      <button
        onClick={handleAddMedication}
        className={`ml-1 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
          isDark 
            ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white' 
            : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'
        }`}
      >
        <Plus className="w-3.5 h-3.5" strokeWidth={2.5} />
        Add Medication
      </button>
    </div>
  );
}

/* ============================================================
   Red flag row — title/subtitle split on " — ", collapsible detail
   ============================================================ */
function RedFlagRow({ text }) {
  const { isDark } = useTheme();
  const [showFull, setShowFull] = React.useState(false);
  // Split priority: ":" first (Stage-5 convention "Label: criteria…"), then " — "
  // (older format), then the whole thing as title. Keeps the bold label short
  // and scannable so a clinician can ignore the criteria detail unless they need it.
  const splitText = (raw) => {
    if (!raw) return { title: '', sub: null };
    // Split on the first "Label: criteria" colon. The label can be long when it
    // carries a parenthetical (e.g. "Acute decompensation (… oedema): review"),
    // so rather than a fixed length cap we only require that the label isn't
    // itself running prose (no sentence boundary before the colon) and that
    // there is real text after it. This keeps every flag split into title + sub.
    const colonIdx = raw.indexOf(': ');
    if (colonIdx !== -1 && colonIdx < raw.length - 2 && !/[.!?]\s/.test(raw.slice(0, colonIdx))) {
      return { title: raw.slice(0, colonIdx).trim(), sub: raw.slice(colonIdx + 2).trim() };
    }
    const dashIdx = raw.indexOf(' — ');
    if (dashIdx !== -1) {
      return { title: raw.slice(0, dashIdx).trim(), sub: raw.slice(dashIdx + 3).trim() };
    }
    return { title: raw, sub: null };
  };
  const { title: flagTitle, sub: flagSub } = splitText(text);
  // Long criteria lists ("SBP ≥160 OR DBP ≥110 OR thrombocytopenia OR …") get
  // truncated with a Show more toggle — preserves scannability without losing audit.
  const SUB_CAP = 90;
  const subIsLong = flagSub && flagSub.length > SUB_CAP;
  const subDisplay = subIsLong && !showFull ? `${flagSub.slice(0, SUB_CAP).trimEnd()}…` : flagSub;
  return (
    <div className={`py-2.5 border-b last:border-b-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${isDark ? 'bg-red-500/20 text-red-300' : 'bg-red-100 text-red-700'}`}>
          <Check className="w-3 h-3" strokeWidth={2.4} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-semibold leading-snug ${isDark ? 'text-red-400' : 'text-red-600'}`}>{flagTitle}</div>
          {flagSub && (
            <div className={`text-xs mt-0.5 leading-snug ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
              {subDisplay}
              {subIsLong && (
                <button
                  type="button"
                  onClick={() => setShowFull((v) => !v)}
                  className={`ml-1 text-[10px] font-semibold underline-offset-2 hover:underline ${isDark ? 'text-slate-400' : 'text-slate-500'}`}
                >
                  {showFull ? 'less' : 'more'}
                </button>
              )}
            </div>
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

function MedListRow({ bulletTone = 'ok', drugName, dose, description, tag, tagTone, graphRule }) {
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
          <div className={`flex items-center gap-2 flex-wrap text-sm font-semibold leading-snug ${nameColor}`}>
            <span>{drugName}</span>
            <GraphVerifiedBadge rule={graphRule} />
          </div>
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
      <div className="text-[11px] font-sans font-semibold uppercase tracking-wider text-[var(--accent-primary)]">{timeline}</div>
      {body && (
        <p className={`text-sm leading-relaxed mt-0.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{body}</p>
      )}
    </div>
  );
}

/* Convert a follow-up timeline label into a sortable offset in days so the plan
   reads earliest → latest. Ranges ("4-6 weeks") sort by their lower bound.
   Immediate cues map to 0; recurring/standing instructions ("each visit",
   "ongoing") have no fixed point, so they sort to the end as continuous care. */
function timelineToDays(timeline) {
  const t = String(timeline || '').toLowerCase();
  if (!t || t === '—') return Number.POSITIVE_INFINITY;
  if (/\b(immediate|immediately|today|now|stat|on discharge|at discharge)\b/.test(t)) return 0;
  if (/\b(each|every|per)\s+visit\b|\bongoing\b|\bcontinuous\b|\bindefinite|\blong[-\s]?term\b|\bas\s+needed\b|\bprn\b|\broutine\b/.test(t)) {
    return Number.POSITIVE_INFINITY;
  }
  const UNIT_DAYS = { day: 1, week: 7, fortnight: 14, month: 30, year: 365 };
  // Lower bound of the first number(s) in the label (handles "4-6 weeks", "3 months").
  const m = t.match(/(\d+(?:\.\d+)?)\s*(?:[-–—]\s*\d+(?:\.\d+)?\s*)?(day|week|fortnight|month|year)/);
  if (m) return parseFloat(m[1]) * UNIT_DAYS[m[2]];
  return Number.POSITIVE_INFINITY;
}

function FollowUpBlock({ followUp }) {
  const { isDark } = useTheme();

  const parseInstruction = (text) => {
    const source = String(text || '').replace(/\s+/g, ' ').trim();
    const dashMatch = source.match(/\s+(?:-|—|–)\s+/);
    if (dashMatch?.index != null) {
      return {
        timeline: source.slice(0, dashMatch.index).trim(),
        body: source.slice(dashMatch.index + dashMatch[0].length).trim(),
      };
    }
    const colonIdx = source.indexOf(':');
    if (colonIdx === -1) return { timeline: '—', body: text };
    return { timeline: source.slice(0, colonIdx).trim(), body: source.slice(colonIdx + 1).trim() };
  };

  const raw = Array.isArray(followUp) ? followUp : followUp ? [followUp] : [];
  // Parse first, then sort chronologically (earliest → latest) with a stable
  // tiebreak so equal/recurring timelines keep their original relative order.
  const items = raw
    .map((it, idx) => ({ idx, ...parseInstruction(it) }))
    .sort((a, b) => {
      const da = timelineToDays(a.timeline);
      const db = timelineToDays(b.timeline);
      return da === db ? a.idx - b.idx : da - db;
    });

  return (
    <div className="relative pl-7">
      <div className={`absolute left-2 top-2 bottom-2 w-px ${isDark ? 'bg-white/10' : 'bg-slate-200'}`} />
      {items.map((it) => (
        <FollowUpItem key={it.idx} timeline={it.timeline} body={it.body} isDark={isDark} />
      ))}
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
              <span className={`text-[10px] font-sans px-1.5 py-0.5 rounded-full
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
   CPG Evidence Renderer Utilities
   ============================================================ */

/** Parse and replace [Grade X] / [Level X] tokens with styled pill spans */
function renderGradePills(text) {
  if (!text) return null;
  // Split on [Grade A/B/C] and [Level I/II-2/III] tokens
  const parts = text.split(/(\[(?:Grade\s+[A-C]|Level\s+[I]{1,3}(?:-[23])?)\])/gi);
  return parts.map((part, i) => {
    const gradeMatch = part.match(/^\[Grade\s+([A-C])\]$/i);
    const levelMatch = part.match(/^\[Level\s+(I{1,3}(?:-[23])?)\]$/i);
    if (gradeMatch) {
      const g = gradeMatch[1].toUpperCase();
      const color =
        g === 'A' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
        g === 'B' ? 'bg-sky-500/15 text-sky-400 border-sky-500/30' :
                    'bg-amber-500/15 text-amber-400 border-amber-500/30';
      return (
        <span key={i} className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[9px] font-bold font-sans tracking-wider mx-0.5 align-middle ${color}`}>
          Grade {g}
        </span>
      );
    }
    if (levelMatch) {
      const l = levelMatch[1].toUpperCase();
      const isStrong = l === 'I';
      const color = isStrong
        ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/25'
        : l === 'II' || l.startsWith('II')
          ? 'bg-sky-500/10 text-sky-500 border-sky-500/25'
          : 'bg-amber-500/10 text-amber-500 border-amber-500/25';
      return (
        <span key={i} className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[9px] font-sans tracking-wider mx-0.5 align-middle ${color}`}>
          Level {l}
        </span>
      );
    }
    // Bold text (** **)
    const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
    if (boldParts.length > 1) {
      return boldParts.map((bp, j) => {
        const bm = bp.match(/^\*\*([^*]+)\*\*$/);
        return bm
          ? <strong key={`${i}-${j}`} className="font-semibold">{bm[1]}</strong>
          : <React.Fragment key={`${i}-${j}`}>{bp}</React.Fragment>;
      });
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

/** Render a block of CPG text line-by-line with grade pills, bullets, and section headings */
function CpgTextBlock({ text, isDark, muted = false }) {
  if (!text) return null;
  const lines = text.split('\n');
  const baseText = muted
    ? (isDark ? 'text-slate-400' : 'text-slate-500')
    : (isDark ? 'text-slate-300' : 'text-slate-700');

  // Detect recommendations block
  let inRecsBlock = false;
  const recLines = [];
  const elements = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Detect "Recommendations" heading
    if (/^\*?\*?Recommendations?\*?\*?\s*:?\s*$/i.test(trimmed) || trimmed === '**Recommendations**') {
      inRecsBlock = true;
      // If there are pending rec lines from a prior iteration, flush them
      if (recLines.length > 0) {
        elements.push(
          <RecommendationBox key={`recs-${i}`} lines={[...recLines]} isDark={isDark} />
        );
        recLines.length = 0;
      }
      continue;
    }

    // Lines starting with "- [Grade" belong to recs block
    if (inRecsBlock && /^\s*-\s*\[(?:Grade|Level)/i.test(trimmed)) {
      recLines.push(trimmed.replace(/^-\s*/, ''));
      continue;
    }

    // Flush recs block when we hit a non-rec line
    if (inRecsBlock && recLines.length > 0 && trimmed !== '') {
      elements.push(
        <RecommendationBox key={`recs-flush-${i}`} lines={[...recLines]} isDark={isDark} />
      );
      recLines.length = 0;
      inRecsBlock = false;
    }

    if (trimmed === '') {
      elements.push(<div key={i} className="h-2" />);
      continue;
    }

    // H1 heading (#)
    if (/^# /.test(trimmed)) {
      elements.push(
        <h3 key={i} className={`text-[11px] font-bold mt-3 mb-1 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
          {renderGradePills(trimmed.replace(/^#+\s*/, ''))}
        </h3>
      );
      continue;
    }
    // H2 heading (##)
    if (/^## /.test(trimmed)) {
      elements.push(
        <h4 key={i} className={`text-[10.5px] font-semibold mt-2 mb-0.5 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
          {renderGradePills(trimmed.replace(/^#+\s*/, ''))}
        </h4>
      );
      continue;
    }
    // H3+ heading (###)
    if (/^###/.test(trimmed)) {
      elements.push(
        <h5 key={i} className={`text-[10px] font-medium mt-1.5 mb-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {renderGradePills(trimmed.replace(/^#+\s*/, ''))}
        </h5>
      );
      continue;
    }
    // Bullet point
    if (/^-\s/.test(trimmed)) {
      elements.push(
        <div key={i} className={`flex gap-1.5 mt-0.5 text-[11px] leading-relaxed ${baseText}`}>
          <span className="mt-1 flex-shrink-0 w-1 h-1 rounded-full bg-current opacity-50" />
          <span>{renderGradePills(trimmed.replace(/^-\s*/, ''))}</span>
        </div>
      );
      continue;
    }
    // Normal paragraph line
    elements.push(
      <p key={i} className={`text-[11px] leading-relaxed ${baseText} ${i > 0 ? 'mt-0.5' : ''}`}>
        {renderGradePills(trimmed)}
      </p>
    );
  }

  // Flush any remaining rec lines
  if (recLines.length > 0) {
    elements.push(
      <RecommendationBox key="recs-final" lines={recLines} isDark={isDark} />
    );
  }

  return <div>{elements}</div>;
}

/** Highlighted box for extracted Grade A/B recommendations */
function RecommendationBox({ lines, isDark }) {
  if (!lines || lines.length === 0) return null;
  return (
    <div className={`mt-2 mb-2 rounded-lg border overflow-hidden ${
      isDark ? 'border-emerald-500/20 bg-emerald-900/10' : 'border-emerald-500/20 bg-emerald-50/60'
    }`}>
      <div className={`px-2.5 py-1.5 flex items-center gap-1.5 border-b ${
        isDark ? 'border-emerald-500/15 bg-emerald-900/20' : 'border-emerald-500/15 bg-emerald-50'
      }`}>
        <Check className="w-3 h-3 text-emerald-500" strokeWidth={2.5} />
        <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-500">Recommendations</span>
      </div>
      <div className="px-2.5 py-1.5 space-y-1">
        {lines.map((line, i) => (
          <div key={i} className={`text-[11px] leading-relaxed flex gap-1.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            <span className="flex-shrink-0 mt-0.5">→</span>
            <span>{renderGradePills(line)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** A single collapsible evidence tier */
function EvidenceTier({ icon, label, defaultOpen = false, children, isDark, accentColor = 'slate', badge }) {
  const [open, setOpen] = useState(defaultOpen);
  const colorMap = {
    emerald: isDark ? 'text-emerald-400 hover:bg-emerald-900/20' : 'text-emerald-600 hover:bg-emerald-50',
    sky:     isDark ? 'text-sky-400 hover:bg-sky-900/20'         : 'text-sky-600 hover:bg-sky-50',
    slate:   isDark ? 'text-slate-400 hover:bg-slate-700/30'     : 'text-slate-500 hover:bg-slate-100',
  };
  const iconColor = colorMap[accentColor] || colorMap.slate;
  return (
    <div className={`rounded-lg border overflow-hidden ${
      isDark ? 'border-white/8' : 'border-slate-200/80'
    }`}>
      <button
        onClick={() => setOpen(v => !v)}
        className={`w-full flex items-center gap-2 px-3 py-2 text-left text-[11px] font-semibold transition-colors ${iconColor} ${
          isDark ? 'bg-white/3 hover:bg-white/5' : 'bg-slate-50/80 hover:bg-slate-100'
        }`}
      >
        <span className="text-[13px] leading-none">{icon}</span>
        <span className="flex-1">{label}</span>
        {badge && (
          <span className={`text-[9px] font-bold font-sans px-1.5 py-0.5 rounded ${
            isDark ? 'bg-white/8 text-slate-500' : 'bg-slate-200 text-slate-400'
          }`}>{badge}</span>
        )}
        <span className={`flex-shrink-0 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
          {open
            ? <ChevronUp className="w-3.5 h-3.5" strokeWidth={2} />
            : <ChevronDown className="w-3.5 h-3.5" strokeWidth={2} />}
        </span>
      </button>
      {open && (
        <div className={`px-3 pt-2 pb-3 border-t ${
          isDark ? 'border-white/5 bg-slate-900/30' : 'border-slate-100 bg-white'
        }`}>
          {children}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Source preview — truncated flat text with expand toggle.
   If sectionNum is provided (e.g. '7.1.4'), seeks to that
   subsection heading within the text so the preview starts
   at the relevant paragraph, not the top of a larger chunk.
   ============================================================ */
function SourcePreview({ text, sectionNum, previewLimit = 600, isDark }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return null;

  // Try to seek to the specific subsection within the text
  let relevantText = text;
  let seeked = false;
  if (sectionNum && text.length > previewLimit) {
    // Look for heading patterns like "7.1.4" or "7.1.4:" or "## 7.1.4"
    const escapedNum = sectionNum.replace(/\./g, '\\.');
    const patterns = [
      new RegExp(`^#{1,4}\\s*(?:Section\\s*)?${escapedNum}[:\\s]`, 'im'),
      new RegExp(`(?:^|\\n)\\s*${escapedNum}[.:\\s]`, 'i'),
      new RegExp(`(?:^|\\n)\\s*(?:Section\\s*)?${escapedNum}\\b`, 'i'),
    ];
    for (const pat of patterns) {
      const match = text.match(pat);
      if (match && match.index != null && match.index > 0) {
        relevantText = text.slice(match.index).trimStart();
        seeked = true;
        break;
      }
    }
  }

  const isLong = relevantText.length > previewLimit;
  const displayText = expanded || !isLong ? relevantText : relevantText.slice(0, previewLimit);

  return (
    <div className={`px-3.5 pb-3 ${isDark ? 'bg-slate-900/20' : 'bg-slate-50/60'}`}>
      <div className={`p-2.5 rounded-lg border text-[11px] leading-relaxed max-h-64 overflow-y-auto ${
        isDark
          ? 'bg-slate-900/50 border-white/5 text-slate-400'
          : 'bg-white border-slate-200 text-slate-500'
      }`}>
        <CpgTextBlock text={displayText} isDark={isDark} muted={true} />
        {isLong && !expanded && (
          <span className="text-[10px] text-slate-500">{"\u2026"}</span>
        )}
      </div>
      {(isLong || seeked) && (
        <div className="flex gap-3 mt-1.5">
          {isLong && (
            <button
              onClick={() => setExpanded(v => !v)}
              className={`text-[10px] font-medium transition-colors ${
                isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              {expanded ? 'Show less' : `Show full text (${Math.round(relevantText.length / 1000)}k chars)`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function CpgReferenceCard({ cpgRef, isDark, onOpenSource }) {
  const hasContext = Boolean(cpgRef?.context);
  const hasMatchedClause = Boolean(cpgRef?.matchedClause);
  const hasSectionContext = Boolean(cpgRef?.sectionContext);
  const hasBroaderContext = Boolean(cpgRef?.broaderContext);
  const hasLegacyText = !hasMatchedClause && Boolean(cpgRef?.originalText);

  const legacyMatchedClause = React.useMemo(() => {
    if (!hasLegacyText || !cpgRef?.originalText) return null;
    const text = cpgRef.originalText;
    const matchedMarker = 'Matched Clause:\n';
    const matchedIdx = text.indexOf(matchedMarker);
    if (matchedIdx !== -1) return text.slice(matchedIdx + matchedMarker.length).trim();
    const hasParentMarker = text.includes('Parent Section Context:\n') || text.includes('Section Context:\n');
    return hasParentMarker ? null : text;
  }, [hasLegacyText, cpgRef?.originalText]);

  const legacyBroaderContext = React.useMemo(() => {
    if (!hasLegacyText || !cpgRef?.originalText) return null;
    const text = cpgRef.originalText;
    const matchedIdx = text.indexOf('Matched Clause:\n');
    if (matchedIdx === -1) return null;
    return text.slice(0, matchedIdx).trim() || null;
  }, [hasLegacyText, cpgRef?.originalText]);

  const hasAnySourceEffective = hasMatchedClause || Boolean(legacyMatchedClause) || Boolean(legacyBroaderContext) || hasSectionContext || hasBroaderContext;

  // Section depth coloring — deeper sections get warmer accent
  const sectionNum = cpgRef?.sectionNum || '';
  const sectionDepth = sectionNum ? sectionNum.split('.').length : 0;
  const accentBorder =
    sectionDepth >= 3 ? 'border-l-emerald-500' :
    sectionDepth === 2 ? 'border-l-sky-500' :
                         'border-l-violet-500';
  const sectionBadgeColor =
    sectionDepth >= 3
      ? (isDark ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25' : 'bg-emerald-50 text-emerald-700 border-emerald-200')
      : sectionDepth === 2
        ? (isDark ? 'bg-sky-500/15 text-sky-400 border-sky-500/25' : 'bg-sky-50 text-sky-700 border-sky-200')
        : (isDark ? 'bg-violet-500/15 text-violet-400 border-violet-500/25' : 'bg-violet-50 text-violet-700 border-violet-200');

  return (
    <div className={`rounded-lg border-l-[3px] border border-l-[3px] transition-all duration-200 overflow-hidden ${accentBorder} ${
      isDark
        ? 'bg-slate-800/30 border-slate-700/50'
        : 'bg-white border-slate-200'
    }`}>

      {/* Header: Section badge + Intervention (primary content) */}
      <div className="px-3.5 pt-3 pb-2.5">
        {/* Section label */}
        {cpgRef.section && (
          <span className={`inline-block text-[10px] font-bold font-sans px-2 py-0.5 rounded border mb-1.5 ${sectionBadgeColor}`}>
            Section {sectionNum}
          </span>
        )}

        {/* Primary content: What this reference is used for */}
        {cpgRef?.usedBy?.length > 0 && (
          <div className="flex items-start gap-2 mt-1">
            <Pill className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${isDark ? 'text-[var(--accent-primary)]' : 'text-[var(--accent-primary)]'}`} strokeWidth={1.8} />
            <div className="flex-1 min-w-0">
              {cpgRef.usedBy.map((u, i) => (
                <span key={i} className={`text-[12px] font-semibold leading-snug ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  {u}{i < cpgRef.usedBy.length - 1 ? ', ' : ''}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Verify Source — opens side drawer with full chunk */}
      {hasAnySourceEffective && (
        <div className={`border-t ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
          <button
            onClick={() => onOpenSource?.({ ...cpgRef, legacyMatchedClause, legacyBroaderContext })}
            className={`w-full flex items-center gap-1.5 px-3.5 py-1.5 text-left transition-colors ${
              isDark
                ? 'text-slate-500 hover:text-slate-300 hover:bg-white/3'
                : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'
            }`}
          >
            <FileText className="w-3 h-3" strokeWidth={2} />
            <span className="text-[10px] font-medium">View source chunk</span>
            <span className="flex-1" />
            <ArrowRight className="w-3 h-3" strokeWidth={2} />
          </button>
        </div>
      )}
    </div>
  );
}

function CpgReferenceGroup({ group, isDark, onOpenSource }) {
  const [open, setOpen] = useState(true);
  const count = group.refs.length;

  return (
    <div className={`rounded-xl border overflow-hidden ${
      isDark ? 'border-slate-700/50' : 'border-slate-200'
    }`}>
      {/* Group header */}
      <button
        onClick={() => setOpen(v => !v)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
          isDark
            ? 'bg-[var(--accent-primary)]/8 hover:bg-[var(--accent-primary)]/12'
            : 'bg-[var(--accent-primary)]/5 hover:bg-[var(--accent-primary)]/10'
        }`}
      >
        <BookOpen className="w-4 h-4 flex-shrink-0 text-[var(--accent-primary)]" strokeWidth={1.7} />
        <div className="flex-1 min-w-0">
          <span className={`text-sm font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
            {group.cpgFullName}
          </span>
          <span className={`ml-2 text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            {count} reference{count !== 1 ? 's' : ''}
          </span>
        </div>
        <div className={`flex-shrink-0 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          {open
            ? <ChevronUp className="w-4 h-4" strokeWidth={2} />
            : <ChevronDown className="w-4 h-4" strokeWidth={2} />}
        </div>
      </button>

      {/* Refs inside */}
      {open && (
        <div className={`flex flex-col gap-1.5 p-3 ${isDark ? 'bg-slate-900/30' : 'bg-slate-50/50'}`}>
          {group.refs.map((ref, idx) => (
            <CpgReferenceCard key={idx} cpgRef={ref} isDark={isDark} onOpenSource={onOpenSource} />
          ))}
        </div>
      )}
    </div>
  );
}



/* ── Side drawer: full CPG chunk with section context ── */
function CpgReferenceDrawer({ cpgRef, onClose, isDark }) {
  useEffect(() => {
    if (!cpgRef) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cpgRef, onClose]);

  if (!cpgRef) return null;

  const matched = cpgRef.matchedClause || cpgRef.legacyMatchedClause || '';
  const section = cpgRef.sectionContext || '';
  const parent = cpgRef.broaderContext || cpgRef.legacyBroaderContext || '';
  const fallback = !matched && !section && !parent ? (cpgRef.originalText || '') : '';

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]"
      />
      <aside
        role="dialog"
        aria-label="CPG source chunk"
        className={`fixed top-0 right-0 z-50 h-full w-full max-w-[560px] shadow-2xl flex flex-col border-l ${
          isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
        }`}
      >
        {/* Header */}
        <div className={`flex items-start gap-3 px-5 py-4 border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
          <BookOpen className="w-4 h-4 mt-1 flex-shrink-0 text-[var(--accent-primary)]" strokeWidth={1.8} />
          <div className="flex-1 min-w-0">
            <div className={`text-[11px] font-sans ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              {cpgRef.cpgShortName || cpgRef.cpgName || 'CPG'}{cpgRef.sectionNum ? ` § ${cpgRef.sectionNum}` : ''}
            </div>
            <div className={`text-sm font-semibold leading-snug ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
              {cpgRef.cpgFullName || cpgRef.cpgName || 'Source chunk'}
            </div>
            {cpgRef.section && (
              <div className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {cpgRef.section}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className={`p-1.5 rounded-md transition-colors ${
              isDark ? 'text-slate-400 hover:bg-slate-800 hover:text-slate-200' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
            }`}
          >
            <X className="w-4 h-4" strokeWidth={2} />
          </button>
        </div>

        {/* Used-by chips */}
        {cpgRef.usedBy?.length > 0 && (
          <div className={`px-5 py-3 border-b ${isDark ? 'border-slate-800 bg-slate-900/60' : 'border-slate-100 bg-slate-50/60'}`}>
            <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Used by
            </div>
            <div className="flex flex-wrap gap-1.5">
              {cpgRef.usedBy.map((u, i) => (
                <span
                  key={i}
                  className={`text-[11px] px-2 py-0.5 rounded-md border ${
                    isDark ? 'bg-slate-800 text-slate-300 border-slate-700' : 'bg-white text-slate-700 border-slate-200'
                  }`}
                >
                  {u}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Body — chunk content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {matched && (
            <div>
              <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 text-[var(--accent-primary)]`}>
                Matched clause
              </div>
              <div className={`p-3 rounded-lg border text-[12.5px] leading-relaxed ${
                isDark ? 'bg-slate-800/60 border-slate-700 text-slate-200' : 'bg-emerald-50/40 border-emerald-200 text-slate-800'
              }`}>
                <CpgTextBlock text={matched} isDark={isDark} />
              </div>
            </div>
          )}
          {section && (
            <div>
              <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                Section context
              </div>
              <div className={`p-3 rounded-lg border text-[12px] leading-relaxed ${
                isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-slate-200 text-slate-600'
              }`}>
                <CpgTextBlock text={section} isDark={isDark} muted />
              </div>
            </div>
          )}
          {parent && (
            <div>
              <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                Parent section
              </div>
              <div className={`p-3 rounded-lg border text-[12px] leading-relaxed ${
                isDark ? 'bg-slate-900/40 border-slate-800 text-slate-400' : 'bg-white border-slate-200 text-slate-500'
              }`}>
                <CpgTextBlock text={parent} isDark={isDark} muted />
              </div>
            </div>
          )}
          {fallback && (
            <div className={`p-3 rounded-lg border text-[12px] leading-relaxed ${
              isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-slate-200 text-slate-600'
            }`}>
              <CpgTextBlock text={fallback} isDark={isDark} muted />
            </div>
          )}
          {!matched && !section && !parent && !fallback && (
            <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              No chunk content available for this reference.
            </p>
          )}
        </div>
      </aside>
    </>
  );
}

/* ============================================================
   MAIN — Care Plan section (Tabbed layout)
   ============================================================ */
function parseUnresolvedQuestion(q) {
  const dashMatch = q.match(/\s+(?:—|-|–)\s+/);
  if (dashMatch) {
    const title = q.slice(0, dashMatch.index).replace(/\*\*/g, '').trim();
    const desc = q.slice(dashMatch.index + dashMatch[0].length).trim();
    return { title, desc };
  }
  return { title: q.replace(/\*\*/g, ''), desc: null };
}

/* Unresolved Questions — sub-grouped into three clinical categories:
   - medication_interaction:  drug–drug interactions, dose adjustments, contraindications
   - evidence_gap:            CPG does not specify — apply clinical judgement
   - missing_data:            patient data not available (labs, history, etc.)
   Bucketing uses keyword heuristics on the question text. */
function classifyUnresolved(q) {
  const stripped = (q || '').replace(/\*\*/g, '').trim().toLowerCase();
  // Medication Interaction keywords
  if (
    /interaction/i.test(stripped) ||
    /dose\s*(adjustment|reduction|titrat)/i.test(stripped) ||
    /concurrent/i.test(stripped) ||
    /contraindic/i.test(stripped) ||
    /warfarin|amiodarone|fluconazole|inr|anticoagul/i.test(stripped) ||
    /drug[- ]drug/i.test(stripped) ||
    /co-administ/i.test(stripped) ||
    /pharmacist/i.test(stripped)
  ) return 'medication_interaction';
  // Missing Data keywords
  if (
    /not\s*(provided|available|recorded|known|documented|reported)/i.test(stripped) ||
    /missing|awaiting\s*data|unknown|not\s*specified.*(?:patient|this)/i.test(stripped) ||
    /renal\s*function|liver\s*function|lab|baseline|creatinine|egfr/i.test(stripped) ||
    /^Assumption:/i.test(q.replace(/\*\*/g, '').trim())
  ) return 'missing_data';
  // Everything else is an evidence gap
  return 'evidence_gap';
}

const UNRESOLVED_CATEGORY_CONFIG = {
  medication_interaction: {
    label: 'Medication Interaction',
    hint: 'Drug–drug interactions and dose adjustment concerns.',
    headerBg: 'bg-orange-50 dark:bg-orange-950/30',
    headerText: 'text-orange-600 dark:text-orange-400',
    bodyBg: 'bg-transparent',
    bodyBorder: 'border-orange-100 dark:border-orange-900/30',
    bulletBg: 'bg-orange-400 dark:bg-orange-500',
    titleColor: 'text-slate-900 dark:text-slate-50',
    descColor: 'text-slate-600 dark:text-slate-300',
    countBg: 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300',
    icon: 'pill',
  },
  evidence_gap: {
    label: 'Evidence Gaps',
    hint: 'CPG does not specify — apply clinical judgement.',
    headerBg: 'bg-blue-50 dark:bg-blue-950/30',
    headerText: 'text-blue-600 dark:text-blue-400',
    bodyBg: 'bg-transparent',
    bodyBorder: 'border-blue-100 dark:border-blue-900/30',
    bulletBg: 'bg-blue-400 dark:bg-blue-500',
    titleColor: 'text-slate-900 dark:text-slate-50',
    descColor: 'text-slate-600 dark:text-slate-300',
    countBg: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
    icon: 'book',
  },
  missing_data: {
    label: 'Missing Data',
    hint: 'Patient data not available — verify before proceeding.',
    headerBg: 'bg-violet-50 dark:bg-violet-950/30',
    headerText: 'text-violet-600 dark:text-violet-400',
    bodyBg: 'bg-transparent',
    bodyBorder: 'border-violet-100 dark:border-violet-900/30',
    bulletBg: 'bg-violet-400 dark:bg-violet-500',
    titleColor: 'text-slate-900 dark:text-slate-50',
    descColor: 'text-slate-600 dark:text-slate-300',
    countBg: 'bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300',
    icon: 'alert',
  },
};

const UNRESOLVED_CATEGORY_ORDER = ['medication_interaction', 'evidence_gap', 'missing_data'];

function UnresolvedCategorySection({ categoryKey, items, isDark }) {
  const [open, setOpen] = useState(true);
  const cfg = UNRESOLVED_CATEGORY_CONFIG[categoryKey];
  if (!cfg || items.length === 0) return null;

  // Drive text colour from the app theme (isDark), NOT Tailwind `dark:` variants:
  // Tailwind dark mode here follows the OS (prefers-color-scheme), so when the app
  // theme is light but the OS is dark, `dark:` text renders light-on-light.
  const titleColor = isDark ? 'text-slate-100' : 'text-slate-900';
  const descColor  = isDark ? 'text-slate-300' : 'text-slate-600';

  const iconEl = categoryKey === 'medication_interaction'
    ? <Pill className="w-3.5 h-3.5" strokeWidth={2} />
    : categoryKey === 'evidence_gap'
      ? <BookOpen className="w-3.5 h-3.5" strokeWidth={2} />
      : <AlertCircle className="w-3.5 h-3.5" strokeWidth={2} />;

  return (
    <div className={`rounded-xl overflow-hidden border ${cfg.bodyBorder} transition-colors`}>
      {/* Colored header bar */}
      <button
        onClick={() => setOpen(v => !v)}
        className={`w-full flex items-center gap-2 px-3.5 py-2.5 text-left ${cfg.headerBg} ${cfg.headerText}`}
      >
        {iconEl}
        <span className="text-[11px] font-bold uppercase tracking-wider flex-1">{cfg.label}</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${cfg.countBg}`}>
          {items.length}
        </span>
        <span className="ml-1 opacity-70 hover:opacity-100 transition-opacity">
          {open
            ? <ChevronUp className="w-3.5 h-3.5" strokeWidth={2} />
            : <ChevronDown className="w-3.5 h-3.5" strokeWidth={2} />}
        </span>
      </button>

      {/* Items */}
      {open && (
        <div className={`px-3.5 pb-3 pt-1 ${cfg.bodyBg} space-y-2`}>
          {items.map((q, i) => {
            const cleaned = q.replace(/^(Assumption|Cross-check):\s*/i, '');
            const parsed = parseUnresolvedQuestion(cleaned);
            return (
              <div key={i} className="flex gap-2 items-start">
                <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.bulletBg}`} />
                <div className="flex-1 min-w-0">
                  <p className={`text-[12px] font-semibold leading-snug ${titleColor}`}>
                    {parsed.title}
                  </p>
                  {parsed.desc && (
                    <p className={`text-[11px] leading-relaxed mt-0.5 ${descColor}`}>
                      {parsed.desc}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function UnresolvedQuestionsPanel({ qs, isDark }) {
  const grouped = qs.reduce((acc, q) => {
    const k = classifyUnresolved(q);
    (acc[k] = acc[k] || []).push(q);
    return acc;
  }, {});

  return (
    <div className={`rounded-xl border p-3.5 space-y-2.5 ${
      isDark ? 'bg-slate-800/30 border-white/10' : 'bg-white/60 border-slate-200'
    }`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <AlertCircle className="w-4 h-4 text-amber-500" strokeWidth={2} />
        <span className="text-sm font-bold text-amber-500">Unresolved Questions</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
          isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-700'
        }`}>
          {qs.length}
        </span>
      </div>

      {/* Category sections */}
      {UNRESOLVED_CATEGORY_ORDER.map((key) => (
        <UnresolvedCategorySection
          key={key}
          categoryKey={key}
          items={grouped[key] || []}
          isDark={isDark}
        />
      ))}
    </div>
  );
}

export function CarePlanSection() {
  const { state, dispatch, finalizePlan, goToStep, applySafetyDecisions } = useApp();
  const { isDark } = useTheme();
  const { user, profile } = useAuth();
  const clinicianName = profile?.full_name || user?.email || 'Unknown clinician';
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
  const [safetyAckAt, setSafetyAckAt] = useState(null);
  const [safetyDecisions, setSafetyDecisions] = useState(null);
  const [highlightedMedId, setHighlightedMedId] = useState(null);

  const jumpToMed = (medId) => {
    setTab('meds');
    setHighlightedMedId(medId);
    // Scroll after the tab has had a chance to render
    setTimeout(() => {
      const el = document.getElementById(`med-row-${medId}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 50);
    // Fade highlight after 2s
    setTimeout(() => setHighlightedMedId(null), 2500);
  };
  const [tab, setTab] = useState('overview');
  const [drawerRef, setDrawerRef] = useState(null);

  const safetyBlocksApprove = safetyReport && !safetyReport.safe_to_proceed && !safetyAcknowledged;

  if (!carePlan) return null;

  const handleBack = () => goToStep(2);

  // Persist a clinician feedback event to the human_signals table. Best-effort:
  // a failed insert must never block the approve/reject/regenerate UI flow.
  const recordHumanSignal = (action, comment) => {
    saveHumanSignal({
      consultationId: state.currentConsultationId,
      nric: state.patient?.nsn,
      action,
      comment,
      clinicianId: profile?.id,
      clinicianName,
      // a plan the Stage-6 critic blocked was shipped only if it was unsafe AND ack'd
      safetyOverridden: !!(safetyReport && !safetyReport.safe_to_proceed && safetyAcknowledged),
      cpgReferences: carePlan?.cpgReferences || null,
    }).catch((err) => console.error('human_signals capture failed:', err));
  };

  const handleStatusChange = (newStatus, comment) => {
    setWorkflowStatus(newStatus);
    setWorkflowHistory((prev) => [
      { status: newStatus, action: newStatus === WORKFLOW_STATES.REVIEWED ? 'Marked as Reviewed' : 'Approved', user: clinicianName, timestamp: new Date().toLocaleString(), comment },
      ...prev,
    ]);
    if (newStatus === WORKFLOW_STATES.APPROVED) recordHumanSignal('approved', comment);
  };
  const handleReject = (comment) => {
    setWorkflowStatus(WORKFLOW_STATES.DRAFT);
    setWorkflowHistory((prev) => [
      { status: WORKFLOW_STATES.DRAFT, action: 'Sent back for revision', user: clinicianName, timestamp: new Date().toLocaleString(), comment },
      ...prev,
    ]);
    recordHumanSignal('rejected', comment);
  };
  const handleRegenerate = async (feedback) => {
    console.log('Regenerating with feedback:', feedback);
    recordHumanSignal('regenerate', feedback);
    await new Promise((resolve) => setTimeout(resolve, 1500));
  };

  const handleNextReviewChange = (date) => {
    dispatch({ type: 'SET_NEXT_REVIEW_DATE', payload: date });
    if (date) {
      dispatch({ type: 'SET_PATIENT_STATUS', payload: 'follow-up' });
    } else {
      dispatch({ type: 'SET_PATIENT_STATUS', payload: null });
    }
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
    (carePlan.medications?.contraindicated?.length || 0) +
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
  const refsGroupCount = carePlan.cpgReferenceGroups?.length || 0;

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
              {/* Diagnosis + Allergies: card-based layout */}
              <div className="grid grid-cols-2 gap-4">
                {/* Diagnoses Column */}
                <div>
                  <span className={`text-[11px] font-bold uppercase tracking-wider ${isDark ? 'text-teal-400' : 'text-teal-600'}`}>
                    Diagnoses{selectedDiagnoses.length > 0 ? ` (${selectedDiagnoses.length})` : ''}
                  </span>
                  {selectedDiagnoses.length > 0 ? (
                    <div className="mt-2 space-y-2">
                      {selectedDiagnoses.map((d) => (
                        <div
                          key={d.id}
                          className={`p-3 rounded-xl border transition-all ${
                            isDark
                              ? 'bg-slate-800/60 border-slate-700/60 hover:border-slate-600'
                              : 'bg-white border-slate-200 shadow-sm hover:shadow-md'
                          }`}
                        >
                          <div className="flex-1 min-w-0">
                            <p className={`text-[13px] font-semibold leading-snug ${isDark ? 'text-white' : 'text-slate-800'}`}>
                              {d.name}
                            </p>
                            {d.icdCode && (
                              <span className={`text-[10px] font-medium mt-1 inline-block ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                                ICD-11: {d.icdCode}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className={`text-sm mt-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>None selected</p>
                  )}
                </div>

                {/* Allergies Column */}
                <div>
                  <span className={`text-[11px] font-bold uppercase tracking-wider ${isDark ? 'text-teal-400' : 'text-teal-600'}`}>
                    Allergies
                  </span>
                  <div className="mt-2">
                    {allergiesList.length > 0 ? (
                      <div className="space-y-2">
                        {allergiesList.map((a, idx) => (
                          <div
                            key={idx}
                            className={`p-3 rounded-xl border ${
                              isDark
                                ? 'bg-red-950/30 border-red-500/20'
                                : 'bg-red-50/60 border-red-200 shadow-sm'
                            }`}
                          >
                            <span className={`text-[13px] font-semibold ${isDark ? 'text-red-300' : 'text-red-700'}`}>{a}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className={`p-3 rounded-xl border flex items-center gap-2 ${
                        isDark
                          ? 'bg-slate-800/60 border-slate-700/60'
                          : 'bg-white border-slate-200 shadow-sm'
                      }`}>
                        <span className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${
                          isDark ? 'bg-emerald-500/15 text-emerald-400' : 'bg-emerald-50 text-emerald-500'
                        }`}>
                          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                        </span>
                        <span className={`text-[13px] font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>None known</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Critical Vitals */}
              {(() => {
                const v = vitals;
                const abnormals = [];
                if (v?.bpSystolic && parseInt(v.bpSystolic) > 140) abnormals.push({ label: 'SBP', value: `${v.bpSystolic} mmHg \u2191`, color: 'text-red-500' });
                if (v?.bpDiastolic && parseInt(v.bpDiastolic) > 90) abnormals.push({ label: 'DBP', value: `${v.bpDiastolic} mmHg \u2191`, color: 'text-red-500' });
                if (v?.hr && parseInt(v.hr) > 100) abnormals.push({ label: 'HR', value: `${v.hr} bpm \u2191`, color: 'text-amber-500' });
                if (v?.spo2 && parseInt(v.spo2) < 95) abnormals.push({ label: 'SpO\u2082', value: `${v.spo2}% \u2193`, color: 'text-red-500' });
                if (v?.temp && parseFloat(v.temp) > 37.5) abnormals.push({ label: 'Temp', value: `${v.temp} \u00B0C \u2191`, color: 'text-amber-500' });
                if (abnormals.length === 0) return null;
                return (
                  <div>
                    <span className={`text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      <TrendingUp className="w-3 h-3 text-red-400" strokeWidth={1.5} /> Critical Vitals
                    </span>
                    <div className={`mt-1 p-2 rounded-lg grid grid-cols-2 gap-x-3 gap-y-1 ${isDark ? 'bg-red-900/20 border border-red-500/20' : 'bg-red-50 border border-red-100'}`}>
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

              {/* AI Reasoning Trace */}
              <PipelineProgress
                pipelineEvents={state.pipelineEvents}
                pipelineThinking={state.pipelineThinking}
                summary={state.pipelineSummary}
                isLive={false}
                resynthOverride={state.resynthOverride}
                collapsed={traceCollapsed}
                onToggle={() => setTraceCollapsed((prev) => !prev)}
              />

              {/* Unresolved Questions — collapsible, shows first 3 */}
              {carePlan?.unresolvedQuestions?.length > 0 && (
                <UnresolvedQuestionsPanel qs={carePlan.unresolvedQuestions} isDark={isDark} />
              )}
            </div>
          </GlassCard>
        </div>

        {/* ============ RIGHT PANEL: Tabbed Actionable Plan ============ */}
        <div className="lg:col-span-8 space-y-4">
          <SafetyReviewBanner
            report={safetyReport}
            plannedMeds={Object.entries(carePlan?.medications || {}).flatMap(([section, list]) =>
              (list || []).map((m) => ({ id: m.id, name: m.name, section }))
            )}
            currentMeds={patientData?.currentMedications || patientData?.current_medications || []}
            onJumpToMed={jumpToMed}
            acknowledged={safetyAcknowledged}
            onAcknowledge={(decisions) => {
              applySafetyDecisions(decisions);
              setSafetyDecisions(decisions);
              setSafetyAcknowledged(true);
              setSafetyAckAt(new Date().toISOString());
            }}
          />

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
                      ...(carePlan.medications.stop || []).map((m) => ({ ...m, _origAction: 'stop' })),
                      ...(carePlan.medications.start || []).map((m) => ({ ...m, _origAction: 'start' })),
                      ...(carePlan.medications.change || []).map((m) => ({ ...m, _origAction: 'change' })),
                    ].map((m) => {
                      const effectiveAction = m.displayAction || m._origAction;
                      const toneMap = { stop: 'danger', start: 'ok', change: 'warn', continue: 'info' };
                      const tagToneMap = { stop: 'danger', start: 'accent', change: 'warn', continue: 'default' };
                      return (
                        <MedListRow
                          key={`${m._origAction}-${m.id}`}
                          bulletTone={toneMap[effectiveAction] || 'ok'}
                          drugName={m._origAction === 'change' ? `${m.name} (${m.previousDose} → ${m.newDose})` : m.name}
                          dose={m._origAction !== 'change' ? m.dose : null}
                          description={m.reason}
                          tag={ACTION_STYLES[effectiveAction]?.label || effectiveAction.toUpperCase()}
                          tagTone={tagToneMap[effectiveAction] || 'accent'}
                          graphRule={pickBestRuleForMed(m.name, graphNavigatorRules)}
                        />
                      );
                    })}
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
                    {(carePlan.redFlags || []).map((f, i) => <RedFlagRow key={f || i} text={f} />)}
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
              <MedicationsTable medications={carePlan.medications} dispatch={dispatch} graphRules={graphNavigatorRules} highlightedMedId={highlightedMedId} />
            </Section>
          )}

          {/* ── CARE & MONITORING ──────────────────────────────── */}
          {tab === 'care' && <CareMonitoringPanel carePlan={carePlan} dispatch={dispatch} />}

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
                  {(carePlan.redFlags || []).map((f, i) => <RedFlagRow key={f || i} text={f} />)}
                </div>
              </Section>
            </>
          )}

          {tab === 'refs' && (
            <Section title="CPG References" icon={BookOpen} count={refsCount}>
              {/* Summary line */}
              {refsGroupCount > 0 && (
                <p className={`text-xs mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {refsCount} reference{refsCount !== 1 ? 's' : ''} from {refsGroupCount} guideline{refsGroupCount !== 1 ? 's' : ''}
                </p>
              )}
              <div className="flex flex-col gap-3">
                {(carePlan.cpgReferenceGroups || []).map((group, idx) => (
                  <CpgReferenceGroup key={idx} group={group} isDark={isDark} onOpenSource={setDrawerRef} />
                ))}
                {refsCount === 0 && (
                  <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    No CPG references were matched for this plan.
                  </p>
                )}
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
              nextReviewDate={state.nextReviewDate || ''}
              onNextReviewChange={handleNextReviewChange}
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
          onClick={() => finalizePlan({
            safetyOverride: safetyReport && !safetyReport.safe_to_proceed
              ? { acknowledged: safetyAcknowledged, by: clinicianName, at: safetyAckAt, decisions: safetyDecisions }
              : null,
          })}
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

      <CpgReferenceDrawer cpgRef={drawerRef} onClose={() => setDrawerRef(null)} isDark={isDark} />
    </div>
  );
}
