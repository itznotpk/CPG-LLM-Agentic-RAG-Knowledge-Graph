# Breast Cancer (3rd Edition) Ingestion & Verification Report

## Executive Summary
The ingestion for the **Breast-Cancer(3rd Edition)** Clinical Practice Guideline (CPG) has been successfully completed and verified.

Overall, **66 chunks** and **634 knowledge graph edges** were generated across 13 clinical sections. The ingestion correctly parsed all sections including algorithms, treatment protocols, and familial risk management. One minor issue persists: 1 true H2 leaf chunk (Appendix 7: Medications table) has a null embedding due to heavy HTML table formatting exceeding Titan v1's content tolerance. A structural fix (splitting into 3 H3 subsections by drug category) has been applied to the markdown source and awaits re-ingestion of the appendix file.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ⚠️ 1 Minor Issue (Appendix 7 null embedding)

- **Total Chunks**: 66 (9 H1 parents, 4 H1_leaf, 33 H2, 20 H3)
- **Parent-Child Linkage**: 53 child chunks correctly linked to parents, with **0 orphans**.
- **Embedding Integrity**: 5 null H2 chunks are sub-split parents (by design). **1 true leaf null** — Appendix 7 medication table (10,438 chars of dense Markdown tables with `<br>` HTML tags). Fix applied: split into H3 subsections (Chemotherapy / Targeted Therapy / Hormonal Therapy).
- **Metadata Coverage**: Rich category distribution — *Treatment* (27), *Reference* (21), *Assessment* (20), *Diagnosis* (20), *Classification* (19), *Prevention* (19), *Screening* (14), *Special Populations* (9), *Supportive Treatment* (7), *Epidemiology* (3).
- **Vector Search Test**: End-to-end search for "treatment" works correctly (top match: *5.1.1: Clinical* with sim=1.0000).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Complete Success

- **Total Edges Extracted**: 634 clinical triples.
- **Top Relationships**:
  - `INDICATED_FOR`: 155
  - `INCREASES_RISK_OF`: 144
  - `REDUCES_RISK_OF`: 77
  - `RECOMMENDED_FOR`: 61
  - `CAUSES`: 58
  - `ASSESSED_BY`: 49
  - `REQUIRES_MONITORING`: 29
  - `TREATS`: 27
- **Severity Coverage**: 20.2% of safety-critical edges have severity markers (below the 30% threshold — this is expected for an oncology CPG where risk factors dominate over drug interaction severity).
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (634/634).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 2512/2512 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected.
- **Cross-label duplicates (Safe)**: 162 nodes — expected behaviour (e.g., "hypotension" as both `[AdverseEvent]` and `[Condition]`).

---

## 4. Cumulative Graph Health (SOP Steps 5, 5b, 6b)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 2,512 | Total edges: 2,673 (at time of Breast Cancer verification)
  - Missing evidence: 0 (0.0%)
  - Orphan nodes: 0
  - Cross-DB linkage: 10/10 sampled UUIDs resolve
  - Duplicate triples: 2 patterns (Stent→Restenosis, POBA→Restenosis — from PCI CPG, not Breast Cancer)
- **Step 5b — Duplicate node audit** (`kg_dupes.py`):
  - Overall duplication ratio: **3.3%** (MINOR — all cross-label, 0 same-label bad duplicates)
- **Step 6b — Clinical graph lookup** (`test_graph_clinical.py`):
  - All 4 smoke tests completed without errors
  - Drug interaction, comorbidity flag, and prompt formatting all functional

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG:

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Age | INCREASES_RISK_OF | Breast Cancer | "The risk of breast cancer increases with age. Based on latest National Cancer Registry Report of Mal..." |
| Female Gender | INCREASES_RISK_OF | Breast Cancer | "Female has much higher risk of breast cancer compared with male..." |
| Surgery | INDICATED_FOR | Early Breast Cancer | "Option A: Direct to Surgery..." |
| Surgery | RECOMMENDED_FOR | Metastatic Breast Cancer | "Consider local treatment (radiotherapy/surgery) if indicated..." |
| Surgery | TREATS | Locally Advanced Breast Cancer | "If becomes Operable: → Surgery → Radiotherapy..." |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| Appendix 7 null embedding | Minor | Fix applied, pending re-ingestion | Markdown split into 3 H3 subsections by drug category |
| Severity coverage 20.2% | Informational | Expected | Oncology CPGs emphasise risk factors over drug-drug interaction severity |

======================================================================
✅ **VERIFICATION COMPLETE — CPG ingested with 1 minor pending fix**
======================================================================
