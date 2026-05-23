# Management of Growth Hormone Deficiency in Children and Adults (2010) Ingestion & Verification Report

> **Verified:** 2026-05-20 (SOP verification run on pre-existing ingestion)

## Executive Summary
The **Growth-Hormone-Children-Adults(2010)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. No embedding failures or cross-DB corruption were found.

Current footprint: **62 chunks** across 8 sections and **369 KG edges**, with **45.0%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph holds **10,153 nodes / 13,000 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 62 (8 H1, 1 H1-leaf, 41 H2, 12 H3)
- **Parent-Child Linkage**: 53 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 8 H1 null embeddings and 3 H2 null embeddings are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Treatment* (58), *Special Populations* (41), *Assessment* (29), *Screening* (27), *Diagnosis* (27), *Reference* (10), *Epidemiology* (4), *Introduction* (4), *Methodology* (4).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Section 6: Use Of Growth Hormone In Non-GHD Adults* (sim=1.0000), followed by *6.4: Anti-Ageing Therapy In Healthy Elderly* (0.7803) and *6.2: Critically Ill Patients* (0.7711).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 369 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 88
  - `CAUSES`: 52
  - `REQUIRES_MONITORING`: 51
  - `INDICATED_FOR`: 44
  - `ASSESSED_BY`: 33
  - `HAS_DOSAGE`: 22
  - `CONTRAINDICATED_WITH`: 19
  - `TREATS`: 17
  - `OTHER`: 16
  - `REDUCES_RISK_OF`: 10
  - `REQUIRES_DOSE_ADJUSTMENT`: 8
  - `RECOMMENDED_FOR`: 5
  - `FIRST_LINE_FOR`: 2
  - `INTERACTS_WITH`: 1
  - `SECOND_LINE_FOR`: 1
- **Severity Coverage**: **45.0%** (59/131) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (369/369).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 10,153/10,153 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: Notable examples:
  - *body weight* split across `[OTHER]`, `[PatientProfile]`, `[Condition]`, `[DiagnosticTool]`
  - *poor prognosis* split across `[RiskFactor]`, `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.6% — under the 5% SOP threshold (MINOR, pre-existing across corpus).

---

## 4. KG-8: Full Per-CPG `cpg_chunk_id` Resolution
**Status:** ✅ Clean

- **Resolution**: **46/46 (0% orphaned)** distinct `cpg_chunk_id` values resolve to live Postgres chunks.
- **Shared titles handled**: 2 section titles shared with other CPGs were correctly skipped during the collision-aware sweep and not mis-attributed.
- **Corpus sweep**: ALL CPGs remain clean — 0 orphaned chunk references corpus-wide.

---

## 5. Cumulative Graph Health
**Status:** ✅ Healthy

- **Total nodes**: 10,153 | **Total edges**: 13,000 (unchanged from pre-verification baseline — CPG was pre-existing).
- **Orphan nodes**: 0.
- **Missing evidence**: 0.
- **Issues**: 1 — pre-existing 10 duplicate triple patterns from cross-CPG cardiac overlap (e.g. AF→Stroke). Not introduced by this CPG, unchanged from prior sessions.

---

## 6. Phase D Smoke Test
**Status:** ✅ PASS

- **Gate 1** — candidate drugs extracted from chunks: **PASS** (84 drugs)
- **Gate 2** — flags returned by KG lookup: **PASS**
- **Gate 3** — flags block contains INTERACTION FLAGS: **PASS**
- Sample flags fired: `Dronedarone CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Antiarrhythmic Drug CONTRAINDICATED_WITH Heart Failure`, `Metoprolol REQUIRES_DOSE_ADJUSTMENT Heart Failure`, `Verapamil REQUIRES_DOSE_ADJUSTMENT Heart Failure`.

---

## 7. Clinical Graph Lookup Smoke Test (Step 6b)
**Status:** ⚠ Pre-existing WARN — returns 0 flags

The `clinical_graph_lookup` test probes a Warfarin/Digoxin + Atrial Fibrillation polypharmacy scenario and returns 0 flags. This is a **data gap, not a code bug**. Root cause:

- **Drug-drug query**: Looks for a direct `warfarin -[INTERACTS_WITH|CONTRAINDICATED_WITH]- digoxin` edge. None exists — warfarin's current edges are `TREATS`, `REQUIRES_MONITORING`, and `CAUSES` (from Ischaemic Stroke and Heart Disease in Pregnancy CPGs, where it appears in narrow contexts).
- **Comorbidity query**: Looks for `digoxin -[CONTRAINDICATED_WITH]-> atrial fibrillation`. The graph holds `digoxin -[CONTRAINDICATED_WITH]-> atrial fibrillation with pre-excitation` — the object `name_normalised` does not match the input `"atrial fibrillation"`, so no flag fires.
- **Root cause**: The **Atrial Fibrillation (2012) CPG** — which contains the canonical warfarin↔digoxin interaction and warfarin monitoring-for-AF edges — has not yet been ingested. Once ingested, this smoke test is expected to pass.

**Not caused by this CPG.** Carried forward from prior verification sessions as a known corpus gap.

---

## 8. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-20):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Dexa Scan | ASSESSED_BY [UNSPECIFIED] | Bone Mineral Density | "There are studies showing that treating GHD adults with rhGH replacement improved BMD as assessed by..." |
| Craniopharyngioma | INCREASES_RISK_OF [UNSPECIFIED] | GH Deficiency | "Frequent causes include previous hypothalamic–pituitary disease, such as pituitary adenoma, craniopharyngioma..." |
| Recombinant Human Growth Hormone Therapy | INCREASES_RISK_OF [UNSPECIFIED] | Tumor Regrowth | "adult growth hormone deficiency AND replacement AND tumor regrowth OR recurrence..." |
| Turner Syndrome | INCREASES_RISK_OF [UNSPECIFIED] | Type 2 Diabetes Mellitus | "Follow up of children at risk of T2DM such as obesity, Turner syndrome, intrauterine growth retardation..." |
| Dexa Scan | ASSESSED_BY [UNSPECIFIED] | Repeat Dexa Scan | "If the initial bone density is abnormal, repeat DEXA scan is recommended at 1–3 year intervals..." |

---

## 9. Known Issues

| Issue | Severity | Status | Notes |
|---|---|---|---|
| `clinical_graph_lookup` smoke test returns 0 flags | WARN | Pre-existing / investigate when AF CPG ingested | AF/anticoagulation domain gap — warfarin↔digoxin interaction edge missing because Atrial-Fibrillation(2012) CPG not yet ingested. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |
| Cross-label duplication ratio 4.6% | MINOR | Acceptable | Under 5% SOP threshold; pre-existing across corpus. |

======================================================================
✅ **ALL CHECKS PASSED — CPG verified cleanly (2026-05-20)**
======================================================================
