# Handoff — Safety Critic Agent (post-Stage-5 secondary review)

> **For:** Sonnet 4.6 (thinking: Medium)
> **Reference:** `tasks/Next-Step/Last Step Improvement/Agent_Architecture.md` § Agent 1 — read first
>
> Today a single LLM both synthesises and self-checks the `TreatmentPlan`. The Safety Critic is a **second, independent LLM pass** that runs after Stage 5, receives only the `TreatmentPlan` + `PatientCase` (not Stage 5's reasoning chain), and plays Devil's Advocate — flagging allergy, interaction, dose, and contraindication concerns the synthesis pass may have missed.
>
> Pattern: **Generator → Evaluator**, the standard for reducing hallucination in medical AI. The critic does not rewrite the plan; it returns a `SafetyReport` rendered as a banner above the care plan in the Doctor UI.

---

## Pre-flight — read these first

1. `agent/clinical_stages.py` — `stage_5_synthesize` (around line 600) — how a Pydantic-validated structured-output call is wired (mirror this pattern)
2. `agent/clinical_workflow.py:130–143` — where Stage 5 is invoked in `run_clinical_workflow`; same pattern at lines 234 (streaming) and 317 (resynthesize)
3. `agent/models.py` — `PatientCase`, `TreatmentPlan`, `Recommendation` shapes
4. `agent/api.py:64–69` — `ClinicalPlanResponse` (extend this with `safety_report`)
5. `agent/api.py:599–700` — `/clinical/plan/stream` SSE event shape; mirror for the new `safety_review` event
6. `Doctor UI/src/components/sections/CarePlanSection.jsx` — host for the new banner above the plan
7. `Doctor UI/src/lib/clinicalApi.js:128–134` — SSE event dispatch (add a `safety_review` branch)

Do NOT modify `clinical_cli.py`, `clinicalMappers.js`, `routing.py`, `db_utils.py`, `clinical_stages.py` (except to import nothing — Safety Critic lives in its own file), or any ingestion code.

---

## Deliverables (6 surfaces)

### 1. New file — `agent/safety_critic.py`

```python
from __future__ import annotations
import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from .models import PatientCase, TreatmentPlan
from .clinical_stages import _get_chat_client, _get_model_name  # reuse existing helpers

logger = logging.getLogger(__name__)

Severity = Literal["CRITICAL", "MAJOR", "MODERATE"]
FlagType = Literal["drug_allergy", "drug_interaction", "dose", "contraindication"]


class SafetyFlag(BaseModel):
    severity: Severity
    recommendation_index: int = Field(..., ge=0, description="Index into TreatmentPlan.recommendations that triggered the flag")
    flag_type: FlagType
    detail: str = Field(..., description="One-sentence explanation of the concern, patient-specific")
    suggested_alternative: Optional[str] = None


class SafetyReport(BaseModel):
    flags: list[SafetyFlag] = Field(default_factory=list)
    safe_to_proceed: bool = Field(..., description="False if any CRITICAL or MAJOR flag is present")
    reviewer_notes: Optional[str] = None


SAFETY_CRITIC_SYSTEM = """You are a clinical pharmacist performing an independent medication safety review.

You have NOT seen the reasoning that produced this treatment plan. Your ONLY job is to find reasons it could harm THIS SPECIFIC patient. Do not justify the plan. Do not summarise it.

For each pharmacological recommendation (recommendations[*] where type == 'pharmacological'), check:

1. drug_allergy — Does the drug, its class, or a known cross-reactant conflict with any listed allergy?
   Example: sulfa allergy + furosemide → cross-reactivity risk
2. drug_interaction — Does the drug interact dangerously with any current medication?
   Example: warfarin + new NSAID → bleeding risk
3. dose — Is the implicit dose appropriate for the patient's renal/hepatic function inferred from comorbidities and vitals?
   Example: metformin standard dose + CKD Stage 4 eGFR<30 → contraindicated
4. contraindication — Is the drug contraindicated given any listed comorbidity or vital sign?
   Example: non-cardioselective beta-blocker + severe asthma → bronchospasm risk

Flag EVERY concern you find. Do not suppress concerns because the plan "looks reasonable overall". Conversely, do NOT invent concerns — return an empty flags array if you find none.

Severity scale:
- CRITICAL : life-threatening if the plan is enacted as written (e.g. PDE5i + nitrate)
- MAJOR    : significant harm likely without modification (e.g. wrong dose in renal failure)
- MODERATE : monitoring or dose adjustment warranted, not an outright stop

For each flag, set recommendation_index to the 0-based index of the recommendation in the input array. Provide a one-sentence patient-specific detail. Suggest an alternative only if one is clearly clinically supported.

Set safe_to_proceed = false if ANY CRITICAL or MAJOR flag is present, else true.

Return a valid SafetyReport JSON object. No markdown fences. No preamble."""


async def run_safety_critic(
    case: PatientCase,
    plan: TreatmentPlan,
    emit=None,                      # async callable | None, same signature as Stage 5
) -> SafetyReport:
    """Adversarial post-hoc review of the TreatmentPlan for THIS patient.

    Returns an empty-flags SafetyReport if the critic call fails — fail-open
    rather than fail-closed, because a missing safety review must not block
    the clinician seeing the plan. A logged warning is the failure signal.
    """
    client = _get_chat_client()
    model = _get_model_name()

    user_prompt = json.dumps({
        "patient": {
            "age": case.age,
            "sex": case.sex,
            "comorbidities": case.comorbidities,
            "current_medications": case.current_medications,
            "allergies": case.allergies,
            "vitals": case.vitals,
            "severity_staging": getattr(case, "severity_staging", {}) or {},
        },
        "recommendations": [
            {
                "index": i,
                "type": r.type,
                "action": getattr(r, "action", None),
                "intervention": r.intervention,
            }
            for i, r in enumerate(plan.recommendations)
        ],
    }, ensure_ascii=False)

    if emit:
        await emit("sub_step", {"stage": 6, "detail": "Safety review running…", "status": "running"})

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SAFETY_CRITIC_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw_json = resp.choices[0].message.content.strip()
        data = json.loads(raw_json)
        report = SafetyReport.model_validate(data)
        # Enforce the safe_to_proceed invariant regardless of LLM choice
        report.safe_to_proceed = not any(f.severity in ("CRITICAL", "MAJOR") for f in report.flags)
        return report
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning("Safety critic failed (%s); returning empty report (fail-open)", exc)
        return SafetyReport(flags=[], safe_to_proceed=True, reviewer_notes=f"Safety review unavailable: {exc.__class__.__name__}")
```

**Implementation notes:**
- Reuse the same chat client / model selector helpers Stage 5 uses (`_get_chat_client`, `_get_model_name` — verify exact names while reading `clinical_stages.py`). If those helpers are private or differently named, import the underlying `openai`/`bedrock` client constructor that Stage 5 uses. Do NOT add a new client construction code path.
- Model choice: prefer a Flash-class model (cheaper, faster) — if Stage 5 uses Opus/Sonnet for synthesis, override here with an env var `SAFETY_CRITIC_MODEL` defaulting to the Flash equivalent. Add `os.getenv("SAFETY_CRITIC_MODEL", model)` in `run_safety_critic`.
- The `_` helper imports may not exist — if they don't, replicate the inline `client = AsyncOpenAI(...)` / `client = ...Bedrock(...)` pattern from Stage 5 verbatim. Don't refactor existing helpers in this PR.

### 2. Models — `agent/models.py`

Add to the bottom of the file (after `TreatmentPlan`):

```python
# Re-exported from safety_critic so callers can import everything from .models
from .safety_critic import SafetyFlag, SafetyReport  # noqa: F401
```

If circular import becomes a problem (likely, since safety_critic imports from models), define `SafetyFlag` and `SafetyReport` directly in `models.py` and import them from there inside `safety_critic.py`. Pick one location — do not duplicate definitions.

### 3. Workflow integration — `agent/clinical_workflow.py`

Extend `WorkflowResult` to carry the report:

```python
@dataclass
class WorkflowResult:
    treatment_plan: TreatmentPlan
    ddx: list[DDxResult]
    cpgs: list[CPGDocRef]
    elapsed_ms: float
    stage_errors: list[str] = field(default_factory=list)
    safety_report: Optional[SafetyReport] = None     # NEW
```

Run the critic immediately after `stage_5_synthesize` in ALL THREE workflow functions (`run_clinical_workflow`, `run_clinical_workflow_streaming`, `run_resynthesize_streaming`). Example for the non-streaming path:

```python
# Stage 5 — Synthesize (unrecoverable if it fails)
treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence)

# Stage 6 — Safety review (fail-open, never raises)
from .safety_critic import run_safety_critic
safety_report = await run_safety_critic(case, treatment_plan)
```

For the streaming variants, after the critic returns emit a `safety_review` event:

```python
await emit("safety_review", safety_report.model_dump())
```

Place this **before** `final_result` is emitted so the UI receives the safety review on the same SSE connection.

### 4. API response — `agent/api.py`

Extend `ClinicalPlanResponse`:

```python
class ClinicalPlanResponse(_BaseModel):
    treatment_plan: TreatmentPlan
    ddx: list[dict]
    cpgs_matched: list[str]
    elapsed_ms: float
    stage_errors: list[str] = []
    safety_report: Optional[SafetyReport] = None       # NEW
```

In every place `ClinicalPlanResponse(...)` is constructed (lines 584, 622, 688 and any others), add `safety_report=result.safety_report`.

### 5. Doctor UI — SSE handler

In `Doctor UI/src/lib/clinicalApi.js`, add a `safety_review` branch to both `runClinicalPlanStream` and `resynthesizePlanStream` SSE dispatchers:

```javascript
// inside the SSE frame loop, alongside stage_update / sub_step
else if (eventType === 'safety_review' && onSafetyReview) onSafetyReview(payload);
```

Add `onSafetyReview` as a new optional callback parameter on both functions. Pipe it through from the caller (`Home.jsx` or wherever the streams are invoked).

### 6. Doctor UI — Safety banner

New file: `Doctor UI/src/components/sections/SafetyReviewBanner.jsx`

```jsx
// Mounted above CarePlanSection. Props:
//   report : SafetyReport | null
//   onAcknowledge : () => void   — flips local "acknowledged" state to unblock Approve
//
// Visual contract:
//   no flags          → green pill: "Safety review passed — no concerns flagged"
//   only MODERATE     → amber expandable: list flags, Approve remains enabled
//   any MAJOR/CRITICAL→ red expandable: list flags, Approve DISABLED until acknowledged
//
// Use existing shared components (GlassCard, Button, Pill) for styling consistency
// — match the look of existing alert banners in the codebase.
```

In `CarePlanSection.jsx`:
- Receive `safetyReport` as a prop (or via context, whichever pattern the existing care plan uses)
- Render `<SafetyReviewBanner report={safetyReport} onAcknowledge={...} />` immediately above the plan body
- Disable the existing "Approve" / "Sign & Close" CTA when `safetyReport && !safe_to_proceed && !acknowledged`

Mirror the styling decisions of any existing alert/banner component in the project — do not invent a new visual language.

---

## Out of scope

- ❌ Do NOT modify Stage 5 synthesis prompts or `clinical_stages.py` synthesis logic
- ❌ Do NOT have the critic rewrite or modify the `TreatmentPlan` — review only, no mutation
- ❌ Do NOT wire the critic into the legacy `/chat/stream` path or `prompts.py`
- ❌ Do NOT add a `SAFETY_CRITIC_*` table or persist the report — request-scoped only
- ❌ Do NOT block the API response when the critic fails — fail-open, log warning, return empty report
- ❌ Do NOT add KG / graph_search calls inside the critic in this PR — that's a future enhancement once Gap R6 lands
- ❌ Do NOT change `clinical_cli.py` — the CLI may show the report later, but not in this PR

---

## Tests — `tests/test_safety_critic.py`

Run with `pytest tests/test_safety_critic.py -v --no-cov`.

| Test | Setup | Assertion |
|---|---|---|
| `test_safety_flag_validates` | `SafetyFlag(severity="MAJOR", recommendation_index=0, flag_type="drug_interaction", detail="x")` | round-trips through `model_dump()` |
| `test_safety_flag_rejects_unknown_severity` | `SafetyFlag(severity="LOW", ...)` | raises ValidationError |
| `test_safety_report_safe_to_proceed_invariant` | Build `SafetyReport(flags=[MAJOR flag], safe_to_proceed=True)` directly, then call `run_safety_critic` with mock returning that JSON | resulting report has `safe_to_proceed == False` (post-processing enforces it) |
| `test_safety_critic_returns_flag_on_known_interaction` | Patient: on verapamil. Plan: recommends metoprolol (pharmacological start). Mock the LLM to return a hand-written SafetyReport with a MAJOR drug_interaction flag | report has ≥1 flag with severity in {"MAJOR","CRITICAL"} and `flag_type == "drug_interaction"` |
| `test_safety_critic_fail_open_on_invalid_json` | Mock client to return non-JSON garbage | returns `SafetyReport(flags=[], safe_to_proceed=True)`; no exception bubbles up |
| `test_safety_critic_fail_open_on_validation_error` | Mock client to return `{"flags": "not a list"}` | same fail-open behaviour |
| `test_workflow_result_carries_safety_report` | Patch `stage_5_synthesize` to return a stub `TreatmentPlan`; patch `run_safety_critic` to return a stub `SafetyReport`; call `run_clinical_workflow(case)` | `result.safety_report is not None` and equals the stubbed report |

For LLM-mocked tests, patch the client at the import site (`agent.safety_critic._get_chat_client` or whatever you ended up using) and inspect `messages[0]["content"]` to assert the adversarial system prompt is in place.

---

## E2E smoke test (run after unit tests pass)

Start the server (`python -m agent.api`). In the Doctor UI:

1. **Negative case (clean plan):** Patient with isolated essential hypertension, no allergies, no current meds. Run consultation. Expected: green "Safety review passed" pill. Approve button enabled.

2. **Positive case (interaction):** Patient on `verapamil`, comorbidity `chronic stable angina`. Run consultation. If Stage 5 recommends a beta-blocker (metoprolol/bisoprolol), the critic should flag the verapamil + beta-blocker AV-nodal additive risk as MAJOR. Banner is red. Approve button disabled until acknowledged.

3. **Allergy cross-reactivity case:** Patient with allergies `["sulfa"]`, presenting with heart failure. If Stage 5 recommends furosemide, the critic should flag CROSS_REACTS sulfa risk. MODERATE or MAJOR depending on the critic's call.

Capture screenshots of the three banner states (green/amber/red) and paste into the report-back.

---

## Acceptance criteria

- [ ] `pytest tests/test_safety_critic.py -v --no-cov` — all tests green
- [ ] `agent/safety_critic.py` exists with `SafetyFlag`, `SafetyReport`, `run_safety_critic`
- [ ] `SafetyFlag` / `SafetyReport` are importable from `agent.models` (re-export OR direct definition)
- [ ] All three workflow functions in `clinical_workflow.py` call `run_safety_critic` after Stage 5
- [ ] `WorkflowResult.safety_report` and `ClinicalPlanResponse.safety_report` populated
- [ ] Streaming endpoints emit a `safety_review` SSE event before `final_result`
- [ ] `runClinicalPlanStream` and `resynthesizePlanStream` in `clinicalApi.js` accept and dispatch `onSafetyReview`
- [ ] `SafetyReviewBanner.jsx` renders three states (green / amber / red) and disables Approve on red until acknowledged
- [ ] `/chat/stream` (legacy chat) is untouched
- [ ] `clinical_cli.py` still runs end-to-end — the new field is optional/nullable so the CLI ignores it
- [ ] E2E: all three smoke cases produce the expected banner state

---

## Report back

When done, tell the user:

1. **Files created/modified** — paths and 1-line summary each
2. **Test output** — last 30 lines of pytest
3. **E2E results** — banner state observed for each of the three smoke cases (link or paste screenshots)
4. **Open questions** — any spec ambiguity or codebase surprise that required a judgement call
