# CPG LLM — Agentic RAG + Knowledge Graph

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pydantic AI](https://img.shields.io/badge/Pydantic_AI-Agent_Framework-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-LLM-4285F4?style=for-the-badge&logo=google&logoColor=white)

A deterministic, auditable **clinical decision support pipeline** grounded in Malaysia's Clinical Practice Guidelines (CPGs). Given a patient case, the system predicts ICD-11 codes, routes to the relevant CPGs, retrieves evidence-graded recommendations, and synthesizes a structured treatment plan — all streamed live to the clinician UI.

> **Last Updated:** May 2026 — Steps J–M complete. Step N (clinician-directed re-synthesis) in progress.

---

## Pipeline Overview

```
[Stage 1]  Patient input (PatientCase)
               │
               ▼
[Stage 2]  Symptom → ICD-11 DDx
               │  Pass 1: vector search + morbidity tabulation
               │  Pass 2: Gemini 2.5 Flash + thinking tokens re-rank by clinical context
               ▼
[Stage 3]  ICD → CPG routing
               │  Structural match (exact / parent block / range) on documents.icd11_scope
               │  Semantic fallback if no structural match
               ▼
[Stage 4]  Scoped CPG retrieval
               │  LLM generates 3 targeted queries → vector search scoped by document_id_filter
               │  Top-20 chunks deduplicated by score
               ▼
[Stage 5]  Treatment plan synthesis
               │  Gemini Flash structured JSON → TreatmentPlan (Pydantic-validated)
               ▼
        Doctor UI — live SSE stream + AI reasoning trace
```

Each stage produces a typed, independently-testable artifact. No hardcoded ICD→CPG mappings — all routing is driven by `icd11_scope` metadata on `documents`.

---

## Architecture

| Layer | Component | Technology |
|---|---|---|
| **LLM** | DDx re-ranking, query gen, synthesis | Gemini 2.5 Flash (thinking) via OpenRouter |
| **Embeddings** | Chunks + ICD-11 codes | AWS Bedrock Titan v1 — `vector(1536)` |
| **Vector DB** | Chunk retrieval, scoped search | PostgreSQL + pgvector (Neon) |
| **Knowledge Graph** | Entity relationships | Neo4j Aura + Graphiti |
| **API** | Clinical plan + SSE streaming | FastAPI (`agent/api.py`) on port 8058 |
| **Doctor UI** | Clinician frontend | React + Vite on port 5173 |

---

## Agent Tools

| Tool | Purpose |
|---|---|
| `vector_search` | Semantic similarity search, supports `document_id_filter` for CPG scoping |
| `hybrid_search` | Vector + keyword combined search, also scopeable |
| `graph_search` | Neo4j entity relationships and knowledge graph traversal |
| `get_drug_information` | Multi-step drug retrieval from Neo4j + PostgreSQL |
| `get_algorithm_pathway` | Step-by-step CPG algorithm navigation |

---

## CPG Corpus (19 Guidelines)

All 16 scope-classified CPGs have `scope_verified = TRUE` with non-empty `icd11_scope` arrays in the `documents` table. Routing is fully data-driven.

| CPG | Edition | Sections | RAG Status |
|---|---|---|---|
| Erectile Dysfunction | — | 12 | ✅ Optimized |
| Heart Failure | 5th | 26 | ✅ Optimized |
| Dyslipidaemia | 6th | 14 | ✅ Optimized |
| Ischaemic Stroke | 3rd | 18 | ✅ Optimized |
| STEMI | 4th | 20 | ✅ Optimized |
| NSTE-ACS | 3rd | 12 | ✅ Optimized |
| Atrial Fibrillation | 2012 | 12 | ✅ Optimized |
| NSTEMI | 2011 | 13 | ✅ Optimized |
| Breast Cancer | 3rd | 16 | ✅ Optimized |
| CVD Prevention in Women | 2016 | 9 | ✅ Optimized |
| Prevention, Diagnosis & Mgmt of IE | — | 10 | ✅ Optimized |
| Percutaneous Coronary Intervention | — | 11 | ✅ Optimized |
| Nasopharyngeal Carcinoma | — | — | ✅ Optimized |
| Hypertension | 5th | — | 📋 Ingested (raw) |
| Stable CAD | 2nd | — | 📋 Ingested (raw) |
| Cancer Pain | 2nd | — | 📋 Ingested (raw) |
| Heart Disease in Pregnancy | 2nd | — | 📋 Ingested (raw) |
| Primary & Secondary Prevention of CVD | 2017 | — | 📋 Ingested (raw) |
| Anaesthesia Medication Safety | 2024 | — | 📋 Ingested (raw) |

### ICD-11 Index

3,914 ICD-11 codes ingested across chapters **02, 05, 08, 11, 16, 17** at `vector(1536)`. Used for DDx search and structural CPG routing.

---

## RAG Document Structure

Each fully optimized CPG section is a self-contained, atomic knowledge chunk:

- **`<!-- METADATA -->` blocks** — `category`, `use_case`, `patient_input`, `output`, `critical`, `treatment_type` fields for downstream classification and priority retrieval.
- **Localized abbreviation tables** — per section, eliminating cross-file lookups.
- **Contextual anchors** — summarized content from referenced sections embedded inline, enabling single-chunk retrieval.
- **Evidence keys** — Levels of Evidence and Grades of Recommendation embedded per clinical section.
- **Standardized `[Level, Grade]` recommendation blocks** throughout.

---

## Project Structure

```
CPG-LLM-Agentic-RAG-Knowledge-Graph/
├── agent/
│   ├── api.py                 # FastAPI — POST /clinical/plan + /stream + /resynthesize/stream
│   ├── clinical_workflow.py   # Orchestrator: run_clinical_workflow_streaming()
│   ├── clinical_stages.py     # Stages 2–5 (DDx, routing, retrieval, synthesis)
│   ├── routing.py             # route_icd_to_cpgs() — structural + semantic fallback
│   ├── models.py              # PatientCase, TreatmentPlan, CPGDocRef, WorkflowResult
│   ├── tools.py               # Retrieval tools with document_id_filter support
│   ├── db_utils.py            # PostgreSQL vector/hybrid search with scoped SQL
│   ├── graph_utils.py         # Neo4j + Graphiti entity queries
│   ├── agent.py               # Pydantic AI agent (free-form Q&A mode)
│   └── prompts.py             # System prompts
├── Doctor UI/                 # React clinician frontend
│   └── src/
│       ├── components/
│       │   ├── sections/      # DiagnosisSection, CarePlanSection, PipelineProgress
│       │   └── shared/        # PatientBanner, TraceDrawer, AIReasoningDrawer
│       ├── context/AppContext.jsx   # Global state + streaming reducer
│       └── lib/
│           ├── clinicalApi.js       # runClinicalPlanStream(), resynthesizePlanStream()
│           └── clinicalMappers.js   # DDx → UI, TreatmentPlan → care plan
├── ingestion/
│   ├── ingest.py              # Main ingestion pipeline
│   ├── classify_cpg_scope.py  # LLM-based ICD-11 scope classifier
│   └── verify_cpg_scope.py    # Clinician review → scope_verified = TRUE
├── ddx/
│   ├── ingest_icd11_full.py   # WHO ICD-11 API recursive ingestion (3,914 codes)
│   └── search_ddx.py          # Interactive DDx search (standalone)
├── markdown/                  # RAG-optimized CPG section files
├── sql/
│   ├── schema.sql             # Full database schema
│   └── migrations/            # 001–004 applied (scope columns, ICD embedding resize)
├── tasks/                     # Step-by-step implementation briefs
├── tests/                     # Unit + E2E + streaming test suites (59+ passing)
├── cli.py                     # CLI for free-form CPG Q&A
└── .env                       # Environment config (not tracked)
```

---

## Environment Configuration

```env
# PostgreSQL (Neon)
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require

# Neo4j Aura
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# LLM — OpenRouter
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=google/gemini-2.0-flash-001

# Embeddings — AWS Bedrock Titan v1 (1536d)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Gemini (DDx re-ranking)
GEMINI_API_KEY=AIzaxxxxx
```

---

## Running Locally

```bash
# Backend API (port 8058)
uvicorn agent.api:app --port 8058 --reload

# Doctor UI (port 5173)
cd "Doctor UI"
npm run dev

# Ingest CPG documents
python -m ingestion.ingest -d markdown -v

# Run tests
pytest tests/ -v
```

---

## Implementation Status

| Step | Feature | Status |
|---|---|---|
| A–E | Schemas, DB migrations, ICD-11 ingestion, scope tagging | ✅ Done |
| F–G | CPG routing + scoped retrieval tools | ✅ Done |
| H–I | Targeted query gen + treatment plan synthesis | ✅ Done |
| J | Clinical orchestrator (`clinical_workflow.py`) | ✅ Done |
| K | API endpoints + Doctor UI wiring | ✅ Done |
| L | E2E smoke tests (3 fixture patients, 59+ tests) | ✅ Done |
| M | Live pipeline transparency UI + SSE streaming | ✅ Done |
| **N** | **Clinician-directed re-synthesis (Steps 3–5 re-run on override)** | 🔜 In Progress |
