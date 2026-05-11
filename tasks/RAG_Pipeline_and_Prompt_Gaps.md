# RAG Pipeline & System Prompt — Gap Analysis

> Root causes of incomplete care plan output (empty Monitoring & Testing, missing Summary,
> sparse recommendations, null evidence_grade) observed in the UI and CLI testing.
>
> **Two pipelines, one output format:**
> - `cli.py` → `/chat/stream` → `prompts.py` system prompt → free-text markdown (6 sections)
> - Doctor UI → Stage 2–5 pipeline → `TreatmentPlan` JSON → `clinicalMappers.js` → same 6 sections
>
> Both must produce the same 6 sections:
> 1) Summary  2) Medication Changes  3) Patient Education & Counselling
> 4) Monitoring & Next Steps  5) Referrals  6) Follow-up  + Sources

---

## Output section → TreatmentPlan field mapping

| Care plan section | TreatmentPlan field | Status |
|---|---|---|
| 1) Summary | `summary: str` | ❌ field missing from model |
| 2) Medication Changes | `recommendations` where `type="pharmacological"` | ✅ field exists |
| 3) Patient Education & Counselling | `recommendations` where `type="lifestyle"` | ✅ field exists |
| 4) Monitoring & Next Steps | `monitoring: list[str]` + `red_flags: list[str]` | ✅ fields exist — but LLM was leaving them empty |
| 5) Referrals | `recommendations` where `type="referral"` | ✅ field exists |
| 6) Follow-up | `follow_up: list[str]` | ❌ field missing from model |
| Sources | `recommendations[*].cpg_source` | ✅ field exists per recommendation |

---

## Implementation sequence

```
Phase 0 — Model alignment (MUST do first, everything else depends on it)
  └── Gap M1: Add summary + follow_up fields to TreatmentPlan

Phase 1 — Code only, no re-ingestion (all data already in DB)
  ├── Gap R1: Chunk truncation 400 → 800 chars               ✅ DONE
  ├── Gap R2: Evidence grade assignment (inline tag reading)  ✅ DONE (prompt)
  ├── Gap R3: Category score boosting post-retrieval         ✅ DONE
  ├── Gap R4: Retrieval query shape (5 domains)              ✅ DONE (prompt)
  └── Gap R5: Mandatory 6-section synthesis rules            🔜 BLOCKED by M1

Phase 2 — Category-aware retrieval at DB level (minor SQL change, no re-ingestion)
  ├── Add category_filter to VectorSearchInput
  ├── Add SQL ?| JSONB filter in db_utils.py
  └── Pass category_filter from Stage 4

Phase 3 — Knowledge graph enrichment (one-time batch, after Phase 2)
  ├── Add icd11_code to Condition nodes (Cypher batch)
  ├── Re-run graph_builder.py scoped to Treatment/Assessment chunks
  └── Wire graph_search into Stage 4 contraindication query path

Parallel (independent of all above)
  └── Gap C1: Comorbidity routing (route_comorbidities second pass)
```

---

## Gap M1 — TreatmentPlan model missing summary and follow_up fields ⚡ DO FIRST

**Impact: CRITICAL — sections 1 and 6 of the care plan cannot be populated without these fields**

### What is missing

```python
# models.py — TreatmentPlan is currently missing:
summary: str                    # Section 1 — clinical assessment paragraph
follow_up: list[str]            # Section 6 — timeline, reassessment criteria, outcome-based actions
```

### Fix

**`agent/models.py`** — add two fields to `TreatmentPlan`:
```python
class TreatmentPlan(BaseModel):
    icd_primary: str
    icd_alternates: list[str] = []
    summary: str = Field(..., description="Clinical assessment: diagnosis type, key risk factors, classification")
    recommendations: list[Recommendation]
    monitoring: list[str] = []
    red_flags: list[str] = []
    follow_up: list[str] = []          # timeline + reassessment + outcome-based actions
    confidence: float
    unresolved_questions: list[str] = []
```

**`Doctor UI/src/lib/clinicalMappers.js`** — add rendering for summary and follow_up:
```javascript
summary: plan.summary ?? "",
followUp: plan.follow_up ?? [],
```

**`agent/prompts/stage5_synthesis.txt`** — add instructions for both fields (see Gap R5 below).

**Effort:** 30 min | **Status:** ✅ DONE

---

## Gap R1 — Chunk content was truncated at 400 characters

**Impact: HIGH — dosing instructions and monitoring parameters cut off mid-sentence**

### What was wrong
`_format_evidence` truncated every chunk to 400 chars. CPG recommendations typically span
200–400 chars for the core statement alone; the dose, grade tag, and monitoring note that
follow were all invisible to Stage 5.

### Fix applied
```python
# clinical_stages.py — _format_evidence
lines.append(f"[{i}] {cpg} §{section}\n{c.content[:800]}")
```

**Effort:** 30 min | **Status:** ✅ DONE

---

## Gap R2 — Evidence grades not linked to specific recommendations

**Impact: HIGH — evidence_grade null on all recommendations**

### Why grades cannot be stored as metadata

`evidence_grades` / `evidence_levels` are **not stored in NeonDB chunk metadata**.
Chunker.py extracts them into flat deduplicated arrays during ingestion, but this loses
the link between a grade and the specific recommendation it belongs to:

```
Chunk content: "Bosentan for WHO FC II–III [Grade I, Level A]. Prostacyclin for
               refractory WHO FC IV [Grade IIb, Level C]."
Flat array:    evidence_grades: ["I", "IIb"]  — which grade belongs to which drug?
```

Storing flat arrays would cause the synthesis LLM to assign grades arbitrarily.
**Design decision: grade assignment is a synthesis-time task, not ingestion-time.**

### Fix applied

`stage5_synthesis.txt` now instructs the LLM to:
1. Find the specific sentence supporting this recommendation
2. Read the `[Grade X, Level Y]` tag immediately adjacent to that sentence
3. Copy it verbatim into `evidence_grade`
4. Never assign a grade from a different recommendation in the same chunk

`_format_evidence` passes full 800-char content so inline grade tags remain readable.
No metadata lookup. No ingestion re-run required.

**Effort:** 1 h | **Status:** ✅ DONE (prompt only)

---

## Gap R3 — Background chunks competing with treatment chunks in retrieval

**Impact: HIGH — Introduction/Pathophysiology chunks score comparably to Treatment chunks**

### What was wrong

Vector similarity does not distinguish CPG purpose. An epidemiology section mentioning
"pulmonary hypertension" scores similarly to a treatment algorithm section. Stage 5 then
receives background text and either hallucinates treatment details or produces generic output.

### Category metadata already in DB

Every chunk has `metadata["category"]` populated from Layer 1 `<!-- METADATA -->` blocks
(values: Treatment, Assessment, Diagnosis, Supportive Treatment, Special Populations,
Reference, Introduction, Pathophysiology, Epidemiology, Methodology).

**No re-ingestion needed** — data already present.

### Fix applied (Phase 1 — score boosting post-retrieval)

```python
# clinical_stages.py — stage_4_retrieve, before final sort
_CATEGORY_BOOST = {
    "Treatment": 1.4, "Supportive Treatment": 1.3, "Assessment": 1.2,
    "Diagnosis": 1.2, "Prevention": 1.2, "Special Populations": 1.1,
    "Reference": 1.0, "Introduction": 0.5, "Pathophysiology": 0.4,
    "Epidemiology": 0.4, "Methodology": 0.3,
}
def _boosted_score(chunk): ...
all_chunks.sort(key=_boosted_score, reverse=True)
```

### Phase 2 fix (stronger — SQL pre-filter, excludes background entirely)

```python
# VectorSearchInput — add category_filter
# db_utils.py vector_search — add: AND metadata->'category' ?| $4::text[]
```

**Effort:** Phase 1 done (1 h). Phase 2: 1 h additional | **Status:** ✅ Phase 1 DONE / 🔜 Phase 2 pending

---

## Gap R4 — Retrieval queries were generic and domain-unbalanced

**Impact: HIGH — all 3 queries clustering around "treatment overview"; monitoring and dose-adjustment sections never retrieved**

### What was wrong

`_generate_retrieval_queries` produced 3 free-form queries. LLM defaulted to:
1. "pulmonary hypertension treatment"
2. "PAH management guidelines"
3. "ERA therapy recommendations"

All three retrieved the same overview sections. No query targeted monitoring protocol,
dose adjustment for comorbidities, or escalation criteria.

### Fix applied

`stage4_query_generation.txt` now enforces 5 domains:
1. PHARMACOTHERAPY — drug + dose at specific severity
2. CONTRAINDICATIONS & DRUG INTERACTIONS — patient's current medications named explicitly
3. MONITORING PROTOCOL — parameters, targets, frequency
4. DOSE ADJUSTMENT — comorbidity-specific (CKD, hepatic, elderly)
5. ESCALATION & REFERRAL — criteria for specialist referral or hospitalisation

`queries_per_code` default changed 3 → 5.

**Effort:** 1 h | **Status:** ✅ DONE

---

## Gap R5 — Synthesis prompt has no rules for mandatory 6-section output

**Impact: HIGH — LLM produces only pharmacological recommendations; monitoring, lifestyle, referral, follow-up all empty**

### What was wrong

Old `SYNTHESIS_SYSTEM` had no instruction that:
- `monitoring` list must be populated from evidence (was always `[]`)
- `red_flags` list must be populated from evidence (was always `[]`)
- `lifestyle`, `referral`, `investigation` recommendation types must be attempted
- `summary` and `follow_up` fields must be populated (fields didn't exist yet)

### Fix applied so far

`stage5_synthesis.txt` now has:
- MANDATORY OUTPUT SECTIONS block listing all types
- `monitoring` and `red_flags` rules with format examples
- START/STOP/CHANGE/CONTRAINDICATED format for pharmacological matching `prompts.py` Scenario B
- Grade assignment rules (inline tag reading, not metadata)

### Remaining — BLOCKED on Gap M1

`stage5_synthesis.txt` still needs rules for `summary` and `follow_up` fields.
Cannot be added until `TreatmentPlan` model has those fields (Gap M1).

**Effort:** 1 h | **Status:** ✅ DONE

---

## Gap R6 — Knowledge graph not wired into clinical pipeline

**Impact: HIGH (future) — no graph-based contraindication or pathway retrieval**

### Current state

- `graph_search_tool` exists in `agent/tools.py` but Stage 4 never calls it
- Entity extraction ran with `extraction_method: "skipped"` on many chunks (graph_builder not run on all CPGs)
- No `icd11_code` property on `(:Condition)` nodes — cannot traverse from DDx code to first-line drugs
- `graph_search` does not support `document_id_filter` — returns unscoped results

### Fix plan (Phase 3 — after Phase 2 category filter)

1. Add `icd11_code` to Condition nodes (Cypher batch, 2 h)
2. Re-run `graph_builder.py` scoped to Treatment/Assessment chunks using category filter (1 day)
3. Wire `graph_search` into Stage 4 contraindication query path (0.5 day)
4. Validate: patient on warfarin → graph returns CONTRAINDICATED_WITH nitrates (1 h)

**Effort:** ~2 days | **Status:** 🔜 Phase 3 (after Phase 2)

---

## Gap C1 — Comorbidity CPGs never retrieved

**Impact: CRITICAL — patient with T2DM + hypertension only gets PAH CPG; DM and HTN guidelines never consulted**

### What is wrong

`stage_3_route` routes only the top-2 DDx ICD codes to CPG documents.
`case.comorbidities` (a `list[str]` on `PatientCase`) is never used to retrieve additional CPGs.

A patient presenting with chest pain whose comorbidities include "Type 2 Diabetes Mellitus"
and "Hypertension" will never receive medication adjustment recommendations from the DM or
HTN CPGs — even though those CPGs are ingested and available.

### Fix (independent of all retrieval gaps — can be built in parallel)

```python
# clinical_workflow.py — after stage_3_route
async def route_comorbidities(
    comorbidities: list[str],
    existing_cpgs: list[CPGDocRef],
    top_k: int = 2,
) -> list[CPGDocRef]:
    additional = []
    for condition in comorbidities:
        ddx = await search_ddx(condition, top_k=1)
        if ddx:
            refs = await route_icd_to_cpgs(ddx[0]["code"], top_k=top_k)
            for ref in refs:
                if ref.cpg_name not in {c.cpg_name for c in existing_cpgs}:
                    additional.append(ref)
    return additional
```

**Effort:** ~3 h | **Status:** 🔜 Can start any time (independent)

---

## Summary — what to do next

| Priority | Gap | What | Effort | Status |
|---|---|---|---|---|
| ~~1~~ | ~~M1~~ | ~~Add `summary` + `follow_up` + `action` to model + mapper + prompt~~ | ~~30 min~~ | ✅ DONE |
| ~~2~~ | ~~R5~~ | ~~Complete stage5_synthesis.txt with all 6-section rules~~ | ~~30 min~~ | ✅ DONE |
| 3 | C1 | Comorbidity routing second pass | 3 h | 🔜 parallel |
| 4 | R3 Phase 2 | SQL category pre-filter in db_utils.py | 1 h | 🔜 |
| 5 | R6 | Knowledge graph wiring | 2 days | 🔜 Phase 3 |
| — | ~~R1~~ | ~~Chunk truncation fix~~ | — | ✅ DONE |
| — | ~~R2~~ | ~~Grade assignment (prompt)~~ | — | ✅ DONE |
| — | ~~R3 Phase 1~~ | ~~Category score boosting~~ | — | ✅ DONE |
| — | ~~R4~~ | ~~5-domain query generation~~ | — | ✅ DONE |
