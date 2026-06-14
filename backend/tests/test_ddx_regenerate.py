"""
Step-2 DDx regeneration — exclusion + feedback steering.

Covers the three load-bearing pieces of the "Regenerate differentials" feature:
  1. ClinicalPlanRequest accepts the optional regen_feedback / exclude_codes fields.
  2. stage_2_ddx drops excluded codes from the candidate pool (the bare-minimum
     guarantee: a re-run never reproduces the prior top-5).
  3. _llm_rerank_ddx injects the clinician feedback block into the rerank prompt.

All fully mocked — no real LLM, no real DB, no real embeddings.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent.clinical_stages as clinical_stages
from agent.clinical_stages import stage_2_ddx, _llm_rerank_ddx, DDxResult
from agent.models import PatientCase
from agent.api import ClinicalPlanRequest


@pytest.fixture(autouse=True)
def _clear_phrase_cache():
    clinical_stages._PHRASE_CACHE.clear()
    yield
    clinical_stages._PHRASE_CACHE.clear()


# ---------------------------------------------------------------------------
# 1. Request model
# ---------------------------------------------------------------------------

def test_request_defaults_are_backward_compatible():
    req = ClinicalPlanRequest(case=PatientCase(chief_complaint="chest pain"))
    assert req.exclude_codes == []
    assert req.regen_feedback is None


def test_request_accepts_regeneration_fields():
    req = ClinicalPlanRequest(
        case=PatientCase(chief_complaint="chest pain"),
        exclude_codes=["BA41.1", "BC81.3"],
        regen_feedback="consider endocrine causes",
    )
    assert req.exclude_codes == ["BA41.1", "BC81.3"]
    assert req.regen_feedback == "consider endocrine causes"


# ---------------------------------------------------------------------------
# 2. stage_2_ddx exclusion filter
# ---------------------------------------------------------------------------

def _pool_rows(codes):
    return [
        {"code": c, "title": f"Condition {c}", "similarity": 0.9 - i * 0.05}
        for i, c in enumerate(codes)
    ]


@pytest.mark.asyncio
async def test_stage_2_ddx_excludes_prior_codes():
    case = PatientCase(chief_complaint="chest pain")
    rows = _pool_rows(["A", "B", "C", "D", "E"])

    with patch("ddx.search_ddx.search_ddx", new=AsyncMock(return_value=rows)), \
         patch.object(clinical_stages, "_extract_symptom_phrase", new=AsyncMock(return_value=("chest pain", False))), \
         patch.object(clinical_stages, "_generate_condition_hypotheses", new=AsyncMock(return_value=[])), \
         patch.object(clinical_stages, "_extract_cc_icd_hints", new=AsyncMock(return_value=[])), \
         patch.object(clinical_stages, "_regex_disease_hints", new=AsyncMock(return_value=[])), \
         patch.object(clinical_stages, "_redflag_vitals_hints", new=MagicMock(return_value=[])), \
         patch.object(clinical_stages, "_make_openai_client", new=MagicMock(return_value=MagicMock())):
        result = await stage_2_ddx(
            case, top_k=3, rerank=False, exclude_codes=["A", "B"],
        )

    codes = [r.code for r in result]
    assert "A" not in codes and "B" not in codes
    assert codes == ["C", "D", "E"]


@pytest.mark.asyncio
async def test_stage_2_ddx_returns_empty_when_pool_exhausted():
    case = PatientCase(chief_complaint="chest pain")
    rows = _pool_rows(["A", "B"])

    with patch("ddx.search_ddx.search_ddx", new=AsyncMock(return_value=rows)), \
         patch.object(clinical_stages, "_extract_symptom_phrase", new=AsyncMock(return_value=("chest pain", False))), \
         patch.object(clinical_stages, "_generate_condition_hypotheses", new=AsyncMock(return_value=[])), \
         patch.object(clinical_stages, "_extract_cc_icd_hints", new=AsyncMock(return_value=[])), \
         patch.object(clinical_stages, "_regex_disease_hints", new=AsyncMock(return_value=[])), \
         patch.object(clinical_stages, "_redflag_vitals_hints", new=MagicMock(return_value=[])), \
         patch.object(clinical_stages, "_make_openai_client", new=MagicMock(return_value=MagicMock())):
        result = await stage_2_ddx(
            case, top_k=3, rerank=False, exclude_codes=["A", "B"],
        )

    assert result == []


# ---------------------------------------------------------------------------
# 3. _llm_rerank_ddx feedback injection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rerank_injects_clinician_feedback_into_prompt():
    case = PatientCase(chief_complaint="chest pain")
    candidates = [DDxResult(code="C", title="Condition C", similarity=0.5)]

    captured = {}

    async def _fake_create(*args, **kwargs):
        captured["messages"] = kwargs.get("messages")
        msg = MagicMock()
        msg.content = '{"ranking":[{"code":"C","confidence":0.8,"reasoning":"fits"}]}'
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    client = MagicMock()
    client.chat.completions.create = _fake_create

    with patch.object(clinical_stages, "_make_openai_client", new=MagicMock(return_value=client)):
        await _llm_rerank_ddx(case, candidates, regen_feedback="consider endocrine causes")

    user_msg = next(m["content"] for m in captured["messages"] if m["role"] == "user")
    assert "CLINICIAN REGENERATION FEEDBACK" in user_msg
    assert "consider endocrine causes" in user_msg


@pytest.mark.asyncio
async def test_rerank_omits_feedback_block_when_absent():
    case = PatientCase(chief_complaint="chest pain")
    candidates = [DDxResult(code="C", title="Condition C", similarity=0.5)]

    captured = {}

    async def _fake_create(*args, **kwargs):
        captured["messages"] = kwargs.get("messages")
        msg = MagicMock()
        msg.content = '{"ranking":[{"code":"C","confidence":0.8,"reasoning":"fits"}]}'
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    client = MagicMock()
    client.chat.completions.create = _fake_create

    with patch.object(clinical_stages, "_make_openai_client", new=MagicMock(return_value=client)):
        await _llm_rerank_ddx(case, candidates, regen_feedback=None)

    user_msg = next(m["content"] for m in captured["messages"] if m["role"] == "user")
    assert "CLINICIAN REGENERATION FEEDBACK" not in user_msg
