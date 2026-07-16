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


async def test_schedule_checkins_inserts_each_item_with_correct_params():
    from unittest.mock import AsyncMock, MagicMock, patch
    from datetime import datetime, timezone
    conn = AsyncMock()
    conn.execute = AsyncMock()
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    items = [
        proto.CheckinItem(kind="monitoring", day_offset=0, question="Q0? Reply 1-5."),
        proto.CheckinItem(kind="adherence", day_offset=7, question="Q7? YES/NO."),
    ]
    t0 = datetime(2026, 7, 16, tzinfo=timezone.utc)
    with patch.object(proto, "db_pool", pool):
        n = await proto.schedule_checkins(42, items, t0)
    assert n == 2
    assert conn.execute.await_count == 2
    first = conn.execute.await_args_list[0].args
    # positional order: sql, enrollment_id, kind, question, due_at
    assert first[1] == 42
    assert first[2] == "monitoring"
    assert first[3] == "Q0? Reply 1-5."


async def test_generate_protocol_enforces_max_per_day():
    from unittest.mock import AsyncMock, patch
    raw = {"checkins": [
        {"kind": "monitoring", "day_offset": 3, "question": f"Q{i}? Reply 1-5."}
        for i in range(5)
    ]}
    with patch.object(proto, "_call_llm", AsyncMock(return_value=raw)):
        items = await proto.generate_protocol({"summary": "x"}, "Ahmad")
    same_day = [i for i in items if i.day_offset == 3]
    assert len(same_day) <= proto.MAX_PER_DAY
