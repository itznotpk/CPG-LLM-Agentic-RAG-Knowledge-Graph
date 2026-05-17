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

This task is **six deliverables (D1–D6)** forming **two tracks that converge**: a routing track (D1 → D2 → D4) and a scoring/display track (D3 → D5 → D6). The two tracks are independent of each other until the final pipeline assembly. Follow the phased execution sequence below — do not work top-to-bottom through the D-sections.

## Objectives

- **D1** — ICD-11 hierarchy fallback in Stage 3 routing using existing `parent_code`. No WHO API calls.
- **D2** — Semantic CPG fallback gated by D1 returning 0 hits. Requires a small `documents.scope_embedding` migration.
- **D3** — Exclusion-aware DDx re-ranking: schema migration + backfill + scorer change.
- **D4** — Out-of-scope detector: structured "no CPG matches" response when D1 + D2 both miss and ICD confidence is low.
- **D5** — Clinician-facing score transparency: structured `ScoreBreakdown` per top-5 candidate + honest rendering/badges.
- **D6** — Math ↔ LLM rerank merge: feed math signals into the rerank prompt and surface material disagreements.

## Execution sequence (follow this order — not the D-section order)

Two tracks. **Track A (routing)** and **Track B (scoring/display)** are independent and may be done in either order or in parallel by two passes; they only meet at P6. Each phase has a hard exit gate — do not start the next phase in a track until its gate passes.

| Phase | Track | Deliverable(s) | Why here | Exit gate (must pass before next phase in this track) |
|---|---|---|---|---|
| **P0** | — | Preconditions + baseline snapshots | Capture invariants *before* any change so #11/#12 are provable | §Preconditions queries match expected; `icd11_codes` embedding checksum + `documents` scope snapshot saved to the report draft |
| **P1** | B | D3 migration 008 + `backfill_exclusion_embeddings` + scorer change | Pure data prep + isolated scorer math; zero pipeline risk; fully dry-runnable; unblocks D5 | Migration applied; 402 rows backfilled; idempotent re-run = 0 writes; D3 unit tests green; Smoke 4 green |
| **P2** | A | D1 (ancestor + sibling) + D2 migration 007 + `backfill_scope_embeddings` + D2 semantic fallback | Routing core; D4 cannot be built or tested without both branches existing | Migration applied; 16 scope embeddings backfilled; D1/D2 unit tests green; Smoke 1, 2, 3, 9 green on staging |
| **P3** | A | D4 out-of-scope detector | Observes D1+D2 outputs — only buildable after P2 | D4 unit tests green; Smoke 5 green on staging |
| **P4** | B | D5a model + D5b render + D5c explainer | Consumes D3's `ScoreBreakdown`; needs P1 done | D5 unit tests green; Smoke 7 green on staging |
| **P5** | B | D6a prompt-feed + D6b model ext + D6c render + D6d telemetry + force-rerank harness | Needs D5's candidate model and D3's exclusion signal | D6 unit tests green; Smoke 6, 8 green on staging |
| **P6** | A+B | Pipeline assembly + full pre-deploy gate | Both tracks converge: routing provenance flows into the D5/D6 display | **Full suite Smoke 1–9 green on staging**; all 12 done-criteria checked; then promote to prod |

Recommended single-pass order if done sequentially: **P0 → P1 → P2 → P3 → P4 → P5 → P6**. P1 and P2 have no dependency on each other — if parallelizing, run them as two concurrent passes and converge at P4 (which needs P1) / P3 (which needs P2).

## Preconditions

- Phase A Step 1 merged. Phase A Step 2 (re-ingest) **not required** for D1–D6 implementation, but the E2E smoke tests in §6 expect it complete.
- **P0 baseline (do this first, before any change):** run the verify queries below AND capture the two invariant baselines into the report draft so done-criteria #11/#12 are provable later:
  ```sql
  -- baseline 1: ICD-11 embedding checksum (must be identical post-change)
  SELECT MD5(string_agg(embedding::text, '|' ORDER BY code)) FROM icd11_codes;
  -- baseline 2: verified scope snapshot (must be byte-identical post-change)
  SELECT title, icd11_scope, scope_verified FROM documents ORDER BY title;
  ```
  **Canonical baseline-1 value (captured 2026-05-17, post ICD-11 ch.02/05/08/11/16/17/18/21 ingest + inclusion-embedding cleanup):**
  `embedding_checksum = d8a2db83e95d7655aa3b73cdf72b2631`
  D1–D6 must NOT change `icd11_codes.embedding`; re-running baseline-1 at the end must reproduce this exact MD5. (Re-capture baseline-2 yourself at P0 — it depends on live `documents` rows.) If the corpus is re-ingested or chapters change before this work starts, recompute and replace this value first.
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

## Known issues in the existing embedding pipeline (read before D3/D5)

Discovered 2026-05-17 while backfilling newly ingested ICD-11 chapters 18 (Pregnancy/childbirth, 511 codes) and 21 (Symptoms/signs, 1247 codes). Both issues below were **resolved 2026-05-17**; they are recorded so the D3/D5 implementer understands the data history and does not reintroduce the old patterns.

### Issue 1 — `[DESCRIPTION]` key in `inclusion_embeddings` (RESOLVED — now inclusion-term-only)

An earlier version of [ddx/migrate_inclusion_embeddings.py](../../ddx/migrate_inclusion_embeddings.py) stored, in addition to one embedding per inclusion term, an embedding of the code's `description` under a special key **`"[DESCRIPTION]"`**. This was an **undocumented deviation from STEP_05** — STEP_05 already builds the description into the main `icd11_codes.embedding` vector (`"<title>. <description>. Also known as: <inclusions>"`, STEP_05 line 155), so the separate description vector was redundant and the misnamed key caused real confusion (a `<> '{}'` coverage check became misleading; codes with zero inclusions still got a non-empty JSONB).

**Resolution (2026-05-17):** `[DESCRIPTION]` removed from the script. `icd11_codes.inclusion_embeddings` is now **inclusion-term-only** — keyed solely by raw inclusion text, `{}` for codes with no inclusions. Description-level matching stays in the main `embedding` column, per STEP_05. The script auto-cleans legacy polluted rows: any row still containing a `[DESCRIPTION]` key is flagged by `_needs_processing()` and rewritten (inclusion-only, or `{}`) on the next normal run — `cleaned` counter reports how many stale keys were stripped.

Consequences for D3/D5 (now simple — no special-casing needed):
- The DDx ranker's `max(cosine(q, v) for v in inclusion_embeddings.values())` is now a pure inclusion-term max-pool. **Do not** add description handling back into it; description signal is already in the main `embedding`.
- True inclusion-term coverage is now just `inclusion_embeddings <> '{}'::jsonb` again — no `[DESCRIPTION]` carve-out required. (A code legitimately has `{}` when it has no WHO inclusion synonyms; that is correct, not missing data.)
- The new D3 `exclusion_embeddings` JSONB must likewise be **exclusion-term-only** (no `[DESCRIPTION]` key) — mirror the clean shape, never the old quirk.
- **Prerequisite for D3 verification:** the inclusion backfill must have been re-run post-fix so no `[DESCRIPTION]` keys remain. Confirm with: `SELECT COUNT(*) FROM icd11_codes WHERE inclusion_embeddings ? '[DESCRIPTION]';` → must return **0** before trusting any `inclusion_embeddings` coverage check.

### Issue 2 — backfill scripts were not idempotent (now fixed for inclusions)

As originally written, `migrate_inclusion_embeddings.py`: (a) had no `--help` (ran the full migration even when `--help` was passed), (b) selected every row with inclusions **OR a non-empty description** with no skip for already-populated rows, so every run re-embedded ~2414 rows, and (c) had no chapter filter. The Phase A doc's claim that it is "idempotent — skips populated rows" was inaccurate.

**Fixed 2026-05-17:** the script now has real `argparse` (`--help` is safe), an idempotency skip (`_needs_processing()` — a row is skipped when every inclusion-term key is already present **and** no stale `[DESCRIPTION]` key remains), `--chapters` scoping, `--force`, and `--dry-run`. Correct usage for future newly ingested chapters:
```bash
python -m ddx.migrate_inclusion_embeddings --chapters 18,21 --dry-run   # preview
python -m ddx.migrate_inclusion_embeddings --chapters 18,21             # idempotent backfill
```

**Mandate for D3:** `backfill_exclusion_embeddings.py` (the new D3 script) must be idempotent + `--dry-run` + `--force` **from the start** (already specified in D3), and must NOT replicate the non-idempotent pattern this script originally had. It should also support a `--chapters` filter so future ICD-11 chapter ingests can be topped up cheaply rather than reprocessing all 3,914+ rows.

### Note for D1 — orphaned `parent_code` is expected at chapter roots

A `parent_code` integrity check on the full table returns ~13 "orphaned" rows. These are **benign and expected**: chapter-root entities (`02`, `05`, `08`, `11`, `16`, `18`, `21`) have no in-table parent, and the `HA00`–`HA0Z` codes point at the WHO block grouping `HA00-HA0Z` which STEP_05 intentionally did not ingest (only entities with real codes are stored). **D1's ancestor walk must treat "parent_code not found in icd11_codes" as "top of tree reached — stop", never as an error.** The recursive CTE in §D1 already terminates correctly; just ensure the calling code does not raise on a non-resolving parent.

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

JSONB shape: `{"<exclusion text>": [<1536-dim vector as list>], ...}` — mirrors the *shape* of `inclusion_embeddings` but **exclusion-term-only**. Do **not** add a `[DESCRIPTION]` key (see §Known issues, Issue 1) — the exclusion penalty must be driven purely by WHO exclusion phrases, not diluted by a description vector.

Backfill script `ddx/backfill_exclusion_embeddings.py` (must follow the idempotency lessons in §Known issues, Issue 2):
- Skip rows where `cardinality(exclusions) = 0`.
- Skip rows where `exclusion_embeddings` already has a key for every entry in `exclusions` (idempotent — implement a real skip check, not a "select everything and overwrite" pattern).
- Use the same embed text format as inclusions: just the exclusion phrase, raw.
- Real `argparse` so `--help` is side-effect-free. Support `--dry-run`, `--force`, `--limit N`, **and `--chapters`** (so future ICD-11 chapter ingests can be topped up cheaply instead of reprocessing all 3,914+ rows).
- Batch in groups of 10 for fewer DB round-trips.
- CLI: `--dry-run` (no DB writes, no embedding calls), `--force` (recompute even if already populated), `--limit N` (for testing).

DDx ranker change — symmetric to existing inclusion logic:
```python
EXCLUSION_PENALTY_WEIGHT = 0.3   # λ — start here, tune from logged DDx outputs

# incl_embeddings is inclusion-term-only (the legacy "[DESCRIPTION]" key was
# removed 2026-05-17 — see §Known issues, Issue 1). Description signal already
# lives in the main `embedding` column, so do NOT add it back here.
# excl_embeddings is likewise exclusion-term-only by design.
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

### D5 — Clinician-facing score transparency (top-5 DDx)

**Why this exists:** D3 changes what the DDx confidence number *means*. A single opaque float is no longer clinically defensible — a clinician triaging a top-5 list must see *why* each diagnosis ranked where it did, including when WHO's own exclusion rules pushed one down, and how trustworthy the CPG match behind it is. This deliverable makes the score auditable, not just computed.

**Files touched:** the DDx ranker (same module as D3), the DDx response model (find the dataclass/Pydantic model the API returns for DDx candidates), and the clinician-facing renderer (find via `grep -r "differential" --include="*.py" agent/` and the API serializer for the DDx list).

#### D5a — Structured score-contribution object

Every DDx candidate must carry its score *broken into named contributors*, not just `final_score`. Add to the DDx candidate model:

```python
@dataclass
class ScoreBreakdown:
    base_similarity:     float   # symptom ↔ code title+description
    inclusion_match:     float   # best matching WHO synonym/lay-term sim
    inclusion_phrase:    str | None   # WHICH synonym matched (for display), e.g. "heart attack"
    exclusion_penalty:   float   # EXCLUSION_PENALTY_WEIGHT * strongest exclusion sim (>=0)
    exclusion_phrase:    str | None   # WHICH exclusion fired (for display), e.g. "type 1 diabetes"
    final_score:         float   # base + inclusion_match - exclusion_penalty
    # routing provenance — from D1/D2/D4, attached to the CPG this DDx routed to
    route_method:        str     # exact | ancestor_d1 | ancestor_d2 | sibling | semantic | out_of_scope
    route_similarity:    float | None   # populated only when route_method == "semantic"
```

Rules:
- `final_score` must equal `base_similarity + inclusion_match - exclusion_penalty` (assert this in code; a test enforces it).
- `inclusion_phrase` / `exclusion_phrase` are the actual WHO text that produced the contribution — null when that term didn't fire (sim below a display floor of `0.5`).
- `route_method` / `route_similarity` come straight from D1/D2/D4's routing result for the CPG this candidate maps to. Do not recompute.

#### D5b — Top-5 clinician rendering spec

The top-5 DDx list rendered to the clinician must show, per candidate, in this order:

```text
#{rank}  {ICD code} — {ICD title}                          confidence: {final_score:.0%}
         CPG: {matched CPG title}   [provenance badge]
         Why this rank:
           ✓ Symptom match: {base_similarity:.0%}
           ✓ Matched known term "{inclusion_phrase}" (+{inclusion_match:.0%})        ← omit line if inclusion_phrase is null
           ⚠ WHO excludes "{exclusion_phrase}" — ranked lower (−{exclusion_penalty:.0%})  ← omit line if exclusion_phrase is null
```

**Provenance badge** (the single most important trust signal — render it visually distinct):

These are the **only** `route_method` values the system produces — the implementer must handle all six and map each to exactly the badge below:

| route_method | Badge text | Clinician meaning | Brief example |
|---|---|---|---|
| `exact` | `✓ Exact guideline match` | The CPG explicitly covers this ICD code. Highest trust. | Code `BC81.3` (AF) is listed in the Atrial-Fibrillation CPG's verified scope. |
| `ancestor_d1` / `ancestor_d2` | `≈ Matched via broader category` | No exact CPG; matched a parent category (1–2 levels up). Reasonable, but broader. | Code `BA21.0` (hypotension) not in any scope; its parent `BA20–BA2Z` is in the Anaesthesia CPG → `ancestor_d1`. |
| `sibling` | `≈ Matched via related code` | Matched a sibling code's CPG. Use clinical judgement. | Code `BA01.1` not in scope; a sibling `BA01.0` (same parent) is in the IHD CPG → matched via the sibling. |
| `semantic` | `~ Fuzzy match ({route_similarity:.0%})` | Matched only by text similarity, not curated scope. **Show the % — lower trust.** | ENT query, code not in any loaded chapter; query text is 0.71 cosine to the CKD CPG scope → `semantic`, badge shows `~ Fuzzy match (71%)`. |
| `out_of_scope` | `✕ No guideline covers this` | No CPG matched. Do not present as guideline-backed. | "Acute appendicitis management" — no surgical CPG loaded, no exact/ancestor/sibling/semantic hit → `out_of_scope`. |

Hard requirements:
- The provenance badge is **never** hidden. A `semantic` or `out_of_scope` result must never visually masquerade as an `exact` curated match.
- The exclusion line uses a caution glyph (`⚠`) and the word "ranked lower" — it is a *caution*, not a removal. The diagnosis still appears in the list; it just sits lower with a stated reason.
- If `final_score` is below a display floor (`DDX_DISPLAY_FLOOR = 0.30`), the candidate is still shown in the top-5 if it makes the cut, but its confidence is rendered as "low confidence" text alongside the percentage, not just a bare number.
- No marketing language. "Matched via broader category", not "Confidently identified".

#### D5c — Plain-language explainer (one-time, static)

Add a short static "How confidence is scored" explainer the clinician UI can link to (a markdown string or constant — the implementer picks the delivery mechanism, but the *content* is fixed):

```text
Each diagnosis is scored from three signals:
 • Symptom match — how closely the patient's presentation matches the
   condition's official description.
 • Known-term match — bonus when the patient's words match a recognised
   synonym for the condition (e.g. "heart attack" for myocardial infarction).
 • Exclusion caution — the score is reduced when the presentation matches
   something the WHO guideline explicitly says this code is NOT. The
   diagnosis is not removed; it is ranked lower with the reason shown.

The CPG badge tells you HOW the guideline behind a diagnosis was found:
an exact match is the strongest; a fuzzy/semantic match is shown with its
similarity % so you can weigh it accordingly.
```

### D6 — Math ↔ LLM rerank merge (signal-fed + disagreement surfacing)

**Why this exists:** D3 adds WHO's own exclusion rule to the *math* score. The system already has a **Math → LLM Rerank** stage. Without this deliverable, the LLM rerank runs unaware of the exclusion signal and can silently re-promote a WHO-excluded diagnosis — destroying both the safety value of D3 and the honesty of D5 (the displayed breakdown would no longer reflect the order the clinician sees). D6 makes the merge explicit: **the LLM must reason with the math signals, and when it overrides the math order it must say so on the record.**

This is a **B+C hybrid**: math signals are fed *into* the LLM rerank prompt (B), and material LLM↔math disagreement is surfaced to the clinician with the LLM's stated reason (C).

**Files touched:** the LLM rerank stage (find via `grep -r "rerank" --include="*.py" agent/`), the DDx response model (extend the D5a `ScoreBreakdown` / candidate model), the clinician renderer (D5b).

#### D6a — Feed math signals into the rerank prompt (the B half)

The LLM rerank prompt must include, per candidate, the structured math evidence — not just the candidate names:

```text
Candidate {n}: {ICD code} — {ICD title}
  math_rank: {rank in the math-ordered pool}
  symptom match: {base_similarity:.2f}
  known-term match: {inclusion_match:.2f}  (matched: "{inclusion_phrase}")
  WHO exclusion fired: "{exclusion_phrase}"  (penalty {exclusion_penalty:.2f})   ← only if exclusion_phrase not null
  CPG provenance: {route_method}{ " "+route_similarity if semantic }
```

System-prompt rules the rerank LLM must be given (exact intent, implementer may word-smith):

```text
You are re-ranking differential diagnoses. Each candidate carries a
math score broken into: symptom match, known-term match, and a WHO
exclusion penalty.

- Treat a fired WHO exclusion as strong negative evidence. You MAY
  override it only if the clinical picture clearly warrants it, and
  you MUST then state the clinical reason in `override_reason`.
- Do not silently move a WHO-excluded candidate up the list. Any
  reorder that contradicts the math order on an exclusion-penalised
  candidate requires an explicit `override_reason`.
- You are reasoning over evidence already retrieved; do not invent
  new findings not present in the patient input or CPG evidence.
```

The LLM rerank returns, per candidate: `llm_rank`, and — when its rank differs materially from `math_rank` — an `override_reason` string.

#### D6b — Extend the candidate model (the C half)

Add to the D5a candidate model:

```python
math_rank:       int
llm_rank:        int                 # final rank shown to clinician
rank_delta:      int                 # math_rank - llm_rank (signed)
override_reason: str | None          # required when |rank_delta| crosses the disagreement threshold,
                                     # ESPECIALLY when exclusion_phrase is not null
```

Disagreement constant:

```python
RERANK_DISAGREEMENT_DELTA = 2   # |math_rank - llm_rank| >= this → "materially disagreed", reason required
```

Hard rule (assert in code + test): if `exclusion_phrase is not null` AND the LLM moved that candidate *up* relative to `math_rank` by `>= RERANK_DISAGREEMENT_DELTA`, `override_reason` MUST be non-empty. A WHO exclusion can be overruled, but never silently.

#### D6c — Surface disagreement in the top-5 (extends D5b render)

The final order shown to the clinician is `llm_rank`. When a candidate's `|rank_delta| >= RERANK_DISAGREEMENT_DELTA`, the render adds one line under that candidate:

```text
   ↕ Reasoning model moved this {up|down} (math had it #{math_rank}, now #{llm_rank})
     Reason: {override_reason}
```

**Brief worked example** — `RERANK_DISAGREEMENT_DELTA = 2`:

| Candidate | math_rank | llm_rank | rank_delta | Surfaced? |
|---|---|---|---|---|
| Acute coronary syndrome | 1 | 2 | 1 | No — \|1−2\|=1 < 2, just a shuffle |
| Pulmonary embolism | 4 | 1 | 3 | **Yes** — \|4−1\|=3 ≥ 2 |

PE rendered to the clinician:
```text
#1  CA40.0 — Pulmonary embolism                            confidence: 71%
    ↕ Reasoning model moved this up (math had it #4, now #1)
      Reason: sudden pleuritic chest pain + tachycardia + recent
      immobilisation; math under-weighted the risk-factor cluster.
```
If PE had also carried a WHO exclusion penalty, that same line gets the `⚠` glyph and `override_reason` cannot be empty (the D6b hard rule).

Rules:
- The line is shown only on materially-moved candidates — not on every row (avoids noise).
- If the moved candidate had a WHO exclusion and was promoted, render the reason with the same `⚠` caution glyph so the clinician's eye catches "the model overruled a WHO exclusion here, and here's why".
- The math breakdown (D5b) is still shown beneath — the clinician sees both the math view and the LLM's final call, and exactly where/why they diverged.
- Never hide the divergence. A clinician must be able to tell "math and the reasoning model agreed" from "the model overruled the math, for this stated reason" at a glance.

#### D6d — Telemetry

Log per query: count of candidates where `|rank_delta| >= RERANK_DISAGREEMENT_DELTA`, and separately the count of *exclusion-overrides* (exclusion_phrase set AND promoted past threshold). These two numbers are how you later tune `EXCLUSION_PENALTY_WEIGHT` and `RERANK_DISAGREEMENT_DELTA` from real usage — high exclusion-override rate means the penalty weight is mistuned or the LLM is too eager.

## Constants summary

Define once near the top of the routing module:
```python
ANCESTOR_MAX_DEPTH           = 2
SEMANTIC_FALLBACK_THRESHOLD  = 0.65
SEMANTIC_FALLBACK_TOP_K      = 3
EXCLUSION_PENALTY_WEIGHT     = 0.3
OUT_OF_SCOPE_INCL_THRESHOLD  = 0.55
DDX_PHRASE_DISPLAY_FLOOR     = 0.5    # below this, inclusion/exclusion phrase shown as null
DDX_DISPLAY_FLOOR            = 0.30   # below this, render "low confidence" alongside the %
RERANK_DISAGREEMENT_DELTA    = 2      # |math_rank - llm_rank| >= this → reason required + surfaced
```

Eight tunable constants. Log enough to tune them empirically from real DDx logs. `DDX_PHRASE_DISPLAY_FLOOR`, `DDX_DISPLAY_FLOOR`, `RERANK_DISAGREEMENT_DELTA` are display/telemetry-only and never change `final_score` or `llm_rank`.

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

`tests/test_score_breakdown.py` (D5):

- `test_final_score_equals_sum_of_parts` — `final_score == base_similarity + inclusion_match - exclusion_penalty` for a range of synthetic inputs (this is the core invariant).
- `test_inclusion_phrase_null_below_floor` — best inclusion sim 0.4 < `DDX_PHRASE_DISPLAY_FLOOR` → `inclusion_phrase` is None, line omitted.
- `test_exclusion_phrase_populated_when_fired` — exclusion sim 0.7 → `exclusion_phrase` = the actual WHO text, penalty > 0.
- `test_route_provenance_passed_through_not_recomputed` — ranker receives `route_method="semantic", route_similarity=0.71` → breakdown carries them verbatim.
- `test_badge_text_per_route_method` — each of the 6 `route_method` values maps to the exact badge string in the D5b table.
- `test_semantic_badge_includes_similarity` — `route_method="semantic"`, sim 0.66 → badge renders `~ Fuzzy match (66%)`.
- `test_exclusion_line_uses_caution_not_removal` — rendered exclusion line contains "⚠" and "ranked lower", never "removed"/"excluded from list".
- `test_low_confidence_label_below_display_floor` — `final_score` 0.22 < `DDX_DISPLAY_FLOOR` → render includes "low confidence" text.
- `test_out_of_scope_badge_never_looks_curated` — `route_method="out_of_scope"` → badge is the `✕ No guideline covers this` string, never an exact-match style.
- `test_top5_render_omits_null_phrase_lines` — candidate with null inclusion_phrase and null exclusion_phrase → only the symptom-match line renders, no empty bullets.

`tests/test_rerank_merge.py` (D6) — mock the LLM rerank client; no real LLM calls:

- `test_rerank_prompt_includes_math_signals` — built prompt contains base/inclusion/exclusion_phrase/route per candidate.
- `test_rerank_prompt_includes_exclusion_when_fired` — candidate with exclusion_phrase → its line is in the prompt; candidate without → no exclusion line for it.
- `test_rank_delta_computed` — `rank_delta == math_rank - llm_rank`, signed, for a reordered list.
- `test_override_reason_required_when_exclusion_promoted` — LLM moves an exclusion-penalised candidate up by ≥ `RERANK_DISAGREEMENT_DELTA` with empty `override_reason` → raises / rejects (the hard rule).
- `test_override_reason_not_required_for_small_moves` — `|rank_delta|` = 1 → no `override_reason` demanded.
- `test_no_override_reason_when_llm_agrees` — LLM keeps math order → `override_reason` is None for all, no disagreement line rendered.
- `test_disagreement_line_rendered_above_threshold` — `|rank_delta|` ≥ threshold → render contains the `↕ Reasoning model moved this …` line with the reason.
- `test_disagreement_line_absent_below_threshold` — `|rank_delta|` < threshold → no `↕` line.
- `test_exclusion_override_uses_caution_glyph` — exclusion-penalised candidate promoted with reason → rendered line carries the `⚠` glyph.
- `test_final_order_is_llm_rank` — clinician-facing order equals `llm_rank` ordering, not `math_rank`.
- `test_telemetry_counts_disagreements_and_overrides` — D6d counters report correct disagreement count and exclusion-override count for a synthetic rerank.
- `test_force_rerank_order_inert_in_prod_config` — the Smoke 8 `--force-rerank-order` harness is rejected / unreachable when config is production; only honoured under the test/staging flag.

All tests must mock the WHO API, the DB pool, the embedding client, **and the LLM rerank client** (none called for real). **No real Bedrock or LLM spend in pytest.**

## E2E smoke tests (manual, post-deploy)

**Dry-run scope (read first).** `--dry-run` exists *only* on the two backfill scripts (`backfill_scope_embeddings`, `backfill_exclusion_embeddings`) — the data-prep steps for D2/D3. The **live routing/rerank changes (D1, D4, D5, D6) have no dry-run mode by design**: they are pure read-path logic with no destructive side effects, so their safety net is the mocked unit tests (pre-merge) plus these E2E smokes (post-deploy). Do not assume a dry-run guard exists for the query pipeline.

**Pre-deploy gate.** Run the full smoke suite below against **staging** (pointed at a copy of prod data) and get all of Smoke 1–9 green **before** promoting to production. Production smokes are then a confirmation pass, not the first time these paths run live.

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

### Smoke 7 — Score transparency (D5, the clinician-facing check)
Re-use the Smoke 4 query (the one that triggers an exclusion penalty) and the Smoke 3 query (semantic route). For each, capture the rendered top-5 DDx as a clinician would see it. Verify on the exclusion case:
- The downranked diagnosis still appears in the top-5 (not removed).
- Its breakdown shows all three lines with real numbers; `final_score` visibly equals `base + inclusion − exclusion_penalty`.
- The `⚠ WHO excludes "<phrase>"` line names the actual WHO exclusion text.

And on the semantic case:
- The provenance badge reads `~ Fuzzy match (NN%)` with the real similarity — **not** `✓ Exact guideline match`.

Paste both rendered top-5 blocks verbatim into the report. This is the deliverable a clinician actually sees — it must be legible and honest at a glance.

### Smoke 8 — Math ↔ LLM disagreement surfacing (D6)
**Deterministic harness required — do not rely on the LLM happening to disagree.** Add a test-only `--force-rerank-order` flag (or equivalent injectable fixture) on the DDx endpoint that lets the smoke runner supply a fixed `llm_rank` permutation + `override_reason` per candidate, bypassing the real LLM call. This guarantees the D6c/D6d path is exercised every run regardless of model behaviour. The flag must be inert/unreachable in production config (assert this in a unit test).

Run two deterministic cases:

1. **Plain disagreement** — force a candidate from `math_rank=4` to `llm_rank=1` with a supplied reason. Verify:
   - Final order shown = `llm_rank`, not `math_rank`.
   - The moved candidate shows the `↕ Reasoning model moved this …` line with the supplied `override_reason`.
   - The math breakdown (D5b) is still shown beneath it.
   - D6d telemetry reports exactly 1 disagreement, 0 exclusion-overrides.
2. **Exclusion override** — pick an exclusion-penalised candidate (from Smoke 4) and force-promote it ≥ `RERANK_DISAGREEMENT_DELTA` with a clinical `override_reason`. Verify:
   - The disagreement line carries the `⚠` glyph.
   - The D6b hard rule passes (non-empty `override_reason` accepted) and, as a negative check, the same forced promotion with an **empty** reason is rejected.
   - D6d telemetry reports ≥1 disagreement **and** ≥1 exclusion-override.

Then run **one non-deterministic sanity pass** (no force flag) on a realistic ambiguous query just to confirm the real LLM path also produces a well-formed result — but the pass/fail gate is the two deterministic cases above, not this one.
Paste both deterministic rendered blocks verbatim into the report.

### Smoke 9 — Sibling route (D1, the otherwise-untested branch)
The sibling fallback is the one D1 branch no other smoke exercises. Pick (via SQL) an ICD code that is **not** in any `documents.icd11_scope`, whose parent is **also not** in any scope, but which has a **sibling** (same `parent_code`) that **is** in some CPG's scope:
```sql
-- find a usable sibling-route case
SELECT c.code AS predict_code, s.code AS sibling_in_scope, c.parent_code
FROM icd11_codes c
JOIN icd11_codes s ON s.parent_code = c.parent_code AND s.code <> c.code
WHERE NOT EXISTS (SELECT 1 FROM documents d WHERE c.code = ANY(d.icd11_scope))
  AND NOT EXISTS (SELECT 1 FROM documents d WHERE c.parent_code = ANY(d.icd11_scope))
  AND EXISTS     (SELECT 1 FROM documents d WHERE s.code = ANY(d.icd11_scope))
LIMIT 5;
```
Drive a query that predicts `predict_code`. Verify:
- `route_method` = `sibling` (not `exact`, not `ancestor_*`, not `semantic`).
- The badge renders `≈ Matched via related code`.
- Ancestor lookup is shown (in logs/telemetry) to have run **and missed** before the sibling match — confirming the documented order (exact → ancestor → sibling).
If the SQL returns 0 rows, state that in the report (no sibling-route case exists in the current corpus) and mark this smoke N/A with the query output as evidence — do not skip silently.

## Out of scope

- ❌ Hybrid retrieval (vector + code-prefix + lexical) for ICD lookup. Defer until DDx logs show actual misses.
- ❌ Re-embedding the existing `icd11_codes.embedding` column. The main embedding stays as-is.
- ❌ Adding new ICD-11 chapters. Stick with the 5+1 already loaded.
- ❌ Touching `chunks` table — that's Phase A's territory.
- ❌ Modifying `documents.icd11_scope` for existing CPGs. The 16 verified entries are immutable.
- ❌ Changing the existing inclusion-based ranker logic. D3 *adds* an exclusion penalty term — it does not rewrite inclusion scoring.
- ❌ Real WHO API calls, or real LLM rerank calls, in tests.
- ❌ Tuning the eight constants — ship with the defaults above and tune from real DDx logs in a follow-up.
- ❌ Replacing or retraining the LLM rerank model itself. D6 *feeds signals into* the existing rerank stage and surfaces its disagreements — it does not swap the model or change its core prompt beyond the documented additions.
- ❌ Frontend visual design / CSS for D5/D6. This doc fixes the *content, ordering, badge text, and honesty rules* of the clinician render; pixel-level styling is a follow-up for whoever owns the UI. The structured candidate model (D5a + D6b) is the contract — a text/CLI rendering that satisfies §D5b and §D6c is sufficient to mark this done.

## Done criteria

All twelve must hold:

1. Migrations 007 and 008 applied cleanly. `\d documents` shows `scope_embedding vector(1536)`. `\d icd11_codes` shows `exclusion_embeddings jsonb`.
2. `python -m ddx.backfill_scope_embeddings` populates all 16 documents. Verify: `SELECT COUNT(*) FROM documents WHERE scope_embedding IS NOT NULL` returns 16.
3. `python -m ddx.backfill_exclusion_embeddings` populates the 402 rows with non-empty exclusions. Verify: `SELECT COUNT(*) FROM icd11_codes WHERE exclusion_embeddings != '{}'::jsonb` returns 402.
4. Re-running both backfills makes 0 embedding calls and 0 DB writes (idempotent).
5. `pytest tests/test_routing_fallback.py tests/test_exclusion_rerank.py tests/test_score_breakdown.py tests/test_rerank_merge.py -v` all green. No real Bedrock, WHO, or LLM calls.
6. All nine smoke tests in §6 produce the expected result (Smoke 9 may be a documented N/A if the corpus has no sibling-route case — the SQL output must be shown). The full suite passed on **staging before** prod promotion. Telemetry is captured. Smoke 7 and the two Smoke 8 deterministic blocks are pasted verbatim.
7. **(D5)** Every DDx candidate returned by the API carries the full breakdown (D5a + D6b fields) populated. `final_score == base_similarity + inclusion_match - exclusion_penalty` holds for every candidate (spot-check 10 from a live query).
8. **(D5)** The rendered top-5 for a `semantic`-routed query shows the `~ Fuzzy match (NN%)` badge — never an exact-match badge. The rendered top-5 for an exclusion-penalised candidate keeps it in the list with the `⚠ ... ranked lower` line, not removed.
9. **(D6)** The clinician-facing order equals `llm_rank`. The LLM rerank prompt provably contains the math signals per candidate (capture one prompt from a live query).
10. **(D6)** Hard rule holds: no exclusion-penalised candidate is promoted ≥ `RERANK_DISAGREEMENT_DELTA` without a non-empty `override_reason`. Materially-moved candidates render the `↕` disagreement line; D6d telemetry counters are emitted. The Smoke 8 `--force-rerank-order` harness is proven inert under production config (unit test asserts it).
11. The 16 verified `icd11_scope` entries on existing documents are byte-for-byte unchanged. Verify: `SELECT title, icd11_scope, scope_verified FROM documents` matches the pre-deploy snapshot.
12. The existing `embedding` column on `icd11_codes` is byte-for-byte unchanged across the full table. Verify the checksum equals the canonical P0 baseline:
   ```sql
   SELECT MD5(string_agg(embedding::text, '|' ORDER BY code)) FROM icd11_codes;
   -- MUST return: d8a2db83e95d7655aa3b73cdf72b2631
   -- (canonical baseline, see §Preconditions P0; unless the corpus was
   --  re-ingested, in which case the P0 value was recomputed and replaced.)
   ```

## Report back

When you finish, return the following — concise, no marketing:

1. **Files created/modified** — exact paths.
2. **Migrations applied** — output of `\d documents` and `\d icd11_codes` (relevant columns only).
3. **Backfill results**:
   - `documents.scope_embedding`: rows populated, embedding calls made, runtime, total cost (Bedrock invocations × $0.0001 / 1k tokens estimate).
   - `icd11_codes.exclusion_embeddings`: rows populated (expect 402), embedding calls made (expect ~748), runtime, total cost.
4. **Idempotency check** — output of re-running both backfills (expect "0 rows updated").
5. **Test output** — last ~30 lines of `pytest tests/test_routing_fallback.py tests/test_exclusion_rerank.py tests/test_score_breakdown.py tests/test_rerank_merge.py -v`.
6. **Smoke test telemetry** — table with one row per routing smoke test (Smoke 1–6 and 9):
   | Smoke # | Query (truncated) | Predicted ICD | route_method | Matched CPG | Notes |
   |---------|-------------------|---------------|--------------|-------------|-------|
   For Smoke 9, include the discovery SQL output (or state N/A with that output as evidence).
7. **D5 rendered output** — Smoke 7's two top-5 blocks pasted **verbatim** (the exclusion-penalty case and the semantic-route case), exactly as a clinician would see them. Plus one spot-check showing `final_score == base + inclusion − exclusion_penalty` arithmetic for one candidate.
8. **D6 rendered output** — Smoke 8's **two deterministic** top-5 blocks pasted **verbatim** (plain disagreement + exclusion override), the negative-check result (empty `override_reason` rejected), one captured LLM rerank prompt showing the math signals are present, and the D6d telemetry counts (disagreements, exclusion-overrides) for both cases.
9. **Pre/post invariants** — the two checksum/count queries in §Done criteria #11 and #12, before and after.
10. **Constants used** — confirm the eight constants in §Constants summary are at their default values (and listed in code at the top of the routing module).
11. **Any deviations** from this brief and why.
12. **Follow-ups noticed but not done** — likely candidates: tuning the eight constants from logged DDx data (esp. `EXCLUSION_PENALTY_WEIGHT` and `RERANK_DISAGREEMENT_DELTA` from D6d telemetry), adding hybrid retrieval if logs show ICD lookup misses, pixel-level UI styling for the D5/D6 badges, surfacing the breakdown + disagreement view in the production frontend.
