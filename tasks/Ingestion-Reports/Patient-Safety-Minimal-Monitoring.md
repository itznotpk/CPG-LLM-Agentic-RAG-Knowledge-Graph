# Ingestion Verification Report
**CPG Title:** Recommendations For Patient Safety And Minimal Monitoring Standards During Anaesthesia And Recovery
**Verification Date:** 2026-05-17
**Overall Status:** ✅ **PASSED (Clean Ingestion)**

---

## 1. Document & Chunking Statistics
- **Total Documents:** 9 Section-level documents
- **Total Chunks:** 54 (9 H1 parents, 45 H2 children)
- **Hierarchy:** 45 child chunks perfectly linked to parents (0 orphans).
- **Embeddings:** 100% complete. 45 H2 leaf chunks embedded using Amazon Titan v1 (dim=1536). 9 H1 parent chunks correctly left unembedded (by design). Vector search verified functional.

**Sections ingested:**
- Section 1: Principles Of Anaesthesia Care
- Section 2: The Anaesthetic Machine / Apparatus
- Section 3: Intraoperative Monitoring Of The Patient
- Section 4: Recovery From Anaesthesia
- Section 5: Anaesthesia Administered Outside The Operating Rooms
- Section 6: Regional Anaesthesia
- Section 7: Monitored Anaesthesia Care And Monitored Sedation
- Section 8: Pre-Anaesthetic Consultation
- Section 9: Resuscitation Facilities

**Category distribution:** Predominantly `Assessment` (46) and `Prevention` (43), with `Treatment` (25) — strongly aligned with this CPG's focus on intraoperative safety protocols and monitoring standards.

---

## 2. Knowledge Graph Extraction (Neo4j)
This CPG is a monitoring-heavy guideline, producing exactly the types of edges our clinical agent needs to flag missing equipment or unmonitored physiological parameters.
**Total New Edges Created:** 67

### Edge Type Breakdown
| Relationship | Count | Impact |
| :--- | :--- | :--- |
| `REQUIRES_MONITORING` | 26 | **Core value — maps equipment to physiological parameters** |
| `ASSESSED_BY` | 20 | Diagnostic tool to condition mappings |
| `RECOMMENDED_FOR` | 6 | Standard care recommendations |
| `OTHER` | 5 | Miscellaneous clinical associations |
| `INDICATED_FOR` | 5 | Equipment indications |
| `INCREASES_RISK_OF` | 4 | Risk factor associations |
| `CONTRAINDICATED_WITH` | 1 | Hard stop |

### Extraction Quality Assessment
- **Severity Coverage:** **37.0%** (10/27 safety-critical edges). This is lower than the previous CPGs because monitoring standards are often stated as procedural requirements without explicit severity language. The 10 edges that do have severity are high-confidence, including `[MAJOR]` ratings on equipment functionality checks.
- **Traceability:** 100% of 67 edges have `evidence_list` and `cpg_chunk_ids` — zero evidence loss.
- **Cross-DB Integrity:** 10/10 sampled `cpg_chunk_id` UUIDs successfully resolved back to Postgres chunks.

---

## 3. Entity Normalisation Health
- **Total Graph Nodes:** Expanded to 1,179 nodes (up from 1,096 after Pre-Anaesthetic-Assessment).
- **Normalisation Status:** 100% of nodes have `name_normalised`.
- **Duplicate Detection (KG-7 Check):**
  - **Bad Duplicates (Same-label):** **0** — normalisation continues to hold perfectly across all 4 ingested CPGs.
  - **Safe Duplicates (Cross-label):** 67 nodes (up from 52). New cross-label splits include 'circulation' appearing as `[DiagnosticTool]`, `[Condition]`, and `[Procedure]` — all valid clinical interpretations that our `clinical_graph_lookup` handles natively.
- **Overall Duplication Ratio:** 2.9% (all cross-label, fully safe).

---

## 4. Spotlight: High-Value Extractions
This CPG's strongest contribution is its **monitoring requirement mappings** — structured data that enables the clinical agent to flag when a patient is missing critical intraoperative monitoring.

> **`(Anaesthetic Machine) -[REQUIRES_MONITORING][MAJOR]-> (Equipment Functionality)`**
> *Evidence: "The anaesthetic machine or apparatus should be regularly maintained and functioning properly before..."*

> **`(Electrocardiogram) -[ASSESSED_BY]-> (Arrhythmia)`**
> *Evidence: "The ECG should be continuously displayed throughout the anaesthetic. While a normal ECG may be present..."*

> **`(Electrocardiogram) -[ASSESSED_BY]-> (Myocardial Ischaemia)`**
> *Evidence: "The ECG should be continuously displayed throughout the anaesthetic..."*

> **`(Transoesophageal Echocardiography) -[OTHER]-> (Cardiac Surgery)`**
> *Evidence: "Transoesophageal echocardiography (e.g., in cardiac surgery, or patients with severe cardiac disease..."*

---

## 5. Cumulative Graph Health (Post-Ingestion)
After ingesting 4 CPGs (Atrial Fibrillation + 3 Anaesthesiology):

| Metric | Value |
| :--- | :--- |
| **Total Nodes** | 1,179 |
| **Total Edges** | 1,257 |
| **Bad Duplicates** | 0 |
| **Overall Duplication** | 2.9% (all cross-label safe) |
| **name_normalised Coverage** | 100% |

---

## 6. Anaesthesiology Domain Summary (All 3 CPGs Combined)
With all 3 Anaesthesiology CPGs now ingested, the Knowledge Graph has a comprehensive perioperative safety layer:

| CPG | Edges | Top Relationship |
| :--- | :--- | :--- |
| Safe Use of Medication in Anaesthesia | 353 | `CAUSES` (64), `CONTRAINDICATED_WITH` (26) |
| Pre-Anaesthetic Assessment | 53 | `ASSESSED_BY` (28) |
| Patient Safety & Minimal Monitoring | 67 | `REQUIRES_MONITORING` (26), `ASSESSED_BY` (20) |
| **Domain Total** | **473** | — |

These 3 CPGs collectively enable the clinical agent to reason across the entire perioperative workflow: pre-op assessment → intraoperative monitoring → medication safety.

---
**Verdict:** Clean ingestion. The Anaesthesiology domain is now fully loaded. The graph can answer multi-hop questions like: *"For a patient with heart disease undergoing surgery, what pre-operative investigations are needed, what monitoring is required intraoperatively, and which medications are contraindicated?"*
