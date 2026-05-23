# Management of Heart Failure (5th Edition) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-19 (full SOP verification run)

## Executive Summary
The **Heart-Failure(5th Edition)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. Initial verification found 1 null-embedding leaf chunk (`Appendix XIII`) caused by 5 `±` (U+00B1, plus-minus sign) characters rejected by Bedrock Titan. Fixed by replacing `±` → `+/-` in `appendix-heartfailure.md` and directly re-embedding the chunk.

Current footprint: **218 chunks** across 29 sections and **1,406 KG edges**, with **53.6%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **9,701 nodes / 11,875 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy (resolved after `±` → `+/-` fix and direct re-embedding)

- **Total Chunks**: 218 (23 H1, 6 H1-leaf, 128 H2, 61 H3)
- **Parent-Child Linkage**: 189 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 23 h1 and 11 h2 null embeddings are expected sub-split parents — no leaf-level FAILs.
  - **Previously affected chunk:** `Appendix XIII: The Different Causes Of ACHD-HF` — contained 5× `±` (U+00B1) in the Management column (`ACEi, ARB ± sacubitril`). Fixed by replacing all `±` with `+/-` in `appendix-heartfailure.md`; embedding written directly to DB.
- **Metadata Coverage**: *Treatment* (100), *Reference* (97), *Assessment* (56), *Special Populations* (46), *Prevention* (42), *Classification* (29), *Diagnosis* (25), *Supportive Treatment* (22), *Epidemiology* (5), *Pathophysiology* (5).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *14.1.1: Risk Of Developing Dysglycemia In Patients With HF* (sim=1.0000), followed by *14.1.3: Prognosis Of Patients With Dysglycemia And HF* (0.8995) and *14.1.2: Risk Of Developing HF Among Patients With Dysglycemia* (0.8855).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 1,406 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 367
  - `INDICATED_FOR`: 240
  - `REDUCES_RISK_OF`: 127
  - `RECOMMENDED_FOR`: 113
  - `ASSESSED_BY`: 100
  - `CAUSES`: 100
  - `CONTRAINDICATED_WITH`: 79
  - `REQUIRES_MONITORING`: 64
  - `REQUIRES_DOSE_ADJUSTMENT`: 55
  - `TREATS`: 54
  - `OTHER`: 34
  - `FIRST_LINE_FOR`: 26
  - `INTERACTS_WITH`: 23
  - `HAS_DOSAGE`: 17
  - `SECOND_LINE_FOR`: 7
- **Severity Coverage**: **53.6%** (172/321) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (1406/1406).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 9,701/9,701 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 825 nodes — expected behaviour. Notable examples:
  - *blood pressure* split across `[DiagnosticTool]`, `[Condition]`, `[RiskFactor]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
  - *ldl-c reduction* split across `[RiskFactor]`, `[Procedure]`, `[DiagnosticTool]`, `[Condition]`
- **Overall duplication ratio**: 4.4% — under the 5% SOP threshold (MINOR).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 9,701 | Total edges: 11,875 (vs. pre-ingestion baseline)
  - 0 missing evidence, 10/10 PG cross-check pass.
  - 304 orphan nodes — pre-existing graph-wide pattern, not introduced by this ingestion.

---

## 5. Phase D & Clinical Lookup Smoke Tests (SOP Steps 6 & 6b)
**Status:** ✅ Phase D PASS | ⚠ Clinical lookup pre-existing WARN

- **Phase D (test_phase_d_af.py)**:
  - Gate 1 — candidate drugs extracted from chunks: **PASS** (83 drugs)
  - Gate 2 — flags returned by KG lookup: **PASS** (22 flags fired)
  - Gate 3 — flags block contains INTERACTION FLAGS: **PASS**
  - Sample flags: `Dronedarone CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Digoxin INTERACTS_WITH Amiodarone [MAJOR]`, `Diltiazem CONTRAINDICATED_WITH Heart Failure With Reduced Lvef [MAJOR]`
- **Clinical lookup smoke test (test_graph_clinical.py)**:
  - Returns 0 flags for Warfarin/Digoxin and AF/Warfarin scenarios — pre-existing WARN, not caused by this CPG (AF/anticoagulation domain gap carried forward from prior sessions).

---

## 6. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-19):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Diltiazem | CONTRAINDICATED_WITH [MAJOR] | Heart Failure With Reduced Lvef | "Diltiazem, verapamil and nifedipine should be avoided…" |
| Dronedarone | CONTRAINDICATED_WITH [MAJOR] | Heart Failure | "Dronedarone should not be used in patients with heart failure." |
| Digoxin | INTERACTS_WITH [MAJOR] | Amiodarone | "Verapamil … Hypotension, heart block, heart failure, digoxin interaction" |
| Sotalol | RECOMMENDED_FOR | Pvc Induced Cardiomyopathy | "Anti-arrhythmic drug therapy that may be considered include β-blockers and class 3 anti-arrhythmic drugs…" |
| Diltiazem | INDICATED_FOR | Atrial Fibrillation | "Its use is mainly to treat hypertension or for rate control in AF…" |

---

## 7. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| `Appendix XIII` — null embedding due to 5× `±` (U+00B1) characters | FAIL (PG-3) | ✅ Resolved | Replaced `±` → `+/-` in `appendix-heartfailure.md` (lines 206–213, 281); embedding written directly to DB. |
| `clinical_graph_lookup` smoke test returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — AF/anticoagulation domain gap. Carried forward from prior verification sessions. |
| 304 orphan nodes graph-wide | INFO | Pre-existing / acceptable | Not introduced by this ingestion. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly (1 PG-3 FAIL resolved via `±` → `+/-` fix)**
======================================================================
