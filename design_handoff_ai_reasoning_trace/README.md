# Handoff: AI Reasoning Trace Redesign

## Overview

This is a redesign of the `PipelineProgress` component rendered inside `TraceDrawer.jsx` in the MHNexus doctor UI. The goal is to make the AI reasoning chain readable by a clinician — not just a developer. The redesign replaces a dense, tree-connector developer-log style with a proper **vertical timeline** layout, clear card hierarchy, and progressive disclosure of technical details.

The redesigned component covers the full pipeline: DDx Analysis → Clinician Override → CPG Routing → Evidence Retrieval.

---

## About the Design Files

The file `AI Reasoning Trace Redesign.html` in this bundle is a **high-fidelity HTML/React prototype** — a design reference, not production code. Your task is to **recreate this design inside the existing MHNexus React codebase** (`CPG/frontend/doctor-ui/src/`), specifically by refactoring `PipelineProgress.jsx` and `TraceDrawer.jsx` using the existing design system, Tailwind classes, and component patterns already in the repo.

Do **not** ship the HTML file directly. Use it as a pixel reference.

---

## Fidelity

**High-fidelity.** Colors, typography, spacing, interactions, and copy are all final and should be matched precisely. The existing design system (`mhnexus-design.css`, Tailwind config) already contains all the tokens used.

---

## Target Files to Modify

```
src/components/sections/PipelineProgress.jsx   ← main component to refactor
src/components/shared/TraceDrawer.jsx          ← drawer shell (minor changes)
```

The data structures fed into `PipelineProgress` (from `AppContext` via `pipelineEvents`, `pipelineThinking`, `pipelineSummary`) do **not** need to change. All changes are purely visual/layout.

---

## Design System Tokens (from `mhnexus-design.css`)

All values are already defined as CSS variables. Use them — do not hardcode hex values.

| Token | Value | Usage |
|---|---|---|
| `--accent-primary` | `#14b8a6` (teal-500) | ICD codes, teal accents |
| `--primary-700` | `#0f766e` | ICD code text |
| `--primary-50/100/200` | teal scale | Rank #1 circle bg, evidence badges |
| `--success` / `success-soft` | `#22c55e` / `#dcfce7` | Complete stage dots, applied CPG rows |
| `--warning` / `warning-soft` | `#f59e0b` / `#fef3c7` | Override banner, re-rank strip, amber line |
| `--danger` / `danger-soft` | `#ef4444` / `#fee2e2` | Excluded CPG rows, ↓ movement badges |
| `--info` (blue) | `#3b82f6` / `#dbeafe` | Search query callout, condition chips |
| `--indigo-*` | `#4f46e5` series | Trace panel header (matches existing TraceDrawer) |
| `--slate-*` | full scale | All neutrals, backgrounds, borders |
| `--font-sans` | `'Geist'` | All text |
| `--font-mono` | `'Geist Mono'` | ICD codes, score values |
| `--radius` / `--radius-sm` | `12px` / `8px` | Card and row border radius |
| `--shadow-sm` / `--shadow` | tinted slate | Card hover shadows |

---

## Layout: Timeline Structure

The panel body is now a **vertical timeline**. Every stage and the clinician override node sit on a shared left rail.

```
Panel header (indigo bg)
│
├─ tl-item: DDx / Diagnosis Ranking        ← green check dot
│    │  [Search query callout]
│    │  [Condition chips]
│    │  [Candidate cards × N]
│    │
├─ tl-item: Clinician Override             ← amber pencil dot
│    │  [Override banner with code chips]
│    │
├─ tl-item: Guideline Matching             ← green check dot
│    │  [Applied CPG rows]
│    │  [Under-evidenced warning?]
│    │  [Excluded toggle]
│    │
└─ tl-item: Evidence Retrieved             ← green check dot (no line below)
     [AI questions accordion]
     [Standard checks accordion]
     [Summary line]
```

### Timeline Rail CSS

```css
/* Left rail column */
.tl-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 46px;          /* fixed, holds dot + line */
  flex-shrink: 0;
  padding-top: 16px;    /* aligns dot with stage title baseline */
}

/* Stage/override dot */
.tl-dot {
  width: 24px; height: 24px;
  border-radius: 50%;
  border: 1.5px solid;
  display: flex; align-items: center; justify-content: center;
  position: relative; z-index: 1;
}
.tl-dot.done     { background: dcfce7; border-color: #bbf7d0; color: #16a34a; }
.tl-dot.override { background: #fef3c7; border-color: #fde68a; color: #d97706; }

/* Connecting line */
.tl-line {
  width: 2px; flex: 1; min-height: 16px;
  background: #bbf7d0;   /* green-200 */
  margin-top: 4px; border-radius: 1px;
}
.tl-line.amber { background: #fde68a; }   /* override → CPG segment */

/* Right content area */
.tl-right {
  flex: 1; min-width: 0;
  padding-right: 18px;
}
```

The **last timeline item** (Evidence) renders no `.tl-line` below its dot.

---

## Component: Stage Header

Each stage header is a clickable row that collapses/expands the stage body. The dot is in the left rail, **not** inside the header element.

```
[Stage title]                    [meta text]  [chevron]
"Diagnosis Ranking"              "top: BD11.2"   ▾
```

- Font: 14px, `font-weight: 600`, `--slate-800`
- Meta: 12px, `--slate-400`
- Chevron: `ChevronDown` / `ChevronUp`, 13px, `--slate-400`
- Padding: `14px 0 12px` (no horizontal — handled by `.tl-right`)
- Cursor: pointer, no border between stages (timeline handles separation)

---

## Component: Search Query Callout

Appears at the top of the DDx stage body.

- Background: `--info` blue-50 (`#eff6ff`)
- Border: 1px `#dbeafe` (blue-100), `border-radius: var(--radius)` (12px)
- Padding: `10px 12px`
- Label: 10px, uppercase, `letter-spacing: 0.06em`, `font-weight: 600`, blue-600 (`#2563eb`), with 🔍 search icon
- Text: 13px, `--slate-700`, `line-height: 1.5`, quoted

---

## Component: Condition Chips

Displayed beneath the search callout as a flex-wrap row.

- Background: blue-50 (`#eff6ff`)
- Border: 1px blue-200 (`#bfdbfe`), `border-radius: 999px`
- Text: 12px, `font-weight: 500`, blue-700 (`#1d4ed8`)
- Padding: `4px 10px`
- Gap: `6px`
- Section eyebrow label above: 10px, uppercase, indigo-600, `letter-spacing: 0.06em`

---

## Component: Candidate Card

Each DDx candidate is a card. Show top 3 by default; "Show N more candidates" toggle reveals the rest.

### Card structure
```
┌──────────────────────────────────────────────────────┐
│  [rank circle]  [ICD code]                  [±badge] │
│                 [Full diagnosis name]                 │
│                 [Evidence rank #N → AI rank #N]       │
├──────────────────────────────────────────────────────┤
│  Re-ranked: [plain-English reason]      (amber strip) │  ← only if override_reason
├──────────────────────────────────────────────────────┤
│  ∨ Score breakdown                                    │  ← collapsed toggle
└──────────────────────────────────────────────────────┘
```

### Rank circle
- Size: 30×30px, `border-radius: 50%`
- Rank #1: teal-50 bg, teal-200 border, teal-700 text
- Rank #2–3: slate-100 bg, slate-200 border, slate-600 text
- Rank #4+: slate-50 bg, slate-200 border, slate-400 text
- Font: 12px `font-weight: 700`

### ICD code
- Font: `var(--font-mono)`, 13px, `font-weight: 600`, teal-600 (`#0d9488`)
- `letter-spacing: 0.02em`

### Full diagnosis name
- **Never truncate** — allow wrapping to 2 lines
- Font: 13px, `--slate-700`, `line-height: 1.4`

### Rank context line
- Font: 11px, `--slate-400`
- Text: `"Evidence rank #N → AI rank #N"`

### Movement badge (top-right)
| Value | Background | Text color |
|---|---|---|
| `↑N` (moved up) | `#dcfce7` (green-100) | `#15803d` (green-700) |
| `↓N` (moved down) | `#fee2e2` (red-100) | `#b91c1c` (red-700) |
| `=` (unchanged) | `--slate-100` | `--slate-500` |

- Font: 11px, `font-weight: 700`, `border-radius: 999px`, padding `2px 6px`

### Re-rank reason strip (amber, conditional)
- Only rendered when `override_reason` is non-null
- Background: amber-50 (`#fffbeb`)
- Border-top: 1px amber-100 (`#fef3c7`)
- Left border: 3px solid amber-600 (`#d97706`)
- Padding: `8px 12px`
- Label "Re-ranked:" — 11px, `font-weight: 600`, amber-600
- Reason text — 12px, amber-700 (`#b45309`), `line-height: 1.5`
- Use `formatOverrideReason()` (already exists) to convert the reason string to plain English

### Score breakdown (collapsed)
- Toggle button: 11px, `--slate-400`, shows "Score breakdown" / "Hide score breakdown" with chevron
- Border-top: 1px `--slate-100`
- When open: shows `base`, `+incl`, `−excl`, `= evidence` values in `font-mono`
- Background: `--slate-50`

### Card shell
- Border: 1px `--slate-200`, `border-radius: var(--radius)` (12px)
- Hover: subtle `box-shadow`
- Gap between cards: `7px`

---

## Component: Clinician Override Banner

Sits between DDx and CPG as its own timeline node (amber dot with edit icon).

- Background: amber-50, border: 1px amber-200, left-border: 3px solid amber-600
- Border-radius: `var(--radius)` (12px)
- Label: "Clinician confirmed diagnoses" — 11px, `font-weight: 600`, amber-700
- Code chips: `border-radius: 999px`, white bg, amber-200 border
  - ICD code part: `font-mono`, 11px, `font-weight: 600`, teal-600
  - Name part: 11px, `--slate-600`
- Gap between chips: `5px`

---

## Component: CPG Stage — Applied Guidelines

```
APPLIED GUIDELINES   ← eyebrow label, green-600, uppercase
✓  Heart-Failure (5th Edition)                    exact
✓  T2-Diabetes-Mellitus (6th Edition)             exact
✓  Obesity-Management (2023)                      exact
```

Each row:
- Background: green-50 (`#f0fdf4`), border: 1px green-100, `border-radius: 8px`
- Checkmark icon: green-600
- Name: 13px, `--slate-700`
- Badge "exact": green-100 bg, green-200 border, green-700 text, 11px, `border-radius: 999px`
- Gap between rows: `5px`

### Under-evidenced warning
- Same structure as a row but amber-50 bg, amber-100 border
- Warning triangle icon: amber-600
- Text: 12px, amber-700

### Excluded guidelines (collapsed toggle)
- Default: collapsed behind a button showing "N guidelines excluded — click to see why"
- Button: slate-50 bg, slate-200 border, 12px, `--slate-500`, full width, space-between flex
- When expanded: red-50 bg rows, red-100 border, each showing CPG name + reason text
- Badge "excluded": red-100 bg, 11px, red-700

---

## Component: Evidence Retrieval — Questions Accordion

Two labelled groups: **AI-generated questions** and **Standard checks always run**.

### Group label
- 10px, uppercase, `letter-spacing: 0.06em`, `--slate-500`
- Count pill: 10px, `font-weight: 600`, slate-100 bg, slate-500 text, `border-radius: 999px`
- Icons: sparkles (AI questions), book (standard checks)
- Gap above second group: `12px`

### Question row (accordion item)
- Border: 1px slate-100, `border-radius: 8px`, white bg
- Content: chevron icon + **full question text** (never truncate) + passage badge
- Question text: 12px, `--slate-600`, `line-height: 1.55`
- Passage badge: `+N new passages` — teal-50 bg, teal-100 border, teal-700, 11px, `font-weight: 600`
- When expanded: shows a subtle explanation in slate-50 bg strip
- Gap between rows: `3px`

### Summary line
- Centered, 12px, `font-weight: 600`, `--slate-600`, slate-50 bg, slate-100 border
- Text: `"20 guideline passages retrieved · duplicates removed"`
- Margin-top: `8px`

---

## Interactions & Behavior

| Interaction | Behavior |
|---|---|
| Click stage header | Collapse/expand stage body (animated, spring easing) |
| Click "Show N more candidates" | Reveal hidden lower-ranked candidates inline |
| Click candidate "Score breakdown" | Toggle score detail row below each card |
| Click "N guidelines excluded" | Expand excluded CPG list |
| Click evidence question row | Expand passage detail strip |
| Panel header click | Collapse entire panel |

All collapse/expand transitions: `200ms`, `cubic-bezier(0.4, 0, 0.2, 1)`.

---

## State Management

These new local state variables are needed inside `PipelineProgress`:

```js
const [ddxOpen, setDdxOpen]   = useState(true);
const [cpgOpen, setCpgOpen]   = useState(true);
const [evOpen, setEvOpen]     = useState(true);
const [showAllCandidates, setShowAllCandidates] = useState(false);
const [exclOpen, setExclOpen] = useState(false);
// Per-candidate score breakdown open state:
const [scoreOpenMap, setScoreOpenMap] = useState({});
// Per-evidence-question open state:
const [evOpenMap, setEvOpenMap] = useState({});
```

No changes needed to `AppContext`, `pipelineEvents`, or backend data structures.

---

## Dark Mode

The component is used inside `TraceDrawer` which already handles dark mode via `useTheme()`. All dark mode variants for the new classes follow the same pattern as existing dark overrides in `PipelineProgress.jsx`:

| Element | Dark override |
|---|---|
| Timeline line | `rgba(22, 163, 74, 0.22)` |
| Timeline amber line | `rgba(217, 119, 6, 0.22)` |
| Done dot | `rgba(22,163,74,.15)` bg, `rgba(22,163,74,.3)` border, `#86efac` text |
| Override dot | `rgba(217,119,6,.15)` bg, `rgba(217,119,6,.3)` border, `#fcd34d` text |
| Candidate card | `rgba(255,255,255,.03)` bg, `rgba(255,255,255,.08)` border |
| ICD code | `#2dd4bf` (teal-400) |
| Search callout | `rgba(59,130,246,.08)` bg, `rgba(59,130,246,.2)` border |

Follow the existing pattern in `PipelineProgress.jsx` — all colors use the `isDark` ternary pattern already established.

---

## Files in This Bundle

| File | Purpose |
|---|---|
| `README.md` | This document — full implementation spec |
| `AI Reasoning Trace Redesign.html` | **Hi-fi reference prototype** — open in a browser to see the final design. All interactions (expand/collapse, show more, dark mode toggle) are live. |

---

## Implementation Checklist

- [ ] Refactor `PipelineProgress.jsx` timeline layout (left rail + right content per stage)
- [ ] Remove tree connectors (`├`, `└`) from all sub-step renders
- [ ] Add `CandidateCard` sub-component (rank circle, full name, movement badge, re-rank strip, score toggle)
- [ ] Add "Show N more candidates" toggle (show top 3 by default)
- [ ] Update `OverrideBanner` to be a proper timeline node (amber dot)
- [ ] Update CPG section: split applied vs excluded, collapsed by default
- [ ] Update Evidence section: two labelled groups, full question text, accordion
- [ ] Verify dark mode for all new elements
- [ ] Verify `collapsed` prop still works (DiagnosisSection uses it)
- [ ] Smoke-test with live `pipelineEvents` data from a real analysis run
