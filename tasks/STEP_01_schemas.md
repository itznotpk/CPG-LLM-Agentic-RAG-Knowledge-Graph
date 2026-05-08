# Step 01 — Clinical Workflow Schemas

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system that helps clinicians by:
1. Taking patient case data
2. Predicting ICD-11 code(s) from symptoms
3. Routing to the correct CPG document(s)
4. Retrieving evidence chunks
5. Producing a structured treatment plan

The full design lives in [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) — read it before starting.

This is **Step 01 of 8**. It is the schema foundation: the typed contracts that every later stage will produce or consume. Nothing else in the pipeline should be touched in this step.

The codebase already uses Pydantic v2. Existing models live in [agent/models.py](../agent/models.py) — follow the conventions in that file (use `Field(...)` with descriptions, `ConfigDict`, `field_validator` where appropriate, `Literal` for enums).

## Objective

Add three new Pydantic models — `PatientCase`, `Recommendation`, `TreatmentPlan` — to [agent/models.py](../agent/models.py), with validation, and a passing test file that round-trips JSON for each.

## Preconditions

- Read [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) §5 (data contracts) for the target shape.
- Read [agent/models.py](../agent/models.py) in full to match style.
- The project runs on Python 3.11+, Pydantic v2. `pytest` is configured (see [pytest.ini](../pytest.ini)).

## Deliverables

### 1. Add to [agent/models.py](../agent/models.py)

Add these models in a new section labelled `# Clinical Workflow Models` placed **after** the `# Agent Models` section and **before** `# Ingestion Models`.

#### 1.1 `PatientCase`
Stage 1 input — the structured patient record passed into the clinical workflow.

Fields:
- `chief_complaint: str` — required, non-empty, free text describing presenting symptoms.
- `history: Optional[str]` — patient history narrative.
- `age: Optional[int]` — `ge=0, le=130`.
- `sex: Optional[Literal["M", "F", "other"]]`.
- `comorbidities: List[str]` — default empty list.
- `current_medications: List[str]` — default empty list.
- `allergies: List[str]` — default empty list.
- `vitals: Dict[str, float]` — default empty dict (e.g. `{"sbp": 165, "dbp": 95, "hr": 110}`).

Add a `field_validator` on `chief_complaint` that strips whitespace and rejects empty strings after stripping.

#### 1.2 `Recommendation`
Single clinical recommendation produced in Stage 5.

Fields:
- `intervention: str` — what to do (e.g. "Sildenafil 50 mg PRN").
- `type: Literal["pharmacological", "procedure", "lifestyle", "referral", "investigation"]`.
- `evidence_grade: Optional[str]` — e.g. `"Grade A, Level 1"`.
- `cpg_source: str` — required citation, e.g. `"CPG AF Management §4.2"`.
- `rationale: str` — required, non-empty.
- `contraindications_checked: List[str]` — default empty list.

#### 1.3 `TreatmentPlan`
Stage 5 output — the final structured plan returned to the doctor.

Fields:
- `icd_primary: str` — required, the highest-confidence ICD-11 code.
- `icd_alternates: List[str]` — default empty list.
- `recommendations: List[Recommendation]` — required, **must be non-empty** (add a `field_validator` enforcing `len >= 1`). If the system genuinely produces zero recommendations, that should surface via `unresolved_questions` instead — never as an empty plan.
- `monitoring: List[str]` — default empty list.
- `red_flags: List[str]` — default empty list.
- `confidence: float` — `ge=0.0, le=1.0`.
- `unresolved_questions: List[str]` — default empty list.

### 2. Create `tests/test_clinical_schemas.py`

Pytest tests covering:
- Valid construction of each model with minimal required fields.
- Valid construction of each model with all fields populated.
- JSON round-trip: `model.model_dump_json()` → `Model.model_validate_json(...)` produces an equal model.
- Validation failures:
  - `PatientCase(chief_complaint="")` raises `ValidationError`.
  - `PatientCase(chief_complaint="   ")` raises `ValidationError` (whitespace-only).
  - `PatientCase(age=-1)` raises `ValidationError`.
  - `Recommendation(type="hocus_pocus", ...)` raises `ValidationError` (bad literal).
  - `TreatmentPlan(..., recommendations=[])` raises `ValidationError`.
  - `TreatmentPlan(..., confidence=1.5)` raises `ValidationError`.

Follow the test patterns already used in [tests/](../tests/) if any exist; otherwise standard pytest with `pytest.raises(ValidationError)`.

## Implementation guidance

- Match the existing file's style: `Field(..., description="...")` for documented fields.
- Don't add custom JSON encoders — Pydantic v2 handles `Literal`, `List`, `Dict` natively.
- Don't import anything new outside what's already in `agent/models.py` (Pydantic, typing, datetime, enum).
- Keep models flat — no nested helper classes beyond the three named.
- The `vitals` dict is intentionally untyped (`Dict[str, float]`) for v1 — don't add a `Vitals` model.

## Out of scope

- ❌ Do NOT modify any other models in `agent/models.py`.
- ❌ Do NOT touch `agent/agent.py`, `agent/tools.py`, `agent/api.py`, or anything in `ingestion/`, `ddx/`, `sql/`.
- ❌ Do NOT add database persistence, ORM mapping, or migrations.
- ❌ Do NOT add an audit trail, logging, or observability — explicitly deferred.
- ❌ Do NOT wire these models into any existing endpoint yet.
- ❌ Do NOT install new dependencies.
- ❌ Do NOT add docstring-only "examples" or `model_config["json_schema_extra"]` blocks unless trivially small.

## Done criteria

All four must pass:

1. `pytest tests/test_clinical_schemas.py -v` — all tests green.
2. `python -c "from agent.models import PatientCase, Recommendation, TreatmentPlan; print('ok')"` prints `ok`.
3. `python -c "from agent.models import PatientCase; PatientCase(chief_complaint='chest pain', age=55, sex='M').model_dump_json()"` runs without error.
4. The existing test suite still passes: `pytest` (no regressions in unrelated tests).

## Report back

When you finish, tell the user:
1. **Files changed** — exact paths.
2. **Test output** — last ~20 lines of `pytest tests/test_clinical_schemas.py -v`.
3. **Any deviations** from this brief and why (e.g. you renamed a field, added a validator not requested, etc.).
4. **Follow-ups noticed but not done** — anything you spotted that should become a future step (do not act on these now).
