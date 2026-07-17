"""Request-local LLM outcome recording and structured-call behavior."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.llm_runtime import (
    LLMResponseError,
    begin_llm_run,
    call_structured,
    current_llm_records,
    end_llm_run,
    record_degradation,
    resolve_target,
)


def _target():
    return resolve_target(
        "prep_brief",
        {
            "LLM_BASE_URL": "https://provider.test/v1",
            "LLM_API_KEY": "super-secret",
            "LLM_CHOICE": "gemini-2.5-flash",
        },
    )


def _response(content: str | None, *, finish_reason: str = "stop", usage=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content),
            )
        ],
        usage=usage
        or SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _client(*responses):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=list(responses))
    return client


@pytest.mark.asyncio
async def test_concurrent_run_contexts_do_not_mix_records():
    async def one(request_id):
        token = begin_llm_run(request_id)
        try:
            record_degradation("prep_brief", "empty_content")
            await asyncio.sleep(0)
            return [r.request_id for r in current_llm_records()]
        finally:
            end_llm_run(token)

    assert await asyncio.gather(one("a"), one("b")) == [["a"], ["b"]]


@pytest.mark.asyncio
async def test_structured_success_records_safe_metadata_only():
    token = begin_llm_run("req-1", consultation_id=42)
    try:
        result = await call_structured(
            _client(_response('{"ok": true}')),
            operation="prep_brief",
            target=_target(),
            messages=[{"role": "user", "content": "patient secret"}],
            prompt_template="Return JSON for private clinical input",
            temperature=0.1,
        )
        records = current_llm_records()
    finally:
        end_llm_run(token)

    assert result.data == {"ok": True}
    assert len(records) == 1
    payload = records[0].to_payload()
    assert payload["operation"] == "prep_brief"
    assert payload["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    serialized = json.dumps(payload)
    for forbidden in (
        "super-secret",
        "provider.test",
        "patient secret",
        "private clinical input",
        "api_key",
        "base_url",
        "messages",
        "content",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_transient_error_retries_and_records_attempt_count():
    transient = RuntimeError("503 model overloaded")
    transient.status_code = 503
    client = _client(transient, _response('{"ok": true}'))
    token = begin_llm_run("req-retry")
    try:
        result = await call_structured(
            client,
            operation="prep_brief",
            target=_target(),
            messages=[],
            prompt_template="prep",
            retry_delays=(0,),
        )
        record = current_llm_records()[0]
    finally:
        end_llm_run(token)

    assert result.data == {"ok": True}
    assert record.attempts == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (_response(None), "empty_content"),
        (_response('{"partial":', finish_reason="length"), "length_truncated"),
        (_response("not-json"), "invalid_json"),
    ],
)
async def test_invalid_structured_outputs_are_classified(response, reason):
    token = begin_llm_run("req-bad")
    try:
        with pytest.raises(LLMResponseError) as exc_info:
            await call_structured(
                _client(response),
                operation="prep_brief",
                target=_target(),
                messages=[],
                prompt_template="prep",
                retry_delays=(),
            )
        record = current_llm_records()[0]
    finally:
        end_llm_run(token)

    assert exc_info.value.reason == reason
    assert record.outcome == "degraded"
    assert record.reason == reason


def test_end_llm_run_returns_completed_records_and_restores_parent_context():
    parent = begin_llm_run("parent")
    child = begin_llm_run("child")
    record_degradation("prep_brief", "invalid_schema")

    completed = end_llm_run(child)

    assert [record.request_id for record in completed] == ["child"]
    assert current_llm_records() == []
    end_llm_run(parent)
