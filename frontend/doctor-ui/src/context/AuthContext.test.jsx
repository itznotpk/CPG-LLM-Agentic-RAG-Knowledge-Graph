// @vitest-environment jsdom
/**
 * Behaviour tests for AuthProvider / useAuth.
 *
 * AuthContext is the load-bearing identity layer (§4.9): it maps the Supabase
 * session to user/profile state, keeps them in sync via onAuthStateChange, and
 * its authenticated identity later signs the Stage-6 acknowledgement and the PDF
 * cover. These tests mock the Supabase client (no network) and assert the
 * provider's contract: initial session resolution, the loading flag, profile
 * lifecycle on SIGNED_IN / SIGNED_OUT, signIn error propagation, sign-out, the
 * useAuth-outside-provider guard, and subscription cleanup on unmount.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor, cleanup } from '@testing-library/react';

const h = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  getCurrentProfile: vi.fn(),
  unsubscribe: vi.fn(),
  authCb: { current: null },
}));

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: h.getSession,
      onAuthStateChange: (cb) => {
        h.authCb.current = cb;
        return { data: { subscription: { unsubscribe: h.unsubscribe } } };
      },
      signInWithPassword: h.signInWithPassword,
      signUp: h.signUp,
      signOut: h.signOut,
    },
    from: vi.fn(() => ({ update: vi.fn(() => ({ eq: vi.fn() })) })),
  },
  getCurrentProfile: h.getCurrentProfile,
}));

import { AuthProvider, useAuth } from './AuthContext';

const SESSION = { user: { id: 'u1', email: 'dr@hospital.my' } };
const PROFILE = { id: 'u1', full_name: 'Dr Tey', role: 'doctor' };

beforeEach(() => {
  vi.clearAllMocks();
  h.authCb.current = null;
  h.getSession.mockResolvedValue({ data: { session: null } });
  h.getCurrentProfile.mockResolvedValue({ profile: null, error: null });
  h.signOut.mockResolvedValue({ error: null });
});

afterEach(() => cleanup());

describe('useAuth guard', () => {
  it('throws when used outside an AuthProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => renderHook(() => useAuth())).toThrow(/useAuth must be used inside AuthProvider/);
    spy.mockRestore();
  });
});

describe('initial session resolution', () => {
  it('with no session: user/profile null and loading clears', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.profile).toBeNull();
    expect(h.getCurrentProfile).not.toHaveBeenCalled();   // no session → no profile fetch
  });

  it('with a session: maps user and loads the profile', async () => {
    h.getSession.mockResolvedValue({ data: { session: SESSION } });
    h.getCurrentProfile.mockResolvedValue({ profile: PROFILE, error: null });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toEqual(SESSION.user);
    await waitFor(() => expect(result.current.profile).toEqual(PROFILE));
  });
});

describe('onAuthStateChange lifecycle', () => {
  it('SIGNED_IN sets the user and (re)loads the profile', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));

    h.getCurrentProfile.mockResolvedValue({ profile: PROFILE, error: null });
    await act(async () => { h.authCb.current('SIGNED_IN', SESSION); });

    expect(result.current.user).toEqual(SESSION.user);
    await waitFor(() => expect(result.current.profile).toEqual(PROFILE));
  });

  it('SIGNED_OUT clears the profile and user', async () => {
    h.getSession.mockResolvedValue({ data: { session: SESSION } });
    h.getCurrentProfile.mockResolvedValue({ profile: PROFILE, error: null });
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.profile).toEqual(PROFILE));

    await act(async () => { h.authCb.current('SIGNED_OUT', null); });
    expect(result.current.user).toBeNull();
    expect(result.current.profile).toBeNull();
  });
});

describe('signIn / signOut', () => {
  it('signIn returns data on success', async () => {
    h.signInWithPassword.mockResolvedValue({ data: { user: SESSION.user }, error: null });
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));

    let data;
    await act(async () => { data = await result.current.signIn('dr@hospital.my', 'pw'); });
    expect(data).toEqual({ user: SESSION.user });
    expect(h.signInWithPassword).toHaveBeenCalledWith({ email: 'dr@hospital.my', password: 'pw' });
  });

  it('signIn rejects (throws) when Supabase returns an error', async () => {
    h.signInWithPassword.mockResolvedValue({ data: null, error: new Error('Invalid login credentials') });
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(result.current.signIn('x@y.z', 'bad')).rejects.toThrow('Invalid login credentials');
  });

  it('signOut delegates to supabase.auth.signOut', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.signOut(); });
    expect(h.signOut).toHaveBeenCalledTimes(1);
  });
});

describe('cleanup', () => {
  it('unsubscribes from auth changes on unmount', async () => {
    const { result, unmount } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));
    unmount();
    expect(h.unsubscribe).toHaveBeenCalledTimes(1);
  });
});
