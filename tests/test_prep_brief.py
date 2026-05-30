"""Tests for agent/clinical_stages.generate_prep_brief — the pre-consultation
prep agent. Fully mocked: no real LLM."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.clinical_stages import generate_prep_brief


def _mock_openai(content: str):
    """Build a patch target that makes the LLM return `content`."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=resp)
    return client


_PRIOR = {
    "visit_date": "2026-04-12",
    "prior_icd_primary": "BA41.1",
    "prior_plan_summary": "Started Aspirin 75mg + Atorvastatin 40mg; Cardiology referral routine.",
    "key_labs_delta": "HbA1c 8.4 -> 7.9",
    "what_changed": "No recurrent chest pain post-PCI.",
}


@pytest.mark.asyncio
async def test_happy_path_parses_three_fields():
    raw = (
        '{"since_last_visit": "HbA1c improved 8.4->7.9; NSTEMI stable post-PCI.", '
        '"med_flags": "On aspirin + statin — no DDI concern.", '
        '"ask_today": "Confirm Cardiology appointment was booked."}'
    )
    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = _mock_openai(raw)
        out = await generate_prep_brief(_PRIOR, [{"name": "Aspirin"}], 64, "Male", ["T2DM"])

    assert set(out.keys()) == {"since_last_visit", "med_flags", "ask_today"}
    assert "HbA1c" in out["since_last_visit"]
    assert out["ask_today"].startswith("Confirm Cardiology")


@pytest.mark.asyncio
async def test_strips_markdown_fence():
    raw = '```json\n{"since_last_visit": "Stable.", "med_flags": null, "ask_today": "Review labs."}\n```'
    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = _mock_openai(raw)
        out = await generate_prep_brief(_PRIOR, [], 50, "Female", [])
    assert out["since_last_visit"] == "Stable."
    assert out["med_flags"] is None


@pytest.mark.asyncio
async def test_enforces_120_char_cap():
    long = "x" * 300
    raw = f'{{"since_last_visit": "{long}", "med_flags": null, "ask_today": null}}'
    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = _mock_openai(raw)
        out = await generate_prep_brief(_PRIOR, [], 50, "Male", [])
    assert len(out["since_last_visit"]) <= 120


@pytest.mark.asyncio
async def test_llm_failure_falls_back_not_raises():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = client
        out = await generate_prep_brief(_PRIOR, [], 64, "Male", ["T2DM"])
    # Fallback derives from prior_visit, never raises
    assert out["since_last_visit"] == "No recurrent chest pain post-PCI."
    assert out["ask_today"].startswith("Started Aspirin")


@pytest.mark.asyncio
async def test_null_prior_fields_do_not_crash_fallback():
    """Regression: prior_plan_summary present-but-None must not crash the
    fallback (None[:120] TypeError)."""
    prior_all_none = {
        "visit_date": "2026-04-12",
        "prior_icd_primary": None,
        "prior_plan_summary": None,
        "key_labs_delta": None,
        "what_changed": None,
    }
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("agent.clinical_stages.openai") as mock_openai:
        mock_openai.AsyncOpenAI.return_value = client
        out = await generate_prep_brief(prior_all_none, [], None, None, [])
    assert out["since_last_visit"]  # non-empty default string
    assert out["ask_today"] is None  # empty summary collapses to None


@pytest.mark.asyncio
async def test_missing_prompt_returns_fallback():
    with patch("agent.clinical_stages.PREP_BRIEF_PROMPT", ""):
        out = await generate_prep_brief(_PRIOR, [], 64, "Male", [])
    assert out["since_last_visit"] == "No recurrent chest pain post-PCI."
