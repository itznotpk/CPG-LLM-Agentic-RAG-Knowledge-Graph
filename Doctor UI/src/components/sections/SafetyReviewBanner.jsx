import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, ShieldX, ChevronDown, ChevronUp, AlertOctagon } from 'lucide-react';
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
  if (severity === 'CRITICAL') return isDark ? 'bg-red-500/10 border-red-500/30' : 'bg-red-50/80 border-red-300';
  if (severity === 'MAJOR')    return isDark ? 'bg-amber-500/10 border-amber-500/20' : 'bg-amber-50/50 border-amber-200';
  return isDark ? 'bg-slate-500/10 border-slate-500/20' : 'bg-slate-50 border-slate-200';
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
  const [expanded, setExpanded] = useState(false);
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

  return (
    <div className={`rounded-xl border mb-4 overflow-hidden ${bannerBg}`}>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 shrink-0 ${iconColor}`} strokeWidth={2} />
          <span className={`text-sm font-semibold ${textColor}`}>
            {isRed ? 'Safety concerns require acknowledgement' : 'Safety concerns detected'}
          </span>
          <span className={`text-xs font-medium ${textColor} opacity-80`}>— {summary}</span>
        </div>
        <div className={`w-5 h-5 ${textColor}`}>
          {expanded ? <ChevronUp strokeWidth={2} /> : <ChevronDown strokeWidth={2} />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-2">
          <p className={`text-xs font-medium px-1 ${textColor} opacity-90`}>{tightenedNote}</p>

          {flags.map((flag, i) => {
            const key = flagKey(flag, i);
            const decision = decisions[key];
            const isCritical = flag.severity === 'CRITICAL';
            const titleDrugs = extractDrugNames(flag.title || safetyFlagTitle(flag));
            const alternatives = extractAlternatives(flag.suggested_alternative, titleDrugs);

            return (
              <div
                key={key}
                className={`rounded-lg border px-3 py-2 ${severityBg(flag.severity, isDark)} ${
                  isCritical ? 'border-l-4' : ''
                } ${isCritical && (isDark ? 'border-l-red-500' : 'border-l-red-600')}`}
              >
                <div className="flex items-start gap-2">
                  <Badge
                    variant={isCritical ? 'danger' : flag.severity === 'MAJOR' ? 'warning' : 'gray'}
                    size="sm"
                    className="shrink-0 mt-0.5 font-bold uppercase text-[10px] gap-1.5"
                  >
                    {isCritical && <AlertOctagon className="w-3 h-3" />}
                    {!isCritical && (
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        flag.severity === 'MAJOR' ? 'bg-amber-500' : 'bg-slate-400'
                      }`} />
                    )}
                    {flag.severity}
                  </Badge>
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
                    <p className={`text-xs mt-1 leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>Impact: </span>{flag.detail}
                    </p>

                    {flag.suggested_alternative && alternatives.length === 0 && (
                      <p className={`text-xs mt-1 font-medium ${isDark ? 'text-sky-400' : 'text-sky-700'}`}>
                        Consider: {flag.suggested_alternative}
                      </p>
                    )}

                    {alternatives.length > 0 && (
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <span className={`text-[11px] font-medium mr-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                          Replace with:
                        </span>
                        {alternatives.map((alt) => (
                          <button
                            key={alt}
                            type="button"
                            disabled={!!decision}
                            onClick={() => handleReplace(key, titleDrugs, alt)}
                            className={`text-[11px] font-semibold px-2 py-1 rounded-full border transition-colors ${
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
                    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                      {decision ? (
                        <>
                          <span className={`text-[11px] font-semibold px-2 py-1 rounded-full ${
                            isDark ? 'bg-emerald-900/40 text-emerald-300' : 'bg-emerald-100 text-emerald-800'
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
                            className={`text-[11px] underline ${isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'}`}
                          >
                            change
                          </button>
                        </>
                      ) : (
                        <>
                          {alternatives.length === 0 && (
                            <button
                              type="button"
                              onClick={() => handleReplace(key, titleDrugs, null)}
                              className={`text-[11px] font-medium px-2 py-1 rounded-md border ${
                                isDark ? 'border-sky-700/60 text-sky-300 hover:bg-sky-900/30' : 'border-sky-300 text-sky-700 hover:bg-sky-50'
                              }`}
                            >
                              Replace
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleKeep(key, flag)}
                            className={`text-[11px] font-medium px-2 py-1 rounded-md border ${
                              isDark ? 'border-amber-700/60 text-amber-300 hover:bg-amber-900/30' : 'border-amber-300 text-amber-700 hover:bg-amber-50'
                            }`}
                          >
                            Keep + acknowledge risk
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemove(key, titleDrugs)}
                            className={`text-[11px] font-medium px-2 py-1 rounded-md border ${
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

          {/* Informational: drug is on patient's current med list but not in the new plan.
              No plan-side decision possible — surfaced so the clinician can review
              the patient's existing prescription separately. */}
          {currentOnlyFlags.length > 0 && (
            <div className={`mt-2 rounded-lg border-l-4 ${
              isDark ? 'bg-sky-900/15 border-l-sky-500 border border-sky-700/30' : 'bg-sky-50/60 border-l-sky-500 border border-sky-200'
            } px-3 py-2`}>
              <p className={`text-[11px] font-semibold uppercase tracking-wider mb-1 ${isDark ? 'text-sky-300' : 'text-sky-800'}`}>
                Review existing prescription ({currentOnlyFlags.length})
              </p>
              <p className={`text-xs mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                These drugs are on the patient's current med list but not in this plan. No plan change needed; review with the patient.
              </p>
              <ul className={`text-xs space-y-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {currentOnlyFlags.map((f, i) => (
                  <li key={`co-${i}`}><span className="font-semibold">{safetyFlagTitle(f)}</span> — {f.detail}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Informational: class-level / no-match flags (likely Stage 6 critic noise). */}
          {noiseFlags.length > 0 && (
            <details className={`mt-2 rounded-lg border ${
              isDark ? 'bg-slate-800/40 border-slate-700/50' : 'bg-slate-50 border-slate-200'
            } px-3 py-2`}>
              <summary className={`text-[11px] font-semibold uppercase tracking-wider cursor-pointer ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Class-level notices not matched to a prescribed drug ({noiseFlags.length})
              </summary>
              <p className={`text-xs mt-2 mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                These flags reference a drug class or alternative drug that is not in the active plan or current meds. Shown for audit; no action required.
              </p>
              <ul className={`text-xs space-y-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {noiseFlags.map((f, i) => (
                  <li key={`noise-${i}`}><span className="font-semibold">{safetyFlagTitle(f)}</span> — {f.detail}</li>
                ))}
              </ul>
            </details>
          )}

          {/* Acknowledge button — only enabled once every flag has a decision */}
          {isRed && !acknowledged && (
            <div className="pt-2 flex items-center gap-3">
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
                <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {flags.filter((f, i) => !decisions[flagKey(f, i)]).length} flag(s) still need a decision
                </span>
              )}
            </div>
          )}
          {isRed && acknowledged && (
            <div className={`flex items-center gap-2 text-xs font-medium pt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              <ShieldCheck className="w-3.5 h-3.5" />
              Concerns acknowledged — Approve is now enabled
            </div>
          )}
        </div>
      )}

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
