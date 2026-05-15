# ClearPath Login — Supabase Auth Wiring Handoff

> Implementation plan for wiring `src/pages/Login.jsx` to real Supabase authentication
> and establishing a dynamic clinician session across the app.

**Target executor:** Sonnet (Claude Code)
**Status:** Ready to implement — all backend scaffolding (Supabase project, `profiles` table, RLS) is already in place; only client-side wiring is needed.

---

## 1. Goal

Replace the placeholder `useState(false)` auth gate in `src/App.jsx` with a real Supabase session-backed gate, so that:

1. **Login.jsx** submits real credentials to `supabase.auth.signInWithPassword()`
2. The app gates on a real Supabase **session** (auto-restored on refresh, expires & redirects to login)
3. The clinician's **profile row** (name, specialty, license, facility, department, avatar) is fetched once on login and made available via React context — replacing the hardcoded `profile` literal in `AppContent`
4. **Sign out** from the sidebar works and bounces the user back to Login
5. "Keep me signed in for 8 hours" is honored via storage choice (localStorage vs sessionStorage)

---

## 2. Current state (what's already there)

| Concern | Status | Notes |
|---|---|---|
| `@supabase/supabase-js` installed | ✅ | `package.json` v2.90.1 |
| `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` in `.env` | ✅ | Already configured |
| Supabase client export | ✅ | `src/lib/supabase.js` exports `supabase` |
| `getCurrentUser()`, `getCurrentSession()`, `signOut()`, `onAuthStateChange()` | ✅ | Already in `src/lib/supabase.js` |
| `getCurrentProfile()`, `updateProfile()` | ✅ | Joins `auth.users` → `public.profiles` |
| `profiles` table schema | ✅ | `id`, `email`, `full_name`, `title`, `specialty`, `license_number`, `phone`, `facility`, `department`, `avatar_url`, `role`, `settings` |
| `Login.jsx` UI complete | ✅ | Currently calls mock `onLogin()` after 800ms |
| `App.jsx` auth gate | ⚠️ Placeholder | `const [authed, setAuthed] = useState(false)` — needs replacement |
| `signInWithPassword` helper | ❌ | Not yet exported from `supabase.js` |
| `AuthProvider` context | ❌ | Needs to be created |
| Sidebar sign-out hookup | ❌ | Button exists; no handler bound |
| Profile-driven `AppContent` | ❌ | `useState({ name: 'Dr. Tay', ... })` is hardcoded in `App.jsx` |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ App.jsx                                                     │
│   ┌────────────────────────────────────────────────────────┐│
│   │ AuthProvider (new — src/context/AuthContext.jsx)       ││
│   │  • subscribes to supabase.auth.onAuthStateChange       ││
│   │  • exposes { session, user, profile, loading,          ││
│   │              signIn, signOut, refreshProfile }         ││
│   └────────────────────────────────────────────────────────┘│
│                                                             │
│   if (!session) → <Login />                                 │
│   else          → <ThemeProvider><AppProvider>…<AppContent>│
│                                                             │
│   AppContent reads `profile` from useAuth() instead of      │
│   useState(...)                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key principle:** Supabase JS SDK persists the session to `localStorage` automatically, so on page reload the SDK re-emits a `SIGNED_IN` event with the restored session. Our `AuthProvider` listens to that event and the gate flips without a manual API call.

---

## 4. Files to create / modify

### A. NEW — `src/context/AuthContext.jsx`

Owns the session state, profile fetch, and exposes auth actions.

```jsx
import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { supabase, getCurrentProfile } from '../lib/supabase';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [user, setUser]       = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true); // gate the splash on first load

  const loadProfile = useCallback(async () => {
    const { data, error } = await getCurrentProfile();
    if (error) {
      console.error('Profile fetch failed', error);
      setProfile(null);
      return;
    }
    setProfile(data);
  }, []);

  useEffect(() => {
    // 1) Hydrate session from localStorage on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session) loadProfile();
      setLoading(false);
    });

    // 2) Subscribe to future changes (login / logout / token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
        if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
          loadProfile();
        }
        if (event === 'SIGNED_OUT') {
          setProfile(null);
        }
      }
    );

    return () => subscription.unsubscribe();
  }, [loadProfile]);

  const signIn = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    return data;
  };

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{
      session, user, profile, loading,
      signIn, signOut, refreshProfile: loadProfile,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
};
```

### B. MODIFY — `src/pages/Login.jsx`

Replace the mock `handleSubmit` with the real call, surface errors inline.

**Add at top:**
```jsx
import { useAuth } from '../context/AuthContext';
```

**Add state:**
```jsx
const { signIn } = useAuth();
const [errorMsg, setErrorMsg] = useState('');
```

**Replace `handleSubmit`:**
```jsx
const handleSubmit = async (e) => {
  e.preventDefault();
  setErrorMsg('');
  setLoading(true);
  try {
    await signIn(email, password);
    // onLogin is no longer needed — App.jsx flips on session change
  } catch (err) {
    setErrorMsg(err.message || 'Sign in failed. Check your credentials.');
  } finally {
    setLoading(false);
  }
};
```

**Render error inline** (above the submit button, styled with `--danger`):
```jsx
{errorMsg && (
  <p style={{
    color: 'var(--danger)',
    fontSize: 13,
    marginBottom: 12,
  }}>{errorMsg}</p>
)}
```

**Handle "Keep me signed in for 8 hours":** Supabase persists session to localStorage by default. To honor the unchecked state (session-only), the client must be re-initialized with `storage: sessionStorage` — but that requires module-level config, not per-submit. The pragmatic compromise:

- **Checked (default):** uses localStorage → persists across browser restarts
- **Unchecked:** on signIn, immediately set a flag in `sessionStorage` and on every page load if that flag is present but the user reopened the browser (no `sessionStorage` flag survives), call `supabase.auth.signOut()`

Or simpler — just document the behavior and leave the checkbox as cosmetic for v1. **Recommended:** mark as cosmetic in v1, add a TODO comment.

### C. MODIFY — `src/App.jsx`

Wrap everything in `AuthProvider`, replace the `authed` state with `useAuth()`.

```jsx
import Login from './pages/Login';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppProvider, useApp } from './context/AppContext';
// ... other imports stay the same

function Gate() {
  const { session, profile, loading } = useAuth();

  if (loading) {
    return <SplashScreen />; // see step D below — quick teal-tinted spinner
  }

  if (!session) {
    return <Login />;
  }

  return (
    <ThemeProvider>
      <AppProvider>
        <ToastProvider>
          <AppContent />
        </ToastProvider>
      </AppProvider>
    </ThemeProvider>
  );
}

function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}

export default App;
```

**Inside `AppContent`:** delete the hardcoded `useState({ name: 'Dr. Tay', ... })` block. Replace with:

```jsx
const { profile, signOut } = useAuth();

// Build the `profile` shape that Sidebar expects from the Supabase profile row.
// Fallback values keep the UI sensible if a field is null in the DB.
const sidebarProfile = profile ? {
  name:       profile.full_name      || 'Clinician',
  email:      profile.email,
  phone:      profile.phone          || '',
  specialty:  profile.specialty      || '',
  license:    profile.license_number || '',
  facility:   profile.facility       || '',
  department: profile.department     || '',
  avatarUrl:  profile.avatar_url     || null,
  role:       profile.role           || 'doctor',
} : null;
```

Then pass `sidebarProfile` and `signOut` to `<Sidebar />`.

### D. NEW — `src/components/shared/SplashScreen.jsx`

A 200ms-or-less skeleton shown while `getSession()` resolves on first paint. Prevents a Login-flash for already-signed-in users.

```jsx
export default function SplashScreen() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'grid',
      placeItems: 'center',
      background: 'linear-gradient(160deg, #f8fafc 0%, #f1f5f9 55%, #e2e8f0 100%)',
    }}>
      <div style={{
        width: 32, height: 32,
        border: '2px solid rgba(20,184,166,.2)',
        borderTopColor: 'var(--primary-600, #0d9488)',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
```

### E. MODIFY — `src/components/layout/Sidebar.jsx`

Find the bottom user-profile chip. Add a sign-out menu item (or a button). Bind to `signOut` from `useAuth`. After signOut, `App.jsx` will auto-render `<Login />` (no manual navigation needed).

```jsx
import { useAuth } from '../../context/AuthContext';

// inside Sidebar component:
const { signOut } = useAuth();

// Add a LogOut menu item near profile chip:
<button onClick={signOut} className="...">
  <LogOut className="w-4 h-4" strokeWidth={1.5} />
  Sign out
</button>
```

### F. OPTIONAL — `src/lib/supabase.js`

Add a `signInWithEmail` helper for symmetry with the existing `signOut`. Not strictly required since `AuthContext.signIn` already wraps it, but nice for callers outside React.

```jsx
export const signInWithEmail = async (email, password) => {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  return { data, error };
};
```

---

## 5. Implementation order

Do these in sequence — each step is independently testable.

1. **Create `AuthContext.jsx`** (file B). Run dev server — no UI change yet, but `useAuth` is now callable.
2. **Wrap App in `AuthProvider`, add `Gate` component** (file C). Login still shown because `session` is `null` on first load.
3. **Create `SplashScreen.jsx`** (file D). Refresh — should see brief spinner then Login.
4. **Wire `Login.jsx` to `useAuth().signIn`** (file B above). Test with a real Supabase user — should sign in and the gate flips to the app.
5. **Refresh the page while signed in** — should re-enter the app, not Login. (Confirms session persistence.)
6. **Replace hardcoded profile in `AppContent`** with `useAuth().profile` mapping. Verify sidebar shows the real clinician's name/specialty.
7. **Wire sign-out in Sidebar** (file E). Click sign out → Login screen appears, refresh stays on Login.
8. **Add inline error rendering in Login.jsx** for failed credentials. Test with wrong password.

---

## 6. Acceptance criteria

- [ ] Sign in with a real Supabase user → app loads with that clinician's profile in the sidebar
- [ ] Refresh the page → no Login flash, app stays loaded (session restored)
- [ ] Sidebar shows `profile.full_name`, `profile.specialty`, etc. from the `profiles` row (not hardcoded `Dr. Tay`)
- [ ] Sign out → returns to Login, refresh stays on Login (session cleared)
- [ ] Wrong credentials → inline red error under the form, no crash
- [ ] Network error during sign in → error message surfaced, form remains usable
- [ ] No `console.error` on a normal sign-in flow
- [ ] All existing app features (consultation, my patients, settings) continue to work
- [ ] Profile updates from Settings page (via existing `updateProfile()`) reflect in the sidebar after `refreshProfile()` is called

---

## 7. Test users to provision

Have at least 2 users in Supabase Auth + matching `profiles` rows for QA:

| Email | Password | full_name | specialty | facility | role |
|---|---|---|---|---|---|
| `dr.tay@mhnexus.com` | (set in dashboard) | Dr. Tay Wei Liang | Family Medicine | Hospital Kuala Lumpur | doctor |
| `dr.lim@mhnexus.com` | (set in dashboard) | Dr. Lim Mei Hua | Cardiology | Pantai Hospital KL | doctor |

The `profiles` row must be created with `id = auth.users.id` — confirm there's either a trigger (`handle_new_user`) auto-inserting profiles on signup OR insert them manually for these test users.

---

## 8. Edge cases & error handling

| Case | Behavior |
|---|---|
| User exists in `auth.users` but no `profiles` row | `getCurrentProfile()` returns null → sidebar shows fallbacks ("Clinician"). Log a warning, don't crash. |
| Session expires while app is open | `onAuthStateChange` fires `SIGNED_OUT` → gate flips to Login automatically. Show a toast: "Session expired, please sign in again." |
| Network failure on sign in | Catch the error in Login.jsx, show inline message, keep form interactive. |
| User signs in from another tab | Supabase emits `SIGNED_IN` across tabs via storage events → this tab's gate also opens. ✅ Works out of the box. |
| `profiles.role !== 'doctor'` | v1: still let them in. v2 (future): gate non-doctor roles to a "no access" screen — see section 9. |

---

## 9. Future work (out of scope for this handoff)

- **Forgot password** — wire the `Forgot password?` link to `supabase.auth.resetPasswordForEmail()` + create a `/reset-password` route
- **Request access** — replace `mailto:` with a real form that creates an admin notification
- **Role-based gating** — read `profile.role` and route doctors vs admins vs nurses to different shells
- **SSO** — Supabase supports SAML/OIDC for hospital identity providers (Auth0, Azure AD)
- **Audit log** — log every sign in / sign out / failed attempt to a `auth_events` table for clinical compliance
- **"Keep me signed in for 8 hours" — proper implementation** — switch Supabase client storage between localStorage and sessionStorage based on the checkbox; requires re-instantiating the client or using a custom storage adapter
- **MFA** — Supabase has built-in TOTP MFA enrollment via `supabase.auth.mfa.enroll()`

---

## 10. Open questions for the team (resolve before merging)

1. Should `profiles` rows be auto-created on signup (DB trigger) or manually provisioned by admins?
2. Should "Sign out" be a confirmation dialog or instant?
3. After session expiry, should the user land on Login with their email pre-filled (UX) or empty (security)?
4. What's the JWT expiry configured in Supabase Auth settings? (Affects session refresh cadence.)
5. Is there a `last_login_at` column to update on each successful sign in? If yes, add to `AuthContext.signIn`.
