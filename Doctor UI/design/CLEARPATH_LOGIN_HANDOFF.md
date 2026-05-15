# ClearPath Login Page — IDE Handoff

> Single-file static landing/login. Drop into the existing Vite + React app or any framework.

---

## Files to ship

| File | Where it goes | Notes |
|---|---|---|
| `Landing Page.html` | reference only — used to mock the design | Source of truth for layout, animations, copy |
| `colors_and_type.css` | `src/styles/clearpath-tokens.css` | Already matches your design system tokens |
| `MHNexus.png` | `public/logos/MHNexus.png` | Company logo |
| `UniMalaya.png` | `public/logos/UniMalaya.png` | University of Malaya partner logo |

---

## How to use this with Claude Code

### Option A — one-shot prompt (fastest)

Open the existing `Doctor UI` codebase, attach `Landing Page.html`, and prompt:

> "Convert `Landing Page.html` into a React route at `src/pages/Login.jsx`. Keep all CSS as a colocated `Login.module.css` (or styled-components — match the rest of the codebase). Preserve the 3D mouse-tilt, the four traveling teal beams, the corner pulse, the breathing halo, and the DM Serif Display headline. Load Geist + DM Serif Display from Google Fonts the same way `colors_and_type.css` already does. Use the existing `useTheme` and routing patterns. Logos go in `public/logos/`."

### Option B — task-by-task

Hand Claude Code the spec below.

---

## Spec

### Route
- Path: `/login` (or whatever your router uses)
- Shows when unauthenticated; redirects to Home on success

### Layout (1.05fr / 1fr split, stacks at 980px)
1. **Left panel (clinical brand)** — slate-50 → soft teal mesh background with 2 blurred orbs + topographic grid overlay
2. **Right panel (sign-in)** — white-ish with a faint dotted scaffold, hosting a centered floating glass card

### Left panel — top → bottom
- Topbar: `[UniMalaya logo] | [MHNexus logo]` — vertical divider, 52px height for Uni, 76px for MHNexus (PNG has internal padding)
- Hero:
  - "ClearPath." — DM Serif Display **italic**, 44px, teal-700
  - "Evidence-Based Clinical Practice Guidance System" — eyebrow, 11px caps tracked .18em, teal-700
  - "Clinician's *second opinion*, at the speed of a glance." — DM Serif Display 64px, italic on "second opinion" in teal-700
  - Animated ECG strip (live waveform, monospace `LIVE · ECG II` label + `HR 72 bpm · SpO₂ 98%` readout)

### Right panel — top → bottom
- Top row (justify-end): "New here? **Request access**"
- Floating 3D card containing the Welcome Back form

### The card
- Max-width 440px, frosted white, 22px radius, perspective 1500px
- **3D tilt** on mousemove: max ±8° rotateX/Y + 6px translateZ
- **Four traveling beams** chasing clockwise around the border (top → right → bottom → left), each `3.6s ease-in-out infinite` offset by `0.9s`
- **Four corner pulses** out of phase
- **Breathing halo** behind the card, brightens on hover
- All animations gated by `prefers-reduced-motion`

### Form fields
- "Welcome Back" h2 + dynamic subhead (rotates by time of day on load)
- Work email (placeholder: `dr.tay@mhnexus.com`)
- Password (show/hide toggle eye)
- Checkbox: "Keep me signed in for 8 hours"
- Forgot password link (right-aligned on password field label)
- Primary submit button: "Sign in →" — teal gradient, accent shadow, hover lifts

### Dynamic welcome subhead
Pick one randomly on load, time-aware:
```
'Sign in to pick up where you left off.'
'Good {morning|afternoon|evening} — sign in to view today's schedule.'
'Sign in to access your ClearPath workspace.'
'Welcome to today's queue. Sign in to continue.'
```

### Tokens used (already in colors_and_type.css)
- `--primary-500 / -600 / -700` — teal scale, headline + beams
- `--slate-50 / 200 / 300 / 700 / 900` — backgrounds, borders, text
- `--font-sans` (Geist) for UI
- `--font-mono` (Geist Mono) for ECG values, captions
- `--font-display` (DM Serif Display) — add to the tokens file alongside the existing imports
- `--radius-lg / -xl` for cards
- `--shadow-accent` for the sign-in button

---

## React conversion notes

```jsx
// src/pages/Login.jsx
import { useEffect, useRef, useState } from 'react';

export default function Login() {
  const cardRef = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const wrap = wrapRef.current, card = cardRef.current;
    if (!wrap || !card) return;
    let raf = 0;
    const onMove = (e) => {
      const r = card.getBoundingClientRect();
      const cx = e.clientX - r.left - r.width / 2;
      const cy = e.clientY - r.top - r.height / 2;
      const rx = (cy / (r.height / 2)) * -8;
      const ry = (cx / (r.width  / 2)) *  8;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        card.style.transform = `rotateX(${rx}deg) rotateY(${ry}deg) translateZ(6px)`;
      });
    };
    const onLeave = () => { card.style.transform = 'rotateX(0) rotateY(0) translateZ(0)'; };
    wrap.addEventListener('mousemove', onMove);
    wrap.addEventListener('mouseleave', onLeave);
    return () => {
      wrap.removeEventListener('mousemove', onMove);
      wrap.removeEventListener('mouseleave', onLeave);
    };
  }, []);

  // ...form state, handlers, JSX matching Landing Page.html
}
```

---

## Acceptance checklist for the CC agent

- [ ] Route renders at `/login`
- [ ] Both logos load with correct sizes (Uni 52px, MHNexus 76px)
- [ ] Headline is DM Serif Display italic and matches the screenshot
- [ ] Card tilts on mousemove and resets on mouseleave
- [ ] All four teal beams visibly chase clockwise on the card border
- [ ] Corner glow dots pulse at different phases
- [ ] Form submits without console errors (mock or real auth)
- [ ] `prefers-reduced-motion` kills the tilt + beams + halo
- [ ] Below 980px width, the two panels stack vertically and the card sits below the left brand hero
- [ ] Welcome subhead rotates between 4 options based on time of day

---

## Open questions to confirm with the team
1. Real auth provider — Supabase, Auth0, hospital SSO?
2. Should "Request access" go to a form or open a mailto?
3. After login, default route = `/` (Home) or last-visited?
4. Branding decision: keep both UM + MHNexus logos, or only one in production?
