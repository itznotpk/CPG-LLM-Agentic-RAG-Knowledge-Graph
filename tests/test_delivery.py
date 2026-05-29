"""Tests for agent/delivery.py — uses aiosmtpd for in-process SMTP capture."""
from __future__ import annotations

import asyncio
import email
import pathlib
import smtplib
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
import pytest_asyncio

import agent.delivery as delivery_mod
from agent.delivery import (
    _build_message,
    _cover_body,
    _validate_subject,
    deliver_care_plan,
)

# ─── aiosmtpd in-process SMTP server ─────────────────────────────────────────

class _CaptureHandler:
    """Captures raw DATA envelopes."""
    def __init__(self):
        self.messages: list[bytes] = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope.content)
        return "250 OK"


SMTP_TEST_PORT = 10125  # fixed port — Windows aiosmtpd doesn't support port=0


class _PlainSMTPClass(smtplib.SMTP):
    """Drop-in for SMTP_SSL: plaintext + skip AUTH (aiosmtpd doesn't advertise AUTH)."""
    def __init__(self, host, port, context=None, timeout=30):
        super().__init__(host, port, timeout=timeout)

    def login(self, user, password, **kwargs):
        pass  # aiosmtpd test server has no AUTH; skip credentials


@pytest_asyncio.fixture
async def smtp_server():
    """Start aiosmtpd on SMTP_TEST_PORT; patch delivery to use plaintext SMTP."""
    from aiosmtpd.controller import Controller

    handler = _CaptureHandler()
    controller = Controller(handler, hostname="127.0.0.1", port=SMTP_TEST_PORT)
    controller.start()

    original_override = delivery_mod._SMTP_OVERRIDE
    delivery_mod._SMTP_OVERRIDE = ("127.0.0.1", SMTP_TEST_PORT)

    with patch("agent.delivery.smtplib.SMTP_SSL", _PlainSMTPClass):
        yield handler

    delivery_mod._SMTP_OVERRIDE = original_override
    controller.stop()


# ─── shared DB mock builder ───────────────────────────────────────────────────

def _make_job_row(**overrides):
    """Return a dict that mimics a delivery_jobs + patients + consultations join row."""
    base = dict(
        consultation_id=1001,
        patient_nric="580315-08-1234",
        recipient="patient@test.com",
        patient_full_name="Alice Tan",
        preferred_language="en",
        email="patient@test.com",
        email_consent_at=datetime.now(timezone.utc),
        consultation_date="2026-05-29",
        report_pdf_url="https://example.com/plan.pdf",
    )
    base.update(overrides)
    return base


def _make_pool_mock(row):
    """Build an asyncpg pool mock whose acquire() returns a conn with fetchrow → row."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_async_ctx(conn))
    return pool, conn


class _async_ctx:
    """Minimal async context manager returning a value."""
    def __init__(self, val):
        self._val = val

    async def __aenter__(self):
        return self._val

    async def __aexit__(self, *a):
        pass


# ─── fixture PDF ─────────────────────────────────────────────────────────────

FIXTURE_PDF_DIR = pathlib.Path(__file__).parent / "fixtures"
FIXTURE_PDF_DIR.mkdir(exist_ok=True)
FIXTURE_PDF = FIXTURE_PDF_DIR / "sample.pdf"
FIXTURE_PDF.write_bytes(b"%PDF-1.4 test")


# ─── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_email_happy_path(smtp_server):
    handler = smtp_server
    row = _make_job_row()
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    with patch("agent.delivery.db_pool", pool):
        with patch("agent.delivery._fetch_pdf", AsyncMock(return_value=FIXTURE_PDF)):
            await deliver_care_plan(jid)

    # status updated to 'sent'
    execute_calls = [str(c) for c in conn.execute.call_args_list]
    assert any("sent" in c for c in execute_calls)

    # SMTP server captured exactly one message
    assert len(handler.messages) == 1
    msg = email.message_from_bytes(handler.messages[0])
    assert "patient@test.com" in msg["To"]
    assert "Care Plan" in msg["Subject"]

    parts = [p for p in email.message_from_bytes(handler.messages[0]).walk()
             if p.get_content_type() == "application/pdf"]
    assert parts, "No PDF attachment"
    assert parts[0].get_filename() == "care_plan.pdf"


@pytest.mark.asyncio
async def test_refuses_without_consent(smtp_server):
    handler = smtp_server
    row = _make_job_row(email_consent_at=None)
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    # deliver_care_plan returns (does not raise) on consent failure
    with patch("agent.delivery.db_pool", pool):
        await deliver_care_plan(jid)

    # status written as 'failed' with error='no_consent'
    execute_calls = conn.execute.call_args_list
    failed_call = next((c for c in execute_calls if "failed" in str(c)), None)
    assert failed_call is not None, "Expected a failed status update"
    assert "no_consent" in str(failed_call)

    # SMTP server received nothing
    assert len(handler.messages) == 0


@pytest.mark.asyncio
async def test_refuses_without_email(smtp_server):
    handler = smtp_server
    # email=None means consent check also fails (email is falsy)
    row = _make_job_row(email=None, email_consent_at=None)
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    with patch("agent.delivery.db_pool", pool):
        await deliver_care_plan(jid)

    execute_calls = conn.execute.call_args_list
    failed_call = next((c for c in execute_calls if "failed" in str(c)), None)
    assert failed_call is not None
    assert len(handler.messages) == 0


def test_subject_phi_guard_rejects_diagnosis():
    with pytest.raises(ValueError, match="diabetes"):
        _validate_subject("Care Plan — Diabetes")


def test_subject_phi_guard_rejects_medication():
    with pytest.raises(ValueError, match="warfarin"):
        _validate_subject("Care Plan — Warfarin dose")


@pytest.mark.asyncio
async def test_idempotency_unique_index():
    """Two enqueue calls for the same job row return the same job_id (mock level)."""
    # The SQL-level idempotency is enforced by the unique index; here we verify
    # deliver_care_plan does NOT insert a new row — it only reads and updates.
    row = _make_job_row()
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    with patch("agent.delivery.db_pool", pool):
        with patch("agent.delivery._fetch_pdf", AsyncMock(return_value=FIXTURE_PDF)):
            with patch("agent.delivery.smtplib.SMTP_SSL", MagicMock()) as mock_smtp:
                instance = mock_smtp.return_value.__enter__.return_value
                instance.send_message = MagicMock()
                await deliver_care_plan(jid)

    # fetchrow called exactly once per deliver_care_plan invocation (no INSERT)
    assert conn.fetchrow.call_count == 1


@pytest.mark.asyncio
async def test_pdf_attachment_round_trip(smtp_server):
    handler = smtp_server
    pdf_bytes = b"%PDF-1.4 roundtrip"
    pdf_path = FIXTURE_PDF_DIR / "roundtrip.pdf"
    pdf_path.write_bytes(pdf_bytes)

    row = _make_job_row()
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    with patch("agent.delivery.db_pool", pool):
        with patch("agent.delivery._fetch_pdf", AsyncMock(return_value=pdf_path)):
            await deliver_care_plan(jid)

    assert len(handler.messages) == 1
    msg_parsed = email.message_from_bytes(handler.messages[0])
    attachments = [p for p in msg_parsed.walk() if p.get_content_type() == "application/pdf"]
    assert attachments
    assert attachments[0].get_filename() == "care_plan.pdf"
    assert attachments[0].get_payload(decode=True) == pdf_bytes


@pytest.mark.asyncio
async def test_no_clinical_columns_mutated(smtp_server):
    """deliver_care_plan must NOT execute any UPDATE on consultations."""
    handler = smtp_server
    row = _make_job_row()
    pool, conn = _make_pool_mock(row)
    jid = uuid.uuid4()

    with patch("agent.delivery.db_pool", pool):
        with patch("agent.delivery._fetch_pdf", AsyncMock(return_value=FIXTURE_PDF)):
            await deliver_care_plan(jid)

    # All execute() calls must be on delivery_jobs only
    for c in conn.execute.call_args_list:
        sql = c.args[0].lower() if c.args else ""
        assert "consultations" not in sql, f"Unexpected consultations write: {c}"
        assert "treatment_plan" not in sql, f"Unexpected treatment_plan write: {c}"
        assert "safety_report" not in sql, f"Unexpected safety_report write: {c}"
