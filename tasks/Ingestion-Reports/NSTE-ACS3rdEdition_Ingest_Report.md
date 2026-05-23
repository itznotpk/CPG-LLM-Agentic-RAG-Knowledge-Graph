# Management of Non-ST Elevation Myocardial Infarction (NSTE-ACS) (3rd Edition) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-19 (fresh ingestion followed by full SOP verification run)

## Executive Summary
The **NSTE-ACS(3rd Edition)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. All 12 sections landed cleanly: every true-leaf chunk has an embedding, all KG edges carry Phase A metadata, and no bad same-label duplicate nodes were introduced.

Current footprint: **71 chunks** across 12 sections and **746 KG edges**, with **50.7%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **8,548 nodes / 10,027 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 71 (9 H1, 3 H1-leaf, 44 H2, 15 H3)
- **Parent-Child Linkage**: 59 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 9 h1 and 4 h2 null embeddings are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Treatment* (42), *Diagnosis* (33), *Assessment* (32), *Classification* (28), *Reference* (22), *Prevention* (10), *Supportive Treatment* (6), *Special Populations* (4), *Epidemiology* (1), *Introduction* (1).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *6.3: Medical Emergency Coordination Centre (MECC) And Ambulance* (sim=0.6851), followed by *Section 7: In-Hospital Management / 7.1: Emergency Department* (0.6826) and *9.2: Investigations During Follow Up* (0.6812).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 746 clinical triples.
- **Relationship Breakdown**:
  - `INDICATED_FOR`: 140
  - `INCREASES_RISK_OF`: 124
  - `RECOMMENDED_FOR`: 87
  - `ASSESSED_BY`: 81
  - `HAS_DOSAGE`: 79
  - `CONTRAINDICATED_WITH`: 46
  - `OTHER`: 41
  - `CAUSES`: 34
  - `REQUIRES_DOSE_ADJUSTMENT`: 31
  - `REDUCES_RISK_OF`: 28
  - `REQUIRES_MONITORING`: 27
  - `FIRST_LINE_FOR`: 9
  - `INTERACTS_WITH`: 8
  - `SECOND_LINE_FOR`: 7
  - `TREATS`: 4
- **Severity Coverage**: **50.7%** (74/146) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (746/746).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 8,548/8,548 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 654 nodes — expected behaviour. Notable examples:
  - *blood pressure* split across `[DiagnosticTool]`, `[Condition]`, `[RiskFactor]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
  - *renal function* split across `[DiagnosticTool]`, `[Condition]`, `[Procedure]`, `[RiskFactor]`
- **Overall duplication ratio**: 3.9% — under the 5% SOP threshold (MINOR, unchanged).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 8,548 | Total edges: 10,027 (vs. pre-ingestion baseline)
  - 0 missing evidence, 0 orphan nodes, 10/10 PG cross-check pass.
  - "1 issue" = same pre-existing duplicate triple patterns from cross-CPG cardiac overlap — unchanged, not introduced by this ingestion.

---

## 5. Phase D & Clinical Lookup Smoke Tests (SOP Steps 6 & 6b)
**Status:** ✅ Phase D PASS | ⚠ Clinical lookup pre-existing WARN

- **Phase D (test_phase_d_af.py)**:
  - Gate 1 — candidate drugs extracted from chunks: **PASS** (86 drugs)
  - Gate 2 — flags returned by KG lookup: **PASS**
  - Gate 3 — flags block contains INTERACTION FLAGS: **PASS**
  - Sample flags: `Dronedarone CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Diltiazem REQUIRES_DOSE_ADJUSTMENT Heart Failure`, `Metoprolol REQUIRES_DOSE_ADJUSTMENT Heart Failure`
- **Clinical lookup smoke test (test_graph_clinical.py)**:
  - Returns 0 flags for Warfarin/Digoxin and AF/Warfarin scenarios — pre-existing WARN, not caused by this CPG (AF/anticoagulation domain gap carried forward from prior sessions).

---

## 6. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-19):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Renal Insufficiency | OTHER | More Prevalent In Older Persons With NSTE-ACS | "These older persons with NSTE-ACS are more likely to be women, have lower body mass indices, higher…" |
| Diltiazem | HAS_DOSAGE | 30–90mg Tds (Immediate Release) | "Immediate release, 30–90mg tds…" |
| Diltiazem | HAS_DOSAGE | 100–200mg Od (Slow Release) | "Slow release, 100–200mg od…" |
| Diltiazem | REQUIRES_DOSE_ADJUSTMENT | Hepatic Impairment | "Hepatic Impairment: Used with caution/consider dose reduction…" |
| Diltiazem | INDICATED_FOR | Alternative To Beta-Blockers In Intolerant Patient | "[Grade IIa, Level B] A non-dihydropyridine CCB (e.g. verapamil or diltiazem) may be used as an alternative…" |

---

## 7. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| `clinical_graph_lookup` smoke test returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — AF/anticoagulation domain gap. Carried forward from prior verification sessions. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
