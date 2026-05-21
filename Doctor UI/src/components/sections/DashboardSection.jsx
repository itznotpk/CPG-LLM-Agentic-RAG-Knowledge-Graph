import React, { useState, useMemo, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  Clock,
  CheckCircle2,
  XCircle,
  FileText,
  Brain,
  Activity,
  ChevronDown,
  RefreshCw,
  BookOpen,
  Stethoscope,
  AlertTriangle,
  Timer,
  FileCheck,
  UserCheck,
  Search,
  Filter,
  Terminal,
  RefreshCw as RefreshIcon,
} from 'lucide-react';
import { GlassCard as Card, Badge, Button } from '../shared';
import { useTheme } from '../../context/ThemeContext';
import { supabase } from '../../lib/supabase';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricCard({ icon: Icon, label, value, sub, color, isDark }) {
  const colorMap = {
    teal:   { bg: isDark ? 'bg-teal-500/15'   : 'bg-teal-50',   text: isDark ? 'text-teal-400'   : 'text-teal-600'   },
    violet: { bg: isDark ? 'bg-violet-500/15'  : 'bg-violet-50', text: isDark ? 'text-violet-400' : 'text-violet-600' },
    sky:    { bg: isDark ? 'bg-sky-500/15'     : 'bg-sky-50',    text: isDark ? 'text-sky-400'    : 'text-sky-600'    },
    amber:  { bg: isDark ? 'bg-amber-500/15'   : 'bg-amber-50',  text: isDark ? 'text-amber-400'  : 'text-amber-600'  },
    emerald:{ bg: isDark ? 'bg-emerald-500/15' : 'bg-emerald-50',text: isDark ? 'text-emerald-400': 'text-emerald-600' },
    blue:   { bg: isDark ? 'bg-blue-500/15'    : 'bg-blue-50',   text: isDark ? 'text-blue-400'   : 'text-blue-600'   },
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
  }[color] || 'bg-[var(--accent-primary)]';

  return (
    <div className={`w-full rounded-full h-1.5 overflow-hidden ${isDark ? 'bg-white/10' : 'bg-slate-200'}`}>
      <div className={`h-full rounded-full transition-all duration-500 ${colorClass}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function DashboardSection() {
  const { isDark, accent } = useTheme();
  const [logFilter, setLogFilter] = useState('all'); // all, accepted, modified
  const [searchTerm, setSearchTerm] = useState('');
  
  const [loading, setLoading] = useState(true);
  const [summaryMetrics, setSummaryMetrics] = useState({
    timeSavedTotal: 0,
    cpgAligned: { count: 0, total: 1 },
    citationsIssued: 0,
    referrals: { count: 0, cpgJustified: 0 },
    consultationsToday: 0,
    avgTimePerConsult: 4.0,
    acceptanceRate: 92, // Still mocked (no field in DB yet)
  });
  const [consultationLog, setConsultationLog] = useState([]);
  const [topDiagnoses, setTopDiagnoses] = useState([]);
  const [cpgSectionsUsed, setCpgSectionsUsed] = useState([]);
  
  // RAG Debugger State
  const [systemLogs, setSystemLogs] = useState([]);
  const [isFetchingLogs, setIsFetchingLogs] = useState(false);
  
  const fetchLogs = async () => {
    try {
      setIsFetchingLogs(true);
      const BASE_URL = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';
      const res = await fetch(`${BASE_URL}/system/logs?lines=100`);
      if (res.ok) {
        const data = await res.json();
        setSystemLogs(data.logs || []);
      }
    } catch (err) {
      console.error('Failed to fetch backend logs', err);
    } finally {
      setIsFetchingLogs(false);
    }
  };

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        // Fetch consultations from the last 30 days
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        
        const { data: consultsData, error: consultsError } = await supabase
          .from('consultations')
          .select('*')
          .gte('created_at', thirtyDaysAgo.toISOString())
          .order('created_at', { ascending: false });
          
        if (consultsError) throw consultsError;
        
        // Fetch all patients to map NRIC -> Name
        const { data: patientsData, error: patientsError } = await supabase
          .from('patients')
          .select('nric, full_name');
          
        if (patientsError) throw patientsError;
        
        const patientMap = {};
        patientsData.forEach(p => { patientMap[p.nric] = p.full_name; });
        
        // --- Process Metrics ---
        let todayCount = 0;
        let totalTimeSaved = 0;
        let cpgAlignedCount = 0;
        let citationsTotal = 0;
        let referralsCount = 0;
        let referralsJustified = 0;
        
        const todayStr = new Date().toISOString().split('T')[0];
        
        const dxMap = {};
        const cpgMap = {};
        const newLogs = [];
        
        (consultsData || []).forEach(c => {
          const isToday = c.created_at.startsWith(todayStr);
          if (isToday) todayCount++;
          
          // Mock time saved: ~4 mins per consult (since this isn't recorded in DB)
          const timeSaved = 4;
          if (isToday) totalTimeSaved += timeSaved;
          
          // Parse CPG References
          let cpgCount = 0;
          let cpgRefs = [];
          try {
             cpgRefs = typeof c.cpg_references === 'string' ? JSON.parse(c.cpg_references) : (c.cpg_references || []);
          } catch(e) {}
          
          if (Array.isArray(cpgRefs) && cpgRefs.length > 0) {
            cpgAlignedCount++;
            cpgCount = cpgRefs.length;
            citationsTotal += cpgCount;
            
            cpgRefs.forEach(ref => {
              const section = ref.section || ref.title || ref.name || 'General Guideline';
              cpgMap[section] = (cpgMap[section] || 0) + 1;
            });
          }
          
          // Parse Referrals
          let refs = [];
          try {
             refs = typeof c.referrals === 'string' ? JSON.parse(c.referrals) : (c.referrals || []);
          } catch(e) {}
          
          if (Array.isArray(refs) && refs.length > 0) {
             referralsCount++;
             if (cpgCount > 0) referralsJustified++;
          }
          
          // Parse Diagnoses
          let dxs = [];
          try {
            dxs = typeof c.diagnoses === 'string' ? JSON.parse(c.diagnoses) : (c.diagnoses || []);
          } catch(e) {}
          
          let ddxStr = 'Pending';
          if (Array.isArray(dxs) && dxs.length > 0) {
            const firstDx = typeof dxs[0] === 'string' ? dxs[0] : (dxs[0].condition || dxs[0].name || dxs[0].diagnosis || 'Unknown');
            ddxStr = firstDx;
            dxs.forEach(dx => {
              const name = typeof dx === 'string' ? dx : (dx.condition || dx.name || dx.diagnosis || 'Unknown');
              if (name && name !== 'Unknown') {
                dxMap[name] = (dxMap[name] || 0) + 1;
              }
            });
          }
          
          // Extract text cleanly from clinical notes
          let complaintText = 'No notes';
          if (c.clinical_notes) {
            complaintText = c.clinical_notes.replace(/<[^>]*>?/gm, '').substring(0, 50);
            if (c.clinical_notes.length > 50) complaintText += '...';
          }
          
          newLogs.push({
            id: c.id,
            patient: patientMap[c.patient_nric] || 'Unknown Patient',
            complaint: complaintText,
            ddx: ddxStr,
            cpgCitations: cpgCount,
            outcome: 'accepted', // Mocked as we don't have tracking for this yet
            timeSaved: timeSaved,
            date: new Date(c.created_at).toLocaleString('en-MY', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
          });
        });
        
        const totalConsults = Math.max(consultsData.length, 1);
        
        // Sort and select top Diagnoses
        const topDxList = Object.entries(dxMap)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([name, count]) => ({
            name,
            count,
            pct: Math.round((count / totalConsults) * 100)
          }));
          
        // Sort and select top CPG sections
        const topCpgList = Object.entries(cpgMap)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([section, hits]) => ({
            section,
            hits
          }));
          
        setSummaryMetrics({
          timeSavedTotal: totalTimeSaved,
          cpgAligned: { count: cpgAlignedCount, total: totalConsults },
          citationsIssued: citationsTotal,
          referrals: { count: referralsCount, cpgJustified: referralsJustified },
          consultationsToday: todayCount,
          avgTimePerConsult: 4.0,
          acceptanceRate: 92, // Mocked 
        });
        
        setConsultationLog(newLogs);
        setTopDiagnoses(topDxList);
        setCpgSectionsUsed(topCpgList);
        
        // Also fetch initial logs
        fetchLogs();
        
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }
    
    fetchData();
  }, []);

  const cpgPct = Math.round((summaryMetrics.cpgAligned.count / summaryMetrics.cpgAligned.total) * 100);

  const filteredLog = useMemo(() => {
    let list = [...consultationLog];
    if (logFilter !== 'all') list = list.filter(c => c.outcome === logFilter);
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      list = list.filter(c => c.patient.toLowerCase().includes(q) || c.ddx.toLowerCase().includes(q));
    }
    return list;
  }, [logFilter, searchTerm, consultationLog]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between">
          <h1 className={`text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
            AI Assistant Performance
          </h1>
          {loading && <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'} animate-pulse`}>Syncing with database...</span>}
        </div>
        <p className={`mt-1 text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          How the Agentic RAG pipeline is supporting your consultations today
        </p>
      </div>

      {/* ── Summary Metrics (mirrors Home's 4 cards + 2 extra) ────────── */}
      <div>
        <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Today's Impact
        </p>
        <Card className="p-0 overflow-hidden" variant={isDark ? 'dark' : 'light'}>
          <div className={`grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 divide-y md:divide-y-0 md:divide-x ${isDark ? 'divide-white/10' : 'divide-slate-200'}`}>
            <MetricCard icon={Timer}     label="Time Reclaimed"   value={<>{summaryMetrics.timeSavedTotal}<span className="text-lg font-medium ml-0.5 opacity-70">min</span></>} sub={`~${summaryMetrics.avgTimePerConsult} min/consult`} color="teal"    isDark={isDark} />
            <MetricCard icon={FileCheck} label="CPG Aligned"      value={<>{cpgPct}<span className="text-lg font-medium ml-0.5 opacity-70">%</span></>} sub={`${summaryMetrics.cpgAligned.count} of ${summaryMetrics.cpgAligned.total} plans`} color="violet"  isDark={isDark} />
            <MetricCard icon={BookOpen}  label="Citations Issued"  value={summaryMetrics.citationsIssued}  sub="evidence-backed decisions"   color="sky"     isDark={isDark} />
            <MetricCard icon={UserCheck} label="Referrals"         value={summaryMetrics.referrals.count}  sub={`${summaryMetrics.referrals.cpgJustified} CPG-justified`} color="amber"   isDark={isDark} />
            <MetricCard icon={Stethoscope} label="Consultations"   value={summaryMetrics.consultationsToday} sub="completed today" color="emerald" isDark={isDark} />
            <MetricCard icon={CheckCircle2} label="Acceptance Rate" value={<>{summaryMetrics.acceptanceRate}<span className="text-lg font-medium ml-0.5 opacity-70">%</span></>} sub="AI recommendations" color="blue"    isDark={isDark} />
          </div>
        </Card>
      </div>

      {/* ── Two-column: Top Diagnoses + CPG Sections Referenced ───────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Diagnoses */}
        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Top Diagnoses (AI-assisted)
          </p>
          <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
            <div className="space-y-4">
              {topDiagnoses.map((dx, i) => (
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

        {/* CPG Sections Referenced */}
        <div>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            CPG Sections Referenced
          </p>
          <Card className="p-5" variant={isDark ? 'dark' : 'light'}>
            <div className="space-y-3">
              {cpgSectionsUsed.map((s) => (
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

      {/* ── Consultation Log ──────────────────────────────────────────── */}
      <div>
        <p className={`text-[10px] font-semibold uppercase tracking-widest mb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Consultation Log
        </p>
        <Card className="overflow-hidden" variant={isDark ? 'dark' : 'light'}>
          {/* Toolbar */}
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
                { key: 'all', label: 'All' },
                { key: 'accepted', label: 'Accepted' },
                { key: 'modified', label: 'Modified' },
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

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className={`border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                  {['Time', 'Patient', 'Chief Complaint', 'AI Diagnosis', 'CPG Cites', 'Saved', 'Outcome'].map(h => (
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
                      <td className={`px-4 py-3 ds-numeric whitespace-nowrap ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {c.date.split(' ')[1]}
                      </td>
                      <td className={`px-4 py-3 font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{c.patient}</td>
                      <td className={`px-4 py-3 max-w-[200px] truncate ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{c.complaint}</td>
                      <td className={`px-4 py-3 font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{c.ddx}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 text-xs ds-numeric ${isDark ? 'text-sky-400' : 'text-sky-600'}`}>
                          <BookOpen className="w-3 h-3" strokeWidth={2} />
                          {c.cpgCitations}
                        </span>
                      </td>
                      <td className={`px-4 py-3 ds-numeric ${isDark ? 'text-teal-400' : 'text-teal-600'}`}>
                        {c.timeSaved}m
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border
                          ${c.outcome === 'accepted'
                            ? 'bg-emerald-500/15 text-emerald-600 border-emerald-400/30'
                            : 'bg-amber-500/15 text-amber-600 border-amber-400/30'}`}>
                          {c.outcome === 'accepted' ? <CheckCircle2 className="w-3 h-3" strokeWidth={2} /> : <AlertTriangle className="w-3 h-3" strokeWidth={2} />}
                          {c.outcome === 'accepted' ? 'Accepted' : 'Modified'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* ── RAG Pipeline Debugging ───────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className={`text-[10px] font-semibold uppercase tracking-widest ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            RAG Pipeline Debugging
          </p>
          <Button 
            variant="ghost" 
            size="sm" 
            icon={RefreshIcon} 
            onClick={fetchLogs} 
            className={isFetchingLogs ? 'animate-spin' : ''}
          >
            Refresh Logs
          </Button>
        </div>
        <Card className="overflow-hidden bg-slate-950 border-slate-800" variant="dark">
          <div className="flex items-center gap-2 p-3 border-b border-white/10 bg-slate-900/50">
            <Terminal className="w-4 h-4 text-slate-400" />
            <span className="text-xs font-mono text-slate-400">agent.log — Backend Traces</span>
          </div>
          <div className="p-4 h-[400px] overflow-y-auto font-mono text-xs leading-relaxed flex flex-col gap-1.5 custom-scrollbar">
            {systemLogs.length === 0 ? (
              <div className="text-slate-500 italic">No logs available. Ensure the backend is running.</div>
            ) : (
              systemLogs.map((log, i) => {
                // Parse standard python log format: "2026-05-12 16:10:22,000 - agent.api - INFO - Message"
                const match = log.match(/^([\d-]+\s[\d:,]+)\s-\s([^\s]+)\s-\s([A-Z]+)\s-\s(.*)/);
                if (!match) return <div key={i} className="text-slate-300 break-words">{log}</div>;
                
                const [_, time, module, level, msg] = match;
                
                let levelColor = 'text-slate-400 bg-slate-800/50';
                if (level === 'INFO') levelColor = 'text-blue-400 bg-blue-900/20';
                if (level === 'ERROR') levelColor = 'text-red-400 bg-red-900/20';
                if (level === 'WARNING') levelColor = 'text-amber-400 bg-amber-900/20';
                if (level === 'DEBUG') levelColor = 'text-emerald-400 bg-emerald-900/20';

                return (
                  <div key={i} className="flex items-start gap-3 hover:bg-white/5 p-1 rounded transition-colors group">
                    <span className="text-slate-600 shrink-0 whitespace-nowrap">{time.split(',')[0]}</span>
                    <span className={`px-1.5 py-0.5 rounded-[4px] text-[10px] font-bold shrink-0 ${levelColor}`}>
                      {level}
                    </span>
                    <span className="text-slate-500 shrink-0 w-24 truncate" title={module}>[{module}]</span>
                    <span className={`break-words ${level === 'ERROR' ? 'text-red-300' : 'text-slate-300'}`}>
                      {msg}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default DashboardSection;
