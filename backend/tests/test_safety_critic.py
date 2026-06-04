"""
Tests for the Safety Critic Agent.

Run with: pytest tests/test_safety_critic.py -v --no-cov
"""
from __future__ import annotations
import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from agent.models import (
    PatientCase,
    TreatmentPlan,
    Recommendation,
    SafetyFlag,
    SafetyReport,
)
from agent.safety_critic import run_safety_critic, SAFETY_CRITIC_SYSTEM


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_case(**kwargs) -> PatientCase:
    defaults = dict(
        chief_complaint="chest pain",
        age=65,
        sex="M",
        comorbidities=["hypertension", "chronic stable angina"],
        current_medications=["verapamil 240 mg OD"],
        allergies=[],
        vitals={"sbp": 140, "dbp": 90, "hr": 72},
    )
    defaults.update(kwargs)
    return PatientCase(**defaults)


def _make_plan(*interventions: str) -> TreatmentPlan:
    recs = [
        Recommendation(
            intervention=iv,
            type="pharmacological",
            action="start",
            cpg_source="CPG Test §1",
            rationale="Test rationale",
        )
        for iv in interventions
    ]
    return TreatmentPlan(
        icd_primary="BA80",
        summary="Test plan",
        recommendations=recs,
        confidence=0.8,
    )


def _mock_client(json_payload: dict):
    """Return an AsyncOpenAI client mock whose .chat.completions.create returns json_payload."""
    choice = MagicMock()
    choice.message.content = json.dumps(json_payload)
    response = MagicMock()
    response.choices = [choice]

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_safety_flag_validates():
    flag = SafetyFlag(
        title="verapamil + metoprolol - AV-nodal depression",
        severity="MAJOR",
        recommendation_index=0,
        flag_type="drug_interaction",
        detail="Verapamil + metoprolol: additive AV-nodal depression risk",
    )
    dumped = flag.model_dump()
    assert dumped["severity"] == "MAJOR"
    assert dumped["flag_type"] == "drug_interaction"
    assert dumped["recommendation_index"] == 0


def test_safety_flag_rejects_unknown_severity():
    with pytest.raises(ValidationError):
        SafetyFlag(
            title="bad severity flag",
            severity="LOW",
            recommendation_index=0,
            flag_type="drug_interaction",
            detail="some detail",
        )


@pytest.mark.asyncio
async def test_safety_report_safe_to_proceed_invariant():
    """LLM may return safe_to_proceed=True even with a MAJOR flag — post-processing must correct it."""
    case = _make_case()
    plan = _make_plan("metoprolol 50 mg BD")

    # LLM incorrectly says safe_to_proceed=True despite a MAJOR flag
    llm_payload = {
        "flags": [
            {
                "title": "verapamil + metoprolol - AV-nodal suppression",
                "severity": "MAJOR",
                "recommendation_index": 0,
                "flag_type": "drug_interaction",
                "detail": "Verapamil + metoprolol: combined AV-nodal suppression risk",
            }
        ],
        "safe_to_proceed": True,  # wrong — must be corrected
    }

    with patch("agent.safety_critic.openai.AsyncOpenAI", return_value=_mock_client(llm_payload)):
        report = await run_safety_critic(case, plan)

    assert report.safe_to_proceed is False, "Post-processing must set safe_to_proceed=False when MAJOR flag present"


@pytest.mark.asyncio
async def test_safety_critic_returns_flag_on_known_interaction():
    """Patient on verapamil + plan recommends metoprolol → critic should flag MAJOR drug_interaction."""
    case = _make_case(current_medications=["verapamil 240 mg OD"])
    plan = _make_plan("metoprolol 50 mg BD")

    llm_payload = {
        "flags": [
            {
                "title": "verapamil + metoprolol - AV-nodal depression",
                "severity": "MAJOR",
                "recommendation_index": 0,
                "flag_type": "drug_interaction",
                "detail": "Verapamil + metoprolol: combined AV-nodal depression risk in patient with angina",
                "suggested_alternative": "Consider amlodipine 5 mg OD instead of metoprolol",
            }
        ],
        "safe_to_proceed": False,
    }

    client_mock = _mock_client(llm_payload)

    with patch("agent.safety_critic.openai.AsyncOpenAI", return_value=client_mock):
        report = await run_safety_critic(case, plan)

    assert len(report.flags) >= 1
    assert report.flags[0].severity in ("MAJOR", "CRITICAL")
    assert report.flags[0].flag_type == "drug_interaction"
    assert report.safe_to_proceed is False

    # Verify adversarial system prompt was sent
    call_args = client_mock.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0] if call_args.args else []
    if not messages and call_args.kwargs:
        messages = call_args.kwargs["messages"]
    assert any(SAFETY_CRITIC_SYSTEM in m.get("content", "") for m in messages), \
        "Adversarial system prompt must be included in LLM messages"


@pytest.mark.asyncio
async def test_safety_critic_fail_open_on_invalid_json():
    """If LLM returns garbage JSON, critic returns empty SafetyReport without raising."""
    case = _make_case()
    plan = _make_plan("aspirin 100 mg OD")

    choice = MagicMock()
    choice.message.content = "this is not json }{{"
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    with patch("agent.safety_critic.openai.AsyncOpenAI", return_value=client):
        report = await run_safety_critic(case, plan)

    assert report.flags == []
    assert report.safe_to_proceed is True


@pytest.mark.asyncio
async def test_safety_critic_fail_open_on_validation_error():
    """If LLM returns structurally invalid JSON, critic returns empty SafetyReport."""
    case = _make_case()
    plan = _make_plan("aspirin 100 mg OD")

    llm_payload = {"flags": "not a list", "safe_to_proceed": True}

    with patch("agent.safety_critic.openai.AsyncOpenAI", return_value=_mock_client(llm_payload)):
        report = await run_safety_critic(case, plan)

    assert report.flags == []
    assert report.safe_to_proceed is True


@pytest.mark.asyncio
async def test_workflow_result_carries_safety_report():
    """run_clinical_workflow should attach the SafetyReport to WorkflowResult."""
    from agent.clinical_workflow import run_clinical_workflow
    from agent.models import MonitoringItem

    stub_plan = TreatmentPlan(
        icd_primary="BA80",
        summary="Stub plan",
        recommendations=[
            Recommendation(
                intervention="aspirin 100 mg OD",
                type="pharmacological",
                action="start",
                cpg_source="CPG Test §1",
                rationale="Anti-platelet",
            )
        ],
        monitoring=[],
        confidence=0.9,
    )
    stub_report = SafetyReport(flags=[], safe_to_proceed=True)

    case = _make_case()

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_3_route", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_4_retrieve", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_5_synthesize", new=AsyncMock(return_value=stub_plan)),
        patch("agent.safety_critic.openai.AsyncOpenAI", return_value=_mock_client(stub_report.model_dump())),
    ):
        result = await run_clinical_workflow(case)

    assert result.safety_report is not None
    assert isinstance(result.safety_report, SafetyReport)
