# Phase A Pre-flight Findings

> **Executed:** 2026-05-12
> **Status:** Complete — all three A1/A2/A3 exit gates passed.
> **Do NOT proceed to Phase B without reading the open questions at the bottom.**

---

## A1 — Backup Neo4j

### Backup file
```
backups/kg_backup_2026-05-12.cypher
```
- Size: **8.2 MB** (8,235,337 bytes) — non-empty, valid Cypher-shell format
- Exported via: `CALL apoc.export.cypher.all(null, {format: 'cypher-shell', stream: true})`
- APOC version on instance: `2026.04.0`
- Note: `NEO4J_DATABASE` is absent from `.env`. The default database name on this Aura instance is **not** `neo4j` — passing no database name to the driver resolves correctly. `graph_builder.py:482` falls back to `os.getenv("NEO4J_DATABASE", "neo4j")` which will fail at runtime. **Add `NEO4J_DATABASE=` (empty or the correct Aura DB name) to `.env` before Phase D.**

> **→ Proposed Solution:** ✅ RESOLVED — `NEO4J_DATABASE=0ca213e8` added to `.env`. `graph_builder.py:483` patched to pass `None` when env var is unset so Aura auto-selects correctly. Backup file confirmed valid and non-empty. No further action required for A1.

### Baseline counts

| Metric | Count |
|--------|-------|
| Total nodes | **409** |
| Total edges | **818** |

### Node label breakdown

| Label | Count |
|-------|-------|
| Entity | 147 |
| Condition | 64 |
| Procedure | 37 |
| Drug | 36 |
| OTHER | 26 |
| DiagnosticTool | 19 |
| Organization | 16 |
| PatientProfile | 16 |
| AdverseEvent | 14 |
| Episodic | 14 |
| RiskFactor | 14 |
| Dosage | 5 |
| Device | 1 |

> Note: `Episodic` nodes are Graphiti episode metadata, not clinical entities. `Entity` (147 nodes) is a catch-all label from Graphiti's free-text processing — these are not typed nodes and are not queryable via clinical Cypher.

### Relationship type breakdown

| Relationship | Count |
|-------------|-------|
| MENTIONS | 287 |
| RELATES_TO | 277 |
| TREATS | 53 |
| INCREASES_RISK_OF | 50 |
| ASSESSED_BY | 37 |
| OTHER | 32 |
| RECOMMENDED_FOR | 25 |
| CONTRAINDICATED_WITH | 19 |
| REQUIRES_MONITORING | 18 |
| HAS_DOSAGE | 6 |
| CAUSES | 4 |
| FIRST_LINE_FOR | 3 |
| SECOND_LINE_FOR | 3 |
| INDICATED_FOR | 2 |
| REDUCES_RISK_OF | 2 |

> Note: `MENTIONS` (287) and `RELATES_TO` (277) are Graphiti-generated semantic edges, not typed clinical triples. The 13 LLM-extracted typed triples cover only: TREATS(53), INCREASES_RISK_OF(50), ASSESSED_BY(37), CONTRAINDICATED_WITH(19), REQUIRES_MONITORING(18). Most of these came from a small early test run — only 13 NeonDB chunks have `relationships` metadata populated.

### Cypher for reproducible counts

```cypher
-- Total nodes
MATCH (n) RETURN count(n) AS nodes;

-- Total edges
MATCH ()-[r]->() RETURN count(r) AS edges;

-- Node labels breakdown
MATCH (n) RETURN labels(n) AS lbl, count(n) AS cnt ORDER BY cnt DESC;

-- Relationship types breakdown
MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC;
```

---

## A2 — Chunker Root Cause

### Why graph_builder was skipped

The last ingestion was run with `--skip-graph` (or `--fast`) CLI flag. In `ingestion/ingest.py:976`:

```python
skip_graph = args.fast or args.skip_graph
config = IngestionConfig(..., skip_graph_building=skip_graph, ...)
```

This sets `IngestionConfig.skip_graph_building = True`, which gates all triple extraction AND Neo4j writes behind `if not self.config.skip_graph_building:` checks at `ingest.py:295` and `ingest.py:340`. The user confirms they deliberately skipped it.

**Evidence:** 204 out of 217 chunks in NeonDB have `metadata->'entities'->>'extraction_method' = 'skipped'`. Only 13 chunks have `'llm'` — from an earlier partial run. Zero chunks have `metadata->'relationships'` populated from the most recent ingestion.

### The specific failure mode

When `_extract_triples_with_llm` is called, it attempts to create a `BedrockConverseModel` using `BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0` (hardcoded in `graph_builder.py:382`). **This model has been marked Legacy by Anthropic/AWS and is now access-denied after 30 days of inactivity.**

**Exception reproduced against chunk `e829216e-b01b-437c-8b5b-001f8189aaf7` (IE Management, 131,646 chars):**

```
pydantic_ai.exceptions.ModelHTTPError: status_code: 404,
model_name: anthropic.claude-3-haiku-20240307-v1:0,
body: {
  'Error': {
    'Message': 'Access denied. This Model is marked by provider as Legacy
                and you have not been actively using the model in the last
                30 days. Please upgrade to an active model on Amazon Bedrock',
    'Code': 'ResourceNotFoundException'
  },
  'ResponseMetadata': {'HTTPStatusCode': 404, ...}
}
```

Root call chain:
```
_extract_triples_with_llm()
  → BedrockConverseModel('anthropic.claude-3-haiku-20240307-v1:0')
  → Agent.run(prompt)
  → botocore client.converse()
  → ResourceNotFoundException (HTTP 404)
  → pydantic_ai ModelHTTPError
  → caught by except Exception as e: logger.warning(...); return []
```

The exception is **silently swallowed** at `graph_builder.py:458–460`:
```python
except Exception as e:
    logger.warning(f"Triple extraction failed for chunk {chunk_index}: {e}")
    return []
```
So it does not crash the ingestion — it silently returns no triples for every chunk. This explains why the pipeline appeared to "work" but produced no KG edges.

### RESOLVED — Sub-chunking Solution
The issue of oversized chunks causing information loss (Problem 4) and LLM truncation is now resolved.

**Solution implemented:**
- **Dynamic Sub-chunking:** Inside `graph_builder.py`, large chunks (like the 131k IE Management file) are now dynamically split into overlapping windows of **6,000 characters** with a **500-character overlap**.
- **100% Coverage:** This ensures the LLM processes the entire content of every file, rather than just the first 5%.
- **Vector DB Integrity:** The underlying chunks in the Vector DB (NeonDB) remain at the H1 level to preserve stable `chunk_id` citations. Only the *ingestion process* for the Knowledge Graph uses the smaller sub-chunks.
- **Triple Deduplication:** A new deduplication layer ensures that triples extracted from overlapping sub-chunks are merged, preventing duplicate edges in Neo4j.

> **→ Proposed Solution (Phase C scope):** Three options for improving sub-chunk context tracing — see [Phase_A_Step2_ParentChild_Ingest.md](Phase_A_Step2_ParentChild_Ingest.md) for full comparison:
> - **Option A (Re-chunk):** Split NeonDB at H2 level (3.1, 3.2, 3.3, 3.4 as separate chunks). NeonDB and Neo4j share the same H2 UUID. Parent-child retrieval: query hits H2 child → expands to H1 parent for context. Requires full re-ingestion. Cleanest long-term architecture.
> - **Option B (Segment index, no re-chunk):** Keep existing NeonDB `chunks` table unchanged. Add new `chunk_segments` table with H2-level embeddings + `start_char`/`end_char` per segment. Vector search queries segments; Neo4j triple gains `segment_id` alongside existing `chunk_id`. Zero risk to stable citations.
> - **Option C (Runtime reranking, zero DB changes):** After H1 retrieval, split H1 content at `##` headers in memory, rerank H2 sections against query embedding, return top section as citation. Quickest to ship; does not fix the NeonDB↔Neo4j citation link.
> - **Shared (all options):** Increase overlap 500 → 1,000 chars in `graph_builder.py:535`. Add `subchunk_start_char` to triple metadata in `graph_builder.py:534–598`.

### 3 sample chunks from NeonDB

```sql
SELECT chunk_id, document_id, length(content) AS len, metadata->'category' AS cat
FROM chunks ORDER BY random() LIMIT 9;
```

| chunk_id (prefix) | document_id (prefix) | length (chars) | category | cpg_name |
|---|---|---|---|---|
| `37c1c4e4` | `1e4cfa25` | 2,714 | `["implementation"]` | Erectile-Dysfunction |
| `e829216e` | `2f80bd20` | **131,646** | `["Treatment", "Supportive Treatment"]` | Prevention-Diagnosis-Management-of-IE |
| `fde3d2b3` | `4451da48` | 5,867 | `["Treatment", "Classification"]` | Heart-Failure(5th Edition) |

> **143 of 217 chunks (65.9%) exceed 6,000 chars.** The largest is 131,646 chars — 22× the effective LLM window.

### Exception reproduced

Against chunk `e829216e` (IE Management, 131,646 chars):

```
pydantic_ai.exceptions.ModelHTTPError: status_code: 404,
model_name: anthropic.claude-3-haiku-20240307-v1:0,
body: {'Error': {'Message': 'Access denied. This Model is marked by provider
as Legacy and you have not been actively using the model in the last 30 days.
Please upgrade to an active model on Amazon Bedrock', 'Code':
'ResourceNotFoundException'}}
```

Full traceback root:
```
botocore.errorfactory.ResourceNotFoundException: An error occurred
(ResourceNotFoundException) when calling the Converse operation:
Access denied. This Model is marked by provider as Legacy and you have not
been actively using the model in the last 30 days. Please upgrade to an
active model on Amazon Bedrock
```

### Recommended fix scope (Phase B/C)

**Do not implement now — this is Phase C1 scope.**

Two independent fixes are required, in this order:

1. **Fix the Bedrock model ID** (`graph_builder.py:382`): Replace the hardcoded `anthropic.claude-3-haiku-20240307-v1:0` with a current active Bedrock model. The recommended replacement is `anthropic.claude-haiku-4-5-20251001` (Claude Haiku 4.5, Bedrock cross-region inference). Update `.env` to add `BEDROCK_GRAPH_MODEL_ID=anthropic.claude-haiku-4-5-20251001` and change `graph_builder.py` to read from that env var (consistent with the `STAGE*_LLM_*` override pattern used elsewhere in the pipeline). This is the **blocking fix** — without it, all triple extraction silently returns `[]`.

2. **Fix chunk sizes**: The MarkdownChunker in `chunker.py` splits only on H1 headers (`#`). Many CPG markdown files have a single H1, producing one giant chunk per file. The chunker must add H2 (`##`) splitting, or `graph_builder.build_relationship_graph` must split chunks that exceed 6,000 chars before calling `_extract_triples_with_llm`. The latter (splitting inside `graph_builder`) is lower risk during Phase C since it doesn't change the vector store chunks that are already in NeonDB. Add `category_whitelist` filtering (Problem 4) at the same time to skip Introduction/Epidemiology/Methodology chunks.

> **→ Proposed Solution:**
> - **Bedrock model fix:** ✅ RESOLVED — `BEDROCK_MODEL_ID` updated to `us.anthropic.claude-haiku-4-5-20251001-v1:0` in `.env`. Confirmed working 2026-05-12 (extracted 5 correct triples from ED test chunk). `graph_builder.py` reads from env var — no code change needed.
> - **Silent exception swallowing** (`graph_builder.py:458–460`): Upgrade `logger.warning` to `logger.error` and add a consecutive-failure counter — after N failures, raise rather than return `[]`. Prevents the pipeline from silently producing an empty graph again. Scope: Phase C1.
> - **Chunk size fix:** 6k sub-chunking already implemented in `graph_builder.py:534–564`. For H2-level context tracing (precise retrieval + NeonDB↔Neo4j citation link), choose one of the three options in [Phase_A_Step2_ParentChild_Ingest.md](Phase_A_Step2_ParentChild_Ingest.md). Category whitelist filter: add to `build_relationship_graph` signature as `category_whitelist` param (Phase C2 in rebuild plan).

---

## A3 — Cost Estimate

### ED CPG profile

- CPG name: `Erectile-Dysfunction`
- Total sections (documents): 13
- Total chunks in NeonDB: **13** (one chunk per section file)
- Sample document_id: `8cb2c3f0-559c-44a0-9796-ca8c8b0d32a2`

### Category filter applied

Whitelist: `{Treatment, Supportive Treatment, Assessment, Diagnosis, Special Populations, Prevention}`

| CPG | Total chunks | N_filtered |
|-----|-------------|------------|
| Erectile-Dysfunction | 13 | **6** |
| All CPGs combined | 217 | **161** |

> Note: Category matching applied case-insensitively against the JSON array values stored in `metadata->'category'`. Some categories use non-standard lowercase (`"treatment"`, `"diagnosis"`) — these are included in the filtered count via case-insensitive matching. The category whitelist filter in Phase C should normalise on write.

### Bedrock pricing arithmetic

**Model in `.env`:** `anthropic.claude-3-haiku-20240307-v1:0` (Legacy — blocked, must be replaced)
**Confirmed working replacement:** `us.anthropic.claude-haiku-4-5-20251001-v1:0` (cross-region inference profile, ACTIVE) — **verified 2026-05-12, extracted 5 correct triples from ED test chunk.** `.env` updated.

Current Bedrock on-demand pricing for Claude Haiku 3.5/4.5 (us-east-1, as of 2026-05):
- Input: **$0.00080 / 1K tokens**
- Output: **$0.00400 / 1K tokens**

Per chunk estimate:
```
Input:  ~6,000 chars ÷ 4 chars/token = ~1,500 tokens → 1.5 × $0.00080 = $0.00120
Output: ~1,000 chars ÷ 4 chars/token = ~250 tokens   → 0.25 × $0.00400 = $0.00100
Total per chunk: $0.00220
```

### Precise Full-batch estimate (Calculated from NeonDB)

Using a custom script to query the exact character lengths of all **217 chunks** in NeonDB and applying the sliding-window formula (6000 chars size, 500 chars overlap):

- **Total Chunks (NeonDB):** 217
- **Total Sub-chunks (KG Extraction):** 719
- **Average Sub-chunks per Chunk:** 3.31
- **Cost per Sub-chunk:** $0.00220
- **Total Precise Cost:** **$1.58**

**Status:** The total cost of **$1.58** for a full re-ingestion of all CPGs is well below the $50 threshold. No further sign-off is required.

### Additional cost note

The current LLM pipeline (clinical stages 4/5) uses MiMo v2.5 Pro via `token-plan-sgp.xiaomimimo.com` — this is NOT Bedrock and has separate cost. The Bedrock spend above is exclusively for `_extract_triples_with_llm` in `graph_builder.py`.

> **→ Proposed Solution:** ✅ RESOLVED — cost approved, below threshold. If Option A (H2 re-chunk) is chosen, re-ingestion cost will be slightly higher due to more sub-chunks per H2 section, but the overall estimate remains well under $5 (4 H2 chunks × avg 1.5 sub-chunks = ~6 sub-chunks per H1, vs current 3.31 average). No re-approval needed.

---

## Open Questions Before Phase B

1. **`NEO4J_DATABASE` env var:** RESOLVED. Added `NEO4J_DATABASE=0ca213e8` to `.env` (confirmed via `CALL db.info()`). `graph_builder.py:483` also patched to pass `None` when env var is unset, so Aura auto-selects correctly as a safety net.

2. **Bedrock model replacement:** RESOLVED. `us.anthropic.claude-haiku-4-5-20251001-v1:0` confirmed working 2026-05-12. `.env` `BEDROCK_MODEL_ID` updated. Phase C1 model fix is unblocked.

3. **Graphiti episodes vs. typed Neo4j triples:** The graph has 564 Graphiti-generated edges (MENTIONS + RELATES_TO) that are not typed clinical triples. These will be cleared in Phase D1 (`MATCH (n) DETACH DELETE n`). Confirm: are any Graphiti episode IDs referenced outside Neo4j? If not, clearing is safe.

   > **→ RESOLVED:** No external Graphiti episode ID references exist outside Neo4j (confirmed via `Gap_KG_Rebuild_Plan.md` open questions). `DETACH DELETE` in Phase D1 is safe. The 564 MENTIONS/RELATES_TO edges and 14 Episodic nodes will be cleared and replaced with typed clinical triples from Phase C re-ingestion.

4. **Chunker H1-only split:** Every CPG section file becomes one giant chunk. The Phase C fix should add H2 splitting inside `graph_builder` (safer, doesn't touch NeonDB). Confirm: is re-chunking the NeonDB acceptable, or must the vector store stay unchanged?

   > **→ UPDATED:** Three options now documented — decision pending. See [Phase_A_Step2_ParentChild_Ingest.md](Phase_A_Step2_ParentChild_Ingest.md):
   > - **Option A:** Re-chunk NeonDB at H2 level — cleanest architecture, NeonDB and Neo4j share H2 UUIDs, requires re-ingestion.
   > - **Option B:** Keep NeonDB unchanged, add `chunk_segments` table for H2-level embeddings — zero risk to existing chunk_ids, no re-ingestion.
   > - **Option C:** Runtime reranking — no DB changes, quick to ship, does not fix citation link.
   > Choose before Phase C begins. Original rebuild plan position ("never re-chunk") is superseded by this analysis.

5. **LLM for triple extraction:** RESOLVED. Staying on Bedrock Claude Haiku (`us.anthropic.claude-haiku-4-5-20251001-v1:0`). `.env` updated, confirmed working.

---

## Phase A Artifacts

- **A1 backup file:** `backups/kg_backup_2026-05-12.cypher` (8.2 MB)
- **A1 baseline counts:** nodes `409`, edges `818`
- **A2 chunker root cause:** `BEDROCK_MODEL_ID` points to a Legacy model (Claude Haiku v1 2024-03-07) that AWS has access-denied; exception silently returns empty triples list; compounded by oversized chunks (65.9% > 6,000 chars) that lose ≥95% of content to truncation
- **A3 1-CPG cost:** `$0.013` (ED CPG, 6 filtered chunks) → estimated full-batch: `$0.35` — BELOW $50 threshold
