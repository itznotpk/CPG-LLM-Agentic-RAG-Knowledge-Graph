import { useEffect, useRef } from 'react';

// Settings → System → Session Timeout writes this key; the hook reads it lazily
// on every activity reset so changes take effect without a reload.
export const IDLE_TIMEOUT_KEY = 'cp_session_timeout_min';
export const DEFAULT_IDLE_MIN = 30;

export const getIdleTimeoutMin = () => {
  const v = Number(localStorage.getItem(IDLE_TIMEOUT_KEY));
  return v > 0 ? v : DEFAULT_IDLE_MIN;
};

// Auto sign-out after N minutes with no user activity. Mounted once in the
// authenticated app shell (AppContent), not per-page.
export function useIdleLogout(signOut) {
  const timerRef = useRef(null);
  const lastResetRef = useRef(0);

  useEffect(() => {
    const arm = () => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => signOut(), getIdleTimeoutMin() * 60000);
    };
    // Throttle: mousemove fires constantly; re-arming once per 15s is plenty
    // for a minutes-scale timeout.
    const onActivity = () => {
      const now = Date.now();
      if (now - lastResetRef.current < 15000) return;
      lastResetRef.current = now;
      arm();
    };
    const events = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach(e => window.addEventListener(e, onActivity, { passive: true }));
    arm();
    return () => {
      clearTimeout(timerRef.current);
      events.forEach(e => window.removeEventListener(e, onActivity));
    };
  }, [signOut]);
}
