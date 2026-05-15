# DDx Routing Robustness + Exclusion-Aware Re-ranking

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](../IMPLEMENTATION.md) — read §1, §4 Step E, §7 before starting.

The ICD-11 ingestion (STEP_05, [tasks/Done/STEP_05_icd11_ingestion.md](../Done/STEP_05_icd11_ingestion.md)) loaded ~3,700 codes across chapters 02/05/08/11/16/17 with `title`, `description`, `inclusions`, `exclusions`, `parent_code`, `chapter`, `embedding (1536)`, `inclusion_embeddings (JSONB)`. Inclusion embeddings are backfilled and live in DDx ranking.

Two real gaps remain in the DDx → routing path:

1. **Routing dead-ends.** Stage 3 routes a predicted ICD-11 code to CPG documents whose `icd11_scope` array contains that code. When the prediction lands on a leaf code that no CPG explicitly lists (common for sub-codes of a parent the CPG *does* cover), we return 0 documents and the pipeline stalls — even though a clinically appropriate CPG exists one level up.
2. **Exclusions are dead weight.** WHO publishes `exclusions` per code (e.g. *"this code excludes type 1 diabetes"*) — these are the authors' own negative-evidence rules. We store them as TEXT[] and never use them. DDx ranking can quietly pick a code its own WHO record says is wrong.

Database state at handoff time:

```text
icd11_codes:    3,914 rows total
                inclusion_embeddings populated for all rows that have inclusions
                exclusion_embeddings column DOES NOT EXIST yet
                402 rows have non-empty exclusions[] (avg 1.86 per row)
                → backfill scope: ~748 Bedrock embedding calls, < $1, < 10 min
```

Phase A Step 2 ([Phase_A_Step2_ParentChild_Ingest.md](Phase_A_Step2_ParentChild_Ingest.md)) restructures the `chunks` table (h1/h2/h3 chain). **It does not touch `icd11_codes` or `documents.icd11_scope`** — the work in this doc is orthogonal and can be implemented and tested independently. Coordination note: smoke-test the routing changes (D1, D2, D4) against the post-Phase-A chunks table once A-13 lands; the ICD-side changes (D3) are completely independent of Phase A.

This task is **four independent deliverables**, ordered by independence so they can ship in separate PRs.

## Objectives

- **D1** — ICD-11 hierarchy fallback in Stage 3 routing using existing `parent_code`. No WHO API calls.
- **D2** — Semantic CPG fallback gated by D1 returning 0 hits. Requires a small `documents.scope_embedding` migration.
- **D3** — Exclusion-aware DDx re-ranking: schema migration + backfill + scorer change.
- **D4** — Out-of-scope detector: structured "no CPG matches" response when D1 + D2 both miss and ICD confidence is low.

## Preconditions

- Phase A Step 1 merged. Phase A Step 2 (re-ingest) **not required** for D1/D2/D3/D4 implementation, but the E2E smoke test in §6 expects it complete.
- `icd11_codes` matches the schema in STEP_05 §Preconditions. Verify before starting:
  ```sql
  SELECT COUNT(*) FROM icd11_codes;                         -- expect 3914
  SELECT COUNT(*) FROM icd11_codes WHERE cardinality(exclusions) > 0;  -- expect 402
  SELECT atttypmod FROM pg_attribute
   WHERE attrelid='icd11_codes'::regclass AND attname='embedding';     -- expect 1536
  ```
- `documents` table has `icd11_scope` populated and `scope_verified=TRUE` for all 16 CPGs.
- Embedding stack: `EMBEDDING_PROVIDER=bedrock`, `EMBEDDING_MODEL=amazon.titan-embed-text-v1`, `VECTOR_DIMENSION=1536`. Reuse `get_embedding_client()` / `get_embedding_model()` from [agent/providers.py](../../agent/providers.py).
- Read the existing routing code in `agent/clinical_stages.py` (Stage 3) and the DDx ranker that currently consumes `inclusion_embeddings` — match its style.

## Deliverables

### D1 — ICD-11 hierarchy fallback (routing)

**File touched:** `agent/clinical_stages.py` (Stage 3 routing), plus a small SQL helper in `agent/db_utils.py`.

Add a routing fallback that walks `parent_code` up the ICD-11 tree when an exact code returns 0 CPGs.

```python
async def find_cpgs_for_code(
    code: str,
    pool: asyncpg.Pool,
    max_depth: int = 2,
) -> tuple[list[Document], str]:
    """
    Returns (matched_documents, route_method).
    route_method ∈ {"exact", "ancestor_d1", "ancestor_d2", "sibling", "none"}

    1. Exact: documents.icd11_scope @> ARRAY[code]
    2. If 0: walk parent_code up to max_depth=2; retry exact match on each ancestor
    3. If still 0: try siblings — codes with same parent_code as the predicted code
    4. If still 0: return ([], "none") — D2 takes over
    """
```

Rules:
- `max_depth=2` is a hard cap. Going higher (chapter-level) is too broad to be clinically defensible.
- Sibling lookup runs **after** ancestor lookup, not before — siblings are usually clinical neighbours of equal specificity, ancestors are broader categories. Try the broader category first; siblings are a finer-grained second chance.
- Stamp `route_method` onto the routing result so downstream telemetry / clinician audit can see *which* path matched. Never silently fall through.

SQL helper for ancestor walk (single query, no recursion needed at depth 2):
```sql
WITH RECURSIVE ancestors AS (
  SELECT code, parent_code, 0 AS depth FROM icd11_codes WHERE code = $1
  UNION ALL
  SELECT c.code, c.parent_code, a.depth + 1
    FROM icd11_codes c JOIN ancestors a ON c.code = a.parent_code
   WHERE a.depth < $2
)
SELECT code, depth FROM ancestors WHERE depth > 0 ORDER BY depth;
```

### D2 — Semantic CPG fallback (gated)

**Files touched:** new migration `sql/migrations/007_documents_scope_embedding.sql`, new backfill script `ddx/backfill_scope_embeddings.py`, Stage 3 routing in `agent/clinical_stages.py`.

Migration:
```sql
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS scope_embedding vector(1536);
CREATE INDEX IF NOT EXISTS idx_documents_scope_embedding
  ON documents USING ivfflat (scope_embedding vector_cosine_ops) WITH (lists = 16);
```

Backfill: for each document, embed `f"{title}. {scope_rationale or ''}"` and write the vector. Idempotent — re-running with `--force` recomputes; default skips rows already populated.

Routing change in Stage 3: if `find_cpgs_for_code()` from D1 returns `route_method == "none"`:
```python
sims = cosine_similarity(query_embedding, all_documents.scope_embedding)
candidates = [(doc, sim) for doc, sim in sims if sim >= SEMANTIC_FALLBACK_THRESHOLD]
candidates.sort(key=lambda x: -x[1])
return candidates[:3], "semantic"
```

Constants (place near the top of the routing module, not magic numbers in the function body):
```python
SEMANTIC_FALLBACK_THRESHOLD = 0.65   # tune empirically; log all near-misses for review
SEMANTIC_FALLBACK_TOP_K     = 3
```

Always log the similarity score with the result. Stamp `route_method = "semantic"` and include the score in the routing result so the clinician UI can show "matched on semantic similarity 0.71" instead of pretending it was a curated route.

### D3 — Exclusion-aware DDx re-ranking

**Files touched:** new migration `sql/migrations/008_icd11_exclusion_embeddings.sql`, new backfill script `ddx/backfill_exclusion_embeddings.py`, DDx ranker (find via `grep -r "inclusion_embeddings" --include="*.py"` — the exclusion logic is symmetric).

Migration:
```sql
ALTER TABLE icd11_codes
  ADD COLUMN IF NOT EXISTS exclusion_embeddings JSONB DEFAULT '{}';
```

JSONB shape: `{"<exclusion text>": [<1536-dim vector as list>], ...}` — exact mirror of `inclusion_embeddings`.

Backfill script `ddx/backfill_exclusion_embeddings.py`:
- Skip rows where `cardinality(exclusions) = 0`.
- Skip rows where `exclusion_embeddings` already has a key for every entry in `exclusions` (idempotent).
- Use the same embed text format as inclusions: just the exclusion phrase, raw.
- Batch in groups of 10 for fewer DB round-trips.
- CLI: `--dry-run` (no DB writes, no embedding calls), `--force` (recompute even if already populated), `--limit N` (for testing).

DDx ranker change — symmetric to existing inclusion logic:
```python
EXCLUSION_PENALTY_WEIGHT = 0.3   # λ — start here, tune from logged DDx outputs

inclusion_score = max(cosine(query_emb, v) for v in incl_embeddings.values()) if incl_embeddings else 0.0
exclusion_score = max(cosine(query_emb, v) for v in excl_embeddings.values()) if excl_embeddings else 0.0
final_score = base_score + inclusion_score - EXCLUSION_PENALTY_WEIGHT * exclusion_score
```

When an exclusion contributes a non-trivial penalty (`exclusion_score > 0.5`), surface the matched exclusion phrase in the DDx evidence trace so a clinician can see *why* a code was downranked. Do not silently penalize.

### D4 — Out-of-scope detector

**File touched:** Stage 3 routing in `agent/clinical_stages.py`.

Triggers when both:
1. `find_cpgs_for_code()` returned `route_method == "none"` (D1 missed)
2. D2 semantic fallback returned 0 candidates above threshold
3. AND the top-K ICD candidates for the query all have `inclusion_score < OUT_OF_SCOPE_INCL_THRESHOLD` (default 0.55)

Returns a structured response:
```python
{
  "route_method": "out_of_scope",
  "icd_candidates_considered": [...],
  "max_inclusion_score": 0.42,
  "message": "No loaded CPG covers this query. Top ICD-11 candidates: ...",
}
```

The downstream synthesis stage must check for `route_method == "out_of_scope"` and produce a clinician-facing "no matching CPG" answer rather than hallucinating from unrelated documents. Do not fall through to "use any CPG."

## Constants summary

Define once near the top of the routing module:
```python
ANCESTOR_MAX_DEPTH           = 2
SEMANTIC_FALLBACK_THRESHOLD  = 0.65
SEMANTIC_FALLBACK_TOP_K      = 3
EXCLUSION_PENALTY_WEIGHT     = 0.3
OUT_OF_SCOPE_INCL_THRESHOLD  = 0.55
```

All five are tunable. Log enough to tune them empirically from real DDx logs.

## Tests

`tests/test_routing_fallback.py` (D1 + D2 + D4):

- `test_exact_match_returns_route_exact` — code in `icd11_scope` of one doc → returns that doc, method="exact".
- `test_ancestor_d1_match` — predicted code's parent is in `icd11_scope` → method="ancestor_d1".
- `test_ancestor_d2_match` — grandparent is in scope → method="ancestor_d2".
- `test_ancestor_walk_capped_at_depth_2` — only chapter-root is in scope (depth 3+) → method="none".
- `test_sibling_match_when_no_ancestor` — sibling (same parent_code) is in scope → method="sibling".
- `test_sibling_only_after_ancestor` — both ancestor and sibling match → ancestor wins.
- `test_semantic_fallback_only_fires_when_d1_misses` — D1 returns docs → semantic never queried (mock asserts).
- `test_semantic_fallback_threshold_filters` — top similarity 0.60 < 0.65 threshold → returns 0 candidates.
- `test_semantic_fallback_returns_top_k_sorted` — 5 candidates above threshold → returns top 3 sorted desc.
- `test_out_of_scope_when_all_signals_weak` — D1 none + D2 none + max incl_score 0.40 → returns out_of_scope dict.
- `test_route_method_always_stamped` — every routing path returns a non-empty `route_method`.

`tests/test_exclusion_rerank.py` (D3):

- `test_exclusion_embedding_shape` — backfill embeds an exclusion → JSONB has `{phrase: [1536-float list]}`.
- `test_backfill_skips_empty_exclusions` — row with `exclusions=[]` → no embedding call, no DB write.
- `test_backfill_idempotent` — second run on same row → 0 embedding calls (mock assert).
- `test_backfill_force_recomputes` — `--force` → embedding called even if already populated.
- `test_ranker_penalizes_strong_exclusion_match` — query closely matches exclusion → final_score < base_score.
- `test_ranker_no_penalty_when_exclusions_empty` — row with no exclusions → score unchanged.
- `test_ranker_surfaces_matched_exclusion_in_trace` — exclusion_score > 0.5 → matched phrase appears in evidence trace.
- `test_dry_run_makes_no_db_writes` — `--dry-run` → pool.execute never called.
- `test_dry_run_makes_no_embedding_calls` — `--dry-run` → embedding client never called.

All tests must mock the WHO API (none should be called), the DB pool, and the embedding client. **No real Bedrock spend in pytest.**

## E2E smoke tests (manual, post-deploy)

Run these after merge, in order. Each one exercises a different fallback path. Capture the routing telemetry (`route_method`, scores) for each.

### Smoke 1 — Exact match (regression check)
Query: *"What is the recommended treatment for atrial fibrillation with rapid ventricular response?"*
- Expected predicted ICD: `BC81.3` (or similar AF code in scope)
- Expected `route_method`: `exact`
- Expected matched doc: `Atrial-Fibrillation` CPG

### Smoke 2 — Ancestor fallback (D1)
Query: *"My patient has hypotension during anaesthesia, what should I check?"*
- Expected predicted ICD: a leaf hypotension code (e.g. `BA21.0`)
- Expected `route_method`: `ancestor_d1` or `ancestor_d2` (since hypotension isn't an explicit `icd11_scope` entry)
- Expected matched doc: a Cardiology or Anaesthesia CPG via the BA20-BA2Z parent

### Smoke 3 — Semantic fallback (D2)
Query: *"Patient with persistent unilateral nasal obstruction and epistaxis — workup?"*
- Expected predicted ICD: an ENT code (chapter not loaded)
- Expected `route_method`: `semantic`
- Expected: top-K candidates with similarity scores logged; either matches a related CPG or proceeds to D4

### Smoke 4 — Exclusion penalty (D3)
Find a code in `icd11_codes` whose `exclusions` contains a clinically meaningful phrase (run `SELECT code, title, exclusions FROM icd11_codes WHERE cardinality(exclusions) > 0 LIMIT 20`). Construct a DDx query that closely matches an exclusion phrase. Verify:
- The code is downranked vs a baseline run (capture both DDx outputs side-by-side).
- The matched exclusion phrase appears in the evidence trace.

### Smoke 5 — Out-of-scope (D4)
Query: *"Best management of acute appendicitis in the ED?"* (no surgical CPG loaded)
- Expected `route_method`: `out_of_scope`
- Expected: structured response with `max_inclusion_score` reported; no CPG cited; clinician-facing message instead of hallucinated synthesis

### Smoke 6 — Idempotency
Re-run both backfill scripts with no args:
```bash
python -m ddx.backfill_scope_embeddings
python -m ddx.backfill_exclusion_embeddings
```
- Expected: 0 embedding calls, 0 DB writes, exit cleanly. Confirms idempotency.

## Out of scope

- ❌ Hybrid retrieval (vector + code-prefix + lexical) for ICD lookup. Defer until DDx logs show actual misses.
- ❌ Re-embedding the existing `icd11_codes.embedding` column. The main embedding stays as-is.
- ❌ Adding new ICD-11 chapters. Stick with the 5+1 already loaded.
- ❌ Touching `chunks` table — that's Phase A's territory.
- ❌ Modifying `documents.icd11_scope` for existing CPGs. The 16 verified entries are immutable.
- ❌ Changing the existing inclusion-based ranker logic. D3 *adds* an exclusion penalty term — it does not rewrite inclusion scoring.
- ❌ Real WHO API calls in tests.
- ❌ Tuning the five constants — ship with the defaults above and tune from real DDx logs in a follow-up.

## Done criteria

All eight must hold:

1. Migrations 007 and 008 applied cleanly. `\d documents` shows `scope_embedding vector(1536)`. `\d icd11_codes` shows `exclusion_embeddings jsonb`.
2. `python -m ddx.backfill_scope_embeddings` populates all 16 documents. Verify: `SELECT COUNT(*) FROM documents WHERE scope_embedding IS NOT NULL` returns 16.
3. `python -m ddx.backfill_exclusion_embeddings` populates the 402 rows with non-empty exclusions. Verify: `SELECT COUNT(*) FROM icd11_codes WHERE exclusion_embeddings != '{}'::jsonb` returns 402.
4. Re-running both backfills makes 0 embedding calls and 0 DB writes (idempotent).
5. `pytest tests/test_routing_fallback.py tests/test_exclusion_rerank.py -v` all green. No real Bedrock or WHO calls.
6. All five smoke tests in §6 produce the expected `route_method`. Telemetry is captured.
7. The 16 verified `icd11_scope` entries on existing documents are byte-for-byte unchanged. Verify: `SELECT title, icd11_scope, scope_verified FROM documents` matches the pre-deploy snapshot.
8. The existing `embedding` column on `icd11_codes` is byte-for-byte unchanged for all 3,914 rows. Verify with a checksum-style query before/after:
   ```sql
   SELECT MD5(string_agg(embedding::text, '|' ORDER BY code)) FROM icd11_codes;
   ```

## Report back

When you finish, return the following — concise, no marketing:

1. **Files created/modified** — exact paths.
2. **Migrations applied** — output of `\d documents` and `\d icd11_codes` (relevant columns only).
3. **Backfill results**:
   - `documents.scope_embedding`: rows populated, embedding calls made, runtime, total cost (Bedrock invocations × $0.0001 / 1k tokens estimate).
   - `icd11_codes.exclusion_embeddings`: rows populated (expect 402), embedding calls made (expect ~748), runtime, total cost.
4. **Idempotency check** — output of re-running both backfills (expect "0 rows updated").
5. **Test output** — last ~30 lines of `pytest tests/test_routing_fallback.py tests/test_exclusion_rerank.py -v`.
6. **Smoke test telemetry** — table with one row per smoke test:
   | Smoke # | Query (truncated) | Predicted ICD | route_method | Matched CPG | Notes |
   |---------|-------------------|---------------|--------------|-------------|-------|
7. **Pre/post invariants** — the two checksum/count queries in §Done criteria #7 and #8, before and after.
8. **Constants used** — confirm the five constants in §Constants summary are at their default values (and listed in code at the top of the routing module).
9. **Any deviations** from this brief and why.
10. **Follow-ups noticed but not done** — likely candidates: tuning the five constants from logged DDx data, adding hybrid retrieval if logs show ICD lookup misses, surfacing `route_method` in the clinician UI.
