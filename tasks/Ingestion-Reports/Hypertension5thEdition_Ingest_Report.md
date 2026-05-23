# Management of Hypertension (5th Edition) Ingestion & Verification Report

> **Ingested & verified:** 2026-05-18 (fresh ingestion followed by full SOP verification run)

## Executive Summary
The **Hypertension(5th Edition)** Clinical Practice Guideline is ingested into both the vector DB and the knowledge graph with **1 FAIL**: two h2 leaf chunks in the Appendices section have null embeddings. Both are large paediatric BP reference tables (~14,600 characters each) that almost certainly exceed the Bedrock Titan input-length limit, identical in nature to the CVD-Prevention-Women oversize table issue. All other checks — KG integrity, normalisation, cross-DB linkage, and the vector smoke test — pass.

Current footprint: **90 chunks** across 14 sections and **887 KG edges**, with **60.4%** severity coverage on safety-critical edges and **100%** evidence/cpg_chunk_id coverage. The cumulative graph now holds **6,938 nodes / 8,230 edges**.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ❌ 2 leaf embeddings missing — otherwise healthy

- **Total Chunks**: 90 (9 H1, 5 H1-leaf, 47 H2, 29 H3)
- **Parent-Child Linkage**: 76 child chunks, **0 orphans**.
- **Embedding Integrity**: 2 true-leaf h2 chunks have null embeddings (FAIL). The 9 h1 and 8 h2 null embeddings are expected sub-split parents. Dim = 1536 on all populated rows.
  - **Affected chunk 1:** `92a885a1-e661-4f7f-86d2-a6ac738d14c5` — `Appendix 3: Blood Pressure Levels For Girls By Age And Height Percentile`, 14,647 chars. Dense age/height/percentile table.
  - **Affected chunk 2:** `aa5b90c9-8c8f-45b6-b508-6b8dad94498a` — `Appendix 2: Blood Pressure Levels For Boys By Age And Height Percentile`, 14,640 chars. Dense age/height/percentile table.
  - Likely root cause: both chunks exceed the Bedrock Titan embedding input limit (~8,192 tokens). Neither has h3 sub-sections to split into, so the chunker left them as single oversized h2 leaves.
- **Metadata Coverage**: *Treatment* (71), *Special Populations* (40), *Reference* (16), *Assessment* (12), *Prevention* (12), *Diagnosis* (6), *Introduction* (6), *Epidemiology* (5), *Classification* (5).
- **Vector Search Test**: End-to-end search for "treatment" returns top match: *Appendix 1: Estimated BP Values After 2 Weeks* (sim=1.0000), followed by *7.9.1: Hypertension In Neonates And Infants* (0.6986) and *7.9.2: Hypertension In Children And Adolescents* (0.6199).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Healthy

- **Total Edges Extracted**: 887 clinical triples.
- **Relationship Breakdown**:
  - `INCREASES_RISK_OF`: 154
  - `INDICATED_FOR`: 148
  - `REDUCES_RISK_OF`: 104
  - `RECOMMENDED_FOR`: 93
  - `CAUSES`: 77
  - `CONTRAINDICATED_WITH`: 62
  - `REQUIRES_MONITORING`: 45
  - `ASSESSED_BY`: 42
  - `TREATS`: 38
  - `HAS_DOSAGE`: 33
  - `FIRST_LINE_FOR`: 33
  - `INTERACTS_WITH`: 26
  - `REQUIRES_DOSE_ADJUSTMENT`: 15
  - `OTHER`: 13
  - `SECOND_LINE_FOR`: 4
- **Severity Coverage**: **60.4%** (136/225) of safety-critical edges have severity markers — above the 30% threshold.
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` (887/887).
- **Cross-DB Linkage**: 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks.

---

## 3. Entity Normalisation Health
**Status:** ✅ Excellent

- **name_normalised**: 6,938/6,938 nodes (100%) have `name_normalised` populated.
- **Same-label duplicates (Bad)**: 0 detected — no normaliser regression introduced.
- **Cross-label duplicates (Safe)**: 516 nodes — expected behaviour. Notable new examples from this CPG:
  - *blood pressure control* split across `[DiagnosticTool]`, `[RiskFactor]`, `[Condition]`, `[Procedure]`
  - *prematurity* split across `[Condition]`, `[AdverseEvent]`, `[PatientProfile]`
  - *dyslipidaemia* split across `[RiskFactor]`, `[Condition]`, `[AdverseEvent]`
- **Overall duplication ratio**: 3.8% — under the 5% SOP threshold (MINOR, unchanged).

---

## 4. Cumulative Graph Health (SOP Step 5)
**Status:** ✅ Healthy

- **Step 5 — Cumulative health check** (`kg_verify.py`):
  - Total nodes: 6,938 | Total edges: 8,230 (+520 net nodes, +887 edges vs. pre-ingestion baseline)
  - 0 missing evidence, 0 orphan nodes, 10/10 PG cross-check pass.
  - "1 issue" = same 10 pre-existing duplicate triple patterns from cross-CPG cardiac overlap — unchanged.

---

## 5. Spotlight Extractions
High-value clinical triples extracted from this CPG (sampled 2026-05-18):

| Subject | Relationship | Object | Evidence |
|---|---|---|---|
| Hypertension | REQUIRES_MONITORING [MAJOR] | Blood Pressure Assessment | "It is very important to ascertain hypertension and the true level of BP before commencing or adding…" |
| Hypertension | REQUIRES_MONITORING | Adverse Reaction | "During these visits, doctors should assess persistence of BP control, adverse reaction to treatment…" |
| Diltiazem | INDICATED_FOR | Rate Control Of Permanent Atrial Fibrillation | "For rate-control of permanent AF, β-blockers or non-dihydropyridine CCBs (verapamil, diltiazem) are preferred…" |
| Metoprolol | INDICATED_FOR | Heart Failure | "Metoprolol, bisoprolol, carvedilol, nebivolol — dose needs to be gradually titrated…" |
| Metoprolol | HAS_DOSAGE | 1 month–11 years: 1 mg/kg/dose (max 8 mg/kg/day); 12–17 years: 50–100 mg/day (max 200 mg/day) | "Metoprolol 1 month – 11 years: Initially 1 mg/kg/dose (Max 8 mg/kg/day or 200 mg/day)…" |

---

## 6. Known Issues & Remediation

| Issue | Severity | Status | Fix |
|---|---|---|---|
| `Appendix 2` (Boys BP table) — null embedding, 14,640 chars | FAIL (PG-3) | Open | Chunk exceeds Bedrock Titan input limit. Split into h3 subsections by age range (e.g. `### Ages 1–5`, `### Ages 6–10`, etc.) in the source markdown, then re-ingest with `--skip-graph`. KG side does not need re-extraction. See [SOP §Recovery PG-3](../Next-Step/SOP_Ingestion_Verification.md#L210-L223). |
| `Appendix 3` (Girls BP table) — null embedding, 14,647 chars | FAIL (PG-3) | Open | Same fix as Appendix 2 above. |
| `clinical_graph_lookup` smoke test returns 0 flags | WARN | Pre-existing / investigate separately | Not caused by this CPG — scenarios are AF/anticoagulation domain. Carried forward from prior verification sessions. |
| 10 duplicate triple patterns graph-wide | INFO | Acceptable | Pre-existing cross-CPG cardiac overlap, not introduced by this ingestion. |

======================================================================
❌ **1 FAIL — 2 oversized appendix table chunks have null embeddings; all other checks passed**
======================================================================
