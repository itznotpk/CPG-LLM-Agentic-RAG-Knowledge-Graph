"""Tests for agent/stage_retry.py — env-driven transient-only stage retries."""
import asyncio

import pytest

from agent.stage_retry import is_transient, retry_attempts_for, run_with_retry


class FakeTimeout(TimeoutError):
    pass


class FakeStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class DeterministicError(ValueError):
    pass


# ─── is_transient classification ─────────────────────────────────────────────

def test_timeout_is_transient():
    assert is_transient(FakeTimeout("slow")) is True


def test_asyncio_timeout_is_transient():
    assert is_transient(asyncio.TimeoutError()) is True


def test_connection_error_is_transient():
    assert is_transient(ConnectionResetError("dropped")) is True


def test_retryable_status_code_is_transient():
    assert is_transient(FakeStatusError(429)) is True
    assert is_transient(FakeStatusError(503)) is True


def test_non_retryable_status_code_is_not_transient():
    assert is_transient(FakeStatusError(400)) is False
    assert is_transient(FakeStatusError(404)) is False


def test_deterministic_error_is_not_transient():
    assert is_transient(DeterministicError("bad input")) is False


def test_transient_cause_chain_detected():
    outer = RuntimeError("wrapper")
    outer.__cause__ = FakeTimeout("inner")
    assert is_transient(outer) is True


def test_status_codes_env_override(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_STATUS_CODES", "418")
    assert is_transient(FakeStatusError(418)) is True
    assert is_transient(FakeStatusError(429)) is False


# ─── retry_attempts_for stage gating ─────────────────────────────────────────

def test_default_attempts():
    assert retry_attempts_for("stage_5_synthesize") == 2


def test_attempts_env_override(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_ATTEMPTS", "5")
    assert retry_attempts_for("stage_2_ddx") == 5


def test_stage_list_gating(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_STAGES", "stage_5_synthesize,stage_6_safety")
    assert retry_attempts_for("stage_5_synthesize") == 2
    assert retry_attempts_for("stage_2_ddx") == 0


def test_zero_attempts_disables(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_ATTEMPTS", "0")
    assert retry_attempts_for("stage_5_synthesize") == 0


# ─── run_with_retry behaviour ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transient_failure_then_success(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_BACKOFF_MS", "0")
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeTimeout("first attempt times out")
        return "ok"

    result = await run_with_retry("stage_5_synthesize", flaky)
    assert result == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_non_transient_not_retried(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_BACKOFF_MS", "0")
    calls = {"n": 0}

    async def broken():
        calls["n"] += 1
        raise DeterministicError("logic bug")

    with pytest.raises(DeterministicError):
        await run_with_retry("stage_5_synthesize", broken)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_exhausted_attempts_raise_original(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_BACKOFF_MS", "0")
    monkeypatch.setenv("STAGE_RETRY_ATTEMPTS", "2")
    calls = {"n": 0}

    async def always_transient():
        calls["n"] += 1
        raise FakeStatusError(503)

    with pytest.raises(FakeStatusError):
        await run_with_retry("stage_4_retrieve", always_transient)
    assert calls["n"] == 3  # 1 initial + 2 retries


@pytest.mark.asyncio
async def test_retry_emits_sub_step(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_BACKOFF_MS", "0")
    events = []

    async def emit(event_type, data):
        events.append((event_type, data))

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeTimeout("boom")
        return "ok"

    await run_with_retry("stage_2_ddx", flaky, emit=emit, stage=2)
    assert events == [("sub_step", {
        "stage": 2, "detail": "Transient error — retrying (2/3)", "badge": "retry",
    })]


@pytest.mark.asyncio
async def test_disabled_stage_never_retries(monkeypatch):
    monkeypatch.setenv("STAGE_RETRY_STAGES", "stage_5_synthesize")
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        raise FakeTimeout("boom")

    with pytest.raises(FakeTimeout):
        await run_with_retry("stage_2_ddx", flaky)
    assert calls["n"] == 1
