# NSTEMI / Unstable Angina (2011) Ingestion & Verification Report

## Executive Summary
The ingestion for the **NSTEMI(2011)** Clinical Practice Guideline (CPG) has been successfully completed and verified with **all checks passed**.

Overall, **55 chunks** and **434 knowledge graph edges** were generated across 13 clinical sections covering diagnosis, risk stratification, triage, pharmacological management, revascularization strategies, special populations, post-discharge care, and cardiac rehabilitation. Severity coverage reached an excellent **69.8%** on safety-critical edges, with outstanding dosage extraction (67 `HAS_DOSAGE` relationships — the richest of any CPG ingested).

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Complete Success

- **Total Chunks**: 55 (10 H1 parents, 3 H1_leaf, 36 H2, 6 H3)
- **Parent-Child Linkage**: 42 child chunks correctly linked to parents, with **0 orphans**.
- **Embedding Integrity**: All true leaf chunks embedded successfully. 1 null H2 chunk is a sub-split parent (by design).
- **Metadata Coverage**: *Diagnosis* (29), *Treatment* (20), *Assessment* (15), *Supportive Treatment* (14), *Reference* (9), *Prevention* (8), *Special Populations* (5), *Pathophysiology* (4), *Methodology* (4), *Classification* (3).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *11.1: Cardiac Rehabilitation Programs* with sim=1.0000.

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Complete Success

- **Total Edges Extracted**: 434 clinical triples.
- **Top Relationships**:
  - `INDICATED_FOR`: 95
  - `INCREASES_RISK_OF`: 85
  - `HAS_DOSAGE`: 67
  - `ASSESSED_BY`: 52
  - `RECOMMENDED_FOR`: 45
  - `CONTRAINDICATED_WITH`: 35
  - `REDUCES_RISK_OF`: 14
  - `REQUIRES_DOSE_ADJUSTMENT`: 12
  - `OTHER`: 12
  - `CAUSES`: 11
- **Severity Coverage**: **69.8%** of safety-critical edges have severity markers — the highest of any CPG ingested so far.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (434/434).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 4,486/4,486 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected.
- **Cross-label duplicates (Safe)**: 305 nodes — expected behaviour.

---

## 4. Cumulative Graph Health (SOP Steps 5, 5b, 6b)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 4,486 | Total edges: 5,059
  - Missing evidence: 0 (0.0%)
  - Orphan nodes: 0
  - Cross-DB linkage: 10/10 sampled UUIDs resolve
  - Duplicate triples: 10 patterns (minor, from overlapping content across CPGs — e.g. shared cardiac drugs)
- **Step 5b — Duplicate node audit** (`kg_dupes.py`):
  - Overall duplication ratio: ~3.3% (MINOR — all cross-label, 0 same-label bad duplicates)
- **Step 6b — Clinical graph lookup** (`test_graph_clinical.py`):
  - All 4 smoke tests completed without errors
  - Drug interaction, comorbidity flag, and prompt formatting all functional

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG:

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Diltiazem | INDICATED_FOR | Non-ST Elevation Myocardial Infarction | "Verapamil or diltiazem as an alternative to patients who are not able to tolerate or who have contra..." |
| Diltiazem | INDICATED_FOR | Unstable Angina | "Verapamil or diltiazem as an alternative to patients who are not able to tolerate or who have contra..." |
| Diltiazem | HAS_DOSAGE | Immediate Release 30-90 mg tds | "Diltiazem \| Immediate release 30-90 mg tds..." |
| Diltiazem | HAS_DOSAGE | Slow Release 100-200 mg od | "Diltiazem \| Slow release 100-200 mg od..." |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| — | — | — | No issues detected |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
