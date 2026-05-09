# Step 04 — Review Verifier (parses cpg_scope_review.md → DB)

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) — read §4 Step D, §6.4 before starting.

Steps 01–03 are complete. Right now:
- All 16 CPG groups in `documents` have proposed `icd11_scope` / `procedure_scope` / `scope_rationale`.
- All rows have `scope_verified = FALSE`.
- A clinician/reviewer has marked decisions in [tasks/cpg_scope_review.md](cpg_scope_review.md) — Approve / Edit / Reject — and made manual scope edits inside that file where they marked Edit.

This is **Step 04 of 8**. Build the verifier that parses the review markdown and writes the reviewer's decisions back to `documents`.

## Objective

Implement a verifier script `ingestion/verify_cpg_scope.py` that:
1. Parses [tasks/cpg_scope_review.md](cpg_scope_review.md) into per-CPG sections.
2. For each CPG, reads the decision (Approve / Edit / Reject) from the checkbox line.
3. Applies the decision to the `documents` rows for that CPG group:
   - **Approve** → flip `scope_verified = TRUE`, set `verified_at` and `verified_by`. Don't touch scope columns.
   - **Edit** → parse the (possibly edited) `Proposed icd11_scope:` and `Proposed procedure_scope:` lines, validate them, UPDATE the DB rows with the new values, then flip `scope_verified = TRUE` with audit timestamps.
   - **Reject** → don't update; leave `scope_verified = FALSE`. Log to a rejection list.
4. Writes a verification report markdown summarising what happened.
5. Is idempotent — re-running on the same file produces the same result (already-verified rows skip cleanly with an INFO log).

## Preconditions

- Read [agent/db_utils.py](../agent/db_utils.py) for the asyncpg connection pattern. Match it.
- Read [ingestion/regenerate_scope_review.py](../ingestion/regenerate_scope_review.py) — its `fetch_groups` query and section format are the inverse of what you're parsing.
- Read [ingestion/classify_cpg_scope.py](../ingestion/classify_cpg_scope.py) — reuse its ICD-11 format validation regex (same rules: `^[0-9A-Z]{2,4}(\.[0-9A-Z]{1,2})?$` or range `^[0-9A-Z]{2,4}-[0-9A-Z]{2,4}$`).
- Step 02's columns exist on `documents`: `scope_verified`, `verified_at`, `verified_by`. No schema changes in this step.

## Critical: format variations the parser MUST tolerate

The reviewer is a human writing markdown — the parser must be lenient about whitespace and case. From the actual file produced in Step 03:

```
- [x] Approve / [ ] Edit / [ ] Reject       ← lowercase x, standard
- [X] Approve / [ ] Edit / [ ] Reject       ← uppercase X (NSTEMI section uses this)
- [ ] Approve / [x ] Edit / [ ] Reject      ← internal space inside brackets (Dyslipidaemia)
- [ ] Approve / [x] Edit / [ ] Reject       ← Edit chosen
```

Use a regex like `r"\[\s*[xX]\s*\]"` to detect a checked box. **Do not require a specific case or zero-padding.**

Other lenience:
- The `## Heading` line is the CPG name; trim whitespace.
- The reviewer added some new lines like `- ICD-11 hierarchy: ...` after the rationale. **Ignore unknown bullet lines** — parser cares only about `Proposed icd11_scope:`, `Proposed procedure_scope:`, `Rationale:`, and the decision line.
- Order of bullets within a section may vary slightly. Parse by *prefix*, not position.

## Deliverables

### 1. Create `ingestion/verify_cpg_scope.py`

The script must:

#### 1a. Markdown parser

```python
class CPGSectionDecision(BaseModel):
    cpg_name: str
    decision: Literal["approve", "edit", "reject", "none"]   # "none" = no box checked, skip
    new_icd11_scope: list[str] | None       # only populated when decision == "edit"
    new_procedure_scope: list[str] | None   # only populated when decision == "edit"
    new_rationale: str | None               # only populated when decision == "edit"
    raw_section_text: str                   # for error reporting
```

Implement `parse_review_file(path: Path) -> list[CPGSectionDecision]`:

1. Read the file as text. Split on `\n## ` (skip the file-level header).
2. For each section, extract:
   - First line after split (until newline) → `cpg_name`. Strip a trailing `✅` marker if present (from regenerate_scope_review.py output).
   - Find the line beginning with `- [ ] Approve / [ ] Edit / [ ] Reject` (in any check pattern).
   - Use the lenient regex pattern to find which of {Approve, Edit, Reject} has its `[x]` set. **If more than one checkbox is checked, raise a clear ValueError** ("Multiple decisions marked for CPG X"). **If zero checked, set decision to `"none"` and skip with INFO log.**
   - For `edit` only: parse the bullets:
     - `- Proposed icd11_scope: \`BC81.3\`, \`BA02\`, ...` → list of codes (strip backticks). The literal `(none)` (case-insensitive) means empty list.
     - `- Proposed procedure_scope: ...` → same parsing, same `(none)` rule.
     - `- Rationale: <text>` → single string. The first hyphen-bullet that begins with `Rationale:`. Multi-line rationales: read until next bullet line starting with `- `.
   - For `approve` and `reject`, leave the new_* fields as `None`.

#### 1b. Validation

For every parsed section with `decision == "edit"`:
- Each `icd11_scope` entry must match `^[0-9A-Z]{2,4}(\.[0-9A-Z]{1,2})?$` or `^[0-9A-Z]{2,4}-[0-9A-Z]{2,4}$`. Drop and log invalid entries; if all are dropped, raise an error for that section (don't write a junk update to DB).
- `procedure_scope` entries: must be non-empty `[a-z][a-z0-9_]*` snake_case. Drop and log otherwise.
- For procedure-only CPGs (Patient-Safety, Pre-Anaesthetic): empty `icd11_scope` is allowed, but `procedure_scope` must be non-empty.
- For disease CPGs: `icd11_scope` must be non-empty after filtering. If both are empty after filtering → error for that section.
- `new_rationale` may be empty / unchanged — don't fail on missing rationale.

#### 1c. Database application

For each parsed section, in a single transaction:

**Approve:**
```sql
UPDATE documents
SET scope_verified = TRUE,
    verified_at    = NOW(),
    verified_by    = $1
WHERE metadata->>'cpg_name' = $2
  AND scope_verified = FALSE;          -- idempotent: don't re-stamp already-verified rows
```
Log how many rows were updated. If zero rows updated AND zero rows verified-already, raise — the cpg_name didn't match anything.

**Edit:**
```sql
UPDATE documents
SET icd11_scope     = $1,
    procedure_scope = $2,
    scope_rationale = $3,
    scope_verified  = TRUE,
    verified_at     = NOW(),
    verified_by     = $4,
    classified_at   = COALESCE(classified_at, NOW())   -- keep original classify time if set
WHERE metadata->>'cpg_name' = $5;
```

**Reject:** No DB write. Log to the rejection list for the report.

**None:** Skip silently with INFO log (`<CPG>: no decision marked, skipped`).

#### 1d. Verification report

After processing all sections, write `tasks/cpg_scope_verification_report.md` with:
- Header line with run timestamp + verifier name.
- Three subsections: `## Approved (N)`, `## Edited (N)`, `## Rejected (N)`, `## Skipped (N)`.
- Under each, one bullet per CPG with: name, row count touched, brief change summary (for Edit: number of codes added/removed). 
- A trailing `## Errors (N)` section if any sections raised — describe what went wrong; the script must NOT crash mid-run on a single bad section, except for unrecoverable cases (DB connection failure).

#### 1e. CLI

```bash
python -m ingestion.verify_cpg_scope --verifier "Dr Smith"           # full apply
python -m ingestion.verify_cpg_scope --verifier "Dr Smith" --dry-run # parse + plan + report, NO DB writes
python -m ingestion.verify_cpg_scope --verifier "Dr Smith" --only "Atrial-Fibrillation(2012),STEMI(4th Edition)"
```

`--verifier` is **required** (no default). The value is written to `documents.verified_by`. Free-text — could be a name, email, or team identifier.

`--dry-run` parses the markdown, runs all validation, and writes the report — but **never opens a write transaction to the DB**. Useful sanity check before applying.

`--only` (comma-separated) lets you re-verify a subset.

Default review file path: `tasks/cpg_scope_review.md`. Add `--review-file` to override only if you need it for tests.

### 2. Tests `tests/test_verify_cpg_scope.py`

All required, all using mocks for DB and synthetic markdown text — NO real LLM calls, NO real DB calls.

- **`test_parse_approve_section`** — synthetic 1-section markdown with `[x] Approve` → returns decision="approve", new_* are None.
- **`test_parse_edit_section_with_codes`** — synthetic markdown with `[x] Edit` and edited scope codes → returns decision="edit", new_icd11_scope contains parsed codes (backticks stripped).
- **`test_parse_reject_section`** — `[x] Reject` → decision="reject".
- **`test_parse_none_section`** — no checkbox checked → decision="none".
- **`test_parse_uppercase_X_box`** — `[X] Approve` → still detected as approve.
- **`test_parse_box_with_internal_whitespace`** — `[x ] Approve` and `[ x ] Approve` → still detected as approve.
- **`test_parse_multiple_decisions_raises`** — `[x] Approve / [x] Edit` → raises ValueError.
- **`test_parse_edit_drops_invalid_codes`** — proposed `BC81, INVALID, 2C60` → only `BC81, 2C60` kept.
- **`test_parse_edit_all_invalid_raises`** — proposed all-invalid → raises (no DB write).
- **`test_parse_edit_handles_none_string`** — `Proposed procedure_scope: (none)` → empty list.
- **`test_parse_ignores_extra_bullets`** — section contains `- ICD-11 hierarchy: ...` and `- Rows in DB: ...` — parser ignores them.
- **`test_db_apply_approve_only_flips_metadata`** (mock pool) — assert UPDATE for approve does NOT touch icd11_scope columns.
- **`test_db_apply_edit_writes_new_scope`** (mock pool) — assert UPDATE includes the edited scope arrays.
- **`test_db_apply_reject_does_not_call_update`** (mock pool).
- **`test_dry_run_makes_no_db_writes`** — full-flow with dry_run=True → mock pool's execute is never called.
- **`test_idempotency_already_verified`** — DB returns 0 rows updated for an approved row (because it was already verified) → script logs INFO, doesn't error.

## Implementation guidance

- **Async throughout**, asyncpg, single connection (or pool with size 1) — there's no parallelism benefit for 16 sequential UPDATEs.
- **One DB transaction wraps the whole apply** so partial-application is impossible. If any section raises during DB UPDATE, rollback all and surface the error in the report. Parse errors during the parse phase are non-fatal — collected and reported, the unaffected sections still proceed.
- **Don't use string-format SQL** for any user-derived value. Always parametrised.
- **Logging**: standard `logging` module. Format `%(asctime)s %(levelname)-7s %(name)s :: %(message)s`. Default INFO; `--verbose` flag for DEBUG is optional.
- **No new dependencies**. asyncpg, pydantic, python-dotenv already present.

## Out of scope

- ❌ Do NOT modify the review markdown — verifier reads only.
- ❌ Do NOT add the `verifier` value to the review markdown header — write it only to the DB and the verification report.
- ❌ Do NOT call any LLM. The reviewer's edits are the source of truth.
- ❌ Do NOT modify schema, classifier, or migration scripts.
- ❌ Do NOT regenerate `cpg_scope_review.md` from this script. Use the existing `regenerate_scope_review.py` for that, separately.
- ❌ Do NOT touch other CPG-adjacent tables (`chunks`, `icd11_codes`, etc.).
- ❌ Do NOT add a UI / web endpoint. CLI only.

## Done criteria

All five must pass:

1. `python -m ingestion.verify_cpg_scope --verifier "<your-or-friends-name>" --dry-run` runs end-to-end without DB writes and prints a per-CPG plan plus the would-be `tasks/cpg_scope_verification_report.md`.
2. `python -m ingestion.verify_cpg_scope --verifier "<name>"` (full apply) commits successfully. After it runs, this query should return non-zero verified rows for every approved/edited CPG:
   ```sql
   SELECT metadata->>'cpg_name', COUNT(*)
   FROM documents
   WHERE scope_verified = TRUE
   GROUP BY metadata->>'cpg_name'
   ORDER BY 1;
   ```
3. The verification report `tasks/cpg_scope_verification_report.md` exists and lists each CPG under exactly one of Approved / Edited / Rejected / Skipped.
4. `pytest tests/test_verify_cpg_scope.py -v` — all tests green.
5. Re-running the full apply (idempotency check) does NOT produce errors and does NOT update verified_at on already-verified rows (the `WHERE scope_verified = FALSE` predicate handles this for approves; for edits, the predicate is broader by design — see note in 1c).

## Report back

When you finish, tell the user:
1. **Files created/modified** — exact paths.
2. **Dry-run output summary** — counts of Approved / Edited / Rejected / Skipped, plus any parse errors.
3. **Full-apply result** — output of the verification SQL above (per-CPG count of verified rows).
4. **Test output** — last ~25 lines of `pytest tests/test_verify_cpg_scope.py -v`.
5. **First 30 lines of `tasks/cpg_scope_verification_report.md`** so user can sanity-check format.
6. **Any deviations** from this brief and why.
7. **Follow-ups noticed but not done.**
