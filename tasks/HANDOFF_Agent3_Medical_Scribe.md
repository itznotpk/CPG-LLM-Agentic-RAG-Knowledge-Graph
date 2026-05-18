# HANDOFF — Agent 3: Medical Scribe (SOAP note generator)

> **For:** a Sonnet coding agent picking this up cold.
> **Author of handoff:** prior session, 2026-05-18. All claims below were verified against the live codebase on that date — file:line references are real, not illustrative.
> **Source of the task:** `tasks/Next-Step/Last Step Improvement/Agent_Architecture.md` → "Agent 3 — Medical Scribe" (lines 268–361).
> **Why this lane:** the **backend slice** (this handoff's scope) is fully self-contained, has zero ordering dependency on the two in-flight backend workstreams (Friend 1 = Phase A re-ingest; Friend 2 = DDx routing), touches no shared DB table, and carries the lowest hallucination risk (it formats already-approved structured data — it does not retrieve, reason, or synthesise new clinical content).
> **⚠️ Scope-justification check (read §0.1 BEFORE writing code):** `design_reconstruction.md` Step 4 (the SOAP view in `OutputSection.jsx`) is **already built** — but it renders SOAP *client-side* with no backend scribe. Agent 3 is therefore **not** "build a missing UI backend"; its only justification is a **server-authoritative canonical note for EMR/FHIR export + audit**. If the team has no such requirement, Agent 3 may be redundant — confirm scope with the requester before building. This handoff covers the backend only; do not modify `OutputSection.jsx`.

---

## 0. Read this first — the big picture (so you don't collide with anyone)

Four workstreams exist. Conflict status was audited 2026-05-18:

| Workstream | Owner | Touches | Status |
|---|---|---|---|
| Phase A — parent-child chunk rebuild | Friend 1 | `chunks` schema, full re-ingest (A-13→A-15) | code done thru A-12; big re-ingest pending |
| KG rebuild / wiring | Friend 1 (same re-ingest) | Neo4j, `graph_builder.py` | code done; full batch rides A-13/A-14 |
| DDx routing robustness (D1–D6) | Friend 2 | `icd11_codes`, `documents.icd11_scope`, Stage 3 routing | in progress, orthogonal |
| **Agent 3 — Medical Scribe** | **YOU** | **new file `agent/medical_scribe.py` + 1 new model + 1 new endpoint** | **not started — this doc** |

**Agent 3 is orthogonal to all three.** It runs *after* a `TreatmentPlan` already exists. It does not read `chunks`, `icd11_codes`, the KG, or any retrieval path. The only shared file you edit is `agent/models.py` (add one model — additive, no existing field changes) and `agent/api.py` (add one endpoint — additive). No git-merge hazard with the other lanes if you keep edits additive.

**Do NOT** touch: `clinical_stages.py`, `clinical_workflow.py`, `db_utils.py`, `graph_*.py`, `ingestion/*`, any `sql/migrations/*`, `icd11_codes`, `documents`. None of those are needed for this task.

---

## 0.1 Frontend status — `design_reconstruction.md` Step 4 IS built (verified against code 2026-05-18)

`Agent_Architecture.md` line 359 lists *"Step 4 SOAP view in `design_reconstruction.md` should be built first"* as a dependency. **That dependency is already satisfied** — verified by reading the actual frontend, not the doc.

**Important: `design_reconstruction.md` has no status tracking — it is a design/audit spec, not a progress doc.** Its line 23 ("Step 4 … currently a summary dump. No SOAP structure") is the *problem statement / "before" state the doc was written to fix*, NOT current status. Do not read that line as "unbuilt". The truth is in the code:

**Verified in `Doctor UI/src/components/sections/OutputSection.jsx` (read 2026-05-18):**
- `OutputSection.jsx:197-299` renders a full SOAP document view: `Subjective` (`:204`), `Objective (Vitals)` (`:215`), `Assessment` with ICD codes + CPG evidence (`:230`), `Plan` with start/stop meds, investigations, follow-up, unresolved (`:252-297`).
- `OutputSection.jsx:301-314` has the "Floating Action Bar": **Export to EMR**, **Print Instructions**, **Sign Note & Close** — exactly the priority-5 spec in `design_reconstruction.md:248`.
- Sibling reconstructed components also exist on disk: `TraceDrawer.jsx` (priority-3), `SafetyReviewBanner.jsx`, `SeverityStagingGrid.jsx`. The design_reconstruction work was substantially executed.

**So Step 4 is NOT a blocker — but it changes WHY Agent 3 exists. Read this carefully:**

The existing `OutputSection.jsx` builds the SOAP note **entirely client-side from React `state.carePlan`** (e.g. `:258` reads `carePlan.clinicalSummary`, `:264` reads `carePlan.medications.start[]`). It does **not** call any backend note endpoint, and its data shape (`carePlan.medications.start[]`) differs from the backend `TreatmentPlan.recommendations[]`.

| Reality | Implication for this task |
|---|---|
| A SOAP view already renders, client-side, with no backend scribe | Agent 3 is **not** "unblock a missing UI". The UI isn't missing. |
| It renders from frontend `carePlan` state, not from `TreatmentPlan` via an endpoint | Agent 3's value is **a server-side canonical note**: a single deterministic source of truth for EMR/FHIR export, audit trail, and signing — not "make SOAP appear on screen" (that already works). |
| Frontend uses a different data shape than the backend models | If/when the frontend is rewired to call `/clinical/note/generate`, a shape adapter is needed. **That rewiring is out of scope here** — but design the endpoint so it's a clean future target. |

**Decision the requester must confirm before you build (ASK if unsure):** Agent 3 is justified *only* if the team wants a **server-authoritative SOAP/clinical note** (for EMR export integrity, audit, FHIR — per `Agent_Architecture.md` "HL7 FHIR export" §). If the current client-side SOAP view is considered sufficient and there is no EMR/audit requirement, **Agent 3 may be redundant** and should be deferred rather than built to duplicate what `OutputSection.jsx` already shows. Do not build a backend that merely re-derives what the UI already renders with no consumer.

**If confirmed in scope:** proceed with the backend per §2 — the deliverable is the canonical note + endpoint, explicitly framed as the future EMR/audit source, with the frontend-rewiring called out as a separate downstream task (do NOT modify `OutputSection.jsx` yourself; note the shape-adapter need in the completion report).

---

## 1. What has already been achieved (verified state — context for you)

This section records what the *rest* of the system has proven, so you understand the platform you're plugging into. You do not need to re-verify this; it is background.

### 1.1 Phase 2 — Comorbidity routing (`RAG_Pipeline_and_Prompt_Gaps.md`) — ✅ DONE
- `route_comorbidities()` live at `agent/clinical_workflow.py:18-69`; called after Stage 3 in non-streaming (`:113`) and streaming (`:211`) paths, with a `sub_step` "comorbidity" badge emit at `:215`.
- Shipped code exceeds the original spec: 0.55 similarity threshold to reject semantic-fallback drift, `top_k=3` DDx lookup, dedup vs existing CPGs, `comorbidities[:4]` latency cap, full diagnostic logging.
- Cross-ref: `Gaps_Closing.md` Gap 1 "✅ CODE IMPLEMENTED"; validated in its Test Run 3 (58M ACS + T2DM + CKD + HTN) — HTN routed correctly, DM/CKD correctly *skipped* (below threshold) because those CPGs are not yet ingested (that data gap is `Gap_1_CPG_Ingestion.md`, a separate unowned item).

### 1.2 Phase 4 — KG deterministic wiring (R6) — ✅ DONE / partly Superseded
- **Consumer wiring (the actual point) is live in all 3 orchestrator paths:** KG lookup between Stage 4 and Stage 5 at `clinical_workflow.py:132` (non-streaming), `:251` (streaming), `:355` (re-synth), each fail-open (`try/except` → `[]` flags, never crashes synthesis).
- `clinical_graph_lookup()` at `agent/graph_clinical.py:298` covers `CONTRAINDICATED_WITH|INTERACTS_WITH` (`:130`), `REQUIRES_DOSE_ADJUSTMENT` (`:177`), `CROSS_REACTS_WITH` (`:230`). Candidate drugs grounded in retrieved chunks via `extract_candidate_drugs_from_chunks()` (`:265`).
- Flag injection into Stage 5: `format_flags_for_prompt(flags)` → `flags_block` inserted into the Stage 5 user prompt at `agent/clinical_stages.py:949` and `:968`; `stage_5_synthesize(..., flags=kg_flags)` signature at `:929`.
- **Superseded sub-steps (do not implement):** R6 step 1 (ICD on `(:Condition)` nodes) and step 3 (ICD-scoped `graph_search`) were *deliberately cancelled* — see `KG_Remaining_Edits_Plan.md` "Architectural decision 2026-05-17": the KG must stay global/unscoped so cross-CPG drug-interaction safety signals aren't suppressed.

### 1.3 Smoke / E2E results already on record (not run by this session — quoted from the planning docs, with their source)

| Test | What it proved | Source doc |
|---|---|---|
| **Phase A Step 1 unit smoke** | `pytest tests/test_clinical_stages.py` → **26 passed**. Content beyond the old 4k truncation now reaches Stage 5; oversized prompts blocked before Bedrock send; parent dedupe tracked; TreatmentPlan still validates. | `Phase_A_Step1_Synthesis_Fixes_Now.md` §S1-8 |
| **Phase A Step 2 — AF live ingest (A-12/A-12b)** | Migrations 006+007 applied; 217 chunks wiped; AF re-ingested → 12 sections → 96 chunks, 0 ingest errors. All 8 acceptance queries PASS (h1_leaf fully embedded, 0 bad parents, 17 chunks/25 cross_refs, `match_chunks` returns only embedded rows, 0 non-AF leakage). `icd11_codes`=3914 preserved. | `Phase_A_Step2_ParentChild_Ingest.md` A-12/A-12b |
| **KG Phase A code gate** | 105 triples / 10 AF chunks; severity 27% populated, 0 invalid severity values (controlled-vocab enforced); `evidence_list`/`cpg_chunk_ids`/`severity` written+appended correctly. | `KG_Remaining_Edits_Plan.md` Phase A gate |
| **KG Phase B.1 — AF dry-run** | 635 nodes / 784 edges. `INTERACTS_WITH` 16 edges (56% severity-tagged), `REQUIRES_DOSE_ADJUSTMENT` 19 edges (25 with `trigger`), `cpg_chunk_id` linkage 784/784, 10/10 sampled present in Postgres, 0 orphans/dupes/missing-evidence. Verdict: Phase A gate passes under realistic conditions. | `KG_Remaining_Edits_Plan.md` Phase B.1 |
| **KG Phase D — wiring smoke** | `scratch/test_phase_d_af.py`: AF polypharmacy patient (warfarin+digoxin+metoprolol, HF+renal) → 90 candidate drugs from 50 chunks, 11 flags with evidence + Postgres chunk UUIDs, 3215-char INTERACTION FLAGS block produced. Gates 1/2/3 PASS. | `KG_Remaining_Edits_Plan.md` Phase D gate |

**Still pending across the platform (NOT your job, just so you know what "done" excludes):** full-corpus re-ingest (A-13), KG full 16-CPG batch (B.2/A-14), end-to-end clinical smoke A-15, the warfarin/sulfa/CKD fixture validation for R6 step 6, and DDx D1–D6 smoke suite (Smoke 1–9 in `DDx_Routing_Robustness_And_Exclusion_Rerank.md`). Your work does not block, and is not blocked by, any of these.

---

## 2. Your task — Agent 3: Medical Scribe

### 2.1 One-sentence definition

After a clinician approves the AI-generated `TreatmentPlan`, transform the approved structured data (`PatientCase` + confirmed ICD-11 diagnoses + `TreatmentPlan`) into a standard **SOAP-format clinical note** ready for EMR export. **It transforms structured data into formatted text. It does not call retrieval, the KG, or generate new clinical content.**

### 2.2 SOAP mapping (authoritative — from `Agent_Architecture.md`)

| SOAP section | Source data |
|---|---|
| **S** — Subjective | `PatientCase.chief_complaint` + `PatientCase.history` |
| **O** — Objective | `PatientCase.vitals` (formatted) + `PatientCase.age` / `sex` |
| **A** — Assessment | confirmed ICD-11 codes + titles + `TreatmentPlan.confidence` |
| **P** — Plan | `TreatmentPlan.recommendations` (accepted only) + `monitoring` + `red_flags` |

### 2.3 Exact data shapes you are working with (verified in `agent/models.py`, 2026-05-18)

You do not need to change these; you consume them. Key fields:

- **`PatientCase`** (`models.py:226`): `chief_complaint: str` (required, non-empty), `history: str|None`, `age: int|None`, `sex: Literal["M","F","other"]|None`, `comorbidities: list[str]`, `current_medications: list[str]`, `allergies: list[str]`, `vitals: dict[str,float]` (e.g. `{"sbp":165,"dbp":95,"hr":110}`), `severity_staging: dict[str,str]`, `staged_comorbidities: list[StagedComorbidity]`.
- **`TreatmentPlan`** (`models.py:282`): `icd_primary: str`, `icd_alternates: list[str]`, `summary: str`, `recommendations: list[Recommendation]` (≥1 enforced), `monitoring: list[MonitoringItem]`, `red_flags: list[str]`, `follow_up: list[str]`, `confidence: float` (0–1), `unresolved_questions: list[str]`.
- **`Recommendation`** (`models.py:258`): `intervention: str`, `type: Literal["pharmacological","procedure","lifestyle","referral","investigation"]`, `action: Literal["start","stop","change","continue","contraindicated"]|None`, `evidence_grade: str|None`, `cpg_source: str`, `rationale: str`, `contraindications_checked: list[str]`.
- **`MonitoringItem`** (`models.py:274`): `parameter: str`, `schedule: str`, `target: str|None`, `cpg_ref: str|None`.

### 2.4 New model to add — `ClinicalNote`

Add to `agent/models.py` in the "Clinical Workflow Models" or a new "Scribe Models" section (additive; do not modify existing models). Use the project's existing pydantic v2 style (`Field(..., description=...)`, `field_validator`):

```python
class ClinicalNote(BaseModel):
    """Agent 3 output — SOAP note formatted from an approved TreatmentPlan."""
    soap_note: str = Field(..., description="Full SOAP-formatted note as markdown text")
    icd_codes: List[str] = Field(default_factory=list, description="Confirmed ICD-11 codes (primary first)")
    encounter_date: str = Field(..., description="ISO date of the encounter, e.g. '2026-05-18'")
    clinician_name: str = Field(..., description="Signing clinician")
    follow_up_date: Optional[str] = Field(None, description="ISO date if a follow-up is scheduled")
    export_ready: bool = Field(default=False, description="True once the note passed structural validation")
```

### 2.5 New module — `agent/medical_scribe.py`

**Pattern to follow: copy the structure of `agent/safety_critic.py`** (verified at that path, 123 lines). It is the closest analog — same generator→consumer shape, same provider/model env-var wiring, same fail-open discipline, same `openai.AsyncOpenAI` client usage with `response_format={"type": "json_object"}`, `temperature=0.0`.

Required public function:

```python
async def run_medical_scribe(
    case: PatientCase,
    plan: TreatmentPlan,
    confirmed_diagnoses: list[str],   # ICD codes the clinician confirmed (primary first)
    clinician_name: str,
    encounter_date: str | None = None,   # default: today's date, ISO
    emit=None,                            # optional async emit(event_type, data) for SSE parity
) -> ClinicalNote:
```

**Two viable implementations — pick deterministic-first (recommended):**

- **Recommended — deterministic formatter (no LLM):** Because every field is already structured and clinician-approved, you can build the SOAP markdown by direct string assembly. This is the lowest-hallucination, zero-cost, zero-latency path and matches the doc's stated principle ("It does not retrieve, reason, or synthesise new clinical content"). An LLM here can only *introduce* error. **Strongly prefer this.**
- **Optional — LLM polish pass:** If the team wants prose smoothing, gate it behind an env flag `SCRIBE_LLM_POLISH=1` (default off). Reuse the exact provider/model resolution block from `safety_critic.py:68-74` (`SCRIBE_LLM_*` → `STAGE5_LLM_*` → `LLM_*` fallback chain). The LLM may only rephrase; it must not add clinical facts. Keep the deterministic note as the fallback if the LLM call fails (fail-open, same as `safety_critic.py:116-122`).

**Fail-open contract (mandatory, mirror `safety_critic.py`):** if anything fails, return a `ClinicalNote` built from the deterministic path with `export_ready=False` and a note in `soap_note` that it is a fallback. A scribe failure must never block the clinician — but unlike the safety critic, a *blank* note is useless, so the deterministic build IS the fallback (never return empty).

**Date handling:** `encounter_date` default = `datetime.now().strftime("%Y-%m-%d")`. `follow_up_date`: parse from `plan.follow_up` if a concrete date/interval is present; otherwise leave `None` (do not invent a date — converting "review in 3 months" to an absolute date is acceptable arithmetic; inventing one where none is stated is not).

### 2.6 SOAP note structure to emit (markdown)

```
# Clinical Note — {encounter_date}

## Subjective
{chief_complaint}
{history or "No additional history recorded."}

## Objective
Age/Sex: {age or "—"} / {sex or "—"}
Vitals: {formatted vitals, e.g. "BP 165/95 mmHg, HR 110 bpm"} or "Not recorded."

## Assessment
Primary: {icd_primary} — {primary title if available}
{alternates listed if any}
Plan confidence: {confidence:.0%}
{summary}

## Plan
### Medications & Interventions
{numbered recommendations: intervention — action — cpg_source — rationale}
### Monitoring
{monitoring items: parameter — schedule — target — cpg_ref}
### Red Flags / Safety Netting
{red_flags as bullet list}
### Follow-up
{follow_up as bullet list}

---
Signed: {clinician_name}    Date: {encounter_date}
ICD-11: {comma-joined icd_codes}
```

Notes: omit empty sections gracefully (e.g. if `monitoring` is empty, print "None specified."). Map vitals keys to readable labels (`sbp/dbp`→"BP {sbp}/{dbp} mmHg", `hr`→"HR {hr} bpm", `spo2`→"SpO₂ {spo2}%", `rr`→"RR {rr}/min", `temp`→"Temp {temp} °C"); for unknown keys print `key {value}`. ICD titles: you only reliably have codes; if a title isn't passed in, print the code alone — do NOT look it up (that would couple you to `icd11_codes`, which is Friend 2's table).

### 2.7 API endpoint — `agent/api.py`

Add additively, following the existing `/clinical/plan` pattern (verified at `api.py:573-595`). Request/response models follow the `_BaseModel` convention at `api.py:47-69`.

```python
class ScribeRequest(_BaseModel):
    case: PatientCase
    treatment_plan: TreatmentPlan
    confirmed_diagnoses: list[str]
    clinician_name: str
    encounter_date: str | None = None

class ScribeResponse(_BaseModel):
    clinical_note: ClinicalNote

@app.post("/clinical/note/generate", response_model=ScribeResponse)
async def clinical_note_generate(request: ScribeRequest):
    from .medical_scribe import run_medical_scribe
    note = await run_medical_scribe(
        case=request.case,
        plan=request.treatment_plan,
        confirmed_diagnoses=request.confirmed_diagnoses,
        clinician_name=request.clinician_name,
        encounter_date=request.encounter_date,
    )
    return ScribeResponse(clinical_note=note)
```

Import `ClinicalNote` where `TreatmentPlan` is imported (`api.py:42`). Wrap in try/except like the sibling endpoints (`api.py:590-595`) but recall the fail-open rule — prefer returning a fallback note over a 500 unless the request itself is malformed.

Do **not** wire the scribe into `clinical_workflow.py` — it is explicitly a post-approval, clinician-triggered step, not a pipeline stage. The endpoint is the integration point.

---

## 3. Tests to write — `tests/test_medical_scribe.py`

Match house style (verified in `tests/test_safety_critic.py`): module docstring with run command, `_make_case()` / `_make_plan()` helper factories, `unittest.mock` (`AsyncMock`/`patch`) for any LLM client, no real network calls.

Required cases:

- `test_soap_has_all_four_sections` — output contains `## Subjective`, `## Objective`, `## Assessment`, `## Plan`.
- `test_subjective_maps_chief_complaint_and_history` — both strings appear under Subjective.
- `test_objective_formats_vitals` — `{"sbp":165,"dbp":95,"hr":110}` renders as `BP 165/95 mmHg, HR 110 bpm`.
- `test_assessment_includes_primary_icd_and_confidence` — `icd_primary` and the `confidence` % appear.
- `test_plan_lists_all_recommendations` — every `recommendation.intervention` appears, numbered.
- `test_empty_monitoring_renders_none_specified` — plan with `monitoring=[]` → "None specified.", not a crash or empty heading.
- `test_no_followup_date_when_none_stated` — `plan.follow_up=[]` → `ClinicalNote.follow_up_date is None` (no invented date).
- `test_encounter_date_defaults_to_today` — `encounter_date=None` → today's ISO date.
- `test_icd_codes_passed_through_primary_first` — `confirmed_diagnoses=["BA80","BC81.3"]` → `ClinicalNote.icd_codes == ["BA80","BC81.3"]`.
- `test_fail_open_returns_deterministic_note_not_empty` — force the optional LLM path to raise (mock) → `soap_note` is non-empty deterministic build, `export_ready=False`.
- `test_export_ready_true_on_clean_deterministic_build` — happy path → `export_ready=True`.
- (only if LLM polish implemented) `test_llm_polish_disabled_by_default` — without `SCRIBE_LLM_POLISH=1`, the mocked LLM client is never called.

Run command (match the repo convention seen in `test_safety_critic.py:4`):

```
pytest tests/test_medical_scribe.py -v --no-cov
```

No real Bedrock / OpenAI / DB calls in pytest. If LLM polish is implemented, mock the client exactly as `tests/test_safety_critic.py:59` (`_mock_client`) does.

---

## 4. Definition of done

1. `agent/models.py` — `ClinicalNote` added, additive only, existing models byte-unchanged.
2. `agent/medical_scribe.py` — `run_medical_scribe()` implemented, deterministic-first, fail-open, no retrieval/KG/DB imports.
3. `agent/api.py` — `/clinical/note/generate` endpoint added additively; `ClinicalNote` imported.
4. `tests/test_medical_scribe.py` — all cases in §3 green; `pytest tests/test_medical_scribe.py -v --no-cov` passes with zero network calls.
5. Full existing suite still green for the files you touched: `pytest tests/test_safety_critic.py tests/test_clinical_schemas.py -v --no-cov` (sanity that the `models.py` addition broke nothing).
6. No edits to: `clinical_stages.py`, `clinical_workflow.py`, `db_utils.py`, `graph_*.py`, `ingestion/*`, `sql/*`.
7. A short completion report appended to the bottom of THIS file (§6 template) with: files changed, test output (last ~20 lines), one sample rendered SOAP note pasted verbatim from a test fixture, and any deviations.

---

## 5. Hazards / things people get wrong here

- **Do not LLM-generate the clinical content.** The whole safety argument for this agent is that it only re-formats approved data. An LLM that "improves" the plan reintroduces hallucination into the one component designed to have none. Deterministic build is the default; LLM is opt-in polish only, prose-only, never additive.
- **Do not look up ICD titles from `icd11_codes`.** That table is Friend 2's (`DDx_Routing...`); coupling to it creates a cross-lane dependency for zero benefit. Print codes; accept titles only if passed in by the caller.
- **Do not wire into the pipeline.** It is post-approval and clinician-triggered. Pipeline insertion changes latency and is out of scope (and would collide with `clinical_workflow.py`, a hot file for the other lanes).
- **Do not invent dates.** Converting a stated interval ("review in 3 months") to an absolute date is fine; fabricating a follow-up date where the plan states none is a clinical defect.
- **Fail-open ≠ fail-empty.** Unlike the safety critic (empty report is acceptable), an empty note is useless. The deterministic build is itself the fallback. Never return a `ClinicalNote` with empty `soap_note`.
- **pydantic v2 only.** This repo is pydantic v2 (`field_validator`, `model_validator`, `ConfigDict` — see `models.py:7`). Do not use v1 patterns.

---

## 6. Completion report (fill this in when done — do not delete the template)

```
### Agent 3 — Completion Report (date: __________)

Files created:
- agent/medical_scribe.py
- tests/test_medical_scribe.py

Files modified (additive only):
- agent/models.py        (added ClinicalNote)
- agent/api.py           (added /clinical/note/generate)

Test output (pytest tests/test_medical_scribe.py -v --no-cov, last ~20 lines):
<paste>

Regression sanity (pytest tests/test_safety_critic.py tests/test_clinical_schemas.py -v --no-cov):
<paste pass count>

Sample rendered SOAP note (verbatim, from test fixture):
<paste one full note>

Deviations from this handoff (and why):
<list, or "none">

Scope confirmation (REQUIRED — answer before "done"):
- Did the requester confirm Agent 3 is wanted as a SERVER-AUTHORITATIVE note for
  EMR/FHIR/audit (per §0.1)? [yes / no / deferred]
- If "no/deferred": stop — do not build a backend that duplicates the existing
  client-side SOAP view in OutputSection.jsx. Record the reasoning here.

Follow-ups noticed but not done:
- REQUIRED ENTRY: "OutputSection.jsx already renders SOAP client-side from
  state.carePlan and does NOT call /clinical/note/generate. Rewiring the
  frontend to consume the backend note (incl. a carePlan→TreatmentPlan shape
  adapter) is a separate downstream task, out of scope here (see §0.1).
  OutputSection.jsx was NOT modified by this work."
- <any others, or nothing more>

Frozen API contract for the frontend implementer (paste the final ScribeRequest /
ScribeResponse field list so OutputSection.jsx has a defined target, not a guess):
<paste>
```
