"""Tests for typed-threshold field validation in graph_builder triple extraction."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.graph_builder import GraphBuilder


@pytest.fixture
def gb():
    return GraphBuilder()


def _stub_llm_response(triples):
    """Build a MagicMock that mimics pydantic_ai Agent.run -> response.output."""
    resp = MagicMock()
    resp.output = json.dumps(triples)
    return resp


async def _run(gb, triples):
    with patch("ingestion.graph_builder.get_ingestion_model", create=True), \
         patch("pydantic_ai.Agent") as agent_cls:
        inst = MagicMock()
        inst.run = AsyncMock(return_value=_stub_llm_response(triples))
        agent_cls.return_value = inst
        return await gb._extract_triples_with_llm(
            text="dummy", chunk_index=0, source="t.md", cpg_chunk_id="c1"
        )


@pytest.mark.asyncio
async def test_threshold_passthrough_valid(gb):
    raw = [{"subject": "Metformin", "subject_type": "Drug",
            "relation": "REQUIRES_DOSE_ADJUSTMENT", "object": "Renal Impairment",
            "object_type": "Condition", "evidence": "eGFR < 30",
            "threshold_param": "eGFR", "threshold_op": "<", "threshold_value": 30,
            "threshold_unit": "mL/min/1.73m2", "threshold_confidence": "high"}]
    out = await _run(gb, raw)
    assert out and out[0]["threshold_param"] == "eGFR"
    assert out[0]["threshold_op"] == "<"
    assert out[0]["threshold_value"] == 30
    assert out[0]["threshold_unit"] == "mL/min/1.73m2"
    assert out[0]["threshold_negated"] is False


@pytest.mark.asyncio
async def test_threshold_dropped_on_wrong_relation(gb):
    raw = [{"subject": "Aspirin", "subject_type": "Drug", "relation": "TREATS",
            "object": "MI", "object_type": "Condition", "evidence": "x",
            "threshold_param": "dose", "threshold_op": "<", "threshold_value": 100}]
    out = await _run(gb, raw)
    assert out[0]["threshold_param"] is None
    assert out[0]["threshold_op"] is None


@pytest.mark.asyncio
async def test_threshold_between_requires_value2(gb):
    raw = [{"subject": "Aspirin", "subject_type": "Drug", "relation": "HAS_DOSAGE",
            "object": "Dose", "object_type": "Dosage", "evidence": "x",
            "threshold_param": "aspirin_dose", "threshold_op": "between",
            "threshold_value": 75, "threshold_unit": "mg/day"}]
    out = await _run(gb, raw)
    assert out[0]["threshold_param"] is None  # dropped: missing value2


@pytest.mark.asyncio
async def test_threshold_bad_op_dropped(gb):
    # Evidence must satisfy the CONTRAINDICATED_WITH complement guard so the triple
    # survives long enough for the threshold_op normalization under test to run.
    raw = [{"subject": "X", "subject_type": "Drug", "relation": "CONTRAINDICATED_WITH",
            "object": "Y", "object_type": "Condition",
            "evidence": "X is contraindicated in Y over age 75",
            "threshold_param": "age", "threshold_op": "over", "threshold_value": 75}]
    out = await _run(gb, raw)
    assert out[0]["threshold_op"] is None  # 'over' is non-canonical → normalized to None


@pytest.mark.asyncio
async def test_threshold_unit_trimmed(gb):
    raw = [{"subject": "K", "subject_type": "Condition", "relation": "REQUIRES_MONITORING",
            "object": "Potassium", "object_type": "DiagnosticTool", "evidence": "K+ > 5.5",
            "threshold_param": "K+", "threshold_op": ">", "threshold_value": 5.5,
            "threshold_unit": "  mmol/L  ", "threshold_confidence": "high"}]
    out = await _run(gb, raw)
    assert out[0]["threshold_unit"] == "mmol/L"


@pytest.mark.asyncio
async def test_threshold_dropped_when_confidence_not_high(gb):
    raw = [{"subject": "Metformin", "subject_type": "Drug",
            "relation": "REQUIRES_DOSE_ADJUSTMENT", "object": "Renal Impairment",
            "object_type": "Condition", "evidence": "Reduce dose in renal impairment.",
            "threshold_param": "eGFR", "threshold_op": "<", "threshold_value": 30,
            "threshold_unit": "mL/min/1.73m2", "threshold_confidence": "medium"}]
    out = await _run(gb, raw)
    assert out[0]["threshold_param"] is None  # gated out by confidence != "high"


@pytest.mark.asyncio
async def test_table_row_noise_evidence_dropped(gb):
    raw = [
        {"subject": "ACEi", "subject_type": "Drug", "relation": "RECOMMENDED_FOR",
         "object": "Asthma", "object_type": "Condition",
         "evidence": "Asthma | + | - | + | + | + | +"},
        {"subject": "Metformin", "subject_type": "Drug", "relation": "FIRST_LINE_FOR",
         "object": "T2DM", "object_type": "Condition",
         "evidence": "Metformin remains first-line for T2DM unless eGFR<30."},
    ]
    out = await _run(gb, raw)
    assert len(out) == 1
    assert out[0]["subject"] == "Metformin"
