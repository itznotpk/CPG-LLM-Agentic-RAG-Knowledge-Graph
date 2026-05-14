# MHNexus Doctor UI — Design Review Handoff

> Paste this whole file (or individual tasks) into your IDE agent (Cursor / Claude Code / Cline / etc.).
> Each task is self-contained: file path, target lines, what to change, and an acceptance check.

---

## How to use this with your IDE agent

**Option A — give it everything at once.** Open your repo in your IDE, attach this file, and prompt:

> "Read HANDOFF.md and work through tasks in priority order (P1 first). For each task, open the listed file, make the change, run the dev server, and confirm the acceptance check before moving on. Stop after each priority block and let me review."

**Option B — one task at a time.** Copy a single `### TASK` block into the chat. Cleanest if you want to QA each change.

**Option C — assign by area.** All Consultation tasks → one session. All Sidebar tasks → another. Keeps diffs small.

---

## Priority 1 — Consultation flow (Diagnosis)

### TASK 1.1 — Kill the centered hero on the Diagnosis page

**File:** `src/components/sections/DiagnosisSection.jsx` (around line 62)

**Current:**
```jsx
<div className="text-center mb-6">
  <h2 className={`text-2xl font-bold mb-2 ...`}>AI Risk Assessment & Diagnosis</h2>
  <p className={...}>Review and select the diagnosis to proceed with care plan generation</p>
</div>
```

**Change to:**
- Left-aligned row
- Eyebrow `STEP 2 OF 4` (use the existing `ds-eyebrow` class)
- Short title `Diagnosis` (not "AI Risk Assessment &")
- Subtitle: `Confirm the AI's working diagnosis, or pick differentials to re-route.`
- Move the Back / Confirm buttons inline on the right side of the row

**Acceptance:** No centered text anywhere in `DiagnosisSection`. Title height shrinks ~80px → ~52px.

---

### TASK 1.2 — Remove the "Selected Diagnosis" duplicate hero card

**File:** `src/components/sections/DiagnosisSection.jsx` (the `<GlassCard className="p-6 border-[var(--accent-primary)]/50 border-2">` block, ~line 95)

**Why:** The diagnosis is already shown in the differential list below with a check icon and a teal border. Showing it twice doubles cognitive load.

**Change:** Delete the whole "Selected Diagnosis" hero `GlassCard`. The "Clinical Correlation Required" amber note moves to a single line above the differential list (smaller, no card).

**Acceptance:** Diagnosis appears in exactly one place. Page height drops noticeably.

---

### TASK 1.3 — Slim down differential rows (two-signal badge rule)

**File:** `src/components/sections/DiagnosisSection.jsx` (the differential `button` map, ~line 160)

**Current row carries:** numbered circle + name + `AI Recommended` pill + `ICD-11: XXX` pill + risk pill + possibly a checkmark.

**Change each row to a single line:**

```
[01 mono]  Type II Diabetes Mellitus  [ICD-11 5A11 mono]  •──── moderate · AI top pick · 87%
```

Rules:
- Rank number: mono, teal-600 if selected, slate-400 otherwise. No circle.
- ICD code: mono text, no pill (`<span className="ds-numeric text-slate-500">ICD-11 · 5A11</span>`).
- Risk: a 6px coloured dot + the word "moderate" (no rectangle pill).
- "AI top pick": plain text, not a pill.
- Selected row: left-border 3px teal, light teal background. Drop the `border-2` ring.

**Acceptance:** Each differential row is ~52–60px tall. No more than 2 colours per row (text + one risk dot).

---

## Priority 2 — Glass layers (system primitive)

### TASK 2.1 — Stop wrapping `GlassPanel` around `GlassCard`

**Files:**
- `src/App.jsx` (the consultation render, ~line 130)
- `src/components/shared/GlassCard.jsx`

**Current:** `<GlassPanel><GlassCard>...content with another tinted card inside...</GlassCard></GlassPanel>` produces 3–4 translucent layers.

**Change:**
- In `App.jsx` consultation case, replace the outer `<GlassPanel>` with `<div className="min-h-[600px]">`. The page background already provides the "glass" feeling.
- In `GlassCard.jsx`, remove `backdrop-blur-[14px]` from the `default` and `light` variants. Replace with opaque `bg-white` (light) / `bg-slate-800` (dark), plus the existing `border` + `shadow-lg`.

**Acceptance:** No more than one frosted layer visible at any point in the consultation flow. Text contrast on patient-name rows improves visibly.

---

## Priority 3 — Sidebar

### TASK 3.1 — One signal for "active"

**File:** `src/components/layout/Sidebar.jsx` (the nav button, ~line 56)

**Current active state** (light): `bg-gradient-to-r from-[var(--accent-primary)]/20 to-[var(--accent-secondary)]/20 border border-[var(--accent-primary)]/30 ${accent.text} shadow-lg ${accent.shadow}` + a right-edge accent bar.

**Change active to a single treatment for both modes:**
```jsx
isActive
  ? `border-l-2 border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 ${accent.text} font-semibold`
  : `border-l-2 border-transparent ...hover styles`
```
Drop the gradient, the shadow, the box border, and the right-edge bar.

**Bonus (TASK 3.2):** Add a small mono count next to "My Patients" pulled from `patientRegistry.length`:
```jsx
{!isCollapsed && item.id === 'patients' && (
  <span className="ml-auto text-[10px] text-slate-400 font-mono">{patientCount}</span>
)}
```

**Acceptance:** Active item uses exactly one accent treatment. Sidebar feels lighter.

---

## Priority 4 — PatientChart vitals

### TASK 4.1 — Single colour series for vital lines

**File:** `src/components/pages/PatientChart.jsx` (`vitalsTabs` config, lines 9–48) + `src/components/shared/VitalsLineChart.jsx` (if it consumes the `color` prop).

**Current:** Each metric has its own hex (`#ef4444`, `#f97316`, `#8b5cf6`, `#3b82f6`, `#10b981`, `#f59e0b`).

**Change all `color` values to:**
- Primary line (or single-line metrics): `var(--accent-primary)` = teal 500
- Secondary line in BP pair (Diastolic): `var(--slate-400)` rendered with `strokeDasharray="4 4"`

Then add a single `outOfRange: '#ef4444'` colour rule — applied per-point when a value crosses reference ranges. Reference range shown as a soft `var(--slate-100)` band, not gridlines.

**Acceptance:** Open PatientChart. Switch between tabs. Every chart uses teal as its main hue. Red appears only on individual out-of-range points.

---

## Priority 5 — rPPG Vital Scanner modal

### TASK 5.1 — Fix the background colour

**File:** `src/components/shared/RPPGScanModal.jsx` (line ~105 — the outer wrapper)

**Current:** `style={{ background: isDark ? '#0a0f1e' : '#f0f4ff' }}`

**Change to:**
```jsx
style={{ background: 'var(--bg-primary)' }}
```
Lavender → slate-50.

---

### TASK 5.2 — Replace the empty camera frame with a face-positioning guide

**File:** `src/components/shared/RPPGScanModal.jsx` (the camera-feed `<div>`, ~line 128)

When `!faceFound` and `connected`, overlay:
- A centered dashed oval (110×145px) in teal-500/50
- 4 small teal corner brackets just outside the oval
- A small mono uppercase line above: `POSITION FACE INSIDE THE GUIDE`
- A 4-step prep row below the oval, mono 9px:
  `● GOOD LIGHT     ● NO GLASSES     ● LOOK STRAIGHT     ● ~15 SEC`
- A signal-quality pill anchored to the top-right of the frame: `SIGNAL · NN%` (use the existing `quality` variable)

---

### TASK 5.3 — Collapse the 6 vital cards into a single list

**File:** `src/components/shared/RPPGScanModal.jsx` — replace the `VitalCard` component and the right-panel grid

**New component** (paste into the same file, above `RPPGScanModal`):

```jsx
function VitalRow({ icon: Icon, label, value, unit }) {
  const hasValue = value != null && Number(value) !== 0;
  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 last:border-0">
      <div className="flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${hasValue ? 'bg-teal-600' : 'bg-slate-300'}`} />
        <span className="text-sm text-slate-700">{label}</span>
      </div>
      <div>
        <span className={`ds-numeric font-semibold ${hasValue ? 'text-slate-900' : 'text-slate-300'}`}>
          {hasValue ? (Number.isInteger(Number(value)) ? value : Number(value).toFixed(1)) : '—'}
        </span>
        <span className="ml-1 text-[10px] text-slate-400">{unit}</span>
      </div>
    </div>
  );
}
```

Then swap the `grid grid-cols-2 gap-3` block for a single `<div className="bg-white border border-slate-200 rounded-xl overflow-hidden">` containing 6 `<VitalRow>`s. Same prop signature as before, no `color` prop.

---

### TASK 5.4 — Make the Apply button announce how many vitals are ready

**File:** `src/components/shared/RPPGScanModal.jsx` (Apply button, ~line 213)

**Change button label** while not yet applied:
```jsx
const readyCount = [hr, spo2, vitals?.sbp, vitals?.dbp, vitals?.rr, temp]
  .filter(v => v != null && Number(v) !== 0).length;

// inside button
<><Zap className="w-5 h-5" /> Apply {readyCount} of 6 vitals</>
```

---

### TASK 5.5 — Make sure the modal actually covers the sidebar

**File:** `src/components/shared/RPPGScanModal.jsx` (line ~105)

Confirm the wrapper is `<div className="fixed inset-0 z-[80] ...">` and there is no parent transform/contain rule clipping it. If the sidebar is still visible behind the modal in the live app, raise `z-[80]` → `z-[100]` and add `isolation: isolate` to the wrapper.

---

## Priority 6 — System-level rules (apply globally as you touch files)

These are not single-file tasks; they're rules to follow during any edit.

### RULE A — Two-hue ceiling per screen
Use teal for accent. Use slate for everything neutral. Reserve `violet / sky / amber / rose` for **state** (in-progress, info, warning, error). No category colours.

### RULE B — One eyebrow per section, max
The `ds-eyebrow` class is precision text. If a section already has a heading + a card border, drop the eyebrow.

### RULE C — Badge ceiling: 1 status + 1 ID per row
Anything beyond that becomes plain text or a 6px dot.

### RULE D — Padding scale
`p-6` is for top-level panels only. List rows are `p-3` to `p-4`. Audit any list-style component (`MyPatients` table rows, schedule rows, differential rows) and tighten.

### RULE E — Springs for confirms, linear for hovers
Find any element using `--ease-spring` on `:hover`. Switch hovers to `--ease-out` at `--dur-fast` (150ms). Keep springs for step transitions and toast reveals.

### RULE F — Dark-mode contrast audit
Grep for `text-slate-400` next to `bg-slate-800` or `bg-white/5`. Bump body text to `text-slate-300`. Inner borders in dark mode should be `border-white/10` minimum.

---

## Suggested commit plan

| # | Branch / commit | Tasks |
|---|---|---|
| 1 | `chore/diagnosis-cleanup` | 1.1, 1.2, 1.3 |
| 2 | `chore/glass-layers` | 2.1 |
| 3 | `chore/sidebar` | 3.1, 3.2 |
| 4 | `chore/rppg-modal` | 5.1, 5.2, 5.3, 5.4, 5.5 |
| 5 | `chore/charts` | 4.1 |
| 6 | rolling | Rules A–F as encountered |

Land each branch independently; none of them depend on each other.

---

## Verification prompt (paste to your IDE agent after it finishes a block)

> "Take a screenshot of `<screen>` in light mode and dark mode. Compare against the 'Next' vignette in `Design Review.html` for the same screen. List any visual deltas — don't just say 'looks good'. Then run `npm run dev` and confirm no console errors."
