# Ingest Audit — Atrial Fibrillation (2012) chunks dump

> **Date:** 2026-05-16
> **Source of evidence:** CSV export of `chunks` table filtered to `cpg_name = "Atrial-Fibrillation(2012)"` (~50 rows across sections 6, 8, 9, 10, 11, 12).
> **Scope:** Diagnose why the current DB state diverges from the chain-model design in [`tasks/Next-Step/Phase_A_Step2_ParentChild_Ingest.md`](Phase_A_Step2_ParentChild_Ingest.md), and propose a single re-ingest plan that fixes everything in one pass.

---

## 1. Executive summary

The chunks visible in the DB were written by **an older ingest run that pre-dates the chain-model refactor**, and that run was further degraded by **Bedrock Titan throttling**, **wrong-encoding markdown reads**, and **a partial abort** that left 6 of 12 section files un-ingested. The current code on disk (chunker + persistence) is correct in principle, but it has never been run end-to-end against this dataset.

Net effect:

- Vector retrieval is **unreliable** — many rows hold zero-vector placeholders that produce spurious nearest-neighbour hits.
- Hierarchical retrieval is **impossible** — every row is `chunk_level='h1_leaf'` with `parent_chunk_id=NULL`, so the H1/H2/H3 chain does not exist.
- KG citation linking is **broken** — `cap_split_h2_index` metadata points at H2 UUIDs that were never written.
- Content quality is **degraded** — UTF-8 mojibake (`â`, `Ã`, `â¥`) is baked into both the embedded text and the KG triples.

A single coordinated re-ingest after the fixes in §3 will resolve all 12 issues.

---

## 2. Observed issues and root causes

### Issue 1 — `chunk_level` is uniformly `'h1_leaf'`
**Observed:** Every row (H1 parents, H2 children, H3 sub-sections) carries `chunk_level='h1_leaf'`.

**Root cause:** Rows were written before the chain-model refactor. The chunker did not set `chunk_level`, so every insert took the schema default defined in [`sql/schema.sql:50`](../../sql/schema.sql). The new chunker in [`ingestion/chunker.py:260,322,335,375`](../../ingestion/chunker.py) explicitly emits `'h1' / 'h2' / 'h3'`, but it has not been re-run.

---

### Issue 2 — H1 parent rows are embedded with full content
**Observed:** Row `55297435` (section-8 chunk 0) holds the full 26 k-char document including `<!-- parent_only_reference_start -->` blocks, and has a real Titan vector.

**Root cause:** Same as #1. The current Pass-1 persistence at [`ingestion/ingest.py:909-931`](../../ingestion/ingest.py) stores `embedding=NULL` for H1 parents, but that branch never executed in the run that produced these rows.

---

### Issue 3 — `parent_chunk_id` is `NULL` everywhere
**Observed:** No chunk references a parent, even where `cap_split_h2_index` is present.

**Root cause:** The columns `parent_chunk_id`, `chunk_level`, `start_char`, `end_char` were added by [`sql/migrations/006_chunk_level_and_cleanup.sql`](../../sql/migrations/006_chunk_level_and_cleanup.sql). The old ingest code didn't write them. Pass-2 / Pass-3 wiring at [`ingestion/ingest.py:944-1019`](../../ingestion/ingest.py) is the only code path that links parents — and it didn't run.

---

### Issue 4 — Mass `ThrottlingException` → zero-vector rows
**Observed:** Most rows in sections 6, 9, 12 carry `embedding_error: "ThrottlingException ... reached max retries: 4"` and store `[0,0,0,...]` instead of an embedding.

**Root cause chain:**
1. `batch_size=100` ([`ingestion/embedder.py:44`](../../ingestion/embedder.py)) is too high for Bedrock.
2. Titan has no native batch endpoint — [`ingestion/embedder.py:146`](../../ingestion/embedder.py) issues 100 concurrent `invoke_model` calls via `asyncio.gather`.
3. Bedrock's Titan v1 per-account quota in `us-east-1` throttles bursts well below 100 RPS.
4. Retry only catches OpenAI `RateLimitError` ([`embedder.py:116-127`](../../ingestion/embedder.py)). The boto3 `ThrottlingException` falls through to the generic `Exception` arm — 3 retries, 1-second flat base delay, then re-raised.
5. Re-raised exception trips the batch fallback at [`embedder.py:272-282`](../../ingestion/embedder.py), which writes a 1536-dim zero vector.
6. Persistence inserts the zero vector unchecked — `vector(1536)` does not validate non-zero content.

---

### Issue 5 — *Withdrawn*
Originally flagged "wrong embedding model." Verified that `.env` sets `EMBEDDING_PROVIDER=bedrock` and `EMBEDDING_MODEL=amazon.titan-embed-text-v1`, which matches the CSV. Titan v1 is the **intended** embedder for the current build.

---

### Issue 6 — Mojibake (`â`, `Ã`, `â¥`)
**Observed:** Em-dashes appear as `â`, `≥` as `â¥`, `β` as `Ã`, etc. — across every section's content and into the chunk metadata `use_case` strings.

**Root cause:** Markdown source files are UTF-8 with multi-byte glyphs. [`ingest.py:_read_document`](../../ingestion/ingest.py) opens them with Windows' default `cp1252` codec, then the text is re-encoded as UTF-8 on its way to the DB. Every multi-byte char appears as the byte-level expansion. Corruption is baked into both the embedded text and the KG triples.

---

### Issue 7 — Sections 1–5 and 7 missing
**Observed:** CSV contains chunks only from sections 6, 8, 9, 10, 11, 12. Files for sections 1, 2, 3, 4, 5, 7 exist on disk.

**Root cause:** The run aborted. The most plausible chain: Bedrock throttling exceptions in the embedder eventually propagated past the per-file `try/except` in [`ingest.py:210-220`](../../ingestion/ingest.py), or the operator cancelled after seeing the error storm. The pipeline has **no resume / skip-already-ingested** logic, and every successful insert first runs `DELETE FROM chunks WHERE document_id = $1` ([`ingest.py:886-889`](../../ingestion/ingest.py)) — so re-running deletes prior partial state for the touched docs but never picks up the missing ones.

---

### Issue 8 — Entities `extraction_method: "skipped"`
**Observed:** Every `metadata.entities` block is empty with `"extraction_method":"skipped"`.

**Root cause:** Either the CLI was invoked with `--skip-graph`, or the same Bedrock/LLM throttling tripped the extractor. The branch at [`ingest.py:296-299`](../../ingestion/ingest.py) calls `extract_entities_from_chunks(use_llm=not self.config.skip_graph_building)`; when `use_llm=False`, `graph_builder` returns the empty stub with the `"skipped"` marker. Without entities, KG triple extraction has no anchors to attach to.

---

### Issue 9 — *Withdrawn*
Originally flagged "flat H2/H3, no real nesting beyond two levels" because Appendix C contains both `### C.1` and `### C.1.7.1` as siblings under `## Appendix C`.

On review, this is **intended behaviour, not a bug**. The dotted prefixes (`C.1`, `C.1.7`, `C.1.7.1`) are user-facing labels carried in the heading text, not structural depth. All such headings are genuine `###` siblings under `## Appendix C` in the source markdown. The existing 3-level chain (Section 12 → Appendix C → C.1.7.1) already provides enough synthesis context for retrieval — deepening to a 4-level model would require schema changes plus a Pass 2.5 in persistence with no measurable retrieval benefit.

No code change required. No fix step needed.

---

### Issue 10 — `start_char` / `end_char` inconsistencies
**Observed:** Section-10 H1 reports `end_char=523` for a 2,722-char file. Section-12 H1 reports `end_char=24,912` for a 24,913-char file. Section-8 H1 reports `end_char=26,007` for a 26,353-char file.

**Root cause:** The old chunker computed offsets two different ways depending on whether the file had H2s. When `##` sections existed it emitted an H1 row covering only the preamble (text before the first `##`), then H2 rows for each section. When `##` was absent or sparse, the H1 captured the full document. The current chunker locates `h1_start` via `stripped_content.find(h1_text[:80])` ([`chunker.py:242`](../../ingestion/chunker.py)) — still fragile when the preamble is short, but at least consistent. Either way, the rows in the CSV were produced by the inconsistent old behaviour.

---

### Issue 11 — Two H1 root chunks for section-10
**Observed:** `2bc9b4e1` is a section-10 H1 (chunk_index 1, content = `# Section 10: Referrals and Audit` + METADATA preamble only). `67aad333` is also a section-10 H1 (chunk_index 0, content = whole document). Both are tagged `h1_leaf`, both are embedded.

**Root cause:** Direct consequence of #10 — the old chunker emitted both the whole-doc representation **and** a preamble-only representation when H2 headers existed. Without `chunk_level` distinguishing them, both became indistinguishable `h1_leaf` rows that compete in retrieval. Today this would surface as a duplicate top-k hit for any query touching the section preamble.

---

### Issue 12 — `cap_split_h2_index` references that point nowhere
**Observed:** Rows `1e2b263b`, `5dadca46`, `63403f92`, `a2fdf1e0`, `e4d1099d`, `e009daf8` carry `"cap_split_h2_index": 4` or `11` in metadata, but no row exists with `chunk_level='h2'` and `cap_split=true` for those indices, and `parent_chunk_id` is NULL.

**Root cause:** Schema/code drift. The chunker began emitting `cap_split_h2_index` markers before the persistence learned to consume them. The current persistence resolves these markers via Pass-2's `h2_uuid_by_index` map ([`ingest.py:944-968`](../../ingestion/ingest.py)) and writes the resolved UUID into `parent_chunk_id` — but that path didn't run for these rows. The markers are dead pointers.

---

## 3. Proposed fix plan

A **single coordinated re-ingest** resolves issues 1, 2, 3, 7, 10, 11, 12 because they are all symptoms of "old code wrote the rows; new code never re-wrote them." Issues 4, 6, 8 need targeted code fixes **before** the re-ingest so that the new run doesn't reproduce them. Issue 9 is withdrawn — no fix required.

### Step 0 — Backup
1. `pg_dump` the `chunks` + `documents` tables (snapshot to `backups/chunks_pre_reingest_2026-05-16.sql`).
2. Snapshot Neo4j: `neo4j-admin database dump` or Cypher export to `backups/kg_pre_reingest_2026-05-16.cypher`.

> Rationale: every cause is reversible if we keep a snapshot. Aligns with the existing backup convention recorded in `MEMORY.md` (`backups/kg_backup_2026-05-12.cypher`).

### Step 1 — Fix the markdown read encoding *(Issue 6)*
- In [`ingestion/ingest.py:_read_document`](../../ingestion/ingest.py), open `.md` files with `open(path, 'r', encoding='utf-8', errors='strict')`. Add a test that asserts `'—' in content` for a known section file so cp1252 reads fail loud.
- Decision needed: whether to also normalize NBSP (` `) and curly quotes for embedding consistency.

### Step 2 — Tame Bedrock throttling *(Issue 4)*
Three changes in [`ingestion/embedder.py`](../../ingestion/embedder.py):
1. Lower `batch_size` default to **5** when `provider == 'bedrock'` (keep 100 for OpenAI).
2. Catch `botocore.exceptions.ClientError` and retry on `error.response['Error']['Code'] == 'ThrottlingException'` with exponential backoff + jitter (e.g. `min(60, 2**attempt + random.random())`).
3. **Stop writing zero vectors silently.** When a chunk fails after retries, set `embedding=None` and let the persistence skip the insert (or insert with `embedding IS NULL`). Update `match_chunks()` and `hybrid_search()` to already filter `embedding IS NOT NULL`, which they do per [`sql/migrations/007`](../../sql/migrations/007_chain_model_retrieval_functions.sql).

Optional follow-up: request a Bedrock service-quota increase for Titan v1 in `us-east-1`, or move embedding to OpenAI `text-embedding-3-small` (native batch, 3000 RPM at tier 1).

### Step 3 — Re-enable entity extraction *(Issue 8)*
- Confirm the ingest CLI is invoked **without** `--skip-graph`.
- Add a hard check in [`graph_builder.extract_entities_from_chunks`](../../ingestion/graph_builder.py) that raises if `use_llm=False` is silently in effect when the caller expects entities. Emit a clear log line: `entity_extraction=disabled because skip_graph_building=True`.

### Step 4 — *Withdrawn (was: four-level nesting for Issue 9)*
Issue 9 is intended behaviour. No schema or chunker change required. Step renumbering preserved below for traceability; Step 5 and Step 6 still apply.

### Step 5 — Wipe + re-ingest *(Issues 1, 2, 3, 7, 10, 11, 12)*
1. `DELETE FROM chunks; DELETE FROM documents;` (after Step 0 backup).
2. `MATCH (n) DETACH DELETE n` in Neo4j to clear KG.
3. Run `python -m ingestion.ingest markdown/` end-to-end on all 12 section files of `Atrial-Fibrillation(2012)`, plus the other CPGs that share the same broken state. Use the new chain-model code path (no flags overridden).
4. Estimate: ~50 chunks × ~12 sections × ~24 CPGs ≈ 14 k chunks. At Bedrock's throttled rate (~30 chunks/sec realistic with batch_size=5), full re-ingest ≈ 8 minutes of pure embedding time + KG extraction overhead. Budget for **~45 minutes** with LLM entity/triple extraction included.
5. Cost estimate: Titan v1 is $0.0001 / 1k tokens; ~14 k chunks × ~500 tokens average = 7 M tokens ≈ **$0.70**. LLM triple extraction with Sonnet 4.6 dominates at roughly **$3-$5** depending on chunk volume.

### Step 6 — Verification queries
Run after re-ingest, paste outputs into this file:
```sql
-- All four chunk_level values present, in expected proportions
SELECT chunk_level, COUNT(*) FROM chunks GROUP BY chunk_level;

-- No orphan parent pointers
SELECT COUNT(*) FROM chunks c
WHERE c.parent_chunk_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM chunks p WHERE p.id = c.parent_chunk_id);

-- No zero-vector embeddings
SELECT COUNT(*) FROM chunks
WHERE embedding IS NOT NULL
  AND embedding::text LIKE '[0,0,0,%';

-- No mojibake
SELECT COUNT(*) FROM chunks WHERE content LIKE '%â%' OR content LIKE '%Ã%';

-- All 12 sections present per CPG
SELECT metadata->>'cpg_name' AS cpg, COUNT(DISTINCT metadata->>'source') AS section_files
FROM chunks GROUP BY 1 ORDER BY 2 DESC;
```

Expected:
- `h1`, `h2`, `h3`, `h1_leaf` all > 0, with `h2 + h3 + h1_leaf` >> `h1`.
- Orphan count = 0.
- Zero-vector count = 0.
- Mojibake count = 0.
- Section_files per CPG matches the count on disk.

---

## 4. Issue ↔ fix matrix

| Issue | Cause class | Fixed by step |
|---|---|---|
| 1. All `h1_leaf` | Stale rows | Step 5 (re-ingest) |
| 2. H1 parents embedded | Stale rows | Step 5 |
| 3. NULL `parent_chunk_id` | Stale rows | Step 5 |
| 4. Throttling → zero vectors | Code bug | Step 2, then Step 5 |
| 5. *(withdrawn)* | — | — |
| 6. UTF-8 mojibake | Code bug | Step 1, then Step 5 |
| 7. Missing sections 1–5, 7 | Partial abort | Step 5 |
| 8. Entities skipped | Misconfig / silent fallback | Step 3, then Step 5 |
| 9. *(withdrawn)* | — | — |
| 10. Offset inconsistencies | Stale rows | Step 5 |
| 11. Duplicate section-10 root | Stale rows | Step 5 |
| 12. Dead `cap_split_h2_index` | Stale rows | Step 5 |

Every remaining issue collapses into "code fixes (Steps 1–3) → wipe and re-ingest (Step 5) → verify (Step 6)."

---

## 5. Out of scope for this audit

- KG triple quality / Graphiti episode reconciliation — covered in the existing `Phase_A_Step3_Performance_Pass.md` plan.
- Retrieval-time scoring (hybrid weights, reranking) — depends on healthy embeddings being in place first.
- DDx routing changes — see `DDx_Routing_Robustness_And_Exclusion_Rerank.md`.
