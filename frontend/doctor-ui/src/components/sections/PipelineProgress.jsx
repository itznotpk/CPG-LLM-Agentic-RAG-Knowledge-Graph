import React, { useRef, useEffect, useState } from 'react';
import {
  Check, AlertCircle, Loader2, BrainCircuit, ChevronDown, ChevronUp,
  RefreshCw, Search, Sparkles, BookOpen, Pencil, AlertTriangle, X, FileText,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

// Display titles for the trace timeline (clinician-facing, per redesign spec).
const STAGE_DEFS = [
  { stage: 2, num: '01', label: 'Diagnosis Ranking',  hasThinking: true,  pendingDescription: 'Parses clinical notes to extract symptoms and rank candidate diagnoses.' },
  { stage: 3, num: '02', label: 'Guideline Matching', hasThinking: false, pendingDescription: 'Routes confirmed diagnoses to matching clinical practice guidelines (runs on Confirm).' },
  { stage: 4, num: '03', label: 'Evidence Retrieved', hasThinking: false, pendingDescription: 'Retrieves relevant clinical rules, recommendations, and evidence (runs on Confirm).' },
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

function fmtScore(n, sign = false) {
  if (n === null || n === undefined) return '—';
  const v = Number(n);
  const s = v.toFixed(2);
  return sign && v > 0 ? `+${s}` : s;
}

// ── Sub-step parsing prefixes (engine emits these as raw strings) ──────────
const SYMPTOM_QUERY_PREFIX = 'Extracted symptom query:';
const SYMPTOM_FALLBACK_PREFIX = '⚠ Symptom extraction fell back to raw notes:';
const HYPOTHESES_PREFIX = 'Condition hypotheses:';

function stripQuotes(s) {
  return s.trim().replace(/^["“]/, '').replace(/["”]$/, '').trim();
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

function isAdvancedSubStep(sub) {
  if (!sub) return false;
  if (sub.kind === 'regex_codes' || sub.kind === 'cc_priority') return true;
  const detail = sub.detail || '';
  return detail.startsWith('Regex-injected codes')
    || detail.startsWith('CC priority codes:')
    || detail.startsWith('Extra codes caught')
    || detail.startsWith('Diagnoses the AI pulled');
}

/* ════════════════════════════════════════════════════════════════════════
   Timeline primitives
   ════════════════════════════════════════════════════════════════════════ */

// Left-rail dot. `kind === 'override'` renders the amber pencil node; otherwise
// the dot reflects live stage status (done / running / error / pending).
function TimelineDot({ status, num, kind, isDark }) {
  const base = 'w-6 h-6 rounded-full flex items-center justify-center shrink-0 border-[1.5px] relative z-10 transition-colors duration-300';

  if (kind === 'override') {
    return (
      <div className={`${base} ${isDark
        ? 'bg-[rgba(217,119,6,0.15)] border-[rgba(217,119,6,0.3)] text-[#fcd34d]'
        : 'bg-amber-100 border-amber-200 text-amber-600'}`}>
        <Pencil className="w-3 h-3" strokeWidth={1.6} />
      </div>
    );
  }
  if (status === 'complete') {
    return (
      <div className={`${base} ${isDark
        ? 'bg-[rgba(22,163,74,0.15)] border-[rgba(22,163,74,0.3)] text-[#86efac]'
        : 'bg-green-100 border-green-200 text-green-600'}`}>
        <Check className="w-3 h-3" strokeWidth={2.4} />
      </div>
    );
  }
  if (status === 'running') {
    return (
      <div className={`${base} bg-[var(--accent-primary)]/15 border-[var(--accent-primary)]/40 text-[var(--accent-primary)]`}>
        <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div className={`${base} ${isDark
        ? 'bg-[rgba(220,38,38,0.15)] border-[rgba(220,38,38,0.3)] text-[#fca5a5]'
        : 'bg-red-100 border-red-200 text-red-600'}`}>
        <AlertCircle className="w-3.5 h-3.5" strokeWidth={1.8} />
      </div>
    );
  }
  return (
    <div className={`${base} font-sans text-[11px] font-bold ${isDark
      ? 'bg-[rgba(255,255,255,0.06)] border-[rgba(255,255,255,0.1)] text-slate-500'
      : 'bg-slate-100 border-slate-200 text-slate-400'}`}>
      {num}
    </div>
  );
}

// One timeline row: left rail (dot + connecting line) + right content column.
function TimelineItem({ dot, line, isLast, children }) {
  return (
    <div className="flex">
      <div className="flex flex-col items-center w-[46px] shrink-0 pt-4">
        {dot}
        {!isLast && <div className={`w-[2px] flex-1 min-h-[16px] mt-1 rounded-[1px] ${line}`} />}
      </div>
      <div className="flex-1 min-w-0 pr-[18px]">{children}</div>
    </div>
  );
}

// Clickable stage header inside the right column (dot lives in the rail).
function StageHeader({ title, meta, open, onToggle, isActive, status, isDark }) {
  const titleColor =
    isActive                    ? (isDark ? 'text-white'      : 'text-slate-800') :
    status === 'error'          ? (isDark ? 'text-red-400'    : 'text-red-600') :
    status === 'pending'        ? (isDark ? 'text-slate-500'  : 'text-slate-400') :
                                  (isDark ? 'text-slate-200'  : 'text-slate-800');
  return (
    <div className="flex items-center gap-2.5 py-[14px] cursor-pointer select-none" onClick={onToggle}>
      <span className={`flex-1 text-sm font-semibold ${titleColor}`}>{title}</span>
      {meta && <span className="text-xs text-slate-400 whitespace-nowrap">{meta}</span>}
      <span className="text-slate-400">
        {open ? <ChevronUp className="w-[13px] h-[13px]" strokeWidth={1.7} /> : <ChevronDown className="w-[13px] h-[13px]" strokeWidth={1.7} />}
      </span>
    </div>
  );
}

const Eyebrow = ({ tone, isDark, children, className = '' }) => {
  const tones = {
    blue:   isDark ? 'text-[#93c5fd]' : 'text-blue-600',
    indigo: isDark ? 'text-[#a5b4fc]' : 'text-indigo-600',
    amber:  isDark ? 'text-[#fcd34d]' : 'text-amber-600',
    green:  isDark ? 'text-[#86efac]' : 'text-green-600',
    slate:  isDark ? 'text-slate-400' : 'text-slate-500',
  };
  return (
    <div className={`text-[10px] font-semibold uppercase tracking-[0.06em] flex items-center gap-1.5 ${tones[tone] || tones.slate} ${className}`}>
      {children}
    </div>
  );
};

/* ════════════════════════════════════════════════════════════════════════
   DDx stage — search callout, condition chips, candidate cards
   ════════════════════════════════════════════════════════════════════════ */

function SearchCallout({ query, fellBack, isDark }) {
  return (
    <div className={`rounded-xl px-3 py-2.5 mb-3 border ${
      fellBack
        ? (isDark ? 'bg-[rgba(217,119,6,0.08)] border-[rgba(217,119,6,0.2)]' : 'bg-amber-50 border-amber-200')
        : (isDark ? 'bg-[rgba(59,130,246,0.08)] border-[rgba(59,130,246,0.2)]' : 'bg-blue-50 border-blue-100')
    }`}>
      <Eyebrow tone={fellBack ? 'amber' : 'blue'} isDark={isDark} className="mb-1">
        <Search className="w-[11px] h-[11px]" strokeWidth={1.6} />
        {fellBack ? 'Searched your notes directly' : 'AI searched for'}
      </Eyebrow>
      <p className={`text-[13px] leading-[1.5] ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>“{query}”</p>
    </div>
  );
}

function ConditionChips({ conditions, isDark }) {
  if (!conditions?.length) return null;
  return (
    <>
      <Eyebrow tone="indigo" isDark={isDark} className="mb-1.5">Conditions considered</Eyebrow>
      <div className="flex flex-wrap gap-1.5 mb-3.5">
        {conditions.map((c, i) => (
          <span key={i} className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
            isDark ? 'bg-[rgba(59,130,246,0.1)] border-[rgba(59,130,246,0.2)] text-[#93c5fd]'
                   : 'bg-blue-50 border-blue-200 text-blue-700'}`}>
            {c}
          </span>
        ))}
      </div>
    </>
  );
}

function CandidateCard({ c, i, isDark }) {
  const [scoreOpen, setScoreOpen] = useState(false);
  const sb = c.score_breakdown || {};
  const mathRank = c.math_rank;
  const aiRank = c.llm_rank ?? i + 1;
  const delta = c.rank_delta;
  const moved = typeof delta === 'number' && delta !== 0;
  const moveLabel = !moved ? '=' : delta > 0 ? `↑${delta}` : `↓${Math.abs(delta)}`;

  const circle =
    aiRank === 1
      ? (isDark ? 'bg-[rgba(20,184,166,0.15)] border-[rgba(20,184,166,0.3)] text-[#5eead4]' : 'bg-teal-50 border-teal-200 text-teal-700')
      : aiRank <= 3
        ? (isDark ? 'bg-[rgba(255,255,255,0.06)] border-[rgba(255,255,255,0.1)] text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-600')
        : (isDark ? 'bg-[rgba(255,255,255,0.03)] border-[rgba(255,255,255,0.08)] text-slate-600' : 'bg-slate-50 border-slate-200 text-slate-400');

  const move =
    !moved ? (isDark ? 'bg-[rgba(255,255,255,0.06)] text-slate-500' : 'bg-slate-100 text-slate-500')
    : delta > 0 ? (isDark ? 'bg-[rgba(22,163,74,0.2)] text-[#86efac]' : 'bg-green-100 text-green-700')
                : (isDark ? 'bg-[rgba(220,38,38,0.2)] text-[#fca5a5]' : 'bg-red-100 text-red-700');

  const incl = Number(sb.inclusion_match || 0);
  const excl = Number(sb.exclusion_penalty || 0);

  return (
    <div className={`rounded-xl overflow-hidden border transition-shadow hover:shadow-md ${
      isDark ? 'bg-[rgba(255,255,255,0.03)] border-[rgba(255,255,255,0.08)]' : 'bg-white border-slate-200'}`}>
      <div className="flex items-start gap-2.5 px-3 py-[11px]">
        <div className={`w-[30px] h-[30px] rounded-full shrink-0 flex items-center justify-center text-xs font-bold border-[1.5px] mt-px ${circle}`}>
          {aiRank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2 justify-between">
            <div className="min-w-0">
              <div className={`font-sans text-[13px] font-semibold tracking-[0.02em] ${isDark ? 'text-[#2dd4bf]' : 'text-teal-600'}`}>{c.code}</div>
              <div className={`text-[13px] leading-[1.4] mt-0.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{c.title}</div>
              {mathRank != null && (
                <div className={`text-[11px] mt-1 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>Evidence rank #{mathRank} → AI rank #{aiRank}</div>
              )}
            </div>
            <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-full shrink-0 mt-px ${move}`}>{moveLabel}</span>
          </div>
        </div>
      </div>

      {c.override_reason && (
        <div className={`flex items-start gap-[7px] px-3 py-2 border-t border-l-[3px] ${
          isDark ? 'bg-[rgba(217,119,6,0.08)] border-t-[rgba(217,119,6,0.2)] border-l-[#fbbf24]'
                 : 'bg-amber-50 border-t-amber-100 border-l-amber-600'}`}>
          <span className={`text-[11px] font-semibold shrink-0 whitespace-nowrap ${isDark ? 'text-[#fcd34d]' : 'text-amber-600'}`}>Re-ranked:</span>
          <span className={`text-xs leading-[1.5] ${isDark ? 'text-[#fde68a]' : 'text-amber-700'}`}>{formatOverrideReason(c.override_reason)}</span>
        </div>
      )}

      <button
        onClick={() => setScoreOpen(o => !o)}
        className={`w-full flex items-center gap-1 px-3 py-[5px] text-left text-[11px] border-t transition-colors ${
          isDark ? 'border-[rgba(255,255,255,0.06)] text-slate-600 hover:text-slate-400'
                 : 'border-slate-100 text-slate-400 hover:text-slate-600'}`}
      >
        {scoreOpen ? <ChevronUp className="w-3 h-3" strokeWidth={1.6} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.6} />}
        {scoreOpen ? 'Hide score breakdown' : 'Score breakdown'}
      </button>
      {scoreOpen && (
        <div className={`px-3 py-2 flex flex-wrap gap-x-2.5 gap-y-1 text-[11px] border-t leading-[1.6] ${
          isDark ? 'bg-[rgba(255,255,255,0.03)] border-[rgba(255,255,255,0.06)] text-slate-400' : 'bg-slate-50 border-slate-100 text-slate-500'}`}>
          <span title="base vector similarity">Base <span className="font-sans font-semibold">{fmtScore(sb.base_similarity)}</span></span>
          <span className={incl > 0 ? (isDark ? 'text-[#86efac]' : 'text-green-600') : 'opacity-40'} title={sb.inclusion_phrase || 'inclusion-term match'}>
            Inclusion <span className="font-sans font-semibold">{fmtScore(incl, true)}</span>
          </span>
          <span className={excl > 0 ? (isDark ? 'text-[#fca5a5]' : 'text-red-600') : 'opacity-40'} title={sb.exclusion_phrase || 'exclusion-term penalty'}>
            Exclusion <span className="font-sans font-semibold">{fmtScore(excl)}</span>
          </span>
          <span title="Evidence (math) score — base + inclusion − exclusion. List order is the AI clinical rank, which can differ.">
            = Evidence <span className={`font-sans font-bold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{fmtScore(sb.final_score)}</span>
          </span>
        </div>
      )}
    </div>
  );
}

function DDxBody({ derived, thinking, isThinkingStreaming, isDark }) {
  const [showAll, setShowAll] = useState(false);
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const { searchQuery, fellBack, conditions, candidates } = derived;
  const shown = showAll ? candidates : candidates.slice(0, 3);
  const restCount = Math.max(0, candidates.length - 3);

  return (
    <div className="pb-[18px]">
      {searchQuery && <SearchCallout query={searchQuery} fellBack={fellBack} isDark={isDark} />}
      <ConditionChips conditions={conditions} isDark={isDark} />

      {candidates.length > 0 && (
        <>
          <div className={`text-[10px] leading-snug mb-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Ordered by AI clinical rank. The <span className="font-semibold">evidence</span> score is the raw retrieval signal —
            the AI may rank against it using patient context.
          </div>
          <div className="flex flex-col gap-[7px]">
            {shown.map((c, i) => <CandidateCard key={c.code || i} c={c} i={candidates.indexOf(c)} isDark={isDark} />)}
          </div>
          {restCount > 0 && (
            <button
              onClick={() => setShowAll(o => !o)}
              className={`flex items-center gap-1.5 mt-1 py-[5px] text-xs transition-colors ${isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-500 hover:text-slate-700'}`}
            >
              {showAll ? <ChevronUp className="w-3 h-3" strokeWidth={1.6} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.6} />}
              {showAll ? `Hide ${restCount} lower-ranked candidates` : `Show ${restCount} more candidates`}
            </button>
          )}
        </>
      )}

      <AdvancedSubSteps advanced={derived.advanced} isDark={isDark} />

      {thinking && (
        <div className="mt-2">
          <button
            onClick={() => setThinkingOpen(o => !o)}
            className="flex items-center gap-1.5 text-xs text-[var(--accent-primary)] hover:opacity-80 transition-opacity"
          >
            <BrainCircuit className="w-3.5 h-3.5" strokeWidth={1.5} />
            {thinkingOpen ? 'Hide reasoning' : 'View reasoning'}
            {thinkingOpen ? <ChevronUp className="w-3 h-3" strokeWidth={1.5} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.5} />}
          </button>
          {thinkingOpen && <ThinkingDropdown text={thinking} isStreaming={isThinkingStreaming} />}
        </div>
      )}
    </div>
  );
}

// Deep engine internals (regex-injected codes, CC-priority codes) — collapsed.
function AdvancedSubSteps({ advanced, isDark }) {
  const [open, setOpen] = useState(false);
  if (!advanced?.length) return null;
  return (
    <div className="mt-2.5">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-1 text-[11px] transition-colors ${isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-600'}`}
      >
        {open ? <ChevronUp className="w-3 h-3" strokeWidth={1.5} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.5} />}
        {open ? 'Hide shortlist details' : `How the AI built its shortlist (${advanced.length})`}
      </button>
      {open && (
        <div className="mt-1.5 flex flex-col gap-2">
          {advanced.map((s, i) => {
            if (s.kind === 'cc_priority') return <ChipList key={i} title="Diagnoses from the chief complaint" tone="amber" items={(s.data || []).map(it => it.name || it.code)} isDark={isDark} />;
            if (s.kind === 'regex_codes') return <ChipList key={i} title="Extra codes found in your notes" tone="amber" items={(s.data || []).map(it => it.name ? `${it.name} (${it.code})` : it.code)} isDark={isDark} />;
            return <p key={i} className={`text-[11px] leading-snug ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>{s.detail}</p>;
          })}
        </div>
      )}
    </div>
  );
}

function ChipList({ title, items, tone, isDark }) {
  if (!items?.length) return null;
  return (
    <div>
      <Eyebrow tone={tone} isDark={isDark} className="mb-1">{title}</Eyebrow>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span key={i} className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
            isDark ? 'bg-[rgba(217,119,6,0.1)] border-[rgba(217,119,6,0.25)] text-[#fcd34d]' : 'bg-amber-50 border-amber-200 text-amber-700'}`}>
            {it}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   Clinician override — timeline node
   ════════════════════════════════════════════════════════════════════════ */

function OverrideBanner({ codes, isDark }) {
  return (
    <div className="py-[13px]">
      <div className={`flex items-start gap-2.5 px-3 py-2.5 rounded-xl border border-l-[3px] ${
        isDark ? 'bg-[rgba(217,119,6,0.08)] border-[rgba(217,119,6,0.2)] border-l-[#f59e0b]'
               : 'bg-amber-50 border-amber-200 border-l-amber-600'}`}>
        <span className={`mt-px ${isDark ? 'text-[#fcd34d]' : 'text-amber-600'}`}><Pencil className="w-3.5 h-3.5" strokeWidth={1.5} /></span>
        <div className="flex-1 min-w-0">
          <div className={`text-[11px] font-semibold mb-1.5 ${isDark ? 'text-[#fcd34d]' : 'text-amber-700'}`}>Clinician confirmed diagnoses</div>
          <div className="flex flex-wrap gap-1.5">
            {codes.map((raw, i) => {
              const m = String(raw).match(/^([A-Z0-9][A-Z0-9.]*)\s+(.*)$/);
              const code = m ? m[1] : null;
              const name = m ? m[2] : String(raw);
              return (
                <div key={i} className={`flex items-center gap-1.5 px-2.5 py-[3px] rounded-full border ${
                  isDark ? 'bg-[rgba(255,255,255,0.04)] border-[rgba(217,119,6,0.25)]' : 'bg-white border-amber-200'}`}>
                  {code && <span className={`font-sans text-[11px] font-semibold ${isDark ? 'text-[#2dd4bf]' : 'text-teal-600'}`}>{code}</span>}
                  <span className={`text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{name}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   CPG stage — applied rows + excluded toggle
   ════════════════════════════════════════════════════════════════════════ */

function CPGBody({ derived, isDark }) {
  const [exclOpen, setExclOpen] = useState(false);
  const { applied, excluded, plain } = derived;

  return (
    <div className="pb-[18px]">
      {applied.length > 0 && (
        <>
          <Eyebrow tone="green" isDark={isDark} className="mb-1.5">Applied guidelines</Eyebrow>
          <div className="flex flex-col gap-1.5 mb-2.5">
            {applied.map((s, i) => (
              <div key={i} className={`flex items-center gap-2 px-[11px] py-[9px] rounded-lg border ${
                isDark ? 'bg-[rgba(22,163,74,0.07)] border-[rgba(22,163,74,0.2)]' : 'bg-green-50 border-green-100'}`}>
                <span className={`shrink-0 ${isDark ? 'text-[#86efac]' : 'text-green-600'}`}><Check className="w-[13px] h-[13px]" strokeWidth={2.2} /></span>
                <span className={`flex-1 text-[13px] ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{s.detail}</span>
                {s.badge && (
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border shrink-0 ${
                    isDark ? 'bg-[rgba(22,163,74,0.15)] border-[rgba(22,163,74,0.3)] text-[#86efac]' : 'bg-green-100 border-green-200 text-green-700'}`}>
                    {s.badge}
                  </span>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {plain.map((s, i) => (
        <p key={i} className={`text-xs leading-snug mb-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{s.detail}</p>
      ))}

      {excluded.length > 0 && (
        <>
          <button
            onClick={() => setExclOpen(o => !o)}
            className={`w-full flex items-center justify-between px-[11px] py-[9px] rounded-lg border text-xs transition-colors ${
              isDark ? 'bg-[rgba(255,255,255,0.03)] border-[rgba(255,255,255,0.08)] text-slate-500 hover:bg-[rgba(255,255,255,0.06)]'
                     : 'bg-slate-50 border-slate-200 text-slate-500 hover:bg-slate-100'}`}
          >
            <span className="flex items-center gap-1.5">
              <span className={isDark ? 'text-[#fca5a5]' : 'text-red-600'}><X className="w-[11px] h-[11px]" strokeWidth={2} /></span>
              {excluded.length} guideline{excluded.length === 1 ? '' : 's'} excluded — click to see why
            </span>
            {exclOpen ? <ChevronUp className="w-3 h-3" strokeWidth={1.6} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.6} />}
          </button>
          {exclOpen && (
            <div className="flex flex-col gap-1.5 mt-1.5">
              {excluded.map((s, i) => {
                const text = s.detail || '';
                const dash = text.indexOf(' — ');
                const name = dash !== -1 ? text.slice(0, dash) : text;
                const reason = dash !== -1 ? text.slice(dash + 3) : '';
                return (
                  <div key={i} className={`flex items-start gap-2 px-[11px] py-2 rounded-lg border ${
                    isDark ? 'bg-[rgba(220,38,38,0.06)] border-[rgba(220,38,38,0.15)]' : 'bg-red-50 border-red-100'}`}>
                    <span className={`mt-0.5 shrink-0 ${isDark ? 'text-[#fca5a5]' : 'text-red-600'}`}><X className="w-[11px] h-[11px]" strokeWidth={2} /></span>
                    <div className="flex-1 min-w-0">
                      <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{name}</div>
                      {reason && <div className={`text-[11px] mt-0.5 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>{reason}</div>}
                    </div>
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border shrink-0 ${
                      isDark ? 'bg-[rgba(220,38,38,0.15)] border-[rgba(220,38,38,0.3)] text-[#fca5a5]' : 'bg-red-100 border-red-300 text-red-700'}`}>
                      excluded
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   Evidence stage — two labelled groups, accordion rows
   ════════════════════════════════════════════════════════════════════════ */

function ChunkCard({ c, isDark }) {
  return (
    <div className={`rounded-lg px-2.5 py-1.5 border text-[11px] ${isDark ? 'bg-[rgba(255,255,255,0.03)] border-[rgba(255,255,255,0.06)]' : 'bg-white border-slate-200'}`}>
      <div className="flex items-center gap-1.5 min-w-0">
        <FileText className="w-3 h-3 shrink-0 text-[var(--accent-primary)]" strokeWidth={1.5} />
        <span className={`font-medium truncate ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{c.cpg}</span>
        {c.section && <span className="text-slate-500 truncate">› {c.section}</span>}
      </div>
      {c.snippet && <p className={`mt-0.5 text-[11px] leading-snug ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{c.snippet}</p>}
    </div>
  );
}

function EvidenceRow({ sub, isDark }) {
  const [open, setOpen] = useState(false);
  const chunks = sub.data?.chunks || [];
  const n = sub.data?.new ?? chunks.length;
  const hasChunks = chunks.length > 0;
  return (
    <div className={`rounded-lg border overflow-hidden transition-colors ${
      isDark ? 'bg-[rgba(255,255,255,0.02)] border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.12)]' : 'bg-white border-slate-100 hover:border-slate-200'}`}>
      <div className={`flex items-start gap-2 px-2.5 py-[9px] ${hasChunks ? 'cursor-pointer' : ''}`} onClick={() => hasChunks && setOpen(o => !o)}>
        <span className="text-slate-400 mt-0.5 shrink-0">
          {hasChunks && (open ? <ChevronUp className="w-3 h-3" strokeWidth={1.6} /> : <ChevronDown className="w-3 h-3" strokeWidth={1.6} />)}
        </span>
        <span className={`flex-1 text-xs leading-[1.55] ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{sub.detail}</span>
        <span className={`text-[11px] font-semibold px-[7px] py-0.5 rounded-full border shrink-0 mt-px ${
          n > 0
            ? (isDark ? 'bg-[rgba(20,184,166,0.1)] border-[rgba(20,184,166,0.2)] text-[#5eead4]' : 'bg-teal-50 border-teal-100 text-teal-700')
            : (isDark ? 'bg-[rgba(255,255,255,0.04)] border-[rgba(255,255,255,0.08)] text-slate-500' : 'bg-slate-100 border-slate-200 text-slate-500')
        }`}>
          {n > 0 ? `+${n}` : '0'}
        </span>
      </div>
      {open && hasChunks && (
        <div className={`px-2.5 pt-2 pb-2.5 border-t flex flex-col gap-1.5 ${isDark ? 'border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]' : 'border-slate-100 bg-slate-50'}`}>
          {chunks.map((c, i) => <ChunkCard key={i} c={c} isDark={isDark} />)}
        </div>
      )}
    </div>
  );
}

function EvidenceBody({ derived, isDark }) {
  const { aiQs, anchorQs, summaryText, leading } = derived;
  const groupLabel = (icon, text, count) => (
    <div className={`text-[10px] font-semibold uppercase tracking-[0.06em] flex items-center gap-1.5 mt-3 mb-1.5 first:mt-0 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
      {icon}{text}
      <span className={`text-[10px] font-semibold px-1.5 rounded-full ${isDark ? 'bg-[rgba(255,255,255,0.06)] text-slate-500' : 'bg-slate-100 text-slate-500'}`}>{count}</span>
    </div>
  );
  return (
    <div className="pb-[18px]">
      {leading.map((s, i) => (
        <p key={i} className={`text-xs leading-snug mb-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{s.detail}</p>
      ))}

      {aiQs.length > 0 && (
        <>
          {groupLabel(<Sparkles className="w-[11px] h-[11px]" strokeWidth={1.6} />, 'AI-generated questions', aiQs.length)}
          <div className="flex flex-col gap-[3px]">
            {aiQs.map((s, i) => <EvidenceRow key={i} sub={s} isDark={isDark} />)}
          </div>
        </>
      )}

      {anchorQs.length > 0 && (
        <>
          {groupLabel(<BookOpen className="w-[11px] h-[11px]" strokeWidth={1.6} />, 'Standard checks always run', anchorQs.length)}
          <div className="flex flex-col gap-[3px]">
            {anchorQs.map((s, i) => <EvidenceRow key={i} sub={s} isDark={isDark} />)}
          </div>
        </>
      )}

      {summaryText && (
        <div className={`mt-2 px-[11px] py-[9px] rounded-lg border text-xs font-semibold text-center ${
          isDark ? 'bg-[rgba(255,255,255,0.03)] border-[rgba(255,255,255,0.06)] text-slate-400' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>
          {summaryText}
        </div>
      )}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   Generic / fallback stage body (Plan Synthesis + pending/running states)
   ════════════════════════════════════════════════════════════════════════ */

function GenericBody({ stage, isDark }) {
  const subs = stage.subSteps || [];
  return (
    <div className="pb-[18px]">
      {stage.status === 'error' ? (
        <div className={`p-3 rounded-lg border ${isDark ? 'bg-red-500/10 border-red-500/30' : 'bg-red-50 border-red-200'}`}>
          <p className={`text-xs font-semibold flex items-center gap-1.5 ${isDark ? 'text-red-400' : 'text-red-600'}`}>
            <AlertCircle className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
            {stage.label} failed
          </p>
          <p className={`text-xs mt-1 ${isDark ? 'text-red-300/80' : 'text-red-700/80'}`}>{getFriendlyError(stage.detail)}</p>
          <button className={`mt-2 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-red-300' : 'text-red-700'} hover:underline`}>
            <RefreshCw className="w-3 h-3" strokeWidth={1.5} /> Retry Stage
          </button>
        </div>
      ) : stage.status === 'pending' ? (
        <p className={`text-xs italic ${isDark ? 'text-slate-500' : 'text-slate-400'} opacity-75`}>{stage.pendingDescription}</p>
      ) : (
        <>
          {stage.detail && <p className={`text-xs mb-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{stage.detail}</p>}
          {subs.map((s, i) => (
            <p key={i} className={`text-xs leading-snug ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{s.detail}</p>
          ))}
        </>
      )}
    </div>
  );
}

function ThinkingDropdown({ text, isStreaming }) {
  const scrollRef = useRef(null);
  useEffect(() => {
    if (isStreaming && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [text, isStreaming]);
  if (!text) return null;
  return (
    <div
      ref={scrollRef}
      className="mt-2 max-h-44 overflow-y-auto rounded-lg p-3 text-xs font-sans leading-relaxed
        bg-[var(--accent-primary)]/5 text-slate-300 border border-[var(--accent-primary)]/20"
    >
      {text}
      {isStreaming && <span className="inline-block w-1.5 h-3 ml-0.5 bg-[var(--accent-primary)] animate-pulse align-middle" />}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   Per-stage data derivation (existing event shape → redesign view models)
   ════════════════════════════════════════════════════════════════════════ */

function deriveDDx(stage) {
  let searchQuery = null, fellBack = false, conditions = [];
  const advanced = [];
  for (const s of stage.subSteps || []) {
    const d = s.detail || '';
    if (isAdvancedSubStep(s)) { advanced.push(s); continue; }
    if (d.startsWith(SYMPTOM_QUERY_PREFIX)) { searchQuery = stripQuotes(d.slice(SYMPTOM_QUERY_PREFIX.length)); continue; }
    if (d.startsWith(SYMPTOM_FALLBACK_PREFIX)) { searchQuery = stripQuotes(d.slice(SYMPTOM_FALLBACK_PREFIX.length)); fellBack = true; continue; }
    if (d.startsWith(HYPOTHESES_PREFIX)) { conditions = d.slice(HYPOTHESES_PREFIX.length).split(',').map(x => x.trim()).filter(Boolean); continue; }
  }
  const candidates = Array.isArray(stage.data) ? stage.data : [];
  return { searchQuery, fellBack, conditions, advanced, candidates };
}

function deriveCPG(stage) {
  const applied = [], excluded = [], plain = [];
  for (const s of stage.subSteps || []) {
    if (s.badge === 'excluded' || s.badge === 'out_of_scope') excluded.push(s);
    else if (s.badge) applied.push(s);
    else plain.push(s);
  }
  return { applied, excluded, plain };
}

function deriveEvidence(stage) {
  const subs = stage.subSteps || [];
  const queries = subs.filter(s => s.kind === 'evidence_query');
  const summarySub = subs.find(s => s.kind === 'evidence_summary');
  const leading = subs.filter(s => s.kind !== 'evidence_query' && s.kind !== 'evidence_summary');
  const isAnchor = s => (typeof s.anchor === 'boolean' ? s.anchor : isAnchorQuery(s.detail));
  const aiQs = queries.filter(s => !isAnchor(s));
  const anchorQs = queries.filter(isAnchor);
  const totalNew = queries.reduce((a, s) => a + (s.data?.new ?? (s.data?.chunks?.length || 0)), 0);
  return { aiQs, anchorQs, leading, summaryText: summarySub?.detail || stage.detail, totalNew };
}

function stageMeta(stage, derived) {
  if (stage.status !== 'complete') return '';
  if (stage.stage === 2) return derived.candidates[0]?.code ? `top: ${derived.candidates[0].code}` : '';
  if (stage.stage === 3) return derived.applied.length ? `${derived.applied.length} applied` : '';
  if (stage.stage === 4) return derived.totalNew ? `${derived.totalNew} passages` : '';
  if (stage.badge) return stage.badge;
  return stage.detail ? stage.detail.split('·').pop()?.trim() : '';
}

/**
 * Props:
 *   pipelineEvents:  ordered array of { eventType, stage, name?, status, detail, badge? }
 *   pipelineThinking: { [nodeName]: string }
 *   summary:          { elapsed_ms, ddxCount, cpgCount } | null
 *   isLive:           bool — true while analysis is running
 *   collapsed:        bool — when true, show only the summary header (DiagnosisSection)
 *   onToggle:         () => void — toggle collapsed state
 *   resynthOverride:  { codes: string[] } | null — clinician override node
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
  const [openMap, setOpenMap] = useState({ 2: true, 3: true, 4: true, 5: true });
  const toggleStage = (s) => setOpenMap(m => ({ ...m, [s]: !m[s] }));

  const stageData = STAGE_DEFS.map((def) => {
    const stageEvents = pipelineEvents.filter((e) => e.stage === def.stage);
    const stageUpdate = [...stageEvents].reverse().find((e) => e.eventType === 'stage_update');
    const subSteps = stageEvents.filter((e) => e.eventType === 'sub_step');
    return {
      ...def,
      status: stageUpdate?.status || 'pending',
      detail: stageUpdate?.detail || '',
      badge: stageUpdate?.badge || null,
      subSteps,
      data: stageUpdate?.data || null,
    };
  });

  const thinkingText = pipelineThinking['DDx Re-rank'] || '';
  const isThinkingStreaming = isLive && stageData[0]?.status === 'running' && thinkingText.length > 0;

  const summaryText = summary
    ? `${(summary.elapsed_ms / 1000).toFixed(1)}s · ${summary.ddxCount} ICD codes · ${summary.cpgCount} CPGs`
    : isLive ? 'Analysing…' : '';

  // Build the ordered timeline rows (stages + the override node between 2 and 3).
  const rows = [];
  stageData.forEach((stage) => {
    if (stage.stage === 3 && resynthOverride) {
      rows.push({ type: 'override', codes: resynthOverride.codes || [] });
    }
    rows.push({ type: 'stage', stage });
  });

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
            <span className={`text-base font-semibold ${isDark ? 'text-indigo-300' : 'text-indigo-700'}`}>AI Reasoning Trace</span>
          </div>
          {summaryText && <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{summaryText}</span>}
        </div>
        {onToggle && (
          collapsed
            ? <ChevronDown className="w-4 h-4 text-slate-500" strokeWidth={1.5} />
            : <ChevronUp className="w-4 h-4 text-slate-500" strokeWidth={1.5} />
        )}
      </div>

      {/* Timeline body */}
      {!collapsed && (
        <>
          <div className="pt-1 pb-1">
            {rows.map((row, idx) => {
              const isLast = idx === rows.length - 1;

              if (row.type === 'override') {
                return (
                  <TimelineItem
                    key="override"
                    dot={<TimelineDot kind="override" isDark={isDark} />}
                    line={isDark ? 'bg-[rgba(217,119,6,0.22)]' : 'bg-amber-200'}
                    isLast={isLast}
                  >
                    <OverrideBanner codes={row.codes} isDark={isDark} />
                  </TimelineItem>
                );
              }

              const { stage } = row;
              const open = openMap[stage.stage];
              const isActive = stage.status === 'running';

              let derived = null, body = null;
              if (stage.stage === 2) { derived = deriveDDx(stage); body = <DDxBody derived={derived} thinking={stage.hasThinking ? thinkingText : ''} isThinkingStreaming={isThinkingStreaming} isDark={isDark} />; }
              else if (stage.stage === 3) { derived = deriveCPG(stage); body = <CPGBody derived={derived} isDark={isDark} />; }
              else if (stage.stage === 4) { derived = deriveEvidence(stage); body = <EvidenceBody derived={derived} isDark={isDark} />; }
              else { body = <GenericBody stage={stage} isDark={isDark} />; }

              // Stages 3 & 4 fall back to the generic body until they have data.
              if ((stage.stage === 3 || stage.stage === 4) && stage.status === 'pending') {
                body = <GenericBody stage={stage} isDark={isDark} />;
              }

              const lineColor = stage.status === 'complete'
                ? (isDark ? 'bg-[rgba(22,163,74,0.22)]' : 'bg-green-200')
                : (isDark ? 'bg-[rgba(255,255,255,0.08)]' : 'bg-slate-200');

              return (
                <TimelineItem
                  key={stage.stage}
                  dot={<TimelineDot status={stage.status} num={stage.num} isDark={isDark} />}
                  line={lineColor}
                  isLast={isLast}
                >
                  <StageHeader
                    title={stage.label}
                    meta={stageMeta(stage, derived || {})}
                    open={open}
                    onToggle={() => toggleStage(stage.stage)}
                    isActive={isActive}
                    status={stage.status}
                    isDark={isDark}
                  />
                  {open && body}
                </TimelineItem>
              );
            })}
          </div>

          {/* Footer */}
          <div className={`px-[18px] py-2.5 border-t text-[11px] ${isDark ? 'bg-[rgba(255,255,255,0.02)] border-[rgba(255,255,255,0.06)] text-slate-600' : 'bg-slate-50 border-slate-100 text-slate-400'}`}>
            Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs
          </div>
        </>
      )}
    </div>
  );
}
