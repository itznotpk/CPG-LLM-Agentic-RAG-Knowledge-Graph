// Pure auth-gate routing decision — no React, no router, importable anywhere.
// Consolidates the rules previously scattered across App.jsx's LandingRoute /
// LoginRoute / AppShell / Gate into one testable place, so the load-bearing
// contract ("AuthProvider outermost; no app view renders without a session;
// sign-out → /login; unknown slug → dashboard") can be regression-guarded.

// Top-level app views that map 1:1 to URL paths (/dashboard, /patients, …).
// 'chart' is intentionally NOT routable — it's an in-memory sub-view that needs
// a patient object, so it lives under /patients and falls back there.
export const APP_VIEWS = ['dashboard', 'patients', 'consultation', 'settings', 'analytics'];

/**
 * Decide what an auth-gated route should do.
 *
 * @param {object} args
 * @param {'landing'|'login'|'app'|'notfound'} args.route  which route is rendering
 * @param {boolean} [args.loading]  auth still resolving the initial session
 * @param {object|null} [args.session]  the Supabase session (null = signed out)
 * @param {string|null} [args.view]  the :view slug (only for route === 'app')
 * @param {string[]} [args.appViews]  valid view slugs
 * @returns {{action:'splash'} | {action:'render'} | {action:'redirect', to:string}}
 */
export function resolveRoute({ route, loading = false, session = null, view = null, appViews = APP_VIEWS }) {
  // While the initial session is resolving, nothing routes — show the splash.
  if (loading) return { action: 'splash' };

  switch (route) {
    // Public routes: an authenticated user is bounced into the app.
    case 'landing':
    case 'login':
      return session ? { action: 'redirect', to: '/dashboard' } : { action: 'render' };

    // Protected shell: unauthenticated → /login (same as sign-out); unknown
    // slug → normalise to the dashboard.
    case 'app':
      if (!session) return { action: 'redirect', to: '/login' };
      if (!appViews.includes(view)) return { action: 'redirect', to: '/dashboard' };
      return { action: 'render' };

    // Anything else → home.
    default:
      return { action: 'redirect', to: '/' };
  }
}
