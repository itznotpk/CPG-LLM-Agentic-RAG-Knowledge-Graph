/**
 * Unit tests for the pure auth-gate routing decision.
 *
 * Guards the load-bearing access contract (CLAUDE.md / §4.9): the AuthProvider is
 * outermost, so no app view may render without a session, sign-out lands on
 * /login, and an unknown slug normalises to the dashboard. resolveRoute is the
 * single source of truth App.jsx's route components now defer to.
 */
import { describe, it, expect } from 'vitest';
import { resolveRoute, APP_VIEWS } from './routeGuard';

const session = { user: { id: 'u1' } };

describe('resolveRoute — loading', () => {
  it('shows the splash while auth is still resolving, regardless of route/session', () => {
    expect(resolveRoute({ route: 'app', loading: true, session })).toEqual({ action: 'splash' });
    expect(resolveRoute({ route: 'login', loading: true, session: null })).toEqual({ action: 'splash' });
  });
});

describe('resolveRoute — public routes (landing / login)', () => {
  it('renders the public page when signed out', () => {
    expect(resolveRoute({ route: 'landing', session: null })).toEqual({ action: 'render' });
    expect(resolveRoute({ route: 'login', session: null })).toEqual({ action: 'render' });
  });
  it('bounces an authenticated user into the app', () => {
    expect(resolveRoute({ route: 'landing', session })).toEqual({ action: 'redirect', to: '/dashboard' });
    expect(resolveRoute({ route: 'login', session })).toEqual({ action: 'redirect', to: '/dashboard' });
  });
});

describe('resolveRoute — protected app shell', () => {
  it('redirects an unauthenticated visitor to /login (the sign-out destination)', () => {
    expect(resolveRoute({ route: 'app', session: null, view: 'dashboard' }))
      .toEqual({ action: 'redirect', to: '/login' });
  });

  it('renders a known view for an authenticated clinician', () => {
    for (const view of APP_VIEWS) {
      expect(resolveRoute({ route: 'app', session, view })).toEqual({ action: 'render' });
    }
  });

  it('normalises an unknown slug to the dashboard', () => {
    expect(resolveRoute({ route: 'app', session, view: 'chart' }))      // in-memory sub-view, not routable
      .toEqual({ action: 'redirect', to: '/dashboard' });
    expect(resolveRoute({ route: 'app', session, view: 'totally-made-up' }))
      .toEqual({ action: 'redirect', to: '/dashboard' });
  });

  it('checks the session BEFORE the slug (no slug leakage to an anon visitor)', () => {
    expect(resolveRoute({ route: 'app', session: null, view: 'totally-made-up' }))
      .toEqual({ action: 'redirect', to: '/login' });
  });
});

describe('resolveRoute — unknown route', () => {
  it('sends anything unrecognised home', () => {
    expect(resolveRoute({ route: 'notfound', session })).toEqual({ action: 'redirect', to: '/' });
  });
});
