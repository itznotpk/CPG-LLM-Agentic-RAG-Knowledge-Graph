# Pulmonary Arterial Hypertension (2011) Ingestion & Verification Report

## Executive Summary
The ingestion for the **Pulmonary-Arterial-Hypertension(2011)** Clinical Practice Guideline (CPG) has been successfully completed and verified with **all checks passed**.

Overall, **74 chunks** and **555 knowledge graph edges** were generated across 21 clinical sections covering adult PAH (classification, pathogenesis, screening, diagnosis, treatment), paediatric PAH, and PAH in congenital heart diseases including Eisenmenger syndrome. Severity coverage reached **54.3%** on safety-critical edges, with rich dosage data extraction (49 `HAS_DOSAGE` relationships).

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Complete Success

- **Total Chunks**: 74 (12 H1 parents, 9 H1_leaf, 53 H2)
- **Parent-Child Linkage**: 53 child chunks correctly linked to parents, with **0 orphans**.
- **Embedding Integrity**: All true leaf chunks embedded successfully. 12 null H1 chunks are parent-level by design.
- **Metadata Coverage**: *Treatment* (45), *Supportive Treatment* (27), *Assessment* (27), *Special Populations* (21), *Diagnosis* (18), *Reference* (15), *Pathophysiology* (4), *Introduction* (3), *Epidemiology* (3), *Prevention* (3).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *6.2: Detection Of PHT* with sim=0.7589.

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Complete Success

- **Total Edges Extracted**: 555 clinical triples.
- **Top Relationships**:
  - `INDICATED_FOR`: 110
  - `INCREASES_RISK_OF`: 108
  - `ASSESSED_BY`: 74
  - `HAS_DOSAGE`: 49
  - `RECOMMENDED_FOR`: 49
  - `CAUSES`: 49
  - `CONTRAINDICATED_WITH`: 29
  - `TREATS`: 20
  - `REQUIRES_MONITORING`: 17
  - `FIRST_LINE_FOR`: 11
  - `REDUCES_RISK_OF`: 10
  - `INTERACTS_WITH`: 10
  - `SECOND_LINE_FOR`: 10
- **Severity Coverage**: **54.3%** of safety-critical edges have severity markers — well above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (555/555).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 4,138/4,138 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected.
- **Cross-label duplicates (Safe)**: 282 nodes — expected behaviour (e.g., "hypertension" as `[Condition]`, `[AdverseEvent]`, and `[RiskFactor]`).

---

## 4. Cumulative Graph Health (SOP Steps 5, 5b, 6b)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 4,138 | Total edges: 4,625
  - Missing evidence: 0 (0.0%)
  - Orphan nodes: 0
  - Cross-DB linkage: 10/10 sampled UUIDs resolve
  - Duplicate triples: 8 patterns (minor, from overlapping content across CPGs)
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
| Diltiazem | INDICATED_FOR | Acute PAH Responder | "WHO Class I–IV → Amlodipine, diltiazem, nifedipine (B)..." |
| Diltiazem | HAS_DOSAGE | 30 mg tds up to max 900 mg/day | "Adults: Start with 30 mg tds up to maximum 900 mg/day..." |
| TOE | ASSESSED_BY | Atrial Septal Defect | "Transoesophageal echocardiography [may be] useful to detect presence of atrial septal defect..." |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| — | — | — | No issues detected |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
