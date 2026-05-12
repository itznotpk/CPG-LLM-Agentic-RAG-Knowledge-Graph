import React from 'react';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';
import { AlertCircle, Activity } from 'lucide-react';

export function PatientBanner() {
  const { state } = useApp();
  const { isDark } = useTheme();
  const { patient, mpisData } = state;

  if (!patient || !patient.name) return null;

  // Process allergies into an array
  let allergiesList = [];
  if (mpisData?.allergies) {
    if (Array.isArray(mpisData.allergies)) {
      allergiesList = mpisData.allergies;
    } else if (typeof mpisData.allergies === 'string' && mpisData.allergies.toLowerCase() !== 'none known') {
      allergiesList = mpisData.allergies.split(',').map(s => s.trim()).filter(Boolean);
    }
  }

  const getRiskBadge = (level) => {
    const config = {
      low: { bg: 'bg-emerald-500/20', text: 'text-emerald-500' },
      moderate: { bg: 'bg-amber-500/20', text: 'text-amber-500' },
      high: { bg: 'bg-orange-500/20', text: 'text-orange-500' },
      critical: { bg: 'bg-red-500/20', text: 'text-red-600 font-bold' }
    };
    const cfg = config[level?.toLowerCase()] || config['low'];
    const displayLevel = level || 'Low';
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${cfg.bg} ${cfg.text}`}>
        {displayLevel.charAt(0).toUpperCase() + displayLevel.slice(1)} Risk
      </span>
    );
  };

  return (
    <div className={`mb-6 p-4 rounded-xl flex flex-wrap items-center justify-between gap-4 border ${isDark ? 'bg-slate-800/80 border-white/10' : 'bg-white/80 border-slate-200'} shadow-sm backdrop-blur-md`}>
      <div className="flex items-center gap-4 flex-wrap">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold text-sm shadow-sm`}>
          {patient.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()}
        </div>
        
        <div>
          <h2 className={`text-lg font-bold leading-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
            {patient.name}
          </h2>
          <div className={`flex items-center gap-2 text-sm mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            <span className="ds-mono">{patient.nsn}</span>
            <span>•</span>
            <span className="ds-numeric">{patient.age || '--'} yrs</span>
            <span>•</span>
            <span>{patient.gender || '--'}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        {patient.riskLevel && (
          <div className="flex items-center gap-2">
            <Activity className={`w-4 h-4 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} strokeWidth={1.5} />
            {getRiskBadge(patient.riskLevel)}
          </div>
        )}

        {allergiesList.length > 0 && (
          <div className="flex items-center gap-2 border-l pl-4 border-slate-200 dark:border-white/10">
            <AlertCircle className="w-4 h-4 text-red-500" strokeWidth={1.5} />
            <div className="flex flex-wrap gap-1.5">
              {allergiesList.map((allergy, idx) => (
                <span key={idx} className="bg-red-100 text-red-700 border border-red-300 rounded-full px-2.5 py-0.5 text-xs font-semibold shadow-sm">
                  {allergy}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {allergiesList.length === 0 && (
          <div className="flex items-center gap-2 border-l pl-4 border-slate-200 dark:border-white/10">
            <span className={`text-xs px-2.5 py-0.5 rounded-full border ${isDark ? 'bg-white/5 border-white/10 text-slate-400' : 'bg-slate-50 border-slate-200 text-slate-500'}`}>
              No Known Allergies
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
