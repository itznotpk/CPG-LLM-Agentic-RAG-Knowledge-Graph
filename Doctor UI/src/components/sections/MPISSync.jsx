import React, { useState } from 'react';
import { RefreshCw, Database, CheckCircle, AlertTriangle, Pill, Heart } from 'lucide-react';
import { GlassCard, Button, Badge } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';

export function MPISSync() {
  const { state, syncMPIS } = useApp();
  const { isDark } = useTheme();
  const { mpisData, mpisSynced } = state;
  const [isSyncing, setIsSyncing] = useState(false);

  const handleSync = async () => {
    setIsSyncing(true);
    await syncMPIS();
    setIsSyncing(false);
  };

  return (
    <GlassCard className="p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
            <Database className="w-5 h-5 text-[var(--accent-primary)]" />
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>MPIS Integration</h3>
            <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Medical Patient Information System</p>
          </div>
        </div>
        <Button
          variant={mpisSynced ? 'success' : 'primary'}
          size="sm"
          icon={mpisSynced ? CheckCircle : RefreshCw}
          loading={isSyncing}
          onClick={handleSync}
          disabled={mpisSynced}
          className="whitespace-nowrap"
        >
          {mpisSynced ? 'Synced' : 'Sync MPIS'}
        </Button>
      </div>

      {mpisSynced ? (
        <div className="space-y-4 animate-fadeIn">
          {/* Patient Info */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/50'}`}>
              <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Race</span>
              <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{mpisData.race}</p>
            </div>
            <div className={`p-3 rounded-xl ${isDark ? 'bg-white/10' : 'bg-white/50'}`}>
              <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Allergies</span>
              <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>{mpisData.allergies}</p>
            </div>
          </div>

          {/* Comorbidities */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Heart className="w-4 h-4 text-[var(--accent-primary)]" />
              <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Comorbidities</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {mpisData.comorbidities.map((condition, idx) => (
                <Badge key={idx} variant="warning" size="md">
                  {condition}
                </Badge>
              ))}
            </div>
          </div>

          {/* Current Medications */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Pill className="w-4 h-4 text-[var(--accent-primary)]" />
              <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>Current Medications</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {mpisData.currentMeds.map((med, idx) => (
                <div
                  key={idx}
                  className={`flex items-center justify-between p-2.5 rounded-lg ${isDark ? 'bg-white/10' : 'bg-white/50'}`}
                >
                  <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{med.name}</span>
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {med.dose} {med.frequency}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className={`p-4 rounded-full mb-3 ${isDark ? 'bg-amber-500/20' : 'bg-amber-100/70'}`}>
            <AlertTriangle className={`w-8 h-8 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
          </div>
          <p className={`mb-1 ${isDark ? 'text-white' : 'text-slate-800'}`}>No MPIS data loaded</p>
        </div>
      )}
    </GlassCard>
  );
}
