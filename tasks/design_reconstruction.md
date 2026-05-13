# Doctor UI — Design Reconstruction

> Audit of the current consultation layout (all 4 steps) + AI Reasoning Trace redesign.
> Based on screenshot review of Step 2 (Diagnosis tab) and code reading of all section components.

---

## Current state — what the screenshot reveals

### What works
- Patient banner at the top (`Low Jia Qi · 040204-07-0278 · 22 yrs · Female`) is clean and immediately readable
- Risk level chip (`Moderate Risk`) and allergy chip (`Shellfish`) are already surfaced in the header — this is correct
- The split-screen in Step 2 (Reasoning Trace left / DDx cards right) is structurally right
- CPG Routing sub-steps with `Semantic` badge are legible and informative

### What needs fixing
- **AI Reasoning Trace is Step-2 only** — after the clinician moves to Step 3 (Care Plan), the trace disappears entirely. There is no way to look back at the CPG evidence or routing rationale while prescribing. This is the single biggest usability gap.
- **Evidence Retrieval error is raw JSON** — the 429 error text is dumped verbatim in the trace panel. Clinicians should never see `{'error': {'code': 429, 'message': ...}}`. It needs a human-readable error card.
- **Plan Synthesis is stuck on "Generating…"** — no timeout indicator, no retry affordance. If synthesis fails silently, the clinician has no next action.
- **The trace panel has no expand-to-fullscreen option** — for complex cases (e.g. multi-comorbidity with 5 DDx candidates), the `lg:col-span-5` panel is too narrow to read reasoning tokens comfortably.
- **Step 1 (Data Input) is a long single-column scroll** — reviewed in code: MPIS Search → Demographics → Vitals → ClinicalNotes stacked vertically. No issue on large screens; problematic on 1366px clinic hardware.
- **Step 3 (Care Plan) is full-width** — confirmed ICD and allergies are not kept in view while prescribing medications.
- **Step 4 (Complete / OutputSection)** — currently a summary dump. No SOAP structure. No clear EMR export flow.

---

## AI Reasoning Trace — redesign

### Problem: why it must not live only in Step 2

The trace is the audit trail of the AI's clinical reasoning. Clinicians need it:
- **In Step 2** when choosing which ICD to confirm (obvious — already there)
- **In Step 3** when prescribing medication to verify which CPG a recommendation came from
- **In Step 4** when signing the note — to attach the evidence chain to the record

Hiding it after Step 2 breaks the transparency promise entirely.

### Option A — Persistent collapsible drawer (recommended)

A slim `AI Reasoning Trace` drawer pinned to the **right edge** of the viewport, visible across Steps 2, 3, and 4. It collapses to a 40px tab (`🧠 Trace`) and expands to ~380px wide on demand.

```
┌─────────────────────────────────┬──────────────────────────┐
│  Step content (flexible width)  │  🧠 AI Reasoning Trace   │
│                                 │  ─────────────────────── │
│                                 │  ✅ DDx Analysis          │
│                                 │     top: BB91.Z           │
│                                 │  ✅ CPG Routing           │
│                                 │     Pulmonary-HTN (2011)  │
│                                 │     └ Semantic            │
│                                 │  ❌ Evidence Retrieval    │
│                                 │     Credits depleted      │
│                                 │  ⏳ Plan Synthesis        │
│                                 │─────────────────────────  │
│                                 │  [Expand] [Copy trace]    │
└─────────────────────────────────┴──────────────────────────┘
```

**Tailwind:** `fixed right-0 top-[PatientBannerHeight] h-[calc(100vh-bannerHeight)] w-[380px]` with `translate-x-full` when collapsed, `translate-x-0` when open. Z-index above content but below modals.

**When to auto-open:** Always open on Step 2 entry. Stays in last state for Steps 3 and 4.

### Option B — MedFlow-style block cards (secondary choice)

MedFlow renders reasoning as vertical stacked "blocks" — one block per pipeline node — each with a colored left border indicating status (running = blue pulse, done = green, error = red). Thinking tokens are inside a collapsible inner panel within the block, not a separate accordion.

```
┌─────────────────────────────────────────┐
│ ● DDx Analysis                    ✅    │  ← green left border
│   5 candidates · top: BB91.Z            │
│   ▸ View reasoning (34 tokens)          │
├─────────────────────────────────────────┤
│ ● CPG Routing                     ✅    │  ← green left border
│   1 CPG matched                         │
│   └ Pulmonary-Arterial-HTN(2011) [SEM]  │
├─────────────────────────────────────────┤
│ ● Evidence Retrieval              ❌    │  ← red left border
│   Credits depleted · Retry ↺           │
├─────────────────────────────────────────┤
│ ● Plan Synthesis                  ⏳    │  ← blue pulse border
│   Generating evidence-based plan…       │
└─────────────────────────────────────────┘
```

This is a cleaner visual language than the current numbered-timeline approach and is easier to parse at a glance. The left-border color is the primary signal; the text is secondary.

**Recommendation:** Use Option A (persistent drawer) for the architectural question of *where* it lives, and adopt Option B's block-card visual language *inside* the drawer. This gives you MedFlow's block aesthetics without tying it to Step 2 only.

### Error card — replace raw JSON

Current: dumps raw Python dict string including full URL to ai.studio billing page.

Replace with a structured error card inside the block:

```jsx
// Inside PipelineProgress.jsx, for events with status === 'error'
<div className="mt-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
  <p className="text-sm font-semibold text-red-500 flex items-center gap-2">
    <AlertCircle className="w-4 h-4" /> Evidence Retrieval failed
  </p>
  <p className="text-xs text-red-400 mt-1">{friendlyMessage}</p>
  <button className="mt-2 text-xs text-red-400 underline hover:text-red-300">
    Retry ↺
  </button>
</div>
```

`friendlyMessage` maps error codes:
- 429 → "API quota exhausted. Check billing at AI Studio."
- 401 → "API key invalid or expired."
- 500 → "Upstream model error. Try again in a moment."
- default → "Unexpected error. See console for details."

---

## Step-by-step layout reconstruction

### Step 1 — Data Input (`DataInputSection.jsx`)

**Current:** Single column: MPIS Search → Demographics → Vitals → Clinical Notes

**Reconstruct:**
```
xl: two-column grid (activate at 1280px only — not lg:)

Left col (xl:col-span-5):
  MPIS Search
  → on patient found: Demographics card + Past Medical History + Current Medications (read-only)

Right col (xl:col-span-7):
  Vitals Grid
  Clinical Notes textarea

Below xl: MPIS result collapses into accordion above the vitals form
```

**Why xl: not lg::** Clinic hardware is commonly 1366px wide. `lg:` (1024px) causes the vitals grid to wrap uncomfortably inside a `col-span-7`.

---

### Step 2 — Diagnosis (`DiagnosisSection.jsx`)

**Current:** `lg:col-span-5` trace + `lg:col-span-7` DDx cards (correct structure, wrong trace placement)

**Reconstruct:**
- Keep the `lg:grid-cols-12` split
- Left panel: AI Reasoning Trace (now also the persistent drawer preview — same component, different mount point)
- Right panel: DDx cards — no change needed
- Add "Expand trace" button (top-right of left panel) that pushes the drawer open in full-screen mode
- Error events in the trace must use the new error card format — never raw JSON

**The `pipelineEvents` log must be preserved in AppContext across step changes.** Currently it may clear on step transition — verify and fix if so.

---

### Step 3 — Care Plan (`CarePlanSection.jsx`)

**Current:** Full-width accordion sections (Medications, Investigations, Interventions, Lifestyle)

**Reconstruct:**
```
lg:grid-cols-12 split

Left col (lg:col-span-4): "Clinical Anchor" panel — sticky
  ┌─────────────────────────────┐
  │ Confirmed Diagnosis         │
  │ ICD-11: E11.65 (Type 2 DM) │
  │ ICD-11: E11.40 (Neuropathy) │
  ├─────────────────────────────┤
  │ ⚠ Allergies                 │
  │ [Shellfish] [Penicillin]    │  ← red chips, same as PatientBanner
  ├─────────────────────────────┤
  │ Critical Vitals             │
  │ SBP 165 ↑  HR 110 ↑        │  ← only abnormals, not full grid
  ├─────────────────────────────┤
  │ 🧠 Trace [collapsed]        │  ← tap to open drawer
  └─────────────────────────────┘

Right col (lg:col-span-8): Care Plan (existing accordion sections, no change)
```

The left panel is `sticky top-4` — it doesn't scroll away when the clinician reads through the medication list.

---

### Step 4 — Complete (`OutputSection.jsx`)

**Current:** Summary dump with Download / Print / Share buttons

**Reconstruct — SOAP Document View:**

```
Single column, max-w-3xl centered (this is a document, not a form)

┌──────────────────────────────────────────────────────┐
│ CLINICAL ENCOUNTER NOTE                              │
│ Dr. Tay · Low Jia Qi · 10 May 2026                  │
├──────────────────────────────────────────────────────┤
│ S  SUBJECTIVE                                        │
│    Chief complaint: [from case]                      │
│    History: [from case]                              │
├──────────────────────────────────────────────────────┤
│ O  OBJECTIVE                                         │
│    Vitals: BP 165/95 · HR 110 · Temp 37.1°C         │
├──────────────────────────────────────────────────────┤
│ A  ASSESSMENT                                        │
│    Primary: E11.65 — Type 2 DM Uncontrolled + PN    │
│    Alternate: E11.40 — Diabetic Peripheral Neuropathy│
│    CPG Evidence: Malaysian CPG T2DM 2020 §4.2       │
├──────────────────────────────────────────────────────┤
│ P  PLAN                                              │
│    Medications: [accepted items only]                │
│    Investigations: [accepted items only]             │
│    Lifestyle: [accepted items only]                  │
│    Follow-up: [date]                                 │
│    Unresolved: [list if any]                         │
└──────────────────────────────────────────────────────┘

Floating action bar (fixed bottom, full width):
[ Export to EMR ]  [ Print Patient Instructions ]  [ Sign & Close ]
```

The SOAP structure maps directly to existing data:
- `S` ← `PatientCase.chief_complaint` + `history`
- `O` ← `PatientCase.vitals`
- `A` ← `TreatmentPlan.icd_primary` + `icd_alternates` + `cpg_source` from first recommendation
- `P` ← `carePlan.medications` + `investigations` + `interventions` (accepted items only)

---

## PatientBanner — final spec

Already in the existing UI (screenshot confirms it). Two gaps to fix:

1. **Allergy chips must be red** — current screenshot shows `Shellfish` in a neutral chip. Needs `bg-red-100 text-red-700 border border-red-300` (or dark equivalent `bg-red-900/40 text-red-300 border-red-700/50`).
2. **Banner must persist across ALL steps** — verify it doesn't unmount on step transitions inside `ConsultationLayout` / `App.jsx`.

---

## Implementation priority

| # | Change | Files | Effort | Clinical impact |
|---|---|---|---|---|
| 1 | Fix allergy chip color in PatientBanner | `PatientBanner.jsx` or header component | 15 min | Safety-critical |
| 2 | Replace raw JSON error with error card in PipelineProgress | `PipelineProgress.jsx` | 1 h | UX — stops patient anxiety |
| 3 | Persistent AI Reasoning Trace drawer (Option A) | New `TraceDrawer.jsx` + AppContext state for `traceOpen` | 3 h | Core differentiator |
| 4 | Step 3 split-screen with Clinical Anchor panel | `CarePlanSection.jsx` | 2 h | Prescribing safety |
| 5 | Step 4 SOAP document view + floating action bar | `OutputSection.jsx` | 2 h | EMR handoff polish |
| 6 | Step 1 two-column at xl: breakpoint | `DataInputSection.jsx` | 3 h | Ergonomic (lower priority) |

---

## What NOT to change

- The `pipelineEvents` ordered log — it's the right data structure; don't flatten it
- The `DDxResult` probability sorting — highest first is correct
- The CPG badge row with match-type colors (exact/parent/range/semantic) — already good
- The `PlanSummary` sidebar in `CarePlanSection` — already well-designed
