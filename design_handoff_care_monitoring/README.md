# Handoff: Care & Monitoring Tab Redesign

## Overview
This redesign replaces the three stacked collapsible `<Section>` cards in the `tab === 'care'` block of `CarePlanSection.jsx` with a single, cleaner panel that uses a **segmented control** to switch between Procedures, Monitoring, and Lifestyle sub-sections. Each sub-section renders its data as a structured, column-aligned table — eliminating the "wall of text" and long vertical scroll.

## Fidelity
**High-fidelity.** The HTML reference files are pixel-accurate prototypes with final colours, typography, spacing, and interactions. Recreate the UI as faithfully as possible using the existing Tailwind + React + GlassCard patterns in the codebase.

---

## Target File
**`src/components/sections/CarePlanSection.jsx`**

Locate the `tab === 'care'` block (search for `{/* ── CARE & MONITORING`). Replace the three stacked `<Section>` components with a single `<CareMonitoringPanel>` component. Implement `CareMonitoringPanel` as a new function component within the same file (or in a new `CareMonitoringPanel.jsx` — your call).

---

## Data Field Mapping

The component receives `carePlan` as a prop (already available in scope). Fields map as follows:

### Procedures (`carePlan.interventions`)
| Design field | Source field | Notes |
|---|---|---|
| `name` | `i.name` | Short procedure name — may need trimming if the AI puts a long description in `name` |
| `detail` (Rationale column) | `i.rationale` | Always visible, de-emphasised |
| `note` (expandable AI reason) | `i.reasoning` *(new optional field)* | If not present in the CPG output yet, hide the chevron button entirely for that row |
| `urgency` | `i.urgency` | Maps to urgency pill colour — see tokens below |

### Monitoring (`carePlan.monitoring`)
| Design field | Source field | Notes |
|---|---|---|
| `test` | `i.parameter \|\| i.task` | Test name (existing pattern from `ListRow`) |
| `sub` (secondary label) | — | Optional sub-label (e.g. "eGFR / creatinine") — add to schema if needed |
| `schedule` | `i.schedule` | Rendered as teal text, no icon |
| `target` | `i.target` | Show `—` if null/undefined |

### Lifestyle (`carePlan.lifestyle`)
| Design field | Source field | Notes |
|---|---|---|
| `goal` | `i.goal` | Rendered in card body |
| `category` | `i.category` | Drives the icon and eyebrow label |

---

## Component Structure

```
<CareMonitoringPanel carePlan={carePlan} dispatch={dispatch} />
  └── GlassCard
        ├── Header row  (icon chip + "Care & Monitoring" + total count badge)
        ├── Segmented control  (Procedures · Monitoring · Lifestyle)
        └── Active sub-section
              ├── Procedures  → column table + per-row chevron
              ├── Monitoring  → column table
              └── Lifestyle   → 2-column card grid
```

---

## Detailed Specs

### Card wrapper
Use the existing `<GlassCard>` component — no changes needed.

### Section header
```
display: flex, alignItems: center, gap: 12px
padding: 18px 22px 16px
borderBottom: 1px solid var(--slate-200)
```
- Teal icon chip: `w-9 h-9 rounded-xl bg-[var(--accent-primary)]/12 text-teal-700 flex items-center justify-center`
- Title: `text-[17px] font-semibold tracking-tight text-slate-800`
- Count badge: `text-[12px] font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-500`

### Segmented control
```
mt-4 flex gap-1 bg-slate-100 p-1 rounded-xl
```
Each tab button (inactive):
```
flex-1 flex items-center justify-center gap-2 py-2 px-2.5 rounded-[9px]
text-[13.5px] font-semibold text-slate-500 bg-transparent cursor-pointer
transition-all duration-150
```
Active tab:
```
bg-white shadow-sm text-slate-800 rounded-[9px]
```
Tab count chip:
- Active: `bg-[var(--accent-primary)]/12 text-teal-700`
- Inactive: `bg-white text-slate-400`

### Table header row
```
display: grid, gap: 16px, paddingBottom: 10px
borderBottom: 1px solid var(--slate-200)
fontSize: 10.5px, fontWeight: 700, letterSpacing: .06em, textTransform: uppercase, color: #94a3b8
```

### Procedure rows
Grid columns: `22px 168px 1fr 110px 30px`  
Row padding: `14px 0`, borderBottom: `1px solid #f1f5f9` (slate-100), last row no border

- **Checkbox** (col 1): see ReviewBox spec below
- **Name** (col 2): `text-[14.5px] font-semibold text-slate-800 leading-snug`
- **Rationale** (col 3): `text-[12.5px] text-slate-500 leading-relaxed` — always visible, de-emphasised
- **Urgency pill** (col 4, right-aligned): see UrgencyPill spec below
- **Chevron button** (col 5): 26×26px, `rounded-lg border border-slate-200`, hover/open state: `border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-teal-700`. Icon rotates 180° when open.

**Expanded AI reason panel** (below row, not a new grid row):
```
marginLeft: 206px  (aligns under Rationale column)
padding: 11px 14px
bg: #f8fafc, border: 1px solid #e2e8f0
borderLeft: 2.5px solid var(--accent-primary)
borderRadius: 10px, marginBottom: 14px
```
- Label: `text-[10px] font-bold tracking-widest uppercase text-teal-700 mb-1`
- Body: `text-[12.5px] text-slate-700 leading-relaxed`

### UrgencyPill colours
| Value | Background | Text |
|---|---|---|
| `"Today"` | `#fee2e2` | `#b91c1c` |
| `"This admission"` | `#fef3c7` | `#b45309` |
| Anything else | `#f1f5f9` | `#64748b` |

Style: `text-[11px] font-semibold px-2.5 py-0.5 rounded-full whitespace-nowrap`

### Monitoring rows
Grid columns: `22px 150px 1fr 172px`

- **Test** (col 2): `text-[14.5px] font-semibold text-slate-800`
- **Sub** (secondary, optional): `text-[11.5px] text-slate-400 mt-0.5`
- **Schedule** (col 3): `text-[13px] font-medium text-teal-700` — plain text, NO clock icon
- **Target** (col 4): `text-[12.5px] text-slate-700` if present, `text-slate-400` if null (render `—`)

### Lifestyle cards
Grid: `grid-cols-2 gap-3`

Each card:
```
flex gap-3 p-3.5 rounded-2xl bg-[#fcfdfd]
border border-slate-200 (border-[var(--accent-primary)] when reviewed)
transition-colors duration-150
```
- **Icon chip**: 32×32px, `rounded-xl bg-[var(--accent-primary)]/12 text-teal-700`
- **Category eyebrow**: `text-[10.5px] font-bold tracking-wider uppercase text-teal-700 mb-1`
- **Goal text**: `text-[13px] text-slate-600 leading-snug`
- **ReviewBox**: top-right corner of flex row

### ReviewBox (review checkbox)
```
width: 20px, height: 20px, borderRadius: 6px
unchecked: border 1.5px solid #e2e8f0, bg white
checked:   bg var(--accent-primary), no border
```
Checkmark: Lucide `<Check size={13} strokeWidth={3} color="white" />`

---

## State

```jsx
const [activeTab, setActiveTab] = useState('proc');        // 'proc' | 'mon' | 'life'
const [reviewedIds, setReviewedIds] = useState(new Set()); // ids the doctor has ticked
const [expandedId, setExpandedId] = useState(null);        // which procedure row is open
```

`reviewedIds` and `expandedId` are local UI state — no need to push to `dispatch` unless you want persistence.

---

## Icons (Lucide)
All already imported in `CarePlanSection.jsx`:
- Header: `Activity` (or `Stethoscope` for Procedures sub-section icon)
- Procedures tab: `Stethoscope`
- Monitoring tab: `Activity`
- Lifestyle tab: `Heart`
- Chevron: `ChevronDown` (rotate via `style={{ transform: open ? 'rotate(180deg)' : 'none' }}`)
- Check in ReviewBox: `Check`

For Lifestyle card icons per category (add to the component):
```js
const LIFESTYLE_ICONS = {
  Exercise:   Dumbbell,
  Diet:       Salad,
  Lifestyle:  Heart,
  Adherence:  Pill,
  Weight:     Activity,
};
```

---

## Design Tokens (CSS vars already in `mhnexus-design.css`)
| Token | Value | Usage |
|---|---|---|
| `--accent-primary` | `rgb(20,184,166)` | Teal — borders, icons, schedule text |
| `--radius-lg` | `20px` | GlassCard |
| `--radius-md` | `16px` | — |
| `--font-sans` | `'Geist'` | All text |
| `--slate-100` | `#f1f5f9` | Segmented bg, hover rows |
| `--slate-200` | `#e2e8f0` | Borders, table header underline |
| `--slate-400` | `#94a3b8` | Table headers, faint text |
| `--slate-500` | `#64748b` | De-emphasised body text |
| `--slate-800` | `#1e293b` | Primary titles |

---

## Files in This Bundle
| File | Purpose |
|---|---|
| `Care Monitoring Options.html` | Full interactive prototype — open in browser to see final design |
| `v1.jsx` | The `CareMonitoringPanel` component (React+Babel, assigned to `window`) |
| `shared.jsx` | Primitive components — `SectionHead`, `ReviewBox`, `UrgencyPill`, `ScheduleText`, `IconChip` |
| `icons.jsx` | Inline SVG icon stubs (not needed — use Lucide from the codebase) |
| `data.js` | Mock cardiac data used in the prototype (not needed — use real `carePlan` prop) |
| `mhnexus-design.css` | Design tokens (already in the codebase at `src/mhnexus-design.css`) |

> **Note:** The `.jsx` files in this bundle use React+Babel standalone syntax and assign to `window`. They are **design references only** — do not import them directly into the Vite/React app. Recreate the component natively using Tailwind classes and the existing codebase patterns (GlassCard, Lucide icons, `useTheme`, etc.).

---

## Implementation Checklist
- [ ] Create `CareMonitoringPanel` component (in `CarePlanSection.jsx` or new file)
- [ ] Replace the `tab === 'care'` block with `<CareMonitoringPanel carePlan={carePlan} dispatch={dispatch} />`
- [ ] Map `carePlan.interventions` → Procedures table
- [ ] Map `carePlan.monitoring` → Monitoring table
- [ ] Map `carePlan.lifestyle` → Lifestyle card grid
- [ ] Wire `activeTab` state to segmented control
- [ ] Wire `reviewedIds` state to ReviewBox checkboxes
- [ ] Wire `expandedId` state to procedure row chevrons
- [ ] Check `i.reasoning` field availability in CPG output — hide chevron if field is absent
- [ ] Test in dark mode (`isDark` from `useTheme()` — swap all hardcoded hex colours for dark variants)
- [ ] Verify the total count in the tab bar (`careCount`) still updates correctly
