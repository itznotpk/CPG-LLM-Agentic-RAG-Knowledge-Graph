# Handoff — Gap 4: Severity Staging in PatientCase + Doctor UI

> **For:** Sonnet 4.6 (thinking: Medium)
> **Reference:** `tasks/Next-Step/Gaps_Closing.md` Gap 4 (preserved spec) — read first
> **Also retires:** the deferred Gap D1 (comorbidity → ICD map) by introducing structured comorbidity payloads
>
> CPGs are stratified by severity: NYHA Class for HF, WHO FC for PAH, CKD stage for renal, HbA1c for DM, LVEF for HF phenotype. Today the pipeline embeds these as free text inside `history` / `comorbidities`, so retrieval queries score against generic "treatment" sections instead of FC-III-specific or eGFR-stratified chunks. Stage 4 cannot retrieve what it doesn't know to ask for.
>
> This task adds structured staging input end-to-end: model → API → UI → retrieval query injection.

---

## Pre-flight — read these first

1. `agent/models.py` (lines 210–230) — current `PatientCase`
2. `agent/clinical_stages.py` — `_generate_retrieval_queries` (look for `_load_prompt("stage4_query_generation.txt")`)
3. `agent/prompts/stage4_query_generation.txt` — current 5-domain query template
4. `Doctor UI/src/lib/clinicalApi.js` — `buildClinicalPlanBody` (lines 4–35) — UI → API payload mapper
5. `Doctor UI/src/components/sections/DataInputSection.jsx` — host for new input grid
6. `Doctor UI/src/components/sections/VitalsGrid.jsx` (used by DataInputSection) — pattern to mirror for the new grid

Do NOT modify `clinical_cli.py`, `clinicalMappers.js`, `routing.py`, `clinical_workflow.py`, or `db_utils.py`.

---

## Deliverables (4 surfaces)

### 1. Backend model — `agent/models.py`

Extend `PatientCase` with two new fields:

```python
class StagedComorbidity(BaseModel):
    """Structured comorbidity entry — supersedes free-text strings.
    Frontend submits this when the clinician picks from a dropdown."""
    icd_code: Optional[str] = Field(None, description="ICD-11 code if known, e.g. '5A11', 'GB61.3'")
    label: str = Field(..., description="Human-readable label, e.g. 'Type 2 Diabetes Mellitus', 'CKD Stage 3'")
    severity: Optional[str] = Field(None, description="Severity qualifier, e.g. 'Stage 3b', 'NYHA III'")


class PatientCase(BaseModel):
    """Stage 1 input — structured patient record passed into the clinical workflow."""

    chief_complaint: str = Field(..., description="Presenting symptoms — required, non-empty free text")
    history: Optional[str] = Field(None, description="Patient history narrative")
    age: Optional[int] = Field(None, ge=0, le=130, description="Patient age in years")
    sex: Optional[Literal["M", "F", "other"]] = Field(None, description="Biological sex")
    # KEEP the free-text comorbidities list for backward compatibility with existing CLI / older UI
    comorbidities: List[str] = Field(default_factory=list, description="Free-text comorbidity list (legacy)")
    current_medications: List[str] = Field(default_factory=list, description="Current medication names")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")
    vitals: Dict[str, float] = Field(default_factory=dict, description="Vital signs")
    # NEW — structured severity staging dictionary
    severity_staging: Dict[str, str] = Field(
        default_factory=dict,
        description="Structured staging: NYHA, WHO_FC, CKD_stage, HbA1c, LVEF, eGFR, etc.",
    )
    # NEW — optional structured comorbidities (retires Gap D1 deterministic map)
    staged_comorbidities: List[StagedComorbidity] = Field(
        default_factory=list,
        description="Structured comorbidities with ICD codes. Frontend may populate either this OR comorbidities (free text).",
    )

    @field_validator("chief_complaint")
    @classmethod
    def chief_complaint_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("chief_complaint must not be empty or whitespace-only")
        return stripped
```

**Do not remove `comorbidities`** — the CLI test harness uses it; backward compatibility matters.

### 2. Retrieval prompt — `agent/prompts/stage4_query_generation.txt`

Inject severity context into the existing 5-domain template. Locate the template variables block and add a `{severity_staging}` placeholder. The prompt must:

- Pass severity into domain 1 (PHARMACOTHERAPY) — so "first-line pharmacotherapy heart failure" becomes "first-line pharmacotherapy heart failure NYHA III LVEF 35%"
- Pass severity into domain 4 (DOSE ADJUSTMENT) — so "metformin dose CKD" becomes "metformin dose CKD stage 3b eGFR 42"
- Mention severity in domain 5 (ESCALATION) — so escalation criteria are stratified
- If `severity_staging` is empty, render as "not specified" and the LLM should skip the qualifier

Then update `_generate_retrieval_queries` in `clinical_stages.py` to format the staging dict and inject:

```python
staging_str = ", ".join(f"{k} {v}" for k, v in case.severity_staging.items()) or "not specified"
# Pass to the prompt template renderer
prompt = QUERY_GEN_PROMPT.format(
    chief_complaint=case.chief_complaint,
    ...,
    severity_staging=staging_str,
)
```

Find the existing `.format(...)` call in `_generate_retrieval_queries` and add the new key. If the function builds the prompt via string concatenation, add a line near the top of the prompt: `"Severity / staging: {staging_str}"`.

### 3. UI — new `SeverityStagingGrid` component

Create `Doctor UI/src/components/sections/SeverityStagingGrid.jsx`. Mirror the style of `VitalsGrid.jsx`. The grid lists 6 common staging fields with input boxes, all optional:

| Field key | Label | Input type | Example placeholder |
|---|---|---|---|
| `NYHA` | NYHA Class | select (I/II/III/IV) | – |
| `WHO_FC` | WHO Functional Class (PAH) | select (I/II/III/IV) | – |
| `CKD_stage` | CKD Stage | select (1/2/3a/3b/4/5) | – |
| `HbA1c` | HbA1c % | text | "9.2" |
| `LVEF` | LVEF % | text | "35" |
| `eGFR` | eGFR (calculated or measured) | text | "42" |

State shape: `{ NYHA: "III", CKD_stage: "3b", ... }` — only populated fields submitted.

Mount it in `DataInputSection.jsx` BELOW `VitalsGrid`, behind an expandable disclosure (default collapsed). Use existing GlassCard / Button shared components for consistent look.

Optional bonus — auto-calculate eGFR from existing vitals + age + sex using the CKD-EPI 2021 formula if creatinine is in vitals. Pre-populate the eGFR field. Mark it as `(auto)` next to the label if calculated; user can override.

### 4. API mapper — `Doctor UI/src/lib/clinicalApi.js`

In `buildClinicalPlanBody`, add the new payload fields:

```javascript
return {
  case: {
    chief_complaint: clinicalNotes || patientState.chiefComplaint || '',
    // ... existing fields ...
    severity_staging: stagingData || {},
    // staged_comorbidities is optional — only populate if UI sends structured form
    ...(structuredComorbidities ? { staged_comorbidities: structuredComorbidities } : {}),
  }
};
```

Update the function signature to accept the new `stagingData` and `structuredComorbidities` arguments. Pipe them through from the React component that calls `runClinicalPlan` / `runClinicalPlanStream`.

---

## Out of scope

- ❌ Do NOT change `clinical_cli.py` — it has no UI staging input and will simply pass empty `severity_staging={}`
- ❌ Do NOT change `route_comorbidities` in `clinical_workflow.py` — it still consumes `case.comorbidities` (free-text list)
- ❌ Do NOT touch `clinicalMappers.js` — staging is input only, never displayed back in the care plan
- ❌ Do NOT add a `staging` column to any database table — this is request-scoped state, not persisted (Doctor UI does keep its own session state; that's separate)
- ❌ Do NOT auto-fill `severity_staging` from `comorbidities` strings server-side — that's parser code that would shadow the structured input. Frontend submits structured; backend trusts it.
- ❌ Do NOT remove the free-text `comorbidities` field — CLI harness depends on it

---

## Tests — `tests/test_severity_staging.py`

Write 6 unit tests. Run with `pytest tests/test_severity_staging.py -v --no-cov`.

| Test | What it asserts |
|---|---|
| `test_patientcase_severity_staging_optional` | `PatientCase(chief_complaint="x")` works without staging; `.severity_staging == {}` |
| `test_patientcase_severity_staging_populated` | `PatientCase(chief_complaint="x", severity_staging={"NYHA":"III","CKD_stage":"3b"})` round-trips through `.model_dump()` and back |
| `test_patientcase_staged_comorbidity_populated` | Constructs `PatientCase` with `staged_comorbidities=[{"icd_code":"5A11","label":"T2DM","severity":None}]`; asserts `.staged_comorbidities[0].icd_code == "5A11"` |
| `test_patientcase_staged_comorbidity_label_required` | `StagedComorbidity()` without label raises ValidationError |
| `test_query_generation_injects_staging` | Mock LLM call; assert generated prompt contains the string `"NYHA III"` when `severity_staging={"NYHA":"III"}` is passed |
| `test_query_generation_omits_staging_when_empty` | Same prompt with `severity_staging={}` renders as `"not specified"` or omits the staging line entirely |

For tests 5 + 6, patch the OpenAI client and inspect the `messages[0]["content"]` argument passed to `chat.completions.create`.

---

## E2E smoke test (Sonnet runs this after unit tests pass)

Start the server (`python -m agent.api`). In the Doctor UI:

1. Run a baseline consultation with Test Case 1 (58M ACS narrative, T2DM, CKD Stage 3, HTN) — **no staging filled in**
2. Run the same consultation **with staging**: `NYHA=II`, `CKD_stage=3b`, `HbA1c=9.2`, `LVEF=55`

Compare the Stage 4 query lines emitted in CLI/SSE between the two runs. Expected differences:

- Run 1 (no staging): `"first-line pharmacotherapy HFpEF with hypertension CKD stage…"`
- Run 2 (with staging): `"first-line pharmacotherapy HFpEF NYHA II LVEF 55% hypertension CKD stage 3b…"`

Capture both runs' Stage 4 query sub_step lines and paste into the report-back.

---

## Acceptance criteria

- [ ] `pytest tests/test_severity_staging.py -v --no-cov` — 6 tests green
- [ ] `PatientCase` round-trips `severity_staging` and `staged_comorbidities` through Pydantic without warnings
- [ ] `agent/prompts/stage4_query_generation.txt` references `{severity_staging}` (or equivalent placeholder)
- [ ] `_generate_retrieval_queries` injects staging string when present
- [ ] `SeverityStagingGrid.jsx` exists, renders a 6-field grid, mounts in `DataInputSection.jsx` as a collapsible section
- [ ] `clinicalApi.js` `buildClinicalPlanBody` accepts a staging argument and includes it in the request body
- [ ] E2E: Run 2 retrieval queries clearly differ from Run 1 by containing the staging qualifiers in at least domain 1 (pharmacotherapy) and domain 4 (dose adjustment)
- [ ] No regression in CLI smoke (`clinical_cli.py` continues to work — staging just sends as `{}`)

---

## Report back

When done, tell the user:

1. **Files created/modified** — paths and 1-line summary each
2. **Test output** — last 30 lines of pytest
3. **CLI smoke** — Test Case 1 run via `clinical_cli.py` (sanity check that `severity_staging={}` doesn't break anything)
4. **E2E smoke** — paste both Stage 4 query sub_step lines (no-staging vs with-staging) showing the difference
5. **Auto-eGFR decision** — whether you implemented CKD-EPI 2021 auto-calc bonus; if so, paste the formula
6. **Deviations from this brief** — anything you changed and why
7. **Follow-up noticed** — anything outside scope worth flagging
