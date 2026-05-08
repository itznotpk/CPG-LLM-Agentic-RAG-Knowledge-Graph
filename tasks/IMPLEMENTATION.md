# CPG LLM — End-to-End Clinical Workflow Implementation Plan

> **Goal:** Build a deterministic, auditable pipeline that takes patient data → predicts ICD-11 code(s) → routes to the right CPG(s) → retrieves grounded evidence → produces a structured treatment plan.
>
> **Guiding principle:** No manual ICD-to-CPG mapping. Routing is driven by document-level metadata that is generated once at CPG ingestion time.

---

## 1. Current state

| Layer | Status | Location |
|---|---|---|
| CPG markdown corpus (~25 docs, mostly Malaysian CPGs) | ✅ Present | [markdown/](markdown/) |
| CPG chunking + embedding ingestion | ✅ Working | [ingestion/](ingestion/) |
| Vector / hybrid / graph retrieval tools | ✅ Working | [agent/tools.py](agent/tools.py) |
| Pydantic AI agent (5 tools registered) | ✅ Working | [agent/agent.py](agent/agent.py) |
| ICD-11 vector search (Chapter 17 only, 47 codes) | 🟡 Partial | [ddx/](ddx/) |
| ICD-11 → CPG routing | ❌ Missing | — |
| Structured patient input contract | ❌ Missing | — |
| Structured treatment plan output | ❌ Missing | — |
| Multi-stage clinical orchestrator | ❌ Missing | — |

The two missing bridges are **ICD → CPG routing** and **patient input → treatment plan output schema**. Everything else either exists or is an extension of existing code.

---

## 2. Target workflow

```
[Stage 1]  Patient input          (PatientCase Pydantic schema)
              │
              ▼
[Stage 2]  Symptom → ICD-11        (ddx vector + Morbidity Tabulation, expanded chapters)
              │  top-K candidates with confidence
              ▼
[Stage 3]  ICD → CPG routing       (filter documents by icd11_scope; semantic fallback)
              │  shortlist of document_id's
              ▼
[Stage 4]  CPG section retrieval   (existing tools, scoped via document_id_filter)
              │  evidence chunks tagged with [Grade X, Level Y]
              ▼
[Stage 5]  Treatment plan synthesis (TreatmentPlan structured output)
              │
              ▼
       Doctor UI (answer + evidence chain)
```

Each stage produces a typed artifact. Each stage is independently testable. The orchestrator is a thin sequential controller — no graph framework needed for v1.

---

## 3. Components — what's new vs reused

| # | Component | Status | Path |
|---|---|---|---|
| 3.1 | `PatientCase` / `Recommendation` / `TreatmentPlan` schemas | ✅ DONE (Step 01) | [agent/models.py](../agent/models.py) |
| 3.2 | Extend `documents` table with scope columns + GIN index | NEW | [sql/schema.sql](../sql/schema.sql) |
| 3.3 | CPG scope classifier (one-shot) | NEW | `ingestion/classify_cpg_scope.py` |
| 3.4 | Human review + verification flip | NEW | `ingestion/verify_cpg_scope.py` |
| 3.5 | ICD-11 ingestion expanded to relevant chapters | EXTEND | [ddx/ingest_icd11.py](../ddx/ingest_icd11.py) |
| 3.6 | DDx vector + tabulation search | REUSE | [ddx/search_ddx.py](../ddx/search_ddx.py) |
| 3.7 | `route_icd_to_cpgs()` | NEW | `agent/routing.py` |
| 3.8 | Add `document_id_filter` to retrieval tools | EXTEND | [agent/tools.py](../agent/tools.py) |
| 3.9 | Targeted query generator | NEW | inside Stage 4 prompt |
| 3.10 | Clinical orchestrator | NEW | `agent/clinical_workflow.py` |
| 3.11 | API endpoint for clinical flow | EXTEND | [agent/api.py](../agent/api.py) |

> **Architectural simplification (post-IMPLEMENTATION-v1):** Originally proposed a separate `cpg_documents` table with a new `cpg_id` foreign key on `chunks`. After inspecting [sql/schema.sql](../sql/schema.sql), every document in this system *is* a CPG, and `chunks.document_id` already references `documents.id`. So scope metadata is added as columns on `documents` directly — no new table, no chunks backfill, no FK churn. Routing filters `documents` by `icd11_scope` and joins chunks via the existing `document_id`.

---

## 4. Build order

Each step is independently shippable and testable. Do not start step N+1 until step N has a passing test.

### Step A — Schema foundations (~1 h) ✅ DONE
- Added `PatientCase`, `Recommendation`, `TreatmentPlan` to [agent/models.py](../agent/models.py).
- Tests in [tests/test_clinical_schemas.py](../tests/test_clinical_schemas.py) — 32 passing.
- Brief: [STEP_01_schemas.md](STEP_01_schemas.md).

### Step B — Extend `documents` with scope columns (~30 min)
- `ALTER TABLE documents` adding `icd11_scope TEXT[]`, `procedure_scope TEXT[]`, `scope_rationale TEXT`, `scope_verified BOOLEAN`, `classified_at`, `verified_at`, `verified_by`.
- New GIN index on `documents(icd11_scope)`.
- Update destructive `DROP/CREATE` block in [sql/schema.sql](../sql/schema.sql) so a fresh schema apply produces the new columns.
- Test: a fixture document with `icd11_scope = ARRAY['BC81']` is retrievable via the GIN index.
- No changes to `chunks` (already references `documents.id`).
- Brief: [STEP_02_extend_documents.md](STEP_02_extend_documents.md).

### Step C — CPG scope classifier (~1.5 h)
- Script `ingestion/classify_cpg_scope.py`.
- Reads each `markdown/*.md`, sends `(title + first ~200 lines)` to LLM, parses JSON, upserts the matching row in `documents` with the proposed scope and `scope_verified = FALSE`.
- Generates `ingestion/cpg_scope_review.md` for clinician review.
- Test: dry-run on 3 known CPGs (AF, Hypertension, Stroke), assert expected ICD blocks present.

### Step D — Human verification (~30 min clinician + 20 min eng)
- Clinician reviews `cpg_scope_review.md`, edits where needed.
- Script `ingestion/verify_cpg_scope.py` parses the reviewed file and flips `scope_verified = TRUE`, writes `verified_at` / `verified_by`.
- Outcome: all 25 CPG rows in `documents` have `scope_verified = TRUE`.

### Step E — Expand ICD-11 ingestion (~2 h)
- Extend [ddx/ingest_icd11.py](../ddx/ingest_icd11.py) to pull additional chapters from WHO ICD-11 API or MMS linearization download. Target chapters: 02 (neoplasms), 08 (nervous system), BA–BE (circulatory), keep 17 (sexual health). Skip chapters with no covering CPG.
- Test: random spot-checks that `BC81.3`, `8B20`, `2C61` are retrievable by description text.

### Step F — `route_icd_to_cpgs()` (~1 h)
- New module `agent/routing.py`.
- Function signature:
  ```python
  async def route_icd_to_cpgs(
      icd_code: str,
      top_k: int = 3,
  ) -> list[CPGDocRef]
  ```
- Logic:
  1. Structural match: any `documents` row where `scope_verified = TRUE` and whose `icd11_scope` contains `icd_code` or its 3-char parent block (or covers a stored range like `BC60-BC9Z`).
  2. If no structural match → semantic fallback: embed ICD code title+description, cosine match against pre-computed CPG title/scope embeddings.
  3. Return list of `(document_id, title, match_type, score)`.
- Helper SQL function `icd11_in_scope(code TEXT, scope TEXT[]) RETURNS BOOLEAN` to keep the hierarchy/range logic in one place.
- Tests: `BC81.3 → CPG AF`, `8B20 → CPG Stroke`, `2C61 → CPG Breast Cancer`, `XX99 (unknown) → semantic fallback returns top-K`.

### Step G — Scope retrieval tools (~30 min)
- Add optional `document_id_filter: list[UUID] | None` parameter to `vector_search_tool`, `hybrid_search_tool`, `graph_search_tool` in [agent/tools.py](../agent/tools.py).
- When provided, retrieval is restricted to chunks whose parent `document_id` is in the filter.
- When `None`, behavior is unchanged (backward compatible).

### Step H — Targeted query generator (~1 h)
- Inside the Stage 4 step of the orchestrator: prompt the LLM with `(PatientCase, predicted ICD, CPG titles)` and ask it to produce 3–5 *targeted retrieval queries*. Do not pass raw user chat text into vector search.
- Each generated query is run through the scoped tools.
- Results are deduplicated and ranked by embedding score.

### Step I — Treatment plan synthesizer (~1.5 h)
- Final LLM call. Inputs: `PatientCase`, predicted ICD(s), retrieved evidence chunks.
- Output: validated `TreatmentPlan` (use Pydantic AI's structured output / `result_type=TreatmentPlan`).
- Prompt enforces: every `Recommendation.cpg_source` must reference a chunk that was actually retrieved; if no evidence found for a needed decision, populate `unresolved_questions` instead of inventing.

### Step J — Clinical orchestrator (~1.5 h)
- New file `agent/clinical_workflow.py`.
- Single async function `run_clinical_workflow(case: PatientCase) -> TreatmentPlan` that calls Stages 2 → 5 sequentially.
- Each stage's output is held in a local dict; all stages have explicit error handling.

### Step K — API integration (~30 min)
- Add `POST /clinical/plan` endpoint to [agent/api.py](../agent/api.py) accepting `PatientCase`, returning `TreatmentPlan`.
- Keep the existing `/chat` endpoint untouched for general Q&A.

### Step L — End-to-end smoke tests (~1 h)
- Three fixture cases:
  1. AF symptoms → `BC81.x` → CPG AF → rate/rhythm/anticoagulation recommendations.
  2. ED symptoms → `HA01.1` → CPG Erectile Dysfunction → PDE5 inhibitor recommendation.
  3. Out-of-scope query (e.g. dermatology) → low-confidence ICD → semantic CPG fallback or graceful "unresolved".

---

## 5. Data contracts

### 5.1 `PatientCase` (Stage 1 input)
```python
class PatientCase(BaseModel):
    chief_complaint: str
    history: str | None = None
    age: int | None = None
    sex: Literal["M", "F", "other"] | None = None
    comorbidities: list[str] = []
    current_medications: list[str] = []
    allergies: list[str] = []
    vitals: dict[str, float] = {}        # e.g. {"sbp": 165, "dbp": 95, "hr": 110}
```

### 5.2 `documents` scope columns (Stage 3 routing index)
Scope metadata is added directly to the existing `documents` table (see §3 simplification note). No new table; no foreign-key churn on `chunks`.

```sql
ALTER TABLE documents
  ADD COLUMN icd11_scope      TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN procedure_scope  TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN scope_rationale  TEXT,
  ADD COLUMN scope_verified   BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN classified_at    TIMESTAMPTZ,
  ADD COLUMN verified_at      TIMESTAMPTZ,
  ADD COLUMN verified_by      TEXT;

CREATE INDEX idx_documents_icd_scope ON documents USING GIN (icd11_scope);
```

The destructive `CREATE TABLE documents (...)` block in [sql/schema.sql](../sql/schema.sql) is updated in parallel so a fresh schema apply produces the new columns inline (avoid drift between fresh-install and migrated DBs).

### 5.3 `TreatmentPlan` (Stage 5 output)
```python
class Recommendation(BaseModel):
    intervention: str
    type: Literal["pharmacological", "procedure", "lifestyle", "referral", "investigation"]
    evidence_grade: str | None
    cpg_source: str                       # "CPG AF Management §4.2"
    rationale: str
    contraindications_checked: list[str] = []

class TreatmentPlan(BaseModel):
    icd_primary: str
    icd_alternates: list[str] = []
    recommendations: list[Recommendation]
    monitoring: list[str] = []
    red_flags: list[str] = []
    confidence: float                     # 0.0 – 1.0
    unresolved_questions: list[str] = []
```

---

## 6. CPG scope classifier — operational detail

### 6.1 Inputs per CPG
- `documents.source` (the filename / source key — already populated by ingestion)
- `documents.title` (already populated)
- First ~200 lines of the markdown file (typically TOC + scope statement)

### 6.2 LLM prompt (sketch)
> *You are an ICD-11 coding expert. Given a CPG title and table of contents, identify the ICD-11 block codes (3-character) or ranges this CPG provides treatment guidance for. Be conservative — only include codes for which the CPG offers actionable guidance. If the CPG is procedure-oriented (e.g. anaesthesia), return empty `icd11_scope` and populate `procedure_scope` with short tags like `pre_op_assessment`, `intraop_monitoring`. Return JSON: `{icd11_scope: [...], procedure_scope: [...], rationale: "..."}`.*

### 6.3 Validation
- `icd11_scope` entries must match `^[0-9A-Z]{2,4}(\.[0-9A-Z]{1,2})?$` or a range `XX00-XX9Z`.
- Reject empty `icd11_scope` AND empty `procedure_scope` — every CPG must be classifiable.

### 6.4 Review artifact (`ingestion/cpg_scope_review.md`)
Generated entry per CPG:
```markdown
## CPG Management of Atrial Fibrillation
- Filename: CPG Management of Atrial Fibrillation.md
- LLM proposed scope: BC81, BC9Z
- Rationale: "AF and related arrhythmias..."
- [ ] Approve  [ ] Edit  [ ] Reject
```
Clinician edits in place. `verify_cpg_scope.py` then parses the file and updates `documents` (`scope_verified = TRUE`, `verified_at`, `verified_by`).

### 6.5 Granularity decision
**Document-level only for v1.** Section-level tagging is rejected because (a) embeddings already do section-level discrimination, (b) review burden balloons from 25 → 1,000+ items, (c) intra-CPG sections share the same ICD anyway. If specific cross-disease sections misroute in production, add a small `document_section_overrides` table later — only for the misrouting cases. Don't pre-build it.

---

## 7. Routing logic — `route_icd_to_cpgs`

### 7.1 Structural match SQL
```sql
SELECT id AS document_id, title, icd11_scope
FROM documents
WHERE scope_verified = TRUE
  AND icd11_in_scope($1, icd11_scope);
```
The `icd11_in_scope(code, scope)` function:
1. Exact match: `code = ANY(scope)`.
2. Parent block match: `LEFT(code, 3) = ANY(scope)` (e.g. `BC81.3` matched by `BC81`).
3. Range match: any element of `scope` formatted `AAA-BBB` whose lex-bounded interval contains `code`.

### 7.2 Semantic fallback
- Pre-compute one embedding per CPG: `title + scope_rationale`. Store in `documents.title_embedding VECTOR(...)` (added in the same migration as the scope columns, or in Step F).
- On unknown ICD code: embed the code's title + description, cosine-rank against `title_embedding`, return top-K with score ≥ threshold.
- Mark these results with `match_type = "semantic"` so the audit/UI can show that routing was inferred, not direct.

### 7.3 Multi-ICD case
If Stage 2 returns multiple high-confidence ICDs (e.g. AF + HTN), call `route_icd_to_cpgs` for each, union the `document_id` shortlist, deduplicate. Stage 4 retrieval runs once over the combined shortlist.

---

## 8. Testing strategy

| Layer | Test type | Examples |
|---|---|---|
| Schemas | Unit | `PatientCase` JSON round-trip; `TreatmentPlan` rejects unknown `type` enum |
| Classifier | Snapshot | Re-run on 3 fixed CPGs, expected ICD blocks present |
| Routing | Unit | `BC81.3 → CPG AF`; range `BC60-BC9Z` covers `BC81`; unknown code → semantic |
| Retrieval | Integration | Vector search with `document_id_filter` returns only chunks from filtered CPGs |
| Workflow | E2E | 3 fixture patients (AF, ED, out-of-scope) produce expected `TreatmentPlan` shape |
| API | Contract | `POST /clinical/plan` returns 200 + valid `TreatmentPlan` JSON |

Place under [tests/](tests/), one file per stage.

---

## 9. Out of scope for v1

The following are intentionally deferred. Do not build them until v1 ships and produces real query logs:

- **Audit trail / decision logging** — pipeline must be stable first; otherwise the audit captures churn.
- **Section-level ICD overrides** — only build if v1 evidence shows recurring misroutes.
- **Streaming / WebSocket transparency** — synchronous JSON response is enough for v1.
- **LangGraph migration** — current 5 stages are linear; Pydantic AI handles it.
- **Consensus / dual-LLM safety check** — add only on the synthesis step in v2 if doctor feedback flags hallucinations.
- **Rejection-driven prompt optimisation** — needs real rejection volume, not synthetic.

---

## 10. Effort summary

| Phase | Tasks | Estimate |
|---|---|---|
| Foundations | A ✅, B, E | ~3.5 h (A done) |
| Scope tagging | C, D | ~2 h + 30 min clinician |
| Routing layer | F, G | ~1.5 h |
| Retrieval + synthesis | H, I | ~2.5 h |
| Orchestration + API | J, K | ~2 h |
| Tests | L | ~1 h |
| **Total** | | **~12.5 h engineering + 30 min clinician review** |

Realistically a focused 2–3 day build for one engineer. (Reduced slightly from the original ~13 h after the chunks-backfill step was eliminated by extending `documents` directly.)

---

## 11. Open decisions before kickoff

1. **CPG scope granularity** → document-level (settled, see §6.5).
2. **Orchestration framework** → Pydantic AI for v1, revisit LangGraph only if branching/HITL is needed.
3. **ICD-11 ingestion source** → WHO ICD-11 API vs MMS linearization download. Pick whichever your network/access supports; data shape is equivalent.
4. **CPG scope reviewer** → who is the clinician signing off on the 25 rows? Block step D until identified.

---

## 12. Done criteria for v1

- All 25 CPG rows in `documents` have `scope_verified = TRUE` with non-empty `icd11_scope` (or non-empty `procedure_scope` for procedure-only CPGs).
- ICD-11 chapters covering the 25 CPGs are ingested and searchable.
- `route_icd_to_cpgs()` passes unit tests for all CPG/ICD fixture pairs.
- `POST /clinical/plan` end-to-end returns a `TreatmentPlan` for each of the 3 fixture patients in under 15 s.
- No hardcoded ICD→CPG mappings anywhere in code (all routing data lives in `documents`).
