# CVD Prevention in Women (2016) Ingestion & Verification Report

## Executive Summary
The ingestion for the **CVD-Prevention-Women(2016)** Clinical Practice Guideline (CPG) has been successfully completed and verified with **all checks passed**.

Overall, **76 chunks** and **682 knowledge graph edges** were generated across 9 clinical sections covering cardiovascular disease types, risk factors, risk assessment, prevention recommendations, and adherence/compliance. This is the **highest-yield CPG** ingested to date with 682 edges — reflecting the comprehensive nature of CVD risk factor documentation. Severity coverage reached an excellent **69.4%** on safety-critical edges.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Complete Success

- **Total Chunks**: 76 (9 H1 parents, 52 H2, 15 H3)
- **Parent-Child Linkage**: 67 child chunks correctly linked to parents, with **0 orphans**.
- **Embedding Integrity**: All true leaf chunks embedded successfully. 3 null H2 chunks are sub-split parents (by design).
- **Metadata Coverage**: *Special Populations* (37), *Treatment* (25), *Assessment* (22), *Epidemiology* (19), *Reference* (17), *Diagnosis* (16), *Classification* (16), *Prevention* (9), *Screening* (8), *Pathophysiology* (7).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Appendix 1: Cancer And The Heart* with sim=1.0000.

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Complete Success

- **Total Edges Extracted**: 682 clinical triples.
- **Top Relationships**:
  - `INCREASES_RISK_OF`: 269
  - `RECOMMENDED_FOR`: 102
  - `ASSESSED_BY`: 80
  - `CONTRAINDICATED_WITH`: 44
  - `INDICATED_FOR`: 38
  - `REDUCES_RISK_OF`: 33
  - `OTHER`: 25
  - `TREATS`: 25
  - `CAUSES`: 24
  - `FIRST_LINE_FOR`: 22
  - `REQUIRES_MONITORING`: 13
- **Severity Coverage**: **69.4%** of safety-critical edges have severity markers — excellent, well above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (682/682).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 3,711/3,711 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected.
- **Cross-label duplicates (Safe)**: 244 nodes — expected behaviour (e.g., "hypertension" as `[Condition]`, `[AdverseEvent]`, and `[RiskFactor]`).

---

## 4. Cumulative Graph Health (SOP Steps 5, 5b, 6b)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 3,711 | Total edges: 4,070
  - Missing evidence: 0 (0.0%)
  - Orphan nodes: 0
  - Cross-DB linkage: 10/10 sampled UUIDs resolve
  - Duplicate triples: 5 patterns (minor, from overlapping content across CPGs)
- **Step 5b — Duplicate node audit** (`kg_dupes.py`):
  - Overall duplication ratio: **3.3%** (MINOR — all cross-label, 0 same-label bad duplicates)
- **Step 6b — Clinical graph lookup** (`test_graph_clinical.py`):
  - All 4 smoke tests completed without errors
  - Drug interaction, comorbidity flag, and prompt formatting all functional

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG:

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Hypertension | INCREASES_RISK_OF [MAJOR] | Heart Failure | "Hypertension increases the risk of developing HF almost 3-fold in women as compared to 2-fold in men..." |
| Hypertension | INCREASES_RISK_OF [MAJOR] | Cardiovascular Disease | "This age-related rise in BP, particularly systolic BP and pulse pressure, contributes substantially..." |
| Hypertension | INCREASES_RISK_OF [MAJOR] | Coronary Heart Disease | "An increase in SBP by 20 mmHg is associated with a two fold increase in the rate of death from stroke..." |
| Hypertension | INCREASES_RISK_OF | Cardiovascular Risk With OCP Use | "The CV risk of COCs is increased if the women is diabetic, obese, smokes, or has hypertension..." |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| — | — | — | No issues detected |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
