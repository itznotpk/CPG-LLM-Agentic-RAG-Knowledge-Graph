# Step 06 — ICD-to-CPG Routing + Scoped Retrieval Tools

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) — read §3.7, §4 Steps F–G, §7 before starting.

Steps 01–05 are complete:
- `PatientCase`, `Recommendation`, `TreatmentPlan` Pydantic models exist in [agent/models.py](../agent/models.py).
- `documents` table has 16 CPG rows, all `scope_verified = TRUE`, with `icd11_scope TEXT[]` populated.
- `icd11_codes` has 3,914 rows across chapters 02, 05, 08, 11, 16, 17 with `embedding vector(1536)`.
- Existing retrieval tools (`vector_search_tool`, `hybrid_search_tool`, `graph_search_tool`) in [agent/tools.py](../agent/tools.py) work but are unscoped (search all chunks).

This is **Step 06 of 8**. Build the routing layer (Step F) and scope the retrieval tools (Step G).

---

## Objective

Two deliverables:

1. **`agent/routing.py`** — `route_icd_to_cpgs()` function that maps one ICD-11 code to a shortlist of CPG document IDs using structural matching first, semantic fallback second.
2. **Extend `agent/tools.py`** — add optional `document_id_filter: list[str] | None` to `vector_search_tool`, `hybrid_search_tool`, and `graph_search_tool`. When provided, restrict results to chunks whose `document_id` is in the filter. Backward compatible when `None`.

---

## Preconditions

### Database state
- `documents` table columns (already exist):
  ```
  id UUID PK | title TEXT | source TEXT
  icd11_scope TEXT[] | procedure_scope TEXT[] | scope_rationale TEXT
  scope_verified BOOLEAN | classified_at TIMESTAMPTZ | verified_at TIMESTAMPTZ | verified_by TEXT
  ```
- `icd11_codes` table columns (already exist):
  ```
  id SERIAL PK | code VARCHAR(20) UNIQUE | title VARCHAR(255) | description TEXT
  inclusions TEXT[] | exclusions TEXT[] | parent_code VARCHAR(20) | chapter VARCHAR(10)
  embedding vector(1536) | inclusion_embeddings JSONB DEFAULT '{}'
  ```
- `chunks` table (actual schema — do not recreate):
  ```
  id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4()
  document_id        UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE
  content            TEXT NOT NULL
  embedding          VECTOR(1536)
  chunk_index        INTEGER NOT NULL
  metadata           JSONB DEFAULT '{}'
  token_count        INTEGER
  created_at         TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
  parent_chunk_id    UUID REFERENCES chunks(id) ON DELETE SET NULL
  section_hierarchy  TEXT[]
  is_recommendation  BOOLEAN DEFAULT false
  is_table           BOOLEAN DEFAULT false
  is_algorithm       BOOLEAN DEFAULT false
  structured_content JSONB
  ```
  Indexes: IVFFLAT on `embedding`, GIN on `content` (trgm), BTREE on `document_id`, `chunk_index`, `parent_chunk_id`, `is_recommendation`, `is_table`, `is_algorithm`.

### icd11_scope values currently in documents (verified sample — read from DB before writing SQL)
Key examples:
- AF CPG: `['BC81.3']`
- HTN CPG: `['BA00', 'BA01', 'BA02', 'BA03', 'BA04']`
- HF CPG: `['BD10', 'BD11', 'BD12', 'BD13', 'BD1Z']`
- Stroke CPG: `['8B11']`
- STEMI CPG: `['BA41.0']`
- Dyslipidaemia CPG: `['5C80', '5C81', '5C82', '5C83', '5C84', '5C85', '5C8Z']`
- ED CPG: `['HA01.10', 'HA01.1Z']` (range-like but stored as discrete codes)
- Breast Cancer CPG: `['2C60', '2C61', '2C62', '2C63', '2C6Y', '2C6Z']`
- PAH CPG: `['BB01']`
- CVD Prevention Women: 20 codes (long list — query DB for truth)

### Existing code to read before writing
- [agent/tools.py](../agent/tools.py) — `vector_search_tool`, `hybrid_search_tool`, `graph_search_tool` signatures and input models
- [agent/db_utils.py](../agent/db_utils.py) — `vector_search()`, `hybrid_search()` functions and `db_pool` global
- [agent/providers.py](../agent/providers.py) — `get_embedding_client()`, `get_embedding_model()`

---

## Deliverable 1: `agent/routing.py`

### Data model

```python
from pydantic import BaseModel
from typing import Literal

class CPGDocRef(BaseModel):
    document_id: str          # UUID as string
    title: str
    match_type: Literal["exact", "parent", "semantic"]
    score: float              # 1.0 for structural matches, cosine score for semantic
    matched_scope: str        # which scope entry triggered the match, e.g. "BC81" or "semantic:0.87"
```

### Main function

```python
async def route_icd_to_cpgs(
    icd_code: str,
    top_k: int = 3,
    semantic_threshold: float = 0.60,
) -> list[CPGDocRef]:
```

Returns up to `top_k` CPG documents that cover `icd_code`. Always tries structural first; semantic fallback only fires when structural returns 0 results.

### Matching logic

#### Stage 1 — Structural match (SQL)

Three sub-passes in one SQL query using a CASE expression to determine match type:

```sql
SELECT
    id::text AS document_id,
    title,
    icd11_scope,
    CASE
        WHEN $1 = ANY(icd11_scope)                   THEN 'exact'
        WHEN LEFT($1, 3) = ANY(icd11_scope)          THEN 'parent'
        WHEN LEFT($1, 4) = ANY(icd11_scope)          THEN 'parent'
        WHEN _icd11_range_match($1, icd11_scope)     THEN 'range'
        ELSE NULL
    END AS match_type
FROM documents
WHERE scope_verified = TRUE
  AND (
      $1 = ANY(icd11_scope)
      OR LEFT($1, 3) = ANY(icd11_scope)
      OR LEFT($1, 4) = ANY(icd11_scope)
      OR _icd11_range_match($1, icd11_scope)
  )
```

`_icd11_range_match(code TEXT, scope TEXT[]) RETURNS BOOLEAN` — a Python helper (not SQL function, to avoid schema changes). Logic:
- Scan each element of `scope`; if it matches pattern `^[A-Z0-9]{2,4}-[A-Z0-9]{2,4}$`, split on `-`, check `low <= code <= high` (lexicographic, which is valid for ICD-11 alphanumeric codes within the same prefix).
- Return True if any range matches.

Implement as a Python function `_icd11_range_match(code: str, scope: list[str]) -> bool` called in Python after the `ANY()` checks fail, or use it as an additional filter row by row.

**Simpler alternative (recommended):** Run one SQL query for exact + parent matches (these cover >95% of real cases), then apply range matching in Python on the full `scope_verified = TRUE` document set if needed. Avoids custom SQL functions.

```python
async def _structural_match(conn, icd_code: str) -> list[CPGDocRef]:
    rows = await conn.fetch("""
        SELECT id::text, title, icd11_scope
        FROM documents
        WHERE scope_verified = TRUE
          AND (
              $1 = ANY(icd11_scope)
              OR LEFT($1, 3) = ANY(icd11_scope)
              OR LEFT($1, 4) = ANY(icd11_scope)
          )
    """, icd_code)

    results = []
    for row in rows:
        if icd_code in row["icd11_scope"]:
            match_type, matched = "exact", icd_code
        elif any(icd_code.startswith(s) and len(s) <= len(icd_code) for s in row["icd11_scope"]):
            # find longest matching prefix
            match_type = "parent"
            matched = next(s for s in sorted(row["icd11_scope"], key=len, reverse=True)
                           if icd_code.startswith(s))
        results.append(CPGDocRef(document_id=row["id"], title=row["title"],
                                 match_type=match_type, score=1.0, matched_scope=matched))
    return results
```

Then for range matching, fetch ALL scope_verified documents and do Python-side range check:

```python
async def _range_match(conn, icd_code: str) -> list[CPGDocRef]:
    rows = await conn.fetch("""
        SELECT id::text, title, icd11_scope
        FROM documents WHERE scope_verified = TRUE
    """)
    results = []
    for row in rows:
        for entry in row["icd11_scope"]:
            if "-" in entry:
                parts = entry.split("-", 1)
                if len(parts) == 2 and parts[0] <= icd_code <= parts[1]:
                    results.append(CPGDocRef(..., match_type="exact", matched_scope=entry, score=1.0))
                    break
    return results
```

Deduplicate by `document_id` across exact + parent + range results.

#### Stage 2 — Semantic fallback

Only executed when structural returns 0 results.

```python
async def _semantic_fallback(conn, icd_code: str, top_k: int, threshold: float) -> list[CPGDocRef]:
    # 1. Look up the ICD code's title + description from icd11_codes
    row = await conn.fetchrow(
        "SELECT title, description FROM icd11_codes WHERE code = $1", icd_code
    )
    if not row:
        # Unknown code — embed the raw code string
        query_text = icd_code
    else:
        query_text = row["title"]
        if row["description"]:
            query_text += ". " + row["description"]

    # 2. Embed query_text using generate_embedding (from agent.tools)
    query_embedding = await generate_embedding(query_text)

    # 3. Cosine search against documents.title_embedding
    #    IMPORTANT: documents may not have title_embedding yet (see §Migration note below)
    #    Fallback to embedding the scope_rationale text if title_embedding column doesn't exist
    ...
```

**Migration note for semantic fallback:** `documents` does not currently have a `title_embedding` column. You have two options:

**Option A (preferred — no schema change):** For the semantic fallback, embed the ICD code text and do a vector search against `chunks` restricted to `scope_verified = TRUE` documents. Use the existing `vector_search()` in `db_utils.py` but add a `document_ids` filter. Return the top-K unique document IDs from the chunk results.

```python
# Get IDs of all scope_verified documents
verified_doc_ids = await conn.fetch(
    "SELECT id::text FROM documents WHERE scope_verified = TRUE"
)
id_list = [r["id"] for r in verified_doc_ids]

# Scoped vector search (uses the new document_id_filter you'll add in Deliverable 2)
chunk_results = await vector_search(
    embedding=query_embedding,
    limit=top_k * 5,              # over-fetch for dedup
    document_id_filter=id_list
)

# Deduplicate: take top-K unique document_ids by best chunk score
seen = {}
for c in chunk_results:
    doc_id = str(c["document_id"])
    if doc_id not in seen or c["similarity"] > seen[doc_id]["score"]:
        seen[doc_id] = {"score": c["similarity"], "title": c["document_title"]}

return [
    CPGDocRef(document_id=doc_id, title=v["title"],
              match_type="semantic", score=v["score"],
              matched_scope=f"semantic:{v['score']:.2f}")
    for doc_id, v in sorted(seen.items(), key=lambda x: -x[1]["score"])
    if v["score"] >= threshold
][:top_k]
```

**Option B (if you need it — schema change):** Add `title_embedding vector(1536)` to `documents` and populate it. Only do this if Option A proves insufficient. Write a migration SQL file `sql/migrations/005_documents_title_embedding.sql` if you go this route.

Default to Option A.

### Full `route_icd_to_cpgs` flow

```python
async def route_icd_to_cpgs(
    icd_code: str,
    top_k: int = 3,
    semantic_threshold: float = 0.60,
) -> list[CPGDocRef]:
    async with db_pool.acquire() as conn:
        results = await _structural_match(conn, icd_code)
        if not results:
            results += await _range_match(conn, icd_code)

        # Remove duplicates (same document_id may appear from exact + range)
        seen_ids = set()
        deduped = []
        for r in results:
            if r.document_id not in seen_ids:
                seen_ids.add(r.document_id)
                deduped.append(r)
        results = deduped

        if not results:
            results = await _semantic_fallback(conn, icd_code, top_k, semantic_threshold)

    return results[:top_k]
```

Import `db_pool` from `agent.db_utils` and `generate_embedding` from `agent.tools`.

---

## Deliverable 2: Extend `agent/tools.py`

### Add `document_id_filter` to `vector_search_tool`

#### Input model change
```python
class VectorSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, description="Maximum number of results")
    document_id_filter: list[str] | None = Field(
        default=None,
        description="If provided, restrict results to chunks from these document UUIDs"
    )
```

#### Tool function change
```python
async def vector_search_tool(input_data: VectorSearchInput) -> list[ChunkResult]:
    embedding = await generate_embedding(input_data.query)
    results = await vector_search(
        embedding=embedding,
        limit=input_data.limit,
        document_id_filter=input_data.document_id_filter,  # NEW
    )
    ...
```

Apply the same pattern to `HybridSearchInput` / `hybrid_search_tool`.

For `graph_search_tool`: graph search operates on a separate Neo4j store. Add `document_id_filter: list[str] | None = None` to `GraphSearchInput` but **do not implement filtering inside Neo4j** — just accept the param and log a warning if non-None is passed ("graph_search_tool does not support document_id_filter; returning unscoped results"). This keeps the API consistent without requiring Neo4j schema changes.

### Extend `db_utils.py` — add `document_id_filter` to `vector_search` and `hybrid_search`

#### `vector_search`
```python
async def vector_search(
    embedding: list[float],
    limit: int = 10,
    document_id_filter: list[str] | None = None,
) -> list[dict]:
    async with db_pool.acquire() as conn:
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'

        if document_id_filter:
            # Cast each id to UUID for the ANY() clause
            results = await conn.fetch("""
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.content,
                    1 - (c.embedding <=> $1::vector) AS similarity,
                    c.metadata,
                    d.title AS document_title,
                    d.source AS document_source
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.document_id = ANY($3::uuid[])
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
            """, embedding_str, limit, document_id_filter)
        else:
            results = await conn.fetch(
                "SELECT * FROM match_chunks($1::vector, $2)",
                embedding_str, limit
            )
        return [...]
```

**Important:** The existing `match_chunks` SQL function does a full-table scan without filter. When `document_id_filter` is None, keep using it (backwards compatible). When `document_id_filter` is provided, inline the query with an `ANY($3::uuid[])` WHERE clause. Do NOT modify the `match_chunks` function — it may be used by other paths.

Apply the same pattern to `hybrid_search` — inline the SQL with an optional document filter when provided, fall through to `hybrid_search()` SQL function when None.

---

## Deliverable 3: Tests `tests/test_routing.py`

All tests use mocking — NO real DB, NO real embeddings, NO real WHO API.

### Required tests

#### Routing unit tests

- **`test_exact_match`** — `icd11_scope = ['BC81.3']`, query `BC81.3` → match_type `exact`, score 1.0.
- **`test_parent_3char_match`** — `icd11_scope = ['BC81']`, query `BC81.3` → match_type `parent`.
- **`test_parent_4char_match`** — `icd11_scope = ['BA41']`, query `BA41.0` → match_type `parent`.
- **`test_range_match`** — `icd11_scope = ['BC60-BC9Z']`, query `BC81` → match found.
- **`test_range_no_match`** — `icd11_scope = ['BC60-BC9Z']`, query `BA00` → no match.
- **`test_multi_code_dedup`** — document has `['BC81', 'BC81.3']`, query `BC81.3` → document appears once.
- **`test_semantic_fallback_fires_on_no_structural`** — structural returns [], semantic fallback is called.
- **`test_semantic_fallback_threshold`** — fallback result with score < threshold is excluded.
- **`test_semantic_fallback_skipped_when_structural_matches`** — structural returns 1 result → semantic fallback NOT called.
- **`test_unknown_icd_code_uses_raw_string`** — code not in `icd11_codes` table → raw code string is embedded.
- **`test_returns_at_most_top_k`** — 5 matching documents → only top_k=3 returned.
- **`test_empty_scope_verified_false`** — document with matching code but `scope_verified = FALSE` → NOT returned.

#### Scoped retrieval unit tests

- **`test_vector_search_with_filter`** — `document_id_filter=['uuid1']` → SQL query includes `ANY($3::uuid[])`, `match_chunks` not called.
- **`test_vector_search_without_filter`** — `document_id_filter=None` → `match_chunks` function is called (existing path).
- **`test_hybrid_search_with_filter`** — same pattern.
- **`test_graph_search_filter_logs_warning`** — `document_id_filter=['x']` → warning logged, results returned unscoped.

#### Integration smoke (mocked DB)

- **`test_route_then_filter_roundtrip`** — mock `route_icd_to_cpgs` returns `[CPGDocRef(document_id='abc', ...)]`; assert that `vector_search_tool` called with `document_id_filter=['abc']` uses the filtered path.

---

## Implementation guidance

- Import `db_pool` from `agent.db_utils` in `routing.py` — do NOT create a new connection pool.
- Import `generate_embedding` from `agent.tools` in `routing.py` — do NOT reimplement it.
- The `_range_match` Python path fetches all scope_verified documents (~16 rows) — this is fine, not a performance concern at this scale.
- `asyncpg` passes Python `list[str]` as `TEXT[]` to `ANY($n::uuid[])` — you need to pass it as a list, not a comma-joined string.
- Keep `CPGDocRef` in `routing.py`, not in `models.py` — it's routing-internal, not a user-facing schema type.
- Do NOT add `document_id_filter` to the `match_chunks` or `hybrid_search` SQL functions in the DB — keep all filter logic in Python/inline SQL to avoid requiring a DB migration.

---

## Out of scope

- ❌ Do NOT add `title_embedding` column to `documents` unless Option A (chunk-based semantic fallback) is genuinely insufficient and you've tried it.
- ❌ Do NOT modify the `icd11_codes` table or `icd11_codes` search path — DDx (Stage 2) is built in Step 07.
- ❌ Do NOT modify the clinical orchestrator, PatientCase handling, or TreatmentPlan synthesis — those are Steps 07–08.
- ❌ Do NOT wire `route_icd_to_cpgs` into the agent's tool registry yet — that's Step 08.
- ❌ Do NOT touch [ddx/](../ddx/) scripts.
- ❌ Do NOT add semantic CPG title embeddings unless structural + chunk-semantic fails a test case.

---

## Done criteria

All four must pass:

1. `pytest tests/test_routing.py -v` — all tests green, zero real DB/embedding/API calls.
2. Manual smoke (can be a quick script or added to `if __name__ == "__main__"` block in `routing.py`):
   ```python
   # python -c "import asyncio; from agent.routing import route_icd_to_cpgs; print(asyncio.run(route_icd_to_cpgs('BC81.3')))"
   # Expected: CPGDocRef with AF CPG document_id, match_type='exact' or 'parent', score=1.0
   ```
3. `vector_search_tool` called with `document_id_filter=['<any-uuid>']` returns only chunks from that document (verify with a real DB call or check the SQL branch logic in test).
4. `route_icd_to_cpgs('XX99ZZ')` (unknown code) returns at most `top_k` results with `match_type='semantic'` and no exception raised.

---

## Report back

When you finish, tell the user:

1. **Files created/modified** — exact paths.
2. **Routing test fixture** — paste the output of the manual `route_icd_to_cpgs('BC81.3')` smoke call.
3. **Test output** — last ~30 lines of `pytest tests/test_routing.py -v`.
4. **Option chosen for semantic fallback** — A (chunk-based) or B (title_embedding column) and why.
5. **Any deviations** from this brief and why.
6. **Follow-ups noticed but not done.**
