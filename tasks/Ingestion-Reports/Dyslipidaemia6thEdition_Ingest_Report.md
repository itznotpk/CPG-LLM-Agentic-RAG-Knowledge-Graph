# Ingestion Report — Management of Dyslipidaemia 2023 (6th Edition)

**Date:** 2026-05-19
**CPG folder:** `markdown/Dyslipidaemia(6th-Edition)/`
**Sections ingested:** 15 (14 sections + appendices)
**Verification SOP:** `tasks/Next-Step/SOP_Ingestion_Verification.md`

---

## 1. Document & Chunking Statistics

| Metric | Value |
|---|---|
| Document rows (Postgres) | 15 |
| Total chunks | 93 |
| h1 chunks | 13 |
| h1_leaf chunks | 2 |
| h2 chunks | 54 |
| h3 chunks | 24 |
| Null embeddings (h2/h3/h1_leaf) | 0 (4 are sub-split parents — expected) |
| Embedding dimension | 1536 (consistent across all) |
| Orphan chunks (no parent) | 0 |

**Category distribution:**

| Category | Chunks |
|---|---|
| Treatment | 56 |
| Prevention | 35 |
| Special Populations | 13 |
| Screening | 10 |
| Diagnosis | 9 |
| Pathophysiology | 7 |
| Assessment | 7 |
| Reference | 6 |
| Epidemiology | 4 |
| Introduction | 4 |

---

## 2. Knowledge Graph Extraction

| Metric | Value |
|---|---|
| Total edges created | 258 |
| Bedrock model (entity extraction) | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Throttling warnings | Several (429 ThrottlingException, auto-retried successfully) |

**Edges by relationship type:**

| Relationship | Count |
|---|---|
| INCREASES_RISK_OF | 64 |
| INDICATED_FOR | 36 |
| REDUCES_RISK_OF | 27 |
| CAUSES | 21 |
| RECOMMENDED_FOR | 20 |
| CONTRAINDICATED_WITH | 19 |
| ASSESSED_BY | 19 |
| TREATS | 12 |
| OTHER | 11 |
| INTERACTS_WITH | 11 |
| HAS_DOSAGE | 7 |
| FIRST_LINE_FOR | 6 |
| REQUIRES_MONITORING | 3 |
| REQUIRES_DOSE_ADJUSTMENT | 2 |

**Severity coverage:** 32/56 safety-critical edges have severity populated (57.1%) — above the 30% threshold (KG-2 ✅)

**Phase A regression check:** 258/258 edges have `evidence_list` and `cpg_chunk_ids` (KG-3 ✅)

**Cross-DB integrity:** 10/10 sampled `cpg_chunk_id` UUIDs resolve to Postgres chunks (KG-4 ✅)

---

## 3. Entity Normalisation Health

| Check | Result |
|---|---|
| `name_normalised` population | 10,138/10,138 nodes (100%) ✅ |
| Same-label duplicates (bad) | 0 ✅ |
| Cross-label duplicates (safe) | 885 nodes (expected — e.g., "blood pressure" split across `[Condition]`, `[RiskFactor]`, `[DiagnosticTool]`) |
| Overall duplication ratio (KG-7) | 4.5% (below 5% threshold — MINOR, manageable) ✅ |

---

## 4. Spotlight Extractions

High-value clinical triples extracted from this CPG:

1. **(Hypertension) -[INCREASES_RISK_OF]→ (Very High Risk)**
   > "Diabetes with proteinuria or with a major risk factor such as smoking, hypertension or dyslipidemia places patients in the Very High Risk category."

2. **(Statin) -[TREATS]→ (Nephrotic Syndrome)**
   > "There is limited data available on the use of lipid lowering therapies in nephrotic syndrome. Statins significantly reduced LDL-C and proteinuria."

3. **(Statin) -[INCREASES_RISK_OF]→ (New Onset Diabetes)**
   > "Risk of new onset diabetes should also be considered when prescribing statins in children with risk factors."

4. **(Statin) -[TREATS]→ (Dyslipidemia)** (CKD context)
   > "In patients with CKD, statins significantly reduced the risk of all-cause mortality, CV mortality and non-fatal MI."

---

## 5. Cumulative Graph Health (Post-Ingestion)

| Metric | Before | After | Delta |
|---|---|---|---|
| Total nodes | 9,728 | 10,138 | +410 |
| Total edges | 11,915 | 12,598 | +683 |
| Missing evidence | 0 | 0 | — |
| Orphan nodes | — | 303 | Pre-existing |
| Duplicate triple patterns | — | 10 | Pre-existing |

*Note: 303 orphan nodes and 10 duplicate triple patterns are pre-existing corpus-wide issues, not introduced by this ingestion.*

---

## 6. Smoke Tests

| Test | Result |
|---|---|
| PG-1 through PG-6 | ✅ All passed |
| KG-1 through KG-7 | ✅ All passed |
| Phase D polypharmacy wiring (Gate 1/2/3) | ✅ PASS (84 candidate drugs extracted) |
| Clinical graph lookup (`test_graph_clinical.py`) | ⚠ Warfarin/Digoxin and AF/Warfarin scenarios return 0 flags — **pre-existing gap**, not a regression from this ingestion (Phase D Gate 2/3 passed) |

---

## 7. Overall Result

```
✅ REMEDIATED & RE-VERIFIED (2026-05-20) — SOP ALL CHECKS PASSED
```

The cross-DB corruption documented in §8 was remediated on 2026-05-20 (clean delete + full re-ingest). See §9 for the remediation log and re-verification results. The original "all green" was invalidated by a deeper per-CPG check (§8); the corruption is now resolved, with one minor residual data-quality note (§9.3).

---

## 8. Post-Verification Incident — Chunk UUID Orphaning

**Discovered:** 2026-05-19, after the SOP report was first written.

### What happened

During verification, an accidental second invocation of `python -m ingestion.ingest --documents "markdown\Dyslipidaemia(6th-Edition)"` was started and then killed mid-run (~13/15 sections processed). The ingester at [ingest.py:855](ingestion/ingest.py#L855) executes:

```sql
DELETE FROM chunks WHERE document_id = $1::uuid
```

before re-inserting chunks, so chunk UUIDs are regenerated on every run. Neo4j edges (MERGE-idempotent on triple identity) retained the **original** UUIDs from the user's first ingest; Postgres now holds chunks with **new** UUIDs from the partial re-run. The two databases are out of sync.

### Damage measured

| Field | Resolves in Postgres | Orphaned |
|---|---|---|
| `cpg_chunk_id` (singular) on Dyslipidaemia edges | 2/32 | **30 (94%)** |
| `cpg_chunk_ids` (list) on Dyslipidaemia edges | 2/32 | **30 (94%)** |
| Distinct edges affected | — | 247 |
| Postgres chunks under Dyslipidaemia documents | 93 | (intact, but new UUIDs) |

The SOP KG-4 check passed earlier because it samples 10 random `cpg_chunk_id`s corpus-wide, not per-CPG. A per-CPG full check (`scratch/_dyslip_uuid_check2.py`) is what surfaced this.

### Required remediation

1. Delete all Dyslipidaemia edges from Neo4j:
   ```cypher
   MATCH ()-[r]->() WHERE r.source_document CONTAINS 'Dyslipidaemia' DELETE r
   ```
2. Delete Dyslipidaemia chunks + documents from Postgres:
   ```sql
   DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE source ILIKE '%Dyslipidaemia%');
   DELETE FROM documents WHERE source ILIKE '%Dyslipidaemia%';
   ```
3. Re-run full ingestion cleanly:
   ```
   python -m ingestion.ingest --documents "markdown\Dyslipidaemia(6th-Edition)"
   ```
4. Re-run SOP verification, including the per-CPG UUID resolution check (not just KG-4's corpus-wide 10-sample).

### Process improvement

SOP KG-4 should be amended to perform a **per-CPG full check** of `cpg_chunk_id` / `cpg_chunk_ids` resolution against Postgres, not a corpus-wide 10-sample. The 10-sample method missed a 94%-orphan condition on this CPG.

---

## 9. Remediation & Re-Verification (2026-05-20)

> **Two cleanup passes were required.** Pass 1 used a flawed edge filter and left most of the corruption behind; Pass 2 used the correct filter and fully resolved it. Both are documented below so the failure mode isn't repeated.

### 9.1 Pass 1 (incomplete) — and why it failed

`scratch/cleanup_dyslip.py` deleted Neo4j edges via `source_document CONTAINS 'Dyslipidaemia'`, then re-ingested. **This filter was wrong.** The CPG's section titles use mixed spelling and generic names — e.g. "Section 10: Management Of **Dyslipidemia**" (American), "Section 3: Classification Of **Dyslipidemia**", "Section 6: Target Lipid Levels". Only Section 7's title contains the British "Dyslipidaemia", so the filter deleted just **247 edges (≈ Section 7 only)** and left the stale corrupted edges from every other section untouched.

The re-ingest then MERGE'd fresh edges on top of the survivors. Triples that recurred had their `cpg_chunk_id` updated to a valid new chunk; triples unique to the old corrupted data kept their dead UUIDs. **The same `CONTAINS` blind spot also hid the damage during verification** — KG-4's 10-sample and the "strict per-CPG" check both used `CONTAINS 'Dyslipidaemia'`, so they only ever inspected Section 7 and reported a misleading "19.5%, Section-7-only" residual. A proper title-based audit (`scratch/_dyslip_proper_check.py`) revealed the truth: **63/133 distinct IDs orphaned (~47%), spread across 11 sections.**

### 9.2 Pass 2 (correct) — full remediation

`scratch/cleanup_dyslip_v2.py`:

1. **Neo4j** — deleted **878** edges matched by the **13 section titles unique to Dyslipidaemia**. The two generic titles ("Appendices", "Section 1: Introduction") were excluded because they collide with ~16 other CPGs *and* carry zero Dyslipidaemia edges, so excluding them is both safe and lossless. Verified 0 remaining.
2. **Postgres** — deleted 93 chunks + 15 documents by `metadata->>'cpg_name' = 'Dyslipidaemia(6th-Edition)'` (robust; no spelling dependency). Verified 0 remaining.
3. **Re-ingest** — `python -m ingestion.ingest --documents "markdown\Dyslipidaemia(6th-Edition)"`, exit 0, no Bedrock 404/`ResourceNotFoundException`. All 15 sections.

### 9.3 Re-verification results (post Pass 2)

| Check | Result |
|---|---|
| **Proper per-section `cpg_chunk_id` resolution** | **70/70 distinct IDs resolve — 0 orphans across all 11 edge-bearing sections** ✅ |
| PG-1..PG-6 | All ✅ (93 chunks, 0 leaf null embeddings, 0 orphan children, vector search OK) |
| KG-1 edges from CPG | 642 ✅ |
| KG-2..KG-7 | All ✅ (severity coverage, evidence_list/cpg_chunk_ids 100%, KG-4 10/10, name_normalised 100%, dupe ratio <5%) |
| Cumulative health | nodes → 10,451, edges → 12,538 (down vs 12,598 baseline: 878 stale edges removed, ~511 fresh added) |
| Clinical lookup smoke | Warfarin/Digoxin & AF/Warfarin = 0 flags — **pre-existing anticoagulation-domain gap, not a regression** |

**SOP footer: ✅ ALL CHECKS PASSED — CPG ingested cleanly.** The §8 corruption is fully resolved; 0 orphaned chunk references remain.

### 9.4 Side effect — orphan nodes (cosmetic)

Deleting 878 edges left entity nodes with no remaining relationships, raising corpus-wide orphan nodes from 303 (pre-existing) to **647**. These are inert (zero edges → unreachable by any traversal, including `clinical_graph_lookup`) and do not affect correctness. Optional cleanup: `MATCH (n) WHERE NOT (n)--() DELETE n`. Left in place pending a decision (it's a corpus-wide op that would also remove the 303 pre-existing orphans).

### 9.5 Process improvement

- **Never identify a CPG's edges by a spelling substring.** Use the full set of that CPG's section titles (from `documents` where `cpg_name = ...`), and exclude titles that collide with other CPGs (verify with a collision query first).
- The SOP's KG-4 and any "per-CPG" UUID check must derive the section-title set the same way — a `CONTAINS '<name>'` filter silently under-samples CPGs with mixed/American spelling or generic section names.

Diagnostic / remediation scripts: `scratch/_dyslip_proper_check.py` (authoritative per-section check), `scratch/cleanup_dyslip_v2.py`, `scratch/_orphan_rate_allcpg.py`. Superseded: `scratch/cleanup_dyslip.py`, `scratch/_dyslip_uuid_check2.py` (both rely on the flawed `CONTAINS` filter).

---

## Original (pre-incident) result

258 KG edges added, 0 embedding nulls, 0 orphan chunks, 0 same-label duplicates. Postgres and Neo4j were correctly populated by the user's original ingest — the cross-DB break was introduced afterwards by the accidental partial re-ingest documented in §8.
