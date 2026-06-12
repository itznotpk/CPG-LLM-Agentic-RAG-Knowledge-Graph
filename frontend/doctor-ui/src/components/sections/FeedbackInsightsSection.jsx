import React, { useState, useEffect } from 'react';
import {
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  ShieldAlert,
  MessageSquare,
  Activity,
} from 'lucide-react';
import { GlassCard as Card } from '../shared';
import { useTheme } from '../../context/ThemeContext';
import { supabase, getFeedbackInsights } from '../../lib/supabase';

// signal_type → display label + colour
const SIGNAL_META = {
  gate_failure: { label: 'Referral gate', color: 'amber' },
  coverage_gap: { label: 'Coverage gap', color: 'sky' },
  data_quality: { label: 'Data quality', color: 'violet' },
  stage_error:  { label: 'Stage error', color: 'red' },
  kg_gap:       { label: 'KG gap', color: 'teal' },
};

const ACTION_META = {
  approved:   { label: 'Approved', icon: ThumbsUp, color: 'emerald' },
  rejected:   { label: 'Rejected', icon: ThumbsDown, color: 'red' },
  regenerate: { label: 'Regenerate', icon: RefreshCw, color: 'amber' },
};

// Full static class strings — Tailwind purges interpolated `text-${x}-500`.
const TEXT_500 = {
  teal: 'text-teal-500', violet: 'text-violet-500', sky: 'text-sky-500',
  amber: 'text-amber-500', emerald: 'text-emerald-500', red: 'text-red-500',
};
const txt = (color) => TEXT_500[color] || TEXT_500.teal;

function SeverityDot({ severity }) {
  const map = { critical: 'bg-red-500', warning: 'bg-amber-500', info: 'bg-slate-400' };
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${map[severity] || map.info}`} />;
}

function StatTile({ icon: Icon, label, value, sub, color, isDark }) {
  const colorMap = {
    teal:    isDark ? 'text-teal-400'    : 'text-teal-600',
    violet:  isDark ? 'text-violet-400'  : 'text-violet-600',
    sky:     isDark ? 'text-sky-400'     : 'text-sky-600',
    amber:   isDark ? 'text-amber-400'   : 'text-amber-600',
    emerald: isDark ? 'text-emerald-400' : 'text-emerald-600',
    red:     isDark ? 'text-red-400'     : 'text-red-500',
  };
  const c = colorMap[color] || colorMap.teal;
  return (
    <div className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-3.5 h-3.5 ${c}`} strokeWidth={2} />
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
      </div>
      <p className={`text-3xl font-bold ds-numeric leading-none ${c}`}>{value}</p>
      {sub && <p className={`text-xs mt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{sub}</p>}
    </div>
  );
}

function Bar({ pct, color, isDark }) {
  const colorClass = {
    teal: 'bg-teal-500', violet: 'bg-violet-500', sky: 'bg-sky-500',
    amber: 'bg-amber-500', emerald: 'bg-emerald-500', red: 'bg-red-500',
  }[color] || 'bg-[var(--accent-primary)]';
  return (
    <div className={`w-full rounded-full h-1.5 overflow-hidden ${isDark ? 'bg-white/10' : 'bg-slate-200'}`}>
      <div className={`h-full rounded-full transition-all duration-500 ${colorClass}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

export function FeedbackInsightsSection({ days = 30 }) {
  const { isDark } = useTheme();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    const insights = await getFeedbackInsights({ days });
    setData(insights);
    setLoading(false);
  };

  useEffect(() => {
    load(true);
    // Re-aggregate when either feed changes (mirrors DashboardSection's realtime sub).
    const channel = supabase
      .channel('feedback-insights-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'human_signals' }, () => load(false))
      .on('postgres_changes', { event: '*', schema: 'public', table: 'machine_signals' }, () => load(false))
      .subscribe();
    return () => supabase.removeChannel(channel);
  }, [days]);

  const mutedText = isDark ? 'text-slate-400' : 'text-slate-500';
  const subtleText = isDark ? 'text-slate-500' : 'text-slate-400';
  const rowBorder = isDark ? 'border-white/10' : 'border-slate-200';

  if (!data) {
    return (
      <Card className="p-6" variant={isDark ? 'dark' : 'light'}>
        <p className={`text-sm ${mutedText} animate-pulse`}>Loading feedback insights…</p>
      </Card>
    );
  }

  const { human, recentComments, cpgRejection, machine, pipeline } = data;
  const hasAny = human.total > 0 || machine.total > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className={`text-2xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Feedback &amp; System Health
          </h2>
          <p className={`mt-1 text-sm ${mutedText}`}>
            Clinician feedback &amp; pipeline signals · last {days} days
          </p>
        </div>
        {loading && <span className={`text-xs mt-1 ${subtleText} animate-pulse`}>Syncing…</span>}
      </div>

      {!hasAny && (
        <Card className="p-6" variant={isDark ? 'dark' : 'light'}>
          <p className={`text-sm ${mutedText}`}>
            No feedback or pipeline signals recorded yet in this window. Approve or reject a care plan,
            and run a consultation, to populate this view.
          </p>
        </Card>
      )}

      {/* ── Row 1: Human-signal headline metrics ─────────────────────── */}
      <Card className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
        <div className={`grid grid-cols-2 md:grid-cols-4 divide-y md:divide-y-0 md:divide-x ${isDark ? 'divide-white/10' : 'divide-slate-200'}`}>
          <StatTile icon={ThumbsUp}    label="Approval Rate" value={<>{human.approvalRate}<span className="text-lg font-medium ml-0.5 opacity-70">%</span></>} sub={`${human.approved} of ${human.total} decisions`} color="emerald" isDark={isDark} />
          <StatTile icon={ThumbsDown}  label="Rejected"      value={human.rejected}        sub="sent back / regenerated" color="red" isDark={isDark} />
          <StatTile icon={ShieldAlert} label="Safety Overrides" value={human.safetyOverrides} sub="blocked plans shipped" color={human.safetyOverrides > 0 ? 'red' : 'emerald'} isDark={isDark} />
          <StatTile icon={Activity}    label="Pipeline Signals" value={machine.total}      sub={`${Object.keys(machine.byType).length} signal types`} color="sky" isDark={isDark} />
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── CPG amendment rate ──────────────────────────────────────── */}
        <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
          <h3 className={`text-sm font-semibold mb-1 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Most-amended CPGs</h3>
          <p className={`text-[11px] mb-4 ${subtleText}`}>Guidelines whose plans clinicians most often reject or send back</p>
          {cpgRejection.length === 0 ? (
            <p className={`text-xs ${subtleText}`}>
              Nothing here yet — this fills in when clinicians reject or regenerate a plan,
              attributing the amendment to the CPGs it cited. An empty panel with decisions
              recorded means plans are being approved as-is.
            </p>
          ) : (
            <div className="space-y-3">
              {cpgRejection.map((c) => (
                <div key={c.cpg}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-medium truncate pr-2 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{c.cpg}</span>
                    <span className={`text-xs font-bold tabular-nums ${c.rate >= 50 ? 'text-red-500' : mutedText}`}>{c.rate}%</span>
                  </div>
                  <Bar pct={c.rate} color={c.rate >= 50 ? 'red' : 'amber'} isDark={isDark} />
                  <p className={`text-[10px] mt-0.5 ${subtleText}`}>{c.rejected} amended of {c.total} plans citing it</p>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* ── Pipeline signals, parsed into what to act on ────────────── */}
        <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
          <h3 className={`text-sm font-semibold mb-1 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Recurring pipeline signals</h3>
          <p className={`text-[11px] mb-4 ${subtleText}`}>Missing inputs that keep blocking CPG referral triggers</p>
          {machine.total === 0 ? (
            <p className={`text-xs ${subtleText}`}>No pipeline signals recorded yet.</p>
          ) : (
            <div className="space-y-4">
              {pipeline.missingData.length > 0 && (
                <div className="space-y-2">
                  {pipeline.missingData.map((m, i) => (
                    <div key={i} className={`flex items-start justify-between gap-3 pb-2 ${i < pipeline.missingData.length - 1 ? `border-b ${rowBorder}` : ''}`}>
                      <div className="min-w-0">
                        <p className={`text-xs font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{m.reason}</p>
                        <p className={`text-[10px] mt-0.5 ${subtleText}`}>
                          blocks {m.specialties.join(', ')} referral{m.specialties.length > 1 ? 's' : ''}
                        </p>
                      </div>
                      <span className={`text-xs font-bold tabular-nums shrink-0 px-1.5 py-0.5 rounded-full ${isDark ? 'bg-amber-500/15 text-amber-400' : 'bg-amber-50 text-amber-600'}`}>
                        ×{m.count}
                      </span>
                    </div>
                  ))}
                  <p className={`text-[10px] pt-1 ${subtleText}`}>
                    Capturing these at intake (Step 1) lets the AI confirm or rule out the referral instead of leaving it pending.
                  </p>
                </div>
              )}

              {pipeline.otherTop.length > 0 && (
                <ul className="space-y-2">
                  {pipeline.otherTop.map((s, i) => {
                    const meta = SIGNAL_META[s.signal_type] || { label: s.signal_type, color: 'teal' };
                    return (
                      <li key={i} className="flex items-start gap-2">
                        <SeverityDot severity={s.severity} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] font-bold uppercase tracking-wider ${txt(meta.color)}`}>{meta.label}</span>
                            <span className={`text-xs font-bold tabular-nums ${mutedText}`}>×{s.count}</span>
                          </div>
                          <p className={`text-xs mt-0.5 break-words ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{s.detail}</p>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              {(pipeline.ruledOut > 0 || pipeline.suppressed > 0) && (
                <p className={`text-[10px] pt-2 border-t ${rowBorder} ${subtleText}`}>
                  {pipeline.ruledOut > 0 && <>{pipeline.ruledOut} referral trigger{pipeline.ruledOut > 1 ? 's' : ''} correctly ruled out by documented evidence</>}
                  {pipeline.ruledOut > 0 && pipeline.suppressed > 0 && ' · '}
                  {pipeline.suppressed > 0 && <>{pipeline.suppressed} low-priority suppression notice{pipeline.suppressed > 1 ? 's' : ''} hidden</>}
                </p>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* ── Recent clinician comments ─────────────────────────────────── */}
      <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className={`w-4 h-4 ${isDark ? 'text-violet-400' : 'text-violet-600'}`} />
          <h3 className={`text-sm font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Recent clinician comments</h3>
        </div>
        {recentComments.length === 0 ? (
          <p className={`text-xs ${subtleText}`}>No comments captured yet.</p>
        ) : (
          <div className="space-y-3">
            {recentComments.map((c, i) => {
              const meta = ACTION_META[c.action] || { label: c.action, icon: MessageSquare, color: 'teal' };
              const Icon = meta.icon;
              return (
                <div key={i} className={`flex items-start gap-3 pb-3 ${i < recentComments.length - 1 ? `border-b ${rowBorder}` : ''}`}>
                  <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${txt(meta.color)}`} strokeWidth={2} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${txt(meta.color)}`}>{meta.label}</span>
                      {c.safetyOverridden && (
                        <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-500">Safety override</span>
                      )}
                      <span className={`text-[10px] ${subtleText}`}>{c.clinician}</span>
                      <span className={`text-[10px] ${subtleText}`}>· {new Date(c.at).toLocaleString()}</span>
                    </div>
                    <p className={`text-xs mt-1 italic ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>"{c.comment}"</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

export default FeedbackInsightsSection;
