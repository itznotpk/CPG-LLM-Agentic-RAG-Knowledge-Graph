# Colorectal Carcinoma (2017) Ingestion & Verification Report

## Executive Summary
The ingestion for the **Colorectal-Carcinoma(2017)** Clinical Practice Guideline (CPG) has been successfully completed and verified with **all checks passed**.

Overall, **38 chunks** and **220 knowledge graph edges** were generated across 10 clinical sections covering screening, surgical management, chemotherapy/radiotherapy, and prevention. The ingestion achieved an excellent severity coverage of **68.4%** on safety-critical edges, with perfect cross-database integrity and zero duplicate nodes.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Complete Success

- **Total Chunks**: 38 (6 H1 parents, 4 H1_leaf, 23 H2, 5 H3)
- **Parent-Child Linkage**: 28 child chunks correctly linked to parents, with **0 orphans**.
- **Embedding Integrity**: All true leaf chunks embedded successfully. The single null H2 chunk is a sub-split parent (by design).
- **Metadata Coverage**: *Classification* (12), *Prevention* (12), *Reference* (11), *Screening* (11), *Treatment* (9), *Assessment* (5), *Diagnosis* (5), *Supportive Treatment* (4), *Introduction* (1), *Epidemiology* (1).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *5.1: Pre-Operative Preparation* with sim=1.0000.

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Complete Success

- **Total Edges Extracted**: 220 clinical triples.
- **Top Relationships**:
  - `INCREASES_RISK_OF`: 49
  - `ASSESSED_BY`: 34
  - `INDICATED_FOR`: 32
  - `REDUCES_RISK_OF`: 30
  - `RECOMMENDED_FOR`: 28
  - `CAUSES`: 13
  - `TREATS`: 12
  - `OTHER`: 8
  - `FIRST_LINE_FOR`: 7
- **Severity Coverage**: **68.4%** of safety-critical edges have severity markers — well above the 30% threshold. Excellent capture of drug safety data (e.g., Heparin→DVT/PE with `[MAJOR]` severity).
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (220/220).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 2757/2757 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected.
- **Cross-label duplicates (Safe)**: 170 nodes — expected behaviour (e.g., "fatigue" as `[RiskFactor]`, `[AdverseEvent]`, and `[Condition]`).

---

## 4. Cumulative Graph Health (SOP Steps 5, 5b, 6b)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 2,895 | Total edges: 3,030
  - Missing evidence: 0 (0.0%)
  - Orphan nodes: 0
  - Cross-DB linkage: 10/10 sampled UUIDs resolve
  - Duplicate triples: 3 patterns (Stent→Restenosis, POBA→Restenosis, Colonoscopy→CRC — minor, from overlapping CPG content)
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
| Aspirin | REDUCES_RISK_OF | Colorectal Carcinoma | "It was not significant in primary prevention but significant in secondary prevention with a reduction..." |
| Heparin | REDUCES_RISK_OF [MAJOR] | Deep Vein Thrombosis And/Or Pulmonary Embolism | "Heparin significantly prevented deep vein thrombosis and/or pulmonary embolism (OR=0.32, 95% CI 0.02..." |
| Computed Tomography | ASSESSED_BY | Colorectal Carcinoma | "Computed tomography (CT) is routinely used and remains the mainstay technique for primary staging an..." |
| Computed Tomography | INDICATED_FOR | Identification Of Lesion Location And Size | "It is used for identification of the location and size of the lesion, demonstration of local extensi..." |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| — | — | — | No issues detected |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
