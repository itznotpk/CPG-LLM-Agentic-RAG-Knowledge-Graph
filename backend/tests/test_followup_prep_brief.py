"""Prep-brief injection: alerts reach the LLM payload; empty tables = today's behavior."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.clinical_stages import generate_prep_brief


async def test_alerts_included_in_llm_payload(monkeypatch):
    captured = {}

    class FakeResp:
        class Choice:
            class Msg:
                content = '{"since_last_visit": "ok", "med_flags": null, "ask_today": null}'
            message = Msg()
        choices = [Choice()]

    async def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return FakeResp()

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create
    with patch("agent.clinical_stages._make_openai_client", return_value=fake_client):
        await generate_prep_brief(
            prior_visit={"what_changed": "x"}, current_medications=[],
            patient_age=60, patient_sex="M", comorbidities=[],
            followup_alerts=[{"severity": "critical", "summary": "tripwire: breathless", "created_at": "2026-07-14"}],
            checkin_digest="3 check-ins sent, 2 replies, 1 escalation",
        )
    user_payload = captured["messages"][1]["content"]
    assert "breathless" in user_payload
    assert "escalation" in user_payload


async def test_no_followup_args_behaves_as_today():
    """Omitting the new kwargs must not change the payload shape (regression guard)."""
    captured = {}

    class FakeResp:
        class Choice:
            class Msg:
                content = '{"since_last_visit": "ok", "med_flags": null, "ask_today": null}'
            message = Msg()
        choices = [Choice()]

    async def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return FakeResp()

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create
    with patch("agent.clinical_stages._make_openai_client", return_value=fake_client):
        out = await generate_prep_brief(
            prior_visit={"what_changed": "x"}, current_medications=[],
            patient_age=60, patient_sex="M", comorbidities=[],
        )
    assert "followup" not in captured["messages"][1]["content"]
    assert set(out.keys()) == {"since_last_visit", "med_flags", "ask_today"}
