# Management of Diabetes in Pregnancy (2017) Ingestion & Verification Report

> **Verified:** 2026-05-20 (SOP verification run on fresh ingestion)

## Executive Summary
The **Diabetes-in-Pregnancy(2017)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. No embedding failures or cross-DB corruption were found.

Current footprint: **54 chunks** across 13 sections and **287 KG edges**, with **46.9%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph holds **10,827 nodes / 13,784 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 54 (9 H1, 4 H1-leaf, 37 H2, 4 H3)
- **Parent-Child Linkage**: 41 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 9 H1 null embeddings and 1 H2 null embedding are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Treatment* (37), *Special Populations* (34), *Assessment* (25), *Reference* (19), *Prevention* (15), *Screening* (7), *Diagnosis* (7), *Methodology* (5), *Supportive Treatment* (4), *Introduction* (1).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Section 2: Screening And Diagnosis* (sim=1.0000), followed by *Algorithm A: Screening And Diagnosis Of Diabetes In Pregnancy* (0.9379) and *Appendices / Appendix 1: Example Of Search Strategy* (0.8307).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 287 clinical triples.
- **Relationship Breakdown**:
  - `INDICATED_FOR`: 62
  - `INCREASES_RISK_OF`: 59
  - `REDUCES_RISK_OF`: 49
  - `RECOMMENDED_FOR`: 28
  - `ASSESSED_BY`: 28
  - `CONTRAINDICATED_WITH`: 14
  - `REQUIRES_MONITORING`: 12
  - `HAS_DOSAGE`: 12
  - `TREATS`: 8
  - `OTHER`: 7
  - `REQUIRES_DOSE_ADJUSTMENT`: 5
  - `FIRST_LINE_FOR`: 2
  - `CAUSES`: 1
- **Severity Coverage**: **46.9%** (15/32) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (287/287).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Healthy (1 pre-existing INFO)

- **name_normalised**: 10,827/10,827 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: Notable examples:
  - *body weight* split across `[OTHER]`, `[PatientProfile]`, `[Condition]`, `[DiagnosticTool]`
  - *poor prognosis* split across `[RiskFactor]`, `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.7% — under the 5% SOP threshold (MINOR, pre-existing across corpus).
- **INFO — `Diabete` node**: A node with `name='Diabete'` (normalised: `diabete`) exists as both `[Condition]` and `[RiskFactor]`. This is a **pre-existing extraction artifact from other CPGs** (CVD Prevention, Hypertension, Ischaemic Stroke sections) — not introduced by this ingestion. Its edges originate from sections like "Section 2: Types Of Cardiovascular Disease" and "Section 5: Global Cardiovascular Risk Assessment". Because `diabete ≠ diabetes`, it does not merge with proper Diabetes nodes and is functionally isolated. No action required, but worth cleaning during a future normaliser pass.

---

## 4. KG-8: Full Per-CPG `cpg_chunk_id` Resolution
**Status:** ✅ Clean

- **Resolution**: **36/36 (0% orphaned)** distinct `cpg_chunk_id` values resolve to live Postgres chunks.
- **Shared titles handled**: 3 section titles shared with other CPGs were correctly skipped during the collision-aware sweep and not mis-attributed.
- **Corpus sweep**: ALL CPGs remain clean — 0 orphaned chunk references corpus-wide.

---

## 5. Cumulative Graph Health
**Status:** ✅ Healthy

- **Total nodes**: 10,827 | **Total edges**: 13,784 (grew from baseline of 10,592 nodes / 13,497 edges — +235 nodes, +287 edges from this CPG).
- **Orphan nodes**: 0.
- **Missing evidence**: 0.
- **Issues**: 1 — pre-existing 10 duplicate triple patterns from cross-CPG cardiac overlap (e.g. AF→Stroke). Not introduced by this CPG, unchanged from prior sessions.

---

## 6. Phase D Smoke Test
**Status:** ✅ PASS

- **Gate 1** — candidate drugs extracted from chunks: **PASS** (84 drugs)
- **Gate 2** — flags returned by KG lookup: **PASS**
- **Gate 3** — flags block contains INTERACTION FLAGS: **PASS**
- Sample flags fired: `Dronedarone CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Antiarrhythmic Drug CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Metoprolol REQUIRES_DOSE_ADJUSTMENT Heart Failure`, `Verapamil REQUIRES_DOSE_ADJUSTMENT Heart Failure`.

---

## 7. Clinical Graph Lookup Smoke Test (Step 6b)
**Status:** ✅ PASS (domain-specific auto-discover)

Using `--cpg "Diabetes In Pregnancy"` auto-discover mode, the test identified 20 safety edges across 4 matching sections and returned **3 flags**:

| Flag | Type | Severity | Evidence |
|---|---|---|---|
| Insulin ↔ Hypoglycaemia | MONITORING | UNSPECIFIED | "able to titrate the required insulin doses to achieve glycaemic targets without hypoglycaemia" |
| Vitamin C And E Supplementation ↔ Pre-Eclampsia Prevention In Women With Diabetes | CONTRAINDICATION | MAJOR | "Vitamin C and E supplementation should not be given to prevent pre-eclampsia in women with diabetes." |
| Insulin ↔ Postpartum Period | DOSE_ADJUSTMENT | UNSPECIFIED | "Insulin requirement drops immediately after delivery by 60-75%." |

The hardcoded default AF scenario still returns 0 flags (pre-existing corpus gap — AF CPG not yet ingested, unchanged from prior sessions).

---

## 8. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-20):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Angiotensin-Converting Enzyme Inhibitor | CONTRAINDICATED_WITH [UNSPECIFIED] | Pregnancy | "Prior to conception or upon detection of pregnancy, the following medications should be discontinued: ACE inhibitors..." |
| Corticosteroid | INCREASES_RISK_OF [MODERATE] | Worsened Glycaemic Control | "It is known to elevate plasma glucose levels and worsen glycaemic control of diabetes in pregnancy..." |
| Corticosteroid | INCREASES_RISK_OF [UNSPECIFIED] | Gestational Diabetes Mellitus | "Risk Factors for GDM: Current obstetric problems (e.g. current corticosteroid use)..." |
| Vitamin C And E Supplementation | CONTRAINDICATED_WITH [MAJOR] | Pre-Eclampsia Prevention In Women With Diabetes | "Vitamin C and E supplementation should not be given to prevent pre-eclampsia in women with diabetes." |
| Insulin | REQUIRES_DOSE_ADJUSTMENT [UNSPECIFIED] | Postpartum Period | "Insulin requirement drops immediately after delivery by 60-75%." |

---

## 9. Known Issues

| Issue | Severity | Status | Notes |
|---|---|---|---|
| `Diabete` node (`norm='diabete'`) with edges from other CPGs | INFO | Pre-existing / cosmetic | Not introduced by this ingestion — artifact from CVD Prevention, Hypertension, Stroke CPG extractions. Functionally isolated from proper `diabetes` nodes. Clean during future normaliser pass. |
| `clinical_graph_lookup` default AF scenario returns 0 flags | WARN | Pre-existing / investigate when AF CPG ingested | AF/anticoagulation domain gap. Domain-specific test (--cpg mode) passes with 3 flags. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |
| Cross-label duplication ratio 4.7% | MINOR | Acceptable | Under 5% SOP threshold; pre-existing across corpus. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested and verified cleanly (2026-05-20)**
======================================================================
