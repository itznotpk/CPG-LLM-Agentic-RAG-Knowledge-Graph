import { useCallback, useEffect, useState } from 'react';
import { BellRing } from 'lucide-react';
import { GlassCard, Badge } from '../shared';
import { supabase, getPatientAlerts, ackPatientAlert } from '../../lib/supabase';

const maskNric = (nric) => (nric ? `•••• ${String(nric).slice(-4)}` : 'unknown');

/** Realtime list of open follow-up escalations from the Triage agent. */
export default function PatientAlertsPanel({ isDark }) {
  const [alerts, setAlerts] = useState([]);

  const load = useCallback(async () => {
    try { setAlerts(await getPatientAlerts({ openOnly: true })); }
    catch { /* panel is non-critical — swallow */ }
  }, []);

  useEffect(() => {
    load();
    const ch = supabase
      .channel('patient-alerts')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'patient_alerts' }, load)
      .subscribe();
    return () => supabase.removeChannel(ch);
  }, [load]);

  const ack = async (id) => {
    try {
      await ackPatientAlert(id, 'clinician');
    } catch {
      /* non-critical surface — swallow, the realtime refresh will re-sync */
    }
    load();
  };

  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <BellRing size={18} className="text-red-500" />
        <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
          Patient Alerts {alerts.length > 0 && <span className="text-red-500">({alerts.length})</span>}
        </h3>
      </div>
      {alerts.length === 0 ? (
        <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>No open alerts from follow-up.</p>
      ) : (
        <ul className="space-y-3">
          {alerts.map((a) => (
            <li key={a.id} className={`rounded-lg border p-3 ${isDark ? 'border-red-900/50 bg-red-950/20' : 'border-red-200 bg-red-50'}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant={a.severity === 'critical' ? 'danger' : 'warning'}>{a.severity}</Badge>
                  <span className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                    Patient {maskNric(a.patient_nric)}
                  </span>
                </div>
                <button
                  onClick={() => ack(a.id)}
                  className="text-xs font-medium px-2 py-1 rounded bg-teal-600 text-white hover:bg-teal-700"
                >
                  Acknowledge
                </button>
              </div>
              <p className={`mt-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>"{a.patient_reply}"</p>
              <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                {a.summary} · {new Date(a.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}
