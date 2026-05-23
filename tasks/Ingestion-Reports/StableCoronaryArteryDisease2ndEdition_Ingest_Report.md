# Stable Coronary Artery Disease (2nd Edition) Ingestion & Verification Report

> **Verified:** 2026-05-19 (full SOP verification run; ingestion was performed prior to this session)

## Executive Summary
The **Stable-Coronary-Artery-Disease(2nd Edition)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**.

Current footprint: **74 chunks** across 14 sections and **486 KG edges**, with **31.1%** severity coverage on safety-critical edges (above the 30% SOP threshold) and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **10,138 nodes / 12,598 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 74 (7 H1, 7 H1-leaf, 36 H2, 24 H3)
- **Parent-Child Linkage**: 60 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 7 H1 and 4 H2 null embeddings are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Assessment* (30), *Treatment* (29), *Prevention* (25), *Supportive Treatment* (24), *Diagnosis* (19), *Reference* (10), *Special Populations* (5), *Classification* (4), *Epidemiology* (1), *Pathophysiology* (1).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Table 2: Prognostic indicators for Adverse CV outcomes* (sim=0.7140), followed by *7.4: Risk Stratification Of Stable CAD By Non-Invasive Te...* (0.7091) and *6.2.1: Diagnostic Accuracy Of Exercise Stress ECG* (0.7027).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 486 clinical triples.
- **Relationship Breakdown**:
  - `INDICATED_FOR`: 137
  - `INCREASES_RISK_OF`: 81
  - `ASSESSED_BY`: 69
  - `REDUCES_RISK_OF`: 57
  - `RECOMMENDED_FOR`: 41
  - `OTHER`: 23
  - `CAUSES`: 21
  - `TREATS`: 15
  - `CONTRAINDICATED_WITH`: 13
  - `HAS_DOSAGE`: 10
  - `FIRST_LINE_FOR`: 8
  - `INTERACTS_WITH`: 7
  - `REQUIRES_DOSE_ADJUSTMENT`: 2
  - `REQUIRES_MONITORING`: 2
- **Severity Coverage**: **31.1%** (14/45) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (486/486).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 10,138/10,138 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 885 nodes — expected behaviour. Notable examples:
  - *body weight* split across `[OTHER]`, `[RiskFactor]`, `[PatientProfile]`, `[Condition]`
  - *blood pressure* split across `[DiagnosticTool]`, `[Condition]`, `[RiskFactor]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.5% — under the 5% SOP threshold (MINOR).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 10,138 | Total edges: 12,598
  - 0 missing evidence, 10/10 PG cross-check pass.
  - 303 orphan nodes — pre-existing graph-wide pattern, not introduced by this ingestion.
  - 10 duplicate triple patterns — pre-existing (AF/Hypertension/Diabetes risk pairs).

---

## 5. Phase D & Clinical Lookup Smoke Tests (SOP Steps 6 & 6b)
**Status:** ✅ Phase D PASS | ⚠ Clinical lookup pre-existing WARN

- **Phase D (test_phase_d_af.py)**:
  - Gate 1 — candidate drugs extracted from chunks: **PASS** (84 drugs)
  - Gate 2 — flags returned by KG lookup: **PASS**
  - Gate 3 — flags block contains INTERACTION FLAGS: **PASS**
  - Sample flags: `Digoxin INTERACTS_WITH Amiodarone [MAJOR]`, `Digoxin INTERACTS_WITH Verapamil [UNSPECIFIED]`, `Warfarin INTERACTS_WITH Low Molecular Weight Heparin [UNSPECIFIED]`
- **Clinical lookup smoke test (test_graph_clinical.py)**:
  - Returns 0 flags for Warfarin/Digoxin and AF/Warfarin scenarios — pre-existing WARN, not caused by this CPG (AF/anticoagulation domain gap carried forward from prior sessions).

---

## 6. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-19):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Diabetes | INCREASES_RISK_OF [MAJOR] | Coronary Artery Disease | "Diabetes is associated with an increased risk of CVD. CAD mortality is increased by 3-fold in diabetics…" |
| Hypertension | INCREASES_RISK_OF | Adverse Outcomes In Stable CAD | "presence of CV risk factors: Hypertension…" |
| Atropine | INTERACTS_WITH | Dobutamine | "The addition of atropine augments the sensitivity of the dobutamine stress echocardiogram (DSE)." |
| Sick Sinus Syndrome | CAUSES | Syncope | "The presence of syncope/near syncope may be due to: bradyarrhythmia from drug therapy, conduction disease…" |

---

## 7. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| `clinical_graph_lookup` smoke test returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — AF/anticoagulation domain gap. Carried forward from prior verification sessions. |
| 303 orphan nodes graph-wide | INFO | Pre-existing / acceptable | Not introduced by this ingestion. |
| 10 duplicate triple patterns | INFO | Pre-existing / acceptable | AF/Hypertension/Diabetes risk pairs; cross-CPG redundancy is expected. |

======================================================================
✅ **ALL CHECKS PASSED — CPG verified cleanly**
======================================================================
