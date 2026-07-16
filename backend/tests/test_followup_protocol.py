"""Protocol generation tests. LLM mocked; caps and fallback exercised."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from agent.followup import protocol as proto

PLAN = {
    "summary": "HFrEF optimisation",
    "recommendations": [
        {"intervention": "[START] Bisoprolol 2.5 mg OD", "recommendation_type": "pharmacological", "action": "start"},
    ],
    "monitoring": [{"parameter": "weight", "schedule": "daily for 2 weeks"}],
    "follow_up": [{"when": "2 weeks", "what": "review symptoms"}],
    "safety_netting": ["Worsening breathlessness at rest", "Ankle swelling"],
}


def test_fallback_protocol_shape():
    items = proto.fallback_protocol(PLAN)
    assert len(items) == 3
    assert items[0].day_offset == 0
    assert any(i.kind == "adherence" for i in items)
    # red-flag text surfaces in the day-3 question
    assert "breathless" in items[1].question.lower() or "swelling" in items[1].question.lower()


async def test_generate_protocol_falls_back_on_llm_error():
    with patch.object(proto, "_call_llm", AsyncMock(side_effect=RuntimeError("down"))):
        items = await proto.generate_protocol(PLAN, "Ahmad")
    assert len(items) == 3  # the fallback


async def test_generate_protocol_clamps_caps():
    raw = {"checkins": [
        {"kind": "monitoring", "day_offset": d, "question": f"Q{d}? Reply 1-5."}
        for d in range(20)
    ]}
    with patch.object(proto, "_call_llm", AsyncMock(return_value=raw)):
        items = await proto.generate_protocol(PLAN, "Ahmad")
    assert len(items) <= proto.MAX_CHECKINS
    assert all(0 <= i.day_offset <= 30 for i in items)


def test_compute_due_at_respects_time_scale(monkeypatch):
    t0 = datetime(2026, 7, 16, tzinfo=timezone.utc)
    monkeypatch.setenv("FOLLOWUP_TIME_SCALE", "1")
    assert (proto.compute_due_at(t0, 3) - t0).total_seconds() == 3 * 86400
    monkeypatch.setenv("FOLLOWUP_TIME_SCALE", "21600")
    assert (proto.compute_due_at(t0, 3) - t0).total_seconds() == pytest.approx(12.0)
