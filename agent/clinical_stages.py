"""
Pipeline stages 2–5 for the clinical RAG workflow.

  stage_2_ddx        — differential diagnosis via ICD-11 vector search
  stage_3_route      — map DDx codes to CPG documents
  stage_4_retrieve   — LLM-generated queries + scoped vector retrieval
  stage_5_synthesize — structured TreatmentPlan synthesis from evidence
"""

from __future__ import annotations

import json
import logging
import os

import openai
from pydantic import BaseModel
from pydantic import ValidationError

from .models import ChunkResult, PatientCase, TreatmentPlan
from .routing import CPGDocRef, route_icd_to_cpgs
from .tools import VectorSearchInput, vector_search_tool

logger = logging.getLogger(__name__)

DDX_RERANK_MODEL = os.getenv("LLM_CHOICE", "gpt-4o")
DDX_THINKING_BUDGET = 5000   # tokens; sufficient for re-ranking ≤10 candidates


# ---------------------------------------------------------------------------
# DDxResult — pipeline-internal, not a user-facing schema type
# ---------------------------------------------------------------------------

class DDxResult(BaseModel):
    code: str
    title: str
    similarity: float
    inclusion_match: bool = False
    matched_term: str | None = None
    reasoning: list[str] = []


# ---------------------------------------------------------------------------
# Stage 2 — DDx
# ---------------------------------------------------------------------------

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


async def _llm_rerank_ddx(
    case: PatientCase,
    candidates: list[DDxResult],
    emit=None,                      # async callable(event_type, data) | None
) -> list[DDxResult]:
    """
    Re-rank DDx candidates using Gemini 2.5 Flash extended thinking.

    Falls back to original order on any failure.
    When emit is provided, streams thinking tokens as thinking_delta SSE events.
    """
    if not candidates:
        return candidates

    client = openai.AsyncOpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )

    vitals_str = json.dumps(case.vitals) if case.vitals else "none"
    candidate_lines = "\n".join(
        f"  {i+1}. {c.code}  {c.title}  (vector score: {c.similarity:.3f})"
        for i, c in enumerate(candidates)
    )

    prompt = f"""You are a clinical coding expert performing differential diagnosis.

Patient:
- Chief complaint: {case.chief_complaint}
- Age / sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Current medications: {", ".join(case.current_medications) or "none"}
- Allergies: {", ".join(case.allergies) or "none"}
- Vitals: {vitals_str}

Candidate ICD-11 codes (pre-ranked by vector similarity):
{candidate_lines}

Re-rank these candidates based on clinical probability for THIS specific patient.
Apply reasoning about:
- How age, sex, vitals, and comorbidities shift the prior probability of each code
- Whether current medications suggest an existing diagnosis
- Which codes are actionable vs incidental findings

Return a JSON array of objects, ordered from most to least likely. Include ALL candidates.
No markdown fences. Example format:
[
  {{"code": "BC81.3", "confidence": 0.91, "reasoning": "68M irregular pulse HR 110 — persistent AF fits best"}},
  {{"code": "BC81.1", "confidence": 0.72, "reasoning": "Paroxysmal AF cannot be excluded without Holter"}},
  ...
]"""

    try:
        raw_content = ""

        if emit is not None:
            # Streaming path — capture thinking tokens
            # Gemini 2.5 Flash thinks by default; no extra_body needed on the native API
            stream = await client.chat.completions.create(
                model=DDX_RERANK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # Google native API exposes thinking as delta.reasoning or delta.thinking
                thinking_chunk = (
                    getattr(delta, "reasoning", None)
                    or getattr(delta, "thinking", None)
                    or getattr(delta, "reasoning_content", None)
                )
                if thinking_chunk:
                    await emit("thinking_delta", {
                        "stage": 2,
                        "node": "DDx Re-rank",
                        "chunk": thinking_chunk,
                    })
                if delta.content:
                    raw_content += delta.content
        else:
            # Non-streaming path — identical to pre-Step-09 behavior
            resp = await client.chat.completions.create(
                model=DDX_RERANK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
            )
            raw_content = resp.choices[0].message.content

        # Parse re-ranked list (shared by both paths)
        raw = raw_content.strip().strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:]
        ranked = json.loads(raw)

        code_to_result = {c.code: c for c in candidates}
        reranked: list[DDxResult] = []
        for item in ranked:
            code = item.get("code")
            if code and code in code_to_result:
                result = code_to_result[code].model_copy()
                llm_reason = item.get("reasoning", "")
                if llm_reason:
                    result.reasoning = result.reasoning + [f"LLM: {llm_reason}"]
                reranked.append(result)

        seen = {r.code for r in reranked}
        for c in candidates:
            if c.code not in seen:
                reranked.append(c)

        logger.info("DDx re-ranked %d candidates via %s", len(reranked), DDX_RERANK_MODEL)
        return reranked

    except Exception as exc:
        logger.warning("DDx LLM re-rank failed (%s) — using original order", exc)
        return candidates


async def stage_2_ddx(
    case: PatientCase,
    top_k: int = 5,
    rerank: bool = True,
    emit=None,                      # async callable | None; passed through to _llm_rerank_ddx
) -> list[DDxResult]:
    """
    Return top-k ICD-11 differential diagnoses for the patient case.

    Pass 1: vector similarity + morbidity tabulation (search_ddx).
    Pass 2: Gemini 2.5 Flash thinking re-ranks by clinical probability.
    Set rerank=False to skip Pass 2 (e.g. in unit tests or latency-sensitive paths).
    When emit is provided, thinking tokens are streamed as thinking_delta events.
    """
    from ddx.search_ddx import search_ddx

    symptom_text = _build_symptom_text(case)

    fetch_k = top_k * 2 if rerank else top_k
    raw = await search_ddx(symptom_text, top_k=fetch_k)

    results: list[DDxResult] = []
    for r in raw:
        try:
            results.append(
                DDxResult(**{k: v for k, v in r.items() if k in DDxResult.model_fields})
            )
        except Exception as exc:
            logger.warning("Skipping malformed DDx result %r: %s", r, exc)

    if rerank and results:
        results = await _llm_rerank_ddx(case, results, emit=emit)

    return results[:top_k]


# ---------------------------------------------------------------------------
# Stage 3 — Route
# ---------------------------------------------------------------------------

async def stage_3_route(
    ddx: list[DDxResult],
    top_k_codes: int = 2,
    top_k_cpgs: int = 3,
    emit=None,                      # async callable | None
) -> list[CPGDocRef]:
    """Map the top DDx ICD-11 codes to CPG document sets."""
    all_refs: dict[str, CPGDocRef] = {}

    for result in ddx[:top_k_codes]:
        refs = await route_icd_to_cpgs(result.code, top_k=top_k_cpgs)
        for ref in refs:
            if ref.cpg_name not in all_refs:
                all_refs[ref.cpg_name] = ref
                if emit:
                    await emit("sub_step", {
                        "stage": 3,
                        "detail": f"{ref.cpg_name}",
                        "badge": ref.match_type,
                        "status": "complete",
                    })

    return list(all_refs.values())[:top_k_cpgs]


# ---------------------------------------------------------------------------
# Stage 4 — Retrieve
# ---------------------------------------------------------------------------

async def _generate_retrieval_queries(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    n: int = 3,
) -> list[str]:
    """Use the LLM to produce n focused retrieval queries for vector search."""
    # STAGE4_LLM_* vars override main LLM config (e.g. when primary API is blocked)
    base_url = os.getenv("STAGE4_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("STAGE4_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("STAGE4_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")

    client = openai.AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    icd_summary = ", ".join(f"{d.code} ({d.title})" for d in ddx[:2])
    cpg_names = ", ".join(c.cpg_name for c in cpgs)
    vitals_str = json.dumps(case.vitals) if case.vitals else "none"
    severity_str = json.dumps(getattr(case, "severity_staging", {})) if getattr(case, "severity_staging", None) else "not specified"

    system_prompt = _load_prompt("stage4_query_generation.txt")

    user_content = f"""patient_context:
- Chief complaint: {case.chief_complaint}
- Age/sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Current medications: {", ".join(case.current_medications) or "none"}
- Vitals: {vitals_str}

icd_codes: {icd_summary}
cpg_names: {cpg_names}
severity_staging: {severity_str}

Generate exactly {n} queries (one per domain as instructed)."""

    messages = (
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
        if system_prompt
        else [{"role": "user", "content": user_content}]
    )

    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.strip("` \n")
    if raw.startswith("json"):
        raw = raw[4:]
    queries = json.loads(raw)
    return [q for q in queries if isinstance(q, str)][:n]


async def stage_4_retrieve(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    queries_per_code: int = 5,
    chunks_per_query: int = 5,
    emit=None,                      # async callable | None
) -> list[ChunkResult]:
    """Generate targeted queries and retrieve scoped evidence chunks."""
    if not cpgs:
        logger.warning("stage_4_retrieve: no CPGs to scope search — returning empty")
        return []

    all_doc_ids = [doc_id for cpg in cpgs for doc_id in cpg.document_ids]

    if emit:
        await emit("sub_step", {
            "stage": 4,
            "detail": f"Generating {queries_per_code} targeted queries…",
            "status": "running",
        })

    queries = await _generate_retrieval_queries(case, ddx, cpgs, n=queries_per_code)

    seen_chunk_ids: set[str] = set()
    all_chunks: list[ChunkResult] = []

    for query in queries:
        results = await vector_search_tool(VectorSearchInput(
            query=query,
            limit=chunks_per_query,
            document_id_filter=all_doc_ids,
        ))
        new_chunks = 0
        for chunk in results:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)
                new_chunks += 1
        if emit:
            total = len(results)
            await emit("sub_step", {
                "stage": 4,
                "detail": f'"{query[:60]}{"…" if len(query) > 60 else ""}"',
                "badge": f"{new_chunks} new / {total} hits",
                "status": "complete",
            })

    _CATEGORY_BOOST: dict[str, float] = {
        "Treatment": 1.4,
        "Supportive Treatment": 1.3,
        "Assessment": 1.2,
        "Diagnosis": 1.2,
        "Prevention": 1.2,
        "Special Populations": 1.1,
        "Reference": 1.0,
        "Introduction": 0.5,
        "Pathophysiology": 0.4,
        "Epidemiology": 0.4,
        "Methodology": 0.3,
    }

    def _boosted_score(chunk: ChunkResult) -> float:
        cats = chunk.metadata.get("category", [])
        if not cats:
            return chunk.score
        boost = max(_CATEGORY_BOOST.get(cat, 1.0) for cat in cats)
        return min(chunk.score * boost, 1.0)

    all_chunks.sort(key=_boosted_score, reverse=True)
    final = all_chunks[:20]

    if emit:
        await emit("sub_step", {
            "stage": 4,
            "detail": f"{len(final)} unique chunks after deduplication",
            "status": "complete",
        })

    return final


# ---------------------------------------------------------------------------
# Stage 5 — Synthesize
# ---------------------------------------------------------------------------

def _load_prompt(filename: str) -> str:
    """Load a prompt from agent/prompts/<filename>. Falls back to empty string on error."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    try:
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("Prompt file not found: %s", prompt_path)
        return ""


SYNTHESIS_SYSTEM = _load_prompt("stage5_synthesis.txt")
SYNTHESIS_SCHEMA = TreatmentPlan.model_json_schema()


def _format_evidence(chunks: list[ChunkResult]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        section = c.metadata.get("section_number", "")
        cpg = c.document_title or c.document_source
        lines.append(f"[{i}] {cpg} §{section}\n{c.content[:800]}")
    return "\n\n".join(lines)


async def stage_5_synthesize(
    case: PatientCase,
    ddx: list[DDxResult],
    _cpgs: list[CPGDocRef],
    evidence: list[ChunkResult],
) -> TreatmentPlan:
    """Synthesise a structured TreatmentPlan from patient context and CPG evidence."""
    # STAGE5_LLM_* vars override main LLM config (e.g. when primary API is blocked)
    base_url = os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")

    client = openai.AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
    )

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

    # Ensure required fields are populated when LLM omits them
    data.setdefault("icd_primary", icd_primary)
    data.setdefault("icd_alternates", icd_alternates)
    data.setdefault("summary", f"ICD-11 {icd_primary}: {ddx[0].title if ddx else 'Unknown'}")
    data.setdefault("follow_up", [])

    try:
        return TreatmentPlan.model_validate(data)
    except ValidationError as exc:
        logger.error("TreatmentPlan validation failed. Raw JSON: %s", raw_json)
        raise RuntimeError(f"TreatmentPlan validation failed: {exc}") from exc
