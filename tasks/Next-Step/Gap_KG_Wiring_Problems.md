# Knowledge Graph — Problem Map & Fix Plan

> Status snapshot: KG infrastructure exists (Graphiti + LLM triple extraction + typed Neo4j edges), but it is **not wired into the clinical pipeline** and several structural issues would make it produce poor answers even if it were wired today.
>
> This doc breaks the gap into 6 discrete problems, each with a short description, why it matters clinically, and the smallest viable fix.

### Resolution Summary (updated 2026-05-17)

| Problem | Status | Resolved |
|---------|--------|----------|
| P1 — Graph is never queried | ✅ SOLVED | 2026-05-17 |
| P2 — Wrong graph search wrapper | ✅ SOLVED | 2026-05-16 |
| P3 — Edge traceability broken | ✅ SOLVED | 2026-05-16 |
| P4 — Coverage patchy / unscoped | ✅ SOLVED | 2026-05-16 |
| P5 — Schema gaps (relation taxonomy + prompt + evidence accumulation) | ✅ SOLVED | 2026-05-17 |
| P6 — Name fragmentation | ✅ SOLVED | 2026-05-16 |

---

## Problem 1 — The graph is never queried — ✅ SOLVED

**What's wrong**
[clinical_stages.py:427](../../agent/clinical_stages.py#L427) `stage_4_retrieve` only calls `vector_search_tool`. No code path in the clinical pipeline calls `graph_search_tool` or any Cypher query. Triples sitting in Neo4j have zero effect on the synthesised care plan.

**Why it matters**
Drug-drug interactions, allergy cross-reactivity, and comorbidity dose-adjustments live in the graph as typed edges with evidence, but the LLM never sees them. The Stage 5 prompt asks for `contraindications_checked` from the LLM's training memory — imperfect and unciteable.

**Fix**
After Stage 4 vector retrieval, run 3 narrow Cypher queries in parallel:
1. `(d1:Drug)-[:CONTRAINDICATED_WITH]-(d2:Drug)` where `d1.name IN $patient_meds` and `d2.name IN $retrieved_drugs`
2. `(d:Drug)-[:REQUIRES_MONITORING|HAS_DOSAGE]->(c:Condition)` where `c.name IN $comorbidities`
3. `(d:Drug)-[:CONTRAINDICATED_WITH]->(a)` where `a.name IN $allergies`

Inject results into Stage 5 as a structured `⚠ INTERACTION FLAGS` block prepended to the evidence text. Each flag carries `r.evidence` + `r.source_document` for citation.

**Effort:** 4 h | **Depends on:** nothing (uses current graph as-is)

> **✅ Resolution (2026-05-17):**
> Wired in Phase D across 3 files:
>
> **[agent/graph_clinical.py](../../agent/graph_clinical.py)** — added `extract_candidate_drugs_from_chunks(chunk_ids)`:
> - Takes Stage 4's retrieved chunk UUIDs, queries Neo4j for Drug nodes whose edges were sourced from those exact chunks (`WHERE r.cpg_chunk_id IN $chunk_ids`).
> - Grounds candidate drugs in the evidence the LLM is about to see — flags only fire for drugs the pipeline is actually considering, not the whole graph.
>
> **[agent/clinical_stages.py](../../agent/clinical_stages.py)** — `stage_5_synthesize` gains `flags: list[ClinicalFlag] | None = None`:
> - `format_flags_for_prompt(flags)` is prepended to `evidence_text` in the user prompt, before the retrieved chunks.
> - Backwards-compatible: callers that don't pass `flags` get `None` and the block reads `"INTERACTION FLAGS: None detected by knowledge graph."`.
>
> **[agent/clinical_workflow.py](../../agent/clinical_workflow.py)** — KG lookup block inserted between Stage 4 and Stage 5 in all 3 orchestrator paths (non-streaming, streaming, re-synthesis):
> ```python
> chunk_ids = [c.chunk_id for c in evidence]
> candidate_drugs = await extract_candidate_drugs_from_chunks(chunk_ids)
> kg_flags = await clinical_graph_lookup(
>     patient_meds=case.current_medications,
>     candidate_drugs=candidate_drugs,
>     comorbidities=case.comorbidities,
>     allergies=case.allergies,
> )
> treatment_plan = await stage_5_synthesize(..., flags=kg_flags)
> ```
> Wrapped in `try/except` — Neo4j failure degrades to `[]` flags, never crashes synthesis.
>
> **Gate: ✅ Passed** via [`scratch/test_phase_d_af.py`](../../scratch/test_phase_d_af.py) with an AF polypharmacy patient (warfarin + digoxin + metoprolol, HF + renal impairment comorbidities):
> - Gate 1 — 90 candidate drugs extracted from 50 AF chunks ✅
> - Gate 2 — 11 flags returned (INTERACTION, DOSE_ADJUSTMENT, MONITORING types) with evidence + Postgres chunk UUIDs ✅
> - Gate 3 — `format_flags_for_prompt` produces a 3215-char `INTERACTION FLAGS` block ✅

---

## Problem 2 — The only graph search wrapper is the wrong shape — ✅ SOLVED

**What's wrong**
[tools.py:182](../../agent/tools.py#L182) `graph_search_tool` calls Graphiti's semantic `.search()`. It returns free-text "facts" (strings), runs an internal LLM rerank (slow), and **silently ignores `document_id_filter`** ([tools.py:194-196](../../agent/tools.py#L194-L196)) — so it mixes results from CPGs that weren't routed for this patient.

**Why it matters**
Semantic fact search cannot answer "is drug X contraindicated with drug Y" deterministically. The LLM rerank adds latency. Unscoped results pollute the synthesis prompt with off-protocol text.

**Fix**
Bypass `graph_search_tool` entirely for clinical lookups. Add a new `clinical_graph_lookup` function that takes structured params (drug list, condition list, allergy list) and runs typed Cypher directly via the existing `graph_client.graphiti.driver.session()`. Keep `graph_search_tool` available for free-text agent use, but the clinical pipeline doesn't use it.

**Effort:** 2 h | **Depends on:** nothing

> **✅ Resolution (2026-05-16):**
> Created [`agent/graph_clinical.py`](../../agent/graph_clinical.py) with:
> - `clinical_graph_lookup()` — runs 3 typed Cypher queries sequentially (drug interactions, comorbidity flags, allergy cross-reactivity)
> - Returns structured `ClinicalFlag` dataclass objects with evidence + `cpg_chunk_id` citations
> - `format_flags_for_prompt()` — formats flags into a structured block for Stage 5 synthesis
> - Uses the existing Graphiti Neo4j driver connection (no second connection)
> - Graceful degradation — returns `[]` on failure, never crashes the pipeline
> - Smoke-tested with real data: correctly returned `MONITORING: Warfarin <-> Bleeding` with evidence and chunk UUID

---

## Problem 3 — Edge traceability is broken (chunk_index ≠ chunk_id) — ✅ SOLVED

**What's wrong**
[graph_builder.py:509](../../ingestion/graph_builder.py#L509) writes `r.chunk_index = $chunk_index` — an integer position in the document. The NeonDB chunk has a UUID `chunk_id`. There is no link between a graph edge and the actual evidence chunk in the vector store.

**Why it matters**
When the KG flags an interaction, the UI cannot click through to the source chunk. The gap doc requires `cpg_chunk_id` for clinical defensibility — every flag needs a traceable citation, not "see chunk #12 of the PAH CPG."

**Fix**
Modify `_extract_triples_with_llm` and `build_relationship_graph` ([graph_builder.py:533](../../ingestion/graph_builder.py#L533)) to accept and forward the NeonDB `chunk_id` (UUID). Change the Cypher in `_write_triples_to_neo4j` to set `r.cpg_chunk_id = $chunk_id`. Keep `chunk_index` for backwards compat but make `cpg_chunk_id` the primary join key.

**Effort:** 1 h code + re-ingestion | **Depends on:** Problem 4 (do them together)

> **✅ Resolution (2026-05-16):**
> `_extract_triples_with_llm` and `_write_triples_to_neo4j` in [`ingestion/graph_builder.py`](../../ingestion/graph_builder.py) now:
> - Accept `cpg_chunk_id` (UUID) from the chunk metadata
> - Write it to Neo4j edges via `ON CREATE SET r.cpg_chunk_id = $cpg_chunk_id`
> - Verified: **471/471 edges** in the current graph have `cpg_chunk_id`, and 10 sampled IDs cross-checked successfully against PostgreSQL chunks table

---

## Problem 4 — Coverage is patchy and unscoped — ✅ SOLVED

**What's wrong**
- `graph_builder` runs on **every chunk** including Introduction, Epidemiology, Methodology — wasted LLM calls, polluted graph.
- Many chunks have `extraction_method: "skipped"` because graph_builder was never run on them. Some CPGs have **no triples in Neo4j at all**.
- We deliberately skipped graph building during last ingestion because chunking caused issues (your note).

**Why it matters**
Sparse coverage = sparse interaction flags = clinicians lose trust in the feature. Background chunks in the graph create irrelevant or misleading edges.

**Fix**
Two-part:
1. **Filter ingestion by category.** In `build_relationship_graph`, accept `category_whitelist=["Treatment", "Assessment", "Special Populations", "Supportive Treatment"]` and skip chunks whose `metadata['category']` is outside it.
2. **Re-run on existing CPGs.** Add a CLI flag to `ingestion/ingest.py` like `--graph-only --categories Treatment,Assessment` that re-extracts triples without re-chunking or re-embedding. This is the "one-time batch" the gap doc calls for.

**Effort:** 3 h code + ~1 day batch run (LLM-bound) | **Depends on:** Problem 3

> **✅ Resolution (2026-05-16):**
> Added `CLINICAL_CATEGORY_WHITELIST` and `category_whitelist` parameter to `build_relationship_graph()` in [`ingestion/graph_builder.py`](../../ingestion/graph_builder.py):
> - Default whitelist: Treatment, Supportive Treatment, Assessment, Diagnosis, Special Populations, Prevention, Pharmacological Treatment, Non-Pharmacological Treatment, Management, Monitoring, Referral, plus `None` (for legacy chunks without category metadata)
> - Chunks outside the whitelist are skipped before LLM extraction
> - Logs skipped counts by category for transparency
> - Supports comma-separated and list-type category values
> - Can be overridden per-call with `category_whitelist=` parameter

---

## Problem 5 — Schema gaps block the high-value queries — ✅ SOLVED

**What's wrong** (original framing)
- ~~`(:Condition)` nodes have no `icd11_code` property → cannot traverse `DDx code → first-line drug`.~~ **Withdrawn — see resolution note.**
- Relation taxonomy ([graph_builder.py:59-73](../../ingestion/graph_builder.py#L59-L73)) has a single `CONTRAINDICATED_WITH` bucket — no severity (MAJOR vs MINOR), no `INTERACTS_WITH`, no `CROSS_REACTS_WITH` for allergens, no `REQUIRES_DOSE_ADJUSTMENT` with trigger thresholds.

**Why it matters**
Without severity on contraindication edges, every flag looks equally urgent — clinicians ignore the noise. Without distinct relation types, drug-drug interactions, allergy cross-reactivity, and dose adjustments all collapse into the same bucket.

**Fix**
1. **Expand the relation taxonomy** in `CLINICAL_RELATION_TYPES`:
   - `INTERACTS_WITH` (with `severity` property: MAJOR/MODERATE/MINOR)
   - `CROSS_REACTS_WITH` (with `risk_pct` property)
   - `REQUIRES_DOSE_ADJUSTMENT` (with `trigger` property, e.g. "eGFR<30")
2. **Update the extraction prompt** to ask for these properties explicitly when present in the source text, with strict null-when-absent rule.

> **✅ Resolution (2026-05-17):**
> - Items 3 + 4 + 6 of the [KG Remaining Edits Plan](KG_Remaining_Edits_Plan.md) shipped together in Phase A. `CLINICAL_RELATION_TYPES` expanded with the three new types, extraction prompt enriched with `severity` / `trigger` / `risk_pct`, controlled-vocab post-validation in place, evidence_list + cpg_chunk_ids accumulating with dedup. Read-side queries in `graph_clinical.py` updated to use the new relation types.
> - **ICD enrichment (item 8) was dropped.** After review, ICD codes do not belong on KG nodes:
>   - The KG is queried entity-first (drug/condition names from patient context), not by ICD code. No traversal path in the clinical pipeline starts from an ICD.
>   - ICD-to-CPG routing already lives at the Postgres layer ([routing.py](../../agent/routing.py)) where it belongs.
>   - Scoping the KG by ICD would suppress universal safety signals (e.g., a warfarin↔simvastatin interaction extracted from the Dyslipidaemia CPG must still fire for an AF patient on both drugs, even when only the AF CPG was routed).
>   - See [KG_Remaining_Edits_Plan.md → "Architectural decision"](KG_Remaining_Edits_Plan.md) for the full reasoning.

---

## Problem 6 — Name fragmentation will silently break Cypher queries — ✅ SOLVED

**What's wrong**
`MERGE (s:{subject_label} {name: $subject})` ([graph_builder.py:503](../../ingestion/graph_builder.py#L503)) matches on **exact string**. "Sildenafil", "Sildenafil 50mg", "sildenafil citrate" all become separate nodes. A query for `name: 'Sildenafil'` will miss most of the edges.

Also: `ON MATCH SET r.evidence = CASE WHEN r.evidence IS NULL THEN $evidence ELSE r.evidence END` ([graph_builder.py:513](../../ingestion/graph_builder.py#L513)) — the *first* extraction wins forever, even if a later chunk has stronger evidence.

**Why it matters**
You'll wire Problem 1 perfectly and see zero hits because patient med "Sildenafil" doesn't match graph node "sildenafil citrate (Viagra)". Looks like a bug in the lookup logic, but it's a data quality issue.

**Fix**
1. **Normalise on write.** In `_write_triples_to_neo4j`, lowercase + strip parenthetical brand names + strip dose suffixes before MERGE. Store original as `name_original`.
2. **Use `name_normalised` as MERGE key** with an index: `CREATE INDEX drug_norm_name FOR (d:Drug) ON (d.name_normalised)`.
3. **Normalise on read too.** The new `clinical_graph_lookup` (Problem 2) lowercases input drug names before Cypher.
4. **Append evidence on match.** Change `ON MATCH` to append additional evidence as a list, not lock in the first one.

**Effort:** 2 h code + re-ingestion (covered by Problem 4 batch run)

> **✅ Resolution (2026-05-16):**
> Added `_normalize_entity_name()` static method and `_ABBREV_MAP` to [`ingestion/graph_builder.py`](../../ingestion/graph_builder.py):
> - **Title-casing:** `"warfarin"` → `"Warfarin"`, `"atrial fibrillation"` → `"Atrial Fibrillation"`
> - **De-pluralization:** `"Strokes"` → `"Stroke"` (with protected suffixes: ss, us, is, sis, ics, ies)
> - **Abbreviation expansion:** 20 clinical abbreviation mappings (e.g., `"DCCV"` → `"Direct Current Cardioversion"`, `"ECG"` → `"Electrocardiography"`, `"LMWH"` → `"Low Molecular Weight Heparin"`)
> - Applied in `_write_triples_to_neo4j` before MERGE — all entity names are normalised at write time
> - Read-side normalisation added in `graph_clinical.py` via `_norm()` helper (lowercase + strip parentheticals + strip dose suffixes)
> - Audit before fix: 34 duplicate nodes (7.5%). Will be resolved on next re-ingestion.
> - **Note:** Evidence append (item 4) not yet implemented — deferred to P5 schema expansion

---

## Suggested execution order

| Step | Problems | Why this order | Effort |
|---|---|---|---|
| 1 | P2 + P1 | Wire reading first against current graph — proves the plumbing works, gets flags into the UI even with patchy data | 6 h |
| 2 | P6 | Normalisation fix — without it, P1 queries return mostly empty results | 2 h |
| 3 | P3 + P4 + P5 | Single re-ingestion batch covers all three: chunk_id, category filter, expanded schema | 1 day code + ~1 day batch run |

**Total:** ~3 days, sequenced so each step delivers visible value before the next starts.

---

## Out of scope (deliberate)

- ❌ Hardcoded `HIGH_RISK_PAIRS` Python table — the gap doc explicitly rules this out
- ❌ Manual Cypher inserts for interactions — every edge must come from CPG text so it has citation
- ❌ Replacing Graphiti — it's fine for free-text agent search; the clinical pipeline just shouldn't depend on it
