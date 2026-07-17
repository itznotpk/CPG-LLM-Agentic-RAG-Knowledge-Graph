"""Reminder scanner tests. Pure helpers first, then the DB scan (mocked pool)."""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.followup import reminder_scanner as rs


def test_compute_due_at_is_utc_for_malaysia_local_9am():
    # 30 Jun 2026, minus 3 days = 27 Jun 09:00 MYT (UTC+8) = 27 Jun 01:00 UTC
    due = rs.compute_due_at(date(2026, 6, 30), 3)
    assert due == datetime(2026, 6, 27, 1, 0, tzinfo=timezone.utc)


def test_compute_due_at_one_day_offset():
    due = rs.compute_due_at(date(2026, 6, 30), 1)
    assert due == datetime(2026, 6, 29, 1, 0, tzinfo=timezone.utc)


def test_render_reminder_t1_says_tomorrow_and_names_date():
    txt = rs.render_reminder(date(2026, 6, 30), 1)
    assert "tomorrow" in txt.lower()
    assert "30" in txt  # names the day


def test_render_reminder_t3_is_dated_not_tomorrow():
    txt = rs.render_reminder(date(2026, 6, 30), 3)
    assert "tomorrow" not in txt.lower()
    assert "30" in txt


@pytest.mark.parametrize("offset", [3, 1])
def test_render_reminder_obeys_house_style(offset):
    txt = rs.render_reminder(date(2026, 6, 30), offset)
    assert "!" not in txt
    # no emoji (any char above the basic multilingual plane / symbol ranges)
    assert all(ord(c) < 0x2190 for c in txt)
    assert "clinic" in txt.lower()


def _scan_pool(enrollment_rows):
    """Pool whose conn.fetch returns the active-enrollment rows; execute is captured."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=enrollment_rows)
    async def _exec(sql, *args):
        return "INSERT 0 1" if "INSERT" in str(sql).upper() else "UPDATE 0"
    conn.execute = AsyncMock(side_effect=_exec)
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


_NOW = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_scan_inserts_two_reminders_for_future_review():
    rows = [{"enrollment_id": 2, "patient_nric": "X", "review_date": date(2026, 6, 30)}]
    pool, conn = _scan_pool(rows)
    with patch.object(rs, "db_pool", pool):
        n = await rs.scan_due_reminders(_NOW)
    inserts = [c for c in conn.execute.call_args_list if "INSERT" in str(c.args[0]).upper()]
    assert n == 2 and len(inserts) == 2


@pytest.mark.asyncio
async def test_scan_skips_past_review_date():
    rows = [{"enrollment_id": 2, "patient_nric": "X", "review_date": date(2026, 6, 10)}]
    pool, conn = _scan_pool(rows)
    with patch.object(rs, "db_pool", pool):
        n = await rs.scan_due_reminders(_NOW)
    inserts = [c for c in conn.execute.call_args_list if "INSERT" in str(c.args[0]).upper()]
    assert n == 0 and len(inserts) == 0


@pytest.mark.asyncio
async def test_scan_cancels_superseded_pending_reminders():
    rows = [{"enrollment_id": 2, "patient_nric": "X", "review_date": date(2026, 6, 30)}]
    pool, conn = _scan_pool(rows)
    with patch.object(rs, "db_pool", pool):
        await rs.scan_due_reminders(_NOW)
    sql = " ".join(str(c.args[0]).lower() for c in conn.execute.call_args_list)
    assert "cancelled" in sql and "pending" in sql


@pytest.mark.asyncio
async def test_scan_is_fail_open_on_db_error():
    pool = MagicMock()
    pool.acquire.side_effect = RuntimeError("db down")
    with patch.object(rs, "db_pool", pool):
        assert await rs.scan_due_reminders(_NOW) == 0


@pytest.mark.asyncio
async def test_start_is_noop_when_worker_disabled(monkeypatch):
    monkeypatch.setenv("FOLLOWUP_WORKER_ENABLED", "false")
    rs._task = None
    rs.start()
    assert rs._task is None


@pytest.mark.asyncio
async def test_start_is_noop_without_bot_token(monkeypatch):
    monkeypatch.setenv("FOLLOWUP_WORKER_ENABLED", "true")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rs._task = None
    rs.start()
    assert rs._task is None


def test_insert_sql_revives_cancelled_but_not_sent_rows():
    # Fix 1: ON CONFLICT must revive a cancelled row, guarded so sent/pending are untouched.
    assert "DO UPDATE" in rs._INSERT_SQL
    assert "status = 'pending'" in rs._INSERT_SQL
    assert "followup_checkins.status = 'cancelled'" in rs._INSERT_SQL


async def test_scan_does_not_cancel_due_or_overdue_reminders():
    # Fix 2: cancel must be scoped to future reminders (due_at > now) and pass `now`.
    assert "due_at > $2" in rs._CANCEL_SQL
    rows = [{"enrollment_id": 2, "patient_nric": "X", "review_date": date(2026, 6, 30)}]
    pool, conn = _scan_pool(rows)
    with patch.object(rs, "db_pool", pool):
        await rs.scan_due_reminders(_NOW)
    cancel_calls = [c for c in conn.execute.call_args_list
                    if "UPDATE followup_checkins" in str(c.args[0])]
    assert cancel_calls, "cancel query was never issued"
    # now is passed as the 2nd positional arg (enrollment_id, now, due_ats)
    assert cancel_calls[0].args[2] == _NOW
