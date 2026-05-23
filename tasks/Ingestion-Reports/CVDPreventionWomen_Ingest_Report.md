# CVD Prevention in Women (2016) Ingestion & Verification Report

> **Last re-verified:** 2026-05-18 (section-0 re-chunked and re-embedded; all checks passed)

## Executive Summary
The **CVD-Prevention-Women(2016)** Clinical Practice Guideline (CPG) is fully ingested and verified. Section 0.2 (`Critical Reference Tables`) was re-chunked on 2026-05-18 after its original single h2 block (8,505 chars / 5 tables) exceeded the Bedrock Titan input limit and produced a null embedding. The fix was to split it into five h3 subsections (0.2.1–0.2.5), each under 3,300 chars, and re-ingest section 0 only with `--skip-graph`. **All checks now pass.**

Current footprint: **72 chunks** across 9 sections and **508 KG edges**, with **71.9%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Complete

- **Total Chunks**: 72 (9 H1, 43 H2, 20 H3)
- **Parent-Child Linkage**: 63 child chunks, **0 orphans**.
- **Embedding Integrity**: 0 true-leaf null embeddings. 4 null h2 entries are all sub-split parents (expected). Dim = 1536 on all populated rows.
  - Section 0.2 was split into 5 h3 subsections (0.2.1–0.2.5, max 3,295 chars each) to resolve an oversize embedding failure on the original single-block 8,505-char h2.
- **Metadata Coverage**: *Special Populations* (34), *Treatment* (24), *Assessment* (20), *Epidemiology* (17), *Diagnosis* (16), *Classification* (16), *Reference* (14), *Prevention* (8), *Screening* (7), *Pathophysiology* (5).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *5.5: Assessment Of CVD Risk* with sim=1.0000.

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 508 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 230
  - `ASSESSED_BY`: 68
  - `RECOMMENDED_FOR`: 50
  - `INDICATED_FOR`: 41
  - `REDUCES_RISK_OF`: 26
  - `CONTRAINDICATED_WITH`: 23
  - `TREATS`: 23
  - `REQUIRES_MONITORING`: 18
  - `CAUSES`: 10
  - `OTHER`: 8
  - `INTERACTS_WITH`: 5
  - `FIRST_LINE_FOR`: 4
  - `HAS_DOSAGE`: 1
  - `REQUIRES_DOSE_ADJUSTMENT`: 1
- **Severity Coverage**: **71.9%** (41/57) of safety-critical edges have severity markers — well above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (508/508).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 4,446/4,446 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected.
- **Cross-label duplicates (Safe)**: 309 nodes — expected behaviour (e.g., "hypertension" as `[Condition]`, `[AdverseEvent]`, `[RiskFactor]`; "sedation" as `[Drug]`, `[Procedure]`, `[AdverseEvent]`).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 4,446 | Total edges: 4,885

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-18):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Previous Myocardial Infarction | INCREASES_RISK_OF | Heart Failure | "Women with prior MI are at a higher risk of developing HF than men." |
| Previous Myocardial Infarction | INCREASES_RISK_OF [MAJOR] | Sudden Cardiac Death | "In women with a previous MI, the risk of SCD is 2-fold higher…" |
| Hypertension | INCREASES_RISK_OF [MAJOR] | Heart Failure | "Hypertension increases the risk of developing HF almost 3-fold in women as compared to 2-fold in men…" |
| Hypertension | INCREASES_RISK_OF [MAJOR] | Coronary Heart Disease | "Hypertension and LVH are both stronger predictors for CVD, HF, CHD and stroke mortality in women than…" |
| Cardiomyopathy | INCREASES_RISK_OF | High Cardiotoxicity | "Patient Related Risk: Heart failure or cardiomyopathy…" |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| — | — | — | No issues detected |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
