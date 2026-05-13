# Phase A — Step 3: Performance Pass (After Correctness)

> **Position in rollout:** Step 3 of 3. Runs **only after** Step 1 and Step 2 are in production and clinical answers are verified correct.
> **Goal:** Cut latency and Bedrock spend without changing answer quality. Pure performance work — every change here must be benchmark-justified, not speculative.
> **Status:** Not yet started. Implement only after Step 2 re-ingest is stable.

---

## 1. Prerequisites

Do not start Step 3 until:
- Step 1 caps removed, end-to-end clinical query returns correct answer.
- Step 2 parent-child re-ingest done; KG triples carry H2 UUIDs; retrieval hits H2 children.
- A benchmark suite of 10–20 representative clinical queries exists with **known-correct outputs**. Without this, any "speedup" is unsafe — you cannot tell if a perf change regressed accuracy.

---

## 2. Changes

### 2.1 Anthropic prompt caching on static content

For each Bedrock call in `clinical_stages.py`, the message layout is:

```
[system]  stage-N-system-prompt.txt          ← CACHE (constant per stage)
[user]    SCHEMA (TreatmentPlan JSON schema) ← CACHE (constant)
[user]    evidence pack                       ← do NOT cache (variable per query)
[user]    clinical query                      ← do NOT cache
```

Anthropic cache has a 5-minute TTL. With 5 stages × N consultations per session, the system prompt + schema gets reused many times. Add:

```python
messages = [
    {"role": "system", "content": [
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
    ]},
    {"role": "user", "content": [
        {"type": "text", "text": schema_json, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": evidence_pack},
        {"type": "text", "text": user_query},
    ]},
]
```

Measure cache_read_input_tokens in the response to confirm hit rate >70% in a typical session.

### 2.2 Per-stage evidence rightsizing

Step 1 introduced a `_format_evidence_light` variant for Stage 4. Step 3 formalises this:

| Stage | Evidence size | Why |
|---|---|---|
| 1 — Intent | None | Operates on query alone |
| 2 — Entity | None | Operates on query alone |
| 3 — Retrieval | None | Generates queries; doesn't consume chunks |
| 4 — Grading | Children only, ~30k tokens | Relevance check — no parent needed |
| 5 — Synthesis | Full pack with parents, ~50k tokens | Needs full context for grounded answer |

Bedrock input tokens per consultation should drop ~40% versus a naive "format full evidence for every stage" path.

### 2.3 Parallelise independent stages

Stages 1 and 2 (intent + entity) operate on the query alone — independent. Run them in parallel via `asyncio.gather`. Saves one LLM round-trip's worth of latency per consultation (~500ms–1s).

Stages 3, 4, 5 remain sequential (each depends on the previous output).

### 2.4 Embedding cache

The same query embedding is computed multiple times today (Stage 3 retrieval + any rerank step). Add an in-memory LRU keyed on `query_text`:

```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def _embed_cached(query_text: str) -> tuple[float, ...]:
    return tuple(embed(query_text))
```

`tuple` because lists are unhashable; convert back to list at call site. Negligible code change; eliminates redundant embedding calls during a single consultation.

### 2.5 NeonDB connection pooling audit

Confirm `db_utils.py` uses an asyncpg pool, not per-call connections. If per-call, every retrieval pays ~50–100ms TCP+TLS handshake. One-time fix, big latency win.

### 2.6 Triple-extraction batching (KG path)

Currently `graph_builder.py` extracts triples one sub-window at a time. Bedrock Converse API supports concurrent calls. Bound concurrency at `asyncio.Semaphore(5)` to avoid rate-limit churn:

```python
sem = asyncio.Semaphore(5)
async def extract(window):
    async with sem:
        return await self._extract_triples_with_llm(window)
results = await asyncio.gather(*[extract(w) for w in windows])
```

Reduces re-ingest wall time from minutes to seconds for large CPGs. No quality impact (triple dedup is unchanged).

---

## 3. Out-of-Scope for Step 3 (Tempting but Risky)

- **Switching to a smaller model for Stages 1–3.** Cheaper, but mixing models complicates failure modes. Revisit only after a real cost problem appears.
- **Pre-computing all embeddings at NeonDB write-time and storing alongside chunks** — already done. Don't re-touch.
- **Streaming Stage 5 output.** UX improvement, but not a correctness or cost win. Separate workstream.

---

## 4. Implementation Steps

| Step | Action | Files | Risk |
|------|--------|-------|------|
| S3-1 | Build 10–20 query regression benchmark | `tests/clinical_regression/` | Medium |
| S3-2 | Add `cache_control` to system prompts + schema in Bedrock messages | `clinical_stages.py` | Low |
| S3-3 | Measure cache hit rate; tune cache block boundaries if <60% | telemetry | Low |
| S3-4 | Formalise `_format_evidence_light` for Stage 4 | `clinical_stages.py` | Low |
| S3-5 | `asyncio.gather` Stages 1+2 | `agent.py` orchestration | Low |
| S3-6 | Add `_embed_cached` LRU | `agent/embedder.py` (or wherever embed lives) | Low |
| S3-7 | Audit asyncpg pool usage | `db_utils.py` | Low |
| S3-8 | Batch triple extraction with `Semaphore(5)` | `graph_builder.py` | Medium |
| S3-9 | Re-run regression benchmark; confirm zero accuracy regression | tests | High |

---

## 5. Expected Outcome

- Per-consultation Bedrock spend down ~50% (caching + per-stage rightsizing).
- End-to-end consultation latency down ~30% (parallel stages + pooling).
- Full KG re-ingest time down from ~10 min to ~2 min for the whole CPG library.
- **Zero change in clinical answer correctness** — verified by the regression suite.

If any benchmark query regresses, revert the specific change and investigate before continuing. Performance is never worth a wrong clinical answer.
