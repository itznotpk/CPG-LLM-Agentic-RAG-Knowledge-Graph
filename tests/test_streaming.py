"""Tests for clinical workflow streaming + thinking token emission."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.clinical_workflow import run_clinical_workflow_streaming, WorkflowResult
from agent.clinical_stages import DDxResult, _llm_rerank_ddx
from agent.models import PatientCase, TreatmentPlan


@pytest.fixture
def minimal_case():
    return PatientCase(chief_complaint="palpitations", age=68, sex="M")


@pytest.fixture
def mock_ddx():
    return [DDxResult(code="BC81.3", title="AF", similarity=0.91)]


@pytest.fixture
def mock_plan():
    return TreatmentPlan(
        icd_primary="BC81.3",
        summary="Atrial fibrillation management plan.",
        recommendations=[{
            "intervention": "Rate control with beta-blocker",
            "type": "pharmacological",
            "cpg_source": "AF CPG §4.2",
            "rationale": "Reduces ventricular rate in AF",
        }],
        confidence=0.85,
    )


# ── Stage progress tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_streaming_emits_all_stage_events(minimal_case, mock_ddx, mock_plan):
    """All 4 stages emit running + complete events."""
    events = []

    async def collect(event_type, data):
        events.append((event_type, data))

    with patch("agent.clinical_workflow.stage_2_ddx", AsyncMock(return_value=mock_ddx)), \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        await run_clinical_workflow_streaming(minimal_case, collect)

    updates = [e for e in events if e[0] == "stage_update"]
    for stage_num in [2, 3, 4, 5]:
        statuses = {e[1]["status"] for e in updates if e[1]["stage"] == stage_num}
        assert "running"  in statuses, f"Stage {stage_num} missing 'running'"
        assert "complete" in statuses, f"Stage {stage_num} missing 'complete'"


@pytest.mark.asyncio
async def test_streaming_passes_emit_to_stage2(minimal_case, mock_ddx, mock_plan):
    """run_clinical_workflow_streaming passes emit= to stage_2_ddx."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock) as mock_s2, \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):
        mock_s2.return_value = mock_ddx
        await run_clinical_workflow_streaming(minimal_case, noop)

    call_kwargs = mock_s2.call_args.kwargs
    assert "emit" in call_kwargs
    assert call_kwargs["emit"] is noop


@pytest.mark.asyncio
async def test_streaming_returns_workflow_result(minimal_case, mock_ddx, mock_plan):
    """Returns WorkflowResult with treatment plan."""
    async def noop(et, d): pass

    with patch("agent.clinical_workflow.stage_2_ddx", AsyncMock(return_value=mock_ddx)), \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_clinical_workflow_streaming(minimal_case, noop)

    assert isinstance(result, WorkflowResult)
    assert result.treatment_plan.icd_primary == "BC81.3"


@pytest.mark.asyncio
async def test_streaming_stage_error_emits_error_status(minimal_case, mock_plan):
    """Stage 2 failure → error event; pipeline continues."""
    events = []

    async def collect(et, d):
        events.append((et, d))

    with patch("agent.clinical_workflow.stage_2_ddx", AsyncMock(side_effect=Exception("db down"))), \
         patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.stage_5_synthesize", AsyncMock(return_value=mock_plan)):

        result = await run_clinical_workflow_streaming(minimal_case, collect)

    error_ev = [e for e in events if e[0] == "stage_update" and e[1]["status"] == "error"]
    assert len(error_ev) == 1 and error_ev[0][1]["stage"] == 2
    assert "Stage 2 DDx" in result.stage_errors[0]


# ── Thinking token streaming tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_rerank_streams_thinking_tokens_when_emit_provided(minimal_case):
    """When emit is provided, thinking tokens are emitted as thinking_delta."""
    candidates = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
    emitted = []

    async def collect(et, d):
        emitted.append((et, d))

    # Build mock streaming response: two chunks — thinking then content
    async def mock_stream():
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock(
            reasoning="68M, irregular pulse — AF likely",
            content=None,
        )
        yield chunk1

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock(
            reasoning=None,
            thinking=None,
            reasoning_content=None,
            content='[{"code":"BC81.3","confidence":0.92,"reasoning":"fits best"}]',
        )
        yield chunk2

    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        result = await _llm_rerank_ddx(minimal_case, candidates, emit=collect)

    thinking_events = [e for e in emitted if e[0] == "thinking_delta"]
    assert len(thinking_events) == 1
    assert "AF likely" in thinking_events[0][1]["chunk"]
    assert thinking_events[0][1]["stage"] == 2
    assert thinking_events[0][1]["node"] == "DDx Re-rank"
    assert result[0].code == "BC81.3"


@pytest.mark.asyncio
async def test_rerank_no_emit_uses_non_streaming_path(minimal_case):
    """When emit=None, non-streaming create() is called (original behavior)."""
    candidates = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]

    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([
        {"code": "BC81.3", "confidence": 0.92, "reasoning": "fits best"},
    ])

    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await _llm_rerank_ddx(minimal_case, candidates, emit=None)

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    # Non-streaming call must NOT pass stream=True
    assert call_kwargs.get("stream") is None or call_kwargs.get("stream") is False
    assert result[0].code == "BC81.3"


@pytest.mark.asyncio
async def test_rerank_thinking_failure_falls_back(minimal_case):
    """If streaming call raises, original candidate order is preserved."""
    candidates = [
        DDxResult(code="BC81.3", title="AF",  similarity=0.91),
        DDxResult(code="BA00",   title="HTN", similarity=0.72),
    ]
    emitted = []

    async def collect(et, d):
        emitted.append((et, d))

    with patch("agent.clinical_stages.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))

        result = await _llm_rerank_ddx(minimal_case, candidates, emit=collect)

    assert [r.code for r in result] == ["BC81.3", "BA00"]
