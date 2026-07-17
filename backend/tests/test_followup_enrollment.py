"""Enrollment logic tests. DB mocked — no live Supabase needed."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.followup import enrollment as enr


def _mock_pool(fetchrow_results=None, fetch_results=None):
    """Async context-manager pool whose conn returns queued results."""
    conn = AsyncMock()
    if fetchrow_results is not None:
        conn.fetchrow = AsyncMock(side_effect=list(fetchrow_results))
    conn.fetch = AsyncMock(return_value=fetch_results or [])
    conn.execute = AsyncMock()
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    # conn.transaction() used as async CM too
    tctx = MagicMock()
    tctx.__aenter__ = AsyncMock(return_value=None)
    tctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tctx)
    return pool, conn


async def test_create_enrollment_returns_token_and_deep_link(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "ClearPathBot")
    pool, conn = _mock_pool(fetchrow_results=[{"name": "Ahmad bin Ali"}, {"id": 1}])
    with patch.object(enr, "db_pool", pool):
        out = await enr.create_enrollment(101, "900101-14-5555")
    assert out["deep_link"].startswith("https://t.me/ClearPathBot?start=")
    assert len(out["token"]) >= 32


async def test_bind_rejects_expired_token():
    expired = {
        "id": 1, "status": "issued", "patient_nric": "X",
        "token_expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    pool, conn = _mock_pool(fetchrow_results=[expired])
    with patch.object(enr, "db_pool", pool):
        assert await enr.bind_enrollment("tok", 555) is None


async def test_bind_supersedes_prior_active_and_activates():
    fresh = {
        "id": 2, "status": "issued", "patient_nric": "X",
        "consultation_id": 101, "patient_first_name": "Ahmad",
        "token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    pool, conn = _mock_pool(fetchrow_results=[fresh])
    with patch.object(enr, "db_pool", pool):
        row = await enr.bind_enrollment("tok", 555)
    assert row["id"] == 2
    assert row["status"] == "active"
    assert row["telegram_chat_id"] == 555
    assert row["activated_at"] is not None
    executed_sql = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "superseded" in executed_sql          # prior active rows superseded
    assert "cancelled" in executed_sql            # their pending check-ins cancelled
    assert "active" in executed_sql               # this row activated


async def test_stop_enrollment_cancels_pending():
    active = {"id": 3}
    pool, conn = _mock_pool(fetchrow_results=[active])
    with patch.object(enr, "db_pool", pool):
        assert await enr.stop_enrollment(555) is True
    executed_sql = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "stopped" in executed_sql and "cancelled" in executed_sql


async def test_create_enrollment_reads_full_name_column(monkeypatch):
    """patients has full_name, not name — a bare `name` select raises UndefinedColumn."""
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "ClearPathFollowupBot")
    pool, conn = _mock_pool(fetchrow_results=[{"full_name": "Ahmad bin Ali"}, {"id": 1}])
    with patch.object(enr, "db_pool", pool):
        await enr.create_enrollment(101, "900101-14-5555")
    select_sql = str(conn.fetchrow.call_args_list[0].args[0])
    assert "full_name" in select_sql
    assert "SELECT name" not in select_sql
    # first name only ever reaches Telegram (PHI constraint)
    insert_args = conn.fetchrow.call_args_list[1].args
    assert "Ahmad" in insert_args
    assert "Ahmad bin Ali" not in insert_args
