# Step 09B — AI Transparency Panel (Chain of Thought)

## What this step achieves

**Transparency is a first-class feature of CPG LLM**, not a debug overlay.

During analysis the clinician sees a live timeline of the AI's reasoning. After analysis it persists as a collapsible "AI Reasoning Trace" card in the Diagnosis step — so the clinician can always review *why* the AI ranked AF first, which CPG was consulted, and which evidence chunks drove the recommendations.

```
┌─ AI Reasoning Trace ─────────────────────────── 8.2s · [▲ Collapse] ─┐
│                                                                         │
│  01  DDx Analysis                                    ✓  5 candidates   │
│  │   Top: BC81.3 Persistent AF                                         │
│  │   [🧠 View reasoning ▼]   ← streams Gemini thinking tokens live    │
│  │                                                                      │
│  02  CPG Routing                                      ✓  2 CPGs        │
│  │   ├  CPG AF Management (2nd Ed.)        exact match                 │
│  │   └  Heart Failure (5th Ed.)            parent match                │
│  │                                                                      │
│  03  Evidence Retrieval                               ✓  12 chunks     │
│  │   ├  "rate control strategies in AF"              6 hits            │
│  │   ├  "anticoagulation CHA₂DS₂-VASc score"        4 hits            │
│  │   └  "cardioversion criteria persistent AF"       4 hits → 2 new   │
│  │   12 unique chunks after deduplication                              │
│  │                                                                      │
│  04  Plan Synthesis                                  ✓  conf. 0.87    │
│      Generated in 8,234 ms                                             │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│  Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs     │
└─────────────────────────────────────────────────────────────────────────┘
```

**Estimated time for Sonnet:** 20–28 min  
**Estimated cost:** ~$0.22  
**Sonnet thinking:** ON, low budget

---

## What changes vs Step 09

| Layer | Step 09 | Step 09B |
|---|---|---|
| Stage 3 sub-steps | ❌ one row | ✅ per-CPG rows with match type |
| Stage 4 sub-steps | ❌ one row | ✅ per-query rows with hit counts |
| Visual design | icons + plain text | numbered timeline with tree connectors |
| Panel lifetime | disappears after analysis | **persists as collapsed card in DiagnosisSection** |
| Summary line | ❌ | ✅ "8.2s · 5 ICD codes · 2 CPGs · 12 chunks" |
| Footer | ❌ | ✅ "Powered by Gemini 2.5 Flash · Malaysian CPGs" |

---

## Read these files first

- `agent/clinical_stages.py` — `stage_3_route` (line 232) and `stage_4_retrieve` (line 301): add `emit=None`
- `agent/clinical_workflow.py` — `run_clinical_workflow_streaming`: thread `emit` into stages 3 and 4
- `Doctor UI/src/components/sections/PipelineProgress.jsx` — full redesign
- `Doctor UI/src/components/sections/DiagnosisSection.jsx` — add persistent collapsed trace card
- `Doctor UI/src/context/AppContext.jsx` — replace `pipelineStages` with `pipelineEvents` ordered log; do NOT clear on step change

---

## Part A — Backend: sub-step events from Stages 3 and 4

### A1. Add `emit=None` to `stage_3_route` in `agent/clinical_stages.py`

Replace the existing `stage_3_route`:

```python
async def stage_3_route(
    ddx: list[DDxResult],
    top_k_codes: int = 2,
    top_k_cpgs: int = 3,
    emit=None,                      # async callable | None
) -> list[CPGDocRef]:
    """Map the top DDx ICD-11 codes to CPG document sets."""
    all_refs: dict[str, CPGDocRef] = {}

    for result in ddx[:top_k_codes]:
        refs = await route_icd_to_cpgs(result.code, top_k=top_k_cpgs)
        for ref in refs:
            if ref.cpg_name not in all_refs:
                all_refs[ref.cpg_name] = ref
                if emit:
                    await emit("sub_step", {
                        "stage": 3,
                        "detail": f"{ref.cpg_name}",
                        "badge": ref.match_type,          # "exact" | "parent" | "range" | "semantic"
                        "status": "complete",
                    })

    return list(all_refs.values())[:top_k_cpgs]
```

### A2. Add `emit=None` to `stage_4_retrieve` in `agent/clinical_stages.py`

Replace the existing `stage_4_retrieve`:

```python
async def stage_4_retrieve(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    queries_per_code: int = 3,
    chunks_per_query: int = 5,
    emit=None,                      # async callable | None
) -> list[ChunkResult]:
    """Generate targeted queries and retrieve scoped evidence chunks."""
    if not cpgs:
        logger.warning("stage_4_retrieve: no CPGs to scope search — returning empty")
        return []

    all_doc_ids = [doc_id for cpg in cpgs for doc_id in cpg.document_ids]

    if emit:
        await emit("sub_step", {
            "stage": 4,
            "detail": f"Generating {queries_per_code} targeted queries…",
            "status": "running",
        })

    queries = await _generate_retrieval_queries(case, ddx, cpgs, n=queries_per_code)

    seen_chunk_ids: set[str] = set()
    all_chunks: list[ChunkResult] = []

    for query in queries:
        results = await vector_search_tool(VectorSearchInput(
            query=query,
            limit=chunks_per_query,
            document_id_filter=all_doc_ids,
        ))
        new_chunks = 0
        for chunk in results:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)
                new_chunks += 1
        if emit:
            total = len(results)
            await emit("sub_step", {
                "stage": 4,
                "detail": f'"{query[:60]}{"…" if len(query) > 60 else ""}"',
                "badge": f"{new_chunks} new / {total} hits",
                "status": "complete",
            })

    all_chunks.sort(key=lambda c: c.score, reverse=True)
    final = all_chunks[:20]

    if emit:
        await emit("sub_step", {
            "stage": 4,
            "detail": f"{len(final)} unique chunks after deduplication",
            "status": "complete",
        })

    return final
```

### A3. Thread `emit` into stages 3 and 4 in `agent/clinical_workflow.py`

In `run_clinical_workflow_streaming`, update the two stage calls that currently don't pass `emit`:

```python
# Stage 3 — change this line:
cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3)
# to:
cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3, emit=emit)

# Stage 4 — change this line:
evidence = await stage_4_retrieve(case, ddx, cpgs)
# to:
evidence = await stage_4_retrieve(case, ddx, cpgs, emit=emit)
```

### A4. Add `confidence` to the Stage 5 complete event

In `run_clinical_workflow_streaming`, update the Stage 5 complete emit to include confidence from the plan:

```python
await emit("stage_update", {
    "stage": 5, "name": "Plan Synthesis", "status": "complete",
    "detail": f"Care plan ready · {elapsed_ms:.0f} ms total",
    "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, 'confidence') and treatment_plan.confidence else None,
})
```

---

## Part B — Frontend

### B1. Replace `pipelineStages` with `pipelineEvents` in `AppContext.jsx`

The key change: events accumulate in order and are **never cleared between steps** — only on a new analysis or RESET.

#### initialState changes
```js
// Remove:
pipelineStages: [],
pipelineThinking: {},

// Add:
pipelineEvents: [],      // ordered log: [...stage_updates, ...sub_steps]
pipelineThinking: {},    // unchanged
pipelineSummary: null,   // { elapsed_ms, ddxCount, cpgCount, chunkCount } set on final_result
```

#### Reducer changes

```js
// Remove SET_PIPELINE_STAGE, CLEAR_PIPELINE_STAGES

// Add:
case 'APPEND_PIPELINE_EVENT':
  return { ...state, pipelineEvents: [...state.pipelineEvents, action.payload] };

case 'SET_PIPELINE_SUMMARY':
  return { ...state, pipelineSummary: action.payload };

case 'RESET_PIPELINE':
  return { ...state, pipelineEvents: [], pipelineThinking: {}, pipelineSummary: null };

// APPEND_THINKING_CHUNK stays unchanged
```

#### analyzeAssessment changes

```js
dispatch({ type: 'RESET_PIPELINE' });   // instead of CLEAR_PIPELINE_STAGES

// stage_update and sub_step callbacks both append to pipelineEvents:
(stageUpdate) => {
  dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...stageUpdate, eventType: 'stage_update' } });
},
(thinkingDelta) => {
  dispatch({ type: 'APPEND_THINKING_CHUNK', payload: { node: thinkingDelta.node, chunk: thinkingDelta.chunk } });
},
```

Also handle `sub_step` events inside `runClinicalPlanStream` — add a third callback `onSubStep`:

```js
// In analyzeAssessment, add third callback:
const response = await runClinicalPlanStream(
  state.patient, state.vitals, state.clinicalNotes, state.mpisData,
  (stageUpdate) => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...stageUpdate, eventType: 'stage_update' } }),
  (thinkingDelta) => dispatch({ type: 'APPEND_THINKING_CHUNK', payload: { node: thinkingDelta.node, chunk: thinkingDelta.chunk } }),
  (subStep)      => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...subStep, eventType: 'sub_step' } }),
);
```

On `final_result`, extract the summary:
```js
// After resolve(payload) in runClinicalPlanStream — add onFinalResult callback or
// derive in analyzeAssessment from the response:
dispatch({
  type: 'SET_PIPELINE_SUMMARY',
  payload: {
    elapsed_ms: response.elapsed_ms,
    ddxCount: response.ddx?.length || 0,
    cpgCount: response.cpgs_matched?.length || 0,
    chunkCount: null,   // not in response; sub_steps provide count
  }
});
```

#### Context value — replace exposed state

```js
// Remove: pipelineStages
// Add:
pipelineEvents:   state.pipelineEvents,
pipelineSummary:  state.pipelineSummary,
pipelineThinking: state.pipelineThinking,
```

### B2. Update `clinicalApi.js` — add `onSubStep` callback

In `runClinicalPlanStream`, add the third parameter and dispatch it:

```js
export async function runClinicalPlanStream(
  patientState, vitals, clinicalNotes, mpisData,
  onStageUpdate,
  onThinkingChunk,
  onSubStep,          // NEW
) {
  // ... existing fetch setup unchanged ...

  // In the frame parsing loop, add:
  else if (eventType === 'sub_step' && onSubStep) onSubStep(payload);
}
```

### B3. Complete redesign of `PipelineProgress.jsx`

This is a full replacement of the file. The component now accepts `pipelineEvents` and `pipelineThinking` and renders a numbered vertical timeline.

```jsx
import React, { useRef, useEffect, useState } from 'react';
import {
  CheckCircle, AlertCircle, Loader2, Circle,
  BrainCircuit, ChevronDown, ChevronUp,
} from 'lucide-react';
import { GlassCard } from '../shared';
import { useTheme } from '../../context/ThemeContext';

const STAGE_DEFS = [
  { stage: 2, num: '01', label: 'DDx Analysis',      hasThinking: true  },
  { stage: 3, num: '02', label: 'CPG Routing',        hasThinking: false },
  { stage: 4, num: '03', label: 'Evidence Retrieval', hasThinking: false },
  { stage: 5, num: '04', label: 'Plan Synthesis',     hasThinking: false },
];

const MATCH_TYPE_COLORS = {
  exact:    'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  parent:   'bg-blue-500/20   text-blue-400    border-blue-500/30',
  range:    'bg-blue-500/20   text-blue-400    border-blue-500/30',
  semantic: 'bg-amber-500/20  text-amber-400   border-amber-500/30',
};

function StatusDot({ status, num }) {
  const base = 'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 shrink-0 transition-all duration-300';
  if (status === 'complete') return (
    <div className={`${base} bg-emerald-500/20 border-emerald-500 text-emerald-400`}>
      <CheckCircle className="w-4 h-4" />
    </div>
  );
  if (status === 'error') return (
    <div className={`${base} bg-red-500/20 border-red-500 text-red-400`}>
      <AlertCircle className="w-4 h-4" />
    </div>
  );
  if (status === 'running') return (
    <div className={`${base} bg-[var(--accent-primary)]/20 border-[var(--accent-primary)] text-[var(--accent-primary)] animate-pulse`}>
      <Loader2 className="w-4 h-4 animate-spin" />
    </div>
  );
  return (
    <div className={`${base} bg-slate-800/50 border-slate-600 text-slate-500`}>
      {num}
    </div>
  );
}

function Badge({ text, colorClass }) {
  if (!text) return null;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${colorClass || 'bg-slate-700/50 text-slate-400 border-slate-600/50'}`}>
      {text}
    </span>
  );
}

function ThinkingDropdown({ text, isStreaming }) {
  const scrollRef = useRef(null);
  useEffect(() => {
    if (isStreaming && scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [text, isStreaming]);

  if (!text) return null;
  return (
    <div
      ref={scrollRef}
      className="mt-2 max-h-44 overflow-y-auto rounded-lg p-3 text-xs font-mono leading-relaxed
        bg-[var(--accent-primary)]/5 text-slate-300 border border-[var(--accent-primary)]/20"
    >
      {text}
      {isStreaming && (
        <span className="inline-block w-1.5 h-3 ml-0.5 bg-[var(--accent-primary)] animate-pulse align-middle" />
      )}
    </div>
  );
}

/**
 * Props:
 *   pipelineEvents:  ordered array of { eventType, stage, name?, label?, status, detail, badge? }
 *   pipelineThinking: { [nodeName]: string }
 *   summary:          { elapsed_ms, ddxCount, cpgCount } | null
 *   isLive:           bool — true while analysis is running (controls animation)
 *   collapsed:        bool — when true, show only the summary header (for DiagnosisSection)
 *   onToggle:         () => void — toggle collapsed state
 */
export function PipelineProgress({
  pipelineEvents = [],
  pipelineThinking = {},
  summary = null,
  isLive = false,
  collapsed = false,
  onToggle,
}) {
  const { isDark } = useTheme();
  const [thinkingOpen, setThinkingOpen] = useState(false);

  // Build per-stage view
  const stageData = STAGE_DEFS.map((def) => {
    const stageEvents = pipelineEvents.filter((e) => e.stage === def.stage);
    const stageUpdate = [...stageEvents].reverse().find((e) => e.eventType === 'stage_update');
    const subSteps = stageEvents.filter((e) => e.eventType === 'sub_step');
    const status = stageUpdate?.status || 'pending';
    const detail = stageUpdate?.detail || '';
    const badge  = stageUpdate?.badge || null;
    return { ...def, status, detail, badge, subSteps };
  });

  const thinkingText = pipelineThinking['DDx Re-rank'] || '';
  const isThinkingStreaming = isLive && stageData[0]?.status === 'running' && thinkingText.length > 0;

  // Summary line
  const summaryText = summary
    ? `${(summary.elapsed_ms / 1000).toFixed(1)}s · ${summary.ddxCount} ICD codes · ${summary.cpgCount} CPGs`
    : isLive ? 'Analysing…' : '';

  return (
    <GlassCard className={`overflow-hidden transition-all duration-300 ${isLive ? 'border-[var(--accent-primary)]/30 border' : ''}`}>
      {/* Header */}
      <div
        className={`flex items-center justify-between px-5 py-3 ${onToggle ? 'cursor-pointer select-none' : ''}`}
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {isLive && <span className="w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />}
            <span className={`text-xs font-semibold uppercase tracking-widest ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              AI Reasoning Trace
            </span>
          </div>
          {summaryText && (
            <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              {summaryText}
            </span>
          )}
        </div>
        {onToggle && (
          collapsed
            ? <ChevronDown className="w-4 h-4 text-slate-500" />
            : <ChevronUp   className="w-4 h-4 text-slate-500" />
        )}
      </div>

      {/* Timeline body */}
      {!collapsed && (
        <div className="px-5 pb-5">
          <div className="space-y-0">
            {stageData.map((stage, stageIdx) => {
              const isLast = stageIdx === stageData.length - 1;
              const isActive = stage.status === 'running';

              return (
                <div key={stage.stage} className="flex gap-4">
                  {/* Left: dot + vertical line */}
                  <div className="flex flex-col items-center">
                    <StatusDot status={stage.status} num={stage.num} />
                    {!isLast && (
                      <div className={`w-0.5 flex-1 my-1 min-h-4 transition-colors duration-500
                        ${stage.status === 'complete' ? 'bg-emerald-500/40' : 'bg-slate-700/50'}`}
                      />
                    )}
                  </div>

                  {/* Right: content */}
                  <div className="flex-1 pb-4 min-w-0">
                    {/* Stage header row */}
                    <div className="flex items-center justify-between pt-1 mb-1">
                      <span className={`text-sm font-semibold ${
                        isActive      ? (isDark ? 'text-white'        : 'text-slate-800') :
                        stage.status === 'complete' ? (isDark ? 'text-slate-200'  : 'text-slate-700') :
                        stage.status === 'error'    ? 'text-red-400' :
                        (isDark ? 'text-slate-500' : 'text-slate-400')
                      }`}>
                        {stage.label}
                      </span>
                      <div className="flex items-center gap-2 ml-3 shrink-0">
                        {stage.badge && (
                          <Badge text={stage.badge}
                            colorClass="bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                          />
                        )}
                        {stage.status === 'complete' && !stage.badge && stage.detail && (
                          <span className="text-xs text-slate-500">{stage.detail.split('·').pop()?.trim()}</span>
                        )}
                      </div>
                    </div>

                    {/* Detail text */}
                    {stage.detail && stage.status !== 'pending' && (
                      <p className={`text-xs mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {stage.detail}
                      </p>
                    )}

                    {/* Sub-steps (CPG rows for Stage 3, query rows for Stage 4) */}
                    {stage.subSteps.length > 0 && (
                      <div className="mt-1.5 space-y-1 pl-3 border-l border-slate-700/50">
                        {stage.subSteps.map((sub, i) => {
                          const isLast = i === stage.subSteps.length - 1;
                          const connector = isLast ? '└' : '├';
                          const matchColor = sub.badge ? (MATCH_TYPE_COLORS[sub.badge] || MATCH_TYPE_COLORS.semantic) : null;
                          return (
                            <div key={i} className="flex items-center gap-2">
                              <span className="text-slate-600 font-mono text-xs shrink-0">{connector}</span>
                              <span className={`text-xs truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                                {sub.detail}
                              </span>
                              {sub.badge && (
                                <Badge text={sub.badge} colorClass={matchColor} />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Thinking dropdown — DDx stage only */}
                    {stage.hasThinking && thinkingText && (
                      <div className="mt-2">
                        <button
                          onClick={() => setThinkingOpen((o) => !o)}
                          className="flex items-center gap-1.5 text-xs text-[var(--accent-primary)] hover:opacity-80 transition-opacity"
                        >
                          <BrainCircuit className="w-3.5 h-3.5" />
                          {thinkingOpen ? 'Hide reasoning' : 'View reasoning'}
                          {thinkingOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>
                        {thinkingOpen && (
                          <ThinkingDropdown text={thinkingText} isStreaming={isThinkingStreaming} />
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className={`mt-2 pt-3 border-t text-xs ${isDark ? 'border-slate-700/50 text-slate-600' : 'border-slate-200 text-slate-400'}`}>
            Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs
          </div>
        </div>
      )}
    </GlassCard>
  );
}
```

### B4. Update `DataInputSection.jsx` — live panel during analysis

```jsx
import { PipelineProgress } from './PipelineProgress';

// Replace the old <PipelineProgress stages=... thinking=...> usage with:
{state.isAnalyzing && (
  <PipelineProgress
    pipelineEvents={state.pipelineEvents}
    pipelineThinking={state.pipelineThinking}
    summary={state.pipelineSummary}
    isLive={true}
  />
)}
```

### B5. Update `DiagnosisSection.jsx` — persistent collapsed trace

Add this block at the top of the `DiagnosisSection` return, before the existing AI Suggested Diagnosis card:

```jsx
import { PipelineProgress } from './PipelineProgress';
import { useApp } from '../../context/AppContext';

// Inside DiagnosisSection component body:
const { state } = useApp();
const [traceCollapsed, setTraceCollapsed] = React.useState(true);

// In JSX, before the first GlassCard:
{state.pipelineEvents?.length > 0 && (
  <PipelineProgress
    pipelineEvents={state.pipelineEvents}
    pipelineThinking={state.pipelineThinking}
    summary={state.pipelineSummary}
    isLive={false}
    collapsed={traceCollapsed}
    onToggle={() => setTraceCollapsed((c) => !c)}
  />
)}
```

---

## Files changed summary

| File | Change |
|------|--------|
| `agent/clinical_stages.py` | `stage_3_route`: add `emit=None`, emit per-CPG sub_step. `stage_4_retrieve`: add `emit=None`, emit query-gen + per-query + dedup sub_steps |
| `agent/clinical_workflow.py` | Pass `emit` to `stage_3_route` and `stage_4_retrieve` calls |
| `Doctor UI/src/lib/clinicalApi.js` | Add `onSubStep` third callback, dispatch `sub_step` events |
| `Doctor UI/src/context/AppContext.jsx` | Replace `pipelineStages` → `pipelineEvents` + `pipelineSummary`; 3 reducer changes; third callback in `analyzeAssessment` |
| `Doctor UI/src/components/sections/PipelineProgress.jsx` | Full redesign — numbered timeline, sub-steps, tree connectors, collapse toggle, footer |
| `Doctor UI/src/components/sections/DataInputSection.jsx` | Update props to new API |
| `Doctor UI/src/components/sections/DiagnosisSection.jsx` | Add persistent collapsed trace card |

---

## Done criteria

1. `pytest tests/test_streaming.py -v` → all 7 still green (no backend contract changes break existing tests)
2. `pytest tests/test_clinical_stages.py -v` → all 23 still green
3. During analysis: numbered timeline renders with live sub-steps appearing inside Stage 3 (CPG rows) and Stage 4 (query rows)
4. "View reasoning" appears on DDx row and expands thinking text with pulsing cursor
5. After analysis completes and UI moves to Step 2 (Diagnosis): collapsed "AI Reasoning Trace" card visible at top; clicking it expands the full completed timeline
6. Stage 3 CPG badges show match type ("exact" in green, "semantic" in amber)
7. Stage 4 sub-rows show query text (truncated to 60 chars) + "N new / M hits" badge
8. Footer line "Powered by Gemini 2.5 Flash · Evidence grounded in Malaysian CPGs" visible when expanded

---

## Implementation notes

- `pipelineEvents` accumulates ALL events (stage_update + sub_step) in arrival order. The component filters by `eventType` and `stage` to render the timeline. This means Stage 3 sub_steps that arrive between the Stage 3 `running` and `complete` events naturally appear in the right place.
- `RESET_PIPELINE` fires at the START of a new `analyzeAssessment` call, not at step transitions. This is what makes the trace persist into Step 2.
- The `collapsed` prop + `onToggle` pattern is only used by `DiagnosisSection`. During live analysis (`DataInputSection`) the panel is always expanded and `onToggle` is omitted.
- `stage_3_route` emits sub_steps INSIDE the loop as each CPG is found — so they appear one-by-one if the routing takes time per code, not all at once.
- `stage_4_retrieve` emits per-query sub_steps AFTER each `vector_search_tool` call returns — same progressive reveal.
- Existing tests call `stage_3_route` and `stage_4_retrieve` without `emit` → `emit=None` → no behavior change.

---

## Report back

1. Diff summary — lines per file
2. `pytest tests/test_streaming.py -v` + `pytest tests/test_clinical_stages.py -v`
3. Screenshot of the live timeline during analysis showing Stage 4 query sub-rows
4. Screenshot of the collapsed "AI Reasoning Trace" card in DiagnosisSection
5. Any deviations and why
