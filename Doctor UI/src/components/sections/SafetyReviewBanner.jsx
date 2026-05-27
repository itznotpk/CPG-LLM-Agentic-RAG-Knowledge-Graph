import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, ShieldX, ChevronDown, ChevronUp, Network, Bot } from 'lucide-react';
import { GlassCard, Button, Badge } from '../shared';
import { useTheme } from '../../context/ThemeContext';

const SEVERITY_ORDER = { CRITICAL: 0, MAJOR: 1, MODERATE: 2 };

const KNOWN_DRUGS = [
  'enalapril', 'spironolactone', 'dapagliflozin', 'bisoprolol', 'furosemide',
  'warfarin', 'aspirin', 'clopidogrel', 'amiodarone', 'digoxin', 'ivabradine',
  'metformin', 'gliclazide', 'insulin', 'atorvastatin', 'simvastatin',
  'amlodipine', 'hydrochlorothiazide', 'losartan', 'valsartan', 'sacubitril',
  'ramipril', 'lisinopril', 'perindopril', 'carvedilol', 'metoprolol',
  'sildenafil', 'tadalafil', 'isosorbide mononitrate', 'nitroglycerin',
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

function severityColor(severity, isDark) {
  if (severity === 'CRITICAL') return isDark ? 'text-red-400' : 'text-red-700';
  if (severity === 'MAJOR')    return isDark ? 'text-amber-400' : 'text-amber-700';
  return isDark ? 'text-slate-400' : 'text-slate-600';
}

function severityBg(severity, isDark) {
  if (severity === 'CRITICAL') return isDark ? 'bg-red-500/10 border-red-500/20' : 'bg-red-50/50 border-red-200';
  if (severity === 'MAJOR')    return isDark ? 'bg-amber-500/10 border-amber-500/20' : 'bg-amber-50/50 border-amber-200';
  return isDark ? 'bg-slate-500/10 border-slate-500/20' : 'bg-slate-50 border-slate-200';
}

/**
 * SafetyReviewBanner
 *
 * Props:
 *   report        : SafetyReport | null
 *   onAcknowledge : () => void  — flips local acknowledged state to unblock Approve
 *   acknowledged  : bool
 */
export function SafetyReviewBanner({ report, onAcknowledge, acknowledged }) {
  const { isDark } = useTheme();
  const [expanded, setExpanded] = useState(false);

  // While critic is running (report not yet received), show nothing
  if (report === undefined || report === null) return null;

  // Deduplicate flags that involve the same set of drugs at the same severity
  // (e.g. "Aspirin + Clopidogrel + Warfarin" vs "Warfarin + Aspirin + Clopidogrel").
  const dedupFlags = (rawFlags) => {
    const seen = new Map(); // key → merged flag
    for (const flag of rawFlags) {
      const drugs = extractDrugNames(flag.title || safetyFlagTitle(flag));
      const key = [...drugs].sort().join('|') + '::' + (flag.severity || '') + '::' + (flag.flag_type || '');
      if (seen.has(key)) {
        // Merge recommendation indices into the existing entry
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

  const flags = dedupFlags(
    (report.flags || []).filter((f) => f.severity !== 'MODERATE')
  ).sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3));
  const hasBlockingFlag = !report.safe_to_proceed;
  const hasFlags = flags.length > 0;

  // ── Green state — no flags ───────────────────────────────────────────────
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

  // ── Amber / Red state — has flags ────────────────────────────────────────
  const topSeverity = flags[0]?.severity;
  const isRed = hasBlockingFlag;

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

  const critCount   = flags.filter(f => f.severity === 'CRITICAL').length;
  const majorCount  = flags.filter(f => f.severity === 'MAJOR').length;
  const modCount    = flags.filter(f => f.severity === 'MODERATE').length;
  const summary = [
    critCount  ? `${critCount} CRITICAL`  : null,
    majorCount ? `${majorCount} MAJOR`    : null,
    modCount   ? `${modCount} MODERATE`   : null,
  ].filter(Boolean).join(', ');

  const graphCount = flags.filter(f => f.source === 'graph').length;
  const llmCount   = flags.filter(f => (f.source ?? 'llm') === 'llm').length;

  return (
    <div className={`rounded-xl border mb-4 overflow-hidden ${bannerBg}`}>
      {/* Header row */}
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
          {(graphCount > 0 || llmCount > 0) && (
            <span className={`hidden sm:inline-flex items-center gap-1 ml-1 text-[10px] font-medium ${textColor} opacity-70`}>
              {graphCount > 0 && (
                <span className="inline-flex items-center gap-0.5">
                  <Network className="w-3 h-3" /> {graphCount} KG
                </span>
              )}
              {llmCount > 0 && (
                <span className="inline-flex items-center gap-0.5">
                  <Bot className="w-3 h-3" /> {llmCount} LLM
                </span>
              )}
            </span>
          )}
        </div>
        <div className={`w-5 h-5 ${textColor}`}>
          {expanded ? <ChevronUp strokeWidth={2} /> : <ChevronDown strokeWidth={2} />}
        </div>
      </button>

      {/* Expanded flag list */}
      {expanded && (
        <div className="px-4 pb-4 space-y-2">
          {flags.map((flag, i) => (
            <div
              key={i}
              className={`rounded-lg border px-3 py-2 ${severityBg(flag.severity, isDark)}`}
            >
              <div className="flex items-start gap-2">
                <Badge
                  variant={flag.severity === 'CRITICAL' ? 'danger' : flag.severity === 'MAJOR' ? 'warning' : 'gray'}
                  size="sm"
                  className="shrink-0 mt-0.5 font-bold uppercase text-[10px] gap-1.5"
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    flag.severity === 'CRITICAL' ? 'bg-red-500 animate-pulse' :
                    flag.severity === 'MAJOR' ? 'bg-amber-500' :
                    'bg-slate-400'
                  }`} />
                  {flag.severity}
                </Badge>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className={`text-sm font-semibold leading-snug ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                      {safetyFlagTitle(flag)}
                    </p>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${
                      isDark
                        ? 'bg-white/5 border-white/10 text-slate-400'
                        : 'bg-white/60 border-slate-200 text-slate-500'
                    }`}>
                      rec {(flag._recIndices && flag._recIndices.length > 0
                        ? flag._recIndices.map(i => `#${i + 1}`).join(', ')
                        : `#${flag.recommendation_index + 1}`)}
                    </span>
                    {flag.source === 'graph' ? (
                      <span
                        title="Verified against a structured edge in the Neo4j clinical knowledge graph"
                        className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${
                          isDark
                            ? 'bg-emerald-900/30 border-emerald-700/50 text-emerald-300'
                            : 'bg-emerald-50 border-emerald-300 text-emerald-800'
                        }`}
                      >
                        <Network className="w-3 h-3" /> Graph-verified
                      </span>
                    ) : (
                      <span
                        title="Adversarial LLM critic finding (independent pharmacist review)"
                        className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${
                          isDark
                            ? 'bg-slate-800/60 border-slate-600/50 text-slate-300'
                            : 'bg-slate-100 border-slate-300 text-slate-700'
                        }`}
                      >
                        <Bot className="w-3 h-3" /> LLM critic
                      </span>
                    )}
                  </div>
                  <p className={`text-xs mt-1 leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>Impact: </span>{flag.detail}
                  </p>
                  {flag.suggested_alternative && (
                    <p className={`text-xs mt-1 font-medium ${isDark ? 'text-sky-400' : 'text-sky-700'}`}>
                      Consider: {flag.suggested_alternative}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}

          {report.reviewer_notes && (
            <p className={`text-xs italic px-1 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              {report.reviewer_notes}
            </p>
          )}

          {/* Acknowledge button — only shown when plan is blocked */}
          {isRed && !acknowledged && (
            <div className="pt-2">
              <Button
                variant="danger"
                size="sm"
                onClick={onAcknowledge}
              >
                I have reviewed these concerns and accept clinical responsibility
              </Button>
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
    </div>
  );
}
