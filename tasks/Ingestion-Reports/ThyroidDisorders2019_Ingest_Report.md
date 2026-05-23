# Management of Thyroid Disorders (2019) Ingestion & Verification Report

> **Verified:** 2026-05-22 (SOP verification run on fresh ingestion)

## Executive Summary
The **Thyroid-Disorders(2019)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. No embedding failures or cross-DB corruption were found.

This is the **largest CPG ingested to date**, with **185 chunks** across 12 sections and **1,682 KG edges** — more than 4× the edge count of the previous largest (T1DM at 497). The graph now holds **12,106 nodes / 15,810 edges** across all ingested CPGs. Severity coverage of **43.2%** and a rare `CROSS_REACTS_WITH` edge are notable clinical quality markers.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 185 (12 H1, 0 H1-leaf, 45 H2, 128 H3)
- **Parent-Child Linkage**: 173 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 12 H1 null embeddings and 13 H2 null embeddings are expected sub-split parents — no leaf-level FAILs. The deep H3 structure (128 chunks) reflects the CPG's fine-grained clinical Q&A format.
- **Metadata Coverage**: *Treatment* (157), *Diagnosis* (81), *Assessment* (81), *Screening* (61), *Special Populations* (61), *Reference* (26), *Methodology* (11), *Epidemiology* (2), *Introduction* (2).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *3.1.6: What Medications May Alter A Patient's Levothyroxine Requirements* (sim=1.0000), followed by *3.1.8: Best Approach To Initiating And Adjusting Levothyroxine* (0.8229) and *3.1.12: How Should Levothyroxine Therapy Be Managed In...* (0.7968).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy — largest extraction to date

- **Total Edges Extracted**: 1,682 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 367
  - `CAUSES`: 255
  - `INDICATED_FOR`: 202
  - `ASSESSED_BY`: 170
  - `TREATS`: 152
  - `RECOMMENDED_FOR`: 123
  - `REQUIRES_MONITORING`: 90
  - `HAS_DOSAGE`: 84
  - `REQUIRES_DOSE_ADJUSTMENT`: 47
  - `CONTRAINDICATED_WITH`: 44
  - `INTERACTS_WITH`: 41
  - `OTHER`: 35
  - `REDUCES_RISK_OF`: 34
  - `FIRST_LINE_FOR`: 27
  - `SECOND_LINE_FOR`: 10
  - `CROSS_REACTS_WITH`: 1
- **Severity Coverage**: **43.2%** (206/477) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (1682/1682).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.
- **Notable**: First CPG to contribute a `CROSS_REACTS_WITH` edge — a high-value allergy cross-reactivity triple relevant to drug safety queries.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 12,106/12,106 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced despite the large volume of new entities.
- **Cross-label duplicates (Safe)**: 1,086 nodes — expected corpus growth. Notable examples:
  - *body weight* split across `[OTHER]`, `[PatientProfile]`, `[Condition]`, `[DiagnosticTool]`, `[RiskFactor]`
  - *poor prognosis* split across `[RiskFactor]`, `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.7% — under the 5% SOP threshold (MINOR, pre-existing across corpus).

---

## 4. KG-8: Full Per-CPG `cpg_chunk_id` Resolution
**Status:** ✅ Clean

- **Resolution**: **148/148 (0% orphaned)** distinct `cpg_chunk_id` values resolve to live Postgres chunks.
- **Shared titles handled**: 1 section title shared with other CPGs was correctly skipped during the collision-aware sweep.
- **Corpus sweep**: ALL CPGs remain clean — 0 orphaned chunk references corpus-wide.

---

## 5. Cumulative Graph Health
**Status:** ✅ Healthy

- **Total nodes**: 12,106 | **Total edges**: 15,810 (grew from baseline of 11,015 nodes / 14,128 edges — +1,091 nodes, +1,682 edges from this CPG).
- **Orphan nodes**: 0.
- **Missing evidence**: 0.
- **Issues**: 1 — pre-existing 10 duplicate triple patterns from cross-CPG cardiac overlap. Not introduced by this CPG, unchanged from prior sessions.

---

## 6. Phase D Smoke Test
**Status:** ✅ PASS

- **Gate 1** — candidate drugs extracted from chunks: **PASS** (84 drugs)
- **Gate 2** — flags returned by KG lookup: **PASS**
- **Gate 3** — flags block contains INTERACTION FLAGS: **PASS**
- Sample flags fired: `Dronedarone CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Antiarrhythmic Drug CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Metoprolol REQUIRES_DOSE_ADJUSTMENT Heart Failure`, `Diltiazem REQUIRES_DOSE_ADJUSTMENT Heart Failure`.

---

## 7. Clinical Graph Lookup Smoke Test (Step 6b)
**Status:** ✅ PASS (domain-specific — `--domain thyroid`)

Using `--domain thyroid` preset, the test returned **6 flags** including 2 `[MAJOR]` severity monitoring alerts:

| Flag | Type | Severity | Evidence |
|---|---|---|---|
| Methimazole ↔ Agranulocytosis | MONITORING | **MAJOR** | "monitoring for adverse events such as liver dysfunction, rash, and agranulocytosis should be carried out" |
| Propylthiouracil ↔ Agranulocytosis | MONITORING | **MAJOR** | Same evidence — class-level antithyroid drug warning |
| Methimazole ↔ Serum T3 Level | MONITORING | UNSPECIFIED | "monitor serum T3 levels initially because some patients normalise their free T4 levels with MMI, but have persistently elevated serum T3" |
| ATD ↔ WBC Count | MONITORING | UNSPECIFIED | "A differential WBC count should be obtained during febrile illness and at the onset of pharyngitis in all patients taking antithyroid medication" |
| Levothyroxine ↔ Pregnancy | DOSE_ADJUSTMENT | UNSPECIFIED | Dose adjustment required in pregnancy |
| Levothyroxine ↔ Hypothyroidism | DOSE_ADJUSTMENT | UNSPECIFIED | Titration guidance for hypothyroid patients |

Run with: `venv\Scripts\python.exe scratch\test_graph_clinical.py --domain thyroid`

The hardcoded default AF scenario still returns 0 flags (pre-existing corpus gap — AF CPG not yet ingested, unchanged).

---

## 8. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-22):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Diltiazem | INDICATED_FOR [MAJOR] | Thyroid Storm | "cardioselective calcium-channel blockers such as diltiazem or intravenous esmolol with shorter half-lives are indicated in thyroid storm..." |
| Metoprolol | REQUIRES_MONITORING [MODERATE] | Asthma Or Reactive Airway Disease | "In patients with asthma or reactive airway disease, cardio-selective β-blockers, such as atenolol or metoprolol, should be used with caution..." |
| Metoprolol | RECOMMENDED_FOR [UNSPECIFIED] | Lactating Women With Thyrotoxic Postpartum Thyroiditis | "A beta-blocker safe for lactating women, such as propranolol or metoprolol, at the lowest possible dose..." |
| Diltiazem | TREATS [UNSPECIFIED] | Thyrotoxicosis | "Oral administration of calcium-channel blockers, both verapamil and diltiazem, has been shown to affect heart rate in thyrotoxicosis..." |
| Methimazole | REQUIRES_MONITORING [MAJOR] | Agranulocytosis | "monitoring for adverse events such as liver dysfunction, rash, and agranulocytosis should be carried out" |

---

## 9. Known Issues

| Issue | Severity | Status | Notes |
|---|---|---|---|
| `clinical_graph_lookup` default AF scenario returns 0 flags | WARN | Pre-existing / investigate when AF CPG ingested | AF/anticoagulation domain gap. `--domain thyroid` preset passes with 6 flags. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |
| Cross-label duplication ratio 4.7% | MINOR | Acceptable | Under 5% SOP threshold; pre-existing across corpus. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested and verified cleanly (2026-05-22)**
======================================================================
