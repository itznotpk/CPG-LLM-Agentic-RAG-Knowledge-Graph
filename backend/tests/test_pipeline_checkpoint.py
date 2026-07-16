"""Tests for agent/pipeline_state.py — typed state + fingerprint-keyed resume."""
import json

import pytest
from unittest.mock import AsyncMock, patch

from agent.clinical_stages import DDxResult
from agent.clinical_workflow import run_clinical_workflow_streaming
from agent.models import PatientCase, SafetyReport, TreatmentPlan
from agent.pipeline_state import (
    PipelineState,
    begin_state,
    checkpoints_enabled,
    compute_resume_key,
)


@pytest.fixture
def case():
    return PatientCase(chief_complaint="palpitations", age=68, sex="M")


@pytest.fixture
def plan():
    return TreatmentPlan(
        icd_primary="BC81.3", summary="AF plan", confidence=0.85,
        recommendations=[{
            "intervention": "Rate control", "type": "pharmacological",
            "cpg_source": "AF CPG §4.2", "rationale": "r",
        }],
    )


@pytest.fixture
def ckpt_env(monkeypatch, tmp_path):
    """Enable checkpointing into an isolated temp dir."""
    monkeypatch.setenv("PIPELINE_CHECKPOINT_ENABLED", "true")
    monkeypatch.setenv("PIPELINE_CHECKPOINT_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def mock_side_stages():
    with patch("agent.safety_critic.run_safety_critic", AsyncMock(return_value=SafetyReport(flags=[], safe_to_proceed=True))), \
         patch("agent.clinical_workflow.extract_candidate_drugs_from_chunks", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.clinical_graph_lookup", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.get_graph_constraints", AsyncMock(return_value=[])), \
         patch("agent.clinical_workflow.fetch_ebm_evidence", AsyncMock(return_value=[])):
        yield


async def _noop(event_type, data):
    pass


def _run_patches(ddx, plan_mock):
    return (
        patch("agent.clinical_workflow.stage_2_ddx", AsyncMock(return_value=ddx)),
        patch("agent.clinical_workflow.stage_3_route", AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_4_retrieve", AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_5_synthesize", plan_mock),
    )


# ─── default-off behaviour ────────────────────────────────────────────────────

def test_disabled_by_default(case, tmp_path, monkeypatch):
    monkeypatch.delenv("PIPELINE_CHECKPOINT_ENABLED", raising=False)
    monkeypatch.setenv("PIPELINE_CHECKPOINT_DIR", str(tmp_path))
    assert checkpoints_enabled() is False
    state = begin_state(case, "streaming")
    assert state.resume_key is None
    state.ddx = [DDxResult(code="X", title="x", similarity=0.5)]
    state.checkpoint()
    assert list(tmp_path.glob("*.json")) == []  # nothing touched disk


# ─── fingerprint keying ───────────────────────────────────────────────────────

def test_key_stable_for_identical_inputs(case):
    assert compute_resume_key(case, "streaming") == compute_resume_key(case, "streaming")


def test_key_changes_with_inputs(case):
    other = PatientCase(chief_complaint="chest pain", age=68, sex="M")
    assert compute_resume_key(case, "streaming") != compute_resume_key(other, "streaming")
    assert compute_resume_key(case, "streaming") != compute_resume_key(case, "full")
    assert compute_resume_key(case, "resynthesize", extra={"selected": ["A"]}) != \
        compute_resume_key(case, "resynthesize", extra={"selected": ["B"]})


# ─── checkpoint round-trip ────────────────────────────────────────────────────

def test_checkpoint_roundtrip(case, ckpt_env):
    state = begin_state(case, "streaming")
    state.ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
    state.checkpoint()

    restored = begin_state(case, "streaming")
    assert restored.is_resumed("ddx")
    assert restored.ddx[0].code == "BC81.3"
    assert not restored.is_resumed("cpgs")


def test_complete_consumes_checkpoint(case, ckpt_env):
    state = begin_state(case, "streaming")
    state.ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
    state.checkpoint()
    state.complete()
    assert not begin_state(case, "streaming").resumed_stages


def test_stale_checkpoint_purged(case, ckpt_env, monkeypatch):
    state = begin_state(case, "streaming")
    state.ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
    state.checkpoint()
    # Age the file past a 1-minute TTL
    path = ckpt_env / f"{state.resume_key}.json"
    old = path.stat().st_mtime - 3600
    import os
    os.utime(path, (old, old))
    monkeypatch.setenv("PIPELINE_CHECKPOINT_TTL_MIN", "1")
    assert not begin_state(case, "streaming").resumed_stages
    assert not path.exists()


def test_corrupt_checkpoint_fails_open(case, ckpt_env):
    key = compute_resume_key(case, "streaming")
    (ckpt_env / f"{key}.json").write_text("{not json", encoding="utf-8")
    state = begin_state(case, "streaming")
    assert state.resumed_stages == []
    assert state.resume_key == key  # still usable for fresh checkpoints


# ─── end-to-end resume through the streaming pipeline ────────────────────────

@pytest.mark.asyncio
async def test_crash_at_stage5_then_resume_skips_stages_2_to_4(case, plan, ckpt_env):
    ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]

    # Run 1: stages 2-4 succeed, stage 5 dies → checkpoint left behind.
    s5_fail = AsyncMock(side_effect=RuntimeError("LLM outage"))
    p2, p3, p4, p5 = _run_patches(ddx, s5_fail)
    with p2, p3, p4, p5:
        with pytest.raises(RuntimeError):
            await run_clinical_workflow_streaming(case, _noop)
    assert len(list(ckpt_env.glob("*.json"))) == 1

    # Run 2: identical case → stages 2-4 restored, only 5/6 execute.
    events = []

    async def collect(event_type, data):
        events.append((event_type, data))

    s2 = AsyncMock(return_value=ddx)
    s5_ok = AsyncMock(return_value=plan)
    p2, p3, p4, p5 = _run_patches(ddx, s5_ok)
    with patch("agent.clinical_workflow.stage_2_ddx", s2), p3 as s3, p4 as s4, p5:
        result = await run_clinical_workflow_streaming(case, collect)

    s2.assert_not_called()
    s3.assert_not_called()
    s4.assert_not_called()
    s5_ok.assert_called_once()
    assert result.treatment_plan.icd_primary == "BC81.3"
    assert result.ddx[0].code == "BC81.3"

    # Resume surfaced in the trace and the SSE contract stayed intact.
    resumed = [e for e in events if e[0] == "sub_step" and e[1].get("badge") == "resumed"]
    assert len(resumed) == 3  # stages 2, 3, 4
    updates = [e for e in events if e[0] == "stage_update"]
    for stage_num in [2, 3, 4, 5, 6]:
        statuses = {e[1]["status"] for e in updates if e[1]["stage"] == stage_num}
        assert {"running", "complete"} <= statuses

    # Success consumed the checkpoint.
    assert list(ckpt_env.glob("*.json")) == []


@pytest.mark.asyncio
async def test_changed_case_does_not_resume(case, plan, ckpt_env):
    ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
    s5_fail = AsyncMock(side_effect=RuntimeError("LLM outage"))
    p2, p3, p4, p5 = _run_patches(ddx, s5_fail)
    with p2, p3, p4, p5:
        with pytest.raises(RuntimeError):
            await run_clinical_workflow_streaming(case, _noop)

    different = PatientCase(chief_complaint="chest pain", age=41, sex="F")
    s2 = AsyncMock(return_value=ddx)
    p2, p3, p4, p5 = _run_patches(ddx, AsyncMock(return_value=plan))
    with patch("agent.clinical_workflow.stage_2_ddx", s2), p3, p4, p5:
        await run_clinical_workflow_streaming(different, _noop)
    s2.assert_called_once()  # different fingerprint → no resume


def test_checkpoint_file_is_versioned_json(case, ckpt_env):
    state = begin_state(case, "streaming")
    state.ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.91)]
    state.checkpoint()
    payload = json.loads((ckpt_env / f"{state.resume_key}.json").read_text(encoding="utf-8"))
    assert payload["v"] == 1
    assert payload["entrypoint"] == "streaming"
    assert payload["fields"]["ddx"][0]["code"] == "BC81.3"


def test_pipeline_state_is_typed(plan):
    """PipelineState round-trips its typed fields through pydantic validation."""
    state = PipelineState(entrypoint="full", treatment_plan=plan)
    assert state.treatment_plan.confidence == 0.85
    with pytest.raises(Exception):
        PipelineState(entrypoint="full", ddx="not-a-list")
