# Step 02 — Extend `documents` table with CPG scope columns

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) — read §1, §2, §3, §5.2 and §7.1 before starting.

This is **Step 02 of 8**. Step 01 added Pydantic schemas (`PatientCase`, `Recommendation`, `TreatmentPlan`) — done.

This step adds the **routing index** that lets Stage 3 (ICD → CPG routing) work. The system needs to know which CPG document covers which ICD-11 codes so a predicted ICD can be filtered down to the relevant document(s) before retrieval.

### Important architectural simplification (read carefully)

An earlier draft proposed a separate `cpg_documents` table and a new `cpg_id` foreign key on `chunks`. **That is NOT the approach.** After inspecting [sql/schema.sql](../sql/schema.sql), it's clear that:

- Every document in this system *is* a CPG. There is no other document type.
- `chunks.document_id` already references `documents.id` — no new FK is needed.

So scope metadata is added as **columns on the existing `documents` table**. No new table. No backfill on `chunks`. Routing will later filter `documents` by `icd11_scope` and join chunks via the existing `document_id`.

## Objective

Extend the `documents` table with seven new columns + one GIN index so future routing can filter CPGs by ICD-11 scope, and verify the change with a fixture-based test.

## Preconditions

- Read [sql/schema.sql](../sql/schema.sql) end-to-end before editing it.
- Read [agent/db_utils.py](../agent/db_utils.py) to understand how the project connects to Postgres (Neon) — match its patterns for the test.
- Database is **Neon Postgres** in production. Tables already exist: `documents`, `chunks`, `sessions`, `messages`, `icd11_codes`. Do not re-create them.
- Step 01 (clinical schemas) is complete — verify by importing `PatientCase` from [agent/models.py](../agent/models.py).
- `pgvector`, `uuid-ossp`, `pg_trgm` extensions are already enabled (per [sql/schema.sql](../sql/schema.sql) lines 4–6).

## Deliverables

### 1. Update [sql/schema.sql](../sql/schema.sql) (canonical schema for fresh installs)

In the `CREATE TABLE documents (...)` block (around lines 14–22), add the seven scope columns inline so a fresh `psql -f schema.sql` produces the new shape:

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    source TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- CPG scope (Stage 3 routing index)
    icd11_scope      TEXT[]      NOT NULL DEFAULT '{}',
    procedure_scope  TEXT[]      NOT NULL DEFAULT '{}',
    scope_rationale  TEXT,
    scope_verified   BOOLEAN     NOT NULL DEFAULT FALSE,
    classified_at    TIMESTAMP WITH TIME ZONE,
    verified_at      TIMESTAMP WITH TIME ZONE,
    verified_by      TEXT
);
```

Then, immediately after the existing index block (around line 25), add:

```sql
CREATE INDEX idx_documents_icd_scope ON documents USING GIN (icd11_scope);
CREATE INDEX idx_documents_scope_verified ON documents (scope_verified) WHERE scope_verified = TRUE;
```

Do not change anything else in `schema.sql`.

### 2. Create idempotent migration script `sql/migrations/001_documents_scope.sql`

`schema.sql` is destructive (`DROP TABLE IF EXISTS ... CASCADE`) so it can't be applied to a populated production DB. Create a separate migration file that only adds the new columns:

```sql
-- Migration 001: add CPG scope columns to documents
-- Idempotent: safe to run on populated DB.

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS icd11_scope      TEXT[]                   NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS procedure_scope  TEXT[]                   NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS scope_rationale  TEXT,
  ADD COLUMN IF NOT EXISTS scope_verified   BOOLEAN                  NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS classified_at    TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS verified_at      TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS verified_by      TEXT;

CREATE INDEX IF NOT EXISTS idx_documents_icd_scope
  ON documents USING GIN (icd11_scope);

CREATE INDEX IF NOT EXISTS idx_documents_scope_verified
  ON documents (scope_verified) WHERE scope_verified = TRUE;
```

Create the `sql/migrations/` directory if it doesn't exist.

### 3. Apply the migration to the live Neon DB

Run `sql/migrations/001_documents_scope.sql` against the production database. Use the same connection method `agent/db_utils.py` already uses (read it to find the env var — likely `DATABASE_URL`). Verify by running:

```sql
\d documents
```
or programmatically (preferred — it works without psql interactive shell):
```sql
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
ORDER BY ordinal_position;
```
You should see the seven new columns at the bottom.

### 4. Create test file `tests/test_documents_scope.py`

The test must exercise the GIN index and the array-containment query pattern that Stage 3 routing will rely on. Use the existing async DB connection helpers from [agent/db_utils.py](../agent/db_utils.py).

Required tests:

- **`test_scope_columns_exist`** — query `information_schema.columns` for `documents`, assert all seven new columns are present with the expected types.
- **`test_gin_index_exists`** — query `pg_indexes` and assert `idx_documents_icd_scope` exists on `documents`.
- **`test_insert_and_query_by_scope`** — insert a fixture document with `icd11_scope = ARRAY['BC81']`, then run `SELECT id FROM documents WHERE 'BC81' = ANY(icd11_scope) AND title = 'TEST_FIXTURE_AF'`, assert exactly one row returned. Clean up the fixture row in a teardown / `finally` block so the test is repeatable.
- **`test_default_scope_verified_false`** — insert a fixture without specifying `scope_verified`, assert it defaults to `FALSE`.
- **`test_array_overlap_pattern`** — insert two fixture rows (one with `icd11_scope = ARRAY['BC81']`, one with `ARRAY['BA00','BA01']`), then query `WHERE icd11_scope && ARRAY['BC81','BC82']::TEXT[]` (overlap operator) and assert exactly one row returned. This is the pattern Stage 3 routing will use.

Each test must fully clean up its fixture rows. Use `source` values that begin with `TEST_FIXTURE_` so a stray run is easy to identify and remove.

If the test file needs DB fixtures setup (e.g. an async pytest fixture for the connection), add it to a new `tests/conftest.py` only if one doesn't already exist; otherwise extend the existing one minimally.

## Implementation guidance

- **Idempotency matters.** The migration uses `ADD COLUMN IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` so re-running is safe. Do not use `DROP COLUMN`, `DROP INDEX`, or any destructive statement.
- **Do not run `schema.sql` on the live DB.** It would `DROP TABLE documents CASCADE` and destroy ingested CPG data. The migration file is the only thing that touches production.
- **`NOT NULL DEFAULT '{}'` on `TEXT[]` columns** is intentional. Querying `WHERE 'X' = ANY(icd11_scope)` on a NULL array returns NULL (not FALSE), which makes routing logic confusing. Empty array is the safer default.
- **The partial index** `idx_documents_scope_verified ... WHERE scope_verified = TRUE` keeps the index small (only verified rows are routable; unverified rows shouldn't appear in routing results).
- **GIN on `TEXT[]`** supports the `@>`, `<@`, `&&`, and `= ANY(...)` operators efficiently. Both routing patterns (exact membership and overlap) will hit the index.
- **Connection management in tests** — match whatever pattern [agent/db_utils.py](../agent/db_utils.py) uses (likely `asyncpg` pool). Don't open new pools per test if there's a shared one available.

## Out of scope

- ❌ Do NOT create a `cpg_documents` table — extend `documents` only.
- ❌ Do NOT add a `cpg_id` column to `chunks` — `document_id` already exists and is sufficient.
- ❌ Do NOT add a `title_embedding` column yet — that comes in Step F (semantic fallback). This step is structural only.
- ❌ Do NOT populate the new columns with real CPG scope data — that is Step C (the classifier). Leave all existing rows at their defaults (`icd11_scope = '{}'`, `scope_verified = FALSE`).
- ❌ Do NOT modify `chunks`, `sessions`, `messages`, `icd11_codes`, or any SQL function (`match_chunks`, `hybrid_search`, etc.).
- ❌ Do NOT modify any Python file in `agent/`, `ingestion/`, or `ddx/` — schema and tests only.
- ❌ Do NOT add audit/logging columns or triggers — deferred.
- ❌ Do NOT install new Python dependencies.

## Done criteria

All five must pass:

1. `sql/schema.sql` shows the seven new columns inside `CREATE TABLE documents` and the two new indexes after it. `git diff sql/schema.sql` only touches the `documents` block + nearby indexes — nothing else.
2. `sql/migrations/001_documents_scope.sql` exists and can be applied **twice in a row** without error (idempotent).
3. The live Neon DB has the seven new columns (verify via the `information_schema.columns` query above).
4. `pytest tests/test_documents_scope.py -v` — all tests green.
5. `pytest --collect-only -q tests/` produces no *new* errors beyond the pre-existing baseline in `tests/tools/` and `scratch/` (i.e. you didn't break anything else).

## Report back

When you finish, tell the user:
1. **Files changed/created** — exact paths.
2. **Migration apply output** — exact command used + the post-migration `\d documents` (or equivalent `information_schema` query) showing all columns.
3. **Test output** — last ~25 lines of `pytest tests/test_documents_scope.py -v`.
4. **Any deviations** from this brief and why.
5. **Follow-ups noticed but not done** — anything you spotted that should become a future step (do not act on these now).
