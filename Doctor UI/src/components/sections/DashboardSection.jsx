import React, { useState } from 'react';
import { 
  BarChart3, 
  TrendingUp, 
  Clock, 
  CheckCircle2, 
  XCircle,
  Users,
  FileText,
  Brain,
  Activity,
  Calendar,
  ChevronDown,
  RefreshCw
} from 'lucide-react';
import { GlassCard as Card, Badge, Button } from '../shared';
import { useTheme } from '../../context/ThemeContext';

// Mock Analytics Data (will be replaced with real backend data)
const mockAnalytics = {
  totalSessions: 1247,
  thisWeek: 89,
  avgTimePerSession: '4.2 min',
  timeSaved: '156 hrs',
  acceptanceRate: 87,
  regenerateRate: 23,
  topDiagnoses: [
    { name: 'Type 2 Diabetes', count: 234, percentage: 18.8 },
    { name: 'Essential Hypertension', count: 198, percentage: 15.9 },
    { name: 'COPD', count: 156, percentage: 12.5 },
    { name: 'Heart Failure', count: 134, percentage: 10.7 },
    { name: 'Chronic Kidney Disease', count: 112, percentage: 9.0 }
  ],
  weeklyUsage: [
    { day: 'Mon', sessions: 42 },
    { day: 'Tue', sessions: 38 },
    { day: 'Wed', sessions: 45 },
    { day: 'Thu', sessions: 51 },
    { day: 'Fri', sessions: 48 },
    { day: 'Sat', sessions: 12 },
    { day: 'Sun', sessions: 8 }
  ],
  recentActivity: [
    { type: 'diagnosis', patient: 'J.S.', diagnosis: 'Type 2 Diabetes', time: '5 min ago', accepted: true },
    { type: 'diagnosis', patient: 'M.K.', diagnosis: 'Hypertension', time: '12 min ago', accepted: true },
    { type: 'regenerate', patient: 'A.B.', diagnosis: 'COPD', time: '25 min ago', reason: 'More conservative' },
    { type: 'diagnosis', patient: 'R.T.', diagnosis: 'Heart Failure', time: '1 hr ago', accepted: false },
    { type: 'diagnosis', patient: 'L.M.', diagnosis: 'CKD Stage 3', time: '2 hrs ago', accepted: true }
  ]
};

// Stat Card Component
function StatCard({ icon: Icon, label, value, subValue, trend, color = 'primary' }) {
  const { isDark } = useTheme();
  const colorClasses = {
    primary: isDark ? 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)]' : 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]',
    green: isDark ? 'bg-green-500/20 text-green-400' : 'bg-green-100 text-green-600',
    amber: isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-600',
    blue: isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600',
    purple: isDark ? 'bg-purple-500/20 text-purple-400' : 'bg-purple-100 text-purple-600'
  };

  return (
    <div className={`backdrop-blur-sm rounded-xl border p-4 hover:shadow-md transition-shadow ${isDark ? 'bg-white/5 border-white/10' : 'bg-white/60 border-slate-200'}`}>
      <div className="flex items-start justify-between">
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-xs ${trend > 0 ? 'text-green-500' : 'text-red-500'}`}>
            <TrendingUp className={`w-3 h-3 ${trend < 0 ? 'rotate-180' : ''}`} />
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div className="mt-3">
        <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>{value}</p>
        <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{label}</p>
        {subValue && <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{subValue}</p>}
      </div>
    </div>
  );
}

// Simple Bar Chart Component
function SimpleBarChart({ data, maxValue }) {
  const { isDark } = useTheme();
  const max = maxValue || Math.max(...data.map(d => d.sessions));
  
  return (
    <div className="flex items-end justify-between gap-2 h-32 px-2">
      {data.map((item, index) => (
        <div key={index} className="flex flex-col items-center flex-1">
          <div 
            className="w-full bg-[var(--accent-primary)] rounded-t-sm hover:bg-[var(--accent-primary-hover)] transition-colors"
            style={{ height: `${(item.sessions / max) * 100}%`, minHeight: '4px' }}
            title={`${item.sessions} sessions`}
          />
          <span className={`text-xs mt-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{item.day}</span>
        </div>
      ))}
    </div>
  );
}

// Horizontal Progress Bar
function ProgressBar({ value, max = 100, color = 'primary' }) {
  const { isDark } = useTheme();
  const percentage = (value / max) * 100;
  const colorClasses = {
    primary: 'bg-[var(--accent-primary)]',
    green: 'bg-green-500',
    amber: 'bg-amber-500',
    blue: 'bg-blue-500'
  };

  return (
    <div className={`w-full rounded-full h-2 overflow-hidden ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
      <div 
        className={`h-full rounded-full transition-all duration-500 ${colorClasses[color]}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}

// Activity Item Component
function ActivityItem({ activity }) {
  const { isDark } = useTheme();
  const getIcon = () => {
    if (activity.type === 'regenerate') {
      return <RefreshCw className="w-4 h-4 text-amber-500" />;
    }
    return activity.accepted 
      ? <CheckCircle2 className="w-4 h-4 text-green-500" />
      : <XCircle className="w-4 h-4 text-red-500" />;
  };

  return (
    <div className={`flex items-center gap-3 py-2 border-b last:border-0 ${isDark ? 'border-white/10' : 'border-slate-100'}`}>
      {getIcon()}
      <div className="flex-1">
        <p className={`text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
          <span className="font-medium">{activity.patient}</span>
          {activity.type === 'regenerate' ? (
            <span className={isDark ? 'text-slate-400' : 'text-slate-500'}> - Regenerated ({activity.reason})</span>
          ) : (
            <span className={isDark ? 'text-slate-400' : 'text-slate-500'}> - {activity.diagnosis}</span>
          )}
        </p>
        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>{activity.time}</p>
      </div>
      {activity.type !== 'regenerate' && (
        <Badge variant={activity.accepted ? 'success' : 'danger'}>
          {activity.accepted ? 'Accepted' : 'Modified'}
        </Badge>
      )}
    </div>
  );
}

// Main Dashboard Component
export function DashboardSection() {
  const { isDark } = useTheme();
  const [timeRange, setTimeRange] = useState('week');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = () => {
    setIsRefreshing(true);
    // Simulate API call
    setTimeout(() => setIsRefreshing(false), 1000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-bold flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>
            <BarChart3 className="w-7 h-7 text-[var(--accent-primary)]" />
            Analytics Dashboard
          </h2>
          <p className={`mt-1 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Monitor CPG LLM usage and performance metrics</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className={`appearance-none border rounded-lg px-4 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 ${
                isDark 
                  ? 'bg-white/10 border-white/20 text-white' 
                  : 'bg-white/80 border-slate-300 text-slate-800'
              }`}
            >
              <option value="today">Today</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
              <option value="year">This Year</option>
            </select>
            <ChevronDown className={`absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon={RefreshCw}
            onClick={handleRefresh}
            className={isRefreshing ? 'animate-spin' : ''}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={FileText}
          label="Total Sessions"
          value={mockAnalytics.totalSessions.toLocaleString()}
          subValue={`+${mockAnalytics.thisWeek} this week`}
          trend={12}
          color="primary"
        />
        <StatCard
          icon={Clock}
          label="Time Saved"
          value={mockAnalytics.timeSaved}
          subValue={`Avg. ${mockAnalytics.avgTimePerSession}/session`}
          trend={8}
          color="green"
        />
        <StatCard
          icon={CheckCircle2}
          label="Acceptance Rate"
          value={`${mockAnalytics.acceptanceRate}%`}
          subValue="Care plan recommendations"
          trend={3}
          color="blue"
        />
        <StatCard
          icon={RefreshCw}
          label="Regenerate Rate"
          value={`${mockAnalytics.regenerateRate}%`}
          subValue="Requests for alternatives"
          trend={-5}
          color="amber"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly Usage Chart */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className={`font-semibold flex items-center gap-2 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
              <Activity className="w-5 h-5 text-[var(--accent-primary)]" />
              Weekly Usage
            </h3>
            <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Sessions per day</span>
          </div>
          <SimpleBarChart data={mockAnalytics.weeklyUsage} />
        </Card>

        {/* Top Diagnoses */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className={`font-semibold flex items-center gap-2 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
              <Brain className="w-5 h-5 text-[var(--accent-primary)]" />
              Top Diagnoses
            </h3>
            <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>By frequency</span>
          </div>
          <div className="space-y-3">
            {mockAnalytics.topDiagnoses.map((diagnosis, index) => (
              <div key={index} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className={isDark ? 'text-slate-200' : 'text-slate-700'}>{diagnosis.name}</span>
                  <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>{diagnosis.count} ({diagnosis.percentage}%)</span>
                </div>
                <ProgressBar 
                  value={diagnosis.percentage} 
                  max={20} 
                  color={index === 0 ? 'primary' : index === 1 ? 'blue' : 'green'} 
                />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className={`font-semibold flex items-center gap-2 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
            <Calendar className="w-5 h-5 text-[var(--accent-primary)]" />
            Recent Activity
          </h3>
          <button className={`text-xs ${isDark ? 'text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)]' : 'text-[var(--accent-primary)] hover:opacity-80'}`}>
            View All
          </button>
        </div>
        <div className={`divide-y ${isDark ? 'divide-white/10' : 'divide-slate-100'}`}>
          {mockAnalytics.recentActivity.map((activity, index) => (
            <ActivityItem key={index} activity={activity} />
          ))}
        </div>
      </Card>

      {/* AI Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-center">
            <div className={`inline-flex items-center justify-center w-12 h-12 rounded-full mb-3 ${isDark ? 'bg-green-500/20' : 'bg-green-100'}`}>
              <Brain className="w-6 h-6 text-green-600" />
            </div>
            <p className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>94%</p>
            <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>AI Confidence</p>
            <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Average across diagnoses</p>
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-center">
            <div className={`inline-flex items-center justify-center w-12 h-12 rounded-full mb-3 ${isDark ? 'bg-blue-500/20' : 'bg-blue-100'}`}>
              <Users className="w-6 h-6 text-blue-600" />
            </div>
            <p className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>23</p>
            <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Active Providers</p>
            <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Using CPG LLM today</p>
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-center">
            <div className={`inline-flex items-center justify-center w-12 h-12 rounded-full mb-3 ${isDark ? 'bg-purple-500/20' : 'bg-purple-100'}`}>
              <TrendingUp className="w-6 h-6 text-purple-600" />
            </div>
            <p className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>+18%</p>
            <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Efficiency Gain</p>
            <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>vs. previous month</p>
          </div>
        </Card>
      </div>

      {/* Note about Backend Integration */}
      <div className={`border rounded-lg p-4 ${isDark ? 'bg-amber-500/10 border-amber-500/30' : 'bg-amber-50 border-amber-200'}`}>
        <div className="flex items-start gap-3">
          <div className={`p-1 rounded ${isDark ? 'bg-amber-500/20' : 'bg-amber-100'}`}>
            <Activity className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <p className={`text-sm font-medium ${isDark ? 'text-amber-400' : 'text-amber-800'}`}>Backend Integration Pending</p>
            <p className={`text-xs mt-1 ${isDark ? 'text-amber-500' : 'text-amber-700'}`}>
              This dashboard currently displays mock data. Real analytics will be available once the backend API is connected.
              The UI is ready to consume real data from your analytics endpoints.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DashboardSection;
