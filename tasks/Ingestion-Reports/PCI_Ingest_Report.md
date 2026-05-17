# PCI (Percutaneous Coronary Intervention) Ingestion & Verification Report

## Executive Summary
The ingestion for the **Percutaneous-Coronary-Intervention** Clinical Practice Guideline (CPG) has been successfully completed and verified. 

Overall, **64 chunks** and **465 knowledge graph edges** were successfully generated for PCI. The ingestion perfectly parsed and embedded the document without any dropped true leaf chunks, and the global knowledge graph remains in excellent health with **0 broken links**.

---

## 1. Chunking & Embedding (Vector DB)
**Status:** ✅ Complete Success

- **Total Chunks**: 64 (8 H1 parents, 2 H1_leaf, 48 H2, 6 H3)
- **Parent-Child Linkage**: 54 child chunks were correctly linked to their H1/H2 parents, with **0 orphans**.
- **Embedding Integrity**: All true leaf chunks were embedded successfully (0 unexpected `null` vectors). The single null H2 chunk was correctly bypassed as a sub-split parent.
- **Metadata Coverage**: Automatically classified with tags like *Treatment* (43), *Classification* (13), and *Assessment* (11).
- **Vector Search Test**: End-to-end vector search for "treatment" works perfectly (top match: *7.1: Vascular Access Complications* with sim=1.0000).

---

## 2. Knowledge Graph Extraction (Neo4j)
**Status:** ✅ Complete Success (Neo4j Core Graph) | ⚠️ Warnings (Graphiti Endpoint)

- **Entities Extracted**: 465 new structured relationships were added.
- **Top Relationships**: `INDICATED_FOR` (121), `INCREASES_RISK_OF` (107), `REDUCES_RISK_OF` (66).
- **Safety Critical Info**: 61.9% of safety-critical edges successfully captured severity markers (e.g. `[MAJOR]`).
- **Data Integrity**: 100% of edges have valid `evidence_list` and `cpg_chunk_ids` safely referencing the Postgres vectors.
- 🟡 **Graphiti Warning**: The terminal output showed multiple HTTP 404 errors pointing to `token-plan-sgp.xiaomimimo.com`. **This is isolated to the secondary Graphiti API (episode generation).** The primary Neo4j knowledge graph extraction *succeeded*, which is why we successfully created 465 relationships.

---

## 3. Global Knowledge Graph Health 
**Status:** ✅ Excellent

Global graph integrity checks confirm:
- **Total Nodes Normalized**: All 2,037 nodes correctly populated their `name_normalised` fields.
- **Orphans**: 0 orphaned chunks.
- **Cross-DB Linkage**: 100% of randomly sampled node UUIDs correctly resolve back to Postgres vector chunks.
- **Node Duplication**: 0 same-label duplicates detected.

======================================================================
✅ **ALL CHECKS PASSED — CPG ingested cleanly**
======================================================================
