"""
Tests for agent/clinical_stages.py — all four pipeline stages.

All tests are fully mocked — no real DB, no real LLM, no real embeddings.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.models import PatientCase, ChunkResult, TreatmentPlan
from agent.routing import CPGDocRef
from agent.clinical_stages import (
    DDxResult,
    DDX_RERANK_MODEL,
    PromptOversizeError,
    _build_symptom_text,
    _generate_retrieval_queries,
    _format_evidence,
    _llm_rerank_ddx,
    stage_2_ddx,
    stage_3_route,
    stage_4_retrieve,
    stage_5_synthesize,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MOCK_DDX_RAW = [
    {"code": "BC81.3", "title": "Atrial fibrillation", "similarity": 0.91,
     "inclusion_match": True, "matched_term": "palpitation", "reasoning": ["Vector similarity 0.910"]},
    {"code": "BC81.1", "title": "Paroxysmal atrial fibrillation", "similarity": 0.82,
     "inclusion_match": False, "matched_term": None, "reasoning": []},
    {"code": "BA00",   "title": "Essential hypertension", "similarity": 0.74,
     "inclusion_match": False, "matched_term": None, "reasoning": []},
    {"code": "MG22",   "title": "Anxiety disorder", "similarity": 0.61,
     "inclusion_match": False, "matched_term": None, "reasoning": []},
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_case() -> PatientCase:
    return PatientCase(
        chief_complaint="palpitations, irregular pulse",
        age=68,
        sex="M",
        history="10-year hypertension",
        comorbidities=["hypertension"],
        vitals={"hr": 110.0, "sbp": 145.0},
    )


def _make_case(**kwargs) -> PatientCase:
    defaults = dict(
        chief_complaint="palpitations, irregular pulse",
        age=68,
        sex="M",
        history="10-year hypertension",
        comorbidities=["hypertension", "diabetes"],
        vitals={"sbp": 145.0, "hr": 112.0},
    )
    defaults.update(kwargs)
    return PatientCase(**defaults)


def _make_ddx(code: str = "BC81.3", title: str = "Atrial fibrillation") -> DDxResult:
    return DDxResult(code=code, title=title, similarity=0.88)


def _make_cpg(cpg_name: str = "AF CPG", doc_ids: list[str] | None = None) -> CPGDocRef:
    ids = doc_ids or ["doc-1", "doc-2"]
    return CPGDocRef(
        cpg_name=cpg_name,
        document_id=ids[0],
        document_ids=ids,
        title=f"{cpg_name} section",
        match_type="exact",
        score=1.0,
        matched_scope="BC81.3",
    )


def _make_chunk(chunk_id: str = "c1", doc_title: str = "AF CPG", score: float = 0.9, section: str = "4.2") -> ChunkResult:
    return ChunkResult(
        chunk_id=chunk_id,
        document_id="doc-1",
        content="Rate control is recommended for most patients.",
        score=score,
        metadata={"section_number": section},
        document_title=doc_title,
        document_source="http://example.com",
    )


def _make_valid_plan_dict(icd_primary: str = "BC81.3") -> dict:
    return {
        "icd_primary": icd_primary,
        "icd_alternates": ["BC81"],
        "recommendations": [
            {
                "intervention": "Rate control with beta-blocker",
                "type": "pharmacological",
                "evidence_grade": "Grade A, Level I",
                "cpg_source": "AF CPG §4.2",
                "rationale": "Reduces ventricular rate in AF",
                "contraindications_checked": ["severe bradycardia"],
            }
        ],
        "monitoring": [
            {"parameter": "heart rate", "schedule": "each visit", "target": "controlled"},
            {"parameter": "blood pressure", "schedule": "each visit", "target": "<140/90 mmHg"},
        ],
        "red_flags": ["syncope", "haemodynamic instability"],
        "confidence": 0.85,
        "unresolved_questions": [],
    }


# ---------------------------------------------------------------------------
# Stage 2 — DDx
# ---------------------------------------------------------------------------

def test_stage2_builds_symptom_text():
    case = _make_case()
    text = _build_symptom_text(case)

    assert "palpitations, irregular pulse" in text
    assert "10-year hypertension" in text
    assert "hypertension" in text
    assert "sbp=145.0" in text or "sbp" in text


def test_stage2_builds_symptom_text_minimal():
    """Chief complaint only — no optional fields."""
    case = PatientCase(chief_complaint="chest pain")
    text = _build_symptom_text(case)
    assert text == "chest pain"


@pytest.mark.asyncio
async def test_stage2_calls_search_ddx():
    """stage_2_ddx calls search_ddx with the symptom text and returns DDxResult list."""
    case = _make_case()
    raw_results = [
        {"code": "BC81.3", "title": "Atrial fibrillation", "similarity": 0.88,
         "inclusion_match": False, "matched_term": None, "reasoning": []},
    ]

    # Mock extraction so the test is deterministic and never hits the LLM
    # (extraction now succeeds and may rephrase/recapitalise the notes).
    with patch("ddx.search_ddx.search_ddx", new=AsyncMock(return_value=raw_results)) as mock_ddx, \
         patch("agent.clinical_stages._extract_symptom_phrase",
               new=AsyncMock(return_value=("palpitations, irregular pulse", False))), \
         patch("agent.clinical_stages._generate_condition_hypotheses",
               new=AsyncMock(return_value=[])):
        result = await stage_2_ddx(case, top_k=5, rerank=False)

    mock_ddx.assert_awaited_once()
    symptom_arg = mock_ddx.call_args[0][0]
    assert "palpitations" in symptom_arg
    assert len(result) == 1
    assert isinstance(result[0], DDxResult)
    assert result[0].code == "BC81.3"



@pytest.mark.asyncio
async def test_stage2_handles_empty_ddx():
    case = _make_case()

    with patch("ddx.search_ddx.search_ddx", new=AsyncMock(return_value=[])), \
         patch("agent.clinical_stages._extract_symptom_phrase",
               new=AsyncMock(return_value=("palpitations", False))), \
         patch("agent.clinical_stages._generate_condition_hypotheses",
               new=AsyncMock(return_value=[])):
        result = await stage_2_ddx(case, rerank=False)

    assert result == []


# ---------------------------------------------------------------------------
# Stage 3 — Route
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage3_routes_top2_codes():
    """Only the top 2 DDx codes should be routed."""
    ddx = [_make_ddx(code=f"CODE{i}", title=f"Cond {i}") for i in range(3)]

    call_log: list[str] = []

    async def mock_route(code, top_k=3, procedure_tags=None):
        call_log.append(code)
        return [_make_cpg(cpg_name=f"CPG_{code}")]

    with patch("agent.clinical_stages.route_icd_to_cpgs", side_effect=mock_route):
        result = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=5)

    assert "CODE0" in call_log
    assert "CODE1" in call_log
    assert "CODE2" not in call_log


@pytest.mark.asyncio
async def test_stage3_deduplicates_cpgs():
    """Two DDx codes both routing to the same CPG → only one entry returned."""
    ddx = [_make_ddx("CODE0"), _make_ddx("CODE1")]

    async def mock_route(code, top_k=3, procedure_tags=None):
        return [_make_cpg(cpg_name="Shared CPG")]  # same CPG for both codes

    with patch("agent.clinical_stages.route_icd_to_cpgs", side_effect=mock_route):
        result = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=5)

    assert len(result) == 1
    assert result[0].cpg_name == "Shared CPG"


@pytest.mark.asyncio
async def test_stage3_caps_at_top_k_cpgs():
    """Routing returns 5 unique CPGs → only top_k_cpgs=3 returned."""
    ddx = [_make_ddx("CODE0"), _make_ddx("CODE1")]

    call_count = 0

    async def mock_route(code, top_k=3, procedure_tags=None):
        nonlocal call_count
        # Return 3 unique CPGs per call; CODE1's CPGs are different names
        offset = call_count * 3
        call_count += 1
        return [_make_cpg(cpg_name=f"CPG {offset + i}") for i in range(3)]

    with patch("agent.clinical_stages.route_icd_to_cpgs", side_effect=mock_route):
        result = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3)

    assert len(result) == 3


# ---------------------------------------------------------------------------
# Stage 4 — Retrieve
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage4_generates_queries():
    """_generate_retrieval_queries returns a list of strings."""
    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [_make_cpg()]

    mock_message = MagicMock()
    mock_message.content = '["query 1", "query 2", "query 3"]'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = mock_client
        queries = await _generate_retrieval_queries(case, ddx, cpgs, n=3)

    assert isinstance(queries, list)
    assert len(queries) == 3
    assert all(isinstance(q, str) for q in queries)


@pytest.mark.asyncio
async def test_stage4_scoped_search():
    """vector_search_tool must be called with document_id_filter containing all CPG doc IDs."""
    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [
        _make_cpg("CPG A", ["uuid-1", "uuid-2"]),
        _make_cpg("CPG B", ["uuid-3"]),
    ]
    expected_ids = ["uuid-1", "uuid-2", "uuid-3"]

    captured_filters: list[list[str]] = []

    async def mock_vector_search(input_data):
        captured_filters.append(input_data.document_id_filter)
        return [_make_chunk()]

    with patch("agent.clinical_stages._generate_retrieval_queries",
               new=AsyncMock(return_value=["query 1", "query 2"])):
        with patch("agent.clinical_stages.vector_search_tool", side_effect=mock_vector_search):
            await stage_4_retrieve(case, ddx, cpgs)

    assert all(f == expected_ids for f in captured_filters), \
        f"Expected filter {expected_ids} for all queries, got {captured_filters}"


@pytest.mark.asyncio
async def test_stage4_deduplicates_chunks():
    """Same chunk_id returned by two queries → appears only once in output."""
    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [_make_cpg()]

    dup_chunk = _make_chunk(chunk_id="dup-id")

    call_n = 0

    async def mock_vector_search(input_data):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return [dup_chunk]
        return [dup_chunk, _make_chunk(chunk_id="unique-id")]

    with patch("agent.clinical_stages._generate_retrieval_queries",
               new=AsyncMock(return_value=["q1", "q2"])):
        with patch("agent.clinical_stages.vector_search_tool", side_effect=mock_vector_search):
            result = await stage_4_retrieve(case, ddx, cpgs)

    chunk_ids = [c.chunk_id for c in result]
    assert chunk_ids.count("dup-id") == 1


@pytest.mark.asyncio
async def test_stage4_caps_at_20_chunks():
    """Even with many queries returning chunks, output is capped at 20."""
    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [_make_cpg()]

    # 4 queries × 6 unique chunks each = 24 → must cap at 20
    queries = [f"q{i}" for i in range(4)]
    chunk_counter = 0

    async def mock_vector_search(input_data):
        nonlocal chunk_counter
        chunks = []
        for _ in range(6):
            chunks.append(_make_chunk(chunk_id=f"c{chunk_counter}"))
            chunk_counter += 1
        return chunks

    with patch("agent.clinical_stages._generate_retrieval_queries",
               new=AsyncMock(return_value=queries)):
        with patch("agent.clinical_stages.vector_search_tool", side_effect=mock_vector_search):
            result = await stage_4_retrieve(case, ddx, cpgs, queries_per_code=4, chunks_per_query=6)

    assert len(result) <= 20


@pytest.mark.asyncio
async def test_stage4_query_gen_llm_call():
    """LLM prompt for query gen must mention CPG names and ICD codes."""
    case = _make_case()
    ddx = [_make_ddx("BC81.3", "Atrial fibrillation")]
    cpgs = [_make_cpg("AF Management CPG")]

    captured_prompt: list[str] = []

    mock_message = MagicMock()
    mock_message.content = '["q1"]'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    def capture_call(**kwargs):
        for msg in kwargs.get("messages", []):
            captured_prompt.append(msg.get("content", ""))
        return mock_resp

    mock_client.chat.completions.create = AsyncMock(side_effect=lambda **kw: (
        captured_prompt.extend(m.get("content", "") for m in kw.get("messages", [])) or mock_resp
    ))

    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = mock_client
        await _generate_retrieval_queries(case, ddx, cpgs, n=1)

    full_prompt = " ".join(captured_prompt)
    assert "BC81.3" in full_prompt
    assert "AF Management CPG" in full_prompt


# ---------------------------------------------------------------------------
# Stage 5 — Synthesize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage5_returns_treatment_plan():
    """Valid LLM JSON response → returns a TreatmentPlan instance."""
    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [_make_cpg()]
    evidence = [_make_chunk()]

    plan_dict = _make_valid_plan_dict()

    mock_message = MagicMock()
    mock_message.content = json.dumps(plan_dict)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = mock_client
        result = await stage_5_synthesize(case, ddx, cpgs, evidence)

    assert isinstance(result, TreatmentPlan)
    assert result.icd_primary == "BC81.3"


@pytest.mark.asyncio
async def test_stage5_sets_icd_from_ddx():
    """When LLM omits icd_primary, the stage fills it from ddx[0].code."""
    case = _make_case()
    ddx = [_make_ddx("BC81.3")]
    cpgs = [_make_cpg()]
    evidence = [_make_chunk()]

    plan_dict = _make_valid_plan_dict()
    del plan_dict["icd_primary"]  # LLM omits it

    mock_message = MagicMock()
    mock_message.content = json.dumps(plan_dict)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = mock_client
        result = await stage_5_synthesize(case, ddx, cpgs, evidence)

    assert result.icd_primary == "BC81.3"


@pytest.mark.asyncio
async def test_stage5_validation_error_raises_runtime():
    """Invalid JSON from LLM (missing required 'recommendations') → RuntimeError, not ValidationError."""
    from pydantic import ValidationError

    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [_make_cpg()]
    evidence = []

    bad_dict = {
        "icd_primary": "BC81.3",
        "icd_alternates": [],
        "confidence": 0.5,
        # 'recommendations' missing — TreatmentPlan requires at least one
    }

    mock_message = MagicMock()
    mock_message.content = json.dumps(bad_dict)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = mock_client
        with pytest.raises(RuntimeError, match="TreatmentPlan validation failed"):
            await stage_5_synthesize(case, ddx, cpgs, evidence)


@pytest.mark.asyncio
async def test_stage5_formats_evidence_with_section():
    """Chunk with metadata section_number=4 must appear as §4 in evidence text."""
    chunk = _make_chunk(section="4")
    evidence_text = _format_evidence([chunk])
    assert "§4" in evidence_text


@pytest.mark.asyncio
async def test_stage5_evidence_keeps_late_chunk_content():
    """Long retrieved chunks should not be cut at the old 4k character ceiling."""
    late_marker = "DUKE_CRITERIA_LATE_SECTION"
    chunk = _make_chunk()
    chunk.content = "a" * 4500 + late_marker

    evidence_text = _format_evidence([chunk])

    assert late_marker in evidence_text


@pytest.mark.asyncio
async def test_stage5_dedupes_parent_context_for_same_document():
    """Repeated chunks from one document should not inject parent context twice."""
    first = _make_chunk(chunk_id="c1")
    second = _make_chunk(chunk_id="c2")

    with patch("agent.clinical_stages.build_parent_context", side_effect=lambda c, include_parent=True: c.content) as mock_build:
        _format_evidence([first, second])

    assert mock_build.call_args_list[0].kwargs["include_parent"] is True
    assert mock_build.call_args_list[1].kwargs["include_parent"] is False


@pytest.mark.asyncio
async def test_stage5_prompt_guard_blocks_oversized_prompt():
    """Oversized Stage 5 prompts should fail before the LLM call."""
    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [_make_cpg()]
    evidence = [_make_chunk()]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()

    with patch("agent.clinical_stages.openai") as mock_openai, \
         patch("agent.clinical_stages._count_tokens", return_value=200_000):
        mock_openai.AsyncOpenAI.return_value = mock_client
        with pytest.raises(PromptOversizeError):
            await stage_5_synthesize(case, ddx, cpgs, evidence)

    mock_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_stage5_empty_evidence_populates_unresolved():
    """Zero evidence chunks — LLM mock returns plan with unresolved_questions populated."""
    case = _make_case()
    ddx = [_make_ddx()]
    cpgs = [_make_cpg()]
    evidence = []  # no evidence

    plan_dict = _make_valid_plan_dict()
    plan_dict["unresolved_questions"] = ["No CPG evidence found for this case; recommend specialist review."]

    mock_message = MagicMock()
    mock_message.content = json.dumps(plan_dict)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = mock_client
        result = await stage_5_synthesize(case, ddx, cpgs, evidence)

    assert len(result.unresolved_questions) > 0


# ---------------------------------------------------------------------------
# Stage 2 — DDx re-rank tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage2_rerank_called_by_default(minimal_case):
    """rerank=True by default → _llm_rerank_ddx is called."""
    with patch("ddx.search_ddx.search_ddx", new=AsyncMock(return_value=MOCK_DDX_RAW[:4])), \
         patch("agent.clinical_stages._extract_symptom_phrase", new=AsyncMock(return_value=("palpitations", False))), \
         patch("agent.clinical_stages._generate_condition_hypotheses", new=AsyncMock(return_value=[])), \
         patch("agent.clinical_stages._llm_rerank_ddx", new_callable=AsyncMock) as mock_rerank:
        mock_rerank.return_value = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
        result = await stage_2_ddx(minimal_case, top_k=1)
        mock_rerank.assert_called_once()
        assert result[0].code == "BC81.3"


@pytest.mark.asyncio
async def test_stage2_rerank_skipped_when_false(minimal_case):
    """rerank=False → _llm_rerank_ddx is never called."""
    with patch("ddx.search_ddx.search_ddx", new=AsyncMock(return_value=MOCK_DDX_RAW[:2])), \
         patch("agent.clinical_stages._extract_symptom_phrase", new=AsyncMock(return_value=("palpitations", False))), \
         patch("agent.clinical_stages._generate_condition_hypotheses", new=AsyncMock(return_value=[])), \
         patch("agent.clinical_stages._llm_rerank_ddx", new_callable=AsyncMock) as mock_rerank:
        await stage_2_ddx(minimal_case, top_k=2, rerank=False)
        mock_rerank.assert_not_called()


@pytest.mark.asyncio
async def test_rerank_uses_configured_model(minimal_case):
    """_llm_rerank_ddx calls the resolved rerank model (STAGE2 override → mimo, else DDX_RERANK_MODEL)."""
    candidates = [
        DDxResult(code="BC81.3", title="AF",  similarity=0.91),
        DDxResult(code="BA00",   title="HTN", similarity=0.72),
    ]
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "fits best"},
        {"code": "BA00",   "confidence": 0.45, "reasoning": "comorbid"},
    ])
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        # Model resolution mirrors clinical_stages: STAGE2 override (e.g. mimo) wins, else DDX_RERANK_MODEL
        expected_model = os.getenv("STAGE2_LLM_CHOICE") or DDX_RERANK_MODEL
        assert call_kwargs["model"] == expected_model
        assert call_kwargs["temperature"] == 1
        # Bumped 4000 → 8000 so mimo's reasoning + JSON output both fit; at 4000 the
        # reasoning model frequently exhausted the budget and returned empty content.
        assert call_kwargs["max_tokens"] == 8000


@pytest.mark.asyncio
async def test_rerank_fallback_on_llm_failure(minimal_case):
    """If LLM call raises, original candidate order is preserved."""
    candidates = [
        DDxResult(code="BC81.3", title="AF",  similarity=0.91),
        DDxResult(code="BA00",   title="HTN", similarity=0.72),
    ]
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))

        result = await _llm_rerank_ddx(minimal_case, candidates)
        assert [r.code for r in result] == ["BC81.3", "BA00"]  # original order


@pytest.mark.asyncio
async def test_rerank_appends_llm_reasoning(minimal_case):
    """LLM reasoning string is appended to DDxResult.reasoning list."""
    candidates = [
        DDxResult(code="BC81.3", title="AF", similarity=0.91,
                  reasoning=["Vector similarity 0.910"]),
    ]
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "68M fits AF profile"},
    ])
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates)
        assert any("LLM:" in r for r in result[0].reasoning)
        assert any("Vector" in r for r in result[0].reasoning)


@pytest.mark.asyncio
async def test_rerank_drops_no_candidates(minimal_case):
    """If LLM response omits a candidate, it is appended at end — no data loss."""
    candidates = [
        DDxResult(code="BC81.3", title="AF",  similarity=0.91),
        DDxResult(code="BA00",   title="HTN", similarity=0.72),
    ]
    mock_resp = MagicMock()
    # LLM only returns one of the two
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "top pick"},
    ])
    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates)
        codes = [r.code for r in result]
        assert "BC81.3" in codes
        assert "BA00" in codes   # appended, not lost
        assert len(result) == 2
