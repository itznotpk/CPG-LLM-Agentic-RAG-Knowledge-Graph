"""Regression tests that clinical call sites consume approved LLM policies."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.clinical_stages import generate_prep_brief, summarise_consultation


def _response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def _client(content):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_response(content))
    return client


@pytest.mark.asyncio
async def test_prep_brief_uses_atomic_gemini_target_and_8000_budget(monkeypatch):
    monkeypatch.delenv("PREP_BRIEF_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("PREP_BRIEF_LLM_API_KEY", raising=False)
    monkeypatch.delenv("PREP_BRIEF_LLM_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_BASE_URL", "https://gemini.test/v1")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_CHOICE", "wrong-global-model")
    client = _client('{"since_last_visit":"Stable","med_flags":null,"ask_today":null}')

    with patch("agent.clinical_stages._make_openai_client", return_value=client) as factory:
        await generate_prep_brief({"what_changed": "Stable"}, [], 60, "M", [])

    factory.assert_called_once_with(
        base_url="https://gemini.test/v1", api_key="gemini-key",
        provider="openai", max_retries=0,
    )
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["max_tokens"] == 8000
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_consultation_summary_uses_8000_budget(monkeypatch):
    monkeypatch.setenv("GEMINI_BASE_URL", "https://gemini.test/v1")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("CONSULTATION_SUMMARY_MODEL", "gemini-2.5-flash")
    client = _client("SOAP summary")

    with patch("agent.clinical_stages._make_openai_client", return_value=client):
        assert await summarise_consultation("Doctor: hello") == "SOAP summary"

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["max_tokens"] == 8000
    assert kwargs["model"] == "gemini-2.5-flash"
