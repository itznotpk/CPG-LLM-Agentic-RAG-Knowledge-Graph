# DDx Routing Robustness + Exclusion-Aware Re-ranking

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](../IMPLEMENTATION.md) — read §1, §4 Step E, §7 before starting.

The ICD-11 ingestion (STEP_05, [tasks/Done/STEP_05_icd11_ingestion.md](../Done/STEP_05_icd11_ingestion.md)) loaded 3,914 codes across chapters 02/05/08/11/16/17/18/21 with `title`, `description`, `inclusions`, `exclusions`, `parent_code`, `chapter`, `embedding (1536)`, `inclusion_embeddings (JSONB)`. Inclusion embeddings are backfilled and live in DDx ranking.

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

documents:      28 CPGs ingested (of 30 planned), 384 doc sections
                2 CPGs still pending ingestion
chunks:         2,246 chunks total (verified 2026-05-21)
                documents.icd11_scope / procedure_scope / scope_rationale — columns exist but unpopulated
                scope_verified = TRUE: 0 rows (data blocker for D1 routing)
```

Phase A Step 2 ([Phase_A_Step2_ParentChild_Ingest.md](Phase_A_Step2_ParentChild_Ingest.md)) restructures the `chunks` table (h1/h2/h3 chain). **It does not touch `icd11_codes` or `documents.icd11_scope`** — the work in this doc is orthogonal and can be implemented and tested independently. Coordination note: smoke-test the routing changes (D1, D4) against the post-Phase-A chunks table once A-13 lands; the ICD-side changes (D3) are completely independent of Phase A.

This task is **seven deliverables (D1–D6, D2 revived)** forming **two tracks that converge**: a routing track (D1 → D2 → D4) and a scoring/display track (D3 → D5 → D6). The two tracks are independent of each other until the final pipeline assembly. Follow the phased execution sequence below — do not work top-to-bottom through the D-sections.

## Objectives

- **D1** — ICD-11 hierarchy fallback in Stage 3 routing using existing `parent_code`. No WHO API calls. Six structural levels: exact → sibling → ancestor_d1 → ancestor_d1_sibling → ancestor_d1_sibling_child → ancestor_d2.
- **D2** — Procedure-scope + semantic CPG fallback: two new steps inserted between `ancestor_d2` and `out_of_scope`. Step 7: procedure_scope tag overlap (catches procedure-only CPGs with no icd11_scope). Step 8: cosine similarity between ICD embedding and CPG scope_embedding (catches cross-chapter conditions D1 misses). Both only fire after all six structural levels miss.
- **D3** — Exclusion-aware DDx re-ranking: schema migration + backfill + scorer change.
- **D4** — Out-of-scope detector: structured "no CPG matches" response when D1 + D2 both miss and ICD confidence is low.
- **D5** — Clinician-facing score transparency: structured `ScoreBreakdown` per top-5 candidate + honest rendering/badges.
- **D6** — Math ↔ LLM rerank merge: feed math signals into the rerank prompt and surface material disagreements.

## Execution sequence (follow this order — not the D-section order)

Two tracks. **Track A (routing)** and **Track B (scoring/display)** are independent and may be done in either order or in parallel by two passes; they only meet at P6. Each phase has a hard exit gate — do not start the next phase in a track until its gate passes.

### P0 — Preconditions + Baseline Snapshots

- Track: —
- Deliverable(s): Preconditions + baseline snapshots
- Why here: Capture invariants *before* any change so #11/#12 are provable
- Exit gate: §Preconditions queries match expected; `icd11_codes` embedding checksum + `documents` scope snapshot saved to the report draft

Progress:
- [x] Run P0 ICD-11 baseline checks.
- [x] Capture ICD-11 embedding checksum.
- [x] Capture `documents` scope snapshot.
- [x] Record P0 findings in `tasks/ddx_routing_robustness_report.md`.
- [x] Resolve blocked document-scope precondition: all 30 CPGs scope-ingested via `ingestion/verify_cpg_scope.py` — 412 `documents` rows now carry `icd11_scope` / `procedure_scope` / `scope_rationale` with `scope_verified=TRUE` (2026-05-23).

### P1 — D3 Exclusion-Aware DDx Re-ranking

- Track: B
- Deliverable(s): D3 migration 008 + `backfill_exclusion_embeddings` + scorer change
- Why here: Pure data prep + isolated scorer math; zero pipeline risk; fully dry-runnable; unblocks D5
- Exit gate: Migration applied; 402 rows backfilled; idempotent re-run = 0 writes; D3 unit tests green; Smoke 4 green

Progress:
- [x] Add migration `sql/migrations/008_icd11_exclusion_embeddings.sql`.
- [x] Apply `icd11_codes.exclusion_embeddings` migration to Neon.
- [x] Add idempotent `ddx/backfill_exclusion_embeddings.py`.
- [x] Support `--dry-run`, `--force`, `--limit`, and `--chapters`.
- [x] Backfill all exclusion phrase embeddings in Neon.
- [x] Confirm idempotent rerun: 0 rows updated, 0 embedding calls.
- [x] Replace hard exclusion filtering with exclusion penalty scoring.
- [x] Surface matched WHO exclusion phrase and penalty fields in DDx output.
- [x] Extend `DDxResult` to carry score/exclusion fields through Stage 2.
- [x] Add focused exclusion rerank tests.
- [x] Run targeted Stage 2 regression tests.

### P2 — D1 Routing Core

- Track: A
- Deliverable(s): D1 six-level structural fallback (exact → sibling → ancestor_d1 → ancestor_d1_sibling → ancestor_d1_sibling_child → ancestor_d2)
- Why here: Routing core; D2 and D4 cannot be built or tested without D1 existing
- Exit gate: D1 unit tests green; Smoke 1, 2, 3, 9 green on staging

Progress:
- [x] Add D1 exact → sibling → ancestor_d1 → ancestor_d1_sibling → ancestor_d1_sibling_child → ancestor_d2 routing fallback.
- [x] Add route method stamping: `exact`, `sibling`, `ancestor_d1`, `ancestor_d1_sibling`, `ancestor_d1_sibling_child`, `ancestor_d2`, `none`.
- [x] Add SQL/helper support for ICD ancestor, sibling, ancestor-sibling, and ancestor-sibling-child lookups.
- [x] Add D1 unit tests.
- [x] Run Smoke 1, 2, 3, and 9 — validated 2026-05-23 against live Neon (staging-equivalent). Smoke 1 exact (BC81.3→AF) ✓; Smoke 2 ancestor_d1 (5A00.0Y→Thyroid) ✓; Smoke 9 sibling (5A61.1→Growth-Hormone) ✓; Smoke 3 out_of_scope (migraine/UTI/epilepsy) ✓ **after fixing 2 real D1 bugs** (see Smoke-validation findings below). Formal hosted-staging run still recommended pre-prod.

### P2b — D2 Semantic Scope Fallback

- Track: A
- Deliverable(s): D2 `scope_rationale` embedding + migration 009 + semantic match step in `find_cpgs_for_code()`
- Why here: Sits between D1 and D4 in the routing chain — D1 must be complete before D2 can be inserted
- Exit gate: Migration 009 applied; 30 CPG scope embeddings backfilled; D2 unit tests green; Smoke 10 green on staging

Progress:
- [x] Write `cpg_scope_rationale` text (100–200 words) for all 30 CPGs — generated via Codex agent and stored in `tasks/cpg_scope_review.md`. Field renamed from single-sentence `icd11_rationale`; new `cpg_scope_rationale` field is the DB-bound text.
- [x] Migration `sql/migrations/009_documents_scope_embedding.sql` (`scope_embedding VECTOR(1536)` column + index). Created idempotently by `backfill_scope_embeddings.py` Step 1. *(column now present on Neon; all 412 rows embedded)*
- [x] Update `ddx/backfill_scope_embeddings.py` — `_build_scope_text(row)` embeds `scope_rationale` (= cpg_scope_rationale) + procedure_scope tags ONLY; ICD-title dump removed (diluted broad CPGs). Embeds each unique scope text once and fans the vector to all of a CPG's rows (~30 calls, not ~389). Helpers `_collect_icd_codes` / `_fetch_icd_title_map` removed.
- [x] Backfill all CPG scope embeddings — 30 CPGs / 412 rows embedded via `ddx/backfill_scope_embeddings.py` (one unique vector per CPG via dedup), 2026-05-23.
- [x] Add `semantic_scope` step in `find_cpgs_for_code()` — `_semantic_scope_match()` uses pgvector `<=>` operator; DISTINCT ON cpg_name for one representative row per CPG; threshold guard at `SEMANTIC_SCOPE_THRESHOLD`.
- [x] Add `procedure_scope` step in `find_cpgs_for_code()` — `_procedure_scope_match()` uses Postgres `&&` array overlap; fires before semantic_scope when `procedure_tags` are supplied.
- [x] Add `"semantic_scope"` and `"procedure_scope"` to `RouteMethod` Literal (`agent/routing.py`) and `ScoreRouteMethod` Literal (`agent/clinical_stages.py`).
- [x] Add badges for `semantic_scope` (`~ Matched via semantic scope similarity`) and `procedure_scope` (`⚙ Matched via procedure context`) in `route_provenance_badge()`.
- [x] Add `SEMANTIC_SCOPE_THRESHOLD` constant to `agent/routing.py` — **calibrated to 0.40** on the full 30-CPG corpus (min in-scope positive 0.417 > max unrelated orphan 0.364; gap held at 14/27/30 CPGs). Was 0.65 — too high for Titan-v1 compressed cosine; D2 would never have fired. (2026-05-23)
- [x] Add `_extract_procedure_tags(clinical_text)` keyword-to-tag mapper in `agent/clinical_stages.py`; `stage_3_route()` now accepts `clinical_context: str | None` and forwards extracted tags to `route_icd_to_cpgs()`.
- [x] Update `route_icd_to_cpgs()` signature to accept and forward `procedure_tags: list[str] | None`.
- [x] Add D2 / procedure-scope unit tests (`tests/test_semantic_scope.py`). 11 tests green (2026-05-23).
- [x] Run Smoke 10 — validated 2026-05-23 against live Neon. D2 `semantic_scope` fires correctly for clinically-related non-scope codes: HA01.1→Erectile-Dysfunction (0.65), MC80.03→Hypertension (0.58), BA5Y→Stable-CAD (0.57), MF41→Erectile-Dysfunction (0.59). **Required fixing a runtime crash in `_semantic_scope_match`** (see findings below). Confirms the 0.40 floor works under real firing (related codes 0.57–0.65 clear it; orphans <0.40 don't). Formal hosted-staging run still recommended pre-prod.

### P3 — D4 Out-of-Scope Detector

- Track: A
- Deliverable(s): D4 out-of-scope detector
- Why here: Observes D1 + D2 output — only buildable after P2 and P2b
- Exit gate: D4 unit tests green; Smoke 5 green on staging

Progress:
- [x] Add structured `out_of_scope` response when D1 misses (all six structural levels) and ICD inclusion confidence is low.
- [x] Update D4 trigger condition: fires only after D1 **and** D2 (`semantic_scope`) both return no match. Satisfied by construction (2026-05-23): `route_icd_to_cpgs` → `find_cpgs_for_code` runs the full 9-step chain (…→ procedure_scope → semantic_scope → out_of_scope), so it returns `[]` only after D1 *and* D2 miss; `stage_3_route`'s `if not all_refs` gate therefore fires D4 only post-D2.
- [x] Ensure downstream synthesis renders "no matching CPG" instead of using unrelated documents.
- [x] Add D4 unit tests — `tests/test_d4_out_of_scope.py` (8 tests: inclusion-gate boundary, empty-ddx, and stage-3 trigger gated on D1+D2 + inclusion confidence). Green 2026-05-23.
- [x] Run Smoke 5 — validated 2026-05-23: migraine (8A80) → out_of_scope []; codes absent from `icd11_codes` → D2 returns [] → out_of_scope. D4 fires only after D1+D2 both miss. Formal hosted-staging run still recommended pre-prod.

### P4 — D5 Score Transparency

- Track: B
- Deliverable(s): D5a model + D5b render + D5c explainer
- Why here: Consumes D3's `ScoreBreakdown`; needs P1 done
- Exit gate: D5 unit tests green; Smoke 7 green on staging

Progress:
- [x] Add structured `ScoreBreakdown` model for top-5 DDx candidates.
- [x] Render base, inclusion, exclusion, and final score honestly.
- [x] Add route provenance badges for all seven route_method values.
- [x] Add D5 tests.
- [x] Run D5 unit tests locally: `tests/test_score_breakdown.py`.
- [x] Run Smoke 7 — validated 2026-05-23: `render_ddx_top5` shows base/inclusion/exclusion lines + provenance badge; exclusion candidate (5A10, WHO-excluded) renders the `⚠ WHO excludes "…"` caution line and stays in the list; `final_score = base + inclusion − exclusion` honoured. Formal hosted-staging run still recommended pre-prod.

### P5 — D6 Math + LLM Rerank Merge

- Track: B
- Deliverable(s): D6a prompt-feed + D6b model ext + D6c render + D6d telemetry + force-rerank harness
- Why here: Needs D5's candidate model and D3's exclusion signal
- Exit gate: D6 unit tests green; Smoke 6, 8 green on staging

Progress:
- [x] Feed math signals into the LLM rerank prompt (symptom_match, inclusion_match, WHO exclusion line per candidate).
- [x] Extend model/output for math-rank vs LLM-rank disagreements (`math_rank`, `llm_rank`, `rank_delta`, `override_reason` on `DDxResult`).
- [x] Surface material LLM movement with reason (`↕` / `⚠ ↕` disagreement line when `|rank_delta| >= RERANK_DISAGREEMENT_DELTA`).
- [x] Enforce override reason when promoting exclusion-penalized candidates (hard rule: injects placeholder if `override_reason` empty and exclusion candidate promoted ≥ threshold).
- [x] Add deterministic force-rerank test harness for Smoke 8 — env-injectable `FORCE_RERANK_ORDER` (JSON order + per-candidate `override_reason`) gated by `ALLOW_FORCE_RERANK=1` and **inert when `APP_ENV=production`**. Feeds a fixed order through the normal parse/assembly so llm_rank, rank_delta, the override hard-rule, and D6d telemetry run unchanged with the LLM bypassed. `_forced_rerank_spec` / `_force_rerank_enabled` in `agent/clinical_stages.py`; tests `tests/test_force_rerank.py` (7, incl. `test_force_rerank_order_inert_in_prod_config` and LLM-bypass integration). 2026-05-23.
- [x] Add D6 telemetry counters (`D6 telemetry: model=... disagreements=... exclusion_overrides=...`).
- [x] Add D6 tests (`tests/test_rerank_merge.py` — 10 tests, all green).
- [x] Run Smoke 6 and 8 — validated 2026-05-23. Smoke 6: exclusion backfill idempotent (703 candidates, 0 pending, 0 calls, 0 writes). Smoke 8 via the `FORCE_RERANK_ORDER` harness: Case 1 plain disagreement (math#4→#1, ↕ line, telemetry disagreements=1/overrides=0) ✓; Case 2a exclusion override WITH reason (⚠↕ + reason, overrides=1) ✓; Case 2b NEGATIVE empty reason → hard rule injects `[override_reason required…]` placeholder ✓. Formal hosted-staging run still recommended pre-prod.

### P6 — Pipeline Assembly + Full Pre-Deploy Gate

- Track: A+B
- Deliverable(s): Pipeline assembly + full pre-deploy gate
- Why here: Both tracks converge: routing provenance flows into the D5/D6 display
- Exit gate: **Full suite Smoke 1-9 green on staging**; all 11 done-criteria checked; then promote to prod

Progress:
- [ ] Full Smoke 1-9 suite green on staging.
- [ ] Verify all 11 done criteria.
- [x] Confirm existing `documents.icd11_scope` snapshot — **new post-ingestion baseline-2 captured 2026-05-23** (412 verified rows; 387 with icd11_scope, 25 procedure-only) via `_dump_snapshot.py` → `ddx_routing_p0_documents_scope_snapshot.json`. Re-run `_dump_snapshot.py` and diff after any future routing/display change to prove no mutation (done-criterion #11).
- [x] Confirm `icd11_codes.embedding` checksum unchanged — verified 2026-05-23: live MD5 `d8a2db83e95d7655aa3b73cdf72b2631` == canonical (done-criterion #12). Note: live `icd11_codes` is now **5672 rows** (not the 3914 in §Preconditions — that prose is stale; the canonical MD5 was recomputed when later codes/chapters were added).
- [ ] Produce final report-back package.
- [x] Decide whether to pull optional D1.5 `.Z` unspecified-code fallback into scope. **DECIDED 2026-05-23: NO separate step — the functional `.Z` (P1 category-unspecified) fallback is already live via the D1 `sibling` step.** `fetch_icd_siblings` uses the same `parent_code` join the D1.5 spec specifies (returns all same-parent codes incl. `.Z`/`.Y`), correctly excludes P2 (`X.nZ` child) and P3 (`XnZ` block) by construction, and runs at step 2 — so `.Z` already outranks the ancestor walk. The only thing NOT pulled in is the cosmetic distinct `route_method="unspecified_z"` + badge + dedicated tests; deferred as low-value (the `sibling` badge "≈ Matched via related code" already signals the correct caution tier). Revisit only if clinicians ask to distinguish "unspecified subtype" matches from specific-sibling matches.

Recommended single-pass order if done sequentially: **P0 → P1 → P2 → P2b → P3 → P4 → P5 → P6**. P1 and P2 have no dependency on each other — if parallelizing, run them as two concurrent passes. P2b (D2 semantic fallback) requires P2 done first; P3 (D4) requires both P2 and P2b done. Note: P2b has a content prerequisite (writing `scope_rationale` for 30 CPGs) that must be completed before any code work in P2b begins.

## Post-spec enhancements (beyond D1–D6)

Shipped during/after the scope-ingestion milestone (2026-05-23). These are **not part of the original D1–D6 scope** but harden the same DDx→routing→display path. Recorded here so they aren't lost; each has tests and is independent of the staging-smoke gate.

- [x] **E1 — Full scope ingestion + D2 calibration.** All 30 CPGs scope-ingested (412 rows) and `scope_embedding` backfilled; `SEMANTIC_SCOPE_THRESHOLD` calibrated 0.65→**0.40** against the full corpus (min positive 0.417 > max orphan 0.364). Ingestion path unified in `ingestion/verify_cpg_scope.py`; review file is `tasks/cpg_scope_review.md`.
- [x] **E2 — Multi-query DDx retrieval (symptom→disease gap fix).** `stage_2_ddx` now searches the extracted symptom phrase **plus LLM-named condition hypotheses** (`_generate_condition_hypotheses`), unioning candidates by code. Bridges the gap where a symptom narrative ("palpitations, irregular pulse") never retrieves the named disease (atrial fibrillation): AF went from absent → rank #1 on the canonical case. Disease-name→ICD-code lookup is reliable where symptom→disease isn't. Hypotheses shown as a trace sub-step.
- [x] **E3 — Symptom-extraction fallback flag.** `_extract_symptom_phrase` returns `(query, fell_back)`; a `⚠ fell back to raw notes` trace sub-step surfaces the previously-silent fail-open. Root cause fixed: mimo (reasoning model) returned empty content until `chat_template_kwargs.enable_thinking=False` was set for the extraction call.
- [x] **E4 — Sex-incompatibility filter.** A male is never routed to an obstetric/female-only CPG (and vice-versa). `sex_incompatible_reason()` + filtering in `stage_3_route` and `route_comorbidities`; exclusions shown as a red trace sub-step. Registry: pregnancy/cervical/CVD-Women → female; ED → male; `"pregnancy"` substring catch-all. Conservative (only fires for explicit M/F; breast cancer NOT filtered). Tests: `tests/test_sex_filter.py`.
- [x] **E5 — Stop-and-confirm gate (Doctor UI).** Stage 2 (DDx) now streams and **pauses** for clinician confirm/override before Stages 3–5 synthesize the plan — so the authoritative care plan is never generated against an unvalidated diagnosis. New `/clinical/plan/ddx/stream` endpoint + `run_ddx_only_streaming`; phase 2 reuses the existing resynthesize path. Tests: `tests/test_ddx_only.py`.
- [x] **E6 — Stage-2 trace transparency.** The AI Reasoning Trace now renders, per DDx candidate: before/after re-rank (`math# → AI#` + delta + `override_reason`), the numeric score breakdown (base / incl / excl / final), and the extraction-fallback / condition-hypotheses sub-steps. Frontend: `Doctor UI/src/components/sections/PipelineProgress.jsx`.

## Smoke-validation findings (2026-05-23) — 3 real bugs caught + fixed

Running the §6 smokes locally against live Neon (staging-equivalent) surfaced three genuine production bugs that the mocked unit tests could not — exactly what the post-deploy smokes exist for. All fixed; full suite (247) green after.

1. **Chapter-root sibling explosion (D1).** Codes whose `parent_code` is a *chapter root* (e.g. migraine `8A80`→`'08'`; chapter roots store `parent_code = ''`, not NULL) had the **entire chapter** as "siblings" (203 codes), so the `sibling` step matched any in-scope code in the chapter (migraine → Ischaemic-Stroke). Fixed `fetch_icd_siblings` with a chapter-root guard (`agent/db_utils.py`).
2. **Chapter-root ancestor-sibling explosion (D1).** Same root cause leaked through `ancestor_d1_sibling` / `ancestor_d1_sibling_child`: a chapter-rooted code's "parent peers" are *other chapters*, so migraine reached Nasopharyngeal-Carcinoma (ch.02). Fixed both `fetch_icd_ancestor_siblings` and `fetch_icd_ancestor_sibling_children` with the same guard.
3. **D2 `semantic_scope` runtime crash.** `_semantic_scope_match` fetched the ICD embedding into Python then re-serialised it with `",".join(map(str, …))` — but asyncpg returns a pgvector column as a *string*, so this produced `"[[,-,0,…]"` and the `::vector` cast threw `InvalidTextRepresentationError`. D2 would have crashed on its first real fire (never hit before because codes always matched a structural step first). Rewrote as a server-side join in `agent/routing.py` (no Python round-trip). D2 semantic now works — and clinically well (Smoke 10).

Net effect: D1 no longer mis-routes unrelated conditions via chapter-wide pseudo-siblings, and D2 semantic_scope is functional for the first time. Unit test `test_unknown_icd_code_uses_raw_string` → `test_unknown_icd_code_returns_empty` (asserted obsolete internals).

### Follow-up bugs found via a clinician CLI run (2026-05-23) — classic ACS case returned no MI/ACS code

A `clinical_cli.py` run on a textbook ACS presentation (62 M smoker, HTN, T2DM, "chest pain radiating to left arm") returned a DDx with **no acute-MI/ACS code at all** (pulmonary embolism #1, aortic dissection, generic chest pain). Two independent root causes:

4. **ivfflat ANN recall loss (CRITICAL, all DDx searches).** `icd11_embedding_idx` is ivfflat with `lists=10`; at the default `ivfflat.probes = 1` the approximate search scans only ~1/10 of vectors and **silently drops the true top matches**. For "acute myocardial infarction", BA41 (exact cosine **0.730**, the #1 match) was missed entirely — the search returned BA60 (0.643) instead, so no MI code reached the candidate pool and the reranker never saw it. Verified: probes=1 → BA41 absent; probes≥10 → BA41 #1. Fixed by `SET ivfflat.probes = 100` on the search connection in `ddx/search_ddx.py` and `_semantic_scope_match` in `agent/routing.py` (negligible cost on 5.7k / 30-row tables; near-exact recall). NOTE: `idx_documents_scope_embedding` (lists=16) had the same latent issue; same fix applied. `idx_chunks_embedding` is lists=1 (already full-scan, unaffected).
5. **mimo rerank empty-output (intermittent).** The Stage-2 rerank ran at `max_tokens=4000` with thinking enabled; for complex 10-candidate cases mimo (a reasoning model) exhausted the budget on hidden reasoning and returned **empty content** → "No JSON array found (len=0)" → fell back to math order (which ranks tight-embedding conditions like PE above ACS). Bumped rerank `max_tokens` 4000 → 8000 in `agent/clinical_stages.py`. After both fixes the same case returns **Unstable angina (BA40.0) #1** with aortic dissection / PE / hypertensive crisis as differentials — clinically correct, routes to NSTE-ACS exact.

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
- `documents` table has `icd11_scope` populated and `scope_verified=TRUE` for all 30 CPGs (28 currently ingested + 2 pending).
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
    conn,
    max_depth: int = 2,
    procedure_tags: list[str] | None = None,
) -> tuple[list[CPGDocRef], str]:
    """
    Returns (matched_documents, route_method).

    Phase 1 — ICD structural (code-to-code, no text/embedding):
      route_method ∈ {"exact", "sibling", "ancestor_d1",
                      "ancestor_d1_sibling", "ancestor_d1_sibling_child", "ancestor_d2"}

    1. exact                     — code in icd11_scope          e.g. BA41.0
    2. sibling                   — same parent_code incl. .Y/.Z  e.g. BA41.1, BA41.Z
    3. ancestor_d1               — one-decimal parent            e.g. BA41 from BA41.0
    4. ancestor_d1_sibling       — peers of that parent          e.g. BA40, BA42
    5. ancestor_d1_sibling_child — children of those peers       e.g. BA40.0, BA42.1
    6. ancestor_d2               — no-decimal block ancestor     e.g. 5B80 from 5B80.00

    Grandchild depth example for 5B80.00:
      exact(5B80.00) → sibling(5B80.01,5B80.0Z) → ancestor_d1(5B80.0)
      → ancestor_d1_sibling(5B80.1,5B80.Y,5B80.Z)
      → ancestor_d1_sibling_child(children of 5B80.1…)
      → ancestor_d2(5B80)

    Phase 2 — text fallbacks (only if all 6 ICD levels exhaust):
      route_method ∈ {"procedure_scope", "semantic_scope", "out_of_scope"}

    7. procedure_scope — tag overlap with caller procedure_tags
    8. semantic_scope  — cosine(icd_embedding, scope_embedding) ≥ threshold
    9. out_of_scope
    """
```

Rules:
- **Phase 1 is purely structural code-to-code: no text, no embeddings, no vector search.** All six levels checked before falling to Phase 2. Stopping at `ancestor_d2` is deliberate — block-group labels and chapter root codes are never stored in CPG `icd11_scope`, so walking higher adds only noise.
- **Phase 2 fires only after Phase 1 exhausts.** `procedure_scope` catches procedure-only CPGs (anaesthesia, pre-op) that have no `icd11_scope`. `semantic_scope` catches cross-chapter conditions D1 structurally misses.
- `ancestor_d1` = direct parent code (one dot-level up, e.g. `5B80.0` → `5B80.00`'s parent).
- `ancestor_d2` = no-decimal block ancestor, two levels up (e.g. `5B80` from `5B80.00`).
- `ancestor_d1_sibling` = peer category codes whose `parent_code` equals ancestor_d1's `parent_code`, excluding ancestor_d1 itself.
- `ancestor_d1_sibling_child` = all codes whose `parent_code` is any of the ancestor_d1_sibling codes.
- Trust degrades visibly per step. Stamp `route_method` onto the routing result so downstream telemetry / clinician audit can see *which* path matched. Never silently fall through.

#### D1 alternative proposal — breadth-first structural routing

> **Proposal status: SUPERSEDED — serial implementation chosen and shipped.** The serial approach (stop at first match, fixed priority order) was implemented and confirmed correct. The breadth-first alternative below is retained for reference only and should NOT be implemented.

Proposed flow:

```text
1. exact match
   - direct ICD code
   - range match

2. if no exact: same-level structural search
   - siblings of the predicted code, including .Y / .Z variants

3. if no same-level hit: ancestor_d1 breadth search
   - direct parent
   - sibling categories of the direct parent
   - children under those sibling categories

4. if no d1-level hit: ancestor_d2
   - grandparent block

5. if no structural hit: none / out_of_scope
```

Implementation intent:
- Query candidate route groups in parallel or as one batched SQL query after exact misses.
- Do **not** return whichever query finishes first.
- Assign every candidate a deterministic `route_priority`, `route_method`, `matched_scope`, and optional `route_distance`.
- Select results by clinical priority, not async completion order.

Recommended priority:

```text
exact
> sibling
> ancestor_d1
> ancestor_d1_sibling
> ancestor_d1_sibling_child
> ancestor_d2
> none
```

Why this may be better:
- Avoids a brittle "reverse back then deep dive" serial feel.
- Lets D1 evaluate the whole relevant ICD neighbourhood at the same structural level.
- Keeps the behaviour auditable because every selected CPG still has a structural route, not a semantic float.
- Gives D5 richer transparency fields: predicted code, matched scope, route method, and route distance.

Suggested D5 display addition if this is implemented:

```text
CPG: {matched CPG title} [{route badge}]
Matched scope: {matched_scope}
Route: {route_method}; distance: {route_distance}
```

Open decision before coding:
- Should `ancestor_d1` always outrank `ancestor_d1_sibling`, even when the sibling category has a more specific child match?
- Should `.Y` / `.Z` siblings receive the same priority as ordinary siblings, or a slightly lower same-level priority?
- Should multiple CPGs from the same route group be returned together, or should P6 cap one CPG per DDx code before deduping globally?

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

### D2 — Semantic CPG fallback via `scope_embedding`

**Status: revived.** Original attempt failed because `scope_rationale` was a one-sentence label — too thin to embed meaningfully. Now properly specced with correct data requirements and insertion point.

**Insertion point in the routing chain:**
```
exact → sibling → ancestor_d1 → ancestor_d1_sibling
      → ancestor_d1_sibling_child → ancestor_d2
      → semantic_scope   ← D2 fires here
      → out_of_scope
```

**Why here:** D1 covers every same-tree structural path. D2 catches the remaining case: a CPG that covers a clinical domain but was tagged to a different ICD subtree (e.g. cross-chapter conditions, rare syndromes). It is the last safety net before declaring no CPG exists.

**Files touched:** `sql/migrations/009_documents_scope_embedding.sql` (already written, not yet applied), new `ddx/backfill_scope_embeddings.py`, `agent/routing.py` (`find_cpgs_for_code()`), `agent/clinical_stages.py` (`ScoreRouteMethod`, `route_provenance_badge()`).

#### How it works

```
icd11_codes.embedding  ──cosine──►  documents.scope_embedding  →  matched CPG
```

1. After `ancestor_d2` returns 0 results, fetch all CPG rows from `documents` that have a non-null `scope_embedding`.
2. Cosine-compare the predicted ICD code's `icd11_codes.embedding` (already in DB — encodes title + description + inclusions) against each CPG's `scope_embedding`.
3. If best match score ≥ `SEMANTIC_SCOPE_THRESHOLD` → route to that CPG, `route_method = "semantic_scope"`.
4. If no CPG exceeds threshold → fall through to `out_of_scope`.

**No extra Bedrock call at query time** — `icd11_codes.embedding` already exists; `scope_embedding` is pre-computed once per CPG at backfill time. The search is 30 cosine comparisons — negligible latency.

#### Why raw ICD codes are excluded from the CPG embedding

`icd11_scope` stores codes like `BC81.3`, `BA00`. These are opaque alphanumeric tokens to the embedding model — it has no knowledge that `BC81.3` means atrial fibrillation. Embedding them adds noise, not signal.

Instead, look up the human-readable **titles** for each code in `icd11_scope` from the `icd11_codes` table and embed those. This creates clinical language overlap with the ICD embedding (which encodes title + description + inclusions), producing meaningful cosine similarity.

#### Combined CPG scope text (what gets embedded)

The backfill script builds one text block per CPG from two sources:

```
{scope_rationale}   (= the cpg_scope_rationale prose)
Procedures: {procedure_scope tags, comma-separated}
```

> **Decision (2026-05-22):** the per-code ICD-11 condition-title dump
> ("Conditions covered: …") was **removed**. For broad CPGs (100+ codes, e.g.
> CVD-Prevention-Women) it diluted the embedding into a blurry centroid. The
> `cpg_scope_rationale` prose already names the conditions in natural language,
> which is a stronger, compact signal. `_build_scope_text` now uses rationale +
> procedure tags only.

**Example — Atrial Fibrillation CPG:**
```
This guideline covers atrial fibrillation as a supraventricular tachyarrhythmia
spectrum including paroxysmal, persistent, long-standing persistent, permanent,
and unspecified atrial fibrillation. Relevant patient population includes adults
with confirmed or suspected AF... (full cpg_scope_rationale)
Procedures: referral_pathway; clinical_audit; warfarin_initiation; inr_monitoring;
dose_adjustment; perioperative_bridging
```

The query side (ICD embedding for `BC81.3`) still encodes the condition names and
synonyms (title + description + inclusions), so semantic overlap is preserved
without dumping titles into the document side. Keep the rationale ~150–350 words.

#### Data prerequisites (must be done before any code)

1. **Rewrite `scope_rationale`** for all 30 CPGs to 100–200 words covering:
   - Patient population this CPG is for
   - Conditions explicitly covered (use clinical names matching WHO language)
   - Conditions explicitly excluded from this CPG
   - Clinical context (primary care, specialist, inpatient)

   A one-sentence label will reproduce the original D2 failure — quality here directly determines whether D2 fires correctly.

2. **`scope_embedding` column** — `VECTOR(1536)` + ivfflat index on `documents`. The backfill creates this itself as Step 1 (`ADD COLUMN IF NOT EXISTS`), so applying `sql/migrations/009_documents_scope_embedding.sql` manually is **optional/redundant** — running the backfill is sufficient.

3. **Run backfill** — `ddx/backfill_scope_embeddings.py` builds the scope text and embeds it. ~30 embedding calls total (one per CPG, see dedup below), < 1 min.

#### Backfill script spec (`ddx/backfill_scope_embeddings.py`)

- Fetch `scope_rationale` and `procedure_scope` from `documents` (`icd11_scope` is selected but not embedded).
- Build text via `_build_scope_text(row)`: `scope_rationale` + `"Procedures: " + procedure_scope tags`. No ICD titles (see decision above). Falls back to `title` only if both are empty.
- **Embed each unique scope text once** and fan the vector out to all rows of that CPG (a CPG's sections share one `cpg_scope_rationale`). This cuts calls from ~1/row (~389) to ~1/CPG (~30).
- Skip rows where `scope_embedding IS NOT NULL` (idempotent — no overwrite unless `--force`).
- Support `--dry-run` (no DB writes, no embedding calls), `--force`, `--limit N`, `--all-documents`.
- Step 1 runs the `scope_embedding` column/index DDL idempotently.

#### Routing code — implemented in `agent/routing.py`

Two functions handle Phase 2 (both already shipped):

**`_procedure_scope_match(conn, procedure_tags)`** — fires first after ancestor_d2 fails:
```python
# Postgres array overlap — one shared tag is enough
WHERE scope_verified = TRUE
  AND procedure_scope && $1::text[]
```
Tags are extracted from the clinical context by `_extract_procedure_tags(clinical_text)` in `clinical_stages.py` using a keyword→tag map, then forwarded via `stage_3_route(clinical_context=...)` → `route_icd_to_cpgs(procedure_tags=...)`.

**`_semantic_scope_match(conn, code)`** — fires after procedure_scope fails:
```python
SEMANTIC_SCOPE_THRESHOLD = 0.65   # tune from Smoke 10 results

# Fetch ICD embedding, convert to vector string, then:
SELECT DISTINCT ON (metadata->>'cpg_name')
       id::text, title,
       metadata->>'cpg_name' AS cpg_name,
       1 - (scope_embedding <=> $1::vector) AS similarity
FROM documents
WHERE scope_embedding IS NOT NULL
  AND scope_verified = TRUE
ORDER BY metadata->>'cpg_name', scope_embedding <=> $1::vector
```
Uses pgvector `<=>` (cosine distance) — no Python-level cosine loop. Picks the single best-scoring CPG; returns it only if `similarity >= SEMANTIC_SCOPE_THRESHOLD`.

Terminal when all 9 steps fail:
```python
return [], "out_of_scope"
```

Note: `DISTINCT ON (cpg_name)` ensures one representative row per CPG — the scope embedding is the same across all sections of the same CPG.

#### Badge and display — implemented in `route_provenance_badge()` (`agent/clinical_stages.py`)

Both Phase 2 badges are shipped:
```python
if route_method == "procedure_scope":
    return "⚙ Matched via procedure context"
if route_method == "semantic_scope":
    return "~ Matched via semantic scope similarity"
```

**Hard rule:** Phase 2 badges must be visually distinct from all Phase 1 structural routes. Never render them as `✓` (exact) or `≈` (related). `⚙` signals procedure-triggered; `~` signals fuzzy semantic — clinician should verify in both cases.

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

Triggers when:
1. `find_cpgs_for_code()` returned `route_method == "out_of_scope"` (all 8 levels exhausted — 6 structural + procedure_scope + semantic_scope)
2. AND the top-K ICD candidates for the query all have `inclusion_score < OUT_OF_SCOPE_INCL_THRESHOLD` (default 0.3)

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
    route_method:        str     # exact | sibling | ancestor_d1 | ancestor_d1_sibling | ancestor_d1_sibling_child | ancestor_d2 | out_of_scope
```

Rules:
- `final_score` must equal `base_similarity + inclusion_match - exclusion_penalty` (assert this in code; a test enforces it).
- `inclusion_phrase` / `exclusion_phrase` are the actual WHO text that produced the contribution — null when that term didn't fire (sim below a display floor of `0.5`).
- `route_method` comes straight from D1/D4's routing result for the CPG this candidate maps to. Do not recompute.

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

These are the **only** `route_method` values the system produces — the implementer must handle all nine and map each to exactly the badge below:

| route_method | Badge text | Clinician meaning | Brief example |
|---|---|---|---|
| `exact` | `✓ Exact guideline match` | The CPG explicitly covers this ICD code. Highest trust. | `5B80.00` (Type 2 DM with diabetic nephropathy, stage 1) is explicitly listed in the Diabetes-Mellitus CPG's verified scope. |
| `sibling` | `≈ Matched via related code` | Matched a same-level peer at the same decimal depth, including `.Y`/`.Z` unspecified variants. Use clinical judgement. | `5B80.00` not in scope; same-level sibling `5B80.01` (stage 2) or `5B80.0Z` (unspecified stage) is in the Diabetes-Mellitus CPG. |
| `ancestor_d1` | `≈ Matched via broader category` | Matched the direct one-decimal parent. Reasonable, but broader than exact. | `5B80.00` and all `.0x` siblings miss; parent `5B80.0` (T2DM with diabetic nephropathy) is in the Diabetes-Mellitus CPG. |
| `ancestor_d1_sibling` | `≈ Matched via related category` | Matched a peer of the one-decimal parent — same clinical block. | `5B80.0` not in scope; peer `5B80.1` (T2DM with diabetic retinopathy) is in the Diabetes-Mellitus CPG. |
| `ancestor_d1_sibling_child` | `≈ Matched via related subcode` | Matched a child of a peer one-decimal category. | `5B80.1` itself not in scope; child `5B80.10` (T2DM with mild retinopathy) is in the Diabetes-Mellitus CPG. |
| `ancestor_d2` | `≈ Matched via broader category` | Matched the no-decimal block ancestor (grandparent). | All `5B80.0x` and `5B80.1x` subcodes exhausted; no-decimal block `5B80` (Type 2 diabetes mellitus) is in the Diabetes-Mellitus CPG. |
| `procedure_scope` | `⚙ Matched via procedure context` | No ICD structural match; CPG selected because the clinical context mentions a procedure this guideline covers (e.g. anaesthesia, pre-op assessment). Verify clinical intent. | Patient booked for surgery — Pre-Anaesthetic-Assessment CPG matched via `pre_op_assessment` tag; no ICD scope defined for that CPG. |
| `semantic_scope` | `~ Matched via semantic scope similarity` | No structural ICD match found; CPG selected because its clinical scope description is semantically similar to the predicted condition. Use with caution — verify clinical relevance. | Rare growth hormone deficiency code outside all CPG ICD scopes; Growth-Hormone-Disorders CPG selected via cosine similarity to scope embedding. |
| `out_of_scope` | `✕ No guideline covers this` | No CPG matched at any structural, procedure, or semantic level. Do not present as guideline-backed. | `5B80.00` walk exhausted all 6 structural levels, no procedure tags matched, semantic similarity below threshold → `out_of_scope`. |

Hard requirements:
- The provenance badge is **never** hidden. An `out_of_scope` result or any non-exact route must never visually masquerade as an `exact` curated match.
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
an exact match is the strongest; a broader ancestor match is shown clearly
so you can weigh it accordingly.
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
  CPG provenance: {route_method}
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
ROUTE_TOP_K                  = 3      # max CPGs returned by route_icd_to_cpgs
SEMANTIC_SCOPE_THRESHOLD     = 0.65   # D2: min cosine(icd_emb, scope_emb) to trigger semantic_scope route
EXCLUSION_PENALTY_WEIGHT     = 0.3
OUT_OF_SCOPE_INCL_THRESHOLD  = 0.3
DDX_PHRASE_DISPLAY_FLOOR     = 0.5    # below this, inclusion/exclusion phrase shown as null
DDX_DISPLAY_FLOOR            = 0.30   # below this, render "low confidence" alongside the %
RERANK_DISAGREEMENT_DELTA    = 2      # |math_rank - llm_rank| >= this → reason required + surfaced
```

Eight tunable constants. Log enough to tune them empirically from real DDx logs. `DDX_PHRASE_DISPLAY_FLOOR`, `DDX_DISPLAY_FLOOR`, `RERANK_DISAGREEMENT_DELTA` are display/telemetry-only and never change `final_score` or `llm_rank`.

## Tests

`tests/test_routing.py` (D1 + D4):

- `test_exact_match_returns_route_exact` — code in `icd11_scope` of one doc → returns that doc, method="exact".
- `test_ancestor_d1_match` — predicted code's parent is in `icd11_scope` → method="ancestor_d1".
- `test_ancestor_d2_match` — grandparent is in scope → method="ancestor_d2".
- `test_ancestor_walk_stops_at_d2` — only a depth-3+ code is in scope → method="none" (confirms ANCESTOR_MAX_DEPTH=2 cap).
- `test_sibling_match_when_no_ancestor` — sibling (same parent_code) is in scope → method="sibling".
- `test_sibling_only_after_ancestor` — both ancestor and sibling match → ancestor wins.
- `test_out_of_scope_when_all_signals_weak` — D1 + D2 both miss + max incl_score 0.40 → returns out_of_scope dict.
- `test_route_method_always_stamped` — every routing path returns a non-empty `route_method`.

`tests/test_semantic_scope.py` (D2) — mock the embedding client and DB; no real Bedrock calls:

- `test_semantic_scope_fires_after_d1_exhausted` — D1 returns none, scope_embedding cosine ≥ threshold → method="semantic_scope".
- `test_semantic_scope_skipped_when_d1_matches` — D1 returns a hit → semantic step never reached.
- `test_semantic_scope_below_threshold_falls_to_out_of_scope` — best cosine 0.60 < 0.65 threshold → method="none".
- `test_semantic_scope_picks_highest_cosine_cpg` — two CPGs with different scope embeddings → CPG with higher cosine selected.
- `test_backfill_skips_null_scope_rationale` — CPG with no scope_rationale → no embedding call, no DB write.
- `test_backfill_idempotent` — CPG with scope_embedding already set → no re-embed unless `--force`.
- `test_backfill_force_recomputes` — `--force` → embedding called even if already populated.
- `test_dry_run_no_db_writes` — `--dry-run` → DB write never called.
- `test_badge_semantic_scope` — `route_provenance_badge("semantic_scope")` returns the `~` badge string.

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
- `test_route_provenance_passed_through_not_recomputed` — ranker receives `route_method="sibling"` → breakdown carries it verbatim.
- `test_badge_text_per_route_method` — each of the 9 `route_method` values (6 structural + procedure_scope + semantic_scope + out_of_scope) maps to the exact badge string in the D5b table.
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

**Dry-run scope (read first).** `--dry-run` exists *only* on the D3 backfill script (`backfill_exclusion_embeddings`) — the data-prep step. The **live routing/rerank changes (D1, D4, D5, D6) have no dry-run mode by design**: they are pure read-path logic with no destructive side effects, so their safety net is the mocked unit tests (pre-merge) plus these E2E smokes (post-deploy). Do not assume a dry-run guard exists for the query pipeline.

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

### Smoke 3 — Out-of-chapter miss → out_of_scope (D4)

> **Note (2026-05-22):** D2 `semantic_scope` is REVIVED, so `out_of_scope` now
> fires only after D1 (6 structural levels) **and** procedure_scope **and** D2
> semantic_scope all miss. Pick a query whose condition is genuinely unrelated to
> every loaded CPG scope (so semantic similarity stays below
> `SEMANTIC_SCOPE_THRESHOLD = 0.65`). NOTE: nasal/epistaxis queries may now route
> to the loaded Nasopharyngeal-Carcinoma CPG (2B6B) — choose a different
> out-of-corpus query (e.g. an unrelated dermatology/ophthalmology presentation).
- Expected predicted ICD: a code in a chapter with no loaded CPG
- Expected `route_method`: `out_of_scope` (all structural levels return 0; procedure + semantic_scope also miss)
- Expected: structured out_of_scope response; no CPG cited

### Smoke 4 — Exclusion penalty (D3)
Find a code in `icd11_codes` whose `exclusions` contains a clinically meaningful phrase (run `SELECT code, title, exclusions FROM icd11_codes WHERE cardinality(exclusions) > 0 LIMIT 20`). Construct a DDx query that closely matches an exclusion phrase. Verify:
- The code is downranked vs a baseline run (capture both DDx outputs side-by-side).
- The matched exclusion phrase appears in the evidence trace.

### Smoke 5 — Out-of-scope (D4)
Query: *"Best management of acute appendicitis in the ED?"* (no surgical CPG loaded)
- Expected `route_method`: `out_of_scope`
- Expected: structured response with `max_inclusion_score` reported; no CPG cited; clinician-facing message instead of hallucinated synthesis

### Smoke 6 — Idempotency
Re-run the exclusion backfill with no args:
```bash
python -m ddx.backfill_exclusion_embeddings
```
- Expected: 0 embedding calls, 0 DB writes, exit cleanly. Confirms idempotency.
- Note: `backfill_scope_embeddings` IS required for D2 semantic_scope — run it (after scope ingestion) to populate `documents.scope_embedding`. It is idempotent.

### Smoke 7 — Score transparency (D5, the clinician-facing check)
Re-use the Smoke 4 query (the one that triggers an exclusion penalty). Capture the rendered top-5 DDx as a clinician would see it. Verify:
- The downranked diagnosis still appears in the top-5 (not removed).
- Its breakdown shows all three lines with real numbers; `final_score` visibly equals `base + inclusion − exclusion_penalty`.
- The `⚠ WHO excludes "<phrase>"` line names the actual WHO exclusion text.
- The provenance badge matches the actual `route_method` (e.g. `✓ Exact guideline match` for `exact`) — never misrepresented.

Paste the rendered top-5 block verbatim into the report. This is the deliverable a clinician actually sees — it must be legible and honest at a glance.

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
- `route_method` = `sibling` (not `exact`, not `ancestor_*`).
- The badge renders `≈ Matched via related code`.
- Ancestor lookup is shown (in logs/telemetry) to have run **and missed** before the sibling match — confirming the documented order (exact → ancestor → sibling).
If the SQL returns 0 rows, state that in the report (no sibling-route case exists in the current corpus) and mark this smoke N/A with the query output as evidence — do not skip silently.

### Smoke 10 — Semantic scope fallback (D2)

Pick a query whose predicted ICD code sits outside all 30 CPGs' `icd11_scope` at every structural level (D1 exhausts all six levels) but whose clinical meaning is semantically close to a CPG's `scope_rationale`.

Example: a rare endocrine condition not directly tagged to any CPG, but whose description is semantically close to the Thyroid Disorders or Growth Hormone CPG.

Run the query and verify:
- D1 exhausts all six structural levels and returns zero matches (confirm in logs).
- D2 fires: `route_method = "semantic_scope"`.
- The matched CPG is clinically plausible given the query.
- The badge renders `~ Matched via semantic scope similarity`.
- The similarity score logged is ≥ `SEMANTIC_SCOPE_THRESHOLD` (0.65).
- Negative check: lower the threshold artificially to 0.99 → D2 misses → falls through to `out_of_scope`.

If no suitable query can be constructed from the current corpus, document the attempt and the best cosine scores observed, and mark this smoke N/A with evidence.

## Follow-up (optional, NOT part of the 12 done-criteria) — D1.5: `.Z` unspecified-code fallback

> **Status: proposed extension to D1.** Captured here so it is not lost. It is *not* required to mark this task done, is *not* in the §Done criteria, and adds no new constants. Implement only if explicitly pulled into scope. Origin: collaborator review note on this doc.

**Concern in plain terms.** When Stage 3 predicts a leaf ICD-11 code that no CPG covers, D1 currently falls back by walking up to the structural `parent_code` (a category header, e.g. `BA01` "Ischaemic heart disease"). ICD-11 also defines, for *some* branches, a `…Z` sibling meaning **"this category, subtype unspecified"** (e.g. `BA01.Z` "Ischaemic heart disease, unspecified"). The `.Z` code is a *real, clinician-recognisable diagnosis*, whereas the bare parent is more of an organisational grouping. So when it exists, routing via the `.Z` sibling is more clinically honest than routing via the parent header.

**Why this can't be a blanket rule (the key constraint).** Unlike `parent_code` — which *every* code has, terminating at a chapter root (see §"Note for D1") — **not every branch has a `.Z` code.** Some do, some don't. So this fallback must *first check whether a `.Z` sibling exists for the predicted code's branch* and only use it when present; it can never be applied unconditionally the way the parent walk is.

**Proposed placement: right after exact, before the ancestor walk.** Prefer a same-branch "unspecified" diagnosis over going broader to a structural parent. New D1 chain:

```
exact → sibling (incl. Y/Z) → ancestor_d1 → ancestor_d1_sibling → ancestor_d1_sibling_child → ancestor_d2 → out_of_scope
```

`route_method` for Y/Z variants is now folded into `"sibling"` — the sibling step covers all same-parent codes including .Y and .Z. Badge: `≈ Matched via related code` — same trust tier as other structural fallbacks, never rendered as an `exact` curated match.

**Detecting the `.Z` sibling — VERIFIED against the live `icd11_codes` table (2026-05-18, 5,672 rows).** The naive "ends in `Z`" rule is **wrong** — 871 codes end in `Z` and they split into three structurally different patterns that must NOT be treated alike:

| Pattern | Example | Count | What it is | `parent_code` of the Z code | Usable here? |
|---|---|---|---|---|---|
| **P1 `X.Z`** | `2A20.Z`, `BC43.Z` | 478 | Category-unspecified — true *sibling* of the specific `X.0`/`X.1` leaves | the category `X` (e.g. `2A20`) | **YES — this is the target** |
| **P2 `X.nZ`** | `2A20.0Z`, `BD50.0Z` | 256 | Leaf-level unspecified — a *child* of one specific leaf | the specific leaf (e.g. `2A20.0`), **not** the category | No — it is a child, not a peer |
| **P3 `XnZ`** | `2A0Z`, `2A3Z` | 137 | Block-level unspecified | the **chapter root** (e.g. `02`) — far too broad | No — near chapter-level, the ancestor walk's cap exists to avoid exactly this |

**The correct discriminator is the `parent_code` join, NOT the code-string shape.** For a predicted code `$1`, its true category-unspecified sibling is the row whose `parent_code` equals `$1`'s `parent_code` and whose own code is the `…Z` of that same category. Verified working on 6 random leaves (`BC43.1`→`BC43.Z`, `JB09.0`→`JB09.Z`, `MG30.11`→`MG30.1Z`, etc. — each found its sibling purely via shared `parent_code`):

```sql
-- given predicted code $1, find its category's unspecified (.Z) sibling if one exists.
-- Correctness comes from the shared parent_code, NOT from the LIKE shape — the LIKE
-- is only a cheap pre-filter. This naturally excludes P2 (X.nZ): a P2 code's
-- parent_code is the specific leaf, never the predicted code's parent, so it can't match.
SELECT z.code
FROM icd11_codes p
JOIN icd11_codes z
  ON z.parent_code = p.parent_code   -- ← the actual correctness condition
 AND z.code <> p.code
 AND z.code LIKE '%Z'                -- ← cheap pre-filter only; parent_code does the real work
WHERE p.code = $1
LIMIT 1;
```

**Verified facts (no longer open assumptions):**
- The category-unspecified code (P1) genuinely shares the specific leaves' `parent_code` — the sibling model in this doc is structurally sound for P1. ✓
- P2 (`X.nZ`) is a *child* of a specific leaf, not a sibling — the `parent_code = p.parent_code` join correctly excludes it without any string special-casing. ✓
- Not every category has a P1 `.Z` (478 of them across 5,672 rows) — confirms this **cannot** be a blanket rule and the existence check is mandatory.

**Open questions still to resolve before implementing** (genuinely undecided, do not assume):
- Behaviour when the predicted code *is itself* a `…Z` code (any of P1/P2/P3): skip this step, fall straight to the ancestor walk. Add an explicit guard + test.
- Whether to *also* accept a P3 block-level `Z` as a last-ditch pre-`none` option, or treat P3 as out of bounds because it is effectively chapter-level (leaning: exclude P3 — it conflicts with the deliberate `ANCESTOR_MAX_DEPTH = 2` clinical-defensibility cap).
- A `.Z` sibling existing in `icd11_codes` does **not** guarantee any CPG covers it — this step still routes via `documents.icd11_scope @> ARRAY[<.Z code>]` and only counts as a hit if a CPG actually lists it; otherwise continue to the ancestor walk.

**If pulled into scope, also add:**
- Unit test `test_z_fallback_before_ancestor` — predicted code not in scope, its `.Z` sibling *is* in scope, parent also in scope → `route_method == "unspecified_z"` (proves `.Z` wins over ancestor).
- Unit test `test_z_fallback_skipped_when_no_z_sibling` — branch has no `.Z` code → behaves exactly as today (falls through to ancestor); proves it is not a blanket rule.
- A Smoke case (or an extension of Smoke 9) driving a query that predicts a code whose branch has a `.Z` in some CPG scope.
- The new `route_method` value in the §D5b badge table and the §D5a `ScoreBreakdown.route_method` allowed set.

**Scope-boundary note.** This is a *routing-layer* refinement (predicted code → CPG), consistent with D1's remit. It is **not** a prediction-layer change (it does not alter which code the model emits). Keeping it routing-only is what makes it a clean optional add-on to D1 rather than a cross-cutting change.

## Out of scope

- ❌ Hybrid retrieval (vector + code-prefix + lexical) for ICD lookup. Defer until DDx logs show actual misses.
- ❌ Re-embedding the existing `icd11_codes.embedding` column. The main embedding stays as-is.
- ❌ Adding new ICD-11 chapters. Stick with the 5+1 already loaded.
- ❌ Touching `chunks` table — that's Phase A's territory.
- ❌ Modifying `documents.icd11_scope` for existing CPGs. The 30 verified entries are immutable.
- ❌ Changing the existing inclusion-based ranker logic. D3 *adds* an exclusion penalty term — it does not rewrite inclusion scoring.
- ❌ Real WHO API calls, or real LLM rerank calls, in tests.
- ❌ Tuning the seven constants — ship with the defaults above and tune from real DDx logs in a follow-up.
- ❌ Replacing or retraining the LLM rerank model itself. D6 *feeds signals into* the existing rerank stage and surfaces its disagreements — it does not swap the model or change its core prompt beyond the documented additions.
- ❌ Frontend visual design / CSS for D5/D6. This doc fixes the *content, ordering, badge text, and honesty rules* of the clinician render; pixel-level styling is a follow-up for whoever owns the UI. The structured candidate model (D5a + D6b) is the contract — a text/CLI rendering that satisfies §D5b and §D6c is sufficient to mark this done.

## Done criteria

All eleven must hold:

1. Migration 008 applied cleanly. `\d icd11_codes` shows `exclusion_embeddings jsonb`. (Migration 009 / `documents.scope_embedding` — D2 revived; created idempotently by `backfill_scope_embeddings.py` Step 1, so applying 009 manually is optional.)
2. `python -m ddx.backfill_exclusion_embeddings` populates the 402 rows with non-empty exclusions. Verify: `SELECT COUNT(*) FROM icd11_codes WHERE exclusion_embeddings != '{}'::jsonb` returns 402.
3. Re-running the exclusion backfill makes 0 embedding calls and 0 DB writes (idempotent).
4. `pytest tests/test_routing.py tests/test_exclusion_rerank.py tests/test_score_breakdown.py tests/test_rerank_merge.py -v` all green. No real Bedrock, WHO, or LLM calls.
5. All nine smoke tests in §6 produce the expected result (Smoke 3 now tests out_of_scope on an ENT query; Smoke 9 may be a documented N/A if the corpus has no sibling-route case — the SQL output must be shown). The full suite passed on **staging before** prod promotion. Telemetry is captured. Smoke 7 and the two Smoke 8 deterministic blocks are pasted verbatim.
6. **(D5)** Every DDx candidate returned by the API carries the full breakdown (D5a + D6b fields) populated. `final_score == base_similarity + inclusion_match - exclusion_penalty` holds for every candidate (spot-check 10 from a live query).
7. **(D5)** The rendered top-5 for an exclusion-penalised candidate keeps it in the list with the `⚠ ... ranked lower` line, not removed. The provenance badge for each candidate matches its actual `route_method` — never shows `✓ Exact guideline match` for a non-exact route.
8. **(D6)** The clinician-facing order equals `llm_rank`. The LLM rerank prompt provably contains the math signals per candidate (capture one prompt from a live query).
9. **(D6)** Hard rule holds: no exclusion-penalised candidate is promoted ≥ `RERANK_DISAGREEMENT_DELTA` without a non-empty `override_reason`. Materially-moved candidates render the `↕` disagreement line; D6d telemetry counters are emitted. The Smoke 8 `--force-rerank-order` harness is proven inert under production config (unit test asserts it).
10. The 30 verified `icd11_scope` entries on existing documents are byte-for-byte unchanged. Verify: `SELECT title, icd11_scope, scope_verified FROM documents` matches the pre-deploy snapshot.
11. The existing `embedding` column on `icd11_codes` is byte-for-byte unchanged across the full table. Verify the checksum equals the canonical P0 baseline:
   ```sql
   SELECT MD5(string_agg(embedding::text, '|' ORDER BY code)) FROM icd11_codes;
   -- MUST return: d8a2db83e95d7655aa3b73cdf72b2631
   -- (canonical baseline, see §Preconditions P0; unless the corpus was
   --  re-ingested, in which case the P0 value was recomputed and replaced.)
   ```

## Report back

When you finish, return the following — concise, no marketing:

1. **Files created/modified** — exact paths.
2. **Migrations applied** — output of `\d icd11_codes` (relevant columns only) and `\d documents` showing `scope_embedding vector(1536)` (D2 revived; created by migration 009 or backfill Step 1).
3. **Backfill results** — `icd11_codes.exclusion_embeddings`: rows populated (expect 402), embedding calls made (expect ~748), runtime, total cost (Bedrock invocations × $0.0001 / 1k tokens estimate).
4. **Idempotency check** — output of re-running `backfill_exclusion_embeddings` with no args (expect "0 rows updated, 0 embedding calls").
5. **Test output** — last ~30 lines of `pytest tests/test_routing.py tests/test_exclusion_rerank.py tests/test_score_breakdown.py tests/test_rerank_merge.py -v`.
6. **Smoke test telemetry** — table with one row per routing smoke test (Smoke 1–6 and 9):
   | Smoke # | Query (truncated) | Predicted ICD | route_method | Matched CPG | Notes |
   |---------|-------------------|---------------|--------------|-------------|-------|
   For Smoke 9, include the discovery SQL output (or state N/A with that output as evidence).
7. **D5 rendered output** — Smoke 7's top-5 block pasted **verbatim** (the exclusion-penalty case), exactly as a clinician would see it. Plus one spot-check showing `final_score == base + inclusion − exclusion_penalty` arithmetic for one candidate.
8. **D6 rendered output** — Smoke 8's **two deterministic** top-5 blocks pasted **verbatim** (plain disagreement + exclusion override), the negative-check result (empty `override_reason` rejected), one captured LLM rerank prompt showing the math signals are present, and the D6d telemetry counts (disagreements, exclusion-overrides) for both cases.
9. **Pre/post invariants** — the two checksum/count queries in §Done criteria #10 and #11, before and after.
10. **Constants used** — confirm the seven constants in §Constants summary are at their default values (and listed in code at the top of the routing module).
11. **Any deviations** from this brief and why.
12. **Follow-ups noticed but not done** — likely candidates: tuning the seven constants from logged DDx data (esp. `EXCLUSION_PENALTY_WEIGHT` and `RERANK_DISAGREEMENT_DELTA` from D6d telemetry), adding hybrid retrieval if logs show ICD lookup misses, pixel-level UI styling for the D5/D6 badges, surfacing the breakdown + disagreement view in the production frontend.
