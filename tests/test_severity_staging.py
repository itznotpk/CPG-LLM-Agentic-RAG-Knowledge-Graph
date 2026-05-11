"""
Unit tests for Gap 4 — severity staging fields in PatientCase and query injection.
Run with: pytest tests/test_severity_staging.py -v --no-cov
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from agent.models import PatientCase, StagedComorbidity
from agent.routing import CPGDocRef
from agent.clinical_stages import DDxResult, _generate_retrieval_queries


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

def test_patientcase_severity_staging_optional():
    """PatientCase constructs without staging; field defaults to empty dict."""
    case = PatientCase(chief_complaint="x")
    assert case.severity_staging == {}
    assert case.staged_comorbidities == []


def test_patientcase_severity_staging_populated():
    """severity_staging round-trips through model_dump() and back."""
    staging = {"NYHA": "III", "CKD_stage": "3b"}
    case = PatientCase(chief_complaint="x", severity_staging=staging)
    dumped = case.model_dump()
    rehydrated = PatientCase(**dumped)
    assert rehydrated.severity_staging == staging


def test_patientcase_staged_comorbidity_populated():
    """staged_comorbidities accepts structured entries and icd_code is preserved."""
    case = PatientCase(
        chief_complaint="x",
        staged_comorbidities=[{"icd_code": "5A11", "label": "T2DM", "severity": None}],
    )
    assert len(case.staged_comorbidities) == 1
    assert case.staged_comorbidities[0].icd_code == "5A11"
    assert case.staged_comorbidities[0].label == "T2DM"


def test_patientcase_staged_comorbidity_label_required():
    """StagedComorbidity without label raises ValidationError."""
    with pytest.raises(ValidationError):
        StagedComorbidity()


# ---------------------------------------------------------------------------
# Query generation tests
# ---------------------------------------------------------------------------

def _make_ddx() -> list[DDxResult]:
    return [DDxResult(code="BA00", title="Essential hypertension", similarity=0.85)]


def _make_cpgs() -> list[CPGDocRef]:
    return [CPGDocRef(
        cpg_name="CPG HTN",
        document_id="doc1",
        document_ids=["doc1"],
        title="CPG HTN Treatment",
        match_type="exact",
        score=1.0,
        matched_scope="BA00",
    )]


@pytest.mark.asyncio
async def test_query_generation_injects_staging():
    """When severity_staging is populated, the prompt passed to the LLM contains the staging string."""
    case = PatientCase(
        chief_complaint="hypertension with HF",
        severity_staging={"NYHA": "III", "LVEF": "35%"},
    )

    captured_messages = []

    async def fake_create(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(
            ["query1", "query2", "query3", "query4", "query5"]
        )
        return mock_resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create

    with patch("agent.clinical_stages.openai.AsyncOpenAI", return_value=mock_client):
        await _generate_retrieval_queries(case, _make_ddx(), _make_cpgs(), n=5)

    full_content = " ".join(
        m["content"] for m in captured_messages if isinstance(m.get("content"), str)
    )
    assert "NYHA III" in full_content, f"Expected 'NYHA III' in prompt. Got: {full_content[:400]}"


@pytest.mark.asyncio
async def test_query_generation_omits_staging_when_empty():
    """When severity_staging is empty, the prompt contains 'not specified'."""
    case = PatientCase(
        chief_complaint="hypertension",
        severity_staging={},
    )

    captured_messages = []

    async def fake_create(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(
            ["query1", "query2", "query3", "query4", "query5"]
        )
        return mock_resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create

    with patch("agent.clinical_stages.openai.AsyncOpenAI", return_value=mock_client):
        await _generate_retrieval_queries(case, _make_ddx(), _make_cpgs(), n=5)

    full_content = " ".join(
        m["content"] for m in captured_messages if isinstance(m.get("content"), str)
    )
    assert "not specified" in full_content, (
        f"Expected 'not specified' for empty staging. Got: {full_content[:400]}"
    )
