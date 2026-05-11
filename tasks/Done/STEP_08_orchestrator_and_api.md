# Step 08 — Orchestrator, API Endpoint, and Doctor UI v1 Wiring

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. This is **the final step for v1**. All pipeline stages are built and tested. Your job is to wire them into a running system.

Steps 01–07B are complete:
- `PatientCase`, `TreatmentPlan` in [agent/models.py](../agent/models.py)
- `stage_2_ddx`, `stage_3_route`, `stage_4_retrieve`, `stage_5_synthesize`, `DDxResult` in [agent/clinical_stages.py](../agent/clinical_stages.py)
- `route_icd_to_cpgs`, `CPGDocRef` in [agent/routing.py](../agent/routing.py)
- FastAPI app already running at [agent/api.py](../agent/api.py) with `/chat`, `/health`, `/search/*` endpoints
- Doctor UI is a **React 18 + Vite SPA** at [Doctor UI/src/](../Doctor%20UI/src/) — currently uses `sampleDiagnosis` and `sampleCarePlan` mock data

**Read these files before writing any code:**
- [agent/clinical_stages.py](../agent/clinical_stages.py) — all 4 stage function signatures
- [agent/api.py](../agent/api.py) — existing FastAPI app structure (lifespan, middleware, CORS all already set up)
- [Doctor UI/src/context/AppContext.jsx](../Doctor%20UI/src/context/AppContext.jsx) — `analyzeAssessment()` and `confirmDiagnosis()` are the two functions to replace
- [Doctor UI/src/data/sampleData.js](../Doctor%20UI/src/data/sampleData.js) — `sampleDiagnosis` and `sampleCarePlan` shapes the UI currently expects

---

## Objective

Three deliverables:

1. **`agent/clinical_workflow.py`** — thin orchestrator calling stages 2→5
2. **`POST /clinical/plan`** in `agent/api.py` — FastAPI endpoint
3. **Doctor UI wiring** — `AppContext.jsx` calls the real endpoint; `DiagnosisSection.jsx` and `CarePlanSection.jsx` render pipeline output

---

## Deliverable 1: `agent/clinical_workflow.py`

```python
"""
Clinical workflow orchestrator.
Calls pipeline stages 2–5 sequentially and returns a TreatmentPlan.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field

from .models import PatientCase, TreatmentPlan
from .clinical_stages import DDxResult, stage_2_ddx, stage_3_route, stage_4_retrieve, stage_5_synthesize
from .routing import CPGDocRef

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    treatment_plan: TreatmentPlan
    ddx: list[DDxResult]
    cpgs: list[CPGDocRef]
    elapsed_ms: float
    stage_errors: list[str] = field(default_factory=list)


async def run_clinical_workflow(case: PatientCase) -> WorkflowResult:
    """
    Run the full clinical workflow for a patient case.

    Stages:
        2 — DDx: symptoms → ICD-11 candidates (vector + Gemini 2.5 Flash thinking re-rank)
        3 — Route: ICD codes → CPG document IDs
        4 — Retrieve: scoped vector search with LLM-generated queries
        5 — Synthesize: TreatmentPlan structured output

    Raises:
        RuntimeError if Stage 5 synthesis fails (unrecoverable).
        All other stage failures are caught, logged, and the pipeline continues
        with degraded output rather than crashing.
    """
    t0 = time.monotonic()
    errors: list[str] = []

    # Stage 2 — DDx
    try:
        ddx = await stage_2_ddx(case, top_k=5)
        logger.info("Stage 2 DDx: %d candidates. Top: %s",
                    len(ddx), ddx[0].code if ddx else "none")
    except Exception as e:
        logger.error("Stage 2 DDx failed: %s", e)
        errors.append(f"Stage 2 DDx: {e}")
        ddx = []

    # Stage 3 — Route
    try:
        cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3)
        logger.info("Stage 3 Routing: %d CPGs matched: %s",
                    len(cpgs), [c.cpg_name for c in cpgs])
    except Exception as e:
        logger.error("Stage 3 Routing failed: %s", e)
        errors.append(f"Stage 3 Routing: {e}")
        cpgs = []

    # Stage 4 — Retrieve
    try:
        evidence = await stage_4_retrieve(case, ddx, cpgs)
        logger.info("Stage 4 Retrieval: %d evidence chunks", len(evidence))
    except Exception as e:
        logger.error("Stage 4 Retrieval failed: %s", e)
        errors.append(f"Stage 4 Retrieval: {e}")
        evidence = []

    # Stage 5 — Synthesize (unrecoverable if it fails)
    treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence)

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info("Workflow complete in %.0f ms. ICD primary: %s",
                elapsed_ms, treatment_plan.icd_primary)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
    )
```

---

## Deliverable 2: `POST /clinical/plan` in `agent/api.py`

### Request / response models (add to `agent/api.py` or keep in `agent/models.py`)

```python
class ClinicalPlanRequest(BaseModel):
    case: PatientCase
    session_id: str | None = None    # optional, for audit linking

class ClinicalPlanResponse(BaseModel):
    treatment_plan: TreatmentPlan
    ddx: list[dict]          # serialised DDxResult list for UI display
    cpgs_matched: list[str]  # CPG names matched during routing
    elapsed_ms: float
    stage_errors: list[str] = []
```

### Endpoint (add after existing `/chat` endpoint in `agent/api.py`)

```python
from .clinical_workflow import run_clinical_workflow
from .clinical_stages import DDxResult

@app.post("/clinical/plan", response_model=ClinicalPlanResponse)
async def clinical_plan(request: ClinicalPlanRequest):
    """
    Run the full clinical workflow for a patient case.
    Accepts PatientCase, returns TreatmentPlan + DDx candidates + matched CPGs.
    """
    try:
        result = await run_clinical_workflow(request.case)
        return ClinicalPlanResponse(
            treatment_plan=result.treatment_plan,
            ddx=[d.model_dump() for d in result.ddx],
            cpgs_matched=[c.cpg_name for c in result.cpgs],
            elapsed_ms=result.elapsed_ms,
            stage_errors=result.stage_errors,
        )
    except RuntimeError as e:
        # Stage 5 synthesis failed — unrecoverable
        logger.error("Clinical plan synthesis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Clinical plan endpoint failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
```

**Do NOT modify** the lifespan, CORS middleware, or any existing endpoint.

---

## Deliverable 3: Doctor UI v1 wiring

### 3a. Backend URL config

Create `Doctor UI/src/lib/clinicalApi.js`:

```javascript
const CLINICAL_API_BASE = import.meta.env.VITE_CLINICAL_API_URL || 'http://localhost:8058';

/**
 * Run the full clinical pipeline for a patient case.
 * Maps Doctor UI state → PatientCase → POST /clinical/plan → response.
 */
export async function runClinicalPlan(patientState, vitals, clinicalNotes, mpisData) {
  const patientCase = {
    chief_complaint: clinicalNotes || patientState.name + ' consultation',
    history: clinicalNotes || null,
    age: patientState.age || null,
    sex: patientState.gender === 'Male' ? 'M' : patientState.gender === 'Female' ? 'F' : 'other',
    comorbidities: mpisData?.comorbidities || [],
    current_medications: (mpisData?.currentMeds || []).map(m => `${m.name} ${m.dose} ${m.frequency}`),
    allergies: mpisData?.allergies ? [mpisData.allergies] : [],
    vitals: buildVitals(vitals),
  };

  const resp = await fetch(`${CLINICAL_API_BASE}/clinical/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case: patientCase }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Clinical plan request failed');
  }

  return resp.json();   // ClinicalPlanResponse shape
}

function buildVitals(vitals) {
  const v = {};
  if (vitals.bpSystolic)   v.sbp = parseFloat(vitals.bpSystolic);
  if (vitals.bpDiastolic)  v.dbp = parseFloat(vitals.bpDiastolic);
  if (vitals.hr)           v.hr  = parseFloat(vitals.hr);
  if (vitals.temp)         v.temp = parseFloat(vitals.temp);
  if (vitals.spo2)         v.spo2 = parseFloat(vitals.spo2);
  if (vitals.weight)       v.weight = parseFloat(vitals.weight);
  if (vitals.rr)           v.rr = parseFloat(vitals.rr);
  return v;
}
```

Add to `Doctor UI/.env` (create if not exists):
```
VITE_CLINICAL_API_URL=http://localhost:8058
```

### 3b. Response-to-UI shape mappers

The UI's `DiagnosisSection` expects `state.diagnosis.differentials[]` with shape:
```js
{ id, name, icdCode, probability, risk }
```

The UI's `CarePlanSection` expects `state.carePlan` with shape:
```js
{ clinicalSummary, medications: {stop[], start[], change[], continue[]}, interventions[], monitoring[], lifestyle[], referrals[] }
```

Create `Doctor UI/src/lib/clinicalMappers.js`:

```javascript
/**
 * Map ClinicalPlanResponse.ddx → diagnosis state shape for DiagnosisSection
 */
export function mapDdxToDiagnosis(ddxList, cpgsMatched) {
  const differentials = ddxList.map((d, i) => ({
    id: i + 1,
    name: d.title,
    icdCode: d.code,
    probability: Math.round(d.similarity * 100),
    risk: d.similarity >= 0.85 ? 'high' : d.similarity >= 0.65 ? 'medium' : 'low',
    reasoning: d.reasoning || [],       // LLM reasoning for display
    inclusionMatch: d.inclusion_match,
  }));

  return {
    differentials,
    selectedDiagnosisIds: differentials.length > 0 ? [differentials[0].id] : [],
    cpgsMatched,    // e.g. ["CPG AF Management", "CPG Hypertension"]
  };
}

/**
 * Map ClinicalPlanResponse.treatment_plan → carePlan state shape for CarePlanSection
 */
export function mapTreatmentPlanToCarePlan(plan) {
  // Split recommendations by type into UI sections
  const pharmacological = plan.recommendations.filter(r => r.type === 'pharmacological');
  const procedures      = plan.recommendations.filter(r => r.type === 'procedure');
  const lifestyle       = plan.recommendations.filter(r => r.type === 'lifestyle');
  const referrals       = plan.recommendations.filter(r => r.type === 'referral');
  const investigations  = plan.recommendations.filter(r => r.type === 'investigation');

  // Build medication list — treat all pharmacological as START (no STOP/CHANGE without prior meds context)
  const startMeds = pharmacological.map((r, i) => ({
    id: i + 1,
    name: r.intervention,
    dose: '',            // LLM puts dose in intervention string
    reason: r.rationale,
    cpgRef: r.cpg_source,
    evidenceGrade: r.evidence_grade || null,
    accepted: true,
  }));

  const interventionItems = [...procedures, ...investigations].map((r, i) => ({
    id: i + 1,
    name: r.intervention,
    rationale: r.rationale,
    urgency: '',
    cpgRef: r.cpg_source,
    evidenceGrade: r.evidence_grade || null,
    accepted: true,
  }));

  const lifestyleItems = lifestyle.map((r, i) => ({
    id: i + 1,
    goal: r.intervention,
    rationale: r.rationale,
    cpgRef: r.cpg_source,
    accepted: true,
  }));

  const referralItems = referrals.map((r, i) => ({
    id: i + 1,
    specialty: r.intervention,
    reason: r.rationale,
    cpgRef: r.cpg_source,
    accepted: true,
  }));

  // Clinical summary — build from primary ICD + first recommendation rationale
  const summary = `ICD-11: ${plan.icd_primary}. Confidence: ${Math.round(plan.confidence * 100)}%. `
    + (plan.recommendations[0]?.rationale || '');

  return {
    clinicalSummary: summary,
    icdPrimary: plan.icd_primary,
    icdAlternates: plan.icd_alternates,
    confidence: plan.confidence,
    medications: {
      stop: [],
      start: startMeds,
      change: [],
      continue: [],
    },
    interventions: interventionItems,
    lifestyle: lifestyleItems,
    referrals: referralItems,
    monitoring: plan.monitoring.map((m, i) => ({ id: i + 1, item: m, accepted: true })),
    redFlags: plan.red_flags,
    unresolvedQuestions: plan.unresolved_questions,
  };
}
```

### 3c. Wire into `AppContext.jsx`

Replace `analyzeAssessment` and `confirmDiagnosis` with real API calls. The key change: **both steps now happen together** in `analyzeAssessment` — one POST call runs the full pipeline and returns both DDx and TreatmentPlan. `confirmDiagnosis` becomes a lightweight "accept and save" step.

In `AppContext.jsx`:

1. Add imports at the top:
```javascript
import { runClinicalPlan } from '../lib/clinicalApi';
import { mapDdxToDiagnosis, mapTreatmentPlanToCarePlan } from '../lib/clinicalMappers';
```

2. Add `clinicalPlanResponse: null` to `initialState`.

3. Add reducer case:
```javascript
case 'SET_CLINICAL_PLAN_RESPONSE':
  return { ...state, clinicalPlanResponse: action.payload };
```

4. Replace `analyzeAssessment`:
```javascript
const analyzeAssessment = async () => {
  dispatch({ type: 'SET_ANALYZING', payload: true });

  // Keep Supabase consultation creation (audit trail)
  if (USE_SUPABASE && state.patient.nsn) {
    try {
      const result = await startConsultation(state.patient.nsn, state.clinicalNotes);
      if (result.success) dispatch({ type: 'SET_CONSULTATION_ID', payload: result.consultationId });
    } catch (err) {
      console.warn('Consultation DB save failed (non-fatal):', err);
    }
  }

  try {
    // Call real pipeline
    const response = await runClinicalPlan(
      state.patient,
      state.vitals,
      state.clinicalNotes,
      state.mpisData,
    );

    // Map to UI shapes
    const diagnosis = mapDdxToDiagnosis(response.ddx, response.cpgs_matched);
    const carePlan  = mapTreatmentPlanToCarePlan(response.treatment_plan);

    dispatch({ type: 'SET_CLINICAL_PLAN_RESPONSE', payload: response });
    dispatch({ type: 'SET_DIAGNOSIS', payload: diagnosis });
    dispatch({ type: 'SET_CARE_PLAN', payload: carePlan });
    dispatch({ type: 'SET_ANALYZING', payload: false });
    dispatch({ type: 'SET_STEP', payload: 2 });

    return diagnosis;

  } catch (err) {
    console.error('Clinical plan failed:', err);
    // Graceful fallback to sample data so UI doesn't break during dev
    dispatch({ type: 'SET_DIAGNOSIS', payload: sampleDiagnosis });
    dispatch({ type: 'SET_ANALYZING', payload: false });
    dispatch({ type: 'SET_STEP', payload: 2 });
    throw err;
  }
};
```

5. `confirmDiagnosis` — keep existing Supabase save logic unchanged; remove the `sampleCarePlan` timeout mock. The care plan is already set in `analyzeAssessment`. Just advance the step:

```javascript
const confirmDiagnosis = async () => {
  dispatch({ type: 'SET_GENERATING_PLAN', payload: true });

  // ... existing Supabase updateConsultation / updatePatientRiskLevel calls unchanged ...

  // Care plan already populated from analyzeAssessment — just advance
  dispatch({ type: 'SET_GENERATING_PLAN', payload: false });
  dispatch({ type: 'SET_STEP', payload: 3 });
};
```

### 3d. Display DDx reasoning in `DiagnosisSection.jsx`

Find where differentials are rendered (the list of diagnosis cards). Add a collapsible reasoning section under each card when `d.reasoning` is non-empty:

```jsx
{d.reasoning && d.reasoning.length > 0 && (
  <details className="mt-2 text-xs text-gray-500">
    <summary className="cursor-pointer hover:text-gray-300">
      View reasoning ({d.reasoning.length})
    </summary>
    <ul className="mt-1 space-y-0.5 pl-3">
      {d.reasoning.map((r, i) => (
        <li key={i} className="list-disc">{r}</li>
      ))}
    </ul>
  </details>
)}
```

Also display matched CPGs as a small badge row above the differentials list:
```jsx
{state.diagnosis?.cpgsMatched?.length > 0 && (
  <div className="flex flex-wrap gap-1 mb-3">
    <span className="text-xs text-gray-400">CPGs consulted:</span>
    {state.diagnosis.cpgsMatched.map(name => (
      <span key={name} className="text-xs bg-blue-900/40 text-blue-300 px-2 py-0.5 rounded">
        {name}
      </span>
    ))}
  </div>
)}
```

### 3e. Display unresolved questions in `CarePlanSection.jsx`

If `state.carePlan.unresolvedQuestions` is non-empty, render a yellow warning card:
```jsx
{state.carePlan?.unresolvedQuestions?.length > 0 && (
  <div className="bg-yellow-900/20 border border-yellow-600/40 rounded-lg p-3 mb-4">
    <p className="text-yellow-400 text-sm font-medium mb-1">⚠ Unresolved Clinical Questions</p>
    <ul className="text-yellow-300 text-xs space-y-0.5 pl-3">
      {state.carePlan.unresolvedQuestions.map((q, i) => (
        <li key={i} className="list-disc">{q}</li>
      ))}
    </ul>
  </div>
)}
```

---

## Deliverable 4: Tests `tests/test_clinical_workflow.py`

All mocked — no real DB, no real LLM, no real embeddings.

```python
# Required tests

test_workflow_calls_all_stages        # mock all 4 stages; assert each called once
test_workflow_returns_treatment_plan  # mock stages return valid data; assert TreatmentPlan in result
test_workflow_stage2_failure_continues # stage_2_ddx raises → ddx=[], pipeline continues, plan still returned
test_workflow_stage3_failure_continues # stage_3_route raises → cpgs=[], pipeline continues
test_workflow_stage4_failure_continues # stage_4_retrieve raises → evidence=[], pipeline continues
test_workflow_stage5_failure_raises    # stage_5_synthesize raises RuntimeError → propagates
test_workflow_records_elapsed_ms       # elapsed_ms > 0 in result
test_workflow_records_stage_errors     # stage 2 failure → stage_errors has one entry
test_clinical_plan_endpoint_200        # mock run_clinical_workflow; POST /clinical/plan → 200 + valid JSON
test_clinical_plan_endpoint_500        # mock raises RuntimeError → 500
test_clinical_plan_maps_ddx            # response.ddx is list of dicts with code/title/similarity
test_clinical_plan_maps_cpgs           # response.cpgs_matched is list of strings
```

---

## Deliverable 5: E2E smoke test fixture

Create `tests/test_e2e_smoke.py` — **three fixture cases, fully mocked** (no real API calls).

```python
# Fixture 1: AF patient
af_case = PatientCase(
    chief_complaint="palpitations and irregular heartbeat for 2 weeks",
    age=68, sex="M",
    comorbidities=["hypertension"],
    current_medications=["amlodipine 5mg OD"],
    vitals={"sbp": 145, "dbp": 88, "hr": 110}
)
# Assert: icd_primary starts with "BC81", cpgs_matched contains AF CPG, ≥1 recommendation

# Fixture 2: ED patient
ed_case = PatientCase(
    chief_complaint="erectile dysfunction for 6 months, unable to achieve erection",
    age=52, sex="M",
    comorbidities=["type 2 diabetes"],
    current_medications=["metformin 1g BD"],
    vitals={}
)
# Assert: icd_primary starts with "HA01", ≥1 pharmacological recommendation

# Fixture 3: Out-of-scope (dermatology — no CPG match expected)
oos_case = PatientCase(
    chief_complaint="widespread itchy rash on trunk and limbs",
    age=35, sex="F",
    comorbidities=[],
    current_medications=[],
    vitals={}
)
# Assert: TreatmentPlan returned (no crash), unresolved_questions non-empty OR confidence < 0.5
```

Use `pytest.mark.asyncio` + mock all IO. Assert shape of output, not content.

---

## Implementation notes

- **`agent/clinical_workflow.py` imports**: only import from `agent.*` — do NOT import from `ddx.*` directly.
- **CORS**: `allow_origins=["*"]` is already set in `api.py` — the React dev server at port 5173 will work without changes.
- **`VITE_CLINICAL_API_URL`**: backend runs on port 8058 (`APP_PORT=8058` in `.env`). Match this in `Doctor UI/.env`.
- **Fallback to sample data**: the `catch` block in `analyzeAssessment` falls back to `sampleDiagnosis` so the UI remains usable even if the backend is down during development. Do NOT remove the fallback.
- **`confirmDiagnosis` Supabase calls**: keep all existing `updateConsultation`, `updatePatientRiskLevel`, `updatePatientMedications` calls unchanged — they provide the audit trail. Only remove the `setTimeout(sampleCarePlan)` mock.
- **Do NOT change `DiagnosisSection.jsx` or `CarePlanSection.jsx` structure** — only add the reasoning accordion and unresolved questions card as described. These are additive changes that render only when new fields are present.
- **`stage_errors` in response**: surface these as a console.warn in the UI — do not show to the doctor unless debugging.

---

## Out of scope

- ❌ Step 09 (live SSE streaming) — that is a separate step
- ❌ Modify existing `/chat`, `/search/*`, `/health` endpoints
- ❌ Change `DiagnosisSection.jsx` or `CarePlanSection.jsx` layout/structure
- ❌ Supabase schema changes
- ❌ PDF export changes (`OutputSection.jsx`)
- ❌ Add `document_id_filter` to the general chat agent

---

## Done criteria

All five must pass:

1. `pytest tests/test_clinical_workflow.py -v` — all 12 tests green, zero real IO.
2. `pytest tests/test_e2e_smoke.py -v` — all 3 fixture cases green.
3. Backend smoke: `python -m agent.api` starts without error; `curl -X POST http://localhost:8058/clinical/plan -H "Content-Type: application/json" -d '{"case": {"chief_complaint": "palpitations"}}' ` returns a `TreatmentPlan` JSON (may take 10–20s).
4. UI smoke: `npm run dev` in `Doctor UI/`; enter any patient + clinical notes + click Analyze → `DiagnosisSection` shows real ICD codes (not sample E11.65 codes); Step 3 shows real CPG recommendations.
5. `pytest tests/ -v --ignore=tests/test_e2e_smoke.py` — all previously passing tests still green (no regressions).

---

## Report back

1. **Files created/modified** — exact paths.
2. **Backend smoke output** — paste the JSON response from `curl POST /clinical/plan` (trimmed to first recommendation).
3. **Test output** — `pytest tests/test_clinical_workflow.py tests/test_e2e_smoke.py -v` last ~40 lines.
4. **UI screenshot description** — what DiagnosisSection shows with a real patient (ICD codes, CPG badges, reasoning accordion).
5. **Elapsed time** — `elapsed_ms` from a real pipeline run.
6. **Any deviations** and why.
7. **Follow-ups for Step 09** (streaming UI).
