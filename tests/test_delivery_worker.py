"""Tests for agent/delivery_worker.py."""
from __future__ import annotations

import asyncio
import smtplib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

import agent.delivery as delivery_mod
from tests.test_delivery import (
    FIXTURE_PDF,
    SMTP_TEST_PORT,
    _CaptureHandler,
    _make_job_row,
    _make_pool_mock,
)


@pytest_asyncio.fixture
async def smtp_server_worker():
    """aiosmtpd on a different port to avoid conflicts with test_delivery.py."""
    from aiosmtpd.controller import Controller

    worker_port = SMTP_TEST_PORT + 1
    handler = _CaptureHandler()
    controller = Controller(handler, hostname="127.0.0.1", port=worker_port)
    controller.start()

    original = delivery_mod._SMTP_OVERRIDE
    delivery_mod._SMTP_OVERRIDE = ("127.0.0.1", worker_port)

    class _Plain(smtplib.SMTP):
        def __init__(self, host, port, context=None, timeout=30):
            super().__init__(host, port, timeout=timeout)

        def login(self, user, password, **kwargs):
            pass

    with patch("agent.delivery.smtplib.SMTP_SSL", _Plain):
        yield handler

    delivery_mod._SMTP_OVERRIDE = original
    controller.stop()


@pytest.mark.asyncio
async def test_worker_picks_up_queued_job(smtp_server_worker):
    handler = smtp_server_worker
    row = _make_job_row()
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    with patch("agent.delivery.db_pool", pool):
        with patch("agent.delivery._fetch_pdf", AsyncMock(return_value=FIXTURE_PDF)):
            await delivery_mod.deliver_care_plan(jid)

    execute_calls = [str(c) for c in conn.execute.call_args_list]
    assert any("sent" in c for c in execute_calls)
    assert len(handler.messages) == 1


@pytest.mark.asyncio
async def test_worker_requeues_on_transient_smtp_error(smtp_server_worker):
    handler = smtp_server_worker
    row = _make_job_row()
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    call_count = 0

    async def _fail_first(url):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("transient error")
        return FIXTURE_PDF

    # First attempt — raises, worker catches and re-marks queued
    with patch("agent.delivery.db_pool", pool):
        with patch("agent.delivery._fetch_pdf", _fail_first):
            with pytest.raises(Exception):
                await delivery_mod.deliver_care_plan(jid)

    # Second attempt — succeeds
    pool2, conn2 = _make_pool_mock(row)
    with patch("agent.delivery.db_pool", pool2):
        with patch("agent.delivery._fetch_pdf", _fail_first):
            await delivery_mod.deliver_care_plan(jid)

    # Second run should send
    assert call_count == 2
    assert len(handler.messages) == 1
    execute_calls = [str(c) for c in conn2.execute.call_args_list]
    assert any("sent" in c for c in execute_calls)
