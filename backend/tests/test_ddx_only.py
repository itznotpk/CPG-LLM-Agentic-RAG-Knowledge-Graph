"""Tests for the stop-and-confirm phase-1 path: run_ddx_only_streaming.

Phase 1 must run ONLY Stage 2 (DDx), emit a terminal `ddx_ready` event with the
candidates, and NOT run Stages 3-5 (no routing/retrieval/synthesis). The care plan
is generated later, after the clinician confirms a diagnosis.
"""
import pytest
from unittest.mock import AsyncMock, patch

from agent.clinical_workflow import run_ddx_only_streaming
from agent.clinical_stages import DDxResult
from agent.models import PatientCase


@pytest.fixture
def case():
    return PatientCase(chief_complaint="palpitations, irregular pulse", age=68, sex="M")


@pytest.fixture
def ddx():
    return [
        DDxResult(code="BC81.30", title="Paroxysmal atrial fibrillation", similarity=0.45),
        DDxResult(code="BC71.03", title="Non-sustained ventricular tachycardia", similarity=0.51),
    ]


@pytest.mark.asyncio
async def test_ddx_only_emits_ddx_ready_and_stops(case, ddx):
    events = []

    async def emit(event_type, data):
        events.append((event_type, data))

    with patch("agent.clinical_workflow.stage_2_ddx", new=AsyncMock(return_value=ddx)):
        result = await run_ddx_only_streaming(case, emit)

    # Returns the DDx list
    assert result == ddx

    types = [e[0] for e in events]
    # Stage 2 ran (running + complete)
    assert "stage_update" in types
    # Terminal gate event present, carrying the candidates
    assert "ddx_ready" in types
    ddx_ready = next(d for t, d in events if t == "ddx_ready")
    assert [c["code"] for c in ddx_ready["ddx"]] == ["BC81.30", "BC71.03"]

    # Stages 3-5 must NOT have run: no stage_update with stage in {3,4,5}
    later_stages = [
        d.get("stage") for t, d in events
        if t == "stage_update" and d.get("stage") in (3, 4, 5)
    ]
    assert later_stages == [], f"phase 1 leaked later stages: {later_stages}"


@pytest.mark.asyncio
async def test_ddx_only_failopen_on_stage2_error(case):
    """Stage-2 failure still emits ddx_ready (empty) and returns [] — never raises."""
    events = []

    async def emit(event_type, data):
        events.append((event_type, data))

    with patch("agent.clinical_workflow.stage_2_ddx",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await run_ddx_only_streaming(case, emit)

    assert result == []
    assert any(t == "stage_update" and d.get("status") == "error" for t, d in events)
    ddx_ready = next(d for t, d in events if t == "ddx_ready")
    assert ddx_ready["ddx"] == []
