# SULAM — "Medical Detective" Booth UI — Implementation Plan

> **Audience:** Sonnet (implementing engineer)
> **Goal:** Build a simple, standalone educational UI for a secondary-school community-service booth that shows students how an **agentic RAG** clinical assistant processes a patient case in real time — and why RAG + agentic beats a plain generative LLM.
> **Hard constraint:** Do **NOT** modify anything inside `CPG LLM/Doctor UI/`. Reuse the existing backend API endpoints only. All new code lives in `CPG LLM/SULAM/`.

---

## 1. Context & What Already Exists

### 1.1 The backend (do not change)
A FastAPI server (`CPG LLM/agent/api.py`) runs on **`http://localhost:8058`**. Start it the same way the team already does (the Doctor UI points at this port via `VITE_CLINICAL_API_URL`).

The clinical pipeline has 5 stages; the booth UI only needs **Stage 2 → 3 → 4 → 5**:

| Stage | Name | What it does |
|-------|------|--------------|
| 2 | DDx Analysis | LLM generates differential diagnoses (ICD-11 codes) from the case |
| 3 | CPG Routing | Matches the AI's **top ICD-11 code(s)** to relevant Clinical Practice Guidelines |
| 4 | Evidence Retrieval | RAG: retrieves relevant guideline chunks |
| 5 | Plan Synthesis | Generates an evidence-based care plan, every recommendation cites a CPG |

### 1.2 Relevant endpoint (already built — reuse as-is)

**`POST /clinical/plan/stream`** — Server-Sent Events. This is the **only** backend endpoint the booth uses.
Request body:
```json
{
  "case": {
    "chief_complaint": "string (required, non-empty)",
    "history": "string | null",
    "age": "int | null",
    "sex": "M | F | other | null",
    "comorbidities": [],
    "current_medications": [],
    "allergies": [],
    "vitals": { "sbp": 165, "dbp": 95, "hr": 110 },
    "severity_staging": {},
    "staged_comorbidities": []
  }
}
```
SSE events emitted (frames are `\n\n`-separated, lines `event: <type>` + `data: <json>`):
- `stage_update` → `{ stage, name, status: "running"|"complete"|"error", detail, data? }`
- `thinking_delta` → `{ stage, node, chunk }` (live LLM "thinking" tokens — Stage 2 only)
- `sub_step` → `{ stage, detail, badge? }`
- `safety_review` → SafetyReport JSON
- `final_result` → **`ClinicalPlanResponse`** JSON (see below)
- `error` → `{ detail }`
- `done` → `{}`

**`ClinicalPlanResponse`** shape (the `final_result` payload):
```json
{
  "treatment_plan": {
    "icd_primary": "string",
    "icd_alternates": ["string"],
    "summary": "string",
    "recommendations": [
      { "type": "pharmacological|procedure|lifestyle|referral|investigation",
        "intervention": "string", "action": "start|stop|change|continue|contraindicated",
        "evidence_grade": "string|null", "cpg_source": "string (citation)",
        "rationale": "string", "contraindications_checked": [] }
    ],
    "monitoring": [ { "parameter": "...", "schedule": "...", "target": "...", "cpg_ref": "..." } ],
    "red_flags": ["string"],
    "follow_up": ["string"],
    "unresolved_questions": ["string"]
  },
  "ddx": [ { "code": "ICD-11", "title": "string", "similarity": 0.0-1.0, "reasoning": ["string"], "inclusion_match": "..." } ],
  "cpgs_matched": ["CPG Management of Hypertension", "..."],
  "elapsed_ms": 1234.5,
  "stage_errors": [],
  "safety_report": { ... } | null
}
```

> We do **not** use `/clinical/plan/resynthesize/stream`, `/chat`, or `/search`. The booth always uses the AI's top-1 DDx code — keep the flow linear and simple.

### 1.3 Reference implementation (read-only — learn from, do not edit)
- `CPG LLM/Doctor UI/src/lib/clinicalApi.js` — the SSE fetch+parse logic. **Copy this pattern** into SULAM.
- `CPG LLM/Doctor UI/src/lib/clinicalMappers.js` — maps `ClinicalPlanResponse` → UI shapes. **Copy/simplify** into SULAM.
- `CPG LLM/Doctor UI/src/components/sections/PipelineProgress.jsx` — stage list `[{stage:2,label:'DDx Analysis'},{3,'CPG Routing'},{4,'Evidence Retrieval'},{5,'Plan Synthesis'}]`.
- `CPG LLM/Doctor UI/src/context/AppContext.jsx` (lines ~248–276) — how the stream callbacks drive state.

---

## 2. What We're Building

A **new, separate Vite + React app** at `CPG LLM/SULAM/`. **Three tabs** in the left sidebar, deliberately simple and visual for a teenage audience. The whole app reuses the screenshot's layout language (left sidebar nav, serif display headings, mono uppercase labels, soft card surfaces) but re-themed **blue + heath** (see §6).

### Tab A — "Medical Detective" (the main interactive booth UI)
The hero of the booth. Flow:
1. **Left panel:** four sample patient **case cards** (see §3). Each card shows name/age + a one-line "chief complaint" blurb + a small condition tag.
2. **The moment a student clicks a case card, the pipeline on the right immediately starts** — no separate "Investigate" button. Clicking a case = POST `/clinical/plan/stream`.
3. **Right panel — the animated "chain of thought" pipeline.** This is the UX centrepiece; spend the polish budget here. Four vertically-stacked **StepCards**, each animating `pending → running → complete` from real `stage_update` events:
   - **Step 1 – "Reading the clues"** (Stage 2, DDx): a `ThinkingBox` types out the `thinking_delta` chunks live (monospace, cursor blink) — literally showing the AI think — then collapses into the differential list with the top diagnosis highlighted as the **"prime suspect"**.
   - **Step 2 – "Choosing the right guidebooks"** (Stage 3, CPG Routing): show "AI picked ICD-11 code `XXX` → opening these guidelines" with the `cpgs_matched` list animating in as chips. Caption this as **the agentic step** — the AI decides what to look up.
   - **Step 3 – "Reading the real guidelines"** (Stage 4, Evidence Retrieval): show "Searching the guideline documents…" → animated chunk counter. Caption as **the RAG step** — grounding in real documents, not memory.
   - **Step 4 – "Writing the care plan"** (Stage 5, Plan Synthesis): render the `treatment_plan` — summary + recommendations, **each with its CPG citation visibly shown** ("📖 Source: …"). This is the payoff: every answer is traceable.
   - Connect the four cards with an animated vertical "flow line" that fills/pulses as each stage completes — reinforces the chain-of-thought feel.
4. While streaming, a small live counter (imported "clues", % processed) can echo the screenshot's right-rail stat cards — optional polish.
5. Backend unreachable → friendly inline error in the pipeline area, no white screen.

### Tab B — "How It Works" (Agentic RAG architecture flow chart)
Replaces the old "Why Not ChatGPT" idea. A **static, animated architecture diagram** of our system — no API calls. Build it as a hand-laid-out flow chart (absolutely-positioned nodes + SVG/`div` connector lines), **glassmorphism style** (frosted translucent cards, soft blur, subtle borders, layered depth — works well on the blue/heath background).
Nodes / regions to show, left-to-right:
1. **Patient Case** (input) →
2. **The Agent** (centre, emphasised — give it a distinct glow/badge: "decides, routes, retrieves, synthesises") →
3. branching to the two data stores: **Vector DB** (guideline chunks / embeddings) and **Knowledge Graph DB** (ICD-11 ↔ CPG ↔ drug relationships) →
4. **5-Stage Pipeline** strip: DDx → CPG Routing → Evidence Retrieval → Plan Synthesis → Safety Critic →
5. **Cited Care Plan** (output).
- Animate connector lines with a flowing dash / pulse so the diagram feels alive.
- Short mono-label captions on each node. Keep copy plain — this tab *explains*, it doesn't need to be clever.
- Make clear **where the agent sits** and that it *orchestrates* both DBs — that's the teaching point.

### Tab C — "Knowledge Graph" (live-feel graph visualisation)
Illustrates "we use **two databases**, not just one." **Use a mocked/hardcoded graph** — accuracy does not matter, the point is to show the concept and that it animates.
- Hardcode a small graph dataset in `src/data/mockGraph.js`: ~20–30 nodes across types — `CPG` nodes (e.g. "CPG Hypertension"), `ICD` nodes (e.g. "BA00 Essential Hypertension"), `Drug` nodes (e.g. "Amlodipine"), `Symptom` nodes — with typed edges (`treats`, `indicated_for`, `coded_as`, `presents_with`).
- Render as a force-directed-style graph. **Simplest reliable approach: a lightweight self-contained force layout** (small custom physics loop, or a tiny lib like `d3-force` — pick one; no heavy 3D libs). Nodes coloured by type, edges labelled.
- "Live-feel" effect: stagger-reveal nodes/edges on mount (e.g. add a node every ~150 ms) and let the layout settle with gentle motion, so it *looks* like a real-time stream even though it's local. A subtle "● streaming from graph DB" mono badge sells it.
- No backend dependency — must always work at the booth.

---

## 3. The 4 Sample Cases — FINAL CONTENT

Put these in `src/data/sampleCases.js`. Chosen for relatability (conditions students have heard of) and clean mapping to ingested CPGs. Input fields are intentionally **light** — only `chief_complaint` is required by the backend validator; everything else is "good enough."

```js
export const SAMPLE_CASES = [
  {
    id: 'htn-01',
    displayName: 'Mr. Tan, 58',
    tag: 'High Blood Pressure',
    blurb: 'Headaches and dizziness for 2 weeks',
    caseBody: {
      chief_complaint: 'Recurring headaches, dizziness, and occasional blurred vision for the past two weeks',
      history: '58-year-old man, smoker, office worker. Father had a stroke. Not on any medication.',
      age: 58, sex: 'M',
      comorbidities: [], current_medications: [], allergies: [],
      vitals: { sbp: 168, dbp: 102, hr: 88 },
      severity_staging: {}, staged_comorbidities: [],
    },
  },
  {
    id: 'hf-01',
    displayName: 'Mdm. Lee, 65',
    tag: 'Heart Failure',
    blurb: 'Breathless when walking, swollen ankles',
    caseBody: {
      chief_complaint: 'Shortness of breath on mild exertion and swelling of both ankles for one month',
      history: '65-year-old woman. Gets tired easily, cannot lie flat at night. History of high blood pressure.',
      age: 65, sex: 'F',
      comorbidities: [], current_medications: [], allergies: [],
      vitals: { sbp: 138, dbp: 86, hr: 102 },
      severity_staging: {}, staged_comorbidities: [],
    },
  },
  {
    id: 'stroke-01',
    displayName: 'Mr. Raj, 60',
    tag: 'Stroke',
    blurb: 'Sudden weakness in right arm and slurred speech',
    caseBody: {
      chief_complaint: 'Sudden weakness of the right arm and slurred speech that started two hours ago',
      history: '60-year-old man. Known high blood pressure. Symptoms came on suddenly while watching TV.',
      age: 60, sex: 'M',
      comorbidities: [], current_medications: [], allergies: [],
      vitals: { sbp: 176, dbp: 98, hr: 90 },
      severity_staging: {}, staged_comorbidities: [],
    },
  },
  {
    id: 'lipid-01',
    displayName: 'Mr. Wong, 45',
    tag: 'High Cholesterol',
    blurb: 'High cholesterol found at a health screening',
    caseBody: {
      chief_complaint: 'No symptoms — routine health screening showed high cholesterol levels',
      history: '45-year-old man, overweight, sedentary job, eats out often. Father has heart disease.',
      age: 45, sex: 'M',
      comorbidities: [], current_medications: [], allergies: [],
      vitals: { sbp: 132, dbp: 84, hr: 78 },
      severity_staging: {}, staged_comorbidities: [],
    },
  },
];
```
> If a case's DDx comes back weak during testing, tweak the `chief_complaint` wording toward a more classic presentation — do **not** add comorbidity/drug data (those subsystems aren't fully built and aren't needed here).

---

## 4. Directory Layout to Create

```
CPG LLM/SULAM/
├── README.md
├── package.json
├── vite.config.js
├── index.html
├── .env.example                # VITE_CLINICAL_API_URL=http://localhost:8058
└── src/
    ├── main.jsx
    ├── App.jsx                  # left sidebar + 3-tab router (Detective / How It Works / Knowledge Graph)
    ├── theme.css                # blue + heath design tokens (see §6)
    ├── index.css                # base + layout styles
    ├── data/
    │   ├── sampleCases.js       # the 4 cases from §3
    │   └── mockGraph.js         # hardcoded nodes + edges for Tab C
    ├── lib/
    │   ├── detectiveApi.js      # copy of clinicalApi.js stream logic, trimmed
    │   └── mappers.js           # copy/simplify of clinicalMappers.js
    └── components/
        ├── Sidebar.jsx          # nav, themed like the screenshot
        ├── detective/
        │   ├── DetectiveView.jsx     # Tab A — orchestrates case-click → stream → state
        │   ├── CaseCard.jsx          # one of the 4 case cards (click = start pipeline)
        │   ├── Pipeline.jsx          # the 4 StepCards + animated flow line
        │   ├── StepCard.jsx          # pending/running/complete card
        │   ├── ThinkingBox.jsx       # streams thinking_delta text w/ blinking cursor
        │   ├── DiagnosisList.jsx     # DDx, top = "prime suspect"
        │   └── CarePlanCard.jsx      # treatment plan + visible CPG citations
        ├── architecture/
        │   └── ArchitectureView.jsx  # Tab B — glassmorphism flow chart
        └── graph/
            └── GraphView.jsx         # Tab C — animated mock knowledge graph
```

---

## 5. Implementation Steps (in order)

### Step 1 — Scaffold
- `cd "CPG LLM/SULAM"`. `package.json` deps: `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `lucide-react` (icons), and **one** small graph helper for Tab C (`d3-force`, or implement a tiny force loop yourself). Plain CSS only — no Tailwind, no Supabase, no jsPDF.
- `vite.config.js`: just the react plugin (copy Doctor UI's).
- `index.html`, `src/main.jsx`, `src/App.jsx` with the left-sidebar + 3-tab layout.
- `.env.example`: `VITE_CLINICAL_API_URL=http://localhost:8058`. Read via `import.meta.env.VITE_CLINICAL_API_URL` with `|| 'http://localhost:8058'` fallback.

### Step 2 — Theme (`src/theme.css`) — see §6 for tokens.

### Step 3 — Sample cases — paste §3 into `src/data/sampleCases.js`.

### Step 4 — API layer (`src/lib/detectiveApi.js`)
- Copy the SSE parsing structure from `Doctor UI/src/lib/clinicalApi.js` `runClinicalPlanStream` **verbatim in structure**, but: input is just a `caseBody` object (already in `PatientCase` shape — no patientState mapping needed); body is `{ case: caseBody }`; POST to `${BASE}/clinical/plan/stream`; callbacks: `onStageUpdate`, `onThinkingChunk`, `onSubStep` (optional), resolve with `final_result`.
- No resynthesize / chat / search.

### Step 5 — Mappers (`src/lib/mappers.js`)
- Copy `mapDdxToDiagnosis` + `mapTreatmentPlanToCarePlan` from `Doctor UI/src/lib/clinicalMappers.js`. Trimming unused fields is fine; copying as-is is lower-risk.

### Step 6 — Tab A (Detective)
- `DetectiveView` state: `selectedCaseId`, `steps` keyed by stage (2,3,4,5) each `{status, detail}`, `thinkingText`, `finalResult`, `error`.
- `CaseCard` onClick → reset state → call `detectiveApi`. Wire: `onStageUpdate` → set `steps[stage]`; `onThinkingChunk` → append to `thinkingText`; `final_result` → store + render `DiagnosisList` + `CarePlanCard`.
- Student-facing relabels (do not show raw "Stage 2"): Step 1 "Reading the clues", Step 2 "Choosing the right guidebooks", Step 3 "Reading the real guidelines", Step 4 "Writing the care plan".
- Animation budget goes here: StepCard status transitions, ThinkingBox typing/cursor, the connecting flow line filling per completed stage, chips animating in for `cpgs_matched`.
- `CarePlanCard`: group recommendations simply (medications / lifestyle / referrals / monitoring); **every item shows its `cpg_source` as a visible source badge**.

### Step 7 — Tab B (Architecture flow chart)
- Static, no API. Absolutely-positioned glassmorphism nodes + SVG connector lines with an animated flowing-dash. Layout per §2 Tab B. Emphasise the **Agent** node. Animate connectors so it feels alive.

### Step 8 — Tab C (Knowledge Graph)
- `src/data/mockGraph.js`: ~20–30 typed nodes + typed edges (see §2 Tab C).
- `GraphView`: force-directed render; nodes coloured by type; stagger-reveal on mount for a "streaming" feel; "● streaming from graph DB" mono badge. No backend.

### Step 9 — README.md
- How to start the backend (port 8058), `npm install`, `npm run dev`, note it must run alongside the backend, note Tabs B & C work offline.

---

## 6. Theme — Blue + Heath (purple-grey)

Re-skin the screenshot's visual language; **keep the structure** (left sidebar, serif display headings, mono uppercase micro-labels, soft rounded cards). Define as CSS custom properties in `theme.css`:

```css
:root {
  /* surfaces */
  --bg:            #f4f6fb;   /* cream-ish cool off-white */
  --surface:       #ffffff;
  --surface-soft:  #eef1f8;   /* soft card fill (was the green tint) */
  --sidebar:       #1b2436;   /* deep blue-charcoal (was near-black) */

  /* brand — blue */
  --primary:       #2f5fd0;   /* deep blue (replaces the green) */
  --primary-soft:  #dce6fb;   /* light blue tint for active nav / chips */
  --primary-ink:   #1c3c8c;

  /* heath accent — muted lavender-grey */
  --heath:         #8b86a8;
  --heath-soft:    #e7e4ef;
  --heath-ink:     #4a4566;

  /* text */
  --ink:           #161a23;
  --ink-soft:      #5b6273;
  --line:          #e3e6ee;

  /* status */
  --ok:            #2f5fd0;   /* keep status cues in-palette */
  --warn:          #b4843a;
  --err:           #c0433f;
}
```
- **Active nav item / "READY"-style chips:** `--primary-soft` fill, `--primary-ink` text (mirrors the green pill in the screenshot).
- **Glassmorphism (Tab B):** `background: rgba(255,255,255,0.55); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.6); box-shadow: 0 8px 32px rgba(27,36,54,0.12);` layered over the `--bg`.
- **Fonts — adapt, don't copy blindly:** screenshot uses a heavy serif display + a mono for labels. Use a free, self-hostable pairing: **display serif** → `Fraunces` or `Instrument Serif`; **mono labels** → `Geist Mono` (already a Doctor UI dep — but install fresh in SULAM, don't import across folders) or `JetBrains Mono`; **body** → `Geist Sans` or system UI. Install via `@fontsource/*` packages in SULAM's own `package.json`.

---

## 7. Guardrails / Definition of Done

- [ ] Nothing under `CPG LLM/Doctor UI/` is modified, added, or deleted. (Check folder before finishing — repo is **not** under git, so verify by inspection/timestamps.)
- [ ] No backend files (`agent/`, `ddx/`, …) modified — SULAM only **calls** the existing `/clinical/plan/stream` endpoint.
- [ ] `npm run dev` in `SULAM/` launches a working app on a different port than Doctor UI.
- [ ] Tab A: clicking any of the 4 case cards **immediately** starts the pipeline; the 4 StepCards animate pending→running→complete from real `stage_update` events; `thinking_delta` text streams visibly; DDx + care plan render with visible CPG citations.
- [ ] Tab B: glassmorphism architecture flow chart renders with animated connectors; the Agent node is clearly emphasised; works with backend offline.
- [ ] Tab C: animated mock knowledge graph renders with stagger-reveal; works with backend offline.
- [ ] Backend unreachable → Tab A shows a friendly inline error, no crash/white screen.
- [ ] Blue + heath theme applied consistently; serif display + mono labels; SULAM has its own font deps (no cross-folder imports).

## 8. Testing
- Start backend on 8058, run `npm run dev`, open in a browser.
- Click through all 4 cases; confirm streaming animation + final results + citations.
- Open Tabs B and C with the backend stopped; confirm both still render and animate.
- Stop the backend, click a case; confirm friendly error state.
- Inspect `Doctor UI/` — confirm zero changes.

## 9. Open Questions (resolve while building if they come up)
- Final wording of the 4 `chief_complaint` strings may need a clinician sanity-check, but the §3 versions are good to build with.
- Booth display resolution / touch-screen vs mouse (affects card + button sizing) — design for a large landscape screen, generous tap targets.
