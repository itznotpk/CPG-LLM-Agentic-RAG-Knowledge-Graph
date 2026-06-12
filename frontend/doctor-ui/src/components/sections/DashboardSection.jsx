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
  ChevronDown,
} from 'lucide-react';
import { GlassCard as Card } from '../shared';
import { useTheme } from '../../context/ThemeContext';
import { supabase } from '../../lib/supabase';
import { safeJson } from '../../lib/helpers';

function getSeverityOrder(s) {
  const m = { CRITICAL: 0, MAJOR: 1, MODERATE: 2, MINOR: 3 };
  return m[(s || '').toUpperCase()] ?? 4;
}

// Legacy cpg_references shape stores citations as "CPG <short> §<sec> [chunk N]".
const LEGACY_CITE_RE = /^CPG\s+(.+?)\s+§([\d.]+)/;

// "T2-Diabetes-Mellitus(6th-Edition)" → "T2 Diabetes Mellitus"; strips the
// edition/year parenthetical so legacy titles and cpgFullName group together.
function prettifyCpgName(name) {
  return name
    .replace(/[-_]/g, ' ')
    .replace(/\s*\([^)]*\)\s*$/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Referral specialty strings arrive as "Referral to Cardiology", "Cardiology
// review", etc. — normalise to the bare specialty so rows group cleanly.
function cleanSpecialty(s) {
  return (s || '')
    .replace(/^refer(ral)?\s+to\s+/i, '')
    .replace(/\s+(review|consultation|referral)$/i, '')
    .trim() || 'Unspecified';
}

// clinical_notes often lead with a "[Severity/Staging] - …" block; the real
// chief complaint sits after a "CC:" marker. Prefer it when present.
function extractComplaint(notes) {
  if (!notes) return 'No notes';
  const text = notes.replace(/<[^>]*>?/gm, '');
  const ccMatch = /CC:\s*(.+)/s.exec(text);
  const src = ccMatch ? ccMatch[1] : text;
  return src.substring(0, 60) + (src.length > 60 ? '…' : '');
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

export function DashboardSection({ days = 30 }) {
  const { isDark, accent } = useTheme();
  const [logFilter, setLogFilter] = useState('completed');
  const [searchTerm, setSearchTerm] = useState('');
  const [specialtyFilter, setSpecialtyFilter] = useState(null); // set by clicking a Referral Overview row
  const [loading, setLoading] = useState(true);
  const [expandedFlag, setExpandedFlag] = useState(null); // flag-group key

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
  const [cpgUsage, setCpgUsage] = useState([]); // [{doc, citations, consults, topSections:[{sec,count}], moreSections}]
  const [safetyFlagList, setSafetyFlagList] = useState([]); // aggregated across all consults
  const [referralBreakdown, setReferralBreakdown] = useState([]); // [{specialty, count, urgency}]

  const fetchData = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);

      const windowStart = new Date();
      windowStart.setDate(windowStart.getDate() - days);

      // Only the columns this dashboard actually reads — select('*') dragged
      // down every JSONB column (care plans, timings, summaries…) per row and
      // made the initial sync take seconds.
      const { data: consultsData, error } = await supabase
        .from('consultations')
        .select('id, created_at, patient_nric, clinical_notes, cpg_references, safety_flags, referrals, diagnoses')
        .gte('created_at', windowStart.toISOString())
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
            let doc = ref.cpgFullName || ref.cpgShortName || null;
            let sec = ref.sectionNum || null;
            if (!doc) {
              const t = ref.title || ref.document || ref.source || ref.name || '';
              const m = LEGACY_CITE_RE.exec(t);
              if (m) { doc = m[1]; sec = sec || m[2]; }
              else doc = t || 'Unknown CPG';
            }
            doc = prettifyCpgName(doc);
            if (!cpgMap[doc]) cpgMap[doc] = { citations: 0, consults: new Set(), sections: {} };
            cpgMap[doc].citations++;
            cpgMap[doc].consults.add(c.id);
            if (sec) cpgMap[doc].sections[sec] = (cpgMap[doc].sections[sec] || 0) + 1;
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
        const rowSpecs = [];
        refs.forEach(r => {
          referralTotal++;
          const urg = (r.urgency || '').toLowerCase();
          if (urg === 'emergency') refEmergency++;
          else if (urg === 'urgent') refUrgent++;
          else refRoutine++;

          const spec = cleanSpecialty(r.specialty || r.referral_to || r.type);
          if (!rowSpecs.includes(spec)) rowSpecs.push(spec);
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
            if (name && name !== 'Unknown') {
              const key = name.toLowerCase();
              if (!dxMap[key]) dxMap[key] = { display: name, count: 0 };
              dxMap[key].count++;
            }
          });
        }

        newLogs.push({
          id: c.id,
          patient: patientMap[c.patient_nric] || 'Unknown Patient',
          complaint: extractComplaint(c.clinical_notes),
          ddx: ddxStr,
          incomplete: ddxStr === 'Pending',
          referralSpecs: rowSpecs,
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
        Object.values(dxMap)
          .sort((a, b) => b.count - a.count)
          .slice(0, 5)
          .map(({ display, count }) => ({ name: display, count, pct: Math.round((count / total30d) * 100) }))
      );

      setCpgUsage(
        Object.entries(cpgMap)
          .sort((a, b) => b[1].citations - a[1].citations)
          .slice(0, 6)
          .map(([doc, d]) => {
            const sections = Object.entries(d.sections)
              .sort((a, b) => b[1] - a[1])
              .map(([sec, count]) => ({ sec, count }));
            return {
              doc,
              citations: d.citations,
              consults: d.consults.size,
              topSections: sections.slice(0, 3),
              moreSections: Math.max(sections.length - 3, 0),
            };
          })
      );

      setSafetyFlagList(
        allFlags.sort((a, b) => getSeverityOrder(a.severity) - getSeverityOrder(b.severity))
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
  }, [days]);

  const cpgPct = Math.round((metrics.cpgAligned.count / metrics.cpgAligned.total) * 100);

  // Group identical flags fired across consultations into one pattern row,
  // severity-first then recurrence — recurring patterns are the real signal.
  const flagGroups = useMemo(() => {
    const groups = {};
    for (const f of safetyFlagList) {
      const key = (f.title || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
      if (!groups[key]) groups[key] = { key, title: f.title, severity: f.severity, patients: [], instances: [] };
      const g = groups[key];
      if (getSeverityOrder(f.severity) < getSeverityOrder(g.severity)) g.severity = f.severity;
      if (!g.patients.includes(f.patient)) g.patients.push(f.patient);
      g.instances.push(f);
    }
    return Object.values(groups).sort((a, b) =>
      getSeverityOrder(a.severity) - getSeverityOrder(b.severity) || b.instances.length - a.instances.length
    );
  }, [safetyFlagList]);

  const filteredLog = useMemo(() => {
    let list = [...consultationLog];
    if (logFilter === 'completed') list = list.filter(c => !c.incomplete);
    if (logFilter === 'flagged') list = list.filter(c => c.flagCount > 0);
    if (logFilter === 'referred') list = list.filter(c => c.referralCount > 0);
    if (specialtyFilter) list = list.filter(c => c.referralSpecs.includes(specialtyFilter));
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      list = list.filter(c => c.patient.toLowerCase().includes(q) || c.ddx.toLowerCase().includes(q));
    }
    return list;
  }, [logFilter, searchTerm, specialtyFilter, consultationLog]);

  const incompleteCount = useMemo(() => consultationLog.filter(c => c.incomplete).length, [consultationLog]);

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
            AI-assisted consultations · last {days} days
          </p>
        </div>
        {loading && <span className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'} animate-pulse`}>Syncing…</span>}
      </div>

      {/* ── Row 1: Core metrics ─────────────────────────────────────── */}
      <Card className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
        <div className={`grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 divide-y md:divide-y-0 md:divide-x ${isDark ? 'divide-white/10' : 'divide-slate-200'}`}>
          {/* Consultations today + sparkline */}
          <div className="p-5 lg:col-span-1">
            <div className="flex items-center gap-2 mb-3">
              <span className={`p-1.5 rounded-lg ${isDark ? 'bg-teal-500/15' : 'bg-teal-50'}`}>
                <Stethoscope className={`w-3.5 h-3.5 ${isDark ? 'text-teal-400' : 'text-teal-600'}`} strokeWidth={2} />
              </span>
              <span className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Consultations</span>
            </div>
            <p className={`text-3xl font-bold ds-numeric leading-none ${isDark ? 'text-teal-400' : 'text-teal-600'}`}>{metrics.consultsToday}</p>
            <p className={`text-xs mt-1.5 mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{metrics.consults30d} in last {days} days</p>
            <Sparkline data={weekSparkline} isDark={isDark} />
            <p className={`text-[9px] mt-1 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>7-day trend</p>
          </div>

          <MetricCard icon={FileCheck}    label="CPG Aligned"      value={<>{cpgPct}<span className="text-lg font-medium ml-0.5 opacity-70">%</span></>}           sub={`${metrics.cpgAligned.count} of ${metrics.cpgAligned.total} plans`}  color="violet"  isDark={isDark} />
          <MetricCard icon={UserCheck}    label="Referrals"        value={metrics.referrals.total}        sub={`${metrics.referrals.emergency} emergency · ${metrics.referrals.urgent} urgent`}     color="amber"   isDark={isDark} />
          <MetricCard icon={ShieldAlert}  label="Safety Flags"     value={metrics.safetyFlags.total}      sub={`${metrics.safetyFlags.critical} critical · ${metrics.safetyFlags.major} major`}      color={metrics.safetyFlags.critical > 0 ? 'red' : 'emerald'} isDark={isDark} />
          <MetricCard icon={Activity}     label="Avg CPG Cites"    value={metrics.consults30d > 0 ? (Math.round((metrics.cpgAligned.count / metrics.consults30d) * 10) / 10).toFixed(1) : '—'}  sub="citations per consult"  color="teal" isDark={isDark} />
        </div>
      </Card>

      {/* ── Row 2: Safety Flags + Referral Breakdown ───────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Safety Flags */}
        <div>
          <div className="flex items-baseline justify-between mb-3">
            <p className={`text-[10px] font-semibold uppercase tracking-widest ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Critical &amp; Major Safety Flags
            </p>
            {flagGroups.length > 0 && (
              <span className={`text-[10px] ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                {flagGroups.length} patterns · {safetyFlagList.length} flags
              </span>
            )}
          </div>
          <Card className="overflow-hidden" variant={isDark ? 'dark' : 'light'}>
            {flagGroups.length === 0 ? (
              <div className={`p-6 text-center text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                No critical or major flags in this period
              </div>
            ) : (
              <div>
                {flagGroups.slice(0, 8).map((g) => {
                  const open = expandedFlag === g.key;
                  return (
                    <div key={g.key} className={`border-b last:border-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                      <button
                        onClick={() => setExpandedFlag(open ? null : g.key)}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors
                          ${isDark ? 'hover:bg-white/5' : 'hover:bg-slate-50'}`}
                      >
                        <SeverityBadge severity={g.severity} isDark={isDark} />
                        <span className={`text-sm font-medium truncate flex-1 min-w-0 ${isDark ? 'text-white' : 'text-slate-800'}`}>
                          {g.title}
                        </span>
                        {g.instances.length > 1 && (
                          <span className={`text-[10px] ds-numeric font-semibold px-1.5 py-0.5 rounded-full shrink-0
                            ${isDark ? 'bg-red-500/15 text-red-400' : 'bg-red-50 text-red-600'}`}>
                            ×{g.instances.length}
                          </span>
                        )}
                        <span className={`text-[10px] shrink-0 max-w-[110px] truncate ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                          {g.patients[0]}{g.patients.length > 1 ? ` +${g.patients.length - 1}` : ''}
                        </span>
                        <ChevronDown
                          className={`w-3.5 h-3.5 shrink-0 transition-transform ${open ? 'rotate-180' : ''} ${isDark ? 'text-slate-500' : 'text-slate-400'}`}
                          strokeWidth={2}
                        />
                      </button>
                      {open && (
                        <div className={`px-4 pb-3 space-y-2 ${isDark ? 'bg-white/[0.02]' : 'bg-slate-50/60'}`}>
                          {g.instances.map((f, i) => (
                            <div key={i} className={`pt-2 ${i > 0 ? `border-t ${isDark ? 'border-white/5' : 'border-slate-100'}` : ''}`}>
                              <p className={`text-[10px] font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                                {f.patient} · {new Date(f.date).toLocaleDateString('en-MY', { day: '2-digit', month: 'short' })}
                              </p>
                              {f.detail && <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{f.detail}</p>}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
                {flagGroups.length > 8 && (
                  <div className={`px-4 py-2 text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    +{flagGroups.length - 8} more patterns — review full log below
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

            {/* Top specialties — click a row to filter the consultation log */}
            {referralBreakdown.length === 0 ? (
              <p className={`text-sm text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No referrals in this period</p>
            ) : (
              <div className="space-y-1.5">
                {referralBreakdown.map(r => {
                  const active = specialtyFilter === r.specialty;
                  return (
                    <button
                      key={r.specialty}
                      onClick={() => { setSpecialtyFilter(active ? null : r.specialty); setLogFilter(active ? 'completed' : 'referred'); }}
                      className={`w-full text-left px-2 py-1.5 -mx-2 rounded-lg transition-colors
                        ${active
                          ? 'bg-[var(--accent-primary)]/10 ring-1 ring-[var(--accent-primary)]/25'
                          : isDark ? 'hover:bg-white/5' : 'hover:bg-slate-50'}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-sm font-medium ${active ? 'text-[var(--accent-primary)]' : isDark ? 'text-white' : 'text-slate-800'}`}>{r.specialty}</span>
                        <div className="flex items-center gap-2">
                          {r.emergency > 0 && <span className="text-[10px] text-red-500 font-semibold">{r.emergency}🔴</span>}
                          {r.urgent    > 0 && <span className={`text-[10px] font-semibold ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>{r.urgent}⚠</span>}
                          <span className={`text-xs ds-numeric ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{r.count}</span>
                        </div>
                      </div>
                      <ProgressBar
                        value={r.count}
                        max={referralBreakdown[0].count}
                        color={r.emergency > 0 ? 'red' : r.urgent > 0 ? 'amber' : 'teal'}
                        isDark={isDark}
                      />
                    </button>
                  );
                })}
                <p className={`text-[10px] pt-1.5 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                  Click a specialty to see its consultations in the log below
                </p>
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* ── Row 3: Top Diagnoses + CPG Sections ────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Top Diagnoses (AI-assisted, {days} days)
          </p>
          <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
            <div className="space-y-1.5">
              {topDiagnoses.length === 0
                ? <p className={`text-sm text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No diagnosis data</p>
                : topDiagnoses.map((dx, i) => {
                const active = searchTerm === dx.name;
                return (
                  <button
                    key={dx.name}
                    onClick={() => setSearchTerm(active ? '' : dx.name)}
                    className={`w-full text-left px-2 py-1.5 -mx-2 rounded-lg transition-colors
                      ${active
                        ? 'bg-[var(--accent-primary)]/10 ring-1 ring-[var(--accent-primary)]/25'
                        : isDark ? 'hover:bg-white/5' : 'hover:bg-slate-50'}`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className={`text-sm font-medium truncate ${active ? 'text-[var(--accent-primary)]' : isDark ? 'text-white' : 'text-slate-800'}`}>{dx.name}</span>
                      <span className={`text-xs ds-numeric shrink-0 ml-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{dx.count} consults · {dx.pct}%</span>
                    </div>
                    <ProgressBar value={dx.pct} color={['teal', 'violet', 'sky', 'amber', 'primary'][i % 5]} isDark={isDark} />
                  </button>
                );
              })}
              {topDiagnoses.length > 0 && (
                <p className={`text-[10px] pt-1.5 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                  Click a diagnosis to see its consultations in the log below
                </p>
              )}
            </div>
          </Card>
        </div>

        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Guidelines Referenced
          </p>
          <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
            <div className="space-y-4">
              {cpgUsage.length === 0
                ? <p className={`text-sm text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No CPG data</p>
                : cpgUsage.map(d => (
                <div key={d.doc} className={`pb-3 border-b last:border-0 last:pb-0 ${isDark ? 'border-white/5' : 'border-slate-100'}`}>
                  <div className="flex items-center justify-between gap-3 mb-1.5">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <BookOpen className={`w-3.5 h-3.5 flex-shrink-0 ${isDark ? 'text-sky-400' : 'text-sky-600'}`} strokeWidth={1.5} />
                      <span className={`text-sm font-medium truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>{d.doc}</span>
                    </div>
                    <span className={`text-xs ds-numeric shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      {d.citations} cites · {d.consults} consult{d.consults !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <ProgressBar value={d.citations} max={cpgUsage[0].citations} color="sky" isDark={isDark} />
                  {d.topSections.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1 mt-1.5">
                      {d.topSections.map(s => (
                        <span key={s.sec} className={`text-[10px] ds-numeric px-1.5 py-0.5 rounded ${isDark ? 'bg-sky-500/10 text-sky-400' : 'bg-sky-50 text-sky-700'}`}>
                          §{s.sec}{s.count > 1 ? ` ×${s.count}` : ''}
                        </span>
                      ))}
                      {d.moreSections > 0 && (
                        <span className={`text-[10px] ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>+{d.moreSections} more sections</span>
                      )}
                    </div>
                  )}
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
              {specialtyFilter && (
                <button
                  onClick={() => { setSpecialtyFilter(null); setLogFilter('completed'); }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
                    bg-[var(--accent-primary)]/15 ${accent.text} border-[var(--accent-primary)]/25`}
                >
                  {specialtyFilter} ✕
                </button>
              )}
              {[
                { key: 'completed', label: 'Completed' },
                { key: 'all',      label: incompleteCount > 0 ? `All (+${incompleteCount} incomplete)` : 'All' },
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
                    <tr key={c.id} className={`border-b last:border-0 transition-colors ${c.incomplete ? 'opacity-50' : ''} ${isDark ? 'border-white/5 hover:bg-white/5' : 'border-slate-100 hover:bg-slate-50'}`}>
                      <td className={`px-4 py-3 ds-numeric whitespace-nowrap text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {new Date(c.date).toLocaleDateString('en-MY', { day: '2-digit', month: 'short' })}
                        {' '}
                        <span className="opacity-60">{new Date(c.date).toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit' })}</span>
                      </td>
                      <td className={`px-4 py-3 font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{c.patient}</td>
                      <td className={`px-4 py-3 max-w-[180px] truncate ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{c.complaint}</td>
                      <td className={`px-4 py-3 font-medium max-w-[200px] truncate ${isDark ? 'text-white' : 'text-slate-800'}`}>
                        {c.incomplete
                          ? <span className={`italic font-normal ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Incomplete — no diagnosis saved</span>
                          : c.ddx}
                      </td>
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
