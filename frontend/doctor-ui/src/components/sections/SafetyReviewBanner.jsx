import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, ShieldX, ChevronDown, ChevronUp, ChevronRight, AlertOctagon } from 'lucide-react';
import { Button, Badge } from '../shared';
import { useTheme } from '../../context/ThemeContext';

const SEVERITY_ORDER = { CRITICAL: 0, MAJOR: 1, MODERATE: 2 };

const KNOWN_DRUGS = [
  'enalapril', 'spironolactone', 'dapagliflozin', 'bisoprolol', 'furosemide',
  'warfarin', 'aspirin', 'clopidogrel', 'amiodarone', 'digoxin', 'ivabradine',
  'metformin', 'gliclazide', 'insulin', 'atorvastatin', 'simvastatin',
  'amlodipine', 'hydrochlorothiazide', 'losartan', 'valsartan', 'sacubitril',
  'ramipril', 'lisinopril', 'perindopril', 'carvedilol', 'metoprolol',
  'sildenafil', 'tadalafil', 'isosorbide mononitrate', 'nitroglycerin',
  // Pregnancy-related alternatives surfaced in safety advice
  'labetalol', 'methyldopa', 'nifedipine', 'hydralazine', 'atenolol',
];

const RISK_LABELS = [
  { re: /hyperkala?emia/i, label: 'hyperkalemia' },
  { re: /symptomatic hypotension|hypotension/i, label: 'hypotension' },
  { re: /acute kidney injury|AKI/i, label: 'acute kidney injury' },
  { re: /renal function|eGFR|creatinine/i, label: 'renal monitoring' },
  { re: /bleeding|haemorrhage|hemorrhage/i, label: 'bleeding' },
  { re: /QT|torsades/i, label: 'QT prolongation' },
  { re: /bradycardia/i, label: 'bradycardia' },
  { re: /bronchospasm/i, label: 'bronchospasm' },
  { re: /allerg|cross-react/i, label: 'allergy cross-reactivity' },
  { re: /dose|CrCl|renal/i, label: 'dose' },
];

function toDisplayDrug(text) {
  return text.trim().replace(/\s+/g, ' ').toLowerCase();
}

function titleCaseDrug(text) {
  return text.replace(/\b\w/g, (c) => c.toUpperCase());
}

function unique(items) {
  return [...new Set(items.filter(Boolean))];
}

function extractDrugNames(detail = '') {
  const fromParentheses = [...detail.matchAll(/\(([^)]+)\)/g)]
    .flatMap((m) => m[1].split(/,| and | & |\+/i))
    .map((s) => s.replace(/\b(and|or)\b/gi, '').trim())
    .filter((s) => /^[a-z][a-z0-9 -]{2,}$/i.test(s) && !/\d/.test(s))
    .map(toDisplayDrug);

  const lower = detail.toLowerCase();
  const fromKnownList = KNOWN_DRUGS.filter((drug) => lower.includes(drug));

  return unique([...fromParentheses, ...fromKnownList]).slice(0, 5);
}

// Pull candidate drug names out of the LLM's suggested_alternative prose.
// Returns an array like ["Labetalol", "Methyldopa"] — empty when the suggestion
// is generic ("switch to a pregnancy-safe antihypertensive") with no named drug.
function extractAlternatives(suggestion = '', primaryDrugs = []) {
  if (!suggestion) return [];
  const lower = suggestion.toLowerCase();
  const primarySet = new Set(primaryDrugs.map(toDisplayDrug));
  return KNOWN_DRUGS
    .filter((drug) => lower.includes(drug) && !primarySet.has(drug))
    .map(titleCaseDrug)
    .slice(0, 4);
}

function flagTypeLabel(flagType = '') {
  return flagType.replace(/_/g, ' ');
}

function riskLabel(detail = '', flagType = '') {
  const matched = RISK_LABELS.find(({ re }) => re.test(detail));
  return matched?.label || flagTypeLabel(flagType) || 'safety';
}

function safetyFlagTitle(flag) {
  if (flag.title) return flag.title;

  const drugs = extractDrugNames(flag.detail);
  const risk = riskLabel(flag.detail, flag.flag_type);
  const type = flagTypeLabel(flag.flag_type);

  if (flag.flag_type === 'drug_interaction' && drugs.length >= 2) {
    return `${drugs.join(' + ')} - ${risk} interaction caution`;
  }

  if (drugs.length >= 1) {
    return `${drugs.join(' + ')} - ${risk} ${type} caution`;
  }

  return `${risk} ${type} caution`;
}

function severityBg(severity, isDark) {
  if (severity === 'CRITICAL') return isDark ? 'bg-slate-900/50 border-slate-700 border-l-[4px] border-l-red-500' : 'bg-white border-slate-200 shadow-sm border-l-[4px] border-l-red-600';
  if (severity === 'MAJOR')    return isDark ? 'bg-slate-900/50 border-slate-700 border-l-[4px] border-l-amber-500' : 'bg-white border-slate-200 shadow-sm border-l-[4px] border-l-amber-500';
  return isDark ? 'bg-slate-900/50 border-slate-700 border-l-[4px] border-l-slate-400' : 'bg-white border-slate-200 shadow-sm border-l-[4px] border-l-slate-400';
}

const DECISION_LABELS = {
  replace: 'Replaced',
  keep: 'Kept (acknowledged)',
  remove: 'Removed',
};

/**
 * SafetyReviewBanner
 *
 * Props:
 *   report        : SafetyReport | null
 *   onAcknowledge : (decisions: { [flagKey]: { decision, alternative?, reason? } }) => void
 *                   Called once when all flags have a per-flag decision and the
 *                   clinician confirms. Decisions are also exposed for audit /
 *                   downstream care-plan mutation by the parent.
 *   acknowledged  : bool
 */
// Classify a flag against the current plan and the patient's existing meds.
// Returns { kind, matchedMed? } where:
//   `plan`           — drug appears in the active care plan → real decision required;
//                       matchedMed = { id, name, section } enables deep-linking
//   `current_only`   — drug is in the patient's current med list but NOT in the
//                       new plan → informational ("review existing prescription"),
//                       no plan mutation possible from the banner
//   `class_or_noise` — neither → collapsed informational pile so the clinician
//                       isn't asked to decide on something they aren't prescribing
//                       (e.g. class-level ARB warning duplicating a specific
//                       Losartan flag already shown above)
function classifyFlag(flag, plannedMeds, currentMeds) {
  const drugs = (flag.title || flag.detail || '').toLowerCase();

  const findMatch = (meds, nameKey = 'name') => {
    for (const med of meds) {
      const rawName = typeof med === 'string' ? med : med?.[nameKey] || med?.drug || '';
      if (!rawName) continue;
      const low = String(rawName).toLowerCase();
      if (low.length < 3) continue;
      const tokenHit = low.split(/[\s,()]+/).some((tok) => tok.length >= 4 && /^[a-z]/.test(tok) && drugs.includes(tok));
      if (drugs.includes(low) || tokenHit) return med;
    }
    return null;
  };

  const planned = findMatch(plannedMeds);
  if (planned) return { kind: 'plan', matchedMed: planned };
  const current = findMatch(currentMeds);
  if (current) return { kind: 'current_only', matchedMed: typeof current === 'string' ? { name: current } : current };
  return { kind: 'class_or_noise' };
}

export function SafetyReviewBanner({ report, onAcknowledge, acknowledged, plannedMeds = [], currentMeds = [], onJumpToMed }) {
  const { isDark } = useTheme();
  const [expandedSections, setExpandedSections] = useState({ CRITICAL: true, MAJOR: true, MODERATE: true });
  const [isMainExpanded, setIsMainExpanded] = useState(true);
  // decisions: { [flagKey]: { decision: 'replace'|'keep'|'remove', alternative?, reason? } }
  const [decisions, setDecisions] = useState({});
  const [criticalReasonModal, setCriticalReasonModal] = useState(null); // { flagKey } | null
  const [criticalReasonDraft, setCriticalReasonDraft] = useState('');

  if (report === undefined || report === null) return null;

  const dedupFlags = (rawFlags) => {
    const seen = new Map();
    for (const flag of rawFlags) {
      const drugs = extractDrugNames(flag.title || safetyFlagTitle(flag));
      const key = [...drugs].sort().join('|') + '::' + (flag.severity || '') + '::' + (flag.flag_type || '');
      if (seen.has(key)) {
        const existing = seen.get(key);
        if (flag.recommendation_index != null) {
          existing._recIndices = existing._recIndices || [existing.recommendation_index];
          if (!existing._recIndices.includes(flag.recommendation_index)) {
            existing._recIndices.push(flag.recommendation_index);
          }
        }
      } else {
        seen.set(key, { ...flag, _recIndices: flag.recommendation_index != null ? [flag.recommendation_index] : [] });
      }
    }
    return [...seen.values()];
  };

  const allFlags = dedupFlags(
    (report.flags || []).filter((f) => f.severity !== 'MODERATE' || f.source === 'graph')
  ).sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3));

  // Classify each flag against the actual plan; only flags whose drug is in the
  // plan get the per-flag decision UI. Current-meds-only and class/noise flags
  // are surfaced separately for audit but don't require a decision.
  const classified = allFlags.map((f) => {
    const c = classifyFlag(f, plannedMeds, currentMeds);
    return { flag: f, ...c };
  });
  // Each entry now carries `matchedMed` ({id, name, section}) when kind === 'plan'
  // so the per-flag card can deep-link to the matched row via onJumpToMed.
  const planClassified   = classified.filter((c) => c.kind === 'plan');
  const flags            = planClassified.map((c) => ({ ...c.flag, _matchedMed: c.matchedMed }));
  const currentOnlyFlags = classified.filter((c) => c.kind === 'current_only').map((c) => ({ ...c.flag, _matchedMed: c.matchedMed }));
  const noiseFlags       = classified.filter((c) => c.kind === 'class_or_noise').map((c) => c.flag);

  const hasBlockingFlag = !report.safe_to_proceed;
  const hasFlags = flags.length > 0 || currentOnlyFlags.length > 0 || noiseFlags.length > 0;

  if (!hasFlags) {
    return (
      <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border mb-4 ${
        isDark ? 'bg-green-900/20 border-green-700/40 text-green-300' : 'bg-green-50 border-green-300 text-green-800'
      }`}>
        <ShieldCheck className="w-4 h-4 shrink-0" strokeWidth={2} />
        <span className="text-sm font-medium">Safety review passed — no concerns flagged</span>
      </div>
    );
  }

  const flagKey = (flag, i) => `${flag.severity}::${flag.flag_type}::${i}`;
  const isRed = hasBlockingFlag;
  const allDecided = isRed ? flags.every((f, i) => !!decisions[flagKey(f, i)]) : true;

  const bannerBg = isRed
    ? (isDark ? 'bg-red-900/20 border-red-700/50' : 'bg-red-50 border-red-300')
    : (isDark ? 'bg-yellow-900/20 border-yellow-600/40' : 'bg-amber-50 border-amber-300');

  const iconColor = isRed
    ? (isDark ? 'text-red-400' : 'text-red-700')
    : (isDark ? 'text-yellow-400' : 'text-amber-700');

  const textColor = isRed
    ? (isDark ? 'text-red-300' : 'text-red-800')
    : (isDark ? 'text-yellow-300' : 'text-amber-800');

  const Icon = isRed ? ShieldX : ShieldAlert;

  const critCount  = flags.filter(f => f.severity === 'CRITICAL').length;
  const majorCount = flags.filter(f => f.severity === 'MAJOR').length;
  const modCount   = flags.filter(f => f.severity === 'MODERATE').length;
  const summary = [
    critCount  ? `${critCount} CRITICAL`  : null,
    majorCount ? `${majorCount} MAJOR`    : null,
    modCount   ? `${modCount} MODERATE`   : null,
  ].filter(Boolean).join(', ');

  const tightenedNote = flags.length === 0
    ? 'No flagged drugs are in the current plan — no plan changes required, but please review the informational notes below.'
    : `${flags.length} flag${flags.length === 1 ? '' : 's'} require${flags.length === 1 ? 's' : ''} a decision before continuing.${
        (currentOnlyFlags.length + noiseFlags.length) > 0
          ? ` ${currentOnlyFlags.length + noiseFlags.length} additional flag(s) are informational — see below.`
          : ''
      }`;

  const setDecision = (key, decision, extra = {}) => {
    setDecisions((prev) => ({ ...prev, [key]: { decision, ...extra } }));
  };

  const handleReplace = (key, drugs, alt) => setDecision(key, 'replace', { alternative: alt, drugs });
  const handleRemove  = (key, drugs)      => setDecision(key, 'remove',  { drugs });
  const handleKeep    = (key, flag) => {
    if (flag.severity === 'CRITICAL') {
      setCriticalReasonDraft('');
      setCriticalReasonModal({ key });
    } else {
      setDecision(key, 'keep');
    }
  };

  const confirmCriticalKeep = () => {
    if (!criticalReasonModal) return;
    const reason = criticalReasonDraft.trim();
    if (reason.length < 10) return; // require a substantive reason
    setDecision(criticalReasonModal.key, 'keep', { reason });
    setCriticalReasonModal(null);
    setCriticalReasonDraft('');
  };

  const totalFlags = flags.length;
  const decidedCount = flags.filter((f, i) => !!decisions[flagKey(f, i)]).length;
  const progressPercent = totalFlags > 0 ? (decidedCount / totalFlags) * 100 : 0;
  
  const toggleSection = (sev) => {
    setExpandedSections(prev => ({ ...prev, [sev]: !prev[sev] }));
  };

  const severityOrder = ['CRITICAL', 'MAJOR', 'MODERATE'];

  return (
    <div className={`rounded-xl border mb-4 overflow-hidden shadow-sm ${
      isRed ? (isDark ? 'bg-red-950/20 border-red-700/50' : 'bg-red-50/50 border-red-200') : (isDark ? 'bg-yellow-950/20 border-yellow-600/40' : 'bg-amber-50 border-amber-200')
    }`}>
      {/* Header */}
      <button 
        onClick={() => setIsMainExpanded(!isMainExpanded)}
        className={`w-full text-left px-4 py-4 border-b flex items-center justify-between gap-3 ${
        isRed ? (isDark ? 'border-red-900/50 hover:bg-red-900/20' : 'border-red-100 hover:bg-red-50/80') : (isDark ? 'border-yellow-900/50 hover:bg-yellow-900/20' : 'border-amber-100 hover:bg-amber-50/80')
      } transition-colors`}>
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-sm ${
            isRed ? 'bg-red-600' : 'bg-amber-500'
          }`}>
            <Icon className="w-5 h-5 text-white" strokeWidth={2} />
          </div>
          <div className="flex-1">
            <h3 className={`text-base font-bold ${
              isRed ? (isDark ? 'text-red-400' : 'text-red-900') : (isDark ? 'text-yellow-400' : 'text-amber-900')
            }`}>
              {isRed ? 'Safety concerns require acknowledgement' : 'Safety concerns detected'}
            </h3>
            <div className="flex items-center gap-2 mt-1.5">
              {critCount > 0 && (
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border ${
                  isDark ? 'bg-red-900/40 text-red-300 border-red-800' : 'bg-red-100 text-red-700 border-red-200'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${isDark ? 'bg-red-400' : 'bg-red-600'}`} />
                  {critCount} Critical
                </span>
              )}
              {majorCount > 0 && (
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border ${
                  isDark ? 'bg-amber-900/40 text-amber-300 border-amber-800' : 'bg-amber-100 text-amber-700 border-amber-200'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${isDark ? 'bg-amber-400' : 'bg-amber-500'}`} />
                  {majorCount} Major
                </span>
              )}
              {modCount > 0 && (
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border ${
                  isDark ? 'bg-blue-900/40 text-blue-300 border-blue-800' : 'bg-blue-100 text-blue-700 border-blue-200'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${isDark ? 'bg-blue-400' : 'bg-blue-500'}`} />
                  {modCount} Moderate
                </span>
              )}
            </div>
          </div>
        </div>
        <div className={`w-5 h-5 shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {isMainExpanded ? <ChevronUp strokeWidth={2} /> : <ChevronDown strokeWidth={2} />}
        </div>
      </button>

      {isMainExpanded && (
        <>
          {/* Decision Progress */}
      {totalFlags > 0 && (
        <div className={`px-4 py-3 border-b flex items-center justify-between gap-4 ${
          isDark ? 'border-slate-700/50 bg-slate-800/50' : 'border-slate-100 bg-white'
        }`}>
          <span className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Decision progress</span>
          <div className={`flex-1 h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
            <div 
              className={`h-full rounded-full transition-all duration-300 ${decidedCount === totalFlags ? 'bg-emerald-500' : 'bg-emerald-400'}`}
              style={{ width: `${progressPercent}%` }} 
            />
          </div>
          <span className={`text-sm font-bold ${decidedCount === totalFlags ? 'text-emerald-600' : 'text-emerald-500'}`}>
            {decidedCount}/{totalFlags} decided
          </span>
        </div>
      )}

      {/* Rows for each severity */}
      <div className={isDark ? 'bg-slate-900/30' : 'bg-white rounded-b-xl'}>
        {severityOrder.map(severity => {
          const severityFlags = flags.filter(f => f.severity === severity);
          if (severityFlags.length === 0) return null;
          
          const isExpanded = expandedSections[severity];
          
          return (
            <div key={severity} className={`border-b last:border-b-0 ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
              <button 
                onClick={() => toggleSection(severity)}
                className={`w-full flex items-center px-4 py-3 gap-3 transition-colors ${
                  isDark ? 'hover:bg-slate-800/50' : 'hover:bg-slate-50'
                }`}
              >
                <div className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {isExpanded ? <ChevronDown strokeWidth={2} className="w-4 h-4" /> : <ChevronRight strokeWidth={2} className="w-4 h-4" />}
                </div>
                
                <Badge
                  variant={severity === 'CRITICAL' ? 'danger' : severity === 'MAJOR' ? 'warning' : 'gray'}
                  size="sm"
                  className="shrink-0 font-bold uppercase text-[10px] gap-1.5"
                >
                  {severity === 'CRITICAL' && <AlertOctagon className="w-3 h-3" />}
                  {severity !== 'CRITICAL' && (
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      severity === 'MAJOR' ? 'bg-amber-500' : 'bg-slate-400'
                    }`} />
                  )}
                  {severity}
                </Badge>
                
                <span className={`text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                  {severityFlags.length} concern{severityFlags.length === 1 ? '' : 's'}
                </span>
              </button>
              
              {isExpanded && (
                <div className="px-4 pb-4 pl-12 space-y-3 pt-1">
                  {severityFlags.map((flag) => {
                    const idx = flags.indexOf(flag);
                    const key = flagKey(flag, idx);
                    const decision = decisions[key];
                    const titleDrugs = extractDrugNames(flag.title || safetyFlagTitle(flag));
                    const alternatives = extractAlternatives(flag.suggested_alternative, titleDrugs);

                    return (
                      <div
                        key={key}
                        className={`rounded-lg px-3 py-3 ${severityBg(flag.severity, isDark)}`}
                      >
                        <div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center flex-wrap gap-2">
                              <p className={`text-sm font-semibold leading-snug ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                                {safetyFlagTitle(flag)}
                              </p>
                              {flag._matchedMed?.id && onJumpToMed && (
                                <button
                                  type="button"
                                  onClick={(e) => { e.stopPropagation(); onJumpToMed(flag._matchedMed.id); }}
                                  className={`text-[11px] font-medium underline-offset-2 hover:underline ${
                                    isDark ? 'text-sky-400 hover:text-sky-300' : 'text-sky-700 hover:text-sky-900'
                                  }`}
                                  title={`Jump to this drug in the ${flag._matchedMed.section} list`}
                                >
                                  → in {flag._matchedMed.section} list
                                </button>
                              )}
                            </div>
                            {flag.suggested_alternative && (
                              <p className={`text-[13px] mt-2 font-medium ${isDark ? 'text-sky-400' : 'text-sky-700'}`}>
                                <span className="font-bold">Consider:</span> {flag.suggested_alternative}
                              </p>
                            )}

                            <details className="mt-2.5 group">
                              <summary className={`text-[12px] font-medium cursor-pointer select-none outline-none flex items-center gap-1 w-max opacity-80 hover:opacity-100 transition-opacity ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                                <span className="group-open:hidden flex items-center gap-1"><ChevronRight className="w-3 h-3" /> Show clinical impact</span>
                                <span className="hidden group-open:flex items-center gap-1"><ChevronDown className="w-3 h-3" /> Hide clinical impact</span>
                              </summary>
                              <p className={`text-[13px] mt-1.5 leading-relaxed pl-3 py-0.5 border-l-2 ${isDark ? 'text-slate-400 border-slate-700' : 'text-slate-600 border-slate-200'}`}>
                                {flag.detail}
                              </p>
                            </details>

                            {alternatives.length > 0 && (
                              <div className="mt-3 flex flex-wrap items-center gap-2">
                                <span className={`text-xs font-medium mr-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                                  Replace with:
                                </span>
                                {alternatives.map((alt) => (
                                  <button
                                    key={alt}
                                    type="button"
                                    disabled={!!decision}
                                    onClick={() => handleReplace(key, titleDrugs, alt)}
                                    className={`text-[11px] font-semibold px-2.5 py-1.5 rounded-full border transition-colors ${
                                      decision?.alternative === alt
                                        ? (isDark ? 'bg-sky-500/20 border-sky-400/60 text-sky-200' : 'bg-sky-100 border-sky-400 text-sky-800')
                                        : (isDark ? 'bg-sky-900/30 border-sky-700/50 text-sky-300 hover:bg-sky-800/40' : 'bg-sky-50 border-sky-300 text-sky-800 hover:bg-sky-100')
                                    } ${decision ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                                  >
                                    {alt}
                                  </button>
                                ))}
                              </div>
                            )}

                            {/* Per-flag decision row */}
                            <div className="mt-3.5 flex flex-wrap items-center gap-2">
                              {decision ? (
                                <>
                                  <span className={`text-[11px] font-semibold px-2.5 py-1.5 rounded-md ${
                                    isDark ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-800' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  }`}>
                                    ✓ {DECISION_LABELS[decision.decision]}
                                    {decision.alternative ? ` → ${decision.alternative}` : ''}
                                  </span>
                                  {decision.reason && (
                                    <span className={`text-[11px] italic ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                                      "{decision.reason}"
                                    </span>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => setDecisions((prev) => { const n = { ...prev }; delete n[key]; return n; })}
                                    className={`text-[11px] font-medium underline-offset-2 underline ${isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'}`}
                                  >
                                    Change
                                  </button>
                                </>
                              ) : (
                                <>
                                  {alternatives.length === 0 && (
                                    <button
                                      type="button"
                                      onClick={() => handleReplace(key, titleDrugs, null)}
                                      className={`text-xs font-medium px-3 py-1.5 rounded-md border transition-colors ${
                                        isDark ? 'border-sky-700/60 text-sky-300 hover:bg-sky-900/30' : 'border-sky-300 text-sky-700 hover:bg-sky-50'
                                      }`}
                                    >
                                      Replace
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => handleKeep(key, flag)}
                                    className={`text-xs font-medium px-3 py-1.5 rounded-md border transition-colors ${
                                      isDark ? 'border-amber-700/60 text-amber-300 hover:bg-amber-900/30' : 'border-amber-300 text-amber-700 hover:bg-amber-50'
                                    }`}
                                  >
                                    Keep + acknowledge risk
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleRemove(key, titleDrugs)}
                                    className={`text-xs font-medium px-3 py-1.5 rounded-md border transition-colors ${
                                      isDark ? 'border-slate-600 text-slate-300 hover:bg-slate-700/40' : 'border-slate-300 text-slate-700 hover:bg-slate-100'
                                    }`}
                                  >
                                    Remove from plan
                                  </button>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        
        {/* Informational: drug is on patient's current med list but not in the new plan. */}
        {currentOnlyFlags.length > 0 && (
          <div className={`p-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
            <div className={`rounded-lg border-l-4 ${
              isDark ? 'bg-sky-900/15 border-l-sky-500 border border-sky-700/30' : 'bg-sky-50/60 border-l-sky-500 border border-sky-200'
            } px-4 py-3`}>
              <p className={`text-[11px] font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-sky-300' : 'text-sky-800'}`}>
                Review existing prescription ({currentOnlyFlags.length})
              </p>
              <p className={`text-xs mb-2.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                These drugs are on the patient's current med list but not in this plan. No plan change needed; review with the patient.
              </p>
              <ul className={`text-xs space-y-1.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {currentOnlyFlags.map((f, i) => (
                  <li key={`co-${i}`}><span className="font-semibold">{safetyFlagTitle(f)}</span> — {f.detail}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Informational: class-level / no-match flags (likely Stage 6 critic noise). */}
        {noiseFlags.length > 0 && (
          <div className={`px-4 pb-4 ${currentOnlyFlags.length === 0 ? 'pt-4 border-t ' + (isDark ? 'border-slate-800' : 'border-slate-100') : ''}`}>
            <details className={`rounded-lg border ${
              isDark ? 'bg-slate-800/40 border-slate-700/50' : 'bg-slate-50 border-slate-200'
            } px-4 py-3`}>
              <summary className={`text-[11px] font-semibold uppercase tracking-wider cursor-pointer ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Class-level notices not matched to a prescribed drug ({noiseFlags.length})
              </summary>
              <p className={`text-xs mt-2.5 mb-2.5 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                These flags reference a drug class or alternative drug that is not in the active plan or current meds. Shown for audit; no action required.
              </p>
              <ul className={`text-xs space-y-1.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {noiseFlags.map((f, i) => (
                  <li key={`noise-${i}`}><span className="font-semibold">{safetyFlagTitle(f)}</span> — {f.detail}</li>
                ))}
              </ul>
            </details>
          </div>
        )}
      </div>
      
      {/* Footer Acknowledge Button Container */}
      <div className={`px-4 py-3 border-t ${
        isDark ? 'bg-slate-900/50 border-slate-800' : 'bg-slate-50 border-slate-200'
      }`}>
        {isRed && !acknowledged && (
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="danger"
              size="sm"
              disabled={!allDecided}
              onClick={() => onAcknowledge?.(decisions)}
              title={allDecided ? undefined : 'Resolve every flag (Replace / Keep / Remove) to enable'}
            >
              I have reviewed these concerns and accept clinical responsibility
            </Button>
            {!allDecided && (
              <span className={`text-xs font-medium ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                {totalFlags - decidedCount} flag(s) still need a decision
              </span>
            )}
          </div>
        )}
        {isRed && acknowledged && (
          <div className={`flex items-center gap-2 text-sm font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
            <ShieldCheck className="w-4 h-4" strokeWidth={2} />
            Concerns acknowledged — Approve is now enabled
          </div>
        )}
      </div>
      </>)}

      {/* CRITICAL keep-reason modal */}
      {criticalReasonModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className={`max-w-md w-full mx-4 rounded-xl border p-5 shadow-xl ${
            isDark ? 'bg-slate-900 border-red-700/60' : 'bg-white border-red-300'
          }`}>
            <div className="flex items-center gap-2 mb-3">
              <AlertOctagon className={`w-5 h-5 ${isDark ? 'text-red-400' : 'text-red-600'}`} />
              <h3 className={`text-base font-semibold ${isDark ? 'text-red-300' : 'text-red-800'}`}>
                Keep a CRITICAL flag — clinical justification required
              </h3>
            </div>
            <p className={`text-xs mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              You are overriding a critical safety concern. State the clinical reason — this is recorded in the consultation audit.
            </p>
            <textarea
              autoFocus
              rows={3}
              value={criticalReasonDraft}
              onChange={(e) => setCriticalReasonDraft(e.target.value)}
              placeholder="e.g. patient already on this drug for 3 years without adverse effect; benefit > risk based on…"
              className={`w-full text-sm rounded-md border p-2 ${
                isDark ? 'bg-slate-800 border-slate-700 text-slate-200 placeholder-slate-500' : 'bg-white border-slate-300 text-slate-800 placeholder-slate-400'
              }`}
            />
            <div className="mt-3 flex items-center justify-between">
              <span className={`text-[11px] ${criticalReasonDraft.trim().length < 10
                ? (isDark ? 'text-slate-500' : 'text-slate-500')
                : (isDark ? 'text-emerald-400' : 'text-emerald-700')
              }`}>
                {criticalReasonDraft.trim().length < 10
                  ? `${10 - criticalReasonDraft.trim().length} more character${10 - criticalReasonDraft.trim().length === 1 ? '' : 's'} required`
                  : '✓ Reason looks substantive'}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => { setCriticalReasonModal(null); setCriticalReasonDraft(''); }}
                >
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  disabled={criticalReasonDraft.trim().length < 10}
                  onClick={confirmCriticalKeep}
                >
                  Confirm override
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
