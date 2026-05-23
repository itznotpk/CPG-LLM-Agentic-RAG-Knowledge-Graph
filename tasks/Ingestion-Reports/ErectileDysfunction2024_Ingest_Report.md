# Management of Erectile Dysfunction (2024) Ingestion & Verification Report

> **Verified:** 2026-05-20 (SOP verification run on fresh ingestion)

## Executive Summary
The **Erectile-Dysfunction(2024)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. No embedding failures or cross-DB corruption were found.

Current footprint: **44 chunks** across 10 sections and **344 KG edges**, with **41.2%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph holds **11,015 nodes / 14,128 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 44 (6 H1, 4 H1-leaf, 31 H2, 3 H3)
- **Parent-Child Linkage**: 34 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 6 H1 null embeddings and 1 H2 null embedding are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Treatment* (28), *Reference* (18), *Methodology* (14), *Epidemiology* (6), *Special Populations* (5), *Assessment* (5), *Diagnosis* (4), *Prevention* (1), *Supportive Treatment* (1), *Introduction* (1).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Section 8: Special Populations / 8.1: Patients With Cardiovascular Disease* (sim=1.0000), followed by *Algorithm 2: Classification For ED Patients With Cardiovascular Disease* (0.8336) and *3.2: Cardiovascular Risk Assessment* (0.8072).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 344 clinical triples.
- **Relationship Breakdown**:
  - `CAUSES`: 72
  - `INCREASES_RISK_OF`: 55
  - `INDICATED_FOR`: 41
  - `CONTRAINDICATED_WITH`: 36
  - `TREATS`: 34
  - `REQUIRES_DOSE_ADJUSTMENT`: 25
  - `ASSESSED_BY`: 18
  - `RECOMMENDED_FOR`: 13
  - `HAS_DOSAGE`: 13
  - `REDUCES_RISK_OF`: 11
  - `REQUIRES_MONITORING`: 10
  - `FIRST_LINE_FOR`: 6
  - `INTERACTS_WITH`: 5
  - `OTHER`: 4
  - `SECOND_LINE_FOR`: 1
- **Severity Coverage**: **41.2%** (61/148) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (344/344).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 11,015/11,015 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: Notable examples:
  - *body weight* split across `[OTHER]`, `[PatientProfile]`, `[Condition]`, `[DiagnosticTool]`
  - *poor prognosis* split across `[RiskFactor]`, `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
- **Overall duplication ratio**: 4.7% — under the 5% SOP threshold (MINOR, pre-existing across corpus).

---

## 4. KG-8: Full Per-CPG `cpg_chunk_id` Resolution
**Status:** ✅ Clean

- **Resolution**: **22/22 (0% orphaned)** distinct `cpg_chunk_id` values resolve to live Postgres chunks.
- **Shared titles handled**: 5 section titles shared with other CPGs were correctly skipped — highest shared-title count seen so far, as generic section names (Introduction, Appendix, Referral, etc.) are common across CPGs.
- **Corpus sweep**: ALL CPGs remain clean — 0 orphaned chunk references corpus-wide.

---

## 5. Cumulative Graph Health
**Status:** ✅ Healthy

- **Total nodes**: 11,015 | **Total edges**: 14,128 (grew from baseline of 10,827 nodes / 13,784 edges — +188 nodes, +344 edges from this CPG).
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

The default `--cpg "Erectile Dysfunction"` substring did not match any `source_document` values (ED section titles are generic, e.g. "Section 4: Treatment"). Using `--cpg "Section 4: Treatment"` successfully matched and returned **6 flags**:

| Flag | Type | Severity | Evidence |
|---|---|---|---|
| Alpha-Blocker ↔ PDE5i | INTERACTION | UNSPECIFIED | "combination of PDE5i with various agents (mainly alpha-blocker, testosterone and antioxidants) was more effective than PDE5i monotherapy..." |
| Antioxidant ↔ PDE5i | INTERACTION | UNSPECIFIED | Same evidence — multi-agent combination study |
| Testosterone ↔ PDE5i | INTERACTION | UNSPECIFIED | Same evidence — multi-agent combination study |
| Phosphodiesterase-5 Inhibitor ↔ Organic Nitrate | CONTRAINDICATION | **MAJOR** | "They are contraindicated in patients taking nitric oxide (NO) donors, organic nitrates or organic nitrites..." |
| Phosphodiesterase-5 Inhibitor ↔ Organic Nitrite | CONTRAINDICATION | **MAJOR** | Same evidence — nitric oxide donors |
| Phosphodiesterase-5 Inhibitor ↔ Sudden Vision Loss | CONTRAINDICATION | **MAJOR** | "Patients with ED should stop PDE5i and seek immediate medical care when there is a sudden loss of vision..." |

> **Note on auto-discover**: The `--cpg` flag matches against `source_document` values in Neo4j, which are section titles (not CPG folder names). For CPGs with generic section titles, use a specific section title as the substring (e.g. `--cpg "Section 4: Treatment"`). A preset `ed` domain scenario should be added to the `PRESETS` registry for convenience.

The hardcoded default AF scenario still returns 0 flags (pre-existing corpus gap — AF CPG not yet ingested).

---

## 8. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-20):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Phosphodiesterase-5 Inhibitor | CONTRAINDICATED_WITH [MAJOR] | Organic Nitrate | "They are contraindicated in patients taking nitric oxide (NO) donors, organic nitrates or organic nitrites (e.g. glyceryl trinitrate)..." |
| Phosphodiesterase-5 Inhibitor | CONTRAINDICATED_WITH [MAJOR] | Sudden Vision Loss | "Patients with ED should stop PDE5i and seek immediate medical care when there is a sudden loss of vision in one or both eyes..." |
| Hypertension | INCREASES_RISK_OF [UNSPECIFIED] | Tadalafil Treatment Failure | "presence of hypertension (OR=2.217, 95% CI 1.015 to 2.987) was associated with the failure of tadalafil treatment..." |
| Atrial Fibrillation | INCREASES_RISK_OF [UNSPECIFIED] | Erectile Dysfunction | "Patients with atrial fibrillation showed an ED prevalence of 57% (95% CI 50 to 64) based on a meta-analysis..." |
| Physical Activity | REDUCES_RISK_OF [UNSPECIFIED] | Erectile Dysfunction | "modifications of CV risk factors which included physical activity, Mediterranean diet and weight loss..." |

---

## 9. Known Issues

| Issue | Severity | Status | Notes |
|---|---|---|---|
| `--cpg "Erectile Dysfunction"` does not match source_documents | INFO | By design | Section titles are generic (e.g. "Section 4: Treatment"). Use specific section title substring or add a preset `ed` domain to `PRESETS` in `test_graph_clinical.py`. |
| `clinical_graph_lookup` default AF scenario returns 0 flags | WARN | Pre-existing / investigate when AF CPG ingested | AF/anticoagulation domain gap. Domain-specific test passes with 6 flags using section-title substring. |
| Pre-existing duplicate triple patterns graph-wide | INFO | Acceptable | Cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |
| Cross-label duplication ratio 4.7% | MINOR | Acceptable | Under 5% SOP threshold; pre-existing across corpus. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested and verified cleanly (2026-05-20)**
======================================================================
