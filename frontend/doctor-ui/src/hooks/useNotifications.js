import { useState, useEffect, useRef, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import { safeJson } from '../lib/helpers';

// Fully dynamic notification feed derived from live DB state.
//
// Pattern: notifications are REBUILT from queries with stable, deterministic
// ids (consult-12, flags-12, delivery-<uuid>-sent, overdue-<nric>-<date>), and
// realtime postgres_changes events simply trigger a debounced rebuild — same
// approach as DashboardSection. This makes the feed idempotent (no duplicate
// events, no fragile payload parsing) and lets read-state survive rebuilds.
//
// Sources:
//   consultations  → completed consults, CRITICAL safety flags, safety overrides
//   delivery_jobs  → care-plan email sent / failed
//   consultations.next_review → overdue follow-up reviews (current state)

const READ_KEY = 'cp_notif_read_v1';
const EVENT_WINDOW_MS = 48 * 3600 * 1000; // recent-events lookback
const MAX_NOTIFS = 30;

const loadReadIds = () => {
  try { return new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]')); }
  catch { return new Set(); }
};
const saveReadIds = (set) => {
  try { localStorage.setItem(READ_KEY, JSON.stringify([...set].slice(-200))); }
  catch { /* storage unavailable — read state just won't persist */ }
};

const timeAgo = (ts) => {
  const diff = Date.now() - new Date(ts).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return d === 1 ? 'Yesterday' : `${d}d ago`;
};

export function useNotifications() {
  const [notifications, setNotifications] = useState([]);
  const readIdsRef = useRef(loadReadIds());
  const debounceRef = useRef(null);

  const build = useCallback(async () => {
    const since = new Date(Date.now() - EVENT_WINDOW_MS).toISOString();

    const [consultsRes, deliveriesRes, reviewsRes, patientsRes] = await Promise.all([
      supabase
        .from('consultations')
        .select('id, created_at, patient_nric, consultation_number, diagnoses, safety_flags, safety_acknowledged')
        .gte('created_at', since)
        .order('created_at', { ascending: false }),
      supabase
        .from('delivery_jobs')
        .select('id, consultation_id, patient_nric, recipient, status, error, updated_at, delivered_at')
        .gte('updated_at', since)
        .order('updated_at', { ascending: false }),
      // Overdue follow-ups are current-state, not an event — look across all
      // consultations carrying a next_review, latest per patient wins.
      supabase
        .from('consultations')
        .select('patient_nric, next_review, created_at')
        .not('next_review', 'is', null)
        .order('created_at', { ascending: false }),
      supabase.from('patients').select('nric, full_name, status'),
    ]);

    const nameOf = {};
    const statusOf = {};
    (patientsRes.data || []).forEach(p => {
      nameOf[p.nric] = p.full_name || p.nric;
      statusOf[p.nric] = p.status || 'active';
    });
    const who = (nric) => nameOf[nric] || nric || 'Unknown patient';

    const list = [];

    // ── Consultation events ──
    (consultsRes.data || []).forEach(c => {
      const dx = safeJson(c.diagnoses);
      const flags = safeJson(c.safety_flags);
      const num = c.consultation_number ? ` #${c.consultation_number}` : '';

      if (dx.length > 0) {
        const first = typeof dx[0] === 'object' ? dx[0].name : dx[0];
        list.push({
          id: `consult-${c.id}`,
          type: 'success',
          title: `Consultation${num} completed`,
          message: `${who(c.patient_nric)} — ${first}${dx.length > 1 ? ` +${dx.length - 1} more` : ''}`,
          ts: c.created_at,
          nric: c.patient_nric,
          cta: 'Open patient chart',
        });
      }

      const critical = flags.filter(f => (f.severity || '').toUpperCase() === 'CRITICAL');
      if (critical.length > 0) {
        list.push({
          id: `flags-${c.id}`,
          type: 'urgent',
          title: `${critical.length} critical safety flag${critical.length > 1 ? 's' : ''}`,
          message: `${who(c.patient_nric)} — ${critical[0].title || critical[0].description || 'see safety review'}`,
          ts: c.created_at,
          nric: c.patient_nric,
          cta: 'Review safety flags',
        });
      }

      if (c.safety_acknowledged) {
        list.push({
          id: `override-${c.id}`,
          type: 'alert',
          title: 'Safety override recorded',
          message: `${who(c.patient_nric)} — blocked plan acknowledged and overridden (audit logged)`,
          ts: c.created_at,
          nric: c.patient_nric,
          cta: 'Review override audit',
        });
      }
    });

    // ── Delivery events ── (table may not exist if migration not run → data null)
    (deliveriesRes.data || []).forEach(j => {
      if (j.status === 'sent') {
        list.push({
          id: `delivery-${j.id}-sent`,
          type: 'success',
          title: 'Care plan delivered',
          message: `${who(j.patient_nric)} — emailed to ${j.recipient}`,
          ts: j.delivered_at || j.updated_at,
          nric: j.patient_nric,
          cta: 'Open patient chart',
        });
      } else if (j.status === 'failed') {
        list.push({
          id: `delivery-${j.id}-failed`,
          type: 'urgent',
          title: 'Care plan delivery failed',
          message: `${who(j.patient_nric)} — ${j.error || 'unknown error'}`,
          ts: j.updated_at,
          nric: j.patient_nric,
          cta: 'Open patient — resend plan',
        });
      }
    });

    // ── Overdue follow-ups ── latest next_review per follow-up patient
    const latestReview = {};
    (reviewsRes.data || []).forEach(r => {
      if (!latestReview[r.patient_nric]) latestReview[r.patient_nric] = r.next_review;
    });
    const today = new Date(); today.setHours(0, 0, 0, 0);
    Object.entries(latestReview).forEach(([nric, nextReview]) => {
      if (statusOf[nric] !== 'follow-up') return;
      const due = new Date(nextReview); due.setHours(0, 0, 0, 0);
      const overdueDays = Math.floor((today - due) / 86400000);
      if (overdueDays <= 0) return;
      list.push({
        id: `overdue-${nric}-${nextReview}`,
        type: 'alert',
        title: 'Follow-up overdue',
        message: `${who(nric)} — review was due ${due.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} (${overdueDays}d ago)`,
        ts: nextReview,
        nric,
        statusFilter: 'follow-up',
        cta: 'Open follow-up',
      });
    });

    list.sort((a, b) => new Date(b.ts) - new Date(a.ts));
    const read = readIdsRef.current;
    setNotifications(
      list.slice(0, MAX_NOTIFS).map(n => ({ ...n, time: timeAgo(n.ts), read: read.has(n.id) }))
    );
  }, []);

  useEffect(() => {
    build();
    const rebuild = () => {
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(build, 600); // collapse update bursts
    };
    const channel = supabase
      .channel('notifications-feed')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'consultations' }, rebuild)
      .on('postgres_changes', { event: '*', schema: 'public', table: 'delivery_jobs' }, rebuild)
      .subscribe();
    return () => {
      clearTimeout(debounceRef.current);
      supabase.removeChannel(channel);
    };
  }, [build]);

  const markRead = useCallback((id) => {
    readIdsRef.current.add(id);
    saveReadIds(readIdsRef.current);
    setNotifications(prev => prev.map(n => (n.id === id ? { ...n, read: true } : n)));
  }, []);

  const markAllRead = useCallback(() => {
    setNotifications(prev => {
      prev.forEach(n => readIdsRef.current.add(n.id));
      saveReadIds(readIdsRef.current);
      return prev.map(n => ({ ...n, read: true }));
    });
  }, []);

  const unreadCount = notifications.filter(n => !n.read).length;

  return { notifications, unreadCount, markRead, markAllRead };
}
