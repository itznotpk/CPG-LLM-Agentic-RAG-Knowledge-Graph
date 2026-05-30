# DDx Routing Robustness + Exclusion-Aware Re-ranking Report

## P0 Baseline

Captured: 2026-05-18

### ICD-11 checks

- `SELECT COUNT(*) FROM icd11_codes`: 5672
- `SELECT COUNT(*) FROM icd11_codes WHERE cardinality(exclusions) > 0`: 703
- `icd11_codes.embedding atttypmod`: 1536
- `SELECT COUNT(*) FROM icd11_codes WHERE inclusion_embeddings ? '[DESCRIPTION]'`: 0
- `embedding_checksum`: `d8a2db83e95d7655aa3b73cdf72b2631`

Notes:
- The ICD row/exclusion counts differ from the older task brief values (`3914` / `402`) because the live DB now includes additional chapters. The checksum matches the canonical value recorded in the brief.

### Documents checks (refreshed 2026-05-22 against live Neon)

- `SELECT COUNT(*) FROM documents`: 389  (was 252 at 2026-05-18 baseline)
- Rows with `metadata->>'cpg_name' IS NOT NULL`: 389
- Distinct CPG groups: 29  (was 19)
- Rows with non-empty `icd11_scope`: 0
- Rows with non-empty `procedure_scope`: 0
- Rows with `scope_verified = TRUE`: 0
- Distinct verified CPG groups: 0
- `icd11_codes.exclusion_embeddings` exists: true (D3 backfill applied)

Scope snapshot (regenerated 2026-05-22, 389 rows):
- `tasks/Next-Step/Last Step Improvement/DDx Gap/ddx_routing_p0_documents_scope_snapshot.json`

Scope-tagging readiness (review file vs live DB):
- 28 of 29 live CPG groups have a reviewed scope in `cpg_scope_review.md` (after
  reconciling 11 edition/year name differences + merging Cancer-Pain Part A/B).
- 1 live group has NO reviewed scope: **Nasopharyngeal-Carcinoma** (11 rows) — needs a scope entry.
- 1 reviewed group is NOT yet ingested: **Type-2-Diabetes-Mellitus(6th Edition)** (0 rows).
- Ingestion path (single source of truth): `python -m ingestion.verify_cpg_scope --verifier "<name>" [--dry-run]` parses `cpg_scope_review.md` and writes `icd11_scope` / `procedure_scope` / `scope_rationale` (from `cpg_scope_rationale`) + stamps `scope_verified`. Idempotent; not-yet-ingested CPGs are skipped.

### P0 Gate Status

Blocked.

The task brief requires populated and verified `documents.icd11_scope` for the reviewed CPGs before D1/D2 routing work is validated. The current Neon `documents` table has no populated ICD or procedure scopes, so exact routing, sibling fallback, and the ancestor-hierarchy fallbacks cannot be meaningfully smoke-tested against the live CPG corpus yet.

Recommended repair before continuing:
- Apply the reviewed CPG scopes from `tasks/cpg_scope_review.md` to the live `documents` table, accounting for current DB group-name differences.
- Re-run the P0 document checks and capture a new scope snapshot.
- Continue to P1/P2 only after scope rows are populated and verified.

## P1 / D3 Exclusion-Aware DDx Re-ranking

Status: implemented and backfilled.

Files created/modified:
- `sql/migrations/008_icd11_exclusion_embeddings.sql`
- `ddx/backfill_exclusion_embeddings.py`
- `ddx/search_ddx.py`
- `agent/clinical_stages.py`
- `tests/test_exclusion_rerank.py`

Migration applied:
- `icd11_codes.exclusion_embeddings` exists: true

Backfill results:
- Rows with non-empty `exclusions`: 703
- Rows with non-empty `exclusion_embeddings`: 703
- Remaining empty rows among rows with exclusions: 0
- Total exclusion phrases: 1423
- Embedded exclusion phrases: 1423

Run notes:
- First full run timed out after partial progress.
- Resume was safe because `ddx.backfill_exclusion_embeddings` is idempotent.
- Final resume updated 43 rows and made 119 embedding calls.

Idempotency check:
```text
Found 703 candidate rows; 0 pending, 703 skipped
Backfill complete: 0 rows updated, 703 skipped, 0 embedding calls
```

Targeted tests:
```text
tests/test_exclusion_rerank.py::test_exclusion_backfill_needs_processing_when_key_missing PASSED
tests/test_exclusion_rerank.py::test_exclusion_backfill_skips_when_all_terms_present PASSED
tests/test_exclusion_rerank.py::test_exclusion_backfill_force_recomputes_complete_row PASSED
tests/test_exclusion_rerank.py::test_exclusion_penalty_downranks_but_keeps_candidate PASSED
tests/test_exclusion_rerank.py::test_inclusion_boost_and_exclusion_penalty_are_both_in_final_score PASSED
tests/test_clinical_stages.py::test_stage2_builds_symptom_text PASSED
tests/test_clinical_stages.py::test_stage2_builds_symptom_text_minimal PASSED
tests/test_clinical_stages.py::test_stage2_calls_search_ddx PASSED
tests/test_clinical_stages.py::test_stage2_handles_empty_ddx PASSED
tests/test_clinical_stages.py::test_stage2_rerank_called_by_default PASSED
tests/test_clinical_stages.py::test_stage2_rerank_skipped_when_false PASSED

11 passed, 20 deselected
```

Implementation notes:
- `ddx/search_ddx.py` now computes `final_score = base_similarity + inclusion_score - 0.3 * exclusion_score`.
- WHO exclusion matches are retained in the candidate list, not hard-filtered.
- Exclusion evidence fields are returned for downstream rendering: `exclusion_match`, `matched_exclusion`, `exclusion_similarity`, and `exclusion_penalty`.
- `DDxResult` now carries the exclusion and score fields through Stage 2.

Remaining blocker:
- Routing phases P2/P3 remain blocked until live `documents.icd11_scope` / `procedure_scope` are populated and verified.

## P2 / D1 Routing Core (+ D2 semantic_scope fallback, revived 2026-05-22)

Status: locally implemented and unit-tested. Not applied/backfilled on Neon.

Files created/modified:
- `agent/routing.py`
- `agent/db_utils.py`
- `ddx/backfill_scope_embeddings.py`
- `tests/test_routing.py`

Implemented (eight-level router):
- D1 exact ICD scope routing (direct code match + range-entry match).
- Sibling fallback — same-parent codes incl. `.Y` / `.Z` variants.
- `ancestor_d1` — direct parent category.
- `ancestor_d1_sibling` — peer categories of the parent.
- `ancestor_d1_sibling_child` — children of those peer categories.
- `ancestor_d2` — grandparent block; ancestor walk capped at depth 2 (`ANCESTOR_MAX_DEPTH = 2`).
- `procedure_scope` — match on shared procedure tags.
- `semantic_scope` (D2) — cosine similarity between `icd11_codes.embedding` and
  `documents.scope_embedding`, gated at `SEMANTIC_SCOPE_THRESHOLD = 0.32` (re-calibrated 2026-05-25 after 7 clinician scope edits; was 0.40, originally 0.65); catches
  cross-chapter conditions the structural walk misses.
- Route method stamping through `CPGDocRef.match_type`: `exact`, `sibling`, `ancestor_d1`, `ancestor_d1_sibling`, `ancestor_d1_sibling_child`, `ancestor_d2`, `procedure_scope`, `semantic_scope`. `find_cpgs_for_code` returns `[], "out_of_scope"` only when all eight levels miss.

D2 semantic_scope fallback — REVIVED (commit 435c781, merged 2026-05-22):
- `_semantic_scope_match` in `agent/routing.py` runs after the structural + procedure_scope levels.
- Requires `documents.scope_embedding` to be populated — see `ddx/backfill_scope_embeddings.py`.
- "No CPG matched" (route_method `none`) now only fires after semantic_scope also misses; the D4 out-of-scope detector then takes over.

Not run on Neon:
- No document scope embeddings were generated.
- No chunks were embedded or modified.

Reason:
- User requested no further Neon embedding/chunk work while credit limit is maxed.
- Live `documents.icd11_scope`, `procedure_scope`, and `scope_verified` are still pending external handling.

Targeted tests:
```text
tests/test_routing.py — 20 passed (eight-level routing incl. semantic_scope,
priority order, ANCESTOR_MAX_DEPTH=2 stop, out_of_scope→none, route_method
stamping, dedup, top_k, document_ids grouping, db_utils search tests).

Combined targeted run (test_routing.py + test_exclusion_rerank.py +
test_score_breakdown.py + test_rerank_merge.py): 49 passed (2026-05-22, post-merge).
```

## P3 / D4 Out-of-Scope Detector

Status: locally implemented. Not tested in this pass by user request.

Files modified:
- `agent/clinical_stages.py`
- `tasks/Next-Step/DDx_Routing_Robustness_And_Exclusion_Rerank.md`

Implemented:
- Added `OutOfScopeInfo` structured payload with:
  - `route_method = "out_of_scope"`
  - `icd_candidates_considered`
  - `max_inclusion_score`
  - clinician-facing `message`
- Added `OUT_OF_SCOPE_INCL_THRESHOLD = 0.3` (matches the spec Constants summary; an earlier draft of this report said 0.55 — that was stale).
- Stage 3 emits an `out_of_scope` sub-step when routing returns `none` and all considered ICD candidates have inclusion score below threshold.
- Stage 5 now short-circuits to a deterministic low-confidence TreatmentPlan when no CPG/evidence exists and the out-of-scope detector fires.
- This avoids LLM synthesis from empty/unrelated CPG evidence.

Not done yet:
- D4 unit tests were not added/run in this pass.
- Smoke 5 was not run.
- No Neon writes, embeddings, chunks, or migrations were run.

---

## Appendix — Major / Minor CPG allocation (T1–T3, P1–P5 landed 2026-05-30)

Companion task: [DDx_Top5_And_Major_Minor_Suggestion.md](DDx_Top5_And_Major_Minor_Suggestion.md).

### What landed

Backend (`agent/clinical_stages.py`, `agent/clinical_workflow.py`, `agent/api.py`, `agent/models.py`, `agent/prompts/stage5_synthesis.txt`):

- **Allocation table** materialised as `_allocate_major_minor(n_minor)`:
  `(3,[])`, `(3,[2])`, `(3,[1,1])`, `(2,[1,1,1])`, `(1,[1,1,1,1])`. Unit-tested.
- **Headless auto-select** as `_auto_select_codes(ddx) -> (selected, major)` —
  rank-1 alone when `prob_rank1 − prob_rank2 ≥ STAGE3_HEADLESS_GAP` (default 0.15,
  env-configurable), otherwise rank-1 Major + rank-2 Minor. Unit-tested.
- **`stage_3_route(selected_codes=…, major_code=…)`** — new signature with full
  backward compatibility for `top_k_codes` / `top_k_cpgs`. Major-first allotment
  fill, leftover-slot cascade (cap 3 per code), and per-code-rank quality floor
  (rank-1 always returned; rank ≥ 2 require `score ≥ SEMANTIC_SCOPE_THRESHOLD`).
- **`stage3_quality_drop` SSE event** — emits `{tier, code, expected_slots,
  actual_slots}` whenever a Major or Minor under-fills, so the UI can flag
  "under-evidenced primary diagnosis".
- **Stage 5 framing** — `run_resynthesize_streaming` reorders `selected_ddx` so
  the Major code is index 0 → Stage 5's `icd_primary` automatically maps to the
  primary diagnosis. Prompt header clarifier added so the LLM treats
  `icd_primary` as the Major and `icd_alternates` as Minor co-considerations.
- **Wire-level types** — `DDxCandidate`, `DDxSuggestion`, `DDxSelection` added
  to `agent/models.py`. `ResynthesizeRequest` carries optional `major_code`;
  `SelectedDiagnosis` carries optional `tier`. Validators enforce
  `major_code ∈ selected_codes` and `len(selected_codes) ≤ 5`.

Doctor UI (`Doctor UI/src/...`):

- New `shared/TierSegmentedControl.jsx` — three-state pill (`Off / Minor /
  Major`), Major-exclusivity enforced silently in the parent.
- New `sections/DDxSelectionPanel.jsx` — top-5 cards with confidence bar,
  hint badges (system-suggested Major / co-primary), Restore-suggestions link,
  Confirm disabled until exactly one Major is set. Does NOT display the
  allocation math (3 / 3+2 / 3+1+1 / …) — that's backend implementation
  detail.
- `context/AppContext.jsx` — captures `ddx_suggestion` and
  `stage3_quality_drop` events; `confirmDiagnosis` accepts
  `{selectedCodes, majorCode}` overrides and forwards both downstream.
- `lib/clinicalApi.js` — `runDDxStream` surfaces `ddx_suggestion`;
  `resynthesizePlanStream` accepts `majorCode` + `onQualityDrop` and sends the
  `major_code` field in the request body.
- `sections/DiagnosisSection.jsx` — renders `DDxSelectionPanel` above the
  legacy multi-select card; routes Confirm through the new selection path.

### Tests

`tests/test_clinical_stages.py` gained 9 new cases covering the allocation
table edges, headless auto-select branches, the 3+2 split, single-code cap,
quality floor blocking weak secondary CPGs, leftover-slot cascade, the
`stage3_quality_drop` SSE event payload, and the `major_code ∈ selected_codes`
validator. All pass alongside the 70+ existing tests (one unrelated
pre-existing failure in `test_rerank_uses_configured_model` re Stage 2
temperature config, untouched by this work).

### Not in this delivery

- T4 ("Three-channel routing" / "Show more" / DDx cap > 5) remains suggestion-only.
- P6 eval re-runs against case08/case09/case10 with the new pipeline still
  need to be executed end-to-end; the chunk-budget headroom logged on
  2026-05-29 (46% / 44%) is the existing rationale for shipping at quota 5.
- `STAGE3_TAIL_SLOT_THRESHOLD` constant not split out from
  `SEMANTIC_SCOPE_THRESHOLD` — reused 0.32 as the per-code-rank floor; revisit
  if eval data shows the threshold needs to diverge.
