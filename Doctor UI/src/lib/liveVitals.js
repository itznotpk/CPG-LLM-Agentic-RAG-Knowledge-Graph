import { supabase } from './supabase';

/**
 * Subscribe to real-time inserts on the live_vitals table.
 * The callback receives each new row as it arrives from the rPPG bridge.
 * @param {(row: object) => void} onVitals
 * @returns {() => void} call to unsubscribe
 */
export function subscribeLiveVitals(onVitals) {
  const channel = supabase
    .channel('live_vitals_feed')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'live_vitals' },
      (payload) => onVitals(payload.new)
    )
    .subscribe();

  return () => supabase.removeChannel(channel);
}

/**
 * One-shot fetch of the most recent live_vitals row.
 * Used on mount to show last known values before the stream arrives.
 * @returns {Promise<object|null>}
 */
export async function getLatestLiveVitals() {
  const { data, error } = await supabase
    .from('live_vitals')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    console.error('liveVitals fetch error:', error);
    return null;
  }
  return data;
}
