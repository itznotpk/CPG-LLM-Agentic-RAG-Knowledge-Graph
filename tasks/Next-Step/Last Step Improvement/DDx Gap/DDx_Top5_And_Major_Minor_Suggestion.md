# DDx Top-5 Suggestion + Clinician-Driven CPG Routing

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
- [ ] `selected_codes` + `major_code` parameters added to `stage_3_route`
- [ ] `_auto_select_codes(ddx)` implemented + unit-tested
- [ ] `_allocate_major_minor(n_minor)` implemented + unit-tested for n_minor=0..4
- [ ] case08 trace matches expected branch

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
- [ ] Major-first allotment fill implemented
- [ ] Cascade rule implemented (cap 3)
- [ ] Unit test for cascade behaviour
- [ ] case08 returns CPGs respecting Major allotment

### P3 — T2.3 + T2.4: Quality floor + Stage 5 synthesis hand-off

- Track: T2
- Deliverable:
  - A code's first CPG always returns; its 2nd or 3rd CPG only if
    `ref.score >= SEMANTIC_SCOPE_THRESHOLD`
  - `major_code` propagated to Stage 5 and surfaced in the synthesis prompt as
    "Primary diagnosis"
- Files: `agent/clinical_stages.py` (guard inside the per-code fill loop, gated by
  per-code rank ≥ 2; Stage 5 prompt builder), `agent/prompts/stage5_synthesis.txt`
  (add Primary / Co-considerations framing)
- Exit gate:
  - synthetic case where Major has 1 strong + 2 weak CPGs and 0 minors returns 1
    (not 3) — unit test
  - synthetic case `(3, [2])` where Major has 1 strong + 2 weak returns 1+2 = 3
    (not 5) — unit test
  - case08 still fills 5 slots when all candidates clear the floor
  - case08 Stage 5 prompt mentions Major code by name as primary diagnosis

Progress:
- [ ] Per-code-rank guard implemented
- [ ] Low-quality single-pillar test passes
- [ ] Low-quality Major+Minor test passes
- [ ] case08 fill unchanged (all candidates above floor)
- [ ] Stage 5 prompt updated with Major framing
- [ ] `STAGE3_TAIL_SLOT_THRESHOLD` constant added if calibration diverges from 0.32

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
- [ ] `DDxSuggestion` + `DDxSelection` schemas in `agent/models.py`
- [ ] `major_code` validator enforced
- [ ] SSE emit added between Stage 2 and Stage 3
- [ ] Selection plumbed into `stage_3_route(selected_codes=..., major_code=...)`
- [ ] Headless regression test green
- [ ] Interactive path test green

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
- [ ] `TierSegmentedControl` component built and unit-styled
- [ ] Panel renders top-5 with rank / code / title / confidence bar
- [ ] All rows initialised to `Off`
- [ ] Tier state managed in `AppContext` with Major-exclusivity invariant
- [ ] Hint badge surfaces top-1 / top-2 suggestion (tap to apply)
- [ ] Restore-suggestion re-shows dismissed hint badges
- [ ] Keyboard shortcuts wired (1–5, Enter)
- [ ] Confirm posts via `clinicalApi.postDDxSelection`
- [ ] `ddx_selection` trace event carries `major_code` and `selected_codes`

### P6 — Wrap-up + telemetry

- Track: —
- Deliverable: Update `tasks/Next-Step/Last Step Improvement/DDx Gap/ddx_routing_robustness_report.md`
  with before/after CPG coverage, per-pillar split, and observed selection patterns
- Exit gate: at least 3 eval cases re-run end-to-end; report appendix signed off

Progress:
- [ ] Eval re-run for case08, case09, and one additional case
- [ ] Coverage diff appended to report
- [ ] Telemetry counters reviewed

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

## Risks & open questions

- **Stage 5 synthesis context budget.** Five CPGs ≈ 1.5× current chunk volume. Verify
  Stage 4 retrieval `top_k` per CPG still fits the synthesis prompt under MiMo /
  Gemini Flash limits before P1 lands. If it doesn't, drop per-CPG chunk count
  proportionally before bumping the CPG quota.
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
