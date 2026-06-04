import React, { useState, useMemo, useEffect } from 'react';
import {
  BookOpen,
  Stethoscope,
  AlertTriangle,
  FileCheck,
  UserCheck,
  Search,
  ShieldAlert,
  TrendingUp,
  Activity,
  Clock,
  ChevronRight,
} from 'lucide-react';
import { GlassCard as Card } from '../shared';
import { useTheme } from '../../context/ThemeContext';
import { supabase } from '../../lib/supabase';
import { safeJson } from '../../lib/helpers';

function getSeverityOrder(s) {
  const m = { CRITICAL: 0, MAJOR: 1, MODERATE: 2, MINOR: 3 };
  return m[(s || '').toUpperCase()] ?? 4;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricCard({ icon: Icon, label, value, sub, color, isDark }) {
  const colorMap = {
    teal:    { bg: isDark ? 'bg-teal-500/15'    : 'bg-teal-50',    text: isDark ? 'text-teal-400'    : 'text-teal-600'    },
    violet:  { bg: isDark ? 'bg-violet-500/15'  : 'bg-violet-50',  text: isDark ? 'text-violet-400'  : 'text-violet-600'  },
    sky:     { bg: isDark ? 'bg-sky-500/15'     : 'bg-sky-50',     text: isDark ? 'text-sky-400'     : 'text-sky-600'     },
    amber:   { bg: isDark ? 'bg-amber-500/15'   : 'bg-amber-50',   text: isDark ? 'text-amber-400'   : 'text-amber-600'   },
    emerald: { bg: isDark ? 'bg-emerald-500/15' : 'bg-emerald-50', text: isDark ? 'text-emerald-400' : 'text-emerald-600' },
    red:     { bg: isDark ? 'bg-red-500/15'     : 'bg-red-50',     text: isDark ? 'text-red-400'     : 'text-red-500'     },
  };
  const c = colorMap[color] || colorMap.teal;
  return (
    <div className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className={`p-1.5 rounded-lg ${c.bg}`}>
          <Icon className={`w-3.5 h-3.5 ${c.text}`} strokeWidth={2} />
        </span>
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
      </div>
      <p className={`text-3xl font-bold ds-numeric leading-none ${c.text}`}>{value}</p>
      {sub && <p className={`text-xs mt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{sub}</p>}
    </div>
  );
}

function ProgressBar({ value, max = 100, color = 'primary', isDark }) {
  const pct = Math.min((value / max) * 100, 100);
  const colorClass = {
    primary: 'bg-[var(--accent-primary)]',
    teal: 'bg-teal-500',
    violet: 'bg-violet-500',
    sky: 'bg-sky-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  }[color] || 'bg-[var(--accent-primary)]';
  return (
    <div className={`w-full rounded-full h-1.5 overflow-hidden ${isDark ? 'bg-white/10' : 'bg-slate-200'}`}>
      <div className={`h-full rounded-full transition-all duration-500 ${colorClass}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SeverityBadge({ severity, isDark }) {
  const s = (severity || '').toUpperCase();
  const map = {
    CRITICAL: 'bg-red-500/15 text-red-500 border-red-400/30',
    MAJOR:    'bg-amber-500/15 text-amber-600 border-amber-400/30',
    MODERATE: 'bg-yellow-500/15 text-yellow-600 border-yellow-400/30',
    MINOR:    isDark ? 'bg-slate-500/15 text-slate-400 border-slate-500/20' : 'bg-slate-100 text-slate-500 border-slate-200',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${map[s] || map.MINOR}`}>
      {s || 'UNKNOWN'}
    </span>
  );
}

// Mini sparkline — 7 bars
function Sparkline({ data, isDark }) {
  const max = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-0.5 h-8">
      {data.map((v, i) => (
        <div
          key={i}
          title={`${v} consults`}
          className={`flex-1 rounded-sm transition-all ${isDark ? 'bg-teal-400/70' : 'bg-teal-500/70'}`}
          style={{ height: `${Math.max((v / max) * 100, 8)}%` }}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function DashboardSection() {
  const { isDark, accent } = useTheme();
  const [logFilter, setLogFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);

  const [metrics, setMetrics] = useState({
    consultsToday: 0,
    consults30d: 0,
    cpgAligned: { count: 0, total: 1 },
    referrals: { total: 0, emergency: 0, urgent: 0, routine: 0 },
    safetyFlags: { total: 0, critical: 0, major: 0 },
    uniqueCpgs: 0,
  });
  const [weekSparkline, setWeekSparkline] = useState(Array(7).fill(0));
  const [consultationLog, setConsultationLog] = useState([]);
  const [topDiagnoses, setTopDiagnoses] = useState([]);
  const [cpgSectionsUsed, setCpgSectionsUsed] = useState([]);
  const [safetyFlagList, setSafetyFlagList] = useState([]); // aggregated across all consults
  const [referralBreakdown, setReferralBreakdown] = useState([]); // [{specialty, count, urgency}]

  const fetchData = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);

      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

      const { data: consultsData, error } = await supabase
        .from('consultations')
        .select('*')
        .gte('created_at', thirtyDaysAgo.toISOString())
        .order('created_at', { ascending: false });

      if (error) throw error;

      const { data: patientsData } = await supabase
        .from('patients')
        .select('nric, full_name');

      const patientMap = {};
      (patientsData || []).forEach(p => { patientMap[p.nric] = p.full_name; });

      const todayStr = new Date().toISOString().split('T')[0];

      // Build day-bucket map for the last 7 days
      const dayBuckets = {};
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        dayBuckets[d.toISOString().split('T')[0]] = 0;
      }

      let consultsToday = 0;
      let cpgAlignedCount = 0;
      let citationsTotal = 0;
      let referralTotal = 0, refEmergency = 0, refUrgent = 0, refRoutine = 0;
      let flagTotal = 0, flagCritical = 0, flagMajor = 0;
      const dxMap = {};
      const cpgMap = {};
      const cpgSet = new Set();
      const specialtyMap = {};
      const allFlags = [];
      const newLogs = [];

      (consultsData || []).forEach(c => {
        const dayKey = c.created_at.split('T')[0];
        if (dayBuckets.hasOwnProperty(dayKey)) dayBuckets[dayKey]++;
        if (dayKey === todayStr) consultsToday++;

        // CPG references
        const cpgRefs = safeJson(c.cpg_references);
        if (cpgRefs.length > 0) {
          cpgAlignedCount++;
          citationsTotal += cpgRefs.length;
          cpgRefs.forEach(ref => {
            const section = ref.section || ref.title || ref.name || 'General Guideline';
            cpgMap[section] = (cpgMap[section] || 0) + 1;
            const doc = ref.document || ref.source || section;
            cpgSet.add(doc);
          });
        }

        // Safety flags
        const flags = safeJson(c.safety_flags);
        flags.forEach(f => {
          const sev = (f.severity || '').toUpperCase();
          flagTotal++;
          if (sev === 'CRITICAL') flagCritical++;
          if (sev === 'MAJOR') flagMajor++;
          if (sev === 'CRITICAL' || sev === 'MAJOR') {
            allFlags.push({
              severity: sev,
              title: f.title || f.flag || 'Safety concern',
              detail: f.detail || f.description || '',
              patient: patientMap[c.patient_nric] || 'Patient',
              date: dayKey,
            });
          }
        });

        // Referrals
        const refs = safeJson(c.referrals);
        refs.forEach(r => {
          referralTotal++;
          const urg = (r.urgency || '').toLowerCase();
          if (urg === 'emergency') refEmergency++;
          else if (urg === 'urgent') refUrgent++;
          else refRoutine++;

          const spec = r.specialty || r.referral_to || r.type || 'Unspecified';
          if (!specialtyMap[spec]) specialtyMap[spec] = { count: 0, emergency: 0, urgent: 0, routine: 0 };
          specialtyMap[spec].count++;
          if (urg === 'emergency') specialtyMap[spec].emergency++;
          else if (urg === 'urgent') specialtyMap[spec].urgent++;
          else specialtyMap[spec].routine++;
        });

        // Diagnoses
        const dxs = safeJson(c.diagnoses);
        let ddxStr = 'Pending';
        if (dxs.length > 0) {
          const first = dxs[0];
          ddxStr = typeof first === 'string' ? first : (first.condition || first.name || first.diagnosis || 'Unknown');
          dxs.forEach(dx => {
            const name = typeof dx === 'string' ? dx : (dx.condition || dx.name || dx.diagnosis || 'Unknown');
            if (name && name !== 'Unknown') dxMap[name] = (dxMap[name] || 0) + 1;
          });
        }

        let complaintText = 'No notes';
        if (c.clinical_notes) {
          complaintText = c.clinical_notes.replace(/<[^>]*>?/gm, '').substring(0, 60);
          if (c.clinical_notes.length > 60) complaintText += '…';
        }

        newLogs.push({
          id: c.id,
          patient: patientMap[c.patient_nric] || 'Unknown Patient',
          complaint: complaintText,
          ddx: ddxStr,
          cpgCitations: cpgRefs.length,
          flagCount: flags.length,
          hasCritical: flags.some(f => (f.severity || '').toUpperCase() === 'CRITICAL'),
          referralCount: refs.length,
          date: c.created_at,
          dayKey,
        });
      });

      const total30d = Math.max(consultsData.length, 1);

      setMetrics({
        consultsToday,
        consults30d: consultsData.length,
        cpgAligned: { count: cpgAlignedCount, total: total30d },
        referrals: { total: referralTotal, emergency: refEmergency, urgent: refUrgent, routine: refRoutine },
        safetyFlags: { total: flagTotal, critical: flagCritical, major: flagMajor },
        uniqueCpgs: cpgSet.size,
      });

      setWeekSparkline(Object.values(dayBuckets));

      setConsultationLog(newLogs);

      setTopDiagnoses(
        Object.entries(dxMap)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([name, count]) => ({ name, count, pct: Math.round((count / total30d) * 100) }))
      );

      setCpgSectionsUsed(
        Object.entries(cpgMap)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([section, hits]) => ({ section, hits }))
      );

      setSafetyFlagList(
        allFlags.sort((a, b) => getSeverityOrder(a.severity) - getSeverityOrder(b.severity)).slice(0, 20)
      );

      setReferralBreakdown(
        Object.entries(specialtyMap)
          .sort((a, b) => b[1].count - a[1].count)
          .slice(0, 6)
          .map(([specialty, counts]) => ({ specialty, ...counts }))
      );

    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(true);
    const channel = supabase
      .channel('dashboard-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'consultations' }, () => fetchData(false))
      .subscribe();
    return () => supabase.removeChannel(channel);
  }, []);

  const cpgPct = Math.round((metrics.cpgAligned.count / metrics.cpgAligned.total) * 100);

  const filteredLog = useMemo(() => {
    let list = [...consultationLog];
    if (logFilter === 'flagged') list = list.filter(c => c.flagCount > 0);
    if (logFilter === 'referred') list = list.filter(c => c.referralCount > 0);
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      list = list.filter(c => c.patient.toLowerCase().includes(q) || c.ddx.toLowerCase().includes(q));
    }
    return list;
  }, [logFilter, searchTerm, consultationLog]);

  const divider = `border-b md:border-b-0 md:border-r ${isDark ? 'border-white/10' : 'border-slate-200'}`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className={`text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Clinical Performance
          </h1>
          <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            AI-assisted consultations · last 30 days
          </p>
        </div>
        {loading && <span className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'} animate-pulse`}>Syncing…</span>}
      </div>

      {/* ── Row 1: Core metrics ─────────────────────────────────────── */}
      <Card className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
        <div className={`grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 divide-y md:divide-y-0 md:divide-x ${isDark ? 'divide-white/10' : 'divide-slate-200'}`}>
          {/* Consultations today + sparkline */}
          <div className="p-5 lg:col-span-1">
            <div className="flex items-center gap-2 mb-3">
              <span className={`p-1.5 rounded-lg ${isDark ? 'bg-teal-500/15' : 'bg-teal-50'}`}>
                <Stethoscope className={`w-3.5 h-3.5 ${isDark ? 'text-teal-400' : 'text-teal-600'}`} strokeWidth={2} />
              </span>
              <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Consultations</span>
            </div>
            <p className={`text-3xl font-bold ds-numeric leading-none ${isDark ? 'text-teal-400' : 'text-teal-600'}`}>{metrics.consultsToday}</p>
            <p className={`text-xs mt-1.5 mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{metrics.consults30d} in last 30 days</p>
            <Sparkline data={weekSparkline} isDark={isDark} />
            <p className={`text-[9px] mt-1 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>7-day trend</p>
          </div>

          <MetricCard icon={FileCheck}    label="CPG Aligned"      value={<>{cpgPct}<span className="text-lg font-medium ml-0.5 opacity-70">%</span></>}           sub={`${metrics.cpgAligned.count} of ${metrics.cpgAligned.total} plans`}  color="violet"  isDark={isDark} />
          <MetricCard icon={BookOpen}     label="CPG Citations"    value={metrics.cpgAligned.count > 0 ? Math.round(metrics.cpgAligned.count > 0 ? (metrics.cpgAligned.total > 0 ? metrics.uniqueCpgs : 0) : 0) : 0} sub={`${metrics.uniqueCpgs} unique guidelines cited`} color="sky" isDark={isDark} />
          <MetricCard icon={UserCheck}    label="Referrals"        value={metrics.referrals.total}        sub={`${metrics.referrals.emergency} emergency · ${metrics.referrals.urgent} urgent`}     color="amber"   isDark={isDark} />
          <MetricCard icon={ShieldAlert}  label="Safety Flags"     value={metrics.safetyFlags.total}      sub={`${metrics.safetyFlags.critical} critical · ${metrics.safetyFlags.major} major`}      color={metrics.safetyFlags.critical > 0 ? 'red' : 'emerald'} isDark={isDark} />
          <MetricCard icon={Activity}     label="Avg CPG Cites"    value={metrics.consults30d > 0 ? (Math.round((metrics.cpgAligned.count / metrics.consults30d) * 10) / 10).toFixed(1) : '—'}  sub="citations per consult"  color="teal" isDark={isDark} />
        </div>
      </Card>

      {/* ── Row 2: Safety Flags + Referral Breakdown ───────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Safety Flags */}
        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Critical &amp; Major Safety Flags
          </p>
          <Card className="overflow-hidden" variant={isDark ? 'dark' : 'light'}>
            {safetyFlagList.length === 0 ? (
              <div className={`p-6 text-center text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                No critical or major flags in this period
              </div>
            ) : (
              <div className="divide-y divide-transparent">
                {safetyFlagList.slice(0, 8).map((f, i) => (
                  <div key={i} className={`flex items-start gap-3 px-4 py-3 border-b last:border-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                    <div className="pt-0.5 flex-shrink-0">
                      <SeverityBadge severity={f.severity} isDark={isDark} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className={`text-sm font-medium truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>{f.title}</p>
                      {f.detail && <p className={`text-xs mt-0.5 line-clamp-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{f.detail}</p>}
                    </div>
                    <span className={`text-[10px] shrink-0 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>{f.patient}</span>
                  </div>
                ))}
                {safetyFlagList.length > 8 && (
                  <div className={`px-4 py-2 text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    +{safetyFlagList.length - 8} more flags — review full log below
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>

        {/* Referral Breakdown */}
        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Referral Overview
          </p>
          <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
            {/* Urgency summary */}
            <div className={`flex gap-4 mb-5 pb-4 border-b ${isDark ? 'border-white/10' : 'border-slate-100'}`}>
              {[
                { label: 'Emergency', count: metrics.referrals.emergency, color: 'text-red-500' },
                { label: 'Urgent',    count: metrics.referrals.urgent,    color: isDark ? 'text-amber-400' : 'text-amber-600' },
                { label: 'Routine',   count: metrics.referrals.routine,   color: isDark ? 'text-teal-400'  : 'text-teal-600'  },
              ].map(u => (
                <div key={u.label} className="flex-1 text-center">
                  <p className={`text-2xl font-bold ds-numeric ${u.color}`}>{u.count}</p>
                  <p className={`text-[10px] uppercase tracking-wide mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{u.label}</p>
                </div>
              ))}
            </div>

            {/* Top specialties */}
            {referralBreakdown.length === 0 ? (
              <p className={`text-sm text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No referrals in this period</p>
            ) : (
              <div className="space-y-3">
                {referralBreakdown.map(r => (
                  <div key={r.specialty}>
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{r.specialty}</span>
                      <div className="flex items-center gap-2">
                        {r.emergency > 0 && <span className="text-[10px] text-red-500 font-semibold">{r.emergency}🔴</span>}
                        {r.urgent    > 0 && <span className={`text-[10px] font-semibold ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>{r.urgent}⚠</span>}
                        <span className={`text-xs ds-numeric ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{r.count} total</span>
                      </div>
                    </div>
                    <ProgressBar
                      value={r.count}
                      max={referralBreakdown[0].count}
                      color={r.emergency > 0 ? 'red' : r.urgent > 0 ? 'amber' : 'teal'}
                      isDark={isDark}
                    />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* ── Row 3: Top Diagnoses + CPG Sections ────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Top Diagnoses (AI-assisted, 30 days)
          </p>
          <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
            <div className="space-y-4">
              {topDiagnoses.length === 0
                ? <p className={`text-sm text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No diagnosis data</p>
                : topDiagnoses.map((dx, i) => (
                <div key={dx.name}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{dx.name}</span>
                    <span className={`text-xs ds-numeric ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{dx.count} consults</span>
                  </div>
                  <ProgressBar value={dx.pct} color={['teal', 'violet', 'sky', 'amber', 'primary'][i % 5]} isDark={isDark} />
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            CPG Sections Referenced
          </p>
          <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
            <div className="space-y-3">
              {cpgSectionsUsed.length === 0
                ? <p className={`text-sm text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No CPG data</p>
                : cpgSectionsUsed.map(s => (
                <div key={s.section} className={`flex items-center justify-between py-2 border-b last:border-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                  <div className="flex items-center gap-2.5">
                    <BookOpen className={`w-3.5 h-3.5 flex-shrink-0 ${isDark ? 'text-sky-400' : 'text-sky-600'}`} strokeWidth={1.5} />
                    <span className={`text-sm ${isDark ? 'text-white' : 'text-slate-800'}`}>{s.section}</span>
                  </div>
                  <span className={`text-xs ds-numeric font-medium px-2 py-0.5 rounded-full ${isDark ? 'bg-sky-500/15 text-sky-400' : 'bg-sky-50 text-sky-700'}`}>
                    {s.hits} hits
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* ── Consultation Log ────────────────────────────────────────── */}
      <div>
        <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Consultation Log
        </p>
        <Card className="overflow-hidden" variant={isDark ? 'dark' : 'light'}>
          <div className={`flex flex-wrap items-center gap-3 p-4 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
            <div className="flex-1 relative min-w-[200px]">
              <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} strokeWidth={1.5} />
              <input
                type="text"
                placeholder="Search patient or diagnosis…"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className={`w-full pl-9 pr-4 py-2 rounded-lg text-sm border transition-colors
                  ${isDark ? 'bg-white/5 border-white/10 text-white placeholder-slate-500' : 'bg-white border-slate-200 text-slate-800 placeholder-slate-400'}
                  focus:outline-none focus:border-[var(--accent-primary)]/50`}
              />
            </div>
            <div className="flex items-center gap-1.5">
              {[
                { key: 'all',      label: 'All' },
                { key: 'flagged',  label: 'Safety Flagged' },
                { key: 'referred', label: 'Referred' },
              ].map(f => (
                <button
                  key={f.key}
                  onClick={() => setLogFilter(f.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                    ${logFilter === f.key
                      ? `bg-[var(--accent-primary)]/15 ${accent.text} border border-[var(--accent-primary)]/25`
                      : isDark ? 'text-slate-400 hover:bg-white/5 border border-transparent' : 'text-slate-500 hover:bg-slate-50 border border-transparent'
                    }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className={`border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                  {['Date', 'Patient', 'Chief Complaint', 'AI Diagnosis', 'CPG Cites', 'Flags', 'Referrals'].map(h => (
                    <th key={h} className={`text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredLog.length === 0 ? (
                  <tr>
                    <td colSpan={7} className={`px-4 py-8 text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      No consultations match the current filter
                    </td>
                  </tr>
                ) : (
                  filteredLog.map(c => (
                    <tr key={c.id} className={`border-b last:border-0 transition-colors ${isDark ? 'border-white/5 hover:bg-white/5' : 'border-slate-100 hover:bg-slate-50'}`}>
                      <td className={`px-4 py-3 ds-numeric whitespace-nowrap text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {new Date(c.date).toLocaleDateString('en-MY', { day: '2-digit', month: 'short' })}
                        {' '}
                        <span className="opacity-60">{new Date(c.date).toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit' })}</span>
                      </td>
                      <td className={`px-4 py-3 font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{c.patient}</td>
                      <td className={`px-4 py-3 max-w-[180px] truncate ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{c.complaint}</td>
                      <td className={`px-4 py-3 font-medium max-w-[200px] truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>{c.ddx}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 text-xs ds-numeric ${isDark ? 'text-sky-400' : 'text-sky-600'}`}>
                          <BookOpen className="w-3 h-3" strokeWidth={2} />
                          {c.cpgCitations}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {c.flagCount > 0 ? (
                          <span className={`inline-flex items-center gap-1 text-xs font-medium ${c.hasCritical ? 'text-red-500' : isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                            <AlertTriangle className="w-3 h-3" strokeWidth={2} />
                            {c.flagCount}
                          </span>
                        ) : (
                          <span className={`text-xs ${isDark ? 'text-slate-600' : 'text-slate-300'}`}>—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {c.referralCount > 0 ? (
                          <span className={`inline-flex items-center gap-1 text-xs font-medium ${isDark ? 'text-violet-400' : 'text-violet-600'}`}>
                            <ChevronRight className="w-3 h-3" strokeWidth={2} />
                            {c.referralCount}
                          </span>
                        ) : (
                          <span className={`text-xs ${isDark ? 'text-slate-600' : 'text-slate-300'}`}>—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default DashboardSection;
