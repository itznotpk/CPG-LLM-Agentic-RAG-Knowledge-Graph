"""Tests for clinician-directed re-synthesis workflow."""
import pytest
from unittest.mock import AsyncMock, patch

from agent.clinical_workflow import run_resynthesize_streaming, WorkflowResult
from agent.clinical_stages import DDxResult
from agent.models import PatientCase, TreatmentPlan


@pytest.fixture
def minimal_case():
    return PatientCase(chief_complaint="palpitations", age=68, sex="M")


@pytest.fixture
def selected_ddx():
    return [DDxResult(code="BC81.3", title="Atrial Fibrillation", similarity=0.95)]


@pytest.fixture
def mock_plan():
    return TreatmentPlan(
        icd_primary="BC81.3",
        summary="Atrial fibrillation management plan.",
        recommendations=[
            {
                "intervention": "Rate control with beta-blocker",
                "type": "pharmacological",
                "cpg_source": "CPG AF Management §4.2",
                "rationale": "Rate control for AF",
            }
        ],
        confidence=0.88,
    )


@pytest.mark.asyncio
async def test_resynth_emits_clinician_override_first(minimal_case, selected_ddx, mock_plan):
    """clinician_override event is the first event emitted."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        await run_resynthesize_streaming(minimal_case, selected_ddx, collect)

    assert events[0][0] == "clinician_override"
    assert "BC81.3" in events[0][1]["codes"][0]


@pytest.mark.asyncio
async def test_resynth_skips_stage_2(minimal_case, selected_ddx, mock_plan):
    """Stage 2 DDx is never called — clinician selection is used directly."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock) as mock_s2, \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        await run_resynthesize_streaming(minimal_case, selected_ddx, collect)

    mock_s2.assert_not_called()
    stage_nums = {e[1].get("stage") for e in events if e[0] == "stage_update"}
    assert 2 not in stage_nums
    assert {3, 4, 5}.issubset(stage_nums)


@pytest.mark.asyncio
async def test_resynth_uses_selected_ddx_for_routing(minimal_case, selected_ddx, mock_plan):
    """stage_3_route is called with the clinician's selected DDx, not AI's."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock) as mock_s3, \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):
        mock_s3.return_value = []
        await run_resynthesize_streaming(minimal_case, selected_ddx, noop)

    call_args = mock_s3.call_args
    passed_ddx = call_args.args[0]
    assert passed_ddx[0].code == "BC81.3"
    assert call_args.kwargs.get("top_k_codes") == len(selected_ddx)


@pytest.mark.asyncio
async def test_resynth_returns_new_treatment_plan(minimal_case, selected_ddx, mock_plan):
    """WorkflowResult contains the new plan for the clinician-selected diagnosis."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_resynthesize_streaming(minimal_case, selected_ddx, noop)

    assert isinstance(result, WorkflowResult)
    assert result.treatment_plan.icd_primary == "BC81.3"
    assert result.ddx == selected_ddx


@pytest.mark.asyncio
async def test_resynth_stage3_failure_continues(minimal_case, selected_ddx, mock_plan):
    """Stage 3 failure is fault-tolerant — pipeline continues to Stage 5."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_3_route", AsyncMock(side_effect=Exception("routing down"))), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_resynthesize_streaming(minimal_case, selected_ddx, collect)

    error_events = [e for e in events if e[0] == "stage_update" and e[1].get("status") == "error"]
    assert any(e[1]["stage"] == 3 for e in error_events)
    assert "Stage 3 Routing" in result.stage_errors[0]
    assert result.treatment_plan.icd_primary == "BC81.3"
