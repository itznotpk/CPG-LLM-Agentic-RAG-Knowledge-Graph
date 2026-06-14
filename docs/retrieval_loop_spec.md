# Retrieval Loop — Boundary Specification

**Status:** Draft (pre-implementation)
**Owner:** Chua Zhu Heng
**Date:** 2026-06-14
**Scope:** Stage 4 query generation → retrieval (KG traversal + hybrid chunk retrieval). Synthesis (Stage 5) stays single-shot.

> Purpose of this doc: define every boundary of the loop **before** writing code, so the loop has explicit stop conditions, a measurable success bar, and a defined fallback. A retrieval loop without these is the #1 source of infinite loops, error amplification, and latency blowout.

---

## 0. Why a loop here (one-line rationale)

Stage 4 retrieval currently regresses **-17.3% coverage** vs the Layer 2 baseline (Coverage 79.7% vs ceiling 97.1%). A loop that reformulates the query / expands KG hops when coverage is weak is meant to close that gap on complex multi-hop queries — **not** to speed anything up.

---

## 1. EVALUATION BOUNDARIES

### 1.1 Goals — what "good retrieval" means for this loop

The loop is satisfied when the assembled context **covers every clinical sub-question in the query**, not merely "returns 10 chunks."

- Retrieval output is fixed at **top-10 chunks** (unchanged). The loop changes *which* 10, not *how many*.
- "Covered" = every distinct clinical entity / sub-question in the user query maps to at least one relevant chunk OR resolved KG node in the final set.
- Out of scope: improving synthesis, reducing latency, changing chunk count.

### 1.2 Standard — the measurable stop threshold

The loop **stops looping (success)** when ANY of:

| Signal | Threshold |
|---|---|
| Coverage score (judge) | ≥ 0.80 |
| All KG entities in query resolved to nodes | true |
| First-hit present (≥1 high-relevance chunk in top-10) | true |

Targets the loop must **beat vs single-shot baseline** to justify shipping:
- Coverage (recall@20-equivalent): **79.7% → ≥ 90%**
- First-Hit (hit@10): **80.4% → ≥ 90%**
- nDCG@10: **0.494 → ≥ baseline 0.657** (do not regress ranking)

### 1.3 Records — what each iteration logs

Per iteration, persist:
- `iteration_n`
- `query_used` (the reformulated query / KG hop for this pass)
- `action_taken` (reformulate | expand_kg_hops | lower_sim_threshold)
- `chunk_ids_retrieved` + scores
- `kg_nodes_resolved`
- `judge_score` + `judge_reason`
- `stop_decision` + `stop_reason`
- `cumulative_latency_ms`, `cumulative_tokens`

Used for: debugging, the eval harness, and detecting the no-new-info condition (compare chunk_ids across iterations).

### 1.4 Judge — who evaluates each iteration

- **Primary:** heuristic first (cheap) — coverage = fraction of query entities with a matching chunk/node. No LLM call if heuristic already ≥ threshold.
  - **Coverage checklist source (confirmed available):** reuse what `_generate_retrieval_queries` already computes — the **DDx ICD codes**, **CPG names**, and the **3 generated query domains**. Coverage = did the top-10 touch each ICD condition + each query domain? No new extraction step needed; keeps heuristic LLM-free.
- **Secondary (only if heuristic ambiguous):** single LLM coverage-scoring call.
  - **Model:** Gemini 2.5 Flash (fast, and keeps judge independent from MiMo synthesis — preserves the model-diversity property already used for the safety critic).
  - Judge must NOT be the synthesis model.

---

## 2. CONTROL BOUNDARIES  *(the loop-safety part — most important)*

### 2.1 Max iterations (hard cap)
- **2 iterations** default (initial pass + 1 retry). Absolute ceiling **3**.
- Enforced regardless of judge verdict. This is the infinite-loop safety net.

### 2.2 Termination conditions (multiple exit doors)
Loop exits on the FIRST of:
1. ✅ Standard met (§1.2)
2. ⛔ Max iterations reached
3. 🔁 **No new information** — iteration N retrieves the same chunk_ids as N-1 → stop (key anti-loop guard)
4. ⏱️ Latency budget exceeded (§2.3)

### 2.3 Latency & cost budget (per query)
- **Latency ceiling: 2.0s** for the whole retrieval stage (fits behind the existing care-plan loading state).
- **Token ceiling: ~20K** per query across all iterations.
- If a budget is hit mid-loop → exit immediately, go to fallback (§2.5).

### 2.4 Action per iteration (must differ each pass)
The loop is pointless unless each pass does something different. Defined escalation order:
1. **Iter 1:** baseline query → hybrid retrieval (current behaviour)
2. **Iter 2 (if needed):** reformulate query for uncovered sub-questions OR expand KG traversal by +1 hop
3. **Iter 3 (rare):** broaden via the **existing deterministic anchor queries** (investigations / lifestyle / referrals / condition pillars — already in `stage_4_retrieve`), then re-rank to top-10. No new mechanism to build.

### 2.5 Fallback — behaviour when exiting UNSATISFIED
When the loop exits without meeting the Standard (max iters / budget hit / no-new-info):
- Return the **best-scoring top-10 seen across all iterations** (never the last iteration if an earlier one scored higher).
- Set `retrieval_confidence = low` flag forwarded to Stage 5 synthesis.
- Synthesis prompt should acknowledge low-confidence context (hedge / flag gaps) — **never silently pass weak context as if complete.**
- Log fallback event for eval.

### 2.6 Baseline to beat (recorded before build)
Frozen single-shot numbers the loop is measured against (from `project_retrieval_eval.md` / Layer 3):

| Metric | Single-shot baseline | Loop target |
|---|---|---|
| Coverage (recall@20) | 79.7% | ≥ 90% |
| First-Hit (hit@10) | 80.4% | ≥ 90% |
| nDCG@10 | 0.494 | ≥ 0.657 (no ranking regression) |
| p95 retrieval latency | (measure now) | ≤ 2.0s |

If the loop does not beat single-shot on coverage/first-hit, it is **pure added latency — do not ship.**

---

## 3. Pre-implementation checklist

- [ ] Record current single-shot p50/p95 retrieval latency (fill §2.6) — **run `backend/eval/run_latency_eval.py`; read `stage_4_retrieve_ms` + `kg_lookup_ms` + `graph_navigator_ms` p95. Instrumentation already exists.**
- [x] Query-entity source confirmed — reuse DDx ICD codes + CPG names + generated query domains from `_generate_retrieval_queries` (no new extraction needed)
- [ ] Decide reformulation prompt for Iter 2
- [ ] Wire per-iteration logging (§1.3) before adding loop logic
- [ ] Build eval harness that runs loop vs single-shot on the same 120 queries
- [ ] Set feature flag so loop can be disabled per-query / globally

---

## 4. Condensed boundary table

| Boundary | Decision |
|---|---|
| Goals | All query sub-questions covered in fixed top-10 |
| Standard | Coverage ≥ 0.80 / entities resolved / first-hit present |
| Records | Per-iter query, chunks, action, judge score, stop reason |
| Judge | Heuristic first → Gemini Flash (≠ synthesis model) |
| Max iters | 2 (hard cap 3) |
| Stop conds | met / max / no-new-info / latency |
| Budget | 2.0s, ~20K tokens per query |
| Action/iter | reformulate → expand KG hop → broaden+rerank |
| Fallback | best top-10 seen + low-confidence flag to synthesis |
| Baseline | must beat 79.7% coverage / 80.4% first-hit |
