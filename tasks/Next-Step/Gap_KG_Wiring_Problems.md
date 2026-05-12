# Knowledge Graph — Problem Map & Fix Plan

> Status snapshot: KG infrastructure exists (Graphiti + LLM triple extraction + typed Neo4j edges), but it is **not wired into the clinical pipeline** and several structural issues would make it produce poor answers even if it were wired today.
>
> This doc breaks the gap into 6 discrete problems, each with a short description, why it matters clinically, and the smallest viable fix.

---

## Problem 1 — The graph is never queried

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

---

## Problem 2 — The only graph search wrapper is the wrong shape

**What's wrong**
[tools.py:182](../../agent/tools.py#L182) `graph_search_tool` calls Graphiti's semantic `.search()`. It returns free-text "facts" (strings), runs an internal LLM rerank (slow), and **silently ignores `document_id_filter`** ([tools.py:194-196](../../agent/tools.py#L194-L196)) — so it mixes results from CPGs that weren't routed for this patient.

**Why it matters**
Semantic fact search cannot answer "is drug X contraindicated with drug Y" deterministically. The LLM rerank adds latency. Unscoped results pollute the synthesis prompt with off-protocol text.

**Fix**
Bypass `graph_search_tool` entirely for clinical lookups. Add a new `clinical_graph_lookup` function that takes structured params (drug list, condition list, allergy list) and runs typed Cypher directly via the existing `graph_client.graphiti.driver.session()`. Keep `graph_search_tool` available for free-text agent use, but the clinical pipeline doesn't use it.

**Effort:** 2 h | **Depends on:** nothing

---

## Problem 3 — Edge traceability is broken (chunk_index ≠ chunk_id)

**What's wrong**
[graph_builder.py:509](../../ingestion/graph_builder.py#L509) writes `r.chunk_index = $chunk_index` — an integer position in the document. The NeonDB chunk has a UUID `chunk_id`. There is no link between a graph edge and the actual evidence chunk in the vector store.

**Why it matters**
When the KG flags an interaction, the UI cannot click through to the source chunk. The gap doc requires `cpg_chunk_id` for clinical defensibility — every flag needs a traceable citation, not "see chunk #12 of the PAH CPG."

**Fix**
Modify `_extract_triples_with_llm` and `build_relationship_graph` ([graph_builder.py:533](../../ingestion/graph_builder.py#L533)) to accept and forward the NeonDB `chunk_id` (UUID). Change the Cypher in `_write_triples_to_neo4j` to set `r.cpg_chunk_id = $chunk_id`. Keep `chunk_index` for backwards compat but make `cpg_chunk_id` the primary join key.

**Effort:** 1 h code + re-ingestion | **Depends on:** Problem 4 (do them together)

---

## Problem 4 — Coverage is patchy and unscoped

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

---

## Problem 5 — Schema gaps block the high-value queries

**What's wrong**
- `(:Condition)` nodes have **no `icd11_code`** property → cannot traverse `DDx code → first-line drug`.
- No `severity_field` on Condition → cannot filter "first-line for NYHA III" vs "NYHA II".
- Relation taxonomy ([graph_builder.py:59-73](../../ingestion/graph_builder.py#L59-L73)) has a single `CONTRAINDICATED_WITH` bucket — no severity (MAJOR vs MINOR), no `INTERACTS_WITH`, no `CROSS_REACTS_WITH` for allergens, no `REQUIRES_DOSE_ADJUSTMENT` with trigger thresholds.

**Why it matters**
Without ICD codes on nodes, you can't go from "DDx says BA00" to "first-line drugs are X, Y, Z". Without severity on contraindication edges, every flag looks equally urgent — clinicians ignore the noise.

**Fix**
1. **Add `icd11_code` via Cypher batch** — match Condition nodes by name to a lookup table (use `ddx/` data as the source). One-off script, idempotent.
2. **Expand the relation taxonomy** in `CLINICAL_RELATION_TYPES`:
   - `INTERACTS_WITH` (with `severity` property: MAJOR/MODERATE/MINOR)
   - `CROSS_REACTS_WITH` (with `risk_pct` property)
   - `REQUIRES_DOSE_ADJUSTMENT` (with `trigger` property, e.g. "eGFR<30")
3. **Update the extraction prompt** ([graph_builder.py:393](../../ingestion/graph_builder.py#L393)) to ask for these properties explicitly when present in the source text.

**Effort:** 4 h schema + re-ingestion (covered by Problem 4 batch run)

---

## Problem 6 — Name fragmentation will silently break Cypher queries

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
