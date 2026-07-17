import React from 'react';
import { AlertCircle, ArrowRight, GitCompareArrows, Globe2, ShieldCheck } from 'lucide-react';
import { Badge, GlassCard } from '../shared';
import { useTheme } from '../../context/ThemeContext';

export default function InternationalGuidancePanel({ comparisonEnabled, comparison }) {
  const { isDark } = useTheme();

  if (!comparisonEnabled) {
    return <GlassCard className="p-6"><div className={`flex gap-3 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}><ShieldCheck className="w-5 h-5 shrink-0 text-emerald-500" /><div><p className={`font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Malaysia CPG mode is active</p><p className="mt-1">The care plan follows the routed Malaysian MoH CPG. Select <strong>Compare international changes</strong> above the plan to review curated differences without changing the active plan.</p></div></div></GlassCard>;
  }

  if (comparison.status !== 'available') {
    return <GlassCard className="p-6"><div className={`flex gap-3 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}><AlertCircle className="w-5 h-5 shrink-0 text-amber-500" /><div><p className={`font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>International comparison unavailable for this diagnosis</p><p className="mt-1">{comparison.message}</p></div></div></GlassCard>;
  }

  const { record } = comparison;
  return (
    <GlassCard className="p-4">
      <div className="flex items-start gap-3">
        <GitCompareArrows className="w-5 h-5 mt-0.5 shrink-0 text-teal-500" />
        <div><div className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>International Guidance Diff</div><p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{record.condition} · reviewed {record.reviewedOn} · Malaysian MoH CPG remains the active plan standard</p></div>
      </div>
      <div className={`mt-4 rounded-lg border px-3 py-2 text-xs ${isDark ? 'border-sky-500/20 bg-sky-500/5 text-slate-300' : 'border-sky-200 bg-sky-50 text-slate-600'}`}><Globe2 className="w-3.5 h-3.5 inline mr-1.5 text-sky-500" />Comparing <strong>{record.local.version} Malaysian MoH guidance</strong> with <strong>{record.international.publisher} {record.international.year}</strong>. This is a curated, read-only review—not an automatic replacement.</div>
      <div className="mt-4 space-y-3">
        {record.changes.map((change, index) => <div key={index} className={`rounded-xl border overflow-hidden ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
          <div className={`flex items-center justify-between px-4 py-2 border-b ${isDark ? 'border-slate-700 bg-slate-800/70' : 'border-slate-100 bg-slate-50'}`}><span className={`text-xs font-bold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{change.section}</span><Badge variant="warning" size="sm">Clinical review needed</Badge></div>
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 p-4 items-start">
            <div><p className={`text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-emerald-300' : 'text-emerald-700'}`}>Active Malaysian CPG</p><p className={`text-xs mt-1 leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{change.local}</p></div>
            <ArrowRight className={`w-4 h-4 hidden md:block mt-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
            <div><p className={`text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-sky-300' : 'text-sky-700'}`}>International comparison</p><p className={`text-xs mt-1 leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{change.international}</p></div>
          </div>
          <div className={`px-4 py-2 text-xs border-t ${isDark ? 'border-slate-700 bg-amber-500/5 text-slate-400' : 'border-slate-100 bg-amber-50/50 text-slate-600'}`}><strong>Why review:</strong> {change.reason}</div>
        </div>)}
      </div>
    </GlassCard>
  );
}
