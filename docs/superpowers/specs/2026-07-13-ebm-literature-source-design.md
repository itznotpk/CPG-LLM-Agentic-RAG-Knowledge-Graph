# Design — EBM Literature as a Third Evidence Source

Date: 2026-07-13
Status: Approved design → pending implementation plan
Working project: `CPG LLM/` (only). Research basis: `CPG LLM/findings.md`.

## 1. Goal

Inject graded, recent published evidence (Europe PMC) into the care-plan synthesis so
recommendations are **backed by** the literature and, where **no routed CPG covers a
question**, can be **extended by** the literature — without displacing the Malaysian MoH
CPG grounding that is the system's authoritative local standard.

Non-goals: replacing CPGs; integrating paywalled point-of-care tools (UpToDate / DynaMed /
BMJ Best Practice have no public API and are out of scope — we replicate their *value*
via publication-type + recency filtering, not their content).

### Not ingested — live fetch by design (READ THIS FIRST)

EBM literature is **NOT chunked, embedded, or stored in pgvector/Neo4j like CPGs.** It is
fetched **live** from Europe PMC at consultation time (Stage 4.6) and thrown away after the
plan is built. This is deliberate and load-bearing:

- CPGs are stable and curated → it makes sense to ingest them once into pgvector for RAG.
- **Literature updates far faster than CPGs.** Chunking EBM would freeze it at ingest time
  and require constant re-ingestion to stay current — defeating the entire reason for
  adding it. A live API call always returns whatever Europe PMC has *today*.
- The only thing that may touch a store is an OPTIONAL short-lived abstract **cache**
  (§4) purely to cut latency/API load — it is not a corpus and can be expired aggressively
  or disabled with no loss of correctness.

Do NOT implement Stage 4.6 as an ingestion/chunking job. It is a scoped, always-live,
EBM-only query — closer to "PubMed search at the point of care" than to the CPG RAG path.

## 2. Confirmed decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Role of EBM | Extra evidence injected into Stage 5 synthesis (can shape recs) |
| Authority | Supporting when a CPG covers it; may fill gaps (tagged) when CPG is silent; never silently overrides a CPG |
| Source | Europe PMC only (free, no API key), with pub-type + recency filters |
| Query key | DDx disease names + draft plan's drug/intervention terms |
| Timing | Two-pass synthesis (draft → EBM fetch → refine) |
| UI surfacing | One standalone "Evidence & Literature" panel; recs not individually tagged |

## 3. Pipeline architecture (two-pass synthesis)

```
Stage 4    Retrieve CPG chunks                       (unchanged)
Stage 4.5  KG inject                                 (unchanged)
Stage 5    Synthesize DRAFT plan   (CPG + KG only)   (existing synthesis call)
Stage 4.6  EBM fetch (NEW)         key = DDx disease names + draft plan drug/intervention terms
Stage 5.5  Refine plan (NEW)       re-synthesize with CPG + KG + EBM evidence block
Stage 6    Safety critic                             (unchanged; runs on the REFINED plan)
```

- Stage 5.5 reuses the existing `resynthesize` synthesis path, adding a clearly delimited
  EBM evidence block to the Stage-5 user content.
- Wire into all pipeline entrypoints that already run synthesis:
  `run_clinical_workflow`, `run_clinical_workflow_streaming`, and
  `run_resynthesize_streaming` (the UI's real plan path) in
  `backend/agent/clinical_workflow.py`.
- **Latency note (accepted):** two-pass adds one extra synthesis LLM call per consult.
- **Safety note (accepted):** Stage 6 runs on the refined, EBM-influenced plan, so any
  literature-introduced rec is still safety-gated. Correct and intended.

## 4. EBM fetch module — Stage 4.6

New file `backend/agent/ebm_lookup.py`.

- **Source:** Europe PMC REST search endpoint. No API key. One call per query.
- **Query construction:** disease name(s) `AND` plan term(s), filtered to
  `publication type ∈ {systematic review, meta-analysis, RCT, guideline}` and a **recency
  window** (default ~last 7 years, env-tunable). This surfaces top-of-pyramid evidence,
  replicating what UpToDate/DynaMed pre-grade by hand.
- **Plan-term extraction:** pull drug + intervention names from the Stage-5 DRAFT plan
  (`TreatmentPlan` medications + interventions) — reuse existing normalization helpers
  where available (mirror the drug-class keyword maps already used in the coverage-gap
  detector) rather than a new parser.
- **Output:** top-N structured records:
  `{title, abstract_snippet, journal, year, pub_type → evidence_tier, pmid/doi, url}`.
  `evidence_tier` is derived deterministically from `pub_type`
  (systematic review/meta-analysis > RCT > guideline > other).
- **Fail-open resilience (hard requirement):** timeout-bounded HTTP + retry/backoff,
  mirroring `_llm_call_with_retry` in `clinical_stages.py`. On ANY failure (timeout, 5xx,
  parse error, zero results) EBM is simply absent: Stage 5.5 is skipped and the Stage-5
  DRAFT plan stands. Europe PMC being down MUST NOT block a plan or drive it to
  degraded/zero-confidence. This is the inverse of the CPG fail-loud contract — EBM is
  additive, so its absence is a no-op, not a degradation.
- **Cache:** abstracts cached keyed on normalized `(disease + term)` (literature changes
  slowly) to cut latency and Europe PMC load. In-process cache to start (mirrors
  `_PHRASE_CACHE` pattern); a persistent cache is a later optional optimization.

## 5. Provenance & authority (the safety contract)

- EBM records are tagged `source: "ebm_literature"` — structurally and visually distinct
  from CPG chunks and KG edges, everywhere they appear (evidence block, response model, UI).
- **Refined-synthesis prompt rule** (new prompt block for Stage 5.5):
  1. CPGs are the authoritative local standard.
  2. EBM may SUPPORT a CPG-covered recommendation (add citation / context / nuance).
  3. EBM may INTRODUCE a recommendation ONLY when no routed CPG addresses that question,
     and it must be explicitly tagged "literature-based, no local CPG."
  4. A paper that contradicts or updates a CPG surfaces as a flagged literature NOTE for
     the clinician — never a silent override of a CPG-grounded rec.
- New Pydantic model (e.g. `EbmEvidence`) in `backend/agent/models.py`, carried on
  `TreatmentPlan` / `ClinicalPlanResponse` alongside existing fields.

## 6. Frontend (`frontend/doctor-ui`)

- New standalone **"Evidence & Literature"** tab/panel in the care plan (GlassCard,
  following existing tab patterns in `CarePlanSection.jsx`). Lists graded citations for the
  case: title, journal, year, evidence tier badge, external link. Recommendations are NOT
  individually tagged (per the chosen UI model).
- New SSE event type `ebm_evidence` emitted from Stage 4.6, added to BOTH consumers
  (`backend/agent/api.py` and `backend/clinical_cli.py`) per the event-type contract.
- Carry EBM records through `clinicalPlanResponse`; add a pure mapper in
  `clinicalMappers.js` (backend JSON → UI shape). No Supabase coupling in the mapper.
- Persistence (optional, later): if EBM cites should survive on the consultation row,
  follow the standard migration + `update_consultation` RPC superset-rebuild procedure —
  NOT in the first cut.

## 7. Evaluation impact

- **Layer D faithfulness** (`backend/eval/run_faithfulness_eval.py`) must judge
  EBM-grounded claims against the EBM+CPG evidence set, not CPG-only — otherwise
  literature-based gap-filling recs are scored "unsupported" and corrupt the metric.
- New tests:
  - `backend/tests/test_ebm_lookup.py` — Europe PMC parsing + tier derivation, fully
    mocked HTTP (no live network in the suite).
  - Fail-open degradation test (INF-style, alongside `run_degradation_robustness_eval.py`)
    proving a Europe PMC outage does not block or degrade the plan.
  - A two-pass wiring test asserting Stage 5.5 runs only when EBM records are present and
    is skipped (draft stands) when EBM is absent.

## 8. Open items intentionally deferred

- Persistent (cross-process) EBM cache.
- Supabase persistence of EBM citations on the consultation row.
- Second-tier Cochrane-only pass (Europe PMC journal filter) — can be added later if the
  general graded query under-surfaces systematic reviews.
- NCBI E-utilities / MeSH-precision path as an alternate source.
