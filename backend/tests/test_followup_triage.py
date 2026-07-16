"""Triage tests: tripwires, LLM parse, fail-safe ESCALATE, scale routing."""
from unittest.mock import AsyncMock, patch

import pytest

from agent.followup import triage as tr


def test_tripwires_hit_and_miss():
    assert tr.check_tripwires("I have chest pain tonight") is not None
    assert tr.check_tripwires("CANT BREATHE properly") is not None
    assert tr.check_tripwires("feeling much better today") is None
    # Conservative by design: negations still trip.
    assert tr.check_tripwires("no chest pain at all") is not None


async def test_classify_reply_parses_valid_json():
    raw = '{"classification": "REASSURE", "rationale": "scale 1", "patient_reply": "Great to hear!"}'
    with patch.object(tr, "_call_llm", AsyncMock(return_value=raw)):
        result = await tr.classify_reply("plan ctx", "How are you?", "1")
    assert result.classification == "REASSURE"


async def test_classify_reply_failsafe_escalates_on_bad_json():
    with patch.object(tr, "_call_llm", AsyncMock(return_value="not json at all")):
        result = await tr.classify_reply("plan ctx", None, "hmm")
    assert result.classification == "ESCALATE"
    assert result.patient_reply == tr.ESCALATE_FALLBACK_REPLY


async def test_classify_reply_failsafe_escalates_on_exception():
    with patch.object(tr, "_call_llm", AsyncMock(side_effect=TimeoutError("slow"))):
        result = await tr.classify_reply("plan ctx", None, "hmm")
    assert result.classification == "ESCALATE"
