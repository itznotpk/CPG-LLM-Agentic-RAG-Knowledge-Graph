import React from 'react';
import { AlertCircle, ArrowRight, ExternalLink, GitCompareArrows, Globe2, ShieldCheck } from 'lucide-react';
import { Badge, GlassCard } from '../shared';
import { useTheme } from '../../context/ThemeContext';

export function InternationalCarePlanContext({ activated, comparisonEnabled, evidence = [] }) {
  const { isDark } = useTheme();
  if (!activated) return null;
  const guidelineCount = evidence.filter((item) => item.source_category === 'international_guideline').length;
  const ebmCount = evidence.length - guidelineCount;
  return <div className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3 py-2 text-xs ${isDark ? 'border-teal-400/20 bg-teal-500/5 text-slate-300' : 'border-teal-200 bg-teal-50 text-slate-600'}`}>
    <div className="flex items-center gap-2"><Globe2 className="w-4 h-4 text-teal-600" /><span><strong>International layer active:</strong> {guidelineCount} guideline and {ebmCount} supporting EBM record(s) retrieved for this care plan.</span></div>
    <span className={`rounded-full px-2 py-0.5 font-semibold ${comparisonEnabled ? (isDark ? 'bg-sky-500/15 text-sky-200' : 'bg-sky-100 text-sky-700') : (isDark ? 'bg-white/10 text-slate-300' : 'bg-white text-slate-600')}`}>{comparisonEnabled ? 'Comparison on' : 'Integrated evidence on'}</span>
  </div>;
}

export function InternationalCarePlanDiff({ mappings = [] }) {
  const { isDark } = useTheme();
  if (!mappings.length) return null;
  return <div className={`rounded-xl border p-3 ${isDark ? 'border-amber-400/25 bg-amber-500/5' : 'border-amber-200 bg-amber-50/60'}`}><p className={`text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>Demo mapping comparison — not production approved</p>{mappings.map((item) => <div key={item.id} className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs"><div className={`rounded-md px-2 py-1.5 ${isDark ? 'bg-red-500/10 text-red-200' : 'bg-red-50 text-red-700'}`}><strong>− Local:</strong> {item.local}</div><div className={`rounded-md px-2 py-1.5 ${isDark ? 'bg-emerald-500/10 text-emerald-200' : 'bg-emerald-50 text-emerald-700'}`}><strong>+ International:</strong> {item.international}</div>{item.reason && <p className={`md:col-span-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{item.reason}</p>}</div>)}</div>;
}

export function DemoMappingApprovalPanel({ candidates = [], approvedIds = [], onToggle }) {
  const { isDark } = useTheme();
  if (!candidates.length) return null;
  return <GlassCard className="p-4"><p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Demo mapping review queue</p><p className={`mt-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>For UI demonstration only. Production needs formal-source verification and a named clinical reviewer.</p><div className="mt-3 space-y-2">{candidates.map((item) => { const on = approvedIds.includes(item.id); return <div key={item.id} className={`flex items-center justify-between gap-3 rounded-lg border p-2.5 ${isDark ? 'border-slate-700' : 'border-slate-200'}`}><span className={`text-xs ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{item.section}: {item.local}</span><button type="button" onClick={() => onToggle(item.id)} className={`shrink-0 rounded-md px-2 py-1 text-[11px] font-bold ${on ? 'bg-emerald-500 text-white' : 'bg-amber-100 text-amber-800'}`}>{on ? 'Demo approved' : 'Approve for demo'}</button></div>; })}</div></GlassCard>;
}

export default function InternationalGuidancePanel({ activated, comparisonEnabled, evidence = [] }) {
  const { isDark } = useTheme();
  const muted = isDark ? 'text-slate-400' : 'text-slate-500';
  const heading = isDark ? 'text-white' : 'text-slate-800';

  if (!activated) {
    return <GlassCard className="p-6"><div className={`flex gap-3 text-sm ${muted}`}><AlertCircle className="w-5 h-5 shrink-0 text-amber-500" /><div><p className={`font-semibold ${heading}`}>International guidance was not activated</p><p className="mt-1">Return to Diagnosis and turn on <strong>Activate international guidance</strong> before confirming the working diagnosis.</p></div></div></GlassCard>;
  }
  if (!comparisonEnabled) {
    return <GlassCard className="p-6"><div className={`flex gap-3 text-sm ${muted}`}><ShieldCheck className="w-5 h-5 shrink-0 text-emerald-500" /><div><p className={`font-semibold ${heading}`}>Malaysia CPG mode is active</p><p className="mt-1">The routed Malaysian CPG remains the plan basis. Turn on <strong>Compare international</strong> to review the live international evidence retrieved for this consultation.</p></div></div></GlassCard>;
  }
  if (!evidence.length) {
    return <GlassCard className="p-6"><div className={`flex gap-3 text-sm ${muted}`}><AlertCircle className="w-5 h-5 shrink-0 text-amber-500" /><div><p className={`font-semibold ${heading}`}>No international evidence was retrieved</p><p className="mt-1">Europe PMC returned no eligible recent records. The Malaysian CPG remains the only plan source for this consultation.</p></div></div></GlassCard>;
  }

  const guidelines = evidence.filter((item) => item.source_category === 'international_guideline');
  const ebm = evidence.filter((item) => item.source_category !== 'international_guideline');
  const renderEvidence = (item, index) => <div key={`${item.pmid || item.doi || item.title}-${index}`} className={`rounded-xl border p-3 ${isDark ? 'border-slate-700 bg-slate-800/30' : 'border-slate-200 bg-white'}`}>
    <div className="flex items-start justify-between gap-3"><div><p className={`text-sm font-semibold ${heading}`}>{item.title || 'Untitled record'}</p><p className={`mt-1 text-xs ${muted}`}>{item.source_label || 'Europe PMC'}{item.journal ? ` · ${item.journal}` : ''}{item.year ? ` · ${item.year}` : ''}</p></div><Badge variant={item.source_category === 'international_guideline' ? 'info' : 'default'} size="sm">{item.source_category === 'international_guideline' ? 'Guideline' : `${item.evidence_tier || 'low'} EBM`}</Badge></div>
    {item.abstract_snippet && <p className={`mt-2 text-xs leading-relaxed ${muted}`}>{item.abstract_snippet}</p>}
    {item.url && <a className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline" href={item.url} target="_blank" rel="noreferrer">Open source <ExternalLink className="w-3 h-3" /></a>}
  </div>;

  return <GlassCard className="p-4">
    <div className="flex items-start gap-3"><GitCompareArrows className="w-5 h-5 mt-0.5 shrink-0 text-teal-500" /><div><div className={`text-sm font-semibold ${heading}`}>International evidence comparison</div><p className={`text-xs mt-1 ${muted}`}>Live retrieval for this consultation. Malaysia MoH CPG remains the active local reference until a clinician approves a mapped change.</p></div></div>
    <div className={`mt-4 rounded-lg border px-3 py-2 text-xs ${isDark ? 'border-sky-500/20 bg-sky-500/5 text-slate-300' : 'border-sky-200 bg-sky-50 text-slate-600'}`}><Globe2 className="w-3.5 h-3.5 inline mr-1.5 text-sky-500" />Europe PMC is shown on the international side: records tagged <strong>Guideline</strong> are separated from supporting reviews and trials. It does not automatically replace Malaysian recommendations.</div>
    <div className={`mt-4 rounded-xl border overflow-hidden ${isDark ? 'border-slate-700' : 'border-slate-200'}`}><div className={`grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 p-4 items-start ${isDark ? 'bg-slate-800/40' : 'bg-slate-50'}`}><div><p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">Plan baseline</p><p className={`text-xs mt-1 ${muted}`}>Routed Malaysian MoH CPG recommendations, formulary, access and referral pathways.</p></div><ArrowRight className={`w-4 h-4 hidden md:block mt-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} /><div><p className="text-[10px] font-bold uppercase tracking-wider text-sky-700">International side</p><p className={`text-xs mt-1 ${muted}`}>{guidelines.length} guideline record(s) and {ebm.length} supporting EBM record(s) retrieved live.</p></div></div></div>
    {guidelines.length > 0 && <section className="mt-4"><p className={`mb-2 text-xs font-bold ${heading}`}>Guideline-labelled records</p><div className="space-y-2">{guidelines.map(renderEvidence)}</div></section>}
    <section className="mt-4"><p className={`mb-2 text-xs font-bold ${heading}`}>Supporting international EBM</p><div className="space-y-2">{ebm.map(renderEvidence)}</div></section>
    <p className={`mt-4 text-xs ${muted}`}><strong>Clinical review required:</strong> a true recommendation-by-recommendation replacement diff needs an approved source adapter and clinician-reviewed mapping; this panel never fabricates one from article abstracts.</p>
  </GlassCard>;
}
