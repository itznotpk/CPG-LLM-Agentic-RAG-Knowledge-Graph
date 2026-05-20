# Management of Ischaemic Stroke (3rd Edition) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-19 (fresh ingestion followed by full SOP verification run)

## Executive Summary
The **Ischaemic-Stroke(3rd Edition)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. Initial ingestion had 2 null-embedding leaf chunks (`5.7 Cardioembolism` and `12.8 End-Of-Life Care`) — one caused by Unicode subscript characters (`CHA₂DS₂-VASc`) rejected by Bedrock Titan, one by a transient API error. Both were resolved by splitting each into h3 subsections and re-ingesting with `--skip-graph`.

Current footprint: **117 chunks** across 18 sections (+4 h3s from the fix) and **794 KG edges**, with **63.8%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **8,068 nodes / 9,281 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy (resolved after h3 split and re-ingest)

- **Total Chunks**: 117 (16 H1, 2 H1-leaf, 68 H2, 31 H3)
- **Parent-Child Linkage**: 99 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 16 h1 and 5 h2 null embeddings are expected sub-split parents — no leaf-level FAILs.
  - **Previously affected chunk 1:** `5.7: Cardioembolism` — contained `CHA₂DS₂-VASc` Unicode subscript characters (U+2082) rejected by Bedrock Titan. Fixed by replacing with ASCII `CHA2DS2-VASc` and splitting into `### 5.7A` (overview + Table 5.5) and `### 5.7B` (Table 5.4 cardiac conditions).
  - **Previously affected chunk 2:** `12.8: End-Of-Life Care` — transient Bedrock API error. Fixed by splitting into `### 12.8A` (clinical guidance) and `### 12.8B` (Table 12.1 recommendations summary + key recommendations).
- **Metadata Coverage**: *Treatment* (84), *Prevention* (25), *Supportive Treatment* (23), *Special Populations* (19), *Diagnosis* (13), *Assessment* (12), *Reference* (9), *Epidemiology* (4), *Pathophysiology* (4), *Classification* (4).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Section 4: Prognosis / 4.1: Survival After Stroke* (sim=1.0000), followed by *4.4: Disability* (0.8322) and *4.2: Risk Factors For Stroke Mortality* (0.7696).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 794 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 157
  - `INDICATED_FOR`: 150
  - `RECOMMENDED_FOR`: 93
  - `ASSESSED_BY`: 90
  - `REDUCES_RISK_OF`: 73
  - `CONTRAINDICATED_WITH`: 56
  - `TREATS`: 38
  - `CAUSES`: 32
  - `HAS_DOSAGE`: 30
  - `REQUIRES_MONITORING`: 29
  - `OTHER`: 25
  - `REQUIRES_DOSE_ADJUSTMENT`: 7
  - `INTERACTS_WITH`: 6
  - `FIRST_LINE_FOR`: 6
  - `SECOND_LINE_FOR`: 2
- **Severity Coverage**: **63.8%** (83/130) of safety-critical edges have severity markers — well above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (794/794).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 8,068/8,068 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 610 nodes — expected behaviour. Notable examples:
  - *blood pressure* split across `[DiagnosticTool]`, `[Condition]`, `[RiskFactor]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
  - *renal function* split across `[DiagnosticTool]`, `[Condition]`, `[Procedure]`, `[RiskFactor]`
- **Overall duplication ratio**: 3.9% — under the 5% SOP threshold (MINOR, unchanged).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 8,068 | Total edges: 9,281 (vs. pre-ingestion baseline)
  - 0 missing evidence, 0 orphan nodes, 10/10 PG cross-check pass.
  - "1 issue" = same pre-existing duplicate triple patterns from cross-CPG cardiac overlap — unchanged, not introduced by this ingestion.

---

## 5. Phase D & Clinical Lookup Smoke Tests (SOP Steps 6 & 6b)
**Status:** ✅ Phase D PASS | ⚠ Clinical lookup pre-existing WARN

- **Phase D (test_phase_d_af.py)**:
  - Gate 1 — candidate drugs extracted from chunks: **PASS** (86 drugs)
  - Gate 2 — flags returned by KG lookup: **PASS** (17 flags fired)
  - Gate 3 — flags block contains INTERACTION FLAGS: **PASS**
  - Sample flags: `Dronedarone CONTRAINDICATED_WITH Heart Failure [MAJOR]`, `Digoxin INTERACTS_WITH Diltiazem`, `Metoprolol REQUIRES_DOSE_ADJUSTMENT Heart Failure`
- **Clinical lookup smoke test (test_graph_clinical.py)**:
  - Returns 0 flags for Warfarin/Digoxin and AF/Warfarin scenarios — pre-existing WARN, not caused by this CPG (AF/anticoagulation domain gap carried forward from prior sessions).

---

## 6. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-19):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Hypertension | INCREASES_RISK_OF [MAJOR] | Ischaemic Stroke | "Hypertension is the commonest and major risk factor for both ischaemic and haemorrhagic strokes in Malaysia…" |
| Hypertension | INCREASES_RISK_OF [MAJOR] | Haemorrhagic Stroke | "Hypertension is the commonest and major risk factor for both ischaemic and haemorrhagic strokes in Malaysia…" |
| Hypertension | REQUIRES_MONITORING | Acute Stroke | "Hypotension and hypertension in patients with acute stroke should be identified and managed accordingly…" |
| Hypertension | INDICATED_FOR | Early Treatment In AIS Patients With Comorbid Condition | "In patients with AIS, early treatment of hypertension is indicated when required by comorbid conditions…" |
| Hypertension | REQUIRES_MONITORING | Cardiovascular Risk | "Those with intermediate to high risks should be followed-up, and maintained on lifestyle interventions…" |

---

## 7. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| `5.7: Cardioembolism` — null embedding due to `CHA₂DS₂-VASc` Unicode chars (U+2082) | FAIL (PG-3) | ✅ Resolved | Replaced Unicode subscript with ASCII `CHA2DS2-VASc`; split into `### 5.7A` and `### 5.7B`; re-ingested with `--skip-graph`. |
| `12.8: End-Of-Life Care` — null embedding (transient Bedrock API error) | FAIL (PG-3) | ✅ Resolved | Split into `### 12.8A` and `### 12.8B`; re-ingested with `--skip-graph`. All leaf chunks now embed cleanly. |
| `clinical_graph_lookup` smoke test returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — AF/anticoagulation domain gap. Carried forward from prior verification sessions. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly (2 PG-3 FAILs resolved via h3 split and re-ingest)**
======================================================================

---

## 8. Cross-DB Corruption Discovery & Remediation (2026-05-20)

### What was found
A corpus-wide read-only sweep (`scratch/sweep_cpg_corruption.py`, the new SOP **KG-8** check) flagged this CPG with **29.5% orphaned `cpg_chunk_id`** — 26 of 88 distinct edge chunk-IDs pointed to Postgres chunks that no longer existed. Same failure mode as the Dyslipidaemia incident: stale edges from a prior/partial ingest left the Neo4j edge set out of sync with regenerated Postgres chunk UUIDs. The original 2026-05-19 verification missed this because SOP KG-4 samples only 10 IDs corpus-wide, not per-CPG.

### Remediation (`scratch/cleanup_stroke.py`)
Collision-aware cleanup + clean re-ingest:
1. **Neo4j** — deleted 770 edges on the **17 section titles unique to this CPG**, plus 31 edges on the **shared** title "Section 3: Diagnosis And Initial Assessment" disambiguated by `cpg_chunk_id` ownership. **Hypertension's 38 Section-3 edges were preserved** (verified before & after).
2. **Postgres** — deleted 117 chunks + 18 documents by `cpg_name`.
3. **Re-ingest** — full clean run, exit 0, no Bedrock errors, all 18 sections.
4. **Singular-pointer repair** — 4 edge instances (3 distinct IDs: Statin→Pregnancy, Clopidogrel dosage, Varenicline→smoking cessation) had a stale *singular* `cpg_chunk_id` while their `cpg_chunk_ids` **list** still held live chunks (cross-CPG MERGE accumulation). Repointed the singular pointer to a live list entry — no data loss.
5. **Orphan-node prune** — removed nodes left edge-less by the deletion.

### Post-remediation verification
| Check | Result |
|---|---|
| **KG-8** full per-CPG `cpg_chunk_id` resolution | **97/97 (0% orphaned)** ✅ |
| Corpus sweep | **ALL CPGs clean — 0 orphaned references** ✅ |
| Shared "Section 3" integrity | 83 edges, 0 dead; Hypertension edges intact ✅ |
| SOP `verify_cpg_ingest.py` | **✅ ALL CHECKS PASSED** (117 chunks, 894 edges) |

**Result:** corruption fully resolved. Edge count rose 794 → 894 (the prior partial state under-counted). See [SOP §Step 4b (KG-8)](../Next-Step/SOP_Ingestion_Verification.md) for the check now guarding against recurrence.
