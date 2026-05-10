# Clinical Pipeline — Gap Closing Plan

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

**Safety impact: CRITICAL**

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

**Safety impact: CRITICAL**

### What the current system does
`case.current_medications` and `case.allergies` are injected as plain text into the Stage 5 synthesis prompt with the instruction: *"contraindications_checked: list of contraindications considered"*. The LLM performs this check from training memory.

### Why this is dangerous
Drug-drug interactions and allergy cross-reactivities are the leading cause of preventable adverse drug events. Two concrete failure scenarios:

1. **Patient on warfarin** → CPG recommends rivaroxaban for AF → LLM may or may not flag double anticoagulation. If it misses it, the `contraindications_checked` field appears populated with other items, giving false assurance.

2. **Patient with sulfa allergy** → CPG recommends furosemide (sulfonamide structure, ~1% cross-reactivity risk) → LLM training data is inconsistent on this interaction; it may recommend furosemide without flagging sulfa cross-reactivity.

3. **Patient on ACE inhibitor** → CPG recommends spironolactone (potassium-sparing) → hyperkalemia risk is well-known but the LLM may omit it if the relevant CPG chunk was not retrieved.

These are the errors that cause ICU admissions. A supervised clinical decision support tool that misses them and presents a clean `contraindications_checked` list is more dangerous than one that says nothing.

### Implementation plan

**New file — `agent/drug_interactions.py`**

A structured lookup table for high-risk pairs, covering the most common interactions in primary care:

```python
from __future__ import annotations

# (drug_a_keyword, drug_b_keyword): (severity, description)
HIGH_RISK_PAIRS: list[tuple[str, str, str, str]] = [
    ("warfarin",       "aspirin",           "MAJOR",    "Combined antiplatelet + anticoagulant: major bleeding risk"),
    ("warfarin",       "nsaid",             "MAJOR",    "NSAIDs potentiate warfarin: major GI and intracranial bleed risk"),
    ("warfarin",       "rivaroxaban",       "MAJOR",    "Dual anticoagulation: major bleeding risk"),
    ("warfarin",       "apixaban",          "MAJOR",    "Dual anticoagulation: major bleeding risk"),
    ("ace inhibitor",  "spironolactone",    "MODERATE", "Hyperkalemia risk — monitor K+ within 1 week of initiation"),
    ("ace inhibitor",  "potassium",         "MODERATE", "Hyperkalemia risk — avoid routine K+ supplementation"),
    ("metformin",      "contrast",          "MODERATE", "Hold metformin 48h before/after iodinated contrast (AKI risk)"),
    ("ssri",           "tramadol",          "MAJOR",    "Serotonin syndrome risk"),
    ("statin",         "amiodarone",        "MODERATE", "Myopathy risk — cap simvastatin at 20mg"),
    ("digoxin",        "amiodarone",        "MAJOR",    "Digoxin toxicity — reduce digoxin dose by 50%"),
]

# (allergy_keyword, drug_keyword): description
HIGH_RISK_ALLERGY_CROSS: list[tuple[str, str, str]] = [
    ("penicillin",  "amoxicillin",   "Direct allergy — contraindicated"),
    ("penicillin",  "ampicillin",    "Direct allergy — contraindicated"),
    ("penicillin",  "cephalosporin", "Cross-reactivity ~1-2% — use with caution, have resuscitation available"),
    ("sulfa",       "furosemide",    "Sulfonamide cross-reactivity risk — consider alternative loop diuretic"),
    ("sulfa",       "thiazide",      "Sulfonamide cross-reactivity risk — consider alternative"),
    ("sulfa",       "celecoxib",     "Sulfonamide cross-reactivity risk"),
    ("aspirin",     "nsaid",         "NSAID cross-reactivity in aspirin-sensitive patients — contraindicated"),
    ("contrast",    "metformin",     "Hold metformin — AKI risk with contrast nephropathy"),
]


def check_interactions(
    medications: list[str],
    allergies: list[str],
    proposed_drugs_context: str,
) -> list[dict]:
    """
    Screen current medications and allergies against a proposed drug context string.
    Returns a list of flagged interactions with severity and description.
    """
    flags = []
    meds_lower = " ".join(medications).lower()
    allergies_lower = " ".join(allergies).lower()
    context_lower = proposed_drugs_context.lower()

    for drug_a, drug_b, severity, description in HIGH_RISK_PAIRS:
        a_in_meds = drug_a in meds_lower
        b_in_meds = drug_b in meds_lower
        a_in_context = drug_a in context_lower
        b_in_context = drug_b in context_lower

        if (a_in_meds and b_in_context) or (b_in_meds and a_in_context):
            flags.append({
                "type": "drug_drug",
                "severity": severity,
                "detail": description,
                "pair": f"{drug_a} + {drug_b}",
            })

    for allergy, drug, description in HIGH_RISK_ALLERGY_CROSS:
        if allergy in allergies_lower and drug in context_lower:
            flags.append({
                "type": "allergy_cross",
                "severity": "MAJOR",
                "detail": description,
                "pair": f"{allergy} allergy + {drug}",
            })

    return flags
```

**In `stage_5_synthesize` — inject flags into evidence prompt:**

```python
from .drug_interactions import check_interactions

# Before synthesis call:
interaction_flags = check_interactions(
    case.current_medications,
    case.allergies,
    evidence_text,          # screen against retrieved CPG evidence
)

if interaction_flags:
    flag_text = "\n".join(
        f"  ⚠ [{f['severity']}] {f['detail']} ({f['pair']})"
        for f in interaction_flags
    )
    evidence_text = f"INTERACTION FLAGS — address each in contraindications_checked:\n{flag_text}\n\n{evidence_text}"
```

This forces the synthesis LLM to see the flags as part of the evidence block, making it structurally impossible to omit them from the response.

**Files to change:** New `agent/drug_interactions.py`, `agent/clinical_stages.py` (`stage_5_synthesize`)
**Effort:** ~2 h
**Test:** Fixture patient on warfarin; evidence text mentions rivaroxaban; assert `contraindications_checked` contains the warfarin interaction.

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

## Implementation roadmap

| Priority | Gap | Files affected | Effort | Safety rating |
|---|---|---|---|---|
| 1 | Comorbidity routing | `clinical_workflow.py` | ~3 h | 🔴 Critical |
| 2 | Drug interaction lookup | New `drug_interactions.py`, `clinical_stages.py` | ~2 h | 🔴 Critical |
| 3 | 5 domain-templated queries | `clinical_stages.py` | ~1 h | 🟠 High |
| 4 | Severity staging in PatientCase + queries | `models.py`, `DataInputSection.jsx`, `clinical_stages.py` | ~4 h | 🟠 High |
| 5 | CPG currency warning | SQL migration, `clinical_stages.py`, UI | ~1.5 h | 🟡 Medium |

**Total effort: ~11.5 h across 2–3 sessions**

Gaps 1 and 2 should be implemented before any clinical pilot. Gaps 3 and 4 should follow immediately after. Gap 5 can ship alongside the next CPG ingestion run.

---

## What these gaps close — clinical summary

| Scenario | Before gaps closed | After gaps closed |
|---|---|---|
| T2DM patient with CKD on metformin prescribed contrast | Metformin not flagged, contrast risk missed | Drug interaction flag injected into synthesis; `contraindications_checked` must address it |
| NYHA FC III heart failure — wrong drug class recommended | Generic FC-agnostic chunk retrieved | FC III-specific query retrieves combination therapy section |
| PAH patient with sulfa allergy prescribed furosemide | Allergy cross-reactivity not checked structurally | Allergy cross-reactivity flag injected; LLM must address or alternative suggested |
| Clinician cites 2011 PAH CPG as current evidence | No age warning; guidance presented as current | `⚠ Published 2011` chip on citation; clinician prompted to verify |
| DM comorbidity: SGLT2i cardioprotection not suggested | T2DM CPG never retrieved | Comorbidity routing adds T2DM CPG to evidence pool; SGLT2i cardioprotection chunk retrieved |
