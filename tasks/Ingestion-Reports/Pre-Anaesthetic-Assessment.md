# Ingestion Verification Report
**CPG Title:** Recommendations on Pre-Anaesthetic Assessment
**Verification Date:** 2026-05-17
**Overall Status:** ✅ **PASSED (Clean Ingestion)**

---

## 1. Document & Chunking Statistics
- **Total Documents:** 9 Section-level documents
- **Total Chunks:** 27 (4 H1, 5 H1_leaf, 18 H2)
- **Hierarchy:** 18 child chunks (H2) perfectly linked to parents (0 orphans).
- **Embeddings:** 100% complete. 23 leaf chunks embedded using Amazon Titan v1 (dim=1536). Vector search verified functional.

**Sections ingested:**
- Section 1: Introduction
- Section 2: General Principles
- Section 3: Detecting Disease And Assessing Severity
- Section 4: Risk Assessment, Stratification And Disclosure
- Section 5: Consent
- Section 6: Pre-Operative Medication
- Section 7: Documentation
- Section 8: Pre-Anaesthetic Assessment Of Paediatric Patients
- Appendix: Recommended Pre-Anaesthetic Investigations

**Category distribution:** Predominantly `Assessment` (13) and `Reference` (11), with `Diagnosis` (5) and `Special Populations` (5) — consistent with the CPG's focus on pre-operative evaluation rather than treatment.

---

## 2. Knowledge Graph Extraction (Neo4j)
This CPG is primarily an assessment/diagnostic guideline rather than a pharmacological one, so edge counts are smaller but highly precise.
**Total New Edges Created:** 53

### Edge Type Breakdown
| Relationship | Count | Impact |
| :--- | :--- | :--- |
| `ASSESSED_BY` | 28 | **Pre-operative investigation → condition mappings** |
| `INDICATED_FOR` | 7 | Pre-op medication indications |
| `RECOMMENDED_FOR` | 7 | Standard assessment recommendations |
| `INCREASES_RISK_OF` | 4 | Perioperative risk factors |
| `REDUCES_RISK_OF` | 3 | Risk mitigation strategies |
| `HAS_DOSAGE` | 2 | Pre-medication dosing |
| `INTERACTS_WITH` | 1 | Drug interaction |
| `CONTRAINDICATED_WITH` | 1 | Hard stop |

### Extraction Quality Assessment
- **Severity Coverage:** **100%** of safety-critical edges (2/2) have severity ratings. Small sample but perfect coverage.
- **Traceability:** 100% of 53 edges have `evidence_list` and `cpg_chunk_ids` populated — zero evidence loss.
- **Cross-DB Integrity:** 7/7 sampled `cpg_chunk_id` UUIDs successfully resolved back to Postgres chunks.

---

## 3. Entity Normalisation Health
- **Total Graph Nodes:** Expanded to 1,096 nodes (up from 1,035 after Anaesthesia-Medication-Safety).
- **Normalisation Status:** 100% of nodes have `name_normalised`.
- **Duplicate Detection (KG-7 Check):**
  - **Bad Duplicates (Same-label):** **0** — normalisation is holding perfectly across 3 ingested CPGs.
  - **Safe Duplicates (Cross-label):** 52 nodes (slight increase from 48, as expected when new entities get categorised differently across CPGs).

---

## 4. Spotlight: High-Value Extractions
This CPG's strongest contribution is its **investigation-to-condition mappings** — structured data that is extremely difficult to retrieve via vector search alone.

> **`(Electrocardiogram) -[ASSESSED_BY]-> (Heart Disease)`**
> *Evidence: "Electrocardiogram (ECG) | 1. Heart disease, hypertension or chronic pulmonary disease..."*

> **`(Electrocardiogram) -[ASSESSED_BY]-> (Diabetes Mellitus)`**
> *Evidence: "Electrocardiogram (ECG) | 2. Diabetes mellitus..."*

> **`(Thyroid Function Test) -[ASSESSED_BY]-> (Thyroid Disease)`**
> *Evidence: "Thyroid function test | 2. History of thyroid disease..."*

> **`(Benzodiazepine) -[INDICATED_FOR]-> (Pre-Operative Sedation)`**
> *Evidence: "Pre-operative medication may be prescribed to facilitate the anaesthetic management..."*

---

## 5. Cumulative Graph Health (Post-Ingestion)
After ingesting 3 CPGs (AF + 2 Anaesthesiology):
- **Total nodes:** 1,096
- **Total edges:** 1,190
- **Overall duplication:** 2.4% (all cross-label, 0 bad duplicates)

---
**Verdict:** Clean ingestion. This CPG adds a unique **diagnostic/assessment layer** to the Knowledge Graph that complements the pharmacological data from the other CPGs. The `ASSESSED_BY` relationships enable the clinical agent to recommend pre-operative investigations based on patient comorbidities — a query pattern that vector search alone cannot answer.
