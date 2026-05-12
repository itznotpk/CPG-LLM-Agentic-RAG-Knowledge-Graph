# RAG Pipeline — Remaining Work

> **Pipelines in use**
> - **Care plan (main):** Doctor UI **and** `clinical_cli.py` → `/clinical/plan/stream` → Stage 2–5 → `stage5_synthesis.txt` → `TreatmentPlan` JSON → 6-section render
> - **Legacy chat (not main):** `/chat/stream` → `rag_agent` (pydantic-ai) → `prompts.py` free-text markdown — left as-is
>
> **Architectural direction — Option C (hybrid, phased):**
> Keep the Stage 2 → 3 → 4 → 5 skeleton **deterministic** for predictability, streamable telemetry, and clinical validation. Add **agentic sub-loops inside Stage 4 and Stage 5** only after the deterministic KG path (R6) is proven correct. Stages 2 and 3 stay deterministic forever.

---

## Phase 1 — Category-aware retrieval (no re-ingestion)

### R3 Phase 2 Step 1 — query-aware SQL category filter (plumbing + conservative default)

**Why:** Background chunks (Methodology, Epidemiology) still consume the candidate slots and token budget. Phase 1 score-boost reorders them down but doesn't exclude them at the DB level.

**Do:**

1. Add `category_filter: list[str] | None` to `VectorSearchInput` in [db_utils.py](../agent/db_utils.py).
2. Add SQL clause to `vector_search`: `AND metadata->'category' ?| $N::text[]`.
3. In `stage_4_retrieve` ([clinical_stages.py](../agent/clinical_stages.py)), pass a hardcoded `EXCLUDED_CATEGORIES = {"Methodology", "Epidemiology"}` for **all 7 query domains** (conservative default).

**Defer:** Per-domain category map (Step 2) — only build if real cases show Methodology being needed for evidence-quality queries. The plumbing supports it; the value just stays hardcoded for now.

**Effort:** ~1 h.

---

## Phase 2 — Comorbidity routing (parallel, independent)

### C1 — `route_comorbidities` second pass

**Why:** `stage_3_route` only routes the top-2 DDx ICDs to CPGs. A patient with T2DM + HTN never gets the DM or HTN CPGs consulted, even though they're ingested.

**Do:** Add `route_comorbidities` after `stage_3_route` in [clinical_workflow.py](../agent/clinical_workflow.py):

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

## Phase 3 — Section-level context enrichment

### R7 — chunk-context retrieval (Option A: sibling fetch at query time)

**Why:** `chunk_method: "markdown_header"` stores each section as one chunk. Some sections are 18k+ chars; even with the 4000-char per-chunk cap we see ~22% of the section. Grade tags and dose details deeper in the section are invisible.

**Pick:** **Option A — sibling fetch at retrieval time** (no re-ingestion, no schema change). When chunk 4.5 is retrieved, fetch all siblings in Section 4 ordered by `section_number` and inject them in order.

**Do:** Extend the post-retrieval pass in [db_utils.py](../agent/db_utils.py):

```python
sibling_sql = """
  SELECT id, content, metadata FROM document_chunks
  WHERE document_id = $1
    AND metadata->>'context_path' LIKE $2
  ORDER BY (metadata->>'section_number')::float
"""
# $2 = 'Section 4%'  (derived by stripping last '.x' from retrieved chunk's context_path)
```

**Fallback (Option C — only if grade misses persist on flat sections):** sub-split sections where `total_chunks: 1` and content > 5000 chars at `chunk_size=600, chunk_overlap=200`. Requires scoped re-ingestion.

**Why not naive paragraph splitting:** CPG paragraphs have up-down dependency. *"Add ERA 62.5mg BD"* is meaningless without the preceding paragraph defining the population as *"WHO FC III–IV with RHC-confirmed PAH"*. Splitting severs this.

**Effort:** ~0.5 day for Option A. Fallback Option C ~0.5 day re-ingestion if needed.

---

## Phase 4 — Knowledge graph (deterministic wiring first)

### R6 — KG schema, extraction, and Stage 4 graph calls

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

#### Do (in this order)

1. **Schema** — add `icd11_code` to `(:Condition)` nodes (Cypher batch). *2 h.*
2. **Re-extract** — re-run [graph_builder.py](../ingestion/graph_builder.py) scoped to Treatment/Assessment chunks (via category filter from Phase 1). Extraction prompt must explicitly target the 6 relation types above. *1 day.*
3. **Add `document_id_filter`** to `graph_search` so results are scoped to the routed CPGs. *2 h.*
4. **Wire deterministic graph calls into Stage 4** ([clinical_stages.py](../agent/clinical_stages.py)) — direct function calls, NOT pydantic-ai tools yet:
   - For each `case.current_medications` × each drug mentioned in retrieved chunks → `graph_search` for `INTERACTS_WITH`
   - For each `case.allergies` → `graph_search` for `CROSS_REACTS_WITH` edges
   - For each `case.comorbidities` ICD × each drug in chunks → `graph_search` for `REQUIRES_DOSE_ADJUSTMENT`
   *0.5 day.*
5. **Inject "INTERACTION FLAGS" block** prepended to evidence text passed to Stage 5. Each flag carries its `cpg_chunk_id` citation. *0.5 day.*
6. **Validate** with fixture cases:
   - warfarin + retrieved-rivaroxaban → `INTERACTS_WITH severity=MAJOR`
   - sulfa allergy + retrieved-furosemide → `CROSS_REACTS_WITH risk_pct=1`
   - T2DM + retrieved-metformin + CKD Stage 4 → `REQUIRES_DOSE_ADJUSTMENT trigger=eGFR<30`

**Why deterministic first:** if graph extraction is buggy, you must see it cleanly before an LLM agent's tool calls obscure the cause. Build the data correctness, then hand the keys to an agent (Phase 5).

**Effort:** ~2.5 days total.

---

## Phase 5 — Agentic sub-loops inside Stage 4 and Stage 5

Only start once Phase 4 is shipped and graph results are clinically validated.

### 5a — Stage 4 retrieval agent

**Why:** Conditional graph lookups (drugs × meds × comorbidities) and retrieval self-correction (re-query thin domains) are exactly what an agent loop handles well — and what nested deterministic loops handle poorly.

**Do:**

- Convert `stage_4_retrieve` internals to a pydantic-ai sub-agent.
- Tools: `vector_search(query, category_filter)`, `graph_search(query, doc_ids)`, `find_interactions(drug_a, drug_b)`, `find_contraindications(drug, condition)`, `check_dose_adjustment(drug, comorbidity, lab_value)`.
- Tool-call budget cap (e.g., max 12 calls) to bound cost and latency.
- Outer pipeline contract unchanged: one call in, `list[ChunkResult]` + interaction flags out.
- New SSE event (or reuse `sub_step`) so the UI can show `Agent called find_interactions(warfarin, bosentan) → MAJOR`.

### 5b — Stage 5 self-critique loop

**Why:** Stage 5 currently commits to its first JSON pass. If `monitoring=[]` and `red_flags=[]` despite the patient needing them, there's no recovery.

**Do:**

- After first JSON draft, inspect output coverage. If any mandatory section is empty AND no `unresolved_questions` entry justifies it, allow Stage 5 to call `request_more_evidence(domain, query)` and re-draft.
- Cap: one critique pass (two LLM calls max for thin cases, one for clean cases).

**Effort:** ~3–4 days total for 5a + 5b.

### 5c — Safety Critic Phase 2: KG-grounded evaluator

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

| # | Phase | Task | Effort | Blocks |
|---|---|---|---|---|
| 1 | 1 | R3 Phase 2 Step 1 — SQL category filter | 1 h | — |
| 2 | 2 | C1 — comorbidity routing | 3 h | independent, can run in parallel |
| 3 | 3 | R7 — sibling fetch at retrieval | 0.5 day | — |
| 4 | 4 | R6 — KG schema + extraction + deterministic Stage 4 wiring | 2.5 days | needs Phase 1 (category filter) for scoped re-extraction |
| 5 | 5a | Stage 4 → agentic sub-agent | 2 days | needs Phase 4 validated |
| 6 | 5b | Stage 5 → self-critique loop | 1.5 days | needs Phase 5a (proves the agentic pattern works) |
| 7 | 5c | Safety Critic → KG-grounded pydantic-ai agent; remove hardcoded sulfonamide list | 1 day | needs Phase 4 KG relations validated |

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
