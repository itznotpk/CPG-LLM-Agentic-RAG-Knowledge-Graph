# Management of Obesity (2023) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-23 (fresh ingestion followed by full SOP verification run)

## Executive Summary
The **Obesity-Management(2023)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **ALL CHECKS PASSED**.

Current footprint: **84 chunks** across 10 sections and **747 KG edges**, with **46.3%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The mandatory KG-8 sweep confirms **0 orphaned chunk references** for this CPG.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** Healthy

- **Total Chunks**: 84 (8 H1, 2 H1-leaf, 30 H2, 44 H3)
- **Document Rows**: 10 section-level documents under `Obesity-Management(2023)`.
- **Parent-Child Linkage**: 74 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 8 h1 and 7 h2 null embeddings are expected sub-split parents, so there are no leaf-level failures.
- **Metadata Coverage**: *Treatment* (59), *Screening* (31), *Diagnosis* (31), *Special Populations* (20), *Prevention* (15), *Reference* (15), *Supportive Treatment* (9), *Methodology* (6), *Introduction* (5), *Epidemiology* (5).
- **Vector Search Test**: End-to-end search for "treatment" returned obesity-management chunks, including *Section 5: Management Of Childhood And Adolescent Obesity* as the top match.

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** Healthy

- **Total Edges Extracted**: 747 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 133
  - `CAUSES`: 127
  - `REDUCES_RISK_OF`: 114
  - `INDICATED_FOR`: 97
  - `RECOMMENDED_FOR`: 63
  - `TREATS`: 57
  - `ASSESSED_BY`: 56
  - `CONTRAINDICATED_WITH`: 42
  - `REQUIRES_MONITORING`: 21
  - `INTERACTS_WITH`: 11
  - `OTHER`: 9
  - `FIRST_LINE_FOR`: 8
  - `HAS_DOSAGE`: 7
  - `REQUIRES_DOSE_ADJUSTMENT`: 2
- **Severity Coverage**: **46.3%** (94/203) of safety-critical edges have severity markers, above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (747/747).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.
- **KG-8 Full Per-CPG Resolution**: 59/59 distinct obesity chunk references resolve to Postgres chunks; **0.0% orphaned**.

---

## 3. Entity Normalisation Health
**Status:** Excellent

- **name_normalised**: 12,583/12,583 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected in the per-CPG verifier, so no normaliser regression was introduced.
- **Cross-label duplicates (Safe)**: 1,132 nodes in the per-CPG verifier output, expected behaviour. Notable examples:
  - *body weight* split across `[OTHER]`, `[PatientProfile]`, `[Condition]`, `[DiagnosticTool]`, `[RiskFactor]`
  - *poor prognosis* split across `[RiskFactor]`, `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.7%, under the 5% SOP threshold (MINOR, manageable).
- **Abbreviation splits**: None found by `kg_dupes.py`.

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** Healthy with one pre-existing corpus-level warning

- **Step 5 - Cumulative health check** (`kg_verify.py`):
  - Total nodes: 12,583
  - Total edges: 16,557
  - Missing evidence: 0
  - Edges with `cpg_chunk_id`: 16,557/16,557
  - PG cross-check: 10/10 sampled UUIDs resolved
  - Orphan nodes: 0
  - Duplicate triple patterns: 10 corpus-wide patterns reported
- **KG-8 corpus sweep**: All CPGs clean; 0 orphaned chunk references.

The 10 duplicate triple patterns are a residual corpus-wide issue and were not identified as an obesity-specific ingestion failure.

---

## 5. Clinical Lookup Smoke Tests (SOP Step 6b)
**Status:** Obesity-targeted PASS

- **Default clinical graph lookup** (`test_graph_clinical.py`):
  - Returned 0 flags for the hardcoded AF/anticoagulation scenario.
  - Treated as a pre-existing/default-scenario warning, not an obesity ingestion failure.
- **Obesity-targeted clinical graph lookup** (`test_graph_clinical.py --cpg "Obesity"`):
  - Auto-discovered 60 safety edges across 2 obesity source sections.
  - Returned 5 graph flags.
  - Empty-input crash guard: PASS.
  - Sample flags:
    - `Secretagogue INTERACTS_WITH Liraglutide [MODERATE]`
    - `Secretagogue INTERACTS_WITH Semaglutide [MODERATE]`
    - `Thyroxine INTERACTS_WITH Orlistat`
    - `Cyclosporine INTERACTS_WITH Orlistat`
    - `Semaglutide CONTRAINDICATED_WITH eGFR <15 ml/min`

---

## 6. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-23):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Metoprolol | INCREASES_RISK_OF | Weight Gain | "Beta-blockers: Metoprolol; Atenolol; Propranolol..." |
| Atenolol | INCREASES_RISK_OF | Weight Gain | "Beta-blockers: Metoprolol; Atenolol; Propranolol..." |
| Propranolol | INCREASES_RISK_OF | Weight Gain | "Beta-blockers: Metoprolol; Atenolol; Propranolol..." |
| Physical Activity | REDUCES_RISK_OF | Obesity | "Availability and accessibility to greenspaces, parks, recreational facilities, and sidewalks..." |
| Proton Pump Inhibitor | RECOMMENDED_FOR [MAJOR] | Intragastric Balloon | "Prophylaxis with PPIs in individuals undergoing IGB therapy..." |
| Semaglutide | CONTRAINDICATED_WITH | eGFR <15 ml/min | "eGFR <15 ml/min" |

---

## 7. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| 10 duplicate triple patterns graph-wide | INFO | Existing / acceptable for this ingestion | Reported by `kg_verify.py`; not obesity-specific. |
| Default AF clinical lookup returns 0 flags | WARN | Pre-existing / investigate separately | The obesity-targeted smoke test passes with 5 flags. |

======================================================================
**ALL CHECKS PASSED - CPG ingested cleanly**
======================================================================
