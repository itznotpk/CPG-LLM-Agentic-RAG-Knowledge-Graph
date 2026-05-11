# Step 10 — Clinician-Directed Re-synthesis

## The clinical problem

The current pipeline runs the full DDx → Route → Retrieve → Synthesize sequence in one shot.
The TreatmentPlan is locked in at analysis time, before the clinician reviews the diagnosis.

If the clinician selects a **different** ICD-11 code than the AI's top pick, the care plan shown is
still the AI's plan — clinically incorrect.

```
Before this step:                      After this step:
─────────────────────────────────────  ────────────────────────────────────────────
AI picks BB01.1 PAH                    AI picks BB01.1 PAH
Pipeline generates PAH care plan       Pipeline generates PAH care plan
Clinician selects BC81.3 AF            Clinician selects BC81.3 AF
→ AF patient sees PAH medications ✗    → Re-runs Stages 3-5 for AF code
                                       → AF patient sees AF medications ✓
```

**Done criteria:** The TreatmentPlan shown to the clinician always reflects the diagnosis
the clinician confirmed, not the AI's initial guess.

---

## Estimated effort

**Sonnet time:** 22–30 min | **Cost:** ~$0.22 | **Thinking:** ON, low budget

---

## Read these files first

- `agent/clinical_stages.py` — `stage_3_route`, `stage_4_retrieve`, `stage_5_synthesize`, `DDxResult`
- `agent/clinical_workflow.py` — `run_clinical_workflow_streaming`; add `run_resynthesize_streaming` alongside
- `agent/api.py` — add `POST /clinical/plan/resynthesize/stream` after the existing streaming endpoint
- `Doctor UI/src/context/AppContext.jsx` — `confirmDiagnosis()` (line 297): add re-synthesis logic
- `Doctor UI/src/lib/clinicalApi.js` — add `resynthesizePlanStream()`
- `Doctor UI/src/components/sections/DiagnosisSection.jsx` — update button label, show re-synthesis progress
- `Doctor UI/src/lib/clinicalMappers.js` — `mapDdxToDiagnosis` (line 4): understand the `icdCode` field

---

## Part A — Backend

### A1. New Pydantic model in `agent/api.py`

Add alongside `ClinicalPlanRequest`:

```python
class SelectedDiagnosis(_BaseModel):
    code: str               # ICD-11 code  e.g. "BC81.3"
    title: str              # Diagnosis name
    probability: float = 0.9
    reasoning: list[str] = []

class ResynthesizeRequest(_BaseModel):
    case: PatientCase
    selected_diagnoses: list[SelectedDiagnosis]
```

### A2. New `run_resynthesize_streaming` in `agent/clinical_workflow.py`

Add after `run_clinical_workflow_streaming`. Runs **Stages 3–5 only** — Stage 2 (DDx) is skipped
because the clinician has already decided the diagnosis.

```python
async def run_resynthesize_streaming(
    case: PatientCase,
    selected_ddx: list[DDxResult],   # clinician-confirmed codes as DDxResult objects
    emit,
) -> WorkflowResult:
    """
    Re-run Stages 3–5 with clinician-selected diagnoses.

    Stage 2 (DDx) is intentionally skipped — the clinician's selection overrides the AI.
    Emits a clinician_override event first so the UI can show what changed.
    Same fault-tolerance contract as run_clinical_workflow_streaming for stages 3–4.
    Stage 5 failure propagates (unrecoverable).
    """
    t0 = time.monotonic()
    errors: list[str] = []

    # Signal the override to the UI
    await emit("clinician_override", {
        "codes": [f"{d.code} {d.title}" for d in selected_ddx],
    })

    # Stage 3 — Route using clinician codes
    await emit("stage_update", {
        "stage": 3, "name": "CPG Routing",
        "status": "running",
        "detail": f"Routing {len(selected_ddx)} clinician-selected code(s)…",
    })
    try:
        cpgs = await stage_3_route(selected_ddx, top_k_codes=len(selected_ddx), top_k_cpgs=3, emit=emit)
        names = [c.cpg_name for c in cpgs]
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "complete",
            "detail": f"{len(cpgs)} CPGs matched: {', '.join(names)}",
            "data": names,
        })
    except Exception as e:
        logger.error("Re-synth Stage 3 failed: %s", e)
        errors.append(f"Stage 3 Routing: {e}")
        await emit("stage_update", {"stage": 3, "name": "CPG Routing", "status": "error", "detail": str(e)})
        cpgs = []

    # Stage 4 — Retrieve
    await emit("stage_update", {
        "stage": 4, "name": "Evidence Retrieval",
        "status": "running", "detail": "Retrieving guideline evidence for selected diagnosis…",
    })
    try:
        evidence = await stage_4_retrieve(case, selected_ddx, cpgs, emit=emit)
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "complete",
            "detail": f"{len(evidence)} evidence chunks retrieved",
        })
    except Exception as e:
        logger.error("Re-synth Stage 4 failed: %s", e)
        errors.append(f"Stage 4 Retrieval: {e}")
        await emit("stage_update", {"stage": 4, "name": "Evidence Retrieval", "status": "error", "detail": str(e)})
        evidence = []

    # Stage 5 — Synthesize (unrecoverable)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan for confirmed diagnosis…",
    })
    treatment_plan = await stage_5_synthesize(case, selected_ddx, cpgs, evidence)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms",
        "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, "confidence") and treatment_plan.confidence else None,
    })
    logger.info("Re-synthesis complete in %.0f ms", elapsed_ms)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=selected_ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
    )
```

### A3. New `POST /clinical/plan/resynthesize/stream` in `agent/api.py`

Add after the existing `/clinical/plan/stream` endpoint.

```python
@app.post("/clinical/plan/resynthesize/stream")
async def clinical_resynthesize_stream(request: ResynthesizeRequest):
    """
    Re-run Stages 3–5 with clinician-selected diagnoses and stream SSE events.

    Called when the clinician confirms a diagnosis that differs from the AI top pick.
    Stage 2 is skipped. Events are identical in shape to /clinical/plan/stream.
    Extra event:
      event: clinician_override   data: {"codes": ["BC81.3 AF", ...]}
    """
    from .clinical_workflow import run_resynthesize_streaming
    from .clinical_stages import DDxResult

    async def generate():
        queue: asyncio.Queue = asyncio.Queue()

        async def emit(event_type: str, data: dict):
            await queue.put((event_type, data))

        async def run_workflow():
            try:
                # Convert SelectedDiagnosis → DDxResult
                selected_ddx = [
                    DDxResult(
                        code=d.code,
                        title=d.title,
                        similarity=d.probability,
                        reasoning=d.reasoning,
                    )
                    for d in request.selected_diagnoses
                ]
                result = await run_resynthesize_streaming(request.case, selected_ddx, emit)
                final = ClinicalPlanResponse(
                    treatment_plan=result.treatment_plan,
                    ddx=[d.model_dump() for d in result.ddx],
                    cpgs_matched=[c.cpg_name for c in result.cpgs],
                    elapsed_ms=result.elapsed_ms,
                    stage_errors=result.stage_errors,
                )
                await queue.put(("final_result", final.model_dump()))
            except Exception as e:
                logger.error("Re-synthesis streaming failed: %s", e)
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
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
```

---

## Part B — Frontend

### B1. Add `resynthesizePlanStream` to `Doctor UI/src/lib/clinicalApi.js`

Add after `runClinicalPlanStream`. Shares the same SSE frame-parsing logic.

```js
/**
 * Re-run Stages 3–5 with clinician-confirmed diagnoses.
 *
 * @param {Object}   patientState
 * @param {Object}   vitals
 * @param {string}   clinicalNotes
 * @param {Object}   mpisData
 * @param {Array}    selectedDiagnoses  — [{icdCode, name, probability, reasoning}]
 * @param {Function} onStageUpdate
 * @param {Function} onSubStep
 * @param {Function} onClinicianOverride  — called once with {codes:[]}
 * @returns {Promise<ClinicalPlanResponse>}
 */
export async function resynthesizePlanStream(
  patientState, vitals, clinicalNotes, mpisData,
  selectedDiagnoses,
  onStageUpdate,
  onSubStep,
  onClinicianOverride,
) {
  const BASE_URL = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

  const body = {
    case: buildClinicalPlanBody(patientState, vitals, clinicalNotes, mpisData).case,
    selected_diagnoses: selectedDiagnoses.map((d) => ({
      code:        d.icdCode,
      title:       d.name,
      probability: (d.probability || 80) / 100,  // UI stores as 0-100, API expects 0-1
      reasoning:   d.reasoning || [],
    })),
  };

  const response = await fetch(`${BASE_URL}/clinical/plan/resynthesize/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Re-synthesis API error ${response.status}: ${text}`);
  }

  return new Promise((resolve, reject) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const pump = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) { reject(new Error('Stream ended without final_result')); return; }
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split('\n\n');
          buffer = frames.pop();

          for (const frame of frames) {
            if (!frame.trim()) continue;
            let eventType = 'message', dataStr = '';
            for (const line of frame.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
            }
            if (!dataStr) continue;
            let payload;
            try { payload = JSON.parse(dataStr); } catch { continue; }

            if      (eventType === 'stage_update'       && onStageUpdate)       onStageUpdate(payload);
            else if (eventType === 'sub_step'           && onSubStep)           onSubStep(payload);
            else if (eventType === 'clinician_override' && onClinicianOverride) onClinicianOverride(payload);
            else if (eventType === 'final_result')                               resolve(payload);
            else if (eventType === 'error')                                      reject(new Error(payload.detail || 'Re-synthesis error'));
            else if (eventType === 'done')                                       return;
          }
        }
      } catch (err) { reject(err); }
    };
    pump();
  });
}
```

### B2. New reducer cases in `AppContext.jsx`

Add to `appReducer`:

```js
case 'RESET_PIPELINE_FROM_STAGE': {
  // Keep events for stages before the given number; clear from that stage onward
  const fromStage = action.payload;
  return {
    ...state,
    pipelineEvents: state.pipelineEvents.filter((e) => (e.stage || 0) < fromStage),
    pipelineSummary: null,
  };
}
case 'SET_RESYNTH_OVERRIDE':
  // Store the clinician override marker for display in PipelineProgress
  return { ...state, resynthOverride: action.payload };
```

Add `resynthOverride: null` to `initialState`. Also add it to `RESET_PIPELINE`:
```js
case 'RESET_PIPELINE':
  return { ...state, pipelineEvents: [], pipelineThinking: {}, pipelineSummary: null, resynthOverride: null };
```

Expose in context value: `resynthOverride: state.resynthOverride`.

### B3. Update `confirmDiagnosis()` in `AppContext.jsx`

Import `resynthesizePlanStream`:
```js
import { runClinicalPlan, runClinicalPlanStream, resynthesizePlanStream } from '../lib/clinicalApi';
```

Replace the final block of `confirmDiagnosis` (currently just `dispatch SET_GENERATING_PLAN false` + `SET_STEP 3`) with:

```js
  // ── Re-synthesis logic ──────────────────────────────────────────────────
  // Determine if clinician selected codes different from what the pipeline used.
  // The pipeline routes on the AI's top-2 DDx codes; if the clinician picked
  // anything outside that set, we must re-run Stages 3-5.
  const aiTopCodes = new Set(
    (state.clinicalPlanResponse?.ddx || []).slice(0, 2).map((d) => d.code)
  );
  const needsResynth = selectedDiagnoses.some((d) => !aiTopCodes.has(d.icdCode));

  if (needsResynth) {
    console.log('🔄 Clinician override detected — re-running Stages 3-5 for:', selectedDiagnoses.map(d => d.icdCode));
    dispatch({ type: 'RESET_PIPELINE_FROM_STAGE', payload: 3 });

    try {
      const response = await resynthesizePlanStream(
        state.patient, state.vitals, state.clinicalNotes, state.mpisData,
        selectedDiagnoses,
        (stageUpdate)        => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...stageUpdate, eventType: 'stage_update' } }),
        (subStep)            => dispatch({ type: 'APPEND_PIPELINE_EVENT', payload: { ...subStep, eventType: 'sub_step' } }),
        (overrideData)       => dispatch({ type: 'SET_RESYNTH_OVERRIDE', payload: overrideData }),
      );

      const newCarePlan = mapTreatmentPlanToCarePlan(response.treatment_plan);
      dispatch({ type: 'SET_CARE_PLAN', payload: newCarePlan });
      dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
      dispatch({
        type: 'SET_PIPELINE_SUMMARY',
        payload: { elapsed_ms: response.elapsed_ms, ddxCount: selectedDiagnoses.length, cpgCount: response.cpgs_matched?.length || 0 },
      });
      console.log('✅ Re-synthesis complete for clinician-selected diagnosis');
    } catch (err) {
      console.error('Re-synthesis failed — keeping original plan:', err);
      // Non-fatal: keep the original care plan, still advance to Step 3
    }
  }

  dispatch({ type: 'SET_GENERATING_PLAN', payload: false });
  dispatch({ type: 'SET_STEP', payload: 3 });
};
```

### B4. Update `DiagnosisSection.jsx` — button label + inline progress

The "Generate Care Plan" button should tell the clinician whether a re-synthesis will happen.

Add near the top of the component (after `selectedDiagnoses` is computed):

```jsx
// Detect if clinician selection differs from AI routing set
const aiTopCodes = new Set(
  (state.clinicalPlanResponse?.ddx || []).slice(0, 2).map((d) => d.code)
);
const willResynth = selectedDiagnoses.some((d) => !aiTopCodes.has(d.icdCode));
```

Update the button label:

```jsx
// Replace the existing button label string:
{isGeneratingPlan
  ? (willResynth ? 'Re-generating Care Plan…' : 'Generating Care Plan…')
  : willResynth
    ? `Re-generate Care Plan for ${selectedDiagnoses.map(d => d.icdCode).join(', ')}`
    : `Generate Care Plan${selectedDiagnoses.length > 1 ? ` (${selectedDiagnoses.length} diagnoses)` : ''}`
}
```

Add a small notice when re-synthesis will occur, just above the action buttons:

```jsx
{willResynth && !isGeneratingPlan && (
  <div className={`flex items-center gap-2 text-xs px-4 py-2 rounded-lg
    ${isDark ? 'bg-amber-900/20 text-amber-300 border border-amber-500/20'
             : 'bg-amber-50    text-amber-700 border border-amber-200'}`}>
    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
    Your selection differs from the AI recommendation — the care plan will be
    re-generated specifically for{' '}
    <strong>{selectedDiagnoses.map(d => d.name).join(', ')}</strong>.
  </div>
)}
```

Show the live pipeline trace during re-synthesis (reuse the `PipelineProgress` already imported):

```jsx
{isGeneratingPlan && willResynth && (
  <PipelineProgress
    pipelineEvents={state.pipelineEvents}
    pipelineThinking={state.pipelineThinking}
    summary={state.pipelineSummary}
    isLive={true}
  />
)}
```

### B5. Handle `clinician_override` event in `PipelineProgress.jsx`

In `PipelineProgress`, if `resynthOverride` is passed as a prop, render a marker row between
Stage 2 (complete) and Stage 3 (re-running):

Add prop `resynthOverride = null` to the component signature.

Inside the stage loop, after rendering the Stage 2 row and before Stage 3, insert:

```jsx
{def.stage === 3 && resynthOverride && (
  <div className="flex gap-4">
    <div className="flex flex-col items-center">
      <div className="w-8 h-8 flex items-center justify-center rounded-full
        bg-amber-500/20 border-2 border-amber-500/50 text-amber-400 text-xs">
        ✎
      </div>
      <div className="w-0.5 flex-1 my-1 min-h-4 bg-amber-500/30" />
    </div>
    <div className="flex-1 pb-4 pt-1">
      <p className={`text-xs font-medium ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
        Clinician override
      </p>
      <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
        {resynthOverride.codes.join(' · ')}
      </p>
    </div>
  </div>
)}
```

Update `DataInputSection.jsx` and `DiagnosisSection.jsx` calls to pass `resynthOverride={state.resynthOverride}`.

---

## Files changed summary

| File | Change |
|---|---|
| `agent/api.py` | `SelectedDiagnosis` + `ResynthesizeRequest` models; `POST /clinical/plan/resynthesize/stream` endpoint |
| `agent/clinical_workflow.py` | `run_resynthesize_streaming` (new function, ~55 lines) |
| `Doctor UI/src/lib/clinicalApi.js` | `resynthesizePlanStream()` (+55 lines) |
| `Doctor UI/src/context/AppContext.jsx` | `resynthOverride` state; `RESET_PIPELINE_FROM_STAGE` + `SET_RESYNTH_OVERRIDE` reducer cases; re-synthesis logic in `confirmDiagnosis` |
| `Doctor UI/src/components/sections/DiagnosisSection.jsx` | `willResynth` detection; button label; amber notice; live progress during re-synthesis |
| `Doctor UI/src/components/sections/PipelineProgress.jsx` | `resynthOverride` prop; clinician override marker row between stages 2 and 3 |
| `Doctor UI/src/components/sections/DataInputSection.jsx` | Pass `resynthOverride` prop |

---

## Tests: `tests/test_resynthesize.py`

```python
"""Tests for clinician-directed re-synthesis workflow."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.clinical_workflow import run_resynthesize_streaming, WorkflowResult
from agent.clinical_stages import DDxResult
from agent.models import PatientCase, TreatmentPlan
from agent.routing import CPGDocRef


@pytest.fixture
def minimal_case():
    return PatientCase(chief_complaint="palpitations", age=68, sex="M")


@pytest.fixture
def selected_ddx():
    # Clinician selected AF — different from AI top pick
    return [DDxResult(code="BC81.3", title="Atrial Fibrillation", similarity=0.95)]


@pytest.fixture
def mock_plan():
    return TreatmentPlan(
        icd_primary="BC81.3",
        clinical_summary="AF management.",
        diagnoses=["Atrial Fibrillation"],
        recommendations=[],
        monitoring=[],
        red_flags=[],
        confidence=0.88,
        unresolved_questions=[],
    )


@pytest.mark.asyncio
async def test_resynth_emits_clinician_override_first(minimal_case, selected_ddx, mock_plan):
    """clinician_override event is the first event emitted."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        await run_resynthesize_streaming(minimal_case, selected_ddx, collect)

    assert events[0][0] == "clinician_override"
    assert "BC81.3" in events[0][1]["codes"][0]


@pytest.mark.asyncio
async def test_resynth_skips_stage_2(minimal_case, selected_ddx, mock_plan):
    """Stage 2 DDx is never called — clinician selection is used directly."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock) as mock_s2, \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        await run_resynthesize_streaming(minimal_case, selected_ddx, collect)

    mock_s2.assert_not_called()
    stage_nums = {e[1].get("stage") for e in events if e[0] == "stage_update"}
    assert 2 not in stage_nums
    assert {3, 4, 5}.issubset(stage_nums)


@pytest.mark.asyncio
async def test_resynth_uses_selected_ddx_for_routing(minimal_case, selected_ddx, mock_plan):
    """stage_3_route is called with the clinician's selected DDx, not AI's."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock) as mock_s3, \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):
        mock_s3.return_value = []
        await run_resynthesize_streaming(minimal_case, selected_ddx, noop)

    call_args = mock_s3.call_args
    passed_ddx = call_args.args[0]
    assert passed_ddx[0].code == "BC81.3"
    # top_k_codes equals the number of selected diagnoses
    assert call_args.kwargs.get("top_k_codes") == len(selected_ddx)


@pytest.mark.asyncio
async def test_resynth_returns_new_treatment_plan(minimal_case, selected_ddx, mock_plan):
    """WorkflowResult contains the new plan for the clinician-selected diagnosis."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_resynthesize_streaming(minimal_case, selected_ddx, noop)

    assert isinstance(result, WorkflowResult)
    assert result.treatment_plan.icd_primary == "BC81.3"
    assert result.ddx == selected_ddx


@pytest.mark.asyncio
async def test_resynth_stage3_failure_continues(minimal_case, selected_ddx, mock_plan):
    """Stage 3 failure is fault-tolerant — pipeline continues to Stage 5."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_3_route", AsyncMock(side_effect=Exception("routing down"))), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_resynthesize_streaming(minimal_case, selected_ddx, collect)

    error_events = [e for e in events if e[0] == "stage_update" and e[1].get("status") == "error"]
    assert any(e[1]["stage"] == 3 for e in error_events)
    assert "Stage 3 Routing" in result.stage_errors[0]
    assert result.treatment_plan.icd_primary == "BC81.3"  # still synthesized
```

---

## Done criteria

1. `pytest tests/test_resynthesize.py -v` → 5 green
2. `pytest tests/test_streaming.py -v` → 7 still green
3. `pytest tests/test_clinical_stages.py -v` → 23 still green
4. When clinician selects the same code as AI top pick → no re-synthesis call (verify via backend logs: no `POST /clinical/plan/resynthesize/stream` request)
5. When clinician selects a different code → amber notice appears in DiagnosisSection; "Re-generate Care Plan for BC81.3" shown on button
6. After clicking → live pipeline progress shows stages 3-5 running with "Clinician override" marker between stages 2 and 3
7. Final care plan in Step 3 reflects the clinician-selected diagnosis ICD code (check `carePlan.icdPrimary`)

---

## Implementation notes

- `top_k_codes=len(selected_ddx)` in the re-synthesis routing call: if the clinician selected 2 diagnoses, route both. This differs from the default `top_k_codes=2` (AI top-2) but is intentional — every clinician-selected code gets routed.
- `RESET_PIPELINE_FROM_STAGE` keeps Stage 2 (DDx) events visible in the trace. The clinician sees the full picture: AI's DDx + their override + re-synthesized stages 3-5.
- Re-synthesis failure is **non-fatal**: the `catch` block in `confirmDiagnosis` logs the error and advances to Step 3 with the original AI-generated plan. The clinician is not blocked. A future improvement could show a warning banner in CarePlanSection.
- The `aiTopCodes` check uses `.slice(0, 2)` to match `top_k_codes=2` in the original `stage_3_route` call. If you change `top_k_codes` in the future, update both places.

---

## Report back

1. Diff summary — lines per file
2. `pytest tests/test_resynthesize.py -v` (5 tests)
3. `pytest tests/test_streaming.py -v` (7 tests)
4. Manual test: select a diagnosis different from AI #1, confirm — show backend log line confirming re-synthesis ran with the new ICD code
5. Any deviations and why
