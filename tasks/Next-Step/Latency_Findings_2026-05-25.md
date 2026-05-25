# Latency Investigation — Findings & Next Steps (2026-05-25)

> **Trigger:** Full clinical workflow takes ~220s (≈4 min) end-to-end.
> **Goal:** Cut latency without regressing clinical answer quality.
> **Status:** Step 1 (instrumentation) DONE. Per-stage numbers MEASURED — see §0.
> **Rule:** Performance changes must not regress clinical answer quality. Re-run `run_e2e_eval` after each change.

---

## 0. MEASURED RESULTS (2026-05-25, 1 case: qa_001)

`python -m eval.run_latency_eval --limit 1`. Total **416,549 ms (~417s)**.

| Stage | Time | Share |
|---|---|---|
| **stage_2_ddx** | **164,530 ms** | **39%** |
| **stage_6_safety** | **142,878 ms** | **34%** |
| stage_5_synthesize | 76,997 ms | 18% |
| stage_4_retrieve | 29,857 ms | 7% |
| kg_lookup | 1,626 ms | 0% |
| stage_3_route | 586 ms | 0% |
| graph_navigator | 72 ms | 0% |
| stage_3_route_comorbidities | 0 ms | 0% |

**Key findings — these OVERTURN the original hypothesis (§3 below was written before measuring):**
1. **Stage 2 (DDx) + Stage 6 (Safety) = 73% of total.** Synthesis (Stage 5) is only 18% — NOT the dominant cost as first guessed.
2. **Total was 417s, ~2× the reported 220s.** MiMo endpoint latency varies a lot run-to-run → infra load is itself a variable. Single-case numbers are noisy; treat as order-of-magnitude.
3. **Root cause is shared across the 3 slow stages:** all call the MiMo reasoning model (`mimo-v2.5-pro`) on the SGP reseller endpoint with **unbounded output, thinking ON, and no timeout**:
   - Stage 2 DDx re-rank: `max_tokens=8000` on a thinking model (`clinical_stages.py:394,424`).
   - Stage 5 synthesis: no `max_tokens`, thinking not disabled (`clinical_stages.py:1666`).
   - Stage 6 safety critic: no `max_tokens`, thinking not disabled, default retries, no timeout (`safety_critic.py:215-223`) — uses `STAGE5_LLM_CHOICE` = mimo-v2.5-pro. A "lightweight" post-check is actually a full reasoning call.
4. **Stage 2 also hit the silent fail-open:** "Symptom extraction returned empty → falling back to raw notes." MiMo extraction returned empty content (likely burned its budget on hidden reasoning), so retrieval ran on raw notes. This is a quality bug AND wasted time.

**Revised priority (highest leverage first):**
1. **Stage 6 safety critic (34%, ~143s):** cap `max_tokens`, disable thinking, set `timeout` + `max_retries=0`. Biggest easy win — it's a post-hoc check that should be fast. Consider a smaller/faster model via `SAFETY_CRITIC_MODEL` (the env hook already exists, `safety_critic.py:183`).
2. **Stage 2 DDx (39%, ~165s):** lower re-rank `max_tokens` 8000→2000, disable thinking on extraction (fixes both latency AND the empty-fallback bug), parallelize extraction+hypotheses (§3.6).
3. **Stage 5 synthesis (18%, ~77s):** §3.2 (cap tokens, disable thinking).
4. The MiMo endpoint itself (§3.1) is the floor under all of the above.

> Next: apply fix #1 (Stage 6), re-measure 1 case, confirm the share drops. Then #2.

---

## 1. What was done (Step 1 — measure first)

Added per-stage timing so we stop guessing:

- **`agent/clinical_workflow.py`**
  - `_time_stage()` context manager — records wall-clock ms per segment (records even if the stage raises).
  - `_log_stage_breakdown()` — emits one sorted log line at the end, e.g.
    `Stage timing breakdown (total 218000 ms): stage_5_synthesize=120000ms (55%) | stage_4_retrieve=48000ms (22%) | ...`
  - New `stage_timings: dict[str, float]` field on `WorkflowResult`.
  - Instrumented all 8 segments of `run_clinical_workflow`: `stage_2_ddx`, `stage_3_route`, `stage_3_route_comorbidities`, `stage_4_retrieve`, `kg_lookup`, `graph_navigator`, `stage_5_synthesize`, `stage_6_safety`.
- **`eval/run_latency_eval.py`**
  - Now drives the full `run_clinical_workflow` and reads `stage_timings`, so the breakdown includes KG lookup, graph navigator, comorbidity routing, and Stage 6 — the old version timed only stages 2–5 directly and silently skipped these.

**Also fixed (blocker):** `eval/gold_sets/clinical_qa_gold.jsonl` had a stray `"` after the `hr` value on 4 lines (18, 19, 29, 30), e.g. `"hr": 78"}` → `"hr": 78}`. This was crashing `load_jsonl` before any timing could run.

### How to get the numbers
```powershell
python -m eval.run_latency_eval
```
Prints p50/p95/p99 per stage + total, writes timestamped CSV/JSON to `eval/results/`. A single real request also now logs the breakdown line — `grep "Stage timing breakdown"`.

**NOT yet instrumented:** the streaming path (`run_clinical_workflow_streaming`), which the live Doctor UI uses. Add the same `_time_stage` wrappers there if UI-perceived latency needs measuring.

---

## 2. Why micro-optimizations are NOT the answer

At the 220s scale, the dominant costs are infrastructure, not loop-level code. The earlier agent scan flagged things like "parallelize 3 Neo4j queries (~50-100ms)" — these are real but they are milliseconds against a 220-second total. Do not start there.

The big costs almost certainly live in the external LLM calls (see §3). Confirm with the breakdown first.

---

## 3. Suspected bottlenecks (ranked — verify against breakdown before acting)

### 3.1 The MiMo reseller endpoint (suspected #1)
All three heavy stages (2, 4, 5) route to `token-plan-sgp.xiaomimimo.com` — a **third-party token-plan reseller**, not a first-party API. These typically have request queuing, rate limits, and slow time-to-first-token. If one synthesis call is 60–120s, no code change fixes it.
- **Action if confirmed:** move synthesis (Stage 5) to a faster model (Gemini Flash / Claude Haiku are dramatically faster for long structured output). Quality tradeoff — test against the gold set, do not assume.
- **Config:** `.env` lines 17–34 (`LLM_*`, `STAGE4_LLM_*`, `STAGE5_LLM_*`).

### 3.2 Stage 5 synthesis: no token cap, thinking left ON (high-value fix)
`agent/clinical_stages.py:1666-1674` — the synthesis call has **no `max_tokens`** and does **not** disable thinking, unlike extraction which sets `enable_thinking: False` (line 657). MiMo is a reasoning model, so it can burn unbounded hidden reasoning tokens over the 50k-token context before emitting JSON.
- **Action:** add `max_tokens` and disable thinking on the Stage 5 call, mirroring the extraction path.

### 3.3 Default retries inflating latency silently
Only the extraction client sets `max_retries=0` (`clinical_stages.py:647`). The Stage 4 (`:975`) and Stage 5 (`:1626`) clients use the OpenAI SDK default of **2 retries with exponential backoff**. A 429/500 from the reseller = tens of seconds of invisible retry with no log line.
- **Action:** set `max_retries=0` (or 1) and an explicit `timeout` on the Stage 4/5 clients so a slow call fails fast instead of hanging + retrying. (SDK default timeout is 600s — one stalled call can dominate the whole run.)

### 3.4 Stage 4 embeddings: 7 cross-region Bedrock calls
`stage_4_retrieve` runs `queries_per_code=7` (`clinical_stages.py:1025`); each query embeds via Bedrock Titan in `us-east-1` (`.env:47-48`) from SG — cross-region round-trips, wrapped in a sync boto3 executor call.
- **Actions:** (a) drop `queries_per_code` 7 → 4 (retrieval quality barely changes); (b) consider an in-memory embedding cache; (c) longer-term, co-locate or switch embedding provider — but switching requires re-ingesting the vector DB so embeddings match.

### 3.5 DDx re-ranker `max_tokens=8000`
`clinical_stages.py:394` and `:424` — the re-ranker only needs to emit a short JSON array of ~5 codes; 8000 output tokens on a thinking model is excessive.
- **Action:** lower to ~2000.

### 3.6 Stage 2 sequential LLM calls (minor)
`clinical_stages.py:659` (symptom extraction) and `:688` (condition hypotheses) are independent but run sequentially.
- **Action:** wrap both in `asyncio.gather`. Saves one LLM round-trip.

---

## 4. Recommended order

1. **Run `python -m eval.run_latency_eval`** — get the real breakdown. (DONE-able now.)
2. Identify the dominant stage from the p50 numbers.
3. If Stage 5 dominates (likely): apply §3.2 + §3.3, re-measure.
4. If Stage 4 dominates: apply §3.4(a) + §3.3, re-measure.
5. Only if infra is the floor (§3.1): evaluate a faster synthesis model against the gold set for accuracy before switching.
6. Re-run latency eval after each change; confirm no accuracy regression via `run_e2e_eval`.

**Each change must be benchmark-justified, not speculative. Performance is never worth a wrong clinical answer.**
