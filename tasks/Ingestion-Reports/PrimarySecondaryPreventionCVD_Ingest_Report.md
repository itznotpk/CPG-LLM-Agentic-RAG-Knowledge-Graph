# Primary & Secondary Prevention of CVD (2017) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-18 (fresh ingestion followed by full SOP verification run)

## Executive Summary
The **Primary-Secondary-Prevention-of-CVD(2017)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. All 15 sections landed cleanly: every true-leaf chunk has an embedding, all KG edges carry Phase A metadata, and no bad same-label duplicate nodes were introduced.

Current footprint: **96 chunks** across 15 sections and **618 KG edges**, with **69.1%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **6,418 nodes / 7,343 edges** across all ingested CPGs. Notably, this CPG contributes the highest `REDUCES_RISK_OF` edge count of any ingested CPG to date (110 edges), reflecting the strong preventive intervention evidence base.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 96 (12 H1, 3 H1-leaf, 58 H2, 23 H3)
- **Parent-Child Linkage**: 81 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 12 h1 and 5 h2 null embeddings are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Treatment* (38), *Reference* (30), *Prevention* (27), *Assessment* (16), *Supportive Treatment* (8), *Special Populations* (8), *Epidemiology* (7), *Diagnosis* (5), *Introduction* (4), *Screening* (3).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *3.1: Primary Prevention* (sim=1.0000), followed by *Section 9: Management of Individual Risk Factors* (0.8614) and *1.1: Epidemiology of Cardiovascular Disease* (0.8044).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 618 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 227
  - `REDUCES_RISK_OF`: 110
  - `INDICATED_FOR`: 84
  - `RECOMMENDED_FOR`: 41
  - `ASSESSED_BY`: 39
  - `TREATS`: 22
  - `CONTRAINDICATED_WITH`: 19
  - `OTHER`: 16
  - `CAUSES`: 15
  - `HAS_DOSAGE`: 13
  - `FIRST_LINE_FOR`: 9
  - `REQUIRES_MONITORING`: 9
  - `INTERACTS_WITH`: 7
  - `REQUIRES_DOSE_ADJUSTMENT`: 5
  - `SECOND_LINE_FOR`: 2
- **Severity Coverage**: **69.1%** (38/55) of safety-critical edges have severity markers — well above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (618/618).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 6,418/6,418 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 477 nodes — expected behaviour. Examples:
  - *hypotension* split across `[AdverseEvent]`, `[Condition]`, `[RiskFactor]`
  - *sedation* split across `[Drug]`, `[Procedure]`, `[AdverseEvent]`
  - *hypertension* split across `[Condition]`, `[AdverseEvent]`, `[RiskFactor]`
- **Overall duplication ratio**: 3.8% — under the 5% SOP threshold (MINOR, unchanged from pre-ingestion baseline).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 6,418 | Total edges: 7,343 (+440 net nodes, +618 edges vs. pre-ingestion baseline)
  - 0 missing evidence, 0 orphan nodes, 10/10 PG cross-check pass.
  - "1 issue" = same 10 pre-existing duplicate triple patterns from cross-CPG cardiac overlap — unchanged, not introduced by this ingestion.

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-18):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Hypertension | INCREASES_RISK_OF [MAJOR] | Cardiovascular Disease | "Based on the prevalence of CV risk factors in our local population, the committee advocates screening…" |
| Hypertension | INDICATED_FOR | Risk Stratification | "Once hypertension is diagnosed, the patient should be risk stratified (Table 14: Risk Stratification…" |
| Hypertension | INDICATED_FOR | Non-Pharmacological Measure | "All patients should be counselled on non-pharmacological measures as outlined in Section 9.1.1…" |
| Hypertension | INCREASES_RISK_OF | Prediabetes | "Hypertension (BP ≥140/90 mmHg or on therapy for hypertension)…" |
| Age | INCREASES_RISK_OF | CVD | "Table 1A and 2A: Age (yr) is a component of the Framingham Risk Score for Assessment of CVD Risk…" |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| `clinical_graph_lookup` smoke test (Warfarin/Digoxin, AF/Warfarin) returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — scenarios are AF/anticoagulation domain. Carried forward from prior verification sessions. |
| 10 duplicate triple patterns graph-wide | INFO | Acceptable | Pre-existing cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
