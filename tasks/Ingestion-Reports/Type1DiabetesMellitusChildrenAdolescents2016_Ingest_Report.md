# Management of Type 1 Diabetes Mellitus in Children and Adolescents (2016) Ingestion & Verification Report

> **Verified:** 2026-05-20 (SOP verification run on fresh ingestion)

## Executive Summary
The **Type-1-Diabetes-Mellitus-Children_Adolescents(2016)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. No embedding failures or cross-DB corruption were found.

Current footprint: **77 chunks** across 19 sections and **497 KG edges**, with **38.8%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph holds **10,592 nodes / 13,497 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 77 (12 H1, 7 H1-leaf, 53 H2, 5 H3)
- **Parent-Child Linkage**: 58 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 12 H1 null embeddings and 1 H2 null embedding are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Treatment* (43), *Supportive Treatment* (13), *Prevention* (12), *Reference* (11), *Special Populations* (9), *Assessment* (9), *Diagnosis* (3), *Epidemiology* (2), *Screening* (1), *Introduction* (1).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Section 5: Treatment Targets / 5.0: Overview Of Treatment* (sim=0.6879), followed by *5.3: Growth And Puberty* (0.6745) and *2.2: Clinical Presentation Of T1DM* (0.6717).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 497 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 149
  - `REDUCES_RISK_OF`: 64
  - `INDICATED_FOR`: 60
  - `ASSESSED_BY`: 49
  - `REQUIRES_MONITORING`: 32
  - `REQUIRES_DOSE_ADJUSTMENT`: 26
  - `OTHER`: 23
  - `HAS_DOSAGE`: 22
  - `CAUSES`: 22
  - `RECOMMENDED_FOR`: 19
  - `CONTRAINDICATED_WITH`: 17
  - `TREATS`: 12
  - `INTERACTS_WITH`: 1
  - `FIRST_LINE_FOR`: 1
- **Severity Coverage**: **38.8%** (38/98) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (497/497).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 10,592/10,592 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: Notable examples:
  - *body weight* split across `[OTHER]`, `[PatientProfile]`, `[Condition]`, `[DiagnosticTool]`
  - *poor prognosis* split across `[RiskFactor]`, `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.7% — under the 5% SOP threshold (MINOR, pre-existing across corpus).

---

## 4. KG-8: Full Per-CPG `cpg_chunk_id` Resolution
**Status:** ✅ Clean

- **Resolution**: **55/55 (0% orphaned)** distinct `cpg_chunk_id` values resolve to live Postgres chunks.
- **Shared titles handled**: 3 section titles shared with other CPGs were correctly skipped during the collision-aware sweep and not mis-attributed.
- **Corpus sweep**: ALL CPGs remain clean — 0 orphaned chunk references corpus-wide.

---

## 5. Cumulative Graph Health
**Status:** ✅ Healthy

- **Total nodes**: 10,592 | **Total edges**: 13,497 (grew from baseline of 10,153 nodes / 13,000 edges — +439 nodes, +497 edges from this CPG).
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
**Status:** ⚠ Pre-existing WARN — returns 0 flags

The `clinical_graph_lookup` smoke test probes a Warfarin/Digoxin + Atrial Fibrillation scenario and returns 0 flags. This is a **pre-existing data gap, not a code bug or regression from this CPG**. The Atrial Fibrillation (2012) CPG — which holds the canonical warfarin↔digoxin interaction edges — has not yet been ingested. Once ingested, this smoke test is expected to pass. Carried forward from prior verification sessions.

---

## 8. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-20):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Physical Activity | INCREASES_RISK_OF [MODERATE] | Hypoglycaemia | "Hypoglycaemia commonly occurs during unplanned physical activities..." |
| Physical Activity | REDUCES_RISK_OF [UNSPECIFIED] | Elevated Triglyceride | "There are benefits of physical activity on triglyceride (SMD= -0.70, 95% CI -1.25 to -0.14)..." |
| Statin | INDICATED_FOR [UNSPECIFIED] | Dyslipidaemia | "statin should be considered in children >10 years old if LDL is >4.1 mmol/L (or >3.4 mmol/L if one or more CVD risk factors present)..." |
| Statin | REDUCES_RISK_OF [UNSPECIFIED] | Macrovascular Disease | "Potential interventions [for Macrovascular disease]: Statins..." |
| Surgery | REQUIRES_MONITORING [UNSPECIFIED] | Glycaemic Control | "Assessment of glycaemic control, electrolyte status and ketones should be done several days before surgery..." |

---

## 9. Known Issues

| Issue | Severity | Status | Notes |
|---|---|---|---|
| `clinical_graph_lookup` smoke test returns 0 flags | WARN | Pre-existing / investigate when AF CPG ingested | AF/anticoagulation domain gap — warfarin↔digoxin interaction edge missing because Atrial-Fibrillation(2012) CPG not yet ingested. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |
| Cross-label duplication ratio 4.7% | MINOR | Acceptable | Under 5% SOP threshold; pre-existing across corpus. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested and verified cleanly (2026-05-20)**
======================================================================
