# Step 09 — SSE Pipeline Streaming + Progress UI (with Thinking Tokens)

## What this step achieves

When the doctor clicks **Analyze**, instead of a blank spinner the UI shows a live 4-stage progress panel. The DDx stage also exposes a **"View reasoning"** accordion identical to MedFlow's `ThinkingDropdown` — Gemini 2.5 Flash's thinking tokens stream character-by-character as it re-ranks ICD candidates.

```
✓  DDx Analysis       "5 candidates · AF ranked #1"   [View reasoning ▼]
                        68-year-old male, palpitations, HR 110 irregular…
                        BC81.3 Persistent AF fits best given age + vitals.
                        BC81.1 Paroxysmal AF cannot be excluded without Holter…
⟳  CPG Routing        "Matching ICD codes to guidelines…"
○  Evidence Retrieval
○  Plan Synthesis
```

**Estimated time for Sonnet:** 15–22 min  
**Estimated cost:** ~$0.18  
**Sonnet thinking setting:** ON, low budget (1024 tokens) — streaming plumbing has enough interleaved state that light thinking prevents wiring mistakes

---

## Context — read these files first

- `agent/clinical_stages.py` — `_llm_rerank_ddx` (line 59) and `stage_2_ddx` (line 155): add optional `emit` param to both
- `agent/clinical_workflow.py` — existing `run_clinical_workflow` (unchanged); add streaming variant alongside
- `agent/api.py` — `POST /clinical/plan` at line 562; add streaming endpoint below it
- `Doctor UI/src/context/AppContext.jsx` — `analyzeAssessment()` at line 190; add streaming path
- `Doctor UI/src/lib/clinicalApi.js` — existing `runClinicalPlan()`; add streaming sibling
- `Doctor UI/src/components/sections/DataInputSection.jsx` — Analyze button section; mount `PipelineProgress` here

**Why `fetch` not `EventSource`:**  
`EventSource` is GET-only. POST body required → use `fetch` + `ReadableStream` to parse SSE frames manually.

---

## Part A — Backend

### A1. Thread `emit` into `_llm_rerank_ddx` and `stage_2_ddx`

**In `agent/clinical_stages.py` — replace `_llm_rerank_ddx` and `stage_2_ddx`**

The only behavior changes:
- `_llm_rerank_ddx` gains an optional `emit` kwarg. When `None` (all existing callers, all tests) → identical to current code. When provided → uses `stream=True` and pipes `delta.reasoning` as `thinking_delta` events.
- `stage_2_ddx` gains optional `emit=None`, passes it through.
- All existing tests pass unchanged because they never pass `emit`.

```python
async def _llm_rerank_ddx(
    case: PatientCase,
    candidates: list[DDxResult],
    emit=None,                      # async callable(event_type, data) | None
) -> list[DDxResult]:
    """
    Re-rank DDx candidates using Gemini 2.5 Flash extended thinking.

    Falls back to original order on any failure.
    When emit is provided, streams thinking tokens as thinking_delta SSE events.
    """
    if not candidates:
        return candidates

    client = openai.AsyncOpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )

    vitals_str = json.dumps(case.vitals) if case.vitals else "none"
    candidate_lines = "\n".join(
        f"  {i+1}. {c.code}  {c.title}  (vector score: {c.similarity:.3f})"
        for i, c in enumerate(candidates)
    )

    prompt = f"""You are a clinical coding expert performing differential diagnosis.

Patient:
- Chief complaint: {case.chief_complaint}
- Age / sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Current medications: {", ".join(case.current_medications) or "none"}
- Allergies: {", ".join(case.allergies) or "none"}
- Vitals: {vitals_str}

Candidate ICD-11 codes (pre-ranked by vector similarity):
{candidate_lines}

Re-rank these candidates based on clinical probability for THIS specific patient.
Apply reasoning about:
- How age, sex, vitals, and comorbidities shift the prior probability of each code
- Whether current medications suggest an existing diagnosis
- Which codes are actionable vs incidental findings

Return a JSON array of objects, ordered from most to least likely. Include ALL candidates.
No markdown fences. Example format:
[
  {{"code": "BC81.3", "confidence": 0.91, "reasoning": "68M irregular pulse HR 110 — persistent AF fits best"}},
  {{"code": "BC81.1", "confidence": 0.72, "reasoning": "Paroxysmal AF cannot be excluded without Holter"}},
  ...
]"""

    try:
        raw_content = ""

        if emit is not None:
            # Streaming path — capture thinking tokens via delta.reasoning
            stream = await client.chat.completions.create(
                model=DDX_RERANK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                stream=True,
                extra_body={
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": DDX_THINKING_BUDGET,
                    }
                },
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # OpenRouter exposes Gemini thinking as delta.reasoning
                # (some models use delta.reasoning_content — check both)
                thinking_chunk = (
                    getattr(delta, "reasoning", None)
                    or getattr(delta, "reasoning_content", None)
                )
                if thinking_chunk:
                    await emit("thinking_delta", {
                        "stage": 2,
                        "node": "DDx Re-rank",
                        "chunk": thinking_chunk,
                    })
                if delta.content:
                    raw_content += delta.content
        else:
            # Non-streaming path — identical to pre-Step-09 behavior
            resp = await client.chat.completions.create(
                model=DDX_RERANK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                extra_body={
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": DDX_THINKING_BUDGET,
                    }
                },
            )
            raw_content = resp.choices[0].message.content

        # Parse re-ranked list (shared by both paths)
        raw = raw_content.strip().strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:]
        ranked = json.loads(raw)

        code_to_result = {c.code: c for c in candidates}
        reranked: list[DDxResult] = []
        for item in ranked:
            code = item.get("code")
            if code and code in code_to_result:
                result = code_to_result[code].model_copy()
                llm_reason = item.get("reasoning", "")
                if llm_reason:
                    result.reasoning = result.reasoning + [f"LLM: {llm_reason}"]
                reranked.append(result)

        seen = {r.code for r in reranked}
        for c in candidates:
            if c.code not in seen:
                reranked.append(c)

        logger.info("DDx re-ranked %d candidates via %s", len(reranked), DDX_RERANK_MODEL)
        return reranked

    except Exception as exc:
        logger.warning("DDx LLM re-rank failed (%s) — using original order", exc)
        return candidates


async def stage_2_ddx(
    case: PatientCase,
    top_k: int = 5,
    rerank: bool = True,
    emit=None,                      # async callable | None; passed through to _llm_rerank_ddx
) -> list[DDxResult]:
    """
    Return top-k ICD-11 differential diagnoses for the patient case.

    Pass 1: vector similarity + morbidity tabulation (search_ddx).
    Pass 2: Gemini 2.5 Flash thinking re-ranks by clinical probability.
    Set rerank=False to skip Pass 2 (e.g. in unit tests or latency-sensitive paths).
    When emit is provided, thinking tokens are streamed as thinking_delta events.
    """
    from ddx.search_ddx import search_ddx

    symptom_text = _build_symptom_text(case)

    fetch_k = top_k * 2 if rerank else top_k
    raw = await search_ddx(symptom_text, top_k=fetch_k)

    results: list[DDxResult] = []
    for r in raw:
        try:
            results.append(
                DDxResult(**{k: v for k, v in r.items() if k in DDxResult.model_fields})
            )
        except Exception as exc:
            logger.warning("Skipping malformed DDx result %r: %s", r, exc)

    if rerank and results:
        results = await _llm_rerank_ddx(case, results, emit=emit)

    return results[:top_k]
```

### A2. Add `run_clinical_workflow_streaming` to `agent/clinical_workflow.py`

Add **after** the existing `run_clinical_workflow`. Do NOT modify the existing function.

```python
async def run_clinical_workflow_streaming(
    case: PatientCase,
    emit,                           # async callable: emit(event_type: str, data: dict) -> None
) -> WorkflowResult:
    """
    Streaming variant of run_clinical_workflow.

    Calls emit() before and after each stage so callers can push SSE events.
    Also threads emit into stage_2_ddx so Gemini thinking tokens stream live.
    Same error-handling contract as run_clinical_workflow.
    """
    t0 = time.monotonic()
    errors: list[str] = []

    # Stage 2 — DDx
    await emit("stage_update", {
        "stage": 2, "name": "DDx Analysis",
        "status": "running", "detail": "Analyzing symptoms and history…"
    })
    try:
        ddx = await stage_2_ddx(case, top_k=5, emit=emit)
        top = ddx[0].code if ddx else "none"
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "complete",
            "detail": f"{len(ddx)} candidates · top: {top}",
            "data": [d.model_dump() for d in ddx],
        })
        logger.info("Stage 2 DDx: %d candidates. Top: %s", len(ddx), top)
    except Exception as e:
        logger.error("Stage 2 DDx failed: %s", e)
        errors.append(f"Stage 2 DDx: {e}")
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "error", "detail": str(e),
        })
        ddx = []

    # Stage 3 — Route
    await emit("stage_update", {
        "stage": 3, "name": "CPG Routing",
        "status": "running", "detail": "Matching ICD codes to clinical guidelines…"
    })
    try:
        cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3)
        names = [c.cpg_name for c in cpgs]
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "complete",
            "detail": f"{len(cpgs)} CPGs matched: {', '.join(names)}",
            "data": names,
        })
        logger.info("Stage 3 Routing: %d CPGs: %s", len(cpgs), names)
    except Exception as e:
        logger.error("Stage 3 Routing failed: %s", e)
        errors.append(f"Stage 3 Routing: {e}")
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "error", "detail": str(e),
        })
        cpgs = []

    # Stage 4 — Retrieve
    await emit("stage_update", {
        "stage": 4, "name": "Evidence Retrieval",
        "status": "running", "detail": "Retrieving relevant guideline chunks…"
    })
    try:
        evidence = await stage_4_retrieve(case, ddx, cpgs)
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "complete",
            "detail": f"{len(evidence)} evidence chunks retrieved",
        })
        logger.info("Stage 4 Retrieval: %d chunks", len(evidence))
    except Exception as e:
        logger.error("Stage 4 Retrieval failed: %s", e)
        errors.append(f"Stage 4 Retrieval: {e}")
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "error", "detail": str(e),
        })
        evidence = []

    # Stage 5 — Synthesize (unrecoverable if it fails)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan…"
    })
    treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms total",
    })
    logger.info("Workflow complete in %.0f ms", elapsed_ms)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
    )
```

### A3. Add `POST /clinical/plan/stream` to `agent/api.py`

Add after the existing `/clinical/plan` endpoint (after line 584).

```python
@app.post("/clinical/plan/stream")
async def clinical_plan_stream(request: ClinicalPlanRequest):
    """
    Run clinical workflow and stream stage progress + DDx thinking as SSE events.

    Events:
      event: stage_update    data: {stage, name, status, detail, data?}
      event: thinking_delta  data: {stage, node, chunk}
      event: final_result    data: ClinicalPlanResponse JSON
      event: error           data: {detail}
      event: done            data: {}
    """
    from .clinical_workflow import run_clinical_workflow_streaming

    async def generate():
        queue: asyncio.Queue = asyncio.Queue()

        async def emit(event_type: str, data: dict):
            await queue.put((event_type, data))

        async def run_workflow():
            try:
                result = await run_clinical_workflow_streaming(request.case, emit)
                final = ClinicalPlanResponse(
                    treatment_plan=result.treatment_plan,
                    ddx=[d.model_dump() for d in result.ddx],
                    cpgs_matched=[c.cpg_name for c in result.cpgs],
                    elapsed_ms=result.elapsed_ms,
                    stage_errors=result.stage_errors,
                )
                await queue.put(("final_result", final.model_dump()))
            except Exception as e:
                logger.error("Streaming clinical plan failed: %s", e)
                await queue.put(("error", {"detail": str(e)}))
            finally:
                await queue.put(None)

        asyncio.create_task(run_workflow())

        while True:
            item = await queue.get()
            if item is None:
                yield f"event: done\ndata: {{}}\n\n"
                break
            event_type, data = item
            yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

---

## Part B — Frontend

### B1. New file: `Doctor UI/src/components/sections/PipelineProgress.jsx`

```jsx
import React, { useRef, useEffect, useState } from 'react';
import { CheckCircle, AlertCircle, Loader2, Circle, BrainCircuit, ChevronDown, ChevronUp } from 'lucide-react';
import { GlassCard } from '../shared';
import { useTheme } from '../../context/ThemeContext';

const STAGE_DEFS = [
  { stage: 2, label: 'DDx Analysis',       hint: 'Analyzing symptoms and history',         hasThinking: true },
  { stage: 3, label: 'CPG Routing',         hint: 'Matching to clinical guidelines',         hasThinking: false },
  { stage: 4, label: 'Evidence Retrieval',  hint: 'Fetching relevant guideline chunks',      hasThinking: false },
  { stage: 5, label: 'Plan Synthesis',      hint: 'Generating evidence-based care plan',     hasThinking: false },
];

function ThinkingDropdown({ text, isStreaming }) {
  const { isDark } = useTheme();
  const scrollRef = useRef(null);

  useEffect(() => {
    if (isStreaming && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [text, isStreaming]);

  if (!text) return null;

  return (
    <div
      ref={scrollRef}
      className={`mt-2 max-h-40 overflow-y-auto rounded-lg p-3 text-xs font-mono leading-relaxed
        ${isDark ? 'bg-[var(--accent-primary)]/5 text-slate-300 border border-[var(--accent-primary)]/20'
                 : 'bg-[var(--accent-primary)]/5 text-slate-600 border border-[var(--accent-primary)]/20'}`}
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
 *   stages:   { stage: int, name: str, status: 'running'|'complete'|'error'|'pending', detail: str }[]
 *   thinking: { [nodeName: str]: string }   accumulated thinking text keyed by node name
 */
export function PipelineProgress({ stages = [], thinking = {} }) {
  const { isDark } = useTheme();
  const [expanded, setExpanded] = useState({});

  const getInfo = (def) =>
    stages.find((s) => s.stage === def.stage) || { status: 'pending', detail: def.hint };

  const iconFor = (status) => {
    switch (status) {
      case 'complete': return <CheckCircle className="w-5 h-5 text-emerald-400" />;
      case 'error':    return <AlertCircle className="w-5 h-5 text-red-400" />;
      case 'running':  return <Loader2 className="w-5 h-5 text-[var(--accent-primary)] animate-spin" />;
      default:         return <Circle className="w-5 h-5 text-slate-500" />;
    }
  };

  return (
    <GlassCard className="p-5 mt-4">
      <p className={`text-xs font-semibold uppercase tracking-widest mb-4
        ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
        AI Pipeline
      </p>
      <div className="space-y-4">
        {STAGE_DEFS.map((def) => {
          const info = getInfo(def);
          const isActive = info.status === 'running';
          const isDone  = info.status === 'complete';
          const thinkingText = def.hasThinking ? (thinking['DDx Re-rank'] || '') : '';
          const hasThinkingContent = thinkingText.length > 0;
          const isThinkingStreaming = isActive && hasThinkingContent;
          const isOpen = expanded[def.stage];

          return (
            <div key={def.stage}>
              <div className="flex items-start gap-3">
                <div className="mt-0.5 shrink-0">{iconFor(info.status)}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <p className={`text-sm font-medium leading-tight
                      ${isActive ? (isDark ? 'text-white' : 'text-slate-800')
                        : isDone  ? (isDark ? 'text-emerald-300' : 'text-emerald-700')
                        : (isDark ? 'text-slate-400' : 'text-slate-500')}`}>
                      {def.label}
                    </p>
                    {def.hasThinking && hasThinkingContent && (
                      <button
                        onClick={() => setExpanded((prev) => ({ ...prev, [def.stage]: !prev[def.stage] }))}
                        className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-md transition-colors
                          ${isDark
                            ? 'text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10'
                            : 'text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10'}`}
                      >
                        <BrainCircuit className="w-3.5 h-3.5" />
                        {isOpen ? 'Hide reasoning' : 'View reasoning'}
                        {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                    )}
                  </div>
                  <p className={`text-xs mt-0.5 truncate ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    {info.detail || def.hint}
                  </p>
                  {def.hasThinking && isOpen && (
                    <ThinkingDropdown text={thinkingText} isStreaming={isThinkingStreaming} />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
```

### B2. Update `Doctor UI/src/lib/clinicalApi.js`

**Extract a shared helper** `buildClinicalPlanBody` from the existing `runClinicalPlan` body-building code. Then add `runClinicalPlanStream`. Do NOT change the existing `runClinicalPlan` behavior.

```js
// ─── shared helper ───────────────────────────────────────────────────────────
function buildClinicalPlanBody(patientState, vitals, clinicalNotes, mpisData) {
  // Move the PatientCase-mapping logic from the existing runClinicalPlan here.
  // runClinicalPlan should call buildClinicalPlanBody(...) instead of repeating it.
  return {
    case: {
      chief_complaint: clinicalNotes || patientState.chiefComplaint || '',
      history: patientState.history || null,
      age: patientState.age || null,
      sex: patientState.gender === 'Male' ? 'M'
         : patientState.gender === 'Female' ? 'F'
         : patientState.gender ? 'other' : null,
      comorbidities: mpisData?.comorbidities || [],
      current_medications: (mpisData?.currentMeds || []).map(
        (m) => (typeof m === 'string' ? m : m.name || m.medication || '')
      ).filter(Boolean),
      allergies: mpisData?.allergies
        ? (typeof mpisData.allergies === 'string'
            ? mpisData.allergies.split(',').map((a) => a.trim()).filter(Boolean)
            : mpisData.allergies)
        : [],
      vitals: vitals ? {
        ...(vitals.bpSystolic  ? { sbp: Number(vitals.bpSystolic) }  : {}),
        ...(vitals.bpDiastolic ? { dbp: Number(vitals.bpDiastolic) } : {}),
        ...(vitals.hr          ? { hr:  Number(vitals.hr) }           : {}),
        ...(vitals.temp        ? { temp: Number(vitals.temp) }         : {}),
        ...(vitals.rr          ? { rr:  Number(vitals.rr) }           : {}),
        ...(vitals.spo2        ? { spo2: Number(vitals.spo2) }         : {}),
        ...(vitals.weight      ? { weight: Number(vitals.weight) }     : {}),
        ...(vitals.height      ? { height: Number(vitals.height) }     : {}),
      } : {},
    },
  };
}

// ─── streaming variant ───────────────────────────────────────────────────────
/**
 * Run the clinical pipeline and stream SSE stage-update + thinking events.
 *
 * @param {Object}   patientState
 * @param {Object}   vitals
 * @param {string}   clinicalNotes
 * @param {Object}   mpisData
 * @param {Function} onStageUpdate   - called with each stage_update payload
 * @param {Function} onThinkingChunk - called with each thinking_delta payload
 * @returns {Promise<ClinicalPlanResponse>}  resolves with the final_result payload
 */
export async function runClinicalPlanStream(
  patientState,
  vitals,
  clinicalNotes,
  mpisData,
  onStageUpdate,
  onThinkingChunk,
) {
  const BASE_URL = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';
  const body = buildClinicalPlanBody(patientState, vitals, clinicalNotes, mpisData);

  const response = await fetch(`${BASE_URL}/clinical/plan/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Clinical stream API error ${response.status}: ${text}`);
  }

  return new Promise((resolve, reject) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const pump = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            reject(new Error('Stream ended without final_result'));
            return;
          }
          buffer += decoder.decode(value, { stream: true });

          // SSE frames are double-newline separated
          const frames = buffer.split('\n\n');
          buffer = frames.pop(); // keep incomplete trailing frame

          for (const frame of frames) {
            if (!frame.trim()) continue;

            let eventType = 'message';
            let dataStr = '';
            for (const line of frame.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
            }
            if (!dataStr) continue;

            let payload;
            try { payload = JSON.parse(dataStr); } catch { continue; }

            if      (eventType === 'stage_update'   && onStageUpdate)    onStageUpdate(payload);
            else if (eventType === 'thinking_delta' && onThinkingChunk)  onThinkingChunk(payload);
            else if (eventType === 'final_result')                        resolve(payload);
            else if (eventType === 'error')                               reject(new Error(payload.detail || 'Pipeline error'));
            else if (eventType === 'done')                                return; // resolve already called
          }
        }
      } catch (err) {
        reject(err);
      }
    };

    pump();
  });
}
```

### B3. Update `Doctor UI/src/context/AppContext.jsx`

#### 3a. Add to `initialState`
```js
pipelineStages: [],     // [{ stage, name, status, detail, data? }]
pipelineThinking: {},   // { [nodeName: string]: string }  accumulated thinking text
```

#### 3b. Add reducer cases in `appReducer`
```js
case 'SET_PIPELINE_STAGE': {
  const { stage } = action.payload;
  const rest = state.pipelineStages.filter((s) => s.stage !== stage);
  return { ...state, pipelineStages: [...rest, action.payload] };
}
case 'CLEAR_PIPELINE_STAGES':
  return { ...state, pipelineStages: [], pipelineThinking: {} };
case 'APPEND_THINKING_CHUNK': {
  const { node, chunk } = action.payload;
  return {
    ...state,
    pipelineThinking: {
      ...state.pipelineThinking,
      [node]: (state.pipelineThinking[node] || '') + chunk,
    },
  };
}
```

#### 3c. Import `runClinicalPlanStream`
```js
import { runClinicalPlan, runClinicalPlanStream } from '../lib/clinicalApi';
```

#### 3d. Replace the try/catch block inside `analyzeAssessment`

Replace the existing `try` block (from `// Call real pipeline` comment to end of try/catch) with:

```js
    try {
      dispatch({ type: 'CLEAR_PIPELINE_STAGES' });

      const response = await runClinicalPlanStream(
        state.patient,
        state.vitals,
        state.clinicalNotes,
        state.mpisData,
        (stageUpdate) => {
          dispatch({ type: 'SET_PIPELINE_STAGE', payload: stageUpdate });
        },
        (thinkingDelta) => {
          dispatch({
            type: 'APPEND_THINKING_CHUNK',
            payload: { node: thinkingDelta.node, chunk: thinkingDelta.chunk },
          });
        },
      );

      const diagnosis = mapDdxToDiagnosis(response.ddx, response.cpgs_matched);
      const carePlan  = mapTreatmentPlanToCarePlan(response.treatment_plan);

      if (response.stage_errors?.length > 0) {
        console.warn('Clinical pipeline stage errors:', response.stage_errors);
      }

      dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
      dispatch({ type: 'SET_DIAGNOSIS', payload: diagnosis });
      dispatch({ type: 'SET_CARE_PLAN', payload: carePlan });
      dispatch({ type: 'SET_ANALYZING', payload: false });
      dispatch({ type: 'SET_STEP', payload: 2 });
      return diagnosis;

    } catch (err) {
      console.error('Streaming failed, falling back to non-streaming:', err);
      try {
        const response = await runClinicalPlan(
          state.patient, state.vitals, state.clinicalNotes, state.mpisData,
        );
        const diagnosis = mapDdxToDiagnosis(response.ddx, response.cpgs_matched);
        const carePlan  = mapTreatmentPlanToCarePlan(response.treatment_plan);
        dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
        dispatch({ type: 'SET_DIAGNOSIS', payload: diagnosis });
        dispatch({ type: 'SET_CARE_PLAN', payload: carePlan });
        dispatch({ type: 'SET_ANALYZING', payload: false });
        dispatch({ type: 'SET_STEP', payload: 2 });
        return diagnosis;
      } catch (fallbackErr) {
        console.error('Fallback also failed:', fallbackErr);
        dispatch({ type: 'SET_DIAGNOSIS', payload: sampleDiagnosis });
        dispatch({ type: 'SET_ANALYZING', payload: false });
        dispatch({ type: 'SET_STEP', payload: 2 });
        throw fallbackErr;
      }
    }
```

#### 3e. Expose new state in context value
```js
pipelineStages:   state.pipelineStages,
pipelineThinking: state.pipelineThinking,
```

### B4. Update `Doctor UI/src/components/sections/DataInputSection.jsx`

```jsx
import { PipelineProgress } from './PipelineProgress';

// In JSX, where the analyze spinner currently shows (inside the isAnalyzing block):
{state.isAnalyzing && (
  <PipelineProgress
    stages={state.pipelineStages}
    thinking={state.pipelineThinking}
  />
)}
```

`state.pipelineStages` and `state.pipelineThinking` are available via `useApp()` after step 3e.

---

## Files changed summary

| File | Change |
|------|--------|
| `agent/clinical_stages.py` | `_llm_rerank_ddx`: add `emit=None`, streaming branch for thinking tokens. `stage_2_ddx`: add `emit=None`, pass through |
| `agent/clinical_workflow.py` | Add `run_clinical_workflow_streaming` (new function, ~70 lines) |
| `agent/api.py` | Add `POST /clinical/plan/stream` endpoint (~35 lines) |
| `Doctor UI/src/lib/clinicalApi.js` | Extract `buildClinicalPlanBody` + add `runClinicalPlanStream` |
| `Doctor UI/src/context/AppContext.jsx` | `pipelineStages` + `pipelineThinking` state, 3 reducer cases, update `analyzeAssessment` |
| `Doctor UI/src/components/sections/PipelineProgress.jsx` | New file — stepper + `ThinkingDropdown` |
| `Doctor UI/src/components/sections/DataInputSection.jsx` | Mount `<PipelineProgress>` |

---

## Tests: `tests/test_streaming.py`

```python
"""Tests for clinical workflow streaming + thinking token emission."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.clinical_workflow import run_clinical_workflow_streaming, WorkflowResult
from agent.clinical_stages import DDxResult, _llm_rerank_ddx, DDX_RERANK_MODEL, DDX_THINKING_BUDGET
from agent.models import PatientCase, TreatmentPlan
from agent.routing import CPGDocRef


@pytest.fixture
def minimal_case():
    return PatientCase(chief_complaint="palpitations", age=68, sex="M")


@pytest.fixture
def mock_ddx():
    return [DDxResult(code="BC81.3", title="AF", similarity=0.91)]


@pytest.fixture
def mock_plan():
    return TreatmentPlan(
        icd_primary="BC81.3",
        clinical_summary="Atrial fibrillation management.",
        diagnoses=["Atrial Fibrillation"],
    )


# ── Stage progress tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_streaming_emits_all_stage_events(minimal_case, mock_ddx, mock_plan):
    """All 4 stages emit running + complete events."""
    events = []

    async def collect(event_type, data):
        events.append((event_type, data))

    with patch("agent.clinical_workflow.stage_2_ddx", AsyncMock(return_value=mock_ddx)), \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        await run_clinical_workflow_streaming(minimal_case, collect)

    updates = [e for e in events if e[0] == "stage_update"]
    for stage_num in [2, 3, 4, 5]:
        statuses = {e[1]["status"] for e in updates if e[1]["stage"] == stage_num}
        assert "running"  in statuses, f"Stage {stage_num} missing 'running'"
        assert "complete" in statuses, f"Stage {stage_num} missing 'complete'"


@pytest.mark.asyncio
async def test_streaming_passes_emit_to_stage2(minimal_case, mock_ddx, mock_plan):
    """run_clinical_workflow_streaming passes emit= to stage_2_ddx."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock) as mock_s2, \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):
        mock_s2.return_value = mock_ddx
        await run_clinical_workflow_streaming(minimal_case, noop)

    call_kwargs = mock_s2.call_args.kwargs
    assert "emit" in call_kwargs
    assert call_kwargs["emit"] is noop


@pytest.mark.asyncio
async def test_streaming_returns_workflow_result(minimal_case, mock_ddx, mock_plan):
    """Returns WorkflowResult with treatment plan."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_2_ddx", AsyncMock(return_value=mock_ddx)), \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_clinical_workflow_streaming(minimal_case, noop)

    assert isinstance(result, WorkflowResult)
    assert result.treatment_plan.icd_primary == "BC81.3"


@pytest.mark.asyncio
async def test_streaming_stage_error_emits_error_status(minimal_case, mock_plan):
    """Stage 2 failure → error event; pipeline continues."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_2_ddx", AsyncMock(side_effect=Exception("db down"))), \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_clinical_workflow_streaming(minimal_case, collect)

    error_ev = [e for e in events if e[0] == "stage_update" and e[1]["status"] == "error"]
    assert len(error_ev) == 1 and error_ev[0][1]["stage"] == 2
    assert "Stage 2 DDx" in result.stage_errors[0]


# ── Thinking token streaming tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_rerank_streams_thinking_tokens_when_emit_provided(minimal_case):
    """When emit is provided, thinking tokens are emitted as thinking_delta."""
    candidates = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
    emitted = []

    async def collect(et, d):
        emitted.append((et, d))

    # Build mock streaming response: two chunks — thinking then content
    async def mock_stream():
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock(
            reasoning="68M, irregular pulse — AF likely",
            content=None,
        )
        yield chunk1

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock(
            reasoning=None,
            content='[{"code":"BC81.3","confidence":0.92,"reasoning":"fits best"}]',
        )
        yield chunk2

    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        result = await _llm_rerank_ddx(minimal_case, candidates, emit=collect)

    thinking_events = [e for e in emitted if e[0] == "thinking_delta"]
    assert len(thinking_events) == 1
    assert "AF likely" in thinking_events[0][1]["chunk"]
    assert thinking_events[0][1]["stage"] == 2
    assert thinking_events[0][1]["node"] == "DDx Re-rank"
    assert result[0].code == "BC81.3"


@pytest.mark.asyncio
async def test_rerank_no_emit_uses_non_streaming_path(minimal_case):
    """When emit=None, non-streaming create() is called (original behavior)."""
    candidates = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]

    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "fits best"},
    ])

    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates, emit=None)

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    # Non-streaming call must NOT pass stream=True
    assert call_kwargs.get("stream") is None or call_kwargs.get("stream") is False
    assert result[0].code == "BC81.3"


@pytest.mark.asyncio
async def test_rerank_thinking_failure_falls_back(minimal_case):
    """If streaming call raises, original candidate order is preserved."""
    candidates = [
        DDxResult(code="BC81.3", title="AF",  similarity=0.91),
        DDxResult(code="BA00",   title="HTN", similarity=0.72),
    ]
    emitted = []

    async def collect(et, d):
        emitted.append((et, d))

    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))

        result = await _llm_rerank_ddx(minimal_case, candidates, emit=collect)

    assert [r.code for r in result] == ["BC81.3", "BA00"]
```

---

## Done criteria

1. `pytest tests/test_streaming.py -v` → 7 green
2. `pytest tests/test_clinical_stages.py -v` → all 23 still green (existing re-rank tests unaffected)
3. `curl -N -X POST http://localhost:8058/clinical/plan/stream -H 'Content-Type: application/json' -d '{"case":{"chief_complaint":"palpitations"}}'` → streams `event: thinking_delta` lines before `event: stage_update` complete for stage 2
4. Doctor UI: Analyze → PipelineProgress renders; DDx stage shows "View reasoning" button after thinking begins; clicking it expands streaming text with pulsing cursor
5. "View reasoning" button appears only for DDx stage, not CPG Routing / Retrieval / Synthesis
6. On backend error: UI falls back to non-streaming `/clinical/plan`, still reaches Step 2

---

## Implementation notes

- `temperature=1` is already set — no change needed. Both streaming and non-streaming branches of `_llm_rerank_ddx` must keep `temperature=1`.
- OpenRouter exposes Gemini thinking tokens as `delta.reasoning`. The code checks `delta.reasoning` first, then `delta.reasoning_content` as a safety fallback (used by some other models on OpenRouter). If neither field exists on the delta, the chunk is silently skipped — no error.
- The non-streaming path (`emit=None`) is **identical to the pre-Step-09 code**. All 23 existing `test_clinical_stages.py` tests call `_llm_rerank_ddx` without `emit`, so they hit the non-streaming path and pass unchanged.
- `asyncio.create_task(run_workflow())` in the SSE endpoint mirrors the existing `/chat/stream` pattern already in `api.py`.
- `X-Accel-Buffering: no` prevents nginx from holding SSE chunks.
- Frontend fallback chain: streaming → non-streaming → sampleDiagnosis (dev only).

---

## Report back

1. **Diff summary** — lines added/changed per file
2. **Test output** — `pytest tests/test_streaming.py -v` (7 tests) + `pytest tests/test_clinical_stages.py -v` (23 tests)
3. **Manual test** — curl output showing `thinking_delta` events interleaved with `stage_update`
4. **Any deviations** and why
