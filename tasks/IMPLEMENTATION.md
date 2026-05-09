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
| ICD-11 vector search (3,914 codes, chapters 02/05/08/11/16/17) | ✅ Done | [ddx/](ddx/) |
| ICD-11 → CPG routing (`route_icd_to_cpgs`) | ✅ Done | [agent/routing.py](agent/routing.py) |
| Scoped retrieval (`document_id_filter`) | ✅ Done | [agent/tools.py](agent/tools.py) |
| Structured patient input contract | ✅ Done | [agent/models.py](agent/models.py) |
| Structured treatment plan output | ✅ Done | [agent/models.py](agent/models.py) |
| Pipeline stages 2–5 (DDx→Route→Retrieve→Synthesize) | ✅ Done | [agent/clinical_stages.py](agent/clinical_stages.py) |
| Multi-stage clinical orchestrator + API endpoint | 🔜 Step 08 | — |

**One step remaining**: wire the stages into `agent/clinical_workflow.py` and expose `POST /clinical/plan`.

---

## 2. Target workflow

```
[Stage 1]  Patient input              (PatientCase Pydantic schema)
              │
              ▼
[Stage 2]  Symptom → ICD-11           Pass 1: vector search + Morbidity Tabulation (search_ddx)
              │                        Pass 2: Gemini 2.5 Flash + thinking (budget=5k) re-ranks
              │  list[DDxResult]               by clinical probability (age/sex/vitals/meds)
              ▼                        Fallback to Pass 1 order if LLM fails
[Stage 3]  ICD → CPG routing          exact/parent/range structural match on documents.icd11_scope
              │                        grouped by cpg_name → CPGDocRef.document_ids (all sections)
              │  list[CPGDocRef]        semantic fallback (scoped chunk vector search) if no match
              ▼
[Stage 4]  CPG section retrieval      LLM generates 3 targeted queries (Gemini Flash)
              │                        vector_search_tool scoped via document_id_filter
              │  list[ChunkResult]      deduplicated, top-20 by score
              ▼
[Stage 5]  Treatment plan synthesis   Gemini Flash structured JSON → TreatmentPlan.model_validate()
              │                        cpg_source must cite retrieved chunk; else unresolved_questions
              ▼
       Doctor UI (answer + evidence chain)
```

Each stage produces a typed artifact. Each stage is independently testable. The orchestrator (Step 08) is a thin sequential controller — no graph framework needed for v1.

---

## 3. Components — what's new vs reused

| # | Component | Status | Path |
|---|---|---|---|
| 3.1 | `PatientCase` / `Recommendation` / `TreatmentPlan` schemas | ✅ Done | [agent/models.py](../agent/models.py) |
| 3.2 | Extend `documents` table with scope columns + GIN index | ✅ Done | [sql/migrations/001_documents_scope.sql](../sql/migrations/001_documents_scope.sql) |
| 3.3 | CPG scope classifier (one-shot) | ✅ Done | [ingestion/classify_cpg_scope.py](../ingestion/classify_cpg_scope.py) |
| 3.4 | Human review + verification flip | ✅ Done | [ingestion/verify_cpg_scope.py](../ingestion/verify_cpg_scope.py) |
| 3.5 | ICD-11 ingestion expanded to relevant chapters | ✅ Done | [ddx/ingest_icd11_full.py](../ddx/ingest_icd11_full.py) |
| 3.6 | DDx: vector + tabulation (Pass 1) + Gemini 2.5 Flash thinking re-rank (Pass 2) | ✅ Done | [agent/clinical_stages.py](../agent/clinical_stages.py) |
| 3.7 | `route_icd_to_cpgs()` — structural + semantic, grouped by cpg_name | ✅ Done | [agent/routing.py](../agent/routing.py) |
| 3.8 | `document_id_filter` on retrieval tools + db_utils | ✅ Done | [agent/tools.py](../agent/tools.py), [agent/db_utils.py](../agent/db_utils.py) |
| 3.9 | Targeted query generator + scoped retrieval (Stage 4) | ✅ Done | [agent/clinical_stages.py](../agent/clinical_stages.py) |
| 3.10 | Clinical orchestrator | 🔜 Step 08 | `agent/clinical_workflow.py` |
| 3.11 | API endpoint `POST /clinical/plan` | 🔜 Step 08 | [agent/api.py](../agent/api.py) |

> **Architectural simplification (post-IMPLEMENTATION-v1):** Originally proposed a separate `cpg_documents` table with a new `cpg_id` foreign key on `chunks`. After inspecting [sql/schema.sql](../sql/schema.sql), every document in this system *is* a CPG, and `chunks.document_id` already references `documents.id`. So scope metadata is added as columns on `documents` directly — no new table, no chunks backfill, no FK churn. Routing filters `documents` by `icd11_scope` and joins chunks via the existing `document_id`.

---

## 4. Build order

Each step is independently shippable and testable. Do not start step N+1 until step N has a passing test.

### ~~Step A — Schema foundations (~1 h)~~ ✅ DONE
- ~~Added `PatientCase`, `Recommendation`, `TreatmentPlan` to [agent/models.py](../agent/models.py).~~
- ~~Tests in [tests/test_clinical_schemas.py](../tests/test_clinical_schemas.py) — 32 passing.~~
- Brief: [STEP_01_schemas.md](STEP_01_schemas.md).

### ~~Step B — Extend `documents` with scope columns (~30 min)~~ ✅ DONE
- ~~`ALTER TABLE documents` adding `icd11_scope TEXT[]`, `procedure_scope TEXT[]`, `scope_rationale TEXT`, `scope_verified BOOLEAN`, `classified_at`, `verified_at`, `verified_by`.~~
- ~~New GIN index on `documents(icd11_scope)`. Migration: [sql/migrations/001_documents_scope.sql](../sql/migrations/001_documents_scope.sql).~~
- ~~Updated `CREATE TABLE documents` in [sql/schema.sql](../sql/schema.sql) to include new columns inline.~~
- Brief: [STEP_02_extend_documents.md](STEP_02_extend_documents.md).

### ~~Step C — CPG scope classifier (~1.5 h)~~ ✅ DONE
- ~~Script `ingestion/classify_cpg_scope.py` — groups CPGs by `cpg_name`, calls OpenRouter (Gemini Flash), parses JSON, upserts `icd11_scope` with `scope_verified = FALSE`.~~
- ~~MiMo hallucinated 10/16 CPG scopes; fixed via migrations [002](../sql/migrations/002_fix_cpg_scopes.sql) and [003](../sql/migrations/003_fix_remaining_scopes.sql).~~
- ~~`ingestion/regenerate_scope_review.py` added to rebuild review file from DB state.~~

### ~~Step D — Human verification (~30 min clinician + 20 min eng)~~ ✅ DONE
- ~~Dr Chin reviewed `tasks/cpg_scope_review.md`: 9 Approved, 7 Edited, 0 Rejected.~~
- ~~`ingestion/verify_cpg_scope.py` parsed review file, flipped `scope_verified = TRUE`, wrote `verified_at` / `verified_by`.~~
- ~~All 16 CPG rows in `documents` have `scope_verified = TRUE`.~~

### ~~Step E — Expand ICD-11 ingestion (~2 h)~~ ✅ DONE
- ~~New script `ddx/ingest_icd11_full.py` — WHO ICD-11 API OAuth2, recursive chapter walker, 8 req/sec rate limit, exponential backoff, resume via `ddx/data/.icd11_progress.json`, Bedrock 1536-dim embeddings.~~
- ~~Migration [sql/migrations/004_icd11_embedding_to_1536.sql](../sql/migrations/004_icd11_embedding_to_1536.sql) standardised `icd11_codes.embedding` from vector(768) → vector(1536).~~
- ~~Ingested 3,914 codes: ch02=1244, ch05=640, ch08=845, ch11=593, ch16=545, ch17=47 (preserved).~~
- ~~`ddx/migrate_inclusion_embeddings.py` populated `inclusion_embeddings` JSONB — 197 codes updated.~~
- Brief: [STEP_05_icd11_ingestion.md](STEP_05_icd11_ingestion.md).

### ~~Step F — `route_icd_to_cpgs()` (~1 h)~~ ✅ DONE
- ~~New module `agent/routing.py` — `CPGDocRef` model, exact/parent/range structural match, semantic fallback via scoped chunk vector search.~~
- ~~Tests: 17 passing, zero real DB/embedding calls.~~

### ~~Step G — Scope retrieval tools (~30 min)~~ ✅ DONE
- ~~`document_id_filter: list[str] | None` added to `VectorSearchInput`, `HybridSearchInput`, `GraphSearchInput` in [agent/tools.py](../agent/tools.py).~~
- ~~`vector_search()` and `hybrid_search()` in [agent/db_utils.py](../agent/db_utils.py) extended with inline SQL filter (`ANY($3::uuid[])`). Graph tool logs warning, stays unscoped.~~

> Brief: [STEP_06_routing_and_scoped_retrieval.md](STEP_06_routing_and_scoped_retrieval.md).

### ~~Step H — Targeted query generator (~1 h)~~ ✅ DONE
- ~~`_generate_retrieval_queries()` in `agent/clinical_stages.py` — LLM produces 3 focused retrieval queries from PatientCase + ICD codes + CPG names. Scoped vector search via `document_id_filter`.~~

### ~~Step I — Treatment plan synthesizer (~1.5 h)~~ ✅ DONE
- ~~`stage_5_synthesize()` in `agent/clinical_stages.py` — Gemini Flash structured JSON output → `TreatmentPlan.model_validate()`. Falls back to `unresolved_questions` when evidence is absent.~~
- ~~**07B bonus**: `stage_2_ddx` upgraded to two-pass — Pass 1 vector+tabulation, Pass 2 Gemini 2.5 Flash + thinking (budget=5000) re-ranks by clinical probability (age/sex/vitals/meds). Fallback to math order on failure.~~

> Briefs: [STEP_07_pipeline_stages.md](STEP_07_pipeline_stages.md), [STEP_07B_ddx_llm_rerank.md](STEP_07B_ddx_llm_rerank.md).

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
- **Option A chosen (no schema change):** embed the ICD code's title + description, scoped vector search against chunks from `scope_verified = TRUE` documents, deduplicate by `document_id`, return top-K by best chunk score ≥ threshold.
- `documents.title_embedding` column was **not added** — Option A proved sufficient.
- Results carry `match_type = "semantic"` so the UI can flag inferred routing.

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
| ~~Foundations~~ | ~~A, B, E~~ ✅ | ~~done~~ |
| ~~Scope tagging~~ | ~~C, D~~ ✅ | ~~done~~ |
| ~~Routing layer~~ | ~~F, G~~ ✅ | ~~done~~ |
| ~~Retrieval + synthesis~~ | ~~H, I~~ ✅ | ~~done~~ |
| Orchestration + API | J, K (Step 08) | ~2 h |
| Tests | L (Step 08) | ~1 h |
| **Remaining** | | **~3 h** |

Realistically a focused 2–3 day build for one engineer. (Reduced slightly from the original ~13 h after the chunks-backfill step was eliminated by extending `documents` directly.)

---

## 11. Decisions made

1. **CPG scope granularity** → document-level ✅ (see §6.5)
2. **Orchestration framework** → plain async functions, no LangGraph ✅
3. **ICD-11 ingestion source** → WHO ICD-11 API (OAuth2, recursive chapter walker) ✅
4. **CPG scope reviewer** → Dr Chin reviewed all 16 CPGs ✅
5. **Embedding dimension** → 1536 (Bedrock Titan v1), unified across `chunks` and `icd11_codes` ✅
6. **Semantic routing fallback** → Option A (chunk-based, no new column) ✅
7. **DDx re-ranking** → two-pass: math first, Gemini 2.5 Flash thinking re-ranks by clinical context ✅
8. **LLM for synthesis** → Gemini 2.0 Flash via OpenRouter (raw `openai.AsyncOpenAI`, not Pydantic AI — avoids `service_tier` rejection) ✅

---

## 12. Done criteria for v1

- ✅ All 16 CPG rows in `documents` have `scope_verified = TRUE` with non-empty `icd11_scope`.
- ✅ 3,914 ICD-11 codes across chapters 02/05/08/11/16/17 ingested and searchable at vector(1536).
- ✅ `route_icd_to_cpgs()` passes 19 unit tests; groups by `cpg_name`, returns all section IDs.
- ✅ Pipeline stages 2–5 implemented and tested (59 tests passing total).
- 🔜 `POST /clinical/plan` end-to-end returns a `TreatmentPlan` for each of the 3 fixture patients in under 15 s.
- ✅ No hardcoded ICD→CPG mappings anywhere in code (all routing data lives in `documents`).
