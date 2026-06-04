import React, { useState, useMemo } from 'react';
import { Network, ChevronDown, ChevronUp, Star } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

const RELATION_LABEL = {
  FIRST_LINE_FOR: '1st-line',
  SECOND_LINE_FOR: '2nd-line',
  RECOMMENDED_FOR: 'Recommended',
};

/**
 * GraphNavigatorPanel
 *
 * Renders the preferred-agent rules surfaced by Agent 2 (Graph Navigator) —
 * positive guidance pulled directly from typed Neo4j edges
 * (FIRST_LINE_FOR / SECOND_LINE_FOR / RECOMMENDED_FOR), scoped to the routed
 * CPGs and denoised of parser-error table-row extractions.
 *
 * Props:
 *   rules: [{drug, condition, relation, evidence, source_document, cpg_chunk_id}]
 */
export function GraphNavigatorPanel({ rules }) {
  const { isDark } = useTheme();
  const [expanded, setExpanded] = useState(false);

  // Group rules by condition for legibility; within each group, sort
  // 1st-line → 2nd-line → recommended → other.
  const grouped = useMemo(() => {
    const order = { FIRST_LINE_FOR: 0, SECOND_LINE_FOR: 1, RECOMMENDED_FOR: 2 };
    const byCond = {};
    for (const r of rules || []) {
      const key = r.condition || 'Unknown';
      (byCond[key] = byCond[key] || []).push(r);
    }
    for (const k of Object.keys(byCond)) {
      byCond[k].sort((a, b) =>
        (order[a.relation] ?? 9) - (order[b.relation] ?? 9) ||
        (a.drug || '').localeCompare(b.drug || '')
      );
    }
    return byCond;
  }, [rules]);

  if (!rules || rules.length === 0) return null;

  const conditions = Object.keys(grouped);
  const drugCount = rules.length;

  return (
    <div
      className={`rounded-xl border mb-4 overflow-hidden ${
        isDark
          ? 'bg-emerald-900/15 border-emerald-700/40'
          : 'bg-emerald-50/60 border-emerald-300'
      }`}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Network
            className={`w-5 h-5 shrink-0 ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}
            strokeWidth={2}
          />
          <span className={`text-sm font-semibold ${isDark ? 'text-emerald-200' : 'text-emerald-900'}`}>
            Guideline-preferred therapy (graph-verified)
          </span>
          <span className={`text-xs font-medium opacity-80 ${isDark ? 'text-emerald-300' : 'text-emerald-800'}`}>
            — {drugCount} rule{drugCount === 1 ? '' : 's'} across {conditions.length} condition{conditions.length === 1 ? '' : 's'}
          </span>
        </div>
        <div className={`w-5 h-5 ${isDark ? 'text-emerald-300' : 'text-emerald-800'}`}>
          {expanded ? <ChevronUp strokeWidth={2} /> : <ChevronDown strokeWidth={2} />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-4">
          <p className={`text-xs italic ${isDark ? 'text-emerald-300/80' : 'text-emerald-800/80'}`}>
            Sourced from typed edges in the Neo4j clinical KG, scoped to the routed CPGs.
            These are positive recommendations from the guideline — review against the patient's
            full profile before prescribing.
          </p>

          {conditions.map((cond) => (
            <div key={cond}>
              <div className={`text-xs font-semibold uppercase tracking-wide mb-2 ${
                isDark ? 'text-emerald-300' : 'text-emerald-800'
              }`}>
                {cond}
              </div>
              <div className="space-y-2">
                {grouped[cond].map((r, i) => {
                  const isFirstLine = r.relation === 'FIRST_LINE_FOR';
                  return (
                    <div
                      key={i}
                      className={`rounded-lg border px-3 py-2 ${
                        isDark
                          ? 'bg-slate-900/40 border-slate-700/50'
                          : 'bg-white/80 border-slate-200'
                      }`}
                    >
                      <div className="flex items-start gap-2 flex-wrap">
                        {isFirstLine && (
                          <Star
                            className={`w-3.5 h-3.5 mt-1 shrink-0 ${
                              isDark ? 'text-amber-400' : 'text-amber-500'
                            }`}
                            fill="currentColor"
                            strokeWidth={2}
                          />
                        )}
                        <span className={`text-sm font-semibold ${
                          isDark ? 'text-slate-100' : 'text-slate-900'
                        }`}>
                          {r.drug}
                        </span>
                        <span
                          className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${
                            isFirstLine
                              ? (isDark
                                  ? 'bg-amber-900/30 border-amber-600/50 text-amber-300'
                                  : 'bg-amber-50 border-amber-300 text-amber-800')
                              : (isDark
                                  ? 'bg-slate-800 border-slate-600 text-slate-300'
                                  : 'bg-slate-100 border-slate-300 text-slate-700')
                          }`}
                        >
                          {RELATION_LABEL[r.relation] || r.relation}
                        </span>
                      </div>
                      {r.evidence && (
                        <p className={`text-xs mt-1.5 leading-snug ${
                          isDark ? 'text-slate-400' : 'text-slate-600'
                        }`}>
                          "{r.evidence}"
                        </p>
                      )}
                      {r.source_document && (
                        <p className={`text-[11px] mt-1 ${
                          isDark ? 'text-slate-500' : 'text-slate-500'
                        }`}>
                          Source: {r.source_document}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
