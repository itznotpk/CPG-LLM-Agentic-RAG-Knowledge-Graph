# Management of Type 2 Diabetes Mellitus (6th Edition) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-23 (fresh ingestion followed by SOP verification run)

## Executive Summary
The **T2-Diabetes-Mellitus(6th-Edition)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph. The main per-CPG verifier reports **ALL CHECKS PASSED**, with complete leaf embeddings, 1,695 KG edges, and 100% evidence/cpg_chunk_id metadata coverage.

However, the mandatory KG-8 full per-CPG chunk-reference sweep found **1 orphaned `cpg_chunk_id`**: 144/145 distinct diabetes chunk references resolve to Postgres, leaving a 0.7% orphan rate. Under the current SOP, any orphan from a fresh ingest should be treated as a remediation item even though the rest of the ingestion is healthy.

Current footprint: **149 chunks** across 18 sections and **1,695 KG edges**, with **64.1%** severity coverage on safety-critical edges.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** Healthy

- **Total Chunks**: 149 (18 H1, 66 H2, 65 H3)
- **Document Rows**: 18 section-level documents under `T2-Diabetes-Mellitus(6th-Edition)`.
- **Parent-Child Linkage**: 131 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 18 h1 and 15 h2 null embeddings are expected sub-split parents, so there are no leaf-level failures.
- **Metadata Coverage**: *Treatment* (115), *Supportive Treatment* (42), *Assessment* (34), *Reference* (28), *Screening* (13), *Prevention* (13), *Diagnosis* (10), *Special Populations* (5), *Epidemiology* (3), *Introduction* (3).
- **Vector Search Test**: End-to-end search for "treatment" returned T2DM treatment chunks, including GLP-1 receptor agonist sections for lixisenatide, liraglutide, and exenatide.

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** Healthy except KG-8 orphan reference

- **Total Edges Extracted**: 1,695 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 301
  - `REDUCES_RISK_OF`: 251
  - `INDICATED_FOR`: 203
  - `RECOMMENDED_FOR`: 163
  - `ASSESSED_BY`: 129
  - `CONTRAINDICATED_WITH`: 122
  - `HAS_DOSAGE`: 107
  - `TREATS`: 98
  - `CAUSES`: 73
  - `REQUIRES_DOSE_ADJUSTMENT`: 68
  - `REQUIRES_MONITORING`: 62
  - `INTERACTS_WITH`: 48
  - `OTHER`: 38
  - `FIRST_LINE_FOR`: 27
  - `SECOND_LINE_FOR`: 5
- **Severity Coverage**: **64.1%** (239/373) of safety-critical edges have severity markers, above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (1,695/1,695).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.
- **KG-8 Full Per-CPG Resolution**: 144/145 distinct T2DM chunk references resolve to Postgres chunks; **1 orphaned ID** (0.7%).

The orphaned ID is:

```text
7fdfd1b8-4321-4e70-943f-b7762db06dd1
```

It is used by one edge:

| Source Document | Subject | Relationship | Object | Evidence |
|---|---|---|---|---|
| Appendix: Drug Dosage Adjustments in Chronic Kidney Disease (CKD) and Cardiovascular Outcome Trials (CVOTs) | Varenicline | TREATS | Tobacco Use Disorder | "If selected, use nicotine replacement therapy (NRT) for at least eight to twelve weeks, whereas varenicline should be used for at least twel..." |

---

## 3. Entity Normalisation Health
**Status:** Excellent

- **name_normalised**: 13,589/13,589 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected in the per-CPG verifier, so no normaliser regression was introduced.
- **Cross-label duplicates (Safe)**: 1,232 nodes in the per-CPG verifier output, expected behaviour. Notable examples:
  - *body weight* split across `[OTHER]`, `[PatientProfile]`, `[Condition]`, `[DiagnosticTool]`, `[RiskFactor]`
  - *glycaemic control* split across `[DiagnosticTool]`, `[Condition]`, `[Procedure]`, `[OTHER]`, `[RiskFactor]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.8%, under the 5% SOP threshold (MINOR, manageable).
- **Abbreviation splits**: None found by `kg_dupes.py`.

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** Healthy with known corpus-level warnings

- **Step 5 - Cumulative health check** (`kg_verify.py`):
  - Total nodes: 13,589
  - Total edges: 18,252
  - Missing evidence: 0
  - Edges with `cpg_chunk_id`: 18,252/18,252
  - PG cross-check: 10/10 sampled UUIDs resolved
  - Orphan nodes: 0
  - Duplicate triple patterns: 10 corpus-wide patterns reported
- **KG-8 corpus sweep**: One CPG flagged: `T2-Diabetes-Mellitus(6th-Edition)` with 144/145 references resolved.

The 10 duplicate triple patterns are corpus-wide and not specific to this T2DM ingestion.

---

## 5. Clinical Lookup Smoke Tests (SOP Step 6b)
**Status:** T2DM-targeted PASS

- **T2DM-targeted clinical graph lookup** (`test_graph_clinical.py --cpg "T2DM"`):
  - Auto-discovered 60 safety edges across 6 T2DM source sections.
  - Returned 4 graph flags.
  - Empty-input crash guard: PASS.
  - Sample flags:
    - `Sulphonylurea INTERACTS_WITH Insulin [MODERATE]`
    - `Insulin REQUIRES_MONITORING DPP4-i`
    - `Metformin CONTRAINDICATED_WITH IV contrast dye exposure [MAJOR]`
    - `Metformin REQUIRES_DOSE_ADJUSTMENT DKD stage 3B [MODERATE]`

---

## 6. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-23):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Hypokalaemia | INCREASES_RISK_OF [MAJOR] | Severe Diabetic Ketoacidosis | "Hypokalaemia on admission (<3.5 mmol/L)..." |
| Hypertension | REQUIRES_MONITORING | Resting Electrocardiogram | "Resting electrocardiogram (ECG) is indicated for T2DM patients: with hypertension..." |
| Hypertension | INCREASES_RISK_OF [MAJOR] | Diabetic Retinopathy | "Hypertension should be detected and treated early in the course of T2DM..." |
| Hypertension | INCREASES_RISK_OF [MAJOR] | Renal Disease Progression | "Hypertension should be detected and treated early in the course of T2DM..." |
| Heart Failure | INCREASES_RISK_OF [MAJOR] | Severe Diabetic Ketoacidosis | "Patients with high risk for DKA or severe DKA should be admitted to HDU or the ICU..." |

---

## 7. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| One orphaned `cpg_chunk_id` in KG-8 | FAIL by SOP KG-8 | Open | Edge: `Varenicline -[TREATS]-> Tobacco Use Disorder`, source appendix CKD/CVOTs, orphan ID `7fdfd1b8-4321-4e70-943f-b7762db06dd1`. |
| 10 duplicate triple patterns graph-wide | INFO | Existing / acceptable for this ingestion | Reported by `kg_verify.py`; corpus-level issue. |
| Overall duplicate node ratio 4.8% | INFO | Manageable | Below 5% SOP threshold; same-label bad duplicates = 0. |

Suggested remediation for the KG-8 orphan:

1. Prefer a clean, collision-aware re-ingest of `T2-Diabetes-Mellitus(6th-Edition)` if this was meant to be a fresh final ingest.
2. If avoiding full re-ingest, delete or repair the single stale Neo4j edge after confirming whether the current appendix chunk still contains the varenicline evidence.
3. Re-run `scratch/sweep_cpg_corruption.py` and confirm `T2-Diabetes-Mellitus(6th-Edition)` reaches 145/145 or a clean lower denominator with 0 orphaned IDs.

======================================================================
**1 FAIL - KG-8 found 1 orphaned chunk reference; all other checks passed**
======================================================================
