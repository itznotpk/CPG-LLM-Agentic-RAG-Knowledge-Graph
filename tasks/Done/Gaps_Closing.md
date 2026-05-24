# Clinical Pipeline — Gap Closing Plan

> **STATUS: CLOSED (2026-05-24).** All in-scope gaps resolved or formally deferred to other tracking docs.
> Remaining follow-ups live in `Gap_1_CPG_Ingestion.md` (DM/CKD ingestion) and `RAG_Pipeline_and_Prompt_Gaps.md` (Gap R6 KG wiring).

> Audit of the current ICD-11 → Care Plan generation pipeline against real clinical requirements.
> Each gap is rated by patient safety impact and includes a concrete implementation plan.

---

## Current pipeline (reference)

```
PatientCase
    │
    ▼ Stage 2 — DDx
    ICD-11 codes (top-5, re-ranked by Gemini 2.5 Flash thinking)
    │
    ▼ Stage 3 — Route (top-2 codes only)
    CPG document IDs (structural match + semantic fallback)
    │
    ▼ Stage 4 — Retrieve
    Top-20 chunks via 3 free-form LLM-generated queries, scoped to CPG IDs
    │
    ▼ Stage 5 — Synthesize
    TreatmentPlan (recommendations + monitoring + red_flags + confidence)
```

**What is already solid:**
- Two-pass DDx (vector + Gemini clinical re-rank) — better than most commercial tools
- Structural ICD→CPG routing with semantic fallback — correct architecture
- `unresolved_questions` field — honest safety valve when evidence is absent
- Clinician override / re-synthesis (Step 10) — directly addresses autonomy gap
- `confidence` score on TreatmentPlan — transparent about evidence coverage

---

## Gap 1 — Comorbidity routing is blind

**Status: ✅ CODE IMPLEMENTED — ⚠️ DATA INCOMPLETE (see `Gap_1_CPG_Ingestion.md`)**

**Safety impact: CRITICAL**

### Resolution summary (2026-05-11)

- `route_comorbidities()` added in `agent/clinical_workflow.py`, called after `stage_3_route` in both streaming and non-streaming workflows
- Per-comorbidity DDx lookup (`top_k=3`) with 0.55 similarity threshold to reject semantic-fallback drift
- Full diagnostic logging: candidate codes/similarities + ICD → CPG mapping per comorbidity
- Streaming path emits `[comorbidity]` badge `sub_step` events for each additional CPG
- Clinical synonym expansion added to `ddx/search_ddx.py` `normalize_query()` — abbreviations (CKD, T2DM, HFpEF, etc.) expanded to ICD-11 full-form terminology before vector embedding
- 11 unit tests in `tests/test_extraction_and_routing.py` covering threshold, dedup, capping, error paths — all passing

### Validated in Test Run 3 (58M ACS, T2DM, CKD, HTN)

| Comorbidity | DDx top match | Similarity | Routed to |
|---|---|---|---|
| Hypertension | `BA03` Hypertensive crisis | 0.75 | Hypertension(5th Edition), CVD-Prevention-Women ✅ |
| Type 2 Diabetes Mellitus | `5A13.3` DM due to endocrinopathies | 0.57 | **No DM CPG ingested** ⚠️ |
| CKD Stage 3 | `2E63` Melanoma in situ (junk) | 0.26 | Skipped (below threshold) ✅ |

### Remaining gap (data, not code)

DM and CKD CPGs are not ingested. Comorbidity routing works correctly when data exists, but cannot route to documents that don't exist. **See `Gap_1_CPG_Ingestion.md` for the ingestion plan.**

---

### Original gap description (preserved for context)


### What the current system does
Stage 3 routes using only the **top-2 DDx ICD-11 codes**. Comorbidities listed in `PatientCase.comorbidities` are passed as plain text into the Stage 5 synthesis prompt but are never used to retrieve additional CPG documents.

### Why this is dangerous
A patient presenting with pulmonary hypertension who also has CKD Stage 3 and T2DM:

- The system routes to: `Pulmonary-Arterial-Hypertension CPG` + `Heart-Failure CPG`
- It **never retrieves**: CKD CPG, T2DM CPG
- The CKD CPG contains critical guidance: *avoid NSAIDs, adjust metformin dose below eGFR 30, target BP <130/80 in proteinuric CKD*
- The T2DM CPG contains guidance on: *SGLT2 inhibitors beneficial in HF comorbidity, GLP-1 RA cardioprotection*

Because those CPGs are never in the evidence pool, Stage 5 synthesis invents dosing adjustments and drug choices **from LLM training data**, not grounded evidence. The `cpg_source` field will cite a real document but the content is hallucinated from memory — the worst kind of error because it looks legitimate.

### Why clinicians cannot catch this
The AI Reasoning Trace shows which CPGs were routed. A clinician who sees "Pulmonary-Arterial-Hypertension(2011), Heart-Failure(5th Edition)" has no signal that the CKD and T2DM CPGs were never consulted. The treatment plan looks complete.

### Implementation plan

**Backend — `agent/clinical_workflow.py`**

Add `route_comorbidities()` after Stage 3, before Stage 4:

```python
async def route_comorbidities(
    comorbidities: list[str],
    existing_doc_ids: set[str],
    top_k: int = 3,
) -> list[CPGDocRef]:
    """
    Map free-text comorbidities to ICD codes via DDx search,
    then route those codes to CPG documents not already in the pool.
    """
    from ddx.search_ddx import search_ddx
    additional: dict[str, CPGDocRef] = {}
    for comorbidity in comorbidities[:4]:          # cap at 4 to limit latency
        hits = await search_ddx(comorbidity, top_k=1)
        if not hits:
            continue
        icd_code = hits[0]["code"]
        refs = await route_icd_to_cpgs(icd_code, top_k=2)
        for ref in refs:
            if ref.cpg_name not in additional:
                # Only add CPGs not already in primary routing set
                new_ids = [d for d in ref.document_ids if d not in existing_doc_ids]
                if new_ids:
                    additional[ref.cpg_name] = ref
    return list(additional.values())[:top_k]
```

In `run_clinical_workflow_streaming` and `run_resynthesize_streaming`:

```python
# After stage_3_route:
existing_ids = {doc_id for cpg in cpgs for doc_id in cpg.document_ids}
comorbidity_cpgs = await route_comorbidities(case.comorbidities, existing_ids)
all_cpgs = (cpgs + comorbidity_cpgs)[:5]   # cap total CPGs at 5

# Emit comorbidity CPGs to trace
for ref in comorbidity_cpgs:
    await emit("sub_step", {
        "stage": 3,
        "detail": ref.cpg_name,
        "badge": f"{ref.match_type} (comorbidity)",
        "status": "complete",
    })
```

**Frontend — `PipelineProgress.jsx`**

Show comorbidity-routed CPGs with a distinct badge colour (e.g. purple `bg-purple-100 text-purple-700`) to distinguish from primary routing hits.

**Files to change:** `agent/clinical_workflow.py`, `agent/clinical_stages.py` (if extracting helper), `PipelineProgress.jsx`
**Effort:** ~3 h
**Test:** Add a fixture patient with 2 comorbidities; assert the comorbidity CPG document IDs appear in `document_id_filter` passed to Stage 4.

---

## Gap 2 — No structured drug interaction / allergy check

**Status: 🟡 DEFERRED — folded into knowledge-graph work in `RAG_Pipeline_and_Prompt_Gaps.md` (Gap R6).**

A hardcoded `HIGH_RISK_PAIRS` lookup table was designed but not implemented. Reason: the knowledge graph (Gap R6) is the principled long-term solution — `(Drug)-[INTERACTS_WITH]->(Drug)` and `(Drug)-[CONTRAINDICATED_IN]->(Condition)` relations extracted from CPG text give evidence-grounded flags with real citations, scalable beyond a ~20-pair maintained list. Doing both creates retire-debt.

**Bridge until KG lands:** the Stage 5 synthesis prompt (`stage5_synthesis.txt`) already instructs the LLM to populate `contraindications_checked` for every recommendation and to never leave it empty when patient has allergies or current medications. This is "good enough" for monitored clinical pilot — clinicians remain in the loop.

**Full design preserved in:** `tasks/RAG_Pipeline_and_Prompt_Gaps.md` (Gap R6 section, refined).

---

## Gap 3 — 3 retrieval queries is too few and wrong shape

**Safety impact: HIGH**

### What the current system does
`_generate_retrieval_queries` asks the LLM to generate 3 free-form queries from the patient context. In practice all 3 tend to cluster around the same semantic region: *"treatment of [condition]"*. They miss entire clinical decision domains.

### Why this matters
CPG documents are structured around distinct clinical decisions. A CPG on heart failure has separate sections for:
- First-line pharmacotherapy (ARNI, beta-blocker, SGLT2i)
- Monitoring protocols (BNP, echo at 3 months, renal function)
- Escalation / device therapy (ICD, CRT indications)
- Specific populations (renal impairment, elderly, pregnancy)

If all 3 queries ask about "heart failure treatment", the monitoring and escalation sections are never retrieved. The care plan's `monitoring` and `red_flags` fields end up empty or hallucinated.

### Example of current vs proposed query output

**Current (3 free-form):**
1. "pulmonary hypertension management in left heart disease"
2. "pulmonary arterial hypertension diagnosis and treatment algorithm"
3. "heart failure preserved ejection fraction comorbid pulmonary"

All three cluster around drug therapy. Monitoring, contraindications, and escalation are unrepresented.

**Proposed (5 domain-templated):**
1. "first-line pharmacotherapy {condition} {severity_class}"
2. "contraindications drug interactions {current_medications} {condition}"
3. "monitoring parameters follow-up intervals targets {condition}"
4. "dose adjustment renal hepatic impairment {comorbidities}"
5. "escalation referral criteria specialist {condition}"

### Implementation plan

**In `_generate_retrieval_queries` — replace free-form generation with domain-templated:**

```python
QUERY_DOMAIN_PROMPT = """Generate exactly {n} targeted CPG retrieval queries, one per clinical domain below.
Do NOT generate multiple queries for the same domain.

Required domains (generate one query each):
1. First-line pharmacotherapy — drug choice, dose, duration for this condition and severity
2. Drug contraindications and interactions — specific to patient's current medications: {medications}
3. Monitoring — parameters, frequency, target values for ongoing management
4. Dose adjustment — renal/hepatic impairment adjustments relevant to: {comorbidities}
5. Escalation and referral — criteria for specialist referral or treatment escalation

Patient: {chief_complaint}, {age}/{sex}, ICD: {icd_summary}
CPGs in scope: {cpg_names}

Return JSON array of {n} strings. No markdown."""
```

Increase `queries_per_code` default from `3` → `5` in `stage_4_retrieve`.

**Files to change:** `agent/clinical_stages.py` (`_generate_retrieval_queries`, `stage_4_retrieve` default param)
**Effort:** ~1 h
**Test:** Assert that generated queries contain terms from at least 3 distinct domains (monitoring, contraindication, escalation).

---

## Gap 4 — Severity and staging absent from routing and retrieval

**Safety impact: HIGH**

### What the current system does
`PatientCase` has free-text `history` and `comorbidities` fields. Severity information (e.g. NYHA Class III, CKD Stage 3b, HbA1c 9.2%) is buried in unstructured text. The ICD-11 code `BB01.1` is identical regardless of whether the patient is WHO FC I or FC IV.

### Why this matters
CPGs are almost entirely structured around severity staging. The Malaysian PAH CPG gives different first-line drug recommendations for:
- WHO FC I–II: monotherapy (PDE5i OR ERA)
- WHO FC III: combination therapy (ERA + PDE5i)
- WHO FC IV: prostacyclin analogue + combination

If the LLM does not know the patient's FC class, it cannot retrieve the correct CPG section. A query for "pulmonary hypertension treatment" retrieves the overview section, not the FC-stratified algorithm section.

The same applies to:
- CKD staging → eGFR-based drug dose adjustments
- HbA1c → intensification thresholds in DM CPG
- LVEF → HFrEF vs HFmrEF vs HFpEF drug choice

### Implementation plan

**`agent/models.py` — extend `PatientCase`:**

```python
class PatientCase(BaseModel):
    chief_complaint: str
    history: str | None = None
    age: int | None = None
    sex: Literal["M", "F", "other"] | None = None
    comorbidities: list[str] = []
    current_medications: list[str] = []
    allergies: list[str] = []
    vitals: dict[str, float] = {}
    # NEW: structured severity staging
    severity_staging: dict[str, str] = {}
    # e.g. {"NYHA": "III", "WHO_FC": "III", "CKD_stage": "3b",
    #        "HbA1c": "9.2%", "LVEF": "35%", "eGFR": "42"}
```

**`Doctor UI/src/lib/clinicalApi.js` — map staging from UI:**

Add a `SeverityStagingInput` component in `DataInputSection.jsx` — a small expandable grid of common staging fields. Pre-populate from vitals where possible (e.g. eGFR calculable from creatinine + age + sex).

**`_generate_retrieval_queries` — inject staging into domain queries:**

```python
staging_str = ", ".join(f"{k} {v}" for k, v in case.severity_staging.items()) or "not specified"
# Inject into domain query 1: "first-line pharmacotherapy ... WHO FC III ..."
```

**Files to change:** `agent/models.py`, `Doctor UI/src/components/sections/DataInputSection.jsx`, `Doctor UI/src/lib/clinicalApi.js`, `agent/clinical_stages.py`
**Effort:** ~2 h backend, ~2 h frontend
**Test:** Fixture patient with `severity_staging: {"NYHA": "III"}`; assert retrieval queries contain "III" or "class III".

---

## Gap 5 — CPG currency is not surfaced

**Safety impact: MEDIUM**

### What the current system does
CPG documents are cited by title only (e.g. `Pulmonary-Arterial-Hypertension(2011)`). The year is in the filename but not stored as structured metadata and not surfaced to the clinician in the care plan or trace.

### Why this matters
`Pulmonary-Arterial-Hypertension(2011)` is 14 years old. The 2022 ESC/ERS guidelines substantially changed PAH management:
- Upfront combination therapy is now standard for most FC II–III patients
- Selexipag added as third agent
- Risk stratification tools (REVEAL 2.0, ESC/ERS 4-strata) now recommended

A clinician seeing `CPG PAH Management §4.2` as a citation has no signal that this guidance is superseded. They may rely on it for a drug choice that the 2022 guidelines explicitly no longer recommend.

This is less likely to cause acute harm than Gaps 1–2 (the clinician should know their field), but it degrades the trustworthiness of the system and creates medicolegal exposure.

### Implementation plan

**Database — add `published_year` to `documents` table:**

```sql
ALTER TABLE documents ADD COLUMN published_year SMALLINT;
```

Backfill from filenames (regex `\((\d{4})\)` matches `CPG-Name(2011)`). Add to `ingestion/classify_cpg_scope.py` for future documents.

**`agent/clinical_stages.py` — `_format_evidence`:**

```python
def _format_evidence(chunks: list[ChunkResult]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        section = c.metadata.get("section_number", "")
        cpg = c.document_title or c.document_source
        published_year = c.metadata.get("published_year")
        age_warning = ""
        if published_year and (2026 - int(published_year)) > 5:
            age_warning = f" ⚠ Published {published_year} — verify against current guidelines"
        lines.append(f"[{i}] {cpg} §{section}{age_warning}\n{c.content[:400]}")
    return "\n\n".join(lines)
```

**Frontend — `PipelineProgress.jsx` / care plan citation display:**

Show a `⚠ 2011` amber chip next to old CPG citations in the trace and in the `cpg_source` field of each recommendation card.

**Files to change:** `sql/migrations/005_documents_published_year.sql`, `ingestion/classify_cpg_scope.py`, `agent/clinical_stages.py`, `PipelineProgress.jsx`, `CarePlanSection.jsx`
**Effort:** ~30 min SQL + ~1 h display
**Test:** Assert that evidence formatted from a document with `published_year=2011` contains the age warning string.

---

## Gap D1 — Deterministic comorbidity → ICD-11 map (DEFERRED)

**Status: 🟡 DEFERRED — superseded by Gap 4 (structured severity staging UI).**

### What was proposed

A hardcoded ~30-entry Python dict mapping common Malaysian comorbidity strings to their ICD-11 codes, used BEFORE `search_ddx` inside `route_comorbidities`:

```python
COMORBIDITY_ICD_MAP = {
    "CKD Stage 3":              "GB61.3",
    "Type 2 Diabetes Mellitus": "5A11",
    "Type 2 DM":                "5A11",
    "T2DM":                     "5A11",
    "Hypertension":             "BA00.Z",
    "Atrial Fibrillation":      "BC81.3",
    "PAH WHO FC III":           "BB01.1",
    # … ~30 most common entries
}
```

This would remove vector-quality risk for the head of the distribution — "CKD Stage 3" reliably resolves to `GB61.3` instead of relying on `search_ddx` similarity (which scored 0.26 in Test Run 3, well below the 0.55 threshold).

### Why deferred

Same retire-debt concern as Gap 2: a maintained hardcoded table is the wrong long-term shape. The right shape is **structured UI input** — when the clinician picks "CKD Stage 3" from a dropdown in the Doctor UI, the underlying value submitted to the API is already `{"GB61.3": "CKD Stage 3"}`. No vector lookup, no maintained map, no abbreviation guessing.

This is exactly what Gap 4 (severity staging in `PatientCase`) addresses for staging fields, and the same pattern can extend to comorbidities (`comorbidities: list[{icd_code, label, severity}]` instead of `list[str]`).

### Bridge already in place

`ddx/search_ddx.py` `normalize_query()` now applies a clinical abbreviation expansion table (`_CLINICAL_SYNONYMS`) before embedding — CKD → "chronic kidney disease", T2DM → "type 2 diabetes mellitus", etc. This recovers most of the precision the hardcoded map would have given, without a parallel maintained ICD-mapping. Combined with the `route_comorbidities` 0.55 similarity threshold, the system fails cleanly (skips + logs) rather than silently mis-routing.

### When to revisit

When Gap 4 is implemented and the Doctor UI starts sending structured comorbidity payloads, delete the comorbidity DDx-lookup path from `route_comorbidities` entirely — replace with a direct `route_icd_to_cpgs(icd_code)` call per submitted code. At that point, this Gap D1 entry can be deleted.

---

## Implementation roadmap

| Priority | Gap | Files affected | Effort | Safety rating | Status |
|---|---|---|---|---|---|
| 1 | Comorbidity routing | `clinical_workflow.py`, `ddx/search_ddx.py` | ~3 h | 🔴 Critical | ✅ Code complete (see Gap_1_CPG_Ingestion.md for data follow-up) |
| 2 | Drug interaction lookup | — | — | 🔴 Critical | 🟡 Deferred → folded into Gap R6 (KG wiring) in `RAG_Pipeline_and_Prompt_Gaps.md` |
| 3 | Domain-templated queries (expanded to 7 domains: + Lifestyle & Counselling, Follow-up & Review) | `clinical_stages.py`, `stage4_query_generation.txt` | ~1 h | 🟠 High | ✅ Done (R4 in RAG gaps) |
| 4 | Severity staging in PatientCase + queries | `models.py`, `DataInputSection.jsx`, `clinical_stages.py`, `clinicalApi.js`, `stage4_query_generation.txt` | ~4 h | 🟠 High | ✅ Done — `severity_staging` field wired end-to-end; embedded in Domains 1/4/5/7; covered by `tests/test_severity_staging.py` |
| 5 | CPG currency warning | SQL migration 005, `clinical_stages.py`, `stage5_synthesis.txt`, `db_utils.py` | ~1.5 h | 🟡 Medium | ✅ Done (age-based warning at `clinical_stages.py:1472-1479`, richer than spec) |
| D1 | Deterministic comorbidity → ICD map | — | — | 🟡 Medium | 🟡 Deferred (superseded by Gap 4 + synonym expansion bridge). Revisit trigger met — Gap 4 landed structured input; the `route_comorbidities` DDx-lookup path can now be replaced with direct `route_icd_to_cpgs(icd_code)` per submitted code, or left as free-text fallback. |

**File closed.** Gap 1 code is complete; data-side tracked in `Gap_1_CPG_Ingestion.md` (DM and CKD CPG ingestion). Gap 2 tracked in `RAG_Pipeline_and_Prompt_Gaps.md` (Gap R6 — KG wiring). All other gaps resolved.

---

## What these gaps close — clinical summary

| Scenario | Before gaps closed | After gaps closed |
|---|---|---|
| T2DM patient with CKD on metformin prescribed contrast | Metformin not flagged, contrast risk missed | Drug interaction flag injected into synthesis; `contraindications_checked` must address it |
| NYHA FC III heart failure — wrong drug class recommended | Generic FC-agnostic chunk retrieved | FC III-specific query retrieves combination therapy section |
| PAH patient with sulfa allergy prescribed furosemide | Allergy cross-reactivity not checked structurally | Allergy cross-reactivity flag injected; LLM must address or alternative suggested |
| Clinician cites 2011 PAH CPG as current evidence | No age warning; guidance presented as current | `⚠ Published 2011` chip on citation; clinician prompted to verify |
| DM comorbidity: SGLT2i cardioprotection not suggested | T2DM CPG never retrieved | Comorbidity routing adds T2DM CPG to evidence pool; SGLT2i cardioprotection chunk retrieved |
