# Step 07 — Pipeline Stages 2–5 (DDx → Routing → Retrieval → TreatmentPlan)

## Context

You are working on **CPG LLM**, a Clinical Practice Guideline-grounded RAG system. The full design is in [tasks/IMPLEMENTATION.md](IMPLEMENTATION.md) — read §2, §4 Steps H–I, §5 before starting.

Steps 01–06 are complete:
- `PatientCase`, `Recommendation`, `TreatmentPlan` models exist in [agent/models.py](../agent/models.py).
- `route_icd_to_cpgs()` and `CPGDocRef` exist in [agent/routing.py](../agent/routing.py).
- `vector_search_tool`, `hybrid_search_tool` in [agent/tools.py](../agent/tools.py) accept `document_id_filter`.
- `search_ddx()` exists in [ddx/search_ddx.py](../ddx/search_ddx.py) — two-stage ICD retrieval (vector + morbidity tabulation layer).
- LLM is OpenRouter Gemini Flash via `get_llm_model()` in [agent/providers.py](../agent/providers.py).

This is **Step 07 of 8**. Build the four inner pipeline stages as individual async functions, and a **known bug fix** to routing.

---

## Bug fix required FIRST: `CPGDocRef` grouping in `agent/routing.py`

### The problem
`documents` has **212 rows** — each row is one **section** of a CPG (e.g. STEMI has ~13 section rows, all with different UUIDs but same `metadata->>'cpg_name'`). The current `route_icd_to_cpgs()` returns one `CPGDocRef` per **row**, so `top_k=3` caps at 3 section rows instead of 3 CPGs. That means the `document_id_filter` passed to vector search misses most of a CPG's sections.

### The fix
1. Add `cpg_name: str` and `document_ids: list[str]` to `CPGDocRef`. Keep `document_id: str` as the first/representative ID (first section row) for backward compatibility.
2. Refactor `_structural_match`, `_range_match`, `_semantic_fallback` to **group results by `metadata->>'cpg_name'`** and collect all matching row IDs under `document_ids`.
3. `top_k` now means top-K **CPGs**, not top-K rows.

Updated `CPGDocRef`:
```python
class CPGDocRef(BaseModel):
    cpg_name: str                        # e.g. "STEMI(4th Edition)"
    document_id: str                     # first/representative section UUID
    document_ids: list[str]              # ALL section UUIDs for this CPG
    title: str                           # title of the representative section row
    match_type: Literal["exact", "parent", "semantic"]
    score: float
    matched_scope: str
```

Updated SQL in `_structural_match` — add `metadata->>'cpg_name'` to SELECT and GROUP in Python:
```python
rows = await conn.fetch("""
    SELECT id::text, title, icd11_scope, metadata->>'cpg_name' AS cpg_name
    FROM documents
    WHERE scope_verified = TRUE
      AND (
          $1 = ANY(icd11_scope)
          OR LEFT($1, 3) = ANY(icd11_scope)
          OR LEFT($1, 4) = ANY(icd11_scope)
      )
""", icd_code)

# Group by cpg_name
from collections import defaultdict
groups: dict[str, dict] = defaultdict(lambda: {"ids": [], "title": "", "icd11_scope": [], "match_type": "parent", "matched": ""})
for row in rows:
    name = row["cpg_name"] or row["id"]   # fallback if cpg_name missing
    groups[name]["ids"].append(row["id"])
    groups[name]["title"] = groups[name]["title"] or row["title"]
    groups[name]["icd11_scope"] = row["icd11_scope"]
    # determine match_type and matched scope for this group
    ...

return [
    CPGDocRef(
        cpg_name=name,
        document_id=v["ids"][0],
        document_ids=v["ids"],
        title=v["title"],
        match_type=v["match_type"],
        score=1.0,
        matched_scope=v["matched"],
    )
    for name, v in groups.items()
]
```

Apply same grouping pattern to `_range_match` and `_semantic_fallback`.

**Update `tests/test_routing.py`** to reflect the new `CPGDocRef` shape. All 17 existing tests must still pass.

---

## Objective

Build `agent/clinical_stages.py` — four async functions, one per pipeline stage:

```
stage_2_ddx(case: PatientCase) -> list[DDxResult]
stage_3_route(ddx: list[DDxResult]) -> list[CPGDocRef]
stage_4_retrieve(case: PatientCase, cpgs: list[CPGDocRef]) -> list[ChunkResult]
stage_5_synthesize(case: PatientCase, ddx: list[DDxResult], cpgs: list[CPGDocRef], evidence: list[ChunkResult]) -> TreatmentPlan
```

Each function is independently importable and testable. Do NOT build the orchestrator here — that's Step 08.

---

## Deliverable 1: `agent/clinical_stages.py`

### Data model

```python
from pydantic import BaseModel

class DDxResult(BaseModel):
    code: str               # ICD-11 code, e.g. "BC81.3"
    title: str
    similarity: float       # vector similarity score 0–1
    inclusion_match: bool = False
    matched_term: str | None = None
    reasoning: list[str] = []
```

### Stage 2 — DDx (`stage_2_ddx`)

Wraps the existing `search_ddx()` from `ddx.search_ddx`.

```python
from ddx.search_ddx import search_ddx

async def stage_2_ddx(case: PatientCase, top_k: int = 5) -> list[DDxResult]:
    # Build symptom text from PatientCase
    symptom_text = _build_symptom_text(case)
    raw = await search_ddx(symptom_text, top_k=top_k)
    return [DDxResult(**{k: v for k, v in r.items() if k in DDxResult.model_fields}) for r in raw]
```

`_build_symptom_text` — concatenates available fields:
```python
def _build_symptom_text(case: PatientCase) -> str:
    parts = [case.chief_complaint]
    if case.history:
        parts.append(case.history)
    if case.comorbidities:
        parts.append("Comorbidities: " + ", ".join(case.comorbidities))
    if case.vitals:
        vitals_str = ", ".join(f"{k}={v}" for k, v in case.vitals.items())
        parts.append("Vitals: " + vitals_str)
    return ". ".join(parts)
```

### Stage 3 — Route (`stage_3_route`)

Calls `route_icd_to_cpgs` for each DDx code, unions results, deduplicates by `cpg_name`.

```python
from .routing import route_icd_to_cpgs, CPGDocRef

async def stage_3_route(
    ddx: list[DDxResult],
    top_k_codes: int = 2,        # use top-2 DDx codes for routing
    top_k_cpgs: int = 3,         # max CPGs to return
) -> list[CPGDocRef]:
    all_refs: dict[str, CPGDocRef] = {}   # keyed by cpg_name

    for result in ddx[:top_k_codes]:
        refs = await route_icd_to_cpgs(result.code, top_k=top_k_cpgs)
        for ref in refs:
            if ref.cpg_name not in all_refs:
                all_refs[ref.cpg_name] = ref

    return list(all_refs.values())[:top_k_cpgs]
```

### Stage 4 — Retrieve (`stage_4_retrieve`)

Two sub-steps:
1. **Targeted query generation** — LLM produces 3–5 focused retrieval queries from the patient case + predicted ICD + CPG names.
2. **Scoped vector search** — each query runs through `vector_search_tool` with `document_id_filter`.

```python
from .tools import vector_search_tool, VectorSearchInput
from .providers import get_llm_model
import pydantic_ai

async def stage_4_retrieve(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    queries_per_code: int = 3,
    chunks_per_query: int = 5,
) -> list[ChunkResult]:
```

#### 4a. Targeted query generation

Use the LLM (OpenRouter Gemini Flash via `get_llm_model()`) to generate retrieval queries. Use raw `openai.AsyncOpenAI` client (same pattern as `ingestion/classify_cpg_scope.py` — Pydantic AI rejects OpenRouter's extra fields):

```python
import openai, os, json

async def _generate_retrieval_queries(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    n: int = 3,
) -> list[str]:
    client = openai.AsyncOpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )
    model = os.getenv("LLM_CHOICE", "google/gemini-2.0-flash-001")

    icd_summary = ", ".join(f"{d.code} ({d.title})" for d in ddx[:2])
    cpg_names = ", ".join(c.cpg_name for c in cpgs)
    vitals_str = json.dumps(case.vitals) if case.vitals else "none"

    prompt = f"""You are a clinical search query expert.

Patient:
- Chief complaint: {case.chief_complaint}
- Age/sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Current medications: {", ".join(case.current_medications) or "none"}
- Vitals: {vitals_str}

Predicted ICD-11 codes: {icd_summary}
Relevant CPGs: {cpg_names}

Generate exactly {n} targeted search queries to retrieve the most relevant CPG recommendations for this patient.
Each query should target a specific clinical decision (e.g. drug choice, dosing, contraindication check, monitoring).
Do NOT use the patient's name or generic phrases like "treatment guidelines".
Return a JSON array of strings, nothing else. Example: ["query 1", "query 2", "query 3"]"""

    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content.strip()
    # Strip markdown code fences if present
    raw = raw.strip("` \n")
    if raw.startswith("json"):
        raw = raw[4:]
    queries = json.loads(raw)
    return [q for q in queries if isinstance(q, str)][:n]
```

#### 4b. Scoped vector search + deduplication

```python
    # Collect all document IDs across matched CPGs
    all_doc_ids = [doc_id for cpg in cpgs for doc_id in cpg.document_ids]

    queries = await _generate_retrieval_queries(case, ddx, cpgs, n=queries_per_code)

    seen_chunk_ids: set[str] = set()
    all_chunks: list[ChunkResult] = []

    for query in queries:
        results = await vector_search_tool(VectorSearchInput(
            query=query,
            limit=chunks_per_query,
            document_id_filter=all_doc_ids,
        ))
        for chunk in results:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)

    # Sort by score descending, cap at 20 chunks total
    all_chunks.sort(key=lambda c: c.score, reverse=True)
    return all_chunks[:20]
```

### Stage 5 — Synthesize (`stage_5_synthesize`)

LLM call with structured output to produce `TreatmentPlan`. Use raw `openai.AsyncOpenAI` with JSON mode (same pattern as stage 4 query gen — avoids Pydantic AI OpenRouter compatibility issue). Parse and validate with `TreatmentPlan.model_validate()`.

```python
async def stage_5_synthesize(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    evidence: list[ChunkResult],
) -> TreatmentPlan:
```

#### Evidence formatting

```python
def _format_evidence(chunks: list[ChunkResult]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        section = c.metadata.get("section_number", "")
        cpg = c.document_title or c.document_source
        lines.append(f"[{i}] {cpg} §{section}\n{c.content[:400]}")
    return "\n\n".join(lines)
```

#### Synthesis prompt

```python
SYNTHESIS_SYSTEM = """You are a clinical decision support system grounded in evidence-based guidelines.
Your role is to synthesise a treatment plan from the retrieved CPG evidence provided.

Rules:
- Every Recommendation.cpg_source MUST reference a specific CPG and section from the evidence (e.g. "CPG AF Management §4.2"). Do not invent sources.
- If the evidence does not cover a needed clinical decision, add it to unresolved_questions instead of inventing a recommendation.
- evidence_grade must come verbatim from the retrieved text (e.g. "Grade A, Level I") or be null if not stated.
- confidence reflects how completely the evidence addresses this case (0.0 = no evidence, 1.0 = full coverage).
- Return valid JSON matching the TreatmentPlan schema exactly. No markdown fences."""

SYNTHESIS_SCHEMA = TreatmentPlan.model_json_schema()
```

```python
    client = openai.AsyncOpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )
    model = os.getenv("LLM_CHOICE", "google/gemini-2.0-flash-001")

    evidence_text = _format_evidence(evidence)
    icd_primary = ddx[0].code if ddx else "Unknown"
    icd_alternates = [d.code for d in ddx[1:3]]

    user_prompt = f"""Patient Case:
- Chief complaint: {case.chief_complaint}
- Age/sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Medications: {", ".join(case.current_medications) or "none"}
- Allergies: {", ".join(case.allergies) or "none"}
- Vitals: {json.dumps(case.vitals) if case.vitals else "none"}

Predicted ICD-11: {icd_primary} ({ddx[0].title if ddx else ""})
Alternate codes: {", ".join(icd_alternates) or "none"}

Retrieved Evidence ({len(evidence)} chunks):
{evidence_text}

Produce a TreatmentPlan JSON object matching this schema:
{json.dumps(SYNTHESIS_SCHEMA, indent=2)}"""

    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYNTHESIS_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw_json = resp.choices[0].message.content.strip()
    data = json.loads(raw_json)

    # Ensure icd_primary and icd_alternates are set from DDx (LLM may omit)
    data.setdefault("icd_primary", icd_primary)
    data.setdefault("icd_alternates", icd_alternates)

    return TreatmentPlan.model_validate(data)
```

If `TreatmentPlan.model_validate()` raises `ValidationError`, catch it, log the raw JSON, and re-raise as a `RuntimeError("TreatmentPlan validation failed: ...")` so the orchestrator (Step 08) can handle it.

---

## Deliverable 2: Tests `tests/test_clinical_stages.py`

All tests mocked — NO real DB, NO real LLM, NO real embeddings.

### Required tests

#### Stage 2
- **`test_stage2_builds_symptom_text`** — case with chief_complaint + history + comorbidities → `_build_symptom_text` includes all parts.
- **`test_stage2_calls_search_ddx`** — mock `search_ddx`; assert called with symptom text, returns `DDxResult` list.
- **`test_stage2_handles_empty_ddx`** — `search_ddx` returns [] → stage returns [].

#### Stage 3
- **`test_stage3_routes_top2_codes`** — mock `route_icd_to_cpgs`; 3 DDx codes passed → only top 2 used for routing.
- **`test_stage3_deduplicates_cpgs`** — two DDx codes both route to same CPG → CPG appears once.
- **`test_stage3_caps_at_top_k_cpgs`** — 5 unique CPGs from routing → only top_k_cpgs=3 returned.

#### Stage 4
- **`test_stage4_generates_queries`** — mock `_generate_retrieval_queries`; assert returns list of strings.
- **`test_stage4_scoped_search`** — mock `vector_search_tool`; assert called with `document_id_filter` containing all CPG doc IDs.
- **`test_stage4_deduplicates_chunks`** — same chunk_id returned by two queries → appears once in output.
- **`test_stage4_caps_at_20_chunks`** — 3 queries × 5 chunks = 15 unique + 5 dupes → returns ≤20.
- **`test_stage4_query_gen_llm_call`** — mock `openai.AsyncOpenAI`; assert system prompt mentions CPG names and ICD codes.

#### Stage 5
- **`test_stage5_returns_treatment_plan`** — mock LLM returns valid TreatmentPlan JSON → `TreatmentPlan` returned.
- **`test_stage5_sets_icd_from_ddx`** — LLM omits icd_primary → stage fills it from DDx results.
- **`test_stage5_validation_error_raises_runtime`** — LLM returns invalid JSON (missing required field) → `RuntimeError` raised, not `ValidationError`.
- **`test_stage5_formats_evidence_with_section`** — chunk with `metadata["section_number"]=4` → formatted as `§4` in prompt.
- **`test_stage5_empty_evidence_populates_unresolved`** — zero evidence chunks → plan has non-empty `unresolved_questions` (LLM mock returns this).

#### Routing fix (update `tests/test_routing.py`)
- **`test_cpgdocref_has_document_ids`** — structural match against AF CPG (13 rows mocked) → `CPGDocRef.document_ids` has 13 entries, `top_k=1` returns 1 CPGDocRef (not 1 row).
- **`test_route_top_k_is_cpg_count`** — 2 CPGs with 10 rows each → `top_k=1` returns 1 CPGDocRef with 10 document_ids.

---

## Implementation notes

- **Import path for `search_ddx`**: `from ddx.search_ddx import search_ddx`. The `ddx/` directory is a package (check for `__init__.py`; create empty one if missing).
- **Do NOT use `pydantic_ai.Agent`** for LLM calls in stages 4 and 5 — use raw `openai.AsyncOpenAI` directly (same as `ingestion/classify_cpg_scope.py`). OpenRouter adds `service_tier` to responses which Pydantic AI rejects.
- **`response_format={"type": "json_object"}`** is supported by OpenRouter with Gemini Flash. If the model ignores it, strip markdown fences as a fallback.
- **`ChunkResult`** is already in [agent/models.py](../agent/models.py) — import from there, do not redefine.
- **`DDxResult`** lives in `agent/clinical_stages.py` (not models.py) — it is pipeline-internal.
- Stage 4 `queries_per_code=3` default produces up to 3 queries × 5 chunks = 15 unique chunks before cap. Tune in Step 08 if needed.
- If `cpgs` is empty (routing found nothing), stage 4 should return [] and log a warning. Stage 5 with empty evidence should still return a valid `TreatmentPlan` with all `unresolved_questions` populated.

---

## Out of scope

- ❌ Do NOT build the orchestrator (`agent/clinical_workflow.py`) — that is Step 08.
- ❌ Do NOT add `POST /clinical/plan` endpoint — Step 08.
- ❌ Do NOT add `document_ids` to the agent tool registry — Step 08 wires it up.
- ❌ Do NOT modify `ddx/search_ddx.py` — use it as-is.
- ❌ Do NOT add hybrid or graph search to Stage 4 for now — vector only is sufficient for v1.
- ❌ Do NOT add retry logic to the LLM calls — Step 08 handles pipeline-level error handling.

---

## Done criteria

All four must pass:

1. `pytest tests/test_clinical_stages.py -v` — all tests green, zero real API/DB/embedding calls.
2. `pytest tests/test_routing.py -v` — all tests still green after CPGDocRef fix (add 2 new tests, keep all 17 existing passing).
3. Manual smoke (no real DB needed — mock or dry-run):
   ```python
   # python -c "
   # import asyncio
   # from agent.clinical_stages import _build_symptom_text
   # from agent.models import PatientCase
   # case = PatientCase(chief_complaint='palpitations, irregular pulse', age=68, sex='M')
   # print(_build_symptom_text(case))
   # "
   # Expected: 'palpitations, irregular pulse'
   ```
4. `from agent.clinical_stages import stage_2_ddx, stage_3_route, stage_4_retrieve, stage_5_synthesize, DDxResult` — no import errors.

---

## Report back

When you finish, tell the user:

1. **Files created/modified** — exact paths.
2. **CPGDocRef fix** — confirm `document_ids` field added, confirm all 17 + 2 new routing tests pass.
3. **Stage functions** — list the 4 function signatures as implemented.
4. **Test output** — last ~35 lines of `pytest tests/test_clinical_stages.py tests/test_routing.py -v`.
5. **Any deviations** from this brief and why.
6. **Follow-ups noticed but not done** (for Step 08).
