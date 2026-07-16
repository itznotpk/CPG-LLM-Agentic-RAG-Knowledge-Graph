"""Scheduler worker: claim → send → mark. DB and Telegram mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.followup import scheduler_worker as sw


def _pool(due_row):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=due_row)
    conn.execute = AsyncMock()
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    tctx = MagicMock()
    tctx.__aenter__ = AsyncMock(return_value=None)
    tctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tctx)
    return pool, conn


async def test_process_one_due_sends_and_marks_sent():
    due = {"id": 9, "enrollment_id": 2, "question": "How are you? Reply 1-5.",
           "telegram_chat_id": 555, "attempts": 0}
    pool, conn = _pool(due)
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(sw, "db_pool", pool), patch.object(sw, "get_client", lambda: tg), \
         patch.object(sw, "log_message", AsyncMock()):
        assert await sw.process_one_due() is True
    tg.send_message.assert_awaited_once_with(555, "How are you? Reply 1-5.")
    executed = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "sent" in executed


async def test_process_one_due_marks_failed_after_send_failure():
    due = {"id": 9, "enrollment_id": 2, "question": "Q", "telegram_chat_id": 555, "attempts": 2}
    pool, conn = _pool(due)
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=False)
    with patch.object(sw, "db_pool", pool), patch.object(sw, "get_client", lambda: tg), \
         patch.object(sw, "log_message", AsyncMock()):
        assert await sw.process_one_due() is True
    executed = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "failed" in executed or "attempts" in executed


async def test_process_one_due_noop_when_nothing_due():
    pool, conn = _pool(None)
    with patch.object(sw, "db_pool", pool):
        assert await sw.process_one_due() is False
