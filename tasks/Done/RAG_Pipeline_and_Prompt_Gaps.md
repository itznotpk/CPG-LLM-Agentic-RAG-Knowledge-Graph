# RAG Pipeline — Remaining Work

> **Pipelines in use**
> - **Care plan (main):** Doctor UI **and** `clinical_cli.py` → `/clinical/plan/stream` → Stage 2–5 → `stage5_synthesis.txt` → `TreatmentPlan` JSON → 6-section render
> - **Legacy chat (not main):** `/chat/stream` → `rag_agent` (pydantic-ai) → `prompts.py` free-text markdown — left as-is
>
> **Architectural direction — Option C (hybrid, phased):**
> Keep the Stage 2 → 3 → 4 → 5 skeleton **deterministic** for predictability, streamable telemetry, and clinical validation. Add **agentic sub-loops inside Stage 4 and Stage 5** only after the deterministic KG path (R6) is proven correct. Stages 2 and 3 stay deterministic forever.

---

## Phase 1 — Category-aware retrieval (no re-ingestion) — ❌ NOT NEEDED

### R3 Phase 2 Step 1 — query-aware SQL category filter (plumbing + conservative default)

> **Status (2026-05-25): ❌ NOT NEEDED — superseded by shipped code.** Verified in codebase: `category_filter` on `VectorSearchInput`, the SQL clause, and `EXCLUDED_CATEGORIES` were never added. Both user-facing problems are fully solved by what *is* shipped: post-retrieval `_CATEGORY_BOOST` ([clinical_stages.py:1083](../agent/clinical_stages.py)) sinks Methodology/Epidemiology below the top-20 cut, and the token-budgeted assembler (`_TOTAL_TOKEN_BUDGET = 50_000`) prevents low-ranked noise from reaching the budget. A hard SQL filter is marginally cleaner but adds zero correctness or safety value. Do not build.
>
> **Original (now-obsolete) deferral rationale (2026-05-18):**
> Two of the three justifications below are now obsolete:
> 1. **The user-facing problem is already solved by the shipped score-boost** (`clinical_stages.py:489-510`): `Methodology ×0.3`, `Epidemiology ×0.4` sort to the bottom and fall outside the `all_chunks[:20]` cut — the clinician never sees them.
> 2. **The "consumes token budget" argument was killed by Phase A Step 1** — the old flat 4000-char/80k caps were replaced with a token-budgeted whole-chunk-or-skip assembler (`_TOTAL_TOKEN_BUDGET`). Low-ranked noise no longer reaches the budget.
> 3. R3 targets the *old* chunk/category shape and says "no re-ingestion"; after A-13 the category lives on H2/H3 children with the new schema, so any SQL filter must be (re)written against post-A-13 `db_utils.py` anyway.
> **Net:** a hard SQL filter is marginally cleaner than a soft boost but adds no correctness or safety value. ~1h plumbing, opportunistic only, **after A-13**. Not a standalone lane.

**Why (original rationale — points 1 & 2 now obsolete, see status above):** Background chunks (Methodology, Epidemiology) still consume the candidate slots and token budget. Phase 1 score-boost reorders them down but doesn't exclude them at the DB level.

**Do:**

1. Add `category_filter: list[str] | None` to `VectorSearchInput` in [db_utils.py](../agent/db_utils.py).
2. Add SQL clause to `vector_search`: `AND metadata->'category' ?| $N::text[]`.
3. In `stage_4_retrieve` ([clinical_stages.py](../agent/clinical_stages.py)), pass a hardcoded `EXCLUDED_CATEGORIES = {"Methodology", "Epidemiology"}` for **all 7 query domains** (conservative default).

**Defer:** Per-domain category map (Step 2) — only build if real cases show Methodology being needed for evidence-quality queries. The plumbing supports it; the value just stays hardcoded for now.

**Effort:** ~1 h.

---

## Phase 2 — Comorbidity routing (parallel, independent) — ✅ DONE

### C1 — `route_comorbidities` second pass — ✅ DONE (verified in code 2026-05-18)

> **Status:** Implemented and live in all orchestrator paths. Code **exceeds** the spec below — it adds a 0.55 similarity threshold to reject semantic-fallback drift, `top_k=3` DDx lookup, dedup against existing CPGs, a `comorbidities[:4]` latency cap, and full diagnostic logging. None of that is in the original snippet.
> **Evidence:** `route_comorbidities()` at [clinical_workflow.py:18-69](../agent/clinical_workflow.py); called after `stage_3_route` in the non-streaming path ([clinical_workflow.py:113](../agent/clinical_workflow.py)) and streaming path ([clinical_workflow.py:211](../agent/clinical_workflow.py), with `sub_step` "comorbidity" badge emit at :215). See also `Gaps_Closing.md` Gap 1 "✅ CODE IMPLEMENTED".
> **Do not re-implement.** The original spec snippet below is the weaker early draft, retained for history only.

**Why:** `stage_3_route` only routes the top-2 DDx ICDs to CPGs. A patient with T2DM + HTN never gets the DM or HTN CPGs consulted, even though they're ingested.

**Do (original draft — superseded by shipped code):** Add `route_comorbidities` after `stage_3_route` in [clinical_workflow.py](../agent/clinical_workflow.py):

```python
async def route_comorbidities(
    comorbidities: list[str],
    existing_cpgs: list[CPGDocRef],
    top_k: int = 2,
) -> list[CPGDocRef]:
    additional = []
    for condition in comorbidities:
        ddx = await search_ddx(condition, top_k=1)
        if ddx:
            refs = await route_icd_to_cpgs(ddx[0]["code"], top_k=top_k)
            for ref in refs:
                if ref.cpg_name not in {c.cpg_name for c in existing_cpgs}:
                    additional.append(ref)
    return additional
```

**Effort:** ~3 h. Independent of Phase 1 / 3 / 4.

---

## Phase 4 — Knowledge graph (deterministic wiring first) — ✅ DONE (Superseded)

### R6 — KG schema, extraction, and Stage 4 graph calls — ✅ DONE / Superseded (verified in code 2026-05-18)

**Why:** No graph-based contraindication, interaction, or pathway retrieval today. Stage 5 performs drug-interaction screening from LLM training memory — imperfect and unverifiable.

**Out of scope:** A hardcoded `HIGH_RISK_PAIRS` Python table. Every interaction must carry a `cpg_chunk_id` for traceability — only KG extraction from CPG text gives this.

#### Target schema

```
(Drug {name, generic_name, drug_class})
    -[:INTERACTS_WITH {severity, mechanism, cpg_chunk_id}]-> (Drug)
    -[:CONTRAINDICATED_IN {reason, severity, cpg_chunk_id}]-> (Condition)
    -[:CROSS_REACTS_WITH {risk_pct, cpg_chunk_id}]-> (Allergen)
    -[:REQUIRES_DOSE_ADJUSTMENT {trigger, target, cpg_chunk_id}]-> (Condition)

(Condition {name, icd11_code, severity_field})
    -[:FIRST_LINE_TREATMENT {grade, level, cpg_chunk_id}]-> (Drug)
    -[:MONITORED_BY {parameter, frequency, cpg_chunk_id}]-> (LabTest)
```

> **Status summary (verified against code 2026-05-18):** The KG **consumer wiring** (steps 4 & 5 — the actual point of R6) is fully implemented and live in all 3 orchestrator paths. Steps 1 & 3 (ICD on Condition nodes / ICD-scoped graph) were **deliberately cancelled** by a later architectural decision — see `Next-Step/KG_Remaining_Edits_Plan.md` "Architectural decision 2026-05-17": the KG must stay **global/unscoped** so cross-CPG drug-interaction safety signals are not suppressed; ICD→CPG mapping stays at the Postgres routing layer. Steps 2 & 6 are code-complete and AF-validated; full-corpus execution rides on Friend 1's pending re-ingest (`Phase_A_Step2` A-13/A-14 = `KG_Remaining_Edits_Plan.md` Phase B.2). **Do not re-implement. Do not add `icd11_code` to KG nodes — explicitly rejected as harmful.**

#### Do (in this order)

1. ⚠️ **Schema** — add `icd11_code` to `(:Condition)` nodes (Cypher batch). **SUPERSEDED — cancelled by design** (`KG_Remaining_Edits_Plan.md` item 8 dropped 2026-05-17; ICD belongs at Postgres routing, not KG nodes).
2. 🟡 **Re-extract** — re-run [graph_builder.py](../ingestion/graph_builder.py) scoped to Treatment/Assessment chunks. **Code done** (taxonomy + extraction prompt expanded — `KG_Remaining_Edits_Plan.md` Phase A ✅; AF dry-run ✅). Full 16-CPG batch pending Friend 1's re-ingest (Phase B.2 / A-14).
3. ⚠️ **Add `document_id_filter`** to `graph_search`. **SUPERSEDED — cancelled by design** (same architectural decision: KG safety lookup is intentionally global/unscoped — scoping would hide cross-CPG interactions).
4. ✅ **Wire deterministic graph calls into Stage 4** — **DONE.** `clinical_graph_lookup()` at [graph_clinical.py:298](../agent/graph_clinical.py) covers `CONTRAINDICATED_WITH|INTERACTS_WITH` (:130), `REQUIRES_DOSE_ADJUSTMENT` (:177), `CROSS_REACTS_WITH` (:230); wired between Stage 4 & 5 in all 3 paths ([clinical_workflow.py:132, 251, 355](../agent/clinical_workflow.py)). Candidate drugs grounded in retrieved chunks via `extract_candidate_drugs_from_chunks()`.
5. ✅ **Inject "INTERACTION FLAGS" block** into Stage 5 — **DONE.** `format_flags_for_prompt(flags)` → `flags_block` injected into the Stage 5 user prompt at [clinical_stages.py:949, 968](../agent/clinical_stages.py); `stage_5_synthesize(..., flags=kg_flags)` signature at :929. Each flag carries `cpg_chunk_id` / `cpg_chunk_ids`.
6. 🟡 **Validate** with fixture cases — AF polypharmacy gate ✅ passed (`scratch/test_phase_d_af.py`, `KG_Remaining_Edits_Plan.md` Phase D). Full warfarin/sulfa/CKD fixture validation deferred to post-Phase-B.2 (needs full-corpus flag density).
   - warfarin + retrieved-rivaroxaban → `INTERACTS_WITH severity=MAJOR`
   - sulfa allergy + retrieved-furosemide → `CROSS_REACTS_WITH risk_pct=1`
   - T2DM + retrieved-metformin + CKD Stage 4 → `REQUIRES_DOSE_ADJUSTMENT trigger=eGFR<30`

**Why deterministic first:** if graph extraction is buggy, you must see it cleanly before an LLM agent's tool calls obscure the cause. Build the data correctness, then hand the keys to an agent (Phase 5).

**Effort:** ~2.5 days total.

---

## Phase 5 — Agentic sub-loops inside Stage 4 and Stage 5

Phase 4 is shipped and validated. 5c is shipped (hybrid-deterministic, not agentic — see note). 5a and 5b remain 🟡 OPTIONAL — value is now marginal given Stage 4.5 KG injection + Stage 6 hybrid Safety Critic already cover the failure modes these were designed to catch.

### 5a — Stage 4 retrieval agent — ❌ NOT NEEDED

**Why:** Conditional graph lookups (drugs × meds × comorbidities) and retrieval self-correction (re-query thin domains) are exactly what an agent loop handles well — and what nested deterministic loops handle poorly.

**Do:**

- Convert `stage_4_retrieve` internals to a pydantic-ai sub-agent.
- Tools: `vector_search(query, category_filter)`, `graph_search(query, doc_ids)`, `find_interactions(drug_a, drug_b)`, `find_contraindications(drug, condition)`, `check_dose_adjustment(drug, comorbidity, lab_value)`.
- Tool-call budget cap (e.g., max 12 calls) to bound cost and latency.
- Outer pipeline contract unchanged: one call in, `list[ChunkResult]` + interaction flags out.
- New SSE event (or reuse `sub_step`) so the UI can show `Agent called find_interactions(warfarin, bosentan) → MAJOR`.

> **Status (2026-05-25): 🟡 OPTIONAL.** Stage 4.5 `clinical_graph_lookup` already injects deterministic KG flags (interactions, contraindications, dose-adjust, cross-react) into Stage 5 with `cpg_chunk_id` citations. Graph Navigator Agent 2 (`graph_navigator.py`) adds the positive-edge PREFER arm. Both run in parallel with Stage 4 retrieval — there is no remaining "conditional graph lookup" gap an agent loop would close. Re-query-thin-domains is the only remaining win; defer until a real case shows the need.

### 5b — Stage 5 self-critique loop — ❌ NOT NEEDED

**Why:** Stage 5 currently commits to its first JSON pass. If `monitoring=[]` and `red_flags=[]` despite the patient needing them, there's no recovery.

**Do:**

- After first JSON draft, inspect output coverage. If any mandatory section is empty AND no `unresolved_questions` entry justifies it, allow Stage 5 to call `request_more_evidence(domain, query)` and re-draft.
- Cap: one critique pass (two LLM calls max for thin cases, one for clean cases).

> **Status (2026-05-25): 🟡 OPTIONAL.** Stage 6 Safety Critic now catches the "missing monitoring / missing red_flags" failure mode post-hoc via KG verify + LLM critic merge — and surfaces it to the clinician rather than silently re-drafting. A self-critique loop would add latency and another LLM call for a problem already covered downstream. Defer.

### 5c — Safety Critic Phase 2: KG-grounded evaluator — ✅ SHIPPED (hybrid, not agentic)

> **Status (2026-05-25): ✅ SHIPPED — different shape than spec.** Implemented as `asyncio.gather(_llm_critic(), _kg_verify_plan(case, plan))` in [agent/safety_critic.py:238](../agent/safety_critic.py), merged without dedup. `_kg_verify_plan` ([:117](../agent/safety_critic.py)) runs deterministic Cypher (CONTRAINDICATED_WITH / INTERACTS_WITH / CROSS_REACTS_WITH / REQUIRES_DOSE_ADJUSTMENT / REQUIRES_MONITORING) — no pydantic-ai tool loop. Every flag carries `cpg_chunk_id`. Hardcoded sulfonamide list **removed** from `SAFETY_CRITIC_SYSTEM` (0 grep matches). Functionally equivalent to the agentic design at lower latency and zero extra LLM calls. **Do not re-implement as a tool-calling agent — the deterministic parallel shape is strictly better for a safety gate.**

#### Original spec (retained for history)

**Why:** The Safety Critic (already shipped as a post-Stage-5 LLM pass) currently relies on MiMo's training-time pharmacology memory. Smoke testing confirmed this is unreliable for nuanced cross-reactivities — the sulfa + furosemide case initially missed and required hardcoding the sulfonamide-derived drug list directly into the prompt. That hardcoded list is fragile maintenance debt; the KG is the principled fix.

**Current state:** [agent/safety_critic.py](../agent/safety_critic.py) is live, using MiMo v2.5-pro via `SAFETY_CRITIC_*` env vars (fallback to `STAGE5_*`). Sulfonamide cross-reactivity is handled via an explicit hardcoded drug list in the system prompt as a Phase 1 workaround.

**Do (after Phase 4 KG relations are validated):**

Convert `run_safety_critic` from a single LLM call to a pydantic-ai agent with four graph tools:

```python
tools = [
    find_interactions(drug_a, drug_b)          # → INTERACTS_WITH edges + cpg_chunk_id
    check_contraindications(drug, condition)   # → CONTRAINDICATED_IN edges + cpg_chunk_id
    check_allergy_crossreact(drug, allergen)   # → CROSS_REACTS_WITH edges + risk_pct + cpg_chunk_id
    check_dose_adjustment(drug, comorbidity)   # → REQUIRES_DOSE_ADJUSTMENT edges + threshold
]
```

The LLM's role shrinks to: receive structured graph results → assign severity → render `SafetyFlag` objects. Every flag carries a real `cpg_chunk_id` citation, not LLM memory.

**In the same PR:** Remove the hardcoded sulfonamide drug list from `SAFETY_CRITIC_SYSTEM` — the `CROSS_REACTS_WITH` graph edges replace it as the authoritative source.

**Model:** MiMo v2.5-pro remains appropriate — the task simplifies from "recall pharmacology" to "interpret structured graph evidence and decide severity," which suits a strong reasoning model.

**Effort:** ~1 day after Phase 4 is validated.

---

## Execution order

| # | Phase | Task | Effort | Status |
|---|---|---|---|---|
| 1 | 1 | R3 Phase 2 Step 1 — SQL category filter | 1 h | ❌ NOT NEEDED — superseded by shipped `_CATEGORY_BOOST` + token-budgeted assembler |
| 2 | 2 | C1 — comorbidity routing | 3 h | ✅ DONE (code exceeds spec) |
| — | 3 | ~~R7 — sibling fetch at retrieval~~ | — | ❌ DELETED — superseded by Phase A Step 2 parent-child chain (`Phase_A_Step2_ParentChild_Ingest.md`); whole parent section now attached to every child hit |
| 4 | 4 | R6 — KG extraction + deterministic Stage 4 wiring | 2.5 days | ✅ DONE / Superseded (wiring live; steps 1+3 cancelled by design; batch rides Friend 1's re-ingest) |
| 5 | 5a | Stage 4 → agentic sub-agent | 2 days | ❌ NOT NEEDED — superseded by Stage 4.5 KG + Graph Navigator + 7-domain queries |
| 6 | 5b | Stage 5 → self-critique loop | 1.5 days | ❌ NOT NEEDED — superseded by Stage 6 Safety Critic (visible flags > silent re-draft) |
| 7 | 5c | Safety Critic → KG-grounded | 1 day | ✅ DONE (hybrid-deterministic, not pydantic-ai agent — strictly better) |

---

## Completed (reference)

| Gap | What was done | Where |
|---|---|---|
| M1 | Added `summary` + `follow_up` to `TreatmentPlan` | [models.py](../agent/models.py) |
| R1 | Per-chunk limit 4000 chars, 80k total budget | [clinical_stages.py](../agent/clinical_stages.py) `_format_evidence` |
| R2 | Inline grade tag reading (Malaysian A–C / I–III) | [stage5_synthesis.txt](../agent/prompts/stage5_synthesis.txt) |
| R3 Phase 1 | Category score boosting post-retrieval | [clinical_stages.py](../agent/clinical_stages.py) `_CATEGORY_BOOST` |
| R4 | 7-domain query generation (covers all 6 care plan sections) | [stage4_query_generation.txt](../agent/prompts/stage4_query_generation.txt) |
| R5 | Mandatory 6-section synthesis rules + structured `monitoring` / `red_flags` | [stage5_synthesis.txt](../agent/prompts/stage5_synthesis.txt) |
| Safety Critic Phase 1 | Post-Stage-5 MiMo adversarial reviewer; `SafetyReport` banner in Doctor UI; fail-open; sulfonamide list hardcoded as Phase 1 workaround | [agent/safety_critic.py](../agent/safety_critic.py) |
| Safety Critic Phase 2 (5c) | Hybrid LLM critic + deterministic `_kg_verify_plan` via `asyncio.gather`; merged without dedup; sulfonamide hardcode removed; every flag carries `cpg_chunk_id` | [agent/safety_critic.py](../agent/safety_critic.py) |
| Graph Navigator (Agent 2) | Positive-edge PREFER arm (FIRST_LINE_FOR / SECOND_LINE_FOR / RECOMMENDED_FOR); CPG-scope filter + table-row-noise filter; fail-open | [agent/graph_navigator.py](../agent/graph_navigator.py) |
| Path B typed thresholds | `threshold_param/op/value/unit/negated` extraction in `graph_builder.py`, gated by `threshold_confidence="high"`; extractor-side table-row-noise filter; 721 typed edges live in Neo4j | [ingestion/graph_builder.py](../ingestion/graph_builder.py) |
| Routing D1–D6 + exclusion_rerank D3 gate + semantic_scope D5 | Deterministic ICD→CPG resolution with calibrated thresholds | [agent/routing.py](../agent/routing.py) — see `Next-Step/Last Step Improvement/DDx Gap/DDx_Routing_Robustness_And_Exclusion_Rerank.md` |
