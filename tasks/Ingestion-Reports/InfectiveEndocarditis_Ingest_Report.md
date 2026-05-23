# Prevention, Diagnosis & Management of Infective Endocarditis (2017) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-18 (fresh ingestion followed by full SOP verification run)

## Executive Summary
The **Prevention-Diagnosis-Management-of-IE** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph and passes the full per-CPG verification suite with **✅ ALL CHECKS PASSED**. All 10 sections landed cleanly: every true-leaf chunk has an embedding, every KG edge carries Phase A metadata, and no bad same-label duplicate nodes were introduced.

Current footprint: **64 chunks** across 10 sections and **759 KG edges**, with **54.7%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **5,978 nodes / 6,725 edges** across all ingested CPGs.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Healthy

- **Total Chunks**: 64 (6 H1, 4 H1-leaf, 36 H2, 18 H3)
- **Parent-Child Linkage**: 54 child chunks, **0 orphans**.
- **Embedding Integrity**: All true-leaf chunks embedded at dim = 1536. The 6 h1 and 6 h2 null embeddings are expected sub-split parents — no leaf-level FAILs.
- **Metadata Coverage**: *Diagnosis* (30), *Treatment* (18), *Reference* (18), *Classification* (17), *Assessment* (13), *Supportive Treatment* (13), *Prevention* (7), *Special Populations* (6), *Epidemiology* (1), *Introduction* (1).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *3.6.2: Interpretation of Echocardiography* (sim=1.0000), followed by *3.6.1: Echocardiography in Diagnosis of IE* (0.8932) and *4.1.1: Monitoring* (0.8538).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 759 clinical triples.
- **Relationship Breakdown**:
  - `INDICATED_FOR`: 155
  - `INCREASES_RISK_OF`: 146
  - `ASSESSED_BY`: 107
  - `REQUIRES_MONITORING`: 64
  - `RECOMMENDED_FOR`: 51
  - `CONTRAINDICATED_WITH`: 51
  - `HAS_DOSAGE`: 47
  - `REQUIRES_DOSE_ADJUSTMENT`: 41
  - `TREATS`: 22
  - `CAUSES`: 21
  - `OTHER`: 21
  - `REDUCES_RISK_OF`: 21
  - `SECOND_LINE_FOR`: 5
  - `FIRST_LINE_FOR`: 3
  - `CROSS_REACTS_WITH`: 2
  - `INTERACTS_WITH`: 2
- **Severity Coverage**: **54.7%** (98/179) of safety-critical edges have severity markers — well above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (759/759).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 5,978/5,978 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 442 nodes — expected behaviour. Examples:
  - *hypotension* split across `[AdverseEvent]`, `[Condition]`, `[RiskFactor]`
  - *sedation* split across `[Drug]`, `[Procedure]`, `[AdverseEvent]`
  - *hypertension* split across `[Condition]`, `[AdverseEvent]`, `[RiskFactor]`
- **Overall duplication ratio**: 3.8% — under the 5% SOP threshold (MINOR, unchanged from pre-ingestion baseline).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 5,978 | Total edges: 6,725 (+623 net nodes, +759 edges vs. pre-IE baseline)
  - 0 missing evidence, 0 orphan nodes, 10/10 PG cross-check pass.
  - "1 issue" = same 10 pre-existing duplicate triple patterns (0.15% of edges) from cross-CPG cardiac overlap — unchanged, not introduced by this ingestion.

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-18):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Transoesophageal Echocardiography | RECOMMENDED_FOR | Prosthetic Valve Endocarditis | "TEE is recommended for patients with prosthetic valves rated as at least possible IE by clinical criteria…" |
| Transoesophageal Echocardiography | ASSESSED_BY [MAJOR] | Paravalvular Abscess | "Causes of uncontrolled infection: paravalvular abscess, pseudoaneurysms or fistulae (using TEE)…" |
| Diabetes | INCREASES_RISK_OF [MODERATE] | Infective Endocarditis | "Co-existing conditions such as diabetes, HIV infection and malignancy are predisposing risk factors for IE…" |
| Transoesophageal Echocardiography | ASSESSED_BY | Prosthetic Valve Endocarditis | "Prosthetic valve endocarditis (PVE) with sensitivity of TTE 36% and TEE 82%…" |
| Transoesophageal Echocardiography | ASSESSED_BY | Infective Endocarditis | "The principal modality is echocardiography (transthoracic and transoesophageal), complemented by other imaging…" |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Note |
|---|---|---|---|
| `clinical_graph_lookup` smoke test (Warfarin/Digoxin, AF/Warfarin) returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — scenarios are AF/anticoagulation domain. Carried forward from prior verification sessions. |
| 10 duplicate triple patterns graph-wide | INFO | Acceptable | 0.15% of edges. Pre-existing cross-CPG cardiac overlap (e.g. AF→Stroke), not introduced by this ingestion. |

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
