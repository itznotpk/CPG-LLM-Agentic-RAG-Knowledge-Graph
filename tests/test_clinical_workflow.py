"""
Unit tests for agent/clinical_workflow.py and the POST /clinical/plan endpoint.
All mocked — no real DB, no real LLM, no real embeddings.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from agent.models import PatientCase, TreatmentPlan, Recommendation
from agent.clinical_stages import DDxResult
from agent.routing import CPGDocRef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_patient() -> PatientCase:
    return PatientCase(
        chief_complaint="palpitations and irregular heartbeat",
        age=68,
        sex="M",
        comorbidities=["hypertension"],
        current_medications=["amlodipine 5mg OD"],
        vitals={"sbp": 145, "dbp": 88, "hr": 110},
    )


def make_ddx() -> list[DDxResult]:
    return [
        DDxResult(code="BC81.3", title="Persistent AF", similarity=0.92),
        DDxResult(code="BC81.1", title="Paroxysmal AF", similarity=0.75),
    ]


def make_cpgs() -> list[CPGDocRef]:
    return [CPGDocRef(
        cpg_name="CPG AF Management",
        document_id="doc-001",
        document_ids=["doc-001"],
        title="CPG AF Management",
        match_type="exact",
        score=0.9,
        matched_scope="BC81.3",
    )]


def make_plan() -> TreatmentPlan:
    return TreatmentPlan(
        icd_primary="BC81.3",
        icd_alternates=["BC81.1"],
        summary="Atrial fibrillation management plan.",
        recommendations=[
            Recommendation(
                intervention="Rate control with bisoprolol 5mg OD",
                type="pharmacological",
                cpg_source="CPG AF Management §4.2",
                rationale="Rate control for persistent AF with HR >100",
            )
        ],
        monitoring=[{"parameter": "heart rate", "schedule": "at each visit"}],
        red_flags=["Haemodynamic compromise"],
        confidence=0.88,
        unresolved_questions=[],
    )


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_calls_all_stages():
    case = make_patient()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=make_ddx()) as m2,
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=make_cpgs()) as m3,
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]) as m4,
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=make_plan()) as m5,
    ):
        from agent.clinical_workflow import run_clinical_workflow
        await run_clinical_workflow(case)
        m2.assert_called_once()
        m3.assert_called_once()
        m4.assert_called_once()
        m5.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_returns_treatment_plan():
    case = make_patient()
    expected_plan = make_plan()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=make_ddx()),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=make_cpgs()),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=expected_plan),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(case)
        assert isinstance(result.treatment_plan, TreatmentPlan)
        assert result.treatment_plan.icd_primary == "BC81.3"


@pytest.mark.asyncio
async def test_workflow_stage2_failure_continues():
    case = make_patient()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, side_effect=RuntimeError("embedding failure")),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=make_cpgs()) as m3,
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]) as m4,
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=make_plan()) as m5,
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(case)
        assert result.ddx == []
        m3.assert_called_once()
        m4.assert_called_once()
        m5.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_stage3_failure_continues():
    case = make_patient()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=make_ddx()),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, side_effect=RuntimeError("routing failure")),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]) as m4,
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=make_plan()) as m5,
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(case)
        assert result.cpgs == []
        m4.assert_called_once()
        m5.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_stage4_failure_continues():
    case = make_patient()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=make_ddx()),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=make_cpgs()),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, side_effect=RuntimeError("retrieval failure")),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=make_plan()) as m5,
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(case)
        # stage 5 still called even though stage 4 failed
        m5.assert_called_once()
        assert isinstance(result.treatment_plan, TreatmentPlan)


@pytest.mark.asyncio
async def test_workflow_stage5_failure_raises():
    case = make_patient()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=make_ddx()),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=make_cpgs()),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, side_effect=RuntimeError("synthesis failed")),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        with pytest.raises(RuntimeError, match="synthesis failed"):
            await run_clinical_workflow(case)


@pytest.mark.asyncio
async def test_workflow_records_elapsed_ms():
    case = make_patient()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=make_ddx()),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=make_cpgs()),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=make_plan()),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(case)
        assert result.elapsed_ms > 0


@pytest.mark.asyncio
async def test_workflow_records_stage_errors():
    case = make_patient()
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, side_effect=ValueError("vector store down")),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=make_cpgs()),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=make_plan()),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(case)
        assert len(result.stage_errors) == 1
        assert result.stage_errors[0].stage == "Stage 2 DDx"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from agent.api import app
    return TestClient(app)


@pytest.mark.asyncio
async def test_clinical_plan_endpoint_200():
    from httpx import AsyncClient, ASGITransport
    from agent.api import app
    from agent.clinical_workflow import WorkflowResult

    mock_result = WorkflowResult(
        treatment_plan=make_plan(),
        ddx=make_ddx(),
        cpgs=make_cpgs(),
        elapsed_ms=1234.5,
        stage_errors=[],
    )

    with patch("agent.clinical_workflow.run_clinical_workflow", new_callable=AsyncMock, return_value=mock_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/clinical/plan", json={"case": {"chief_complaint": "palpitations"}})
        assert resp.status_code == 200
        body = resp.json()
        assert "treatment_plan" in body
        assert "ddx" in body
        assert "cpgs_matched" in body
        assert "elapsed_ms" in body


@pytest.mark.asyncio
async def test_clinical_plan_endpoint_500():
    from httpx import AsyncClient, ASGITransport
    from agent.api import app

    with patch("agent.clinical_workflow.run_clinical_workflow", new_callable=AsyncMock, side_effect=RuntimeError("synthesis failed")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/clinical/plan", json={"case": {"chief_complaint": "palpitations"}})
        assert resp.status_code == 500


@pytest.mark.asyncio
async def test_clinical_plan_maps_ddx():
    from httpx import AsyncClient, ASGITransport
    from agent.api import app
    from agent.clinical_workflow import WorkflowResult

    mock_result = WorkflowResult(
        treatment_plan=make_plan(),
        ddx=make_ddx(),
        cpgs=make_cpgs(),
        elapsed_ms=500.0,
        stage_errors=[],
    )

    with patch("agent.clinical_workflow.run_clinical_workflow", new_callable=AsyncMock, return_value=mock_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/clinical/plan", json={"case": {"chief_complaint": "palpitations"}})
        body = resp.json()
        assert isinstance(body["ddx"], list)
        assert len(body["ddx"]) == 2
        first = body["ddx"][0]
        assert "code" in first
        assert "title" in first
        assert "similarity" in first


@pytest.mark.asyncio
async def test_clinical_plan_maps_cpgs():
    from httpx import AsyncClient, ASGITransport
    from agent.api import app
    from agent.clinical_workflow import WorkflowResult

    mock_result = WorkflowResult(
        treatment_plan=make_plan(),
        ddx=make_ddx(),
        cpgs=make_cpgs(),
        elapsed_ms=500.0,
        stage_errors=[],
    )

    with patch("agent.clinical_workflow.run_clinical_workflow", new_callable=AsyncMock, return_value=mock_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/clinical/plan", json={"case": {"chief_complaint": "palpitations"}})
        body = resp.json()
        assert isinstance(body["cpgs_matched"], list)
        assert body["cpgs_matched"] == ["CPG AF Management"]
