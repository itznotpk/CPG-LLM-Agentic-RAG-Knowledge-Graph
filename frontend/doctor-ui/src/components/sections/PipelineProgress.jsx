import React, { useRef, useEffect, useState } from 'react';
import {
  CheckCircle, AlertCircle, Loader2, Circle,
  BrainCircuit, ChevronDown, ChevronUp, RefreshCw, FileText,
} from 'lucide-react';
import { GlassCard } from '../shared';
import { useTheme } from '../../context/ThemeContext';

const STAGE_DEFS = [
  { stage: 2, num: '01', label: 'DDx Analysis',      hasThinking: true,  pendingDescription: 'Parses clinical notes to extract symptoms and rank candidate diagnoses.' },
  { stage: 3, num: '02', label: 'CPG Routing',        hasThinking: false, pendingDescription: 'Routes confirmed diagnoses to matching clinical practice guidelines (runs on Confirm).' },
  { stage: 4, num: '03', label: 'Evidence Retrieval', hasThinking: false, pendingDescription: 'Retrieves relevant clinical rules, recommendations, and evidence (runs on Confirm).' },
  { stage: 5, num: '04', label: 'Plan Synthesis',     hasThinking: false, pendingDescription: 'Synthesizes guideline-backed care recommendations and performs safety checks (runs on Confirm).' },
];

const FRIENDLY_ERRORS = {
  429: 'API quota exhausted — check billing at AI Studio.',
  401: 'API key invalid or expired.',
  500: 'Upstream model error. Try again in a moment.',
  503: 'Service temporarily unavailable.',
};

function getFriendlyError(detail) {
  if (!detail) return 'Unexpected error. See console for details.';
  const code = Object.keys(FRIENDLY_ERRORS).find(c => String(detail).includes(c));
  return code ? FRIENDLY_ERRORS[code] : 'An error occurred during this step.';
}

const MATCH_TYPE_COLORS = {
  exact:    'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  parent:   'bg-blue-500/20   text-blue-400    border-blue-500/30',
  range:    'bg-blue-500/20   text-blue-400    border-blue-500/30',
  semantic: 'bg-amber-500/20  text-amber-400   border-amber-500/30',
  fallback: 'bg-red-500/20    text-red-400     border-red-500/30',
  DDx:      'bg-indigo-500/20 text-indigo-300  border-indigo-500/30',
  excluded: 'bg-red-500/20    text-red-400     border-red-500/30',
  out_of_scope: 'bg-slate-600/30 text-slate-400 border-slate-500/40',
};

// Keys are normalised (lowercased, spaces → underscores) so both the engine's
// snake_case keys and the LLM's free-form ones (e.g. "Sibling Cluster") map to
// the same plain-language label.
const OVERRIDE_KEY_MAP = {
  'red_flag_cant_miss': "Can't-miss red flag",
  'specificity_over_generic': 'More exact diagnosis',
  'clinical_contradiction': 'Conflicts with the clinical picture',
  'clinical_contradiction_rule': 'Conflicts with a clinical rule',
  'presentation_fit': 'Better fits this patient',
  'age_gender_compat': "Fits the patient's age and sex",
  'sex_compat': "Fits the patient's sex",
  'sibling_cluster': 'Merged look-alike codes',
};

function formatOverrideReason(reason) {
  if (!reason) return '';
  const parts = reason.includes(';') ? reason.split(';') : [reason];
  return parts.map(part => {
    const colonIdx = part.indexOf(':');
    if (colonIdx !== -1) {
      const key = part.slice(0, colonIdx).trim();
      const val = part.slice(colonIdx + 1).trim();
      const norm = key.toLowerCase().replace(/\s+/g, '_');
      const prettyKey = OVERRIDE_KEY_MAP[norm] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      return `${prettyKey}: ${val}`;
    }
    return part.trim().replace(/_/g, ' ');
  }).join('; ');
}

// Deep engine-internal sub-steps — collapsed under a "How the AI built its
// shortlist" dropdown rather than shown inline (regex code injection + the
// clinician-named priority codes pulled from the chief complaint).
function isAdvancedSubStep(sub) {
  if (!sub) return false;
  if (sub.kind === 'regex_codes' || sub.kind === 'cc_priority') return true;
  const detail = sub.detail || '';
  return detail.startsWith('Regex-injected codes')
    || detail.startsWith('CC priority codes:')
    || detail.startsWith('Extra codes caught')
    || detail.startsWith('Diagnoses the AI pulled');
}

// Compact before/after re-rank + score-breakdown table for the DDx stage.
// All fields come from the stage-2 stage_update `data` (DDxResult.model_dump()).
function fmtScore(n, sign = false) {
  if (n === null || n === undefined) return '—';
  const v = Number(n);
  const s = v.toFixed(2);
  return sign && v > 0 ? `+${s}` : s;
}

function DDxCandidateRow({ c, i, isDark }) {
  const [open, setOpen] = useState(false);
  const sb = c.score_breakdown || {};
  const mathRank = c.math_rank;
  const aiRank = c.llm_rank ?? i + 1;
  const delta = c.rank_delta;
  const moved = typeof delta === 'number' && delta !== 0;
  const arrow = !moved ? '=' : delta > 0 ? `↑${delta}` : `↓${Math.abs(delta)}`;
  const arrowColor = !moved ? 'text-slate-500' : delta > 0 ? 'text-emerald-400' : 'text-red-400';
  const incl = Number(sb.inclusion_match || 0);
  const ccBoost = Number(sb.cc_boost || 0);
  const ccRaw = sb.cc_boost_raw;
  const excl = Number(sb.exclusion_penalty || 0);

  return (
    <div className={`rounded-lg px-3 py-2 text-xs border ${isDark ? 'bg-slate-800/40 border-slate-700/50' : 'bg-slate-50 border-slate-200'}`}>
      {/* Row 1: rank, code, title, before→after */}
      <div className="flex items-center gap-2">
        <span className="font-sans font-bold text-slate-400 shrink-0">#{aiRank}</span>
        <span className="font-sans text-[var(--accent-primary)] shrink-0">{c.code}</span>
        <span className={`truncate ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{c.title}</span>
        {mathRank != null && (
          <span className="ml-auto shrink-0 font-sans text-[11px] text-slate-500">
            math #{mathRank} → AI #{aiRank}{' '}
            <span className={`font-bold ${arrowColor}`}>{arrow}</span>
          </span>
        )}
      </div>

      {/* Row 2: score breakdown — collapsed under a dropdown (base + incl − excl) */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="mt-1 flex items-center gap-1 font-sans text-[11px] text-slate-500 hover:text-slate-400 transition-colors"
      >
        {open ? <ChevronUp className="w-3 h-3" strokeWidth={1.5} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.5} />}
        {open ? 'Hide score breakdown' : 'Score breakdown'}
      </button>
      {open && (
        <div className={`mt-1 font-sans text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          <span title="base vector similarity">base {fmtScore(sb.base_similarity)}</span>
          <span className={incl > 0 ? 'text-emerald-400' : 'opacity-40'} title={sb.inclusion_phrase || 'inclusion-term match'}>
            {'  + incl '}{fmtScore(incl, true)}
          </span>
          <span className={excl > 0 ? 'text-red-400' : 'opacity-40'} title={sb.exclusion_phrase || 'exclusion-term penalty'}>
            {'  − excl '}{fmtScore(excl)}
          </span>
          <span
            className={`font-bold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}
            title="Evidence (math) score — base + inclusion − exclusion. The list order is the AI clinical rank, which can differ from this."
          >
            {'  = evidence '}{fmtScore(sb.final_score)}
          </span>
          {ccBoost > 0 && (
            <span
              className="ml-2 inline-flex items-center gap-1 text-[10px] text-sky-400"
              title={ccRaw != null ? `Clinician named this diagnosis (CC confidence ${Math.round(ccRaw * 100)}%) — used by LLM rerank only, not in math` : 'Clinician-named — used by LLM rerank only, not in math'}
            >
              · clinician-named (LLM signal)
            </span>
          )}
        </div>
      )}

      {/* Row 3: override reason, if the AI re-ranked against the math order */}
      {c.override_reason && (
        <div className="mt-1 flex items-start gap-1 text-[11px] text-amber-400">
          <span className="shrink-0 font-semibold">Why the AI re-ranked:</span>
          <span className="italic">{formatOverrideReason(c.override_reason)}</span>
        </div>
      )}
    </div>
  );
}

function DDxCandidateTable({ candidates, isDark }) {
  if (!candidates?.length) return null;
  return (
    <div className="mt-2 space-y-1.5">
      {/* Legend: the list is ordered by the AI's clinical rank, which can differ
          from the raw math/evidence score (the AI reweights against patient context). */}
      <div className={`font-sans text-[10px] leading-snug ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        Ordered by AI clinical rank. The <span className="font-semibold">evidence</span> score is
        the raw retrieval signal — the AI may rank against it using patient context.
      </div>
      {candidates.map((c, i) => (
        <DDxCandidateRow key={c.code || i} c={c} i={i} isDark={isDark} />
      ))}
    </div>
  );
}

// Plain-language rich renders for the stage-2 extraction sub-steps. The engine
// emits these as raw "Key: value" / comma-list strings that get truncated on a
// single line — too coding-ish for a clinician. We detect them by prefix and
// render the full query in a callout, and each hypothesised condition as its
// own chip (matching the medication-pill style elsewhere in the app).
const SYMPTOM_QUERY_PREFIX = 'Extracted symptom query:';
const SYMPTOM_FALLBACK_PREFIX = '⚠ Symptom extraction fell back to raw notes:';
const HYPOTHESES_PREFIX = 'Condition hypotheses:';

function stripQuotes(s) {
  return s.trim().replace(/^["“]/, '').replace(/["”]$/, '').trim();
}

function SymptomQueryCallout({ query, isDark, fellBack }) {
  return (
    <div className={`rounded-lg px-3 py-2 border ${
      fellBack
        ? (isDark ? 'bg-amber-900/15 border-amber-500/25' : 'bg-amber-50 border-amber-200')
        : (isDark ? 'bg-indigo-900/15 border-indigo-500/20' : 'bg-indigo-50 border-indigo-200')
    }`}>
      <p className={`text-[11px] font-semibold uppercase tracking-wide ${
        fellBack ? (isDark ? 'text-amber-300' : 'text-amber-700')
                 : (isDark ? 'text-indigo-300' : 'text-indigo-600')
      }`}>
        {fellBack ? 'Searched your notes directly' : 'What the AI searched for'}
      </p>
      <p className={`mt-0.5 text-sm leading-snug ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
        “{query}”
      </p>
    </div>
  );
}

function ConditionHypotheses({ conditions, isDark }) {
  if (!conditions.length) return null;
  return (
    <div>
      <p className={`text-[11px] font-semibold uppercase tracking-wide ${isDark ? 'text-indigo-300' : 'text-indigo-600'}`}>
        Conditions considered
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {conditions.map((c, i) => (
          <span
            key={i}
            className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
              isDark ? 'bg-blue-500/15 text-blue-200 border-blue-500/30'
                     : 'bg-blue-50 text-blue-700 border-blue-200'
            }`}
          >
            {c}
          </span>
        ))}
      </div>
    </div>
  );
}

// Chips for the codes the AI pulled straight from the chief complaint, with a
// plain-language confidence tag (clinician-named vs AI's own confidence %).
function CcPriorityChips({ items, isDark }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className={`text-[11px] font-semibold uppercase tracking-wide ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
        Diagnoses from the chief complaint
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span
            key={i}
            className={`text-xs px-2.5 py-1 rounded-full border font-medium inline-flex items-center gap-1 ${
              isDark ? 'bg-amber-500/15 text-amber-200 border-amber-500/30' : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}
          >
            {it.name || it.code}
            <span className={`text-[10px] font-normal ${isDark ? 'text-amber-300/70' : 'text-amber-600'}`}>
              {it.explicit ? '· you named this' : `· AI ${Math.round((it.confidence || 0) * 100)}% sure`}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

// Chips for the deterministic text-match safety net — codes written in the notes
// that the AI extractor might otherwise have dropped.
function RegexCodesChips({ items, isDark }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className={`text-[11px] font-semibold uppercase tracking-wide ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
        Extra codes found in your notes
      </p>
      <p className={`text-[10px] mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        Safety net — added in case the AI missed a diagnosis written in the notes.
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span
            key={i}
            className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
              isDark ? 'bg-amber-500/15 text-amber-200 border-amber-500/30' : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}
          >
            {it.name ? `${it.name} (${it.code})` : it.code}
          </span>
        ))}
      </div>
    </div>
  );
}

// One retrieved guideline passage: which CPG + section it came from, plus a
// short preview of the text.
function ChunkCard({ c, isDark }) {
  return (
    <div className={`rounded-lg px-2.5 py-1.5 border text-[11px] ${isDark ? 'bg-slate-800/40 border-slate-700/50' : 'bg-white border-slate-200'}`}>
      <div className="flex items-center gap-1.5 min-w-0">
        <FileText className="w-3 h-3 shrink-0 text-[var(--accent-primary)]" strokeWidth={1.5} />
        <span className={`font-medium truncate ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{c.cpg}</span>
        {c.section && <span className="text-slate-500 truncate">› {c.section}</span>}
      </div>
      {c.snippet && (
        <p className={`mt-0.5 leading-snug ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{c.snippet}</p>
      )}
    </div>
  );
}

// A single evidence question + the new passages it pulled (expandable).
function EvidenceQueryRow({ query, data, isDark }) {
  const [open, setOpen] = useState(false);
  const chunks = data?.chunks || [];
  const n = data?.new ?? chunks.length;
  const hasChunks = chunks.length > 0;
  return (
    <div>
      <div className="flex items-start gap-2">
        <button
          onClick={() => hasChunks && setOpen((o) => !o)}
          className={`flex-1 min-w-0 flex items-start gap-1.5 text-left ${hasChunks ? 'cursor-pointer' : 'cursor-default'}`}
        >
          {hasChunks && (open
            ? <ChevronUp className="w-3 h-3 mt-0.5 shrink-0 text-slate-500" strokeWidth={1.5} />
            : <ChevronDown className="w-3 h-3 mt-0.5 shrink-0 text-slate-500" strokeWidth={1.5} />)}
          <span className={`text-xs leading-snug break-words ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{query}</span>
        </button>
        <span
          title={`This question pulled ${n} guideline passage${n === 1 ? '' : 's'} that earlier questions hadn't already found.`}
          className={`shrink-0 text-[11px] px-2 py-0.5 rounded-full border font-medium ${
            n > 0
              ? (isDark ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-emerald-50 text-emerald-700 border-emerald-200')
              : (isDark ? 'bg-slate-700/40 text-slate-400 border-slate-600/40' : 'bg-slate-100 text-slate-500 border-slate-200')
          }`}
        >
          {n > 0 ? `+${n} new passage${n === 1 ? '' : 's'}` : 'no new passages'}
        </span>
      </div>
      {open && hasChunks && (
        <div className="mt-1.5 ml-4 space-y-1.5">
          {chunks.map((c, i) => <ChunkCard key={i} c={c} isDark={isDark} />)}
        </div>
      )}
    </div>
  );
}

// The final deduplicated evidence count — a plain summary line. The per-question
// rows above already let the clinician drill into the actual passages, so we no
// longer dump all 20 chunk cards here.
function EvidenceSummary({ detail, isDark }) {
  return (
    <span className={`text-xs font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{detail}</span>
  );
}

// Returns a rich block for the special sub-steps, or null for plain ones.
function renderRichSub(sub, isDark) {
  const d = sub?.detail || '';
  if (sub?.kind === 'cc_priority') return <CcPriorityChips items={sub.data} isDark={isDark} />;
  if (sub?.kind === 'regex_codes') return <RegexCodesChips items={sub.data} isDark={isDark} />;
  if (sub?.kind === 'evidence_query') return <EvidenceQueryRow query={d} data={sub.data} isDark={isDark} />;
  if (sub?.kind === 'evidence_summary') return <EvidenceSummary detail={d} data={sub.data} isDark={isDark} />;
  if (d.startsWith(SYMPTOM_QUERY_PREFIX))
    return <SymptomQueryCallout query={stripQuotes(d.slice(SYMPTOM_QUERY_PREFIX.length))} isDark={isDark} />;
  if (d.startsWith(SYMPTOM_FALLBACK_PREFIX))
    return <SymptomQueryCallout query={stripQuotes(d.slice(SYMPTOM_FALLBACK_PREFIX.length))} isDark={isDark} fellBack />;
  if (d.startsWith(HYPOTHESES_PREFIX)) {
    const list = d.slice(HYPOTHESES_PREFIX.length).split(',').map((s) => s.trim()).filter(Boolean);
    return <ConditionHypotheses conditions={list} isDark={isDark} />;
  }
  return null;
}

// FALLBACK only. Anchor vs AI-generated questions are now distinguished by the
// backend's structural `anchor` flag on each evidence_query sub-step. This text
// match is used solely for older trace events emitted before that flag existed.
const ANCHOR_QUERY_SIGNATURES = [
  'baseline investigations, tests, and imaging',
  'lifestyle modifications, diet, exercise',
  'specialist referrals indicated and their urgency',
  'ace inhibitor or arni (sacubitril/valsartan)',
  'beta-blocker bisoprolol carvedilol metoprolol',
  'mineralocorticoid receptor antagonist spironolactone eplerenone',
  'sglt2 inhibitor dapagliflozin empagliflozin',
];

function isAnchorQuery(detail) {
  const d = (detail || '').toLowerCase().trim();
  return ANCHOR_QUERY_SIGNATURES.some((sig) => d.startsWith(sig.slice(0, 40)));
}

// Stage sub-steps: normal steps inline; deep internals (regex-injected codes,
// CC priority codes) tucked under a collapsible "Advanced details" dropdown.
function SubSteps({ subs, isDark }) {
  const [advOpen, setAdvOpen] = useState(false);
  if (!subs || subs.length === 0) return null;
  const normal = subs.filter((s) => !isAdvancedSubStep(s));
  const advanced = subs.filter((s) => isAdvancedSubStep(s));

  const groupHeader = (text) => (
    <p className={`text-[10px] font-semibold uppercase tracking-wide pt-1.5 pb-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
      {text}
    </p>
  );

  const renderSub = (sub, i, arr) => {
    const connector = i === arr.length - 1 ? '└' : '├';
    const rich = renderRichSub(sub, isDark);
    if (rich) {
      return (
        <div key={i} className="flex gap-2">
          <span className="text-slate-600 font-sans text-xs shrink-0 pt-0.5">{connector}</span>
          <div className="flex-1 min-w-0">{rich}</div>
        </div>
      );
    }
    const matchColor = sub.badge ? (MATCH_TYPE_COLORS[sub.badge] || MATCH_TYPE_COLORS.semantic) : null;
    return (
      <div key={i} className="flex items-start gap-2">
        <span className="text-slate-600 font-sans text-xs shrink-0 pt-0.5">{connector}</span>
        <span className={`text-xs leading-snug break-words flex-1 min-w-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{sub.detail}</span>
        {sub.badge && <div className="shrink-0"><StageBadge text={sub.badge} colorClass={matchColor} /></div>}
      </div>
    );
  };

  // Stage-4 evidence questions: split the mixed list into the AI's case-specific
  // questions and the always-asked anchor checks, and show them as two labelled
  // groups (AI-generated first). Surrounding sub-steps (the "Searching…" header
  // and the final count line) keep their original positions.
  const hasEvidenceQueries = normal.some((s) => s.kind === 'evidence_query');
  let normalContent;
  if (hasEvidenceQueries) {
    const queries = normal.filter((s) => s.kind === 'evidence_query');
    const leading = normal.filter((s) => s.kind !== 'evidence_query' && s.kind !== 'evidence_summary');
    const trailing = normal.filter((s) => s.kind === 'evidence_summary');
    // Prefer the backend's structural `anchor` flag; fall back to text-matching
    // only for older events that predate the flag.
    const isAnchor = (s) => (typeof s.anchor === 'boolean' ? s.anchor : isAnchorQuery(s.detail));
    const aiQs = queries.filter((s) => !isAnchor(s));
    const anchorQs = queries.filter((s) => isAnchor(s));
    normalContent = (
      <>
        {leading.map((s, i) => renderSub(s, i, leading))}
        {aiQs.length > 0 && (
          <div className="space-y-1">
            {groupHeader(`AI-generated questions (${aiQs.length})`)}
            {aiQs.map((s, i) => renderSub(s, i, aiQs))}
          </div>
        )}
        {anchorQs.length > 0 && (
          <div className="space-y-1">
            {groupHeader(`Always-asked checks (${anchorQs.length})`)}
            {anchorQs.map((s, i) => renderSub(s, i, anchorQs))}
          </div>
        )}
        {trailing.map((s, i) => renderSub(s, i, trailing))}
      </>
    );
  } else {
    normalContent = normal.map((s, i) => renderSub(s, i, normal));
  }

  return (
    <div className="mt-1.5 space-y-1 pl-3 border-l border-slate-700/50">
      {normalContent}
      {advanced.length > 0 && (
        <div className="space-y-1">
          <button
            onClick={() => setAdvOpen((o) => !o)}
            className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-400 transition-colors"
          >
            {advOpen ? <ChevronUp className="w-3 h-3" strokeWidth={1.5} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.5} />}
            {advOpen ? 'Hide shortlist details' : `How the AI built its shortlist (${advanced.length})`}
          </button>
          {advOpen && advanced.map((s, i) => renderSub(s, i, advanced))}
        </div>
      )}
    </div>
  );
}

function StatusDot({ status, num }) {
  const base = 'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 shrink-0 transition-all duration-300';
  if (status === 'complete') return (
    <div className={`${base} bg-emerald-500/20 border-emerald-500 text-emerald-400`}>
      <CheckCircle className="w-4 h-4" strokeWidth={1.5} />
    </div>
  );
  if (status === 'error') return (
    <div className={`${base} bg-red-500/20 border-red-500 text-red-400`}>
      <AlertCircle className="w-4 h-4" strokeWidth={1.5} />
    </div>
  );
  if (status === 'running') return (
    <div className={`${base} bg-[var(--accent-primary)]/20 border-[var(--accent-primary)] text-[var(--accent-primary)] animate-pulse`}>
      <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
    </div>
  );
  return (
    <div className={`${base} bg-slate-800/50 border-slate-600 text-slate-500`}>
      {num}
    </div>
  );
}

function StageBadge({ text, colorClass }) {
  if (!text) return null;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${colorClass || 'bg-slate-700/50 text-slate-400 border-slate-600/50'}`}>
      {text}
    </span>
  );
}

function ThinkingDropdown({ text, isStreaming }) {
  const scrollRef = useRef(null);
  useEffect(() => {
    if (isStreaming && scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [text, isStreaming]);

  if (!text) return null;
  return (
    <div
      ref={scrollRef}
      className="mt-2 max-h-44 overflow-y-auto rounded-lg p-3 text-xs font-sans leading-relaxed
        bg-[var(--accent-primary)]/5 text-slate-300 border border-[var(--accent-primary)]/20"
    >
      {text}
      {isStreaming && (
        <span className="inline-block w-1.5 h-3 ml-0.5 bg-[var(--accent-primary)] animate-pulse align-middle" />
      )}
    </div>
  );
}

/**
 * Props:
 *   pipelineEvents:  ordered array of { eventType, stage, name?, status, detail, badge? }
 *   pipelineThinking: { [nodeName]: string }
 *   summary:          { elapsed_ms, ddxCount, cpgCount } | null
 *   isLive:           bool — true while analysis is running
 *   collapsed:        bool — when true, show only the summary header (DiagnosisSection)
 *   onToggle:         () => void — toggle collapsed state
 */
export function PipelineProgress({
  pipelineEvents = [],
  pipelineThinking = {},
  summary = null,
  isLive = false,
  collapsed = false,
  onToggle,
  resynthOverride = null,
}) {
  const { isDark } = useTheme();
  const [thinkingOpen, setThinkingOpen] = useState(false);

  const stageData = STAGE_DEFS.map((def) => {
    const stageEvents = pipelineEvents.filter((e) => e.stage === def.stage);
    const stageUpdate = [...stageEvents].reverse().find((e) => e.eventType === 'stage_update');
    const subSteps = stageEvents.filter((e) => e.eventType === 'sub_step');
    const status = stageUpdate?.status || 'pending';
    const detail = stageUpdate?.detail || '';
    const badge  = stageUpdate?.badge || null;
    const data   = stageUpdate?.data || null;   // DDx candidates (stage 2) etc.
    return { ...def, status, detail, badge, subSteps, data };
  });

  const thinkingText = pipelineThinking['DDx Re-rank'] || '';
  const isThinkingStreaming = isLive && stageData[0]?.status === 'running' && thinkingText.length > 0;

  const summaryText = summary
    ? `${(summary.elapsed_ms / 1000).toFixed(1)}s · ${summary.ddxCount} ICD codes · ${summary.cpgCount} CPGs`
    : isLive ? 'Analysing…' : '';

  return (
    <div className={`overflow-hidden rounded-xl border-2 ${isLive ? 'border-[var(--accent-primary)]' : isDark ? 'border-indigo-500/30 bg-slate-800/80' : 'border-indigo-200 bg-white'} transition-all duration-300`}>
      {/* Header */}
      <div
        className={`flex items-center justify-between px-5 py-3 border-b ${isDark ? 'bg-indigo-900/20 border-indigo-500/20' : 'bg-indigo-50 border-indigo-100'} ${onToggle ? 'cursor-pointer select-none' : ''}`}
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {isLive ? (
              <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent-primary)] animate-pulse" />
            ) : (
              <BrainCircuit className={`w-4 h-4 ${isDark ? 'text-indigo-400' : 'text-indigo-600'}`} strokeWidth={1.5} />
            )}
            <span className={`text-base font-semibold ${isDark ? 'text-indigo-300' : 'text-indigo-700'}`}>
              AI Reasoning Trace
            </span>
          </div>
          {summaryText && (
            <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              {summaryText}
            </span>
          )}
        </div>
        {onToggle && (
          collapsed
            ? <ChevronDown className="w-4 h-4 text-slate-500" strokeWidth={1.5} />
            : <ChevronUp   className="w-4 h-4 text-slate-500" strokeWidth={1.5} />
        )}
      </div>

      {/* Timeline body */}
      {!collapsed && (
        <div className="px-5 pb-5">
          <div className="space-y-0">
            {stageData.map((stage, stageIdx) => {
              const isLast = stageIdx === stageData.length - 1;
              const isActive = stage.status === 'running';

              return (
                <React.Fragment key={stage.stage}>
                {/* Clinician override marker — inserted between Stage 2 and Stage 3 */}
                {stage.stage === 3 && resynthOverride && (
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="w-8 h-8 flex items-center justify-center rounded-full
                        bg-amber-500/20 border-2 border-amber-500/50 text-amber-400 text-xs">
                        ✎
                      </div>
                      <div className="w-0.5 flex-1 my-1 min-h-4 bg-amber-500/30" />
                    </div>
                    <div className="flex-1 pb-4 pt-1">
                      <p className={`text-xs font-medium ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
                        Clinician override
                      </p>
                      <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {resynthOverride.codes.join(' · ')}
                      </p>
                    </div>
                  </div>
                )}
                <div className="flex gap-4">
                  {/* Left: dot + vertical line */}
                  <div className="flex flex-col items-center">
                    <StatusDot status={stage.status} num={stage.num} />
                    {!isLast && (
                      <div className={`w-0.5 flex-1 my-1 min-h-4 transition-colors duration-500
                        ${stage.status === 'complete' ? 'bg-emerald-500/40' : 'bg-slate-700/50'}`}
                      />
                    )}
                  </div>

                  {/* Right: content */}
                  <div className="flex-1 pb-4 min-w-0">
                    {/* Stage header row */}
                    <div className="flex items-center justify-between pt-1 mb-1">
                      <span className={`text-sm font-semibold ${
                        isActive                    ? (isDark ? 'text-white'       : 'text-slate-800') :
                        stage.status === 'complete' ? (isDark ? 'text-slate-200'  : 'text-slate-700') :
                        stage.status === 'error'    ? 'text-red-400' :
                        (isDark ? 'text-slate-500' : 'text-slate-400')
                      }`}>
                        {stage.label}
                      </span>
                      <div className="flex items-center gap-2 ml-3 shrink-0">
                        {stage.badge && (
                          <StageBadge text={stage.badge}
                            colorClass="bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                          />
                        )}
                        {stage.status === 'complete' && !stage.badge && stage.detail && (
                          <span className="text-xs text-slate-500">{stage.detail.split('·').pop()?.trim()}</span>
                        )}
                      </div>
                    </div>

                    {/* Detail text or Error card */}
                    {stage.status === 'error' ? (
                      <div className="mt-1 mb-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                        <p className={`text-xs font-semibold flex items-center gap-1.5 ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                          <AlertCircle className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
                          {stage.label} failed
                        </p>
                        <p className={`text-xs mt-1 ${isDark ? 'text-red-300/80' : 'text-red-700/80'}`}>
                          {getFriendlyError(stage.detail)}
                        </p>
                        <button className={`mt-2 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-red-300' : 'text-red-700'} hover:underline`}>
                          <RefreshCw className="w-3 h-3" strokeWidth={1.5} /> Retry Stage
                        </button>
                      </div>
                    ) : stage.detail && stage.status !== 'pending' ? (
                      <p className={`text-xs mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {stage.detail}
                      </p>
                    ) : stage.status === 'pending' && stage.pendingDescription ? (
                      <p className={`text-xs mb-1 italic ${isDark ? 'text-slate-500' : 'text-slate-400'} opacity-75`}>
                        {stage.pendingDescription}
                      </p>
                    ) : null}

                    {/* Sub-steps — normal inline; deep internals under "Advanced details" */}
                    <SubSteps subs={stage.subSteps} isDark={isDark} />

                    {/* DDx candidates: before/after re-rank + score breakdown (stage 2) */}
                    {stage.stage === 2 && Array.isArray(stage.data) && stage.data.length > 0 && (
                      <DDxCandidateTable candidates={stage.data} isDark={isDark} />
                    )}

                    {/* Thinking dropdown — DDx stage only */}
                    {stage.hasThinking && thinkingText && (
                      <div className="mt-2">
                        <button
                          onClick={() => setThinkingOpen((o) => !o)}
                          className="flex items-center gap-1.5 text-xs text-[var(--accent-primary)] hover:opacity-80 transition-opacity"
                        >
                          <BrainCircuit className="w-3.5 h-3.5" strokeWidth={1.5} />
                          {thinkingOpen ? 'Hide reasoning' : 'View reasoning'}
                          {thinkingOpen ? <ChevronUp className="w-3 h-3" strokeWidth={1.5} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.5} />}
                        </button>
                        {thinkingOpen && (
                          <ThinkingDropdown text={thinkingText} isStreaming={isThinkingStreaming} />
                        )}
                      </div>
                    )}
                  </div>
                </div>
                </React.Fragment>
              );
            })}
          </div>

          {/* Footer */}
          <div className={`mt-2 pt-3 border-t text-xs ${isDark ? 'border-slate-700/50 text-slate-600' : 'border-slate-200 text-slate-400'}`}>
            Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs
          </div>
        </div>
      )}
    </div>
  );
}
