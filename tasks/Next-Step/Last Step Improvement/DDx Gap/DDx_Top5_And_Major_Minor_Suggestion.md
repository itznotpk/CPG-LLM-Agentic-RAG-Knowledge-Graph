# DDx Top-5 Suggestion + Clinician-Driven CPG Routing

## Status: 🟢 GREEN — adopt as written (T2.5 SSE event pending)

Validated 2026-05-29 against case 8 (single-comorbidity) and case 9 (NSTEMI + AF + T2DM + PCI + warfarin/amiodarone/fluconazole triple interaction):

| Gate | Result |
|---|---|
| Stage 5 prompt size on case 8 | 58k tok / 128k ctx (46%) — under ceiling |
| Stage 5 prompt size on case 9 (heavier) | 56k tok / 128k ctx (44%) — under ceiling |
| Top-5 covers distinct disease families | ✅ after Gap 6 (SPECIFICITY + DISTINCT-DISEASE prompt rules) + `_collapse_sibling_clusters` deterministic safety net |
| Multi-comorbidity surfaced in top-5 | ✅ case 9 top-5 includes NSTEMI + T2DM + AF concurrently |
| Specialist-med cross-check noise | ✅ action-gated + continuing-token suppression (Residual 1) |
| AF coverage gap (1st-line agent) | ✅ `current_medications` now counted (Residual 2) |
| Gate-audit per-CPG cap | ✅ `MAX_AUDIT_PER_CPG = 2` keeps tail short |

**Adoption decision:** the constants in the [Chunk budget table](#chunk-budget-measured-2026-05-29)
(STAGE3_MAX_CPGS=5, STAGE4_CHUNKS_PER_CPG_MAJOR=4, MINOR=4, BUDGET_CEILING=30)
are cleared to ship. T1/T2.1–T2.4/T3 backend gating is in place. **T2.5 quality-drop SSE event remains the one outstanding deliverable** before flipping the
status to fully green — see P3.

## Context

Stage 3 routing currently caps at 3 CPGs (`top_k_cpgs=3`) drawn from the top 2 DDx codes
(`top_k_codes=2`). After the 2026-05-25 routing revision (semantic scope re-scoring), the
match list is much tighter — broad-range ICD-11 codes no longer flood the slots — and the
system can now safely surface more codes and more CPGs without losing precision.

This task delivers a single coherent flow change:

1. **T1 — Surface the full top-5 DDx for clinician selection, with explicit Major /
   Minor tagging.** Stage 2 already ranks 5+ candidates; instead of silently routing
   only the top 2, expose all 5 with confidence scores. The clinician checks any
   subset (1 to 5) and designates **exactly one selected code as Major**; the rest
   default to Minor. The highest-confidence checked code is auto-flagged Major;
   clicking another code's star transfers the flag. Stage 3 routing reads the
   major/minor split to allocate CPG slots.
2. **T2 — Major / Minor CPG allocation.** The Major code drives the plan and gets
   the biggest slot; Minor codes carry comorbidity context. Allocation table:

   | Selection | Major slot | Minor slots | Total |
   |---|---|---|---|
   | 1 major only | 3 | — | 3 |
   | 1 major + 1 minor | 3 | 2 | 5 |
   | 1 major + 2 minor | 3 | 1, 1 | 5 |
   | 1 major + 3 minor | 2 | 1, 1, 1 | 5 |
   | 1 major + 4 minor (all 5) | 1 | 1, 1, 1, 1 | 5 |

   Formula: `major_allot = max(1, min(3, 5 − n_minor))`; minors split the remaining
   `5 − major_allot` slots evenly (always 1 each under this rule since n_minor ≤ 4).
   Major stays at 3 while 0–2 minors are picked, drops to 2 with 3 minors, and to 1
   only in the all-five "worst case." Minor codes are always guaranteed at least 1
   slot. The all-five case is expected to be rare.
3. **T3 — Headless default policy.** When no clinician is present (eval runs,
   `run_eval_case_08.py`), auto-select top-2 if the probability gap to rank-1 is
   < 0.15 (rank-1 = Major, rank-2 = Minor), else top-1 (rank-1 = Major, no minors).
   Preserves existing eval behaviour without manual clicks.

Current state at start of this task:

```text
agent/routing.py:48              ROUTE_TOP_K = 3
agent/clinical_stages.py:1944    top_k_codes: int = 2
agent/clinical_stages.py:1945    top_k_cpgs:  int = 3
agent/clinical_stages.py:1954    route_fetch_k = max(top_k_cpgs, 10)
agent/clinical_stages.py:2016    ranked_refs = sorted(...)[:top_k_cpgs]
```

The change is independent of Phase A and of any ingestion work. All edits sit in
Stage 2 → Stage 3 wiring + a new pre-Stage-3 selection step + Doctor UI surface.

## Objectives

- **T1.1** — Stage 2 rerank already returns ≥5 candidates; surface all 5 (with code,
  title, probability, score breakdown) as a structured DDx suggestion list. Drop the
  silent `[:top_k_codes]` slice in Stage 3.
- **T1.2** — Emit a new SSE event `ddx_suggestion` after Stage 2 carrying the top-5,
  awaiting an optional `ddx_selection` reply with shape
  `{selected_codes: [str], major_code: str}`. Exactly one of `selected_codes` must
  equal `major_code`; the rest are minors. If no reply within the timeout, headless
  auto-select applies (T3).
- **T1.3** — Doctor UI: render the suggestions as a vertical list of DDx cards.
  Each card shows rank, ICD-11 code, title, a confidence bar, and a single
  **segmented tier control** with three states: `Off` (neutral, default for all
  five), `Minor` (blue pill, "co-consideration"), `Major` (amber pill, "primary
  diagnosis"). One tap sets the state — no separate checkbox + star to coordinate.
  Major exclusivity is enforced silently: tapping `Major` on a new card auto-
  demotes the previous Major to `Minor`. **Default state: all five rows start as
  `Off`** — nothing is pre-selected. The clinician must actively review each
  suggestion and assign Major / Minor where appropriate. This forces clinical
  engagement with every DDx and removes the risk of an unreviewed auto-pick
  driving the plan. A "Restore suggestion" link is available but does **not**
  auto-fill — it simply highlights the top-1 (and top-2 when gap < 0.15) with a
  subtle hint badge ("system suggests this as primary") that the clinician can
  act on with one tap. Confirm button is disabled until exactly one Major is set.
  **The UI does not display the CPG allocation math** (e.g. "3 + 1 + 1") — the
  per-code allotment is a backend implementation detail. The clinician only sees
  the resulting CPGs in the next stage of the pipeline.
- **T2.1** — `stage_3_route` accepts
  `(selected_codes: list[str], major_code: str)` and computes the per-code allotment
  from the T2 table using `n_minor = len(selected_codes) - 1`.
- **T2.2** — **Allocation algorithm.** For each selected code, fetch its ranked CPG
  list (already scored by `_case_cpg_priority`). The Major code receives
  `major_allot` slots (filled from its top-ranked CPGs). Each Minor code receives
  its allotment in selection order. If any code has fewer matching CPGs than its
  allotment, the leftover slots cascade to the next under-filled code (Major first,
  then Minors in selection order), capped at 3 per code.
- **T2.3** — **Quality floor by per-code rank.** Within any selected code, the
  *first* CPG is always returned (the clinician picked that code; respect it). A
  *2nd or 3rd* CPG from the same code is admitted only if its `ref.score >=
  SEMANTIC_SCOPE_THRESHOLD` (0.32, reused from `routing.py`). Matters for the cases
  where Major has a 2- or 3-slot allotment (n_minor = 0–3).
- **T2.4** — **Stage 5 synthesis context.** Pass `major_code` alongside the CPG list
  into Stage 5 so the synthesis prompt can frame the plan around the primary
  diagnosis ("Primary: X; Co-considerations: Y, Z") rather than treating all
  selected codes as peers.
- **T3.1** — Headless default policy: applies **only when there is no UI
  consumer** (eval runs, batch scoring, CLI smoke tests). When the SSE consumer
  does not reply within `STAGE3_USER_TIMEOUT_MS` and the workflow is flagged as
  headless (`HEADLESS_MODE=1` or no `ddx_selection` listener registered),
  auto-select top-2 with rank-1 as Major and rank-2 as Minor if
  `prob_rank1 − prob_rank2 < 0.15`; else top-1 alone as Major. Centralise this
  in `_auto_select_codes(ddx) -> (selected, major)` so behaviour is testable.
  **The Doctor UI never falls back to this** — interactive sessions either show
  the all-Off panel and wait for clinician input, or surface a clear
  "no selection made" error rather than silently auto-routing.

## Execution sequence (follow this order)

Two tracks. **Track T1 (selection surface)** spans backend → SSE → UI. **Track T2
(adaptive routing)** is backend-only. T2 can land first (under a flag) so the routing
logic is provable in eval mode before the UI work begins.

### P0 — Preconditions + Baseline

- Track: —
- Deliverable: Capture current behaviour as a baseline trace
- Exit gate: Run case08 + case09 against current `main`; save SSE traces under
  `tasks/eval_runs/baseline_top3_<stamp>_trace.json`. Record:
  - number of CPGs returned per case
  - which CPGs were dropped at the `[:top_k_cpgs]` slice (one-line `logger.debug` patch
    — revert after baseline)
  - Stage 2 rerank top-5 order with probabilities and gaps

Progress:
- [ ] Baseline trace captured for case08
- [ ] Baseline trace captured for case09
- [ ] Dropped-CPG list recorded
- [ ] Stage 2 probability gaps logged

### P1 — T2.1 + T3.1: Major/Minor quota + headless auto-select (backend, eval mode)

- Track: T2
- Deliverable: `stage_3_route(selected_codes=..., major_code=...)` works end-to-end;
  headless callers use `_auto_select_codes(ddx) -> (selected, major)` when no
  selection is supplied
- Files: `agent/clinical_stages.py` (Stage 3 signature + auto-select helper +
  allocation helper `_allocate_major_minor(n_minor)` returning a tuple
  `(major_allot, minor_allots)` — e.g. `(3, [])`, `(3, [2])`, `(3, [1,1])`,
  `(2, [1,1,1])`, `(1, [1,1,1,1])`), `agent/clinical_workflow.py` (wire selection
  through), `agent/api.py` (request schema)
- Exit gate: `run_eval_case_08.py` runs unchanged and produces a trace where:
  - if Stage 2 gap < 0.15: 2 codes selected (rank-1 Major, rank-2 Minor), allocation
    `(3, [2])`, ≤5 CPGs returned
  - if Stage 2 gap ≥ 0.15: 1 code selected (rank-1 Major), allocation `(3, [])`,
    ≤3 CPGs returned

Progress:
- [x] `selected_codes` + `major_code` parameters added to `stage_3_route`
- [x] `_auto_select_codes(ddx)` implemented + unit-tested
- [x] `_allocate_major_minor(n_minor)` implemented + unit-tested for n_minor=0..4
- [ ] case08 trace matches expected branch (requires live pipeline run — deferred to eval pass)

### P2 — T2.2: Major-first allocation with cascade

- Track: T2
- Deliverable: Major code is filled first (up to `major_allot`), then Minors in
  selection order; leftover slots cascade Major → next-Minor with under-fill
- Files: `agent/clinical_stages.py` (replace the global `sorted(...)[:top_k_cpgs]`
  with the major-first allotment fill)
- Exit gate:
  - case where Major has only 2 matching CPGs in a `(3, [2])` split returns 2 from
    Major + 3 from Minor (cascade, cap 3) — verified by unit test
  - case with `(3, [1,1])` and full availability returns exactly 5
  - case with `(1, [1,1,1,1])` and full availability returns exactly 5

Progress:
- [x] Major-first allotment fill implemented
- [x] Cascade rule implemented (cap 3)
- [x] Unit test for cascade behaviour
- [ ] case08 returns CPGs respecting Major allotment (eval pass)

### P3 — T2.3 + T2.4 + T2.5: Quality floor + Stage 5 synthesis hand-off + under-fill telemetry

- Track: T2
- Deliverable:
  - A code's first CPG always returns; its 2nd or 3rd CPG only if
    `ref.score >= SEMANTIC_SCOPE_THRESHOLD`
  - `major_code` propagated to Stage 5 and surfaced in the synthesis prompt as
    "Primary diagnosis"
  - **NEW (T2.5)** — when the quality floor drops a Major or Minor CPG, emit a
    `stage3_quality_drop` SSE event and surface a per-tier "under-evidenced"
    badge in the Doctor UI plan view
- Files: `agent/clinical_stages.py` (guard inside the per-code fill loop, gated by
  per-code rank ≥ 2; Stage 5 prompt builder; T2.5 emit), `agent/prompts/stage5_synthesis.txt`
  (add Primary / Co-considerations framing),
  `Doctor UI/src/components/clinical/CarePlanSection.jsx` (T2.5 badge render)
- Exit gate:
  - synthetic case where Major has 1 strong + 2 weak CPGs and 0 minors returns 1
    (not 3) — unit test
  - synthetic case `(3, [2])` where Major has 1 strong + 2 weak returns 1+2 = 3
    (not 5) — unit test
  - case08 still fills 5 slots when all candidates clear the floor
  - case08 Stage 5 prompt mentions Major code by name as primary diagnosis
  - **T2.5**: synthetic Major-under-fill case emits a `stage3_quality_drop` event
    with `{tier: "major", code, expected_slots: 3, actual_slots: 1}` — visible in
    the trace JSON — unit test
  - **T2.5**: UI renders a "Primary diagnosis backed by 1 CPG only — consider
    alternatives" badge when the event fires — Storybook or manual walkthrough

Progress:
- [x] Per-code-rank guard implemented
- [x] Low-quality single-pillar test passes
- [x] Low-quality Major+Minor test passes (covered by `test_stage3_quality_floor_blocks_weak_secondary_cpgs`)
- [ ] case08 fill unchanged (all candidates above floor) — eval pass
- [x] Stage 5 prompt updated with Major framing
- [ ] `STAGE3_TAIL_SLOT_THRESHOLD` constant added if calibration diverges from 0.32 (reused 0.32 for now)
- [x] **T2.5** `stage3_quality_drop` SSE event emitted on under-fill
- [x] **T2.5** UI quality-drop hook plumbed via `onQualityDrop` callback + `ddxQualityDrops` state (badge copy review pending)

### T2.5 — Why this matters

Without surfacing under-fill, the system silently degrades from "Major backed by
3 CPGs" to "Major backed by 1 CPG" whenever the quality floor (T2.3) trims weak
candidates. The clinician sees no difference in the UI — they assume the routing
went as planned. For a Major diagnosis (the one driving the plan) this is a
quiet safety issue, not just a cosmetic one. The badge cost is trivial (one SSE
event field + one conditional render); the clinician value is high.

### P4 — T1.1 + T1.2: Surface top-5 + SSE handshake (with Major flag)

- Track: T1
- Deliverable: Stage 2 emits a `ddx_suggestion` event with all top-5; Stage 3 waits
  for an optional `ddx_selection` reply of shape
  `{selected_codes: [str], major_code: str}` before routing
- Files: `agent/models.py` (`DDxSuggestion`, `DDxSelection` with `major_code`
  validator: must be in `selected_codes`), `agent/api.py` (SSE schema + timeout
  config), `agent/clinical_workflow.py` (insert wait point between Stage 2 and
  Stage 3)
- Exit gate: headless mode (timeout = 0) preserves P1 behaviour exactly; with
  timeout > 0, a posted selection (codes + major) reroutes Stage 3; conformance
  test in `tests/test_clinical_stages.py` covers both paths and the
  `major_code ∈ selected_codes` validator

Progress:
- [x] `DDxSuggestion` + `DDxSelection` schemas in `agent/models.py` (plus `DDxCandidate`)
- [x] `major_code` validator enforced (`major_in_selected` + `len ≤ 5`)
- [x] SSE emit added between Stage 2 and Stage 3 (`ddx_suggestion` in `run_ddx_only_streaming`)
- [x] Selection plumbed into `stage_3_route(selected_codes=..., major_code=...)`
- [x] Headless regression test green (all 9 new unit tests + legacy 25 pass)
- [ ] Interactive path test green (E2E browser run — UX walkthrough pending)

### P5 — T1.3: Doctor UI selection panel (segmented tier control)

- Track: T1
- Deliverable: Card-list panel between DiagnosisSection and PipelineProgress
  with a single segmented `Off / Minor / Major` control per row and a live
  allocation summary
- Files: new `Doctor UI/src/components/sections/DDxSelectionPanel.jsx`, new
  `Doctor UI/src/components/shared/TierSegmentedControl.jsx` (reusable pill
  segmented input), `Doctor UI/src/lib/clinicalApi.js` (post selection),
  `Doctor UI/src/context/AppContext.jsx` (tier state per code)

Interaction spec:
- Each card: rank badge, ICD-11 code, title, confidence bar (0–1.0), segmented
  control [Off | Minor | Major]
- **All five cards start as `Off`** — no auto-selection. Clinician taps to
  assign Major / Minor where appropriate
- One tap on a segment sets that tier. Tapping the active segment toggles back
  to `Off`
- Setting `Major` on a card silently demotes the previous Major to `Minor`
  (never to `Off` — preserves the clinician's intent that the code matters)
- A subtle hint badge ("system suggests this as primary") sits next to the
  top-1 row (and "co-primary candidate" next to top-2 when gap < 0.15); tapping
  the badge applies that suggestion as a single shortcut. Manual taps override
- "Restore suggestion" link re-shows the hint badges if the clinician dismissed
  them; it never auto-fills tier states
- Confirm button: disabled until exactly one Major is set; tooltip explains
  why when disabled
- Keyboard: `1`–`5` cycle the corresponding row through tier states;
  `Enter` Confirms when valid
- **No CPG-allocation footer.** The UI deliberately does not show how many CPGs
  each code will yield — that is backend math. The clinician sees the matched
  CPGs only in the next pipeline stage

Exit gate: panel renders with all rows `Off`; clinician can complete a typical
case in 1–3 taps (one for Major, one each for any Minor); UX walkthrough with
synthetic cases for n_minor = 0, 2, 4 produces the expected `ddx_selection`
payload visible in the trace; CPG count returned by Stage 3 matches the
backend allocation table without being shown in the UI

Progress:
- [x] `TierSegmentedControl` component built and unit-styled
- [x] Panel renders top-5 with rank / code / title / confidence bar
- [x] All rows initialised to `Off`
- [x] Tier state managed in `AppContext` with Major-exclusivity invariant (panel-local + `confirmDiagnosis({selectedCodes, majorCode})` override)
- [x] Hint badge surfaces top-1 / top-2 suggestion (tap to apply)
- [x] Restore-suggestion re-shows dismissed hint badges
- [ ] Keyboard shortcuts wired (1–5, Enter) — deferred to a UX-polish pass
- [x] Confirm posts via `resynthesizePlanStream(..., majorCode)` (re-uses existing endpoint)
- [x] `clinician_override` trace event carries `major_code`; resynth request body carries `major_code` + per-diagnosis `tier`

### P6 — Wrap-up + telemetry

- Track: —
- Deliverable: Update `tasks/Next-Step/Last Step Improvement/DDx Gap/ddx_routing_robustness_report.md`
  with before/after CPG coverage, per-pillar split, and observed selection patterns
- Exit gate: at least 3 eval cases re-run end-to-end; report appendix signed off

Progress:
- [ ] Eval re-run for case08, case09, and one additional case
- [ ] Coverage diff appended to report
- [ ] Telemetry counters reviewed

## P7 — First live eval pass: case 11 + case 12 results (2026-05-31)

Both cases ran end-to-end through the new Major/Minor pipeline against the live
local API (`localhost:8058`). The traces are saved as
`tasks/eval_runs/case11_20260531_004134_summary.md` and
`tasks/eval_runs/case12_20260531_010528_summary.md`.

### Results table

| Case | Major (auto-pick) | DDx ranking | CPGs returned | Allocation under-fill | Safety / refusals | Verdict |
|---|---|---|---|---|---|---|
| **Case 11** Stable CAD + ED | `MF41` (symptom code) | ❌ symptom code beat the actual ED disease code | ✅ 5/5 (2 from DDx + 3 from comorbidity channel — PCI, Stable-CAD, NSTE-ACS, CVD Prevention, ED CPG) | Major MF41 → 1 (expected 3); Minor BA52.Z → 1 (expected 2). Cascade exhausted with nothing left to give | ✅ PDE5i flagged contraindicated; urology + cardiology referrals; alternative ED options offered | **Pass — plan correct despite DDx mis-rank; comorbidity channel rescued the CPG coverage** |
| **Case 12** Full Metabolic Syndrome | `5A11` (T2DM) | ✅ correct disease code at rank 1 | ⚠️ 4/5 — **Hypertension (5th Edition) CPG missed** despite HTN being a declared comorbidity | Major 5A11 → 1 (expected 3); Minor 5C80.2 → 1 (expected 2). Cascade exhausted | ✅ refused CVD-risk %; ✅ refused bariatric remission %; ✅ Asian bariatric threshold cited; ✅ priority-ordered plan | **Pass with one routing gap — HTN CPG missing** |

### What this tells us

- **Allocation math is correct in both cases.** The 1-major-only path hits the
  3-cap; the 1+1 path *targets* 5 (n_minor=1 → `(3, [2])`) but the headless
  Major and Minor codes happened to map to only 1 CPG each in the corpus, so
  the cascade exhausted at 2.
- **`stage3_quality_drop` SSE event fired as designed** in both cases, naming
  the under-fill explicitly. T2.5 is doing real work.
- **The hard problems live upstream of Stage 3.** Case 11's miss is a Stage 2
  ranking quality issue (symptom-code-over-disease-code). Case 12's miss is a
  comorbidity-routing reach issue (declared HTN didn't route to the HTN CPG).

### Follow-ups that land in this same task

Two mitigations agreed and tracked here (not deferred to T4):

1. **Chapter-21 demotion** — push Chapter 21 ("Symptoms, signs and clinical
   findings, not elsewhere classified") codes below disease codes in Stage 2
   rerank when a similarly-scored disease code exists. Prevents `MF41` from
   out-ranking the actual ED disease code.
2. **Under-fill fallback to unselected DDx ranks** — when ≥2 codes are
   selected and the Major/Minor allotment can't be filled by the existing
   cascade (because the selected codes are exhausted), walk down the unselected
   DDx ranks (3 → 4 → 5) and pull their best-scoring CPG to top up the budget.
   Subject to the same quality floor and CPG-name dedup. Aim: when ≥2 codes
   are picked, return 5 CPGs whenever the corpus supports it.

Progress (P7):

- [x] Case 11 dry-run validated
- [x] Case 11 live run executed and summary captured
- [x] Case 12 dry-run validated
- [x] Case 12 live run executed and summary captured
- [x] Both cases scored against expected behaviours
- [ ] Chapter-21 demotion implemented + tested  (see Follow-up 1 below)
- [ ] Under-fill fallback to unselected DDx ranks implemented + tested  (see Follow-up 2)
- [ ] Case 11 re-run after both fixes — expect `5C80` / `MF40` rank-1
- [ ] Case 12 re-run after both fixes — expect 5 CPGs incl. Hypertension

### Follow-up 1 — Chapter-21 demotion (Stage 2)

- **Where:** `agent/clinical_stages.py` after `_llm_rerank_ddx` returns.
  Optional prompt clarifier in `agent/prompts/stage2_ddx_rerank.txt`.
- **Rule:** if a Chapter 21 candidate (ICD-11 code starts with `M`) sits at
  rank R, and a non-Chapter-21 disease candidate at rank R+k (k ≥ 1) has
  `similarity >= chapter21.similarity − CHAPTER21_DEMOTION_TOLERANCE` (default
  0.05), swap them so the disease code outranks the symptom code. Apply
  pairwise, top-down, until no more swaps are needed.
- **Why not just the prompt:** prompt alone is unreliable across cases (the
  LLM already had a SPECIFICITY rule and still placed MF41 at rank 1). A
  deterministic post-rerank step is the safety net.
- **Exit gate:** synthetic case where Chapter 21 sym-code and a Chapter 1-15
  disease code score within 0.05 of each other returns the disease code at
  rank 1. Case 11 re-run lifts `5C80.0` or an ED disease code above `MF41`.

### Follow-up 2 — Under-fill messaging (no cross-code padding)

**Spec clarified after the first eval pass: quality > quantity.** The
allotment ceiling (3 for n_selected=1, 5 for n_selected≥2) is a *maximum*, not
a target. Under-fill must NOT be padded by pulling CPGs from unselected DDx
ranks or from codes unrelated to the clinician's selection. If the
clinician-picked codes cannot fill their allotment with related, quality
matches, the slot stays empty and the trace says so explicitly.

- **Where:** `agent/clinical_stages.py::stage_3_route` — sharpen the T2.5
  telemetry rather than adding a Pass 3 cross-code fallback.
- **Rule:**
    - **Pass 1 (allotment fill)** and **Pass 2 (same-code cascade)** stay as
      they are — Major-first, then Minors, capped at 3 per code, quality floor
      `SEMANTIC_SCOPE_THRESHOLD` on per-code rank ≥ 2.
    - **Pass 3 (cross-code padding) is explicitly NOT introduced.** No
      scraping from unselected DDx codes; no relaxing the quality floor to
      hit a numeric target.
    - **`stage3_quality_drop` events differentiate three states per code:**
      - `actual_slots == expected_slots` → not emitted (normal)
      - `0 < actual_slots < expected_slots` → emit existing message
        *"<tier> <code> backed by N CPG (expected M)"* with `badge:
        "under_evidenced"`
      - `actual_slots == 0` → emit a stronger message
        *"<tier> <code>: no CPG found in scope"* with `badge:
        "no_cpg_found"` so the clinician sees a clear out-of-scope signal,
        not just a small number
    - When **every** selected code has `actual_slots == 0`, emit the existing
      `out_of_scope` sub-step at the top level (mirrors current behaviour for
      the legacy single-code path).
- **Why this is the right call:**
    - Padding with unrelated CPGs would have hidden the real signal — case 12
      *should* surface "Hypertension CPG didn't route" loudly so the
      clinician knows the gap exists, rather than silently being topped up
      from a tangential ICD code.
    - Routing quality is the symptom; Stage 2 ranking + comorbidity-routing
      reach (Follow-up 1, plus T4 Option A) are the cures.
- **Exit gate:**
    - Case 11 re-run: with Major MF40 (after chapter-21 demotion lifts a
      disease code into rank 1) and a Minor, routing returns ≤ allotment, and
      any zero-CPG code surfaces a `no_cpg_found` badge in the trace.
    - Case 12 re-run: if Hypertension still doesn't route via the selected
      codes, the trace clearly says so on the relevant code rather than
      back-filling. Hypertension is then expected to land via the
      comorbidity-routing improvements (T4 / dedicated follow-up), not via
      this under-fill path.
    - Synthetic case where every selected code routes to 0 CPGs: top-level
      `out_of_scope` event fires; no CPGs returned.

## T4 — Capacity-of-5 mitigations (SUGGESTION ONLY — not in this task's scope)

> Status: **three alternative proposals for a follow-up task**. Do not implement
> as part of T1–T3. Documented here so the options are preserved while we ship
> the Major/Minor work first. After T1–T3 lands and we have real eval data on
> when the 5-cap bites, one of these three (or a combination) should be picked.

### Why this needs follow-up thinking

After T1–T3 ships, DDx will be capped at 5 predicted codes with a Major/Minor
split. This is enough for genuine differential diagnosis of the chief complaint,
but it quietly leaves two gaps:

1. **Re-prediction of declared comorbidities.** The clinician already typed
   `case.comorbidities = ["T2DM", "Obesity", "HFrEF"]` — but the DDx engine still
   spends some of its 5 slots re-discovering them. This steals capacity from
   genuine differential reasoning.
2. **Missed historical / inferred conditions.** Past disease mentioned in clinical
   notes ("h/o stroke 2019", "post-MI on aspirin"), or conditions implied by
   current medications (warfarin → AF or thrombosis history; levothyroxine →
   hypothyroidism), are not captured anywhere structured. They affect the current
   plan but never reach Stage 3 routing because they are neither in the chief
   complaint nor in the typed `comorbidities` list.

Three options below. They are not mutually exclusive — A + C combine cleanly.

---

### Option A — Three-channel routing (split DDx from comorbidities + extractor)

**Architecturally cleanest. Highest cost. Best long-term answer.**

Split the single-channel DDx engine into **three independent routing channels**,
all merging into Stage 3:

| Channel | Source | Cap | Notes |
|---|---|---|---|
| Primary DDx | Chief complaint + history (current engine) | 5 | Drives Major/Minor selection from T1–T3 |
| Declared comorbidities | `case.comorbidities` | none | Deterministic ICD-11 lookup; routes silently |
| Extracted problem-list codes | History + clinical notes + current meds (new LLM extractor) | 5 | Inferred conditions; routes silently, flagged "inferred" |

```
                   ┌─────────────────────────────────┐
Chief complaint →  │  DDx Engine                     │  → top-5 codes →
+ history          │  (working dx for THIS visit)    │     Major/Minor selection (T1–T3)
                   └─────────────────────────────────┘

case.comorbidities ──── deterministic ICD-11 lookup ──── no cap (declared)

                   ┌─────────────────────────────────┐
History + notes  → │  Problem-List Extractor (LLM)   │  → past/inferred ICD-11
+ current meds     │  "what other conditions exist?" │     codes (capped, e.g. 5)
                   └─────────────────────────────────┘
```

Implementation sketch:

- **Stage 1 case extraction** gains one new structured output field:

  ```python
  class PatientCase(BaseModel):
      # existing fields...
      comorbidities: list[str]            # declared (clinician typed)
      problem_list_codes: list[ICD11Code]  # NEW — extracted from history/notes/meds
  ```

- **Stage 1 extractor prompt** gets a new instruction: *"Also extract any past or
  current medical conditions mentioned in the history, clinical notes, or implied
  by the current medications, and map each to an ICD-11 code."*
- **Stage 3 routing** becomes:
  `route(major_code) + route(minor_codes) + route_all(comorbidities + problem_list_codes)`
  deduped by `cpg_name`. The Major/Minor allocation (T2) only governs the
  predicted-DDx portion of the merged set.
- **Stage 5 synthesis** receives CPGs tagged by source channel so the prompt can
  frame the plan correctly: "Primary diagnosis: …; Active comorbidities: …;
  Inferred from history/notes: …".

**Pros**
- DDx engine focuses purely on the differential for the chief complaint — cleaner Stage 2 rerank input.
- Surfaces past/inferred conditions that today fall through the cracks.
- Total CPG coverage grows without ever raising the DDx cap.

**Cons**
- Touches Stage 1 and Stage 5 — widens blast radius significantly.
- Needs its own eval pass and a new accuracy measurement for the problem-list extractor.
- Adds a separate LLM call to Stage 1.

---

### Option B — Bump the DDx cap from 5 → 7

**Lowest cost. Keeps one-engine model. Pragmatic stopgap.**

Extend the allocation table to handle two more codes. Same Major/Minor rules apply.

Allocation extension (1 major + N minors):

| Selection | Major slot | Minor slots | Total |
|---|---|---|---|
| 1 major + 0 minor | 3 | — | 3 |
| 1 major + 1 minor | 3 | 2 | 5 |
| 1 major + 2 minor | 3 | 1, 1 | 5 |
| 1 major + 3 minor | 3 | 1, 1, 1 | 6 |
| 1 major + 4 minor | 2 | 1, 1, 1, 1 | 6 |
| 1 major + 5 minor | 2 | 1, 1, 1, 1, 1 | 7 |
| 1 major + 6 minor (all 7) | 1 | 1, 1, 1, 1, 1, 1 | 7 |

(Or stay at the 5-CPG cap and just give Stage 2 more candidates to choose from
before clinician selection — the cap question can be decoupled from the DDx
count.)

**Pros**
- Single-line change to `top_k` in Stage 2; allocation helper extends mechanically.
- No new pipeline channels, no Stage 5 prompt rewrite.

**Cons**
- Dilutes Stage 2 rerank quality (LLM reasons over 7 candidates instead of 5).
- Stage 5 prompt grows (more CPG chunks competing for synthesis context).
- Still re-predicts declared comorbidities — doesn't solve the actual problem,
  just gives more room to repeat it.
- UI: 7 cards is borderline for a single-tap-per-row interaction (especially on
  laptop screens without scroll).

---

### Option C — Top-5 hard + expandable "Show more (up to 8)"

**UI-side compromise. Solves the polymorbid overflow without burdening the
typical visit.**

Stage 2 returns top-5 by default; an optional "Show more" toggle requests codes
6–8 from a second, cheaper LLM call (or simply takes the next 3 from the
existing math rank without rerank). The 5-row panel stays the default
experience; clinicians with a polymorbid patient can expand to 8.

Allocation: unchanged from T1–T3 for the first 5. If the clinician picks codes
from the expanded set, each expanded-pick counts as a Minor with a 1-slot
allotment (total CPG quota lifts to 5 + n_expanded_picks, capped at 7 or 8).

**Pros**
- Common case (1–3 active diagnoses) is unchanged — no Stage 2 dilution.
- Polymorbid edge case gets a release valve.
- Lower implementation cost than Option A.

**Cons**
- UI complexity: collapsed-by-default disclosure, separate render path for
  rank-6–8 cards.
- Two-pass Stage 2 LLM call adds latency on expand.
- Doesn't fix re-prediction-of-comorbidities, just adds more room for it.
- "Show more" is a feature clinicians may not discover — risks the expanded
  codes being effectively dead weight.

---

### Recommendation (for the follow-up task)

- **A + C in sequence.** Land A first to fix the re-prediction and missed-inferred
  problems at their root. Then add C later only if eval data shows the polymorbid
  acute case still bites the 5-cap after the comorbidity channel is split out.
- **Avoid B unless deeply time-constrained.** It treats the symptom, not the
  cause, and inflates Stage 2 rerank cost without solving the underlying issue.

### Cross-cutting open questions (apply to whichever option is picked)

- **Confidence threshold for inferred codes** (Options A and C). Should
  `problem_list_codes` extracted from notes/meds carry a confidence score, and
  below what threshold do we drop them silently vs. surface them to the
  clinician for verification?
- **UI surface for inferred codes** (Option A). Show inferred problem-list codes
  in the Major/Minor panel as a separate "Background context" section, or keep
  them invisible and only surface their CPGs in the plan view?
- **Conflict resolution** (Option A). What if the DDx engine and the
  problem-list extractor predict the same code at different confidences?
  Probably keep the DDx version (it owns the Major/Minor tiering), but flag for
  telemetry.
- **Medication → diagnosis inference safety** (Option A). Metformin alone
  doesn't prove T2DM (could be PCOS, prediabetes). Inferred codes from meds need
  a lower confidence weighting than codes named in notes.
- **Discoverability of "Show more"** (Option C). If expand stays collapsed by
  default, what telemetry signal triggers a one-time tooltip to teach the
  feature to clinicians with polymorbid patients?

## Chunk budget (measured 2026-05-29)

Stage 5 currently consumes **~58k tokens** on case 8 (26 chunks) against
`mimo-v2.5-pro` (128k context window) — **~46% utilisation, ~54% headroom**.
This sets a hard ceiling on how aggressively the Top-5 plan can fan out chunks.

| Constant | Value | Rationale |
|---|---|---|
| `STAGE3_MAX_CPGS` | 5 | Was 3. T2 allocation table caps every row at 5. |
| `STAGE4_CHUNKS_PER_CPG_MAJOR` | 4 | Major has 3 CPGs about the *same* dx → heavy overlap; 4 chunks each is enough. |
| `STAGE4_CHUNKS_PER_CPG_MINOR` | 4 | **Matches Major.** Originally proposed at 6 (different conditions need more chunks), but headroom on mimo-v2.5-pro is borderline (~46% used); keeping Minor=4 holds worst case ≈ 55k tokens (~43% of ctx). Bump to 6 only if Stage 5 ever moves to a ≥256k-ctx model. |
| `STAGE4_CHUNK_BUDGET_CEILING` | 30 | Safety brake. Warn loudly if exceeded — never reached in normal operation. |

Worst-case prompt size projections (current `mimo-v2.5-pro`, 128k ctx):

| Scenario | Chunks | Approx tokens | % of ctx |
|---|---|---|---|
| 1 major only `(3, [])` | 12 | ~50k | 39% |
| **1 major + 2 minor `(3, [1,1])`** ⭐ | 20 | ~55k | 43% |
| 1 major + 4 minor `(1, [1,1,1,1])` | 20 | ~55k | 43% |
| Today's case 8 baseline (no plan applied) | 26 | ~58k | 46% |

**Model-aware guardrail (must implement in P0):** at startup, check
`os.environ["STAGE5_LLM_CHOICE"]` against a known-context table. If the model's
context window is ≤32k, abort and log; this plan assumes ≥128k. Required because
today's baseline (58k) already exceeds 32k — silently switching Stage 5 to a
small-context model would corrupt synthesis without throwing.

## Risks & open questions

- **Stage 5 synthesis context budget.** Measured at ~58k tokens / 128k ctx today
  (46% used). The Top-5 plan keeps worst case under ~55k tokens by capping Minor
  CPGs at 4 chunks each. If `STAGE5_LLM_CHOICE` ever switches to a model with
  ≤64k ctx, re-run the measurement (`scripts/run_eval_case_08.py` + the temp
  `STAGE5_PROMPT_SIZE` logger) before shipping.
- **Quality-floor calibration.** 0.32 is calibrated for the D2 semantic-scope fallback
  fork, not for per-code-rank≥2 admission. P3 may need a separate constant
  (`STAGE3_TAIL_SLOT_THRESHOLD`).
- **Selection UX latency.** A blocking SSE handshake adds wall-clock time. Default
  timeout in interactive mode should be short (e.g. 5 s) with auto-accept rather than
  a hard wait, and the auto-select rule (T3.1) is what fires on timeout.
- **Back-compat for headless callers.** `run_eval_case_08.py` and existing tests must
  keep working without a selection step. P1 lands the auto-select rule first
  precisely so the eval path never blocks.

## Out of scope

- Multi-Major selection — exactly one Major is allowed. Co-primary cases are
  handled by routing the second-highest code as a Minor with a guaranteed slot
  rather than introducing a second Major.
- WHO API calls — all changes use existing local data.
- Re-calibrating `SEMANTIC_SCOPE_THRESHOLD` — reuse current 0.32 unless P3 evidence
  forces otherwise.
- Phase-A ingestion / chunks restructuring — orthogonal.
- Safety critic and referral extraction — covered by other tasks.
