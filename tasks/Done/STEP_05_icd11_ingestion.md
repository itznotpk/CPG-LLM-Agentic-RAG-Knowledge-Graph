# Step 05 — Expand ICD-11 Ingestion (WHO API, Full Chapters 02 / 05 / 08 / 11 / 16 / 18 / 21)

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) — read §1, §4 Step E, §7 before starting.

Steps 01–04 are complete. The `documents` table has 30 reviewed CPG groups with `icd11_scope` populated. The other side of the routing pipeline — Stage 2's symptom→ICD prediction — currently only has Chapter 17 (47 codes) in `icd11_codes`. That makes routing impossible for any non-Chapter-17 patient query.

This is **Step 05 of 8**. Ingest WHO ICD-11 chapters that cover all `icd11_scope` values currently in `documents`:

| Chapter | Why we need it | CPGs that use codes from it |
|---|---|---|
| **02** Neoplasms | Breast cancer | Breast-Cancer(3rd Edition) |
| **05** Endocrine, nutritional, metabolic | Lipids, diabetes, obesity | Dyslipidaemia, CVD-Prevention-Women |
| **08** Diseases of the nervous system | Stroke | Ischaemic-Stroke, CVD-Prevention-Women |
| **11** (codes start with `BA`–`BD`) Circulatory | All cardiology CPGs | AF, HF, HTN, NSTE-ACS, NSTEMI, STEMI, PCI, PAH, IE, CVD-Prevention |
| **16** Genitourinary | Chronic kidney disease | CVD-Prevention-Women |
| **18** Pregnancy, childbirth or the puerperium | Diabetes mellitus in pregnancy codes (`JA63*`) | Diabetes-in-Pregnancy |
| **21** Symptoms, signs or clinical findings | Symptom/presentation routing such as short stature and chronic cancer pain (`MG44*`, `MG30*`) | Growth-Hormone-in-Children-and-Adults, Cancer-Pain |
| **17** Sexual health | (✅ already ingested via [ddx/ingest_icd11.py](../ddx/ingest_icd11.py)) | Erectile-Dysfunction |

Build a **new** ingestion script that talks to the WHO ICD-11 API and ingests **the full content of chapters 02, 05, 08, 11, 16, 18, 21** into the existing `icd11_codes` table. Do not touch Chapter 17 (already done).

## Objective

A self-contained, idempotent script `ddx/ingest_icd11_full.py` that:
1. Authenticates against WHO ICD-11 API via OAuth2 (client credentials flow, token cached in memory).
2. Walks the MMS linearization tree for each target chapter, recursively descending into all children.
3. Extracts `code`, `title`, `description`, `inclusions`, `exclusions`, `parent_code`, `chapter` for every entity.
4. Generates an embedding for each code (matching the existing dimension in the `icd11_codes` table).
5. Upserts into `icd11_codes` — re-running is safe.
6. Has resume capability so a partial run after rate-limit / network failure can pick up from where it stopped.

## Preconditions

- Read [ddx/ingest_icd11.py](../ddx/ingest_icd11.py) — the existing 47-row Chapter 17 ingester. Match its style: asyncpg connection, `get_embedding_client()` / `get_embedding_model()` from [agent/providers.py](../agent/providers.py), upsert pattern.
- The `icd11_codes` table already exists with this shape (do NOT re-create it):
  ```
  id SERIAL PK | code VARCHAR(20) UNIQUE | title VARCHAR(255) | description TEXT
  inclusions TEXT[] | exclusions TEXT[] | parent_code VARCHAR(20) | chapter VARCHAR(10)
  embedding vector(1536) | inclusion_embeddings JSONB DEFAULT '{}'
  ```
  (Migration 004 standardised `embedding` to vector(1536).)
- `.env` has been updated with WHO API credentials:
  - `ICD11_API_CLIENT_ID`
  - `ICD11_API_CLIENT_SECRET`
  - `ICD11_API_RELEASE_ID=2024-01`
  - `ICD11_API_LINEARIZATION=mms`
  - `ICD11_API_LANGUAGE=en`
- Bedrock embedding pipeline is already configured via `EMBEDDING_PROVIDER=bedrock`, `EMBEDDING_MODEL=amazon.titan-embed-text-v1`, `VECTOR_DIMENSION=1536` in `.env`.

## Embedding dimension: 1536, no truncation

Migration 004 (applied before this step) standardised `icd11_codes.embedding` to `vector(1536)`. Use the project's standard Bedrock Titan v1 embedder (1536 native dim) — **no truncation**. The same embedding space as `chunks.embedding`.

**Sanity check before ingestion** — verify the migration is in place:
```sql
SELECT atttypmod
FROM pg_attribute
WHERE attrelid = 'icd11_codes'::regclass AND attname = 'embedding';
-- expected: 1536
```
If the column is still 768, abort and run migration 004 first; do not introduce truncation logic.

## Deliverables

### 1. `ddx/ingest_icd11_full.py` (new file)

Top-level structure:

```
- OAuth2 token client (cache in-memory, refresh on 401)
- WHO ICD-11 API client (httpx.AsyncClient with retries + backoff)
- Recursive chapter walker (yields ICD-11 entities)
- Code-shape parser (WHO API JSON → flat dict matching icd11_codes columns)
- Embedding generator (matches existing dimension)
- Upsert writer (asyncpg, ON CONFLICT (code) DO UPDATE)
- Resume / progress tracking (write `ddx/data/.icd11_progress.json` after each chapter)
- CLI with --chapters, --dry-run, --resume, --force-refresh
```

#### 1a. OAuth2 token client

```python
class WHOTokenClient:
    TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
    SCOPE = "icdapi_access"
    
    async def get_token(self) -> str: ...
    # POST form-encoded {grant_type=client_credentials, client_id, client_secret, scope}
    # Cache token + expiry. Refresh proactively when within 60s of expiry.
```

#### 1b. WHO API client

```python
class WHOAPIClient:
    BASE_URL = "https://id.who.int/icd/release/11"
    HEADERS = {
        "Accept": "application/json",
        "API-Version": "v2",
        "Accept-Language": <ICD11_API_LANGUAGE>,
    }
    
    async def get_entity(self, uri_or_code: str) -> dict:
        # GET <release>/<linearization>/<code>
        # Or GET <full-uri> if URI is fully-qualified
        # Auto-retry on 429 with exponential backoff (start 2s, max 60s, max 5 retries)
        # Auto-refresh OAuth token on 401
        ...
    
    async def get_chapter_root(self, chapter_code: str) -> dict:
        # GET <release>/<linearization>/<chapter_code>
        ...
```

Conservative client-side rate limit: **max 8 requests/sec** (use `asyncio.Semaphore` + a small sleep). WHO publishes no hard limit but apply this defensively.

#### 1c. Chapter walker

A recursive async generator that descends from a chapter root through `child` URIs in the JSON response. Each entity has:
- `@id` (full URI)
- `code` (the ICD-11 code, may be empty for grouping-only entities)
- `title.@value` (title string)
- `definition.@value` (the description, optional)
- `inclusion[]` (list with `label.@value`)
- `exclusion[]` (list of objects, parse `label.@value`)
- `parent[]` (list of parent URIs)
- `child[]` (list of child URIs)
- `chapter` (chapter number, derived from breadcrumb if not present)

**Skip entities with empty `code` field** — they are abstract grouping nodes that don't go in our table. Only ingest entities that have a real ICD-11 code.

#### 1d. Code parser

```python
def parse_entity(entity_json: dict, chapter: str, parent_code: str | None) -> dict | None:
    # Returns the dict shape expected by upsert, or None if entity should be skipped.
    # Maps:
    #   code            <- entity_json["code"]
    #   title           <- entity_json["title"]["@value"][:255]
    #   description     <- entity_json.get("definition", {}).get("@value", "")
    #   inclusions      <- [i["label"]["@value"] for i in entity_json.get("inclusion", [])]
    #   exclusions      <- [e["label"]["@value"] for e in entity_json.get("exclusion", [])]
    #                      # exclusions may have foundationReference instead of label; handle both
    #   parent_code     <- parent_code (passed by walker)
    #   chapter         <- chapter
```

#### 1e. Embedding generator

Reuse `get_embedding_client()` and `get_embedding_model()` from [agent/providers.py](../agent/providers.py). Native 1536-dim Bedrock Titan v1 output — no truncation.
Embedding text format:
```
"<title>. <description>. Also known as: <inclusions joined>"
```
(same as existing `create_embedding_text` in [ddx/ingest_icd11.py](../ddx/ingest_icd11.py)).

#### 1f. Database writer

Use the same upsert SQL as [ddx/ingest_icd11.py](../ddx/ingest_icd11.py):

```sql
INSERT INTO icd11_codes (code, title, description, inclusions, exclusions, parent_code, chapter, embedding)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (code) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    inclusions = EXCLUDED.inclusions,
    exclusions = EXCLUDED.exclusions,
    parent_code = EXCLUDED.parent_code,
    chapter = EXCLUDED.chapter,
    embedding = EXCLUDED.embedding;
```

Pass `embedding` as `str(embedding_vector)` — the existing pattern in [ddx/ingest_icd11.py](../ddx/ingest_icd11.py).

Batch in groups of 10 for fewer round-trips, but commit per chapter so partial failure doesn't lose a whole run.

#### 1g. Resume / progress tracking

Maintain `ddx/data/.icd11_progress.json`:
```json
{
  "release_id": "2024-01",
  "completed_chapters": ["08"],
  "in_progress_chapter": "11",
  "in_progress_entities_done": ["BA00", "BA01", "BA02", ...],
  "started_at": "...",
  "last_updated_at": "..."
}
```
Append-only writes after each successful entity insert (write atomically — write to `.tmp` then rename).

#### 1h. CLI

```bash
# Full run, all 7 target chapters
python -m ddx.ingest_icd11_full --chapters 02,05,08,11,16,18,21

# Resume from progress file
python -m ddx.ingest_icd11_full --chapters 02,05,08,11,16,18,21 --resume

# Dry-run: walk + parse, print summary, NO embeddings, NO DB writes
python -m ddx.ingest_icd11_full --chapters 02 --dry-run

# Single chapter for testing
python -m ddx.ingest_icd11_full --chapters 11

# Force re-fetch even if progress shows complete
python -m ddx.ingest_icd11_full --chapters 11 --force-refresh
```

Default `--chapters` value should be `02,05,08,11,16,18,21` (the 7 target chapters). If the user passes nothing, run all seven.

Logging:
- INFO per-chapter start/complete with counts
- INFO every ~50 entities ingested ("Chapter 11: 250 codes ingested...")
- WARNING for skipped entities (no code, malformed JSON)
- ERROR for unrecoverable failures

### 2. Tests `tests/test_ingest_icd11_full.py`

Required, with mocking — NO real WHO API calls, NO real DB writes, NO real embeddings:

- **`test_oauth_token_caches`** — mock httpx; first call hits token endpoint, second call within TTL doesn't.
- **`test_oauth_token_refresh_on_expiry`** — mock httpx; token expires → next call hits token endpoint again.
- **`test_oauth_token_refresh_on_401`** — first API call returns 401 → token re-fetched → request retried.
- **`test_429_backoff_then_retry`** — mock returns 429 then 200; client retries with backoff and succeeds.
- **`test_429_backoff_max_retries`** — mock returns 429 forever; client gives up after 5 retries with a clear error.
- **`test_parse_entity_minimal`** — JSON with only `code` and `title.@value` — produces a valid record with empty inclusions/exclusions.
- **`test_parse_entity_full`** — JSON with description, inclusions, exclusions — all populated correctly.
- **`test_parse_entity_skip_no_code`** — entity with empty `code` → returns None.
- **`test_parse_entity_handles_inclusion_no_label`** — defensive: inclusion entry without `label.@value` → skipped, not crashed.
- **`test_walker_yields_all_descendants`** — synthetic chapter with 3 levels deep → walker yields all leaves and intermediate-coded nodes; no duplicates.
- **`test_walker_records_parent_code`** — walker passes correct parent_code into each parsed entity.
- **`test_progress_file_atomic_write`** — write to `.tmp` first, rename; verify `.tmp` doesn't exist after success.
- **`test_resume_skips_completed_chapters`** — progress file lists chapter 08 as complete → walker doesn't re-fetch chapter 08.
- **`test_resume_skips_completed_entities_within_chapter`** — progress lists `BA00, BA01` → walker yields BA02+.
- **`test_dry_run_makes_no_db_writes`** — pool's execute is never called.
- **`test_dry_run_makes_no_embedding_calls`** — embedding client is never called.
- **`test_embedding_text_format`** — title only → `"Title"`. With description and inclusions → `"Title. Description. Also known as: x, y"`.

### 3. Smoke test (manual, not pytest)

Document in the script's docstring:
```
Smoke test:
  python -m ddx.ingest_icd11_full --chapters 11 --dry-run
  Expected: discovers ~500 codes in chapter 11, NO DB writes, runs in ~1-2 min.
```

## Implementation guidance

- **httpx async** for HTTP. Don't use requests / sync clients.
- **OAuth token TTL**: WHO returns `expires_in` (seconds) — typically 3600. Use that, refresh 60s early.
- **Tree depth**: chapter 11 has ~5 levels. Depth-first recursion is fine; the natural recursion limit isn't an issue. If you're worried, limit to depth 10 with an assertion.
- **Duplicate detection inside the walker**: an entity may appear under multiple parents in some linearizations. Maintain a `visited: set[str]` of seen URIs in the walker to avoid double-fetch (and double-insert). Upsert handles duplicates at the DB layer too, so this is just a perf optimization.
- **Idempotency**: re-running the full command without `--resume` should still be safe — upserts overwrite existing rows. `--resume` is for time/cost saving on partial runs.
- **Don't fail the whole run on one bad entity.** Catch + log + skip. Aggregate failures in a final summary.
- **Don't import from `ingestion/`** — this script lives in `ddx/` and is paired with the existing Chapter 17 ingester.

## Out of scope

- ❌ Do NOT modify the `icd11_codes` schema — column shape is final.
- ❌ Do NOT touch Chapter 17 entries (`code` starts with `HA`). The existing 47 rows must remain untouched. Verify before/after counts.
- ❌ Do NOT modify [ddx/ingest_icd11.py](../ddx/ingest_icd11.py) (the markdown-based Chapter 17 path).
- ❌ Do NOT compute `inclusion_embeddings` (that's a separate column populated by [ddx/migrate_inclusion_embeddings.py](../ddx/migrate_inclusion_embeddings.py) — run that separately after ingestion if needed; out of scope for this step).
- ❌ Do NOT add new dependencies. `httpx`, `asyncpg`, `python-dotenv`, `pydantic` should already be in `requirements.txt`. If `httpx` somehow isn't, add it minimally and note the addition.
- ❌ Do NOT rate-limit aggressively beyond 8 req/sec — there's no need to be slower.
- ❌ Do NOT make real WHO API calls or real DB writes inside `pytest`.
- ❌ Do NOT cache API responses to disk by default. Progress file is enough; the script is one-shot, not interactive.

## Done criteria

All five must pass:

1. `python -m ddx.ingest_icd11_full --chapters 11 --dry-run` runs end-to-end. Reports approximate code count for chapter 11 (expect ~400–600). No DB or embedding side-effects.
2. `python -m ddx.ingest_icd11_full --chapters 02,05,08,11,16,18,21` (full run) completes successfully. Verify with:
   ```sql
   SELECT chapter, COUNT(*) FROM icd11_codes GROUP BY chapter ORDER BY chapter;
   ```
   Expected counts roughly: chapter 02 ~1500, 05 ~600, 08 ~700, 11 ~500, 16 ~400, 18 ~300, 21 ~600, plus chapter 17 ~47 (preserved). Total ~4,600.
3. The 47 Chapter-17 rows are untouched: `SELECT COUNT(*) FROM icd11_codes WHERE code LIKE 'HA%'` still returns 47 (or whatever the pre-step count was — capture it before running).
4. `pytest tests/test_ingest_icd11_full.py -v` — all tests green, NO real WHO API calls.
5. Re-running the full command (idempotency check) produces no errors and no row count change.

## Report back

When you finish, tell the user:
1. **Files created/modified** — exact paths.
2. **Embedding dimension confirmation** — confirm the column is 1536 and the embedder produces 1536-dim vectors with no truncation.
3. **Dry-run output** — code count discovered for chapter 11.
4. **Full-run summary** — per-chapter count of new rows + total runtime + any skipped entities and why.
5. **Test output** — last ~25 lines of `pytest tests/test_ingest_icd11_full.py -v`.
6. **Pre/post Chapter 17 count** — show that the 47 HA-codes are preserved.
7. **Any deviations** from this brief and why.
8. **Follow-ups noticed but not done.**
