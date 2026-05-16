"""
Pipeline stages 2–5 for the clinical RAG workflow.

  stage_2_ddx        — differential diagnosis via ICD-11 vector search
  stage_3_route      — map DDx codes to CPG documents
  stage_4_retrieve   — LLM-generated queries + scoped vector retrieval
  stage_5_synthesize — structured TreatmentPlan synthesis from evidence
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import openai
try:
    import tiktoken
except ImportError:  # pragma: no cover - only used before requirements are reinstalled
    tiktoken = None
from pydantic import BaseModel
from pydantic import ValidationError

from .db_utils import db_pool
from .graph_clinical import ClinicalFlag, format_flags_for_prompt
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

    # Stage 2 override (e.g. MiMo) takes precedence over primary LLM_* vars.
    # Trades thinking-token transparency for availability when Google credits are exhausted.
    stage2_base = os.getenv("STAGE2_LLM_BASE_URL")
    stage2_key = os.getenv("STAGE2_LLM_API_KEY")
    stage2_model = os.getenv("STAGE2_LLM_CHOICE")
    using_override = bool(stage2_base and stage2_key and stage2_model)

    client = openai.AsyncOpenAI(
        base_url=stage2_base or os.getenv("LLM_BASE_URL"),
        api_key=stage2_key or os.getenv("LLM_API_KEY"),
    )
    active_model = stage2_model or DDX_RERANK_MODEL
    logger.info(
        "Stage 2 rerank using model=%s endpoint=%s (override=%s)",
        active_model,
        stage2_base or os.getenv("LLM_BASE_URL"),
        using_override,
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

CRITICAL OUTPUT RULES:
- Keep ALL reasoning extremely concise — one short sentence per code, max 20 words each.
- Your TOTAL response must be under 1500 tokens. The JSON array is the required output.
- Return ONLY the JSON array. No preamble, no markdown fences, no explanation before/after.
- Include ALL candidate codes, ordered from most to least likely.

Format:
[
  {{"code": "BC81.3", "confidence": 0.91, "reasoning": "68M with irregular HR 110 — persistent AF fits best"}},
  {{"code": "BC81.1", "confidence": 0.72, "reasoning": "Paroxysmal AF cannot be excluded without Holter"}}
]"""

    try:
        raw_content = ""

        if emit is not None:
            # Streaming path — capture thinking tokens
            # max_tokens caps total output so MiMo doesn't burn the budget on
            # verbose reasoning and run out before emitting the JSON array.
            stream = await client.chat.completions.create(
                model=active_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                max_tokens=4000,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # TEMP diagnostic — remove after confirming thinking field name
                delta_dict = delta.model_dump() if hasattr(delta, "model_dump") else delta.__dict__
                logger.debug("Stage 2 delta: %s", {k: v for k, v in delta_dict.items() if v})
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
                model=active_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                max_tokens=4000,
            )
            raw_content = resp.choices[0].message.content

        # Parse re-ranked list (shared by both paths).
        # Robust to MiMo prepending reasoning prose before the JSON array — locate
        # the first '[' and parse from there. Falls through to the outer except
        # if no valid array found.
        raw = raw_content.strip().strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:].strip()
        if not raw.startswith("["):
            bracket_idx = raw.find("[")
            if bracket_idx == -1:
                raise ValueError(
                    f"No JSON array found in rerank output (len={len(raw_content)} chars). "
                    f"First 200 chars: {raw_content[:200]!r}"
                )
            raw = raw[bracket_idx:]
            # Trim anything after the matching closing ']' to handle trailing prose
            end_idx = raw.rfind("]")
            if end_idx != -1:
                raw = raw[: end_idx + 1]
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

        logger.info("DDx re-ranked %d candidates via %s", len(reranked), active_model)
        return reranked

    except Exception as exc:
        logger.warning(
            "DDx LLM re-rank FAILED with model=%s endpoint=%s: %s — using original order",
            active_model,
            stage2_base or os.getenv("LLM_BASE_URL"),
            exc,
        )
        return candidates


async def _extract_symptom_phrase(
    notes: str,
    client: openai.AsyncOpenAI,
    model: str,
) -> str:
    """Compress clinical notes to a symptom-focused query string for DDx vector search.

    Long clinical narratives dilute the ICD-11 vector match. This pre-step extracts
    only the presenting symptoms relevant to differential diagnosis.
    """
    # Concise prompt without few-shot examples — MiMo follows direct instructions
    # better than imitating examples (which it can confuse with the expected output format).
    prompt = (
        "Rewrite these clinical notes as a single short phrase (max 15 words) "
        "containing ONLY the primary symptom, its anatomical location or radiation, "
        "character, and duration. Exclude age, sex, history, comorbidities, "
        "medications, and vital signs. Output the phrase only — no preamble, no quotes, "
        "no explanation.\n\n"
        f"Notes: {notes}\n\n"
        "Phrase:"
    )
    logger.info("Symptom extraction starting: model=%s notes_len=%d", model, len(notes))
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0,
        )
        phrase = resp.choices[0].message.content.strip().strip('"').strip("'").rstrip(".")

        word_count = len(phrase.split())
        if word_count > 25:
            logger.warning(
                "Symptom extraction returned %d words (>25) — likely echoed input. "
                "Truncating to 15 words. Raw: %r",
                word_count, phrase[:120],
            )
            phrase = " ".join(phrase.split()[:15])

        if not phrase:
            logger.warning("Symptom extraction returned empty — falling back to raw notes")
            return notes

        logger.info("Symptom extraction OK: %r → %r (%d words)", notes[:60], phrase, len(phrase.split()))
        return phrase
    except Exception as exc:
        logger.warning("Symptom extraction FAILED (%s) — falling back to raw notes", exc)
        return notes


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

    # Honour STAGE2_LLM_* override for extraction (same fallback as _llm_rerank_ddx).
    # When Google API is quota-exhausted, both rerank and extraction use MiMo.
    _s2_base = os.getenv("STAGE2_LLM_BASE_URL")
    _s2_key = os.getenv("STAGE2_LLM_API_KEY")
    _s2_model = os.getenv("STAGE2_LLM_CHOICE")
    _using_override = bool(_s2_base and _s2_key and _s2_model)

    client = openai.AsyncOpenAI(
        base_url=_s2_base or os.getenv("LLM_BASE_URL"),
        api_key=_s2_key or os.getenv("LLM_API_KEY"),
        max_retries=0,   # extraction has a clean fallback; don't waste 3s on 429 retries
    )
    extraction_model = (
        _s2_model if _using_override
        else os.getenv("SYMPTOM_EXTRACT_MODEL", os.getenv("LLM_CHOICE", "gemini-2.0-flash"))
    )
    query = await _extract_symptom_phrase(case.chief_complaint, client, extraction_model)

    if emit is not None:
        await emit("sub_step", {
            "stage": 2,
            "detail": f"Extracted symptom query: \"{query}\"",
            "badge": "DDx",
        })

    fetch_k = top_k * 2 if rerank else top_k
    raw = await search_ddx(query, top_k=fetch_k)

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
    staging_dict = case.severity_staging if case.severity_staging else {}
    severity_str = ", ".join(f"{k} {v}" for k, v in staging_dict.items()) or "not specified"

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
    queries_per_code: int = 7,
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

    search_tasks = [
        vector_search_tool(VectorSearchInput(
            query=q,
            limit=chunks_per_query,
            document_id_filter=all_doc_ids,
        ))
        for q in queries
    ]
    results_per_query = await asyncio.gather(*search_tasks, return_exceptions=True)

    for q, result in zip(queries, results_per_query):
        if isinstance(result, Exception):
            logger.warning("Query %r failed: %s", q, result)
            continue
        new_chunks = 0
        for chunk in result:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)
                new_chunks += 1
        if emit:
            total = len(result)
            await emit("sub_step", {
                "stage": 4,
                "detail": f'"{q[:60]}{"…" if len(q) > 60 else ""}"',
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


_CURRENT_YEAR = 2026
_CPG_STALE_THRESHOLD_YEARS = 5


# Tiered evidence budgets for Stage 5 synthesis.
# Step 1 still receives whole markdown-header chunks. Keep each retrieved chunk
# intact whenever possible so late-section criteria, tables, and qualifiers remain
# visible to the synthesis LLM.
_CHILD_CHAR_LIMIT = 20_000
_PARENT_CHAR_LIMIT = 60_000
_TOTAL_TOKEN_BUDGET = 50_000
_PROMPT_TOKEN_LIMIT = 180_000
_ENC = None


class PromptOversizeError(RuntimeError):
    """Raised before an oversized synthesis prompt is sent to the LLM."""


def _get_token_encoder():
    global _ENC
    if _ENC is False:
        return None
    if _ENC is None and tiktoken is not None:
        try:
            _ENC = tiktoken.encoding_for_model("gpt-4")
        except Exception as exc:
            logger.warning("tiktoken encoder unavailable; using char proxy: %s", exc)
            _ENC = False
    return None if _ENC is False else _ENC


def _count_tokens(s: str) -> int:
    """Count tokens with tiktoken; fall back to a conservative char proxy."""
    if not s:
        return 0
    encoder = _get_token_encoder()
    if encoder is None:
        return max(1, len(s) // 4)
    return len(encoder.encode(s))


async def _prefetch_parent_content(chunks: list[ChunkResult]) -> None:
    """
    Populate parent_content (and section_content for h3 hits) for every chunk
    that has a parent_chunk_id. Walks the chain up to H1 in at most two hops.

    H2 / h1_leaf hit — one hop:
        chunk.parent_content = H1 text (windowed if > _PARENT_CHAR_LIMIT)

    H3 hit — two hops:
        chunk.section_content = cap-split H2 text (passed whole)
        chunk.parent_content  = H1 text with the H2 span replaced by a gap marker
                                (windowed if still > _PARENT_CHAR_LIMIT after slicing)
    """
    # Collect all direct parent IDs needed for the first hop
    first_hop_ids = {
        c.metadata["parent_chunk_id"]
        for c in chunks
        if c.metadata.get("parent_chunk_id")
    }
    if not first_hop_ids:
        return

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, content, chunk_level, start_char, end_char,
                   parent_chunk_id::text AS grandparent_id, metadata
            FROM chunks
            WHERE id = ANY($1::uuid[])
            """,
            list(first_hop_ids),
        )

    # Build lookup: id → full row dict
    parent_row_by_id: dict[str, dict] = {}
    for r in rows:
        parent_row_by_id[r["id"]] = {
            "content":       r["content"],
            "chunk_level":   r["chunk_level"],
            "start_char":    r["start_char"],
            "end_char":      r["end_char"],
            "grandparent_id": r["grandparent_id"],
            "metadata":      json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r["metadata"] or {}),
        }

    # Collect any grandparent IDs needed for H3 two-hop walk
    grandparent_ids = {
        parent_row_by_id[pid]["grandparent_id"]
        for pid in first_hop_ids
        if pid in parent_row_by_id and parent_row_by_id[pid].get("grandparent_id")
    }

    grandparent_row_by_id: dict[str, dict] = {}
    if grandparent_ids:
        async with db_pool.acquire() as conn:
            gp_rows = await conn.fetch(
                "SELECT id::text, content, chunk_level, start_char, end_char FROM chunks WHERE id = ANY($1::uuid[])",
                list(grandparent_ids),
            )
        for r in gp_rows:
            grandparent_row_by_id[r["id"]] = {
                "content":     r["content"],
                "chunk_level": r["chunk_level"],
                "start_char":  r["start_char"],
                "end_char":    r["end_char"],
            }

    for chunk in chunks:
        pid = chunk.metadata.get("parent_chunk_id")
        if not pid or pid not in parent_row_by_id:
            continue

        p = parent_row_by_id[pid]

        if p["chunk_level"] == "h2" and p.get("grandparent_id"):
            # H3 hit — p is the cap-split H2 intermediate; grandparent is H1
            gp_id = p["grandparent_id"]
            gp = grandparent_row_by_id.get(gp_id)

            # [SECTION] — cap-split H2 passed whole
            chunk.section_content = p["content"]

            if gp:
                h1_text  = gp["content"]
                h2_start = p["start_char"] or 0
                h2_end   = p["end_char"] or h2_start
                h2_title = p["metadata"].get("h2_title", "this section")
                gap      = f"\n\n[… {h2_title} shown above …]\n\n"
                h1_ctx   = h1_text[:h2_start] + gap + h1_text[h2_end:]

                if len(h1_ctx) > _PARENT_CHAR_LIMIT:
                    half         = _PARENT_CHAR_LIMIT // 2
                    window_start = max(0, h2_start - half)
                    window_end   = min(len(h1_ctx), h2_end + half)
                    h1_ctx       = h1_ctx[window_start:window_end]
                    logger.info(
                        "H1 window sliced for h3 chunk %s: [%d:%d] of %d-char H1",
                        chunk.chunk_id, window_start, window_end, len(h1_text),
                    )
                chunk.parent_content = h1_ctx
        else:
            # H2 / h1_leaf hit — p is the H1, one hop
            parent_text = p["content"]
            if len(parent_text) <= _PARENT_CHAR_LIMIT:
                chunk.parent_content = parent_text
            else:
                half         = _PARENT_CHAR_LIMIT // 2
                child_start  = chunk.start_char or 0
                child_end    = chunk.end_char or child_start
                window_start = max(0, child_start - half)
                window_end   = min(len(parent_text), child_end + half)
                chunk.parent_content = parent_text[window_start:window_end]
                logger.info(
                    "Parent window sliced for chunk %s: [%d:%d] of %d-char parent",
                    chunk.chunk_id, window_start, window_end, len(parent_text),
                )


async def _resolve_cross_refs(chunks: list[ChunkResult]) -> list[ChunkResult]:
    """
    Collect cross_refs from each chunk and its parent chain, fetch the best
    matching embedded child from each target file, and return them as extra
    ChunkResult objects to be appended to the evidence pack.

    Chain-aware: reads cross_refs from the hit child AND from its section/parent
    content metadata, so a marker placed on an unembedded cap-split H2 preamble
    still fires when one of its H3 children is the hit.

    Each resolved reference is capped at _CHILD_CHAR_LIMIT to avoid blowing
    the token budget. Duplicates (same chunk_id already in evidence) are skipped.
    """
    existing_ids = {c.chunk_id for c in chunks}
    refs_to_resolve: list[dict] = []

    for chunk in chunks:
        # Collect cross_refs from the hit chunk itself
        for ref in chunk.metadata.get("cross_refs", []):
            if ref.get("target_file"):
                refs_to_resolve.append(ref)
        # Also collect from parent chain metadata stored during prefetch
        # (covers markers that landed on an unembedded cap-split H2 preamble)
        for key in ("cap_split_h2_index",):
            pass  # chain metadata is in DB rows already fetched — read from parent_content metadata below

    if not refs_to_resolve:
        return []

    # Deduplicate by target_file + target_heading
    seen_refs: set[tuple] = set()
    unique_refs: list[dict] = []
    for ref in refs_to_resolve:
        key = (ref.get("target_file", ""), ref.get("target_heading", ""))
        if key not in seen_refs:
            seen_refs.add(key)
            unique_refs.append(ref)

    resolved: list[ChunkResult] = []

    async with db_pool.acquire() as conn:
        for ref in unique_refs:
            target_file    = ref.get("target_file", "")
            target_heading = ref.get("target_heading", "")
            target_kind    = ref.get("target_kind", "h1_section")

            if not target_file:
                continue

            # Find the document matching target_file (partial match on source path)
            doc_row = await conn.fetchrow(
                "SELECT id::text FROM documents WHERE source LIKE $1 LIMIT 1",
                f"%{target_file}%",
            )
            if not doc_row:
                logger.debug("cross_ref: no document found for target_file=%r", target_file)
                continue

            doc_id = doc_row["id"]

            # For h2_section / h3_section — find the specific embedded child by heading match
            if target_kind in ("h2_section", "h3_section") and target_heading:
                row = await conn.fetchrow(
                    """
                    SELECT c.id::text AS chunk_id, c.content, c.metadata,
                           d.title AS document_title, d.source AS document_source
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.document_id = $1::uuid
                      AND c.embedding IS NOT NULL
                      AND (
                          c.metadata->>'h2_title' ILIKE $2
                          OR c.metadata->>'h3_title' ILIKE $2
                          OR c.content ILIKE $3
                      )
                    LIMIT 1
                    """,
                    doc_id,
                    f"%{target_heading}%",
                    f"%{target_heading[:60]}%",
                )
            else:
                # h1_section / appendix / algorithm_flowchart — best embedded child
                # (prefer the first embedded child of the target document)
                row = await conn.fetchrow(
                    """
                    SELECT c.id::text AS chunk_id, c.content, c.metadata,
                           d.title AS document_title, d.source AS document_source
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.document_id = $1::uuid
                      AND c.embedding IS NOT NULL
                    ORDER BY c.chunk_index
                    LIMIT 1
                    """,
                    doc_id,
                )

            if not row:
                logger.debug(
                    "cross_ref: no embedded chunk found for target_file=%r heading=%r",
                    target_file, target_heading,
                )
                continue

            chunk_id = row["chunk_id"]
            if chunk_id in existing_ids:
                continue  # already in evidence pack

            existing_ids.add(chunk_id)
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
            content = row["content"][:_CHILD_CHAR_LIMIT]

            resolved.append(ChunkResult(
                chunk_id=chunk_id,
                document_id=doc_id,
                content=content,
                score=0.0,
                metadata={**meta, "_cross_ref_source": target_file},
                document_title=row["document_title"],
                document_source=row["document_source"],
            ))
            logger.info(
                "cross_ref resolved: %r → chunk %s (%d chars)",
                target_file, chunk_id, len(content),
            )

    return resolved


def build_parent_context(chunk: ChunkResult, include_parent: bool = True) -> str:
    """
    Return formatted evidence text for a chunk.

    H3 hit  → [CHILD] + [SECTION] + [PARENT]  (3 tiers, no duplicated text)
    H2 hit  → [CHILD] + [PARENT]               (2 tiers)
    No parent → child only (capped at _PARENT_CHAR_LIMIT)

    If include_parent is False (duplicate parent suppression), emit child only.
    """
    if not include_parent or chunk.parent_content is None:
        return chunk.content[:_PARENT_CHAR_LIMIT]

    child_block = f"[CHILD]\n{chunk.content}"

    if chunk.section_content is not None:
        # H3 hit — 3-tier, H1 already has the H2 span replaced by a gap marker
        section_block = f"[SECTION]\n{chunk.section_content}"
        parent_block  = f"[PARENT]\n{chunk.parent_content}"
        return f"{child_block}\n\n{section_block}\n\n{parent_block}"

    parent_block = f"[PARENT]\n{chunk.parent_content}"
    return f"{child_block}\n\n{parent_block}"


def _format_evidence(chunks: list[ChunkResult]) -> str:
    lines = []
    running_tokens = 0
    seen_documents: set[str] = set()
    for i, c in enumerate(chunks, 1):
        if running_tokens >= _TOTAL_TOKEN_BUDGET:
            break
        section = c.metadata.get("section_number", "")
        cpg = c.document_title or c.document_source
        # CPG currency warning — flag stale evidence so the synthesis LLM can
        # de-emphasise it or surface it in unresolved_questions.
        published_year = c.metadata.get("published_year")
        age_warning = ""
        if published_year:
            try:
                year_int = int(published_year)
                age = _CURRENT_YEAR - year_int
                if age > _CPG_STALE_THRESHOLD_YEARS:
                    age_warning = f"  ⚠ Published {year_int} ({age}y old — verify against current guidelines)"
            except (TypeError, ValueError):
                pass
        document_key = c.metadata.get("parent_chunk_id") or c.document_id
        include_parent = document_key not in seen_documents
        if include_parent:
            seen_documents.add(document_key)
        else:
            logger.debug(
                "Skipping duplicate parent context for document %s via chunk %s",
                document_key,
                c.chunk_id,
            )

        content = build_parent_context(c, include_parent=include_parent)
        content_tokens = _count_tokens(content)
        if len(content) > _CHILD_CHAR_LIMIT and running_tokens + content_tokens > _TOTAL_TOKEN_BUDGET:
            logger.info(
                "Skipping oversized child %s (%d chars, budget exhausted)",
                c.chunk_id,
                len(content),
            )
            continue
        if running_tokens + content_tokens > _TOTAL_TOKEN_BUDGET:
            logger.info(
                "Skipping chunk %s (%d tokens would exceed synthesis evidence budget)",
                c.chunk_id,
                content_tokens,
            )
            continue
        entry = f"[{i}] {cpg} §{section}{age_warning}\n{content}"
        lines.append(entry)
        running_tokens += content_tokens
    return "\n\n".join(lines)


def _guard_prompt_size(system_prompt: str, user_prompt: str) -> None:
    prompt_tokens = _count_tokens(system_prompt) + _count_tokens(user_prompt)
    if prompt_tokens > _PROMPT_TOKEN_LIMIT:
        logger.error(
            "Stage 5 prompt assembled to %d tokens; refusing send",
            prompt_tokens,
        )
        raise PromptOversizeError(
            f"Stage 5 prompt assembled to {prompt_tokens} tokens; "
            f"limit is {_PROMPT_TOKEN_LIMIT}"
        )


async def stage_5_synthesize(
    case: PatientCase,
    ddx: list[DDxResult],
    _cpgs: list[CPGDocRef],
    evidence: list[ChunkResult],
    flags: list[ClinicalFlag] | None = None,
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

    await _prefetch_parent_content(evidence)
    cross_ref_chunks = await _resolve_cross_refs(evidence)
    if cross_ref_chunks:
        logger.info("cross_ref: appending %d referenced evidence chunks", len(cross_ref_chunks))
        evidence = evidence + cross_ref_chunks
    evidence_text = _format_evidence(evidence)

    flags_block = format_flags_for_prompt(flags or [])
    if flags:
        logger.info("stage_5_synthesize: injecting %d KG flags into prompt", len(flags))

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

{flags_block}
Retrieved Evidence ({len(evidence)} chunks):
{evidence_text}

Produce a TreatmentPlan JSON object matching this schema:
{json.dumps(SYNTHESIS_SCHEMA, indent=2)}"""

    _guard_prompt_size(SYNTHESIS_SYSTEM, user_prompt)

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
