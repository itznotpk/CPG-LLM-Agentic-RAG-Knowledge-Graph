# Management of Acute ST Segment Elevation Myocardial Infarction (STEMI) – 4th Edition Ingestion & Verification Report

> **Ingested & verified:** 2026-05-18 (fresh ingestion followed by full SOP verification run)

## Executive Summary
The **STEMI(4th Edition)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. All 20 sections landed cleanly: every true-leaf chunk has an embedding, all KG edges carry Phase A metadata, and no bad same-label duplicate nodes were introduced.

Current footprint: **100 chunks** (STEMI-only, excl. NSTEMI co-match) across 20 sections and **1,026 KG edges**, with **68.8%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **7,432 nodes / 8,519 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 162 combined (STEMI + NSTEMI co-match — 25 H1, 8 H1-leaf, 113 H2, 16 H3)
- **Parent-Child Linkage**: 129 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 25 h1 and 2 h2 null embeddings are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Treatment* (73), *Diagnosis* (52), *Reference* (46), *Prevention* (31), *Supportive Treatment* (28), *Assessment* (20), *Special Populations* (10), *Pathophysiology* (10), *Classification* (9), *Methodology* (4).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Figure 1: Non-Invasive Investigation Of Low Risk Patients* (sim=1.0000), followed by *Flowchart 1: Risk Stratification Of UA/NSTEMI* (0.8921) and *10.2: Follow-Up Investigations* (0.8686).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 1,026 clinical triples.
- **Relationship Breakdown**:
  - `INDICATED_FOR`: 223
  - `ASSESSED_BY`: 122
  - `INCREASES_RISK_OF`: 115
  - `RECOMMENDED_FOR`: 113
  - `HAS_DOSAGE`: 111
  - `CONTRAINDICATED_WITH`: 96
  - `REDUCES_RISK_OF`: 49
  - `OTHER`: 47
  - `TREATS`: 39
  - `REQUIRES_MONITORING`: 27
  - `REQUIRES_DOSE_ADJUSTMENT`: 26
  - `CAUSES`: 23
  - `INTERACTS_WITH`: 17
  - `FIRST_LINE_FOR`: 14
  - `SECOND_LINE_FOR`: 4
- **Severity Coverage**: **68.8%** (130/189) of safety-critical edges have severity markers — well above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (1026/1026).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 7,432/7,432 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 570 nodes — expected behaviour. Notable examples:
  - *renal function* split across `[DiagnosticTool]`, `[Condition]`, `[Procedure]`, `[RiskFactor]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
  - *prematurity* split across `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
- **Overall duplication ratio**: 3.9% — under the 5% SOP threshold (MINOR).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 7,432 | Total edges: 8,519 (+254 net nodes, +1,026 edges vs. pre-ingestion baseline)
  - 0 missing evidence, 0 orphan nodes, 10/10 PG cross-check pass.
  - "1 issue" = same pre-existing duplicate triple patterns from cross-CPG cardiac overlap — unchanged, not introduced by this ingestion.

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-18):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Atropine | INDICATED_FOR [MAJOR] | Symptomatic Bradycardia | "Atropine 0.5 to 1 mg IV (may repeat to a maximum of 3 mg)…" |
| Atropine | RECOMMENDED_FOR | Atrioventricular Block | "Atropine may be given in the interim (maximum 3 mg)…" |
| Atropine | HAS_DOSAGE | 3 Mg Maximum | "Atropine may be given in the interim (maximum 3 mg)…" |
| Diltiazem | HAS_DOSAGE | Immediate Release 30–90 Mg Tds | "Diltiazem — Immediate release 30-90 mg tds…" |
| Diltiazem | HAS_DOSAGE | Slow Release 100–200 Mg Od | "Diltiazem — Slow release 100-200 mg od…" |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| `clinical_graph_lookup` smoke test (Warfarin/Digoxin, AF/Warfarin) returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — scenarios are AF/anticoagulation domain. Carried forward from prior verification sessions. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
