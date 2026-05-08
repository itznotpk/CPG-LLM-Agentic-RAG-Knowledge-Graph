# Step 03 — CPG Scope Classifier (one-shot)

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) — read §3, §6, §7 before starting.

Steps 01 (schemas) and 02 (scope columns on `documents`) are complete. The `documents` table now has `icd11_scope`, `procedure_scope`, `scope_rationale`, `scope_verified`, `classified_at`, `verified_at`, `verified_by` — all defaulted to empty / FALSE / NULL on existing rows.

This is **Step 03 of 8**. It populates `icd11_scope` / `procedure_scope` / `scope_rationale` for every CPG already ingested into `documents`, by sending each CPG's summary content to an LLM and parsing a structured JSON response. Rows are left at `scope_verified = FALSE` until a clinician reviews them in Step 04.

## Critical structural fact about this codebase

The `markdown/` directory does **not** contain one file per CPG. Each CPG is pre-split into ~12–20 section files inside a per-CPG sub-directory. Example:

```
markdown/Atrial-Fibrillation(2012)/section-0-summary.md
markdown/Atrial-Fibrillation(2012)/section-1-introduction.md
markdown/Atrial-Fibrillation(2012)/section-2-pathophysiology.md
... 12 sections total
markdown/STEMI(4th Edition)/section-0-front-matter.md
... 19 sections total
```

The `documents` table has one row per *section file* (~212 rows from 14 CPGs in a typical state). Each row's `source` column points to a single section markdown.

**This means:** the classification unit is the **parent-directory name (the CPG)**, not the individual `documents` row. Group rows by parent-directory; classify each group **once**; write the same scope to all rows in that group.

A small minority of CPGs may be stored as a single top-level `.md` file (no sub-directory). Treat each such file as a one-row group keyed on the filename itself.

## Objective

Build a one-shot script that:
1. Discovers all distinct CPG groups currently in `documents`.
2. For each group, sends the CPG's identity + summary content to the LLM and parses a JSON proposal of `icd11_scope` / `procedure_scope` / `scope_rationale`.
3. Validates the JSON, then UPDATEs every row in that group with the same scope values.
4. Generates a human-readable `tasks/cpg_scope_review.md` so a clinician can approve/edit the proposals in Step 04.

## Preconditions

- Read [agent/providers.py](../agent/providers.py) — uses `get_ingestion_model()` driven by `.env` (`LLM_PROVIDER`, `LLM_CHOICE`, `LLM_BASE_URL`, `LLM_API_KEY`). The user's `.env` is already configured to talk to a **Xiaomi-hosted model** through an **OpenAI-compatible endpoint** — do **not** add a new provider, do **not** hardcode any base URL or model name. Just call `get_ingestion_model()`.
- Read [agent/db_utils.py](../agent/db_utils.py) for the asyncpg connection pattern. Match it for any DB I/O.
- Read [tasks/STEP_02_extend_documents.md](STEP_02_extend_documents.md) — it confirms which scope columns exist.
- Confirm Step 02 is applied: `SELECT COUNT(*) FROM documents WHERE icd11_scope IS NOT NULL` should return all rows (NOT NULL DEFAULT '{}' means existing rows have `icd11_scope = '{}'`, not NULL).

## Deliverables

### 1. Discovery + grouping logic

Inside the new script `ingestion/classify_cpg_scope.py`:

Implement a function that:

1. Queries `SELECT id, source, title FROM documents ORDER BY source`.
2. Derives a `cpg_group_key` for each row from `source`:
   - If `source` contains a path with at least one directory, the group key is the **parent directory name** (the immediate parent of the section file). Strip leading paths like `markdown/`. So `markdown/Atrial-Fibrillation(2012)/section-7-rate-control.md` → `Atrial-Fibrillation(2012)`.
   - If `source` is a bare filename (no directory), the group key is the filename **without extension**. So `CPG Heart Disease in Pregnancy.md` → `CPG Heart Disease in Pregnancy`.
   - If `source` doesn't fit either pattern (e.g. a database-internal id), log a warning and skip the row — record it under an `unmappable` list in the report.
3. Builds `groups: dict[str, list[DocumentRow]]` keyed by `cpg_group_key`.
4. Logs a summary: number of groups, rows per group, any unmappable rows.

Do **not** assume a specific path separator — use `pathlib.PurePosixPath` so the logic is robust to both `/` and `\`.

### 2. Per-group content extraction

For each group, prepare the input the LLM will see:

1. **CPG name** = the group key.
2. **Summary content** = pick the best representative section file(s) from the group's rows:
   - **Priority order**: `section-0-*.md`, `section-1-*.md`, then any other `section-*-summary*.md` or `section-*-introduction*.md`. Pick **up to 2 files**.
   - For single-file groups (no sub-directory), use the file itself.
3. Read the content of those file(s) directly from disk (resolve the path relative to the project root). Concatenate them with a separator like `\n\n--- next section ---\n\n`. Cap total length at **~12,000 characters** (truncate with a clear `[...truncated]` marker if needed) so the prompt stays well within Xiaomi's context window.
4. If the priority files don't exist on disk for a group (e.g. the row's `source` is in the DB but the file is missing), fall back to using just the row's `title` field and log a warning.

### 3. LLM call + JSON parsing

For each group, call the LLM with this system + user prompt structure:

**System:**
```
You are a precise ICD-11 coding expert. Given a Malaysian Clinical Practice Guideline (CPG)'s name and summary content, identify the ICD-11 block codes (3-character) or ranges that this CPG provides treatment guidance for.

Rules:
- Be conservative. Only include codes for which the CPG offers actionable diagnostic or treatment guidance.
- Use 3-character block codes (e.g. "BC81", "BA00") OR ranges in the format "BA00-BA04" when a CPG covers a contiguous block.
- If the CPG is procedure-oriented (e.g. anaesthesia, surgical safety) rather than disease-oriented, leave icd11_scope EMPTY and populate procedure_scope with short snake_case tags such as "pre_op_assessment", "intraop_monitoring", "anaesthetic_safety".
- Every CPG must end with at least one non-empty array — either icd11_scope or procedure_scope.
- Return STRICT JSON only. No markdown fences, no commentary, no leading/trailing text.

Return JSON shape:
{"icd11_scope": ["BC81", "BC9Z"], "procedure_scope": [], "rationale": "Atrial fibrillation and related arrhythmias..."}
```

**User:**
```
CPG name: {cpg_group_key}

Summary content:
{summary_content}
```

After the call:

1. Strip any accidental code-fence wrapping (`` ```json ... ``` ``) defensively before `json.loads`.
2. Validate with a small Pydantic model:
   ```python
   class ScopeProposal(BaseModel):
       icd11_scope: list[str] = []
       procedure_scope: list[str] = []
       rationale: str
   ```
3. **Validate each `icd11_scope` entry against the regex** `^[0-9A-Z]{2,4}(\.[0-9A-Z]{1,2})?$` OR a range pattern `^[0-9A-Z]{2,4}-[0-9A-Z]{2,4}$`. Drop any entry that fails the regex (don't crash; log it).
4. **Reject the proposal** if both `icd11_scope` and `procedure_scope` are empty after filtering — log and continue with the next group; do not write to the DB for that group.
5. **Retry once** on `json.JSONDecodeError`, network errors, or transient LLM errors (with a brief sleep). Don't loop forever — fail the group cleanly after the second attempt.

### 4. Database update

For every successfully classified group:

```sql
UPDATE documents
SET icd11_scope     = $1,
    procedure_scope = $2,
    scope_rationale = $3,
    classified_at   = NOW(),
    scope_verified  = FALSE
WHERE id = ANY($4::uuid[]);
```

Pass the array of `documents.id` values for the group. Use parametrised queries — never f-string SQL.

Idempotency: re-running the classifier MUST be safe. Each row's scope columns are simply overwritten by the latest LLM proposal. `scope_verified` is forced back to `FALSE` so any human edits made between runs are not silently kept (the clinician's source of truth is the review file, not the DB row — re-classification invalidates prior verification).

### 5. Review file generation

After all groups are processed, write `tasks/cpg_scope_review.md` with one section per CPG:

```markdown
# CPG Scope Review — generated {ISO timestamp}

For each CPG below, mark Approve / Edit / Reject. The verifier script (Step 04) will parse this file.

---

## Atrial-Fibrillation(2012)
- Rows updated: 12
- Proposed icd11_scope: `BC81`, `BC9Z`
- Proposed procedure_scope: (none)
- Rationale: Atrial fibrillation and related arrhythmias…

- [ ] Approve
- [ ] Edit (replace lists above; rationale optional)
- [ ] Reject (mark scope_verified false; do nothing)

---

## STEMI(4th Edition)
…
```

Format must be stable and machine-parseable in Step 04 (consistent header levels, fixed bullet keys). The `### Approval` checkboxes use exactly the labels above; do not re-word them.

At the end of the file, add an **Errors** section listing:
- Groups that failed JSON parsing twice.
- Groups rejected because both scope arrays were empty.
- Unmappable rows from §1 step 2.

### 6. CLI entrypoint

The script should be runnable as:

```bash
python -m ingestion.classify_cpg_scope               # full run
python -m ingestion.classify_cpg_scope --dry-run     # discovery + LLM calls, NO DB write, NO review file
python -m ingestion.classify_cpg_scope --only "Atrial-Fibrillation(2012),STEMI(4th Edition)"
```

Use `argparse`. The `--only` flag (comma-separated group keys) is helpful for testing a small subset and for re-classifying just the CPGs that failed in a previous run. `--dry-run` still prints what *would* be written.

Logging: use the standard `logging` module. INFO level for progress (`Classifying CPG: STEMI(4th Edition) (19 rows)`), WARNING for fallbacks/skips, ERROR for hard failures.

### 7. Tests `tests/test_classify_cpg_scope.py`

Required tests (use mocking — do NOT hit the real LLM in tests):

- **`test_group_key_from_path`** — pure function test for the grouping logic: `markdown/AF(2012)/section-7.md` → `AF(2012)`; `CPG X.md` → `CPG X`; `weird-id-string` → unmappable.
- **`test_scope_proposal_validates_good_json`** — feeds a known-good JSON string into the parser, asserts the resulting `ScopeProposal` has expected fields.
- **`test_scope_proposal_strips_code_fence`** — input is `\`\`\`json\n{...}\n\`\`\``, parser still succeeds.
- **`test_invalid_icd_codes_are_dropped`** — proposal contains `["BC81", "not-a-code", "BA00-BA04", "??"]`, parser keeps `["BC81", "BA00-BA04"]`.
- **`test_empty_scope_rejected`** — proposal with both arrays empty raises a ValueError or returns a sentinel that the caller treats as a rejection.
- **`test_db_update_called_per_group`** (mock the DB call) — verify the UPDATE is issued exactly once per group with the right ids.
- **`test_dry_run_makes_no_db_writes`** — same mock setup, assert UPDATE is never called when `--dry-run` is set.

Tests must NOT make real LLM or real DB calls. Use `unittest.mock.AsyncMock` / `monkeypatch` for the LLM call and DB pool. Sample fixture content can be a 30-line synthetic markdown blob.

## Implementation guidance

- **Async throughout.** Use `asyncio` + `asyncpg`. Run group classifications **sequentially** for v1 (don't parallelize across groups — easier to debug, and 14 calls take <2 minutes anyway). If you do parallelize, cap concurrency at 3.
- **Use `get_ingestion_model()` from [agent/providers.py](../agent/providers.py).** Wrap it in a Pydantic AI `Agent(model, result_type=ScopeProposal)` so structured-output validation comes for free — but still defensive-parse if the model strips/breaks the structure.
- **Pathing** must work on both Windows and POSIX. Use `pathlib`.
- **Don't read `.env` directly** — `dotenv.load_dotenv()` is already called inside [agent/providers.py](../agent/providers.py).
- **Don't catch broad `Exception`** silently. Catch specific exceptions (`json.JSONDecodeError`, `ValidationError`, `asyncpg.PostgresError`, `httpx.HTTPError`) and log clearly.

## Out of scope

- ❌ Do NOT call `scope_verified = TRUE` anywhere — verification is Step 04.
- ❌ Do NOT delete or modify existing rows beyond the listed UPDATE.
- ❌ Do NOT add new columns to `documents` — Step 02 is final for this round.
- ❌ Do NOT compute or store `title_embedding` (semantic CPG fallback) — that's deferred to Step F.
- ❌ Do NOT modify `agent/`, `ddx/`, `sql/` (other than reading them).
- ❌ Do NOT add a CLI prompt to ask the user to pick a model — read it from env, full stop.
- ❌ Do NOT add real LLM calls in tests.
- ❌ Do NOT install new dependencies. Pydantic AI, asyncpg, python-dotenv are already present.
- ❌ Do NOT classify CPGs that are NOT yet in the `documents` table. The classifier processes whatever is currently ingested. The 11 un-ingested CPGs will be classified later when their ingestion runs.

## Done criteria

All five must pass:

1. `python -m ingestion.classify_cpg_scope --dry-run` runs end-to-end without DB writes, prints group discovery + per-group LLM proposals + would-be UPDATE counts. Number of groups should match the number of distinct CPG sub-directories represented in `documents.source`.
2. `python -m ingestion.classify_cpg_scope` (full run) completes successfully. Verify with:
   ```sql
   SELECT COUNT(*) AS classified
   FROM documents
   WHERE classified_at IS NOT NULL;
   ```
   Should equal the row count of all mappable groups.
3. `tasks/cpg_scope_review.md` exists, has one section per classified CPG, and parses cleanly by eye (no broken markdown, no missing scope lines).
4. `pytest tests/test_classify_cpg_scope.py -v` — all tests green, NO real LLM or DB calls made.
5. Re-running the full command (idempotency check) does NOT produce duplicate review entries (review file is overwritten, not appended) and does NOT produce errors.

## Report back

When you finish, tell the user:
1. **Files created/modified** — exact paths.
2. **Discovery output** — number of distinct CPG groups found, total rows covered, any unmappable rows.
3. **Classification summary** — for each CPG group: name, proposed icd11_scope, proposed procedure_scope (one line per group). 14ish lines total.
4. **Test output** — last ~25 lines of `pytest tests/test_classify_cpg_scope.py -v`.
5. **Sample of `tasks/cpg_scope_review.md`** — the first 2 CPG sections (so user can sanity-check the format).
6. **Any deviations** from this brief and why.
7. **Follow-ups noticed but not done.**
