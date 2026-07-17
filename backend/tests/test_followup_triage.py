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


@pytest.mark.parametrize("text,expected", [
    # Malay — the hazard set must not depend on the patient writing English.
    ("dada saya sakit sejak semalam", "chest_pain"),
    ("dada rasa ketat", "chest_pain"),
    ("sesak nafas sikit since semalam", "breathless"),   # the Manglish/BM mix patients actually send
    ("susah napas bila baring", "breathless"),           # napas/nafas spelling variance
    ("tak boleh bernafas", "breathless"),
    ("saya pengsan tadi pagi", "collapse"),
    ("rasa nak pitam", "collapse"),
    ("muntah darah pagi tadi", "bleeding"),
    ("kencing berdarah", "bleeding"),
    ("mulut senget dan cakap pelat", "stroke_signs"),
    ("sebelah kanan lemah", "stroke_signs"),
    ("bibir bengkak teruk", "anaphylaxis"),
    ("saya nak bunuh diri", "self_harm"),
])
def test_tripwires_fire_on_malay_hazards(text, expected):
    assert tr.check_tripwires(text) == expected


@pytest.mark.parametrize("text", [
    "terima kasih doktor",
    "got blood test tomorrow",   # a booked blood test is not a bleed report
    "penat nak mati hari ni",    # idiom "tired to death" — NOT suicidality
    "jalan sesak tadi",          # "sesak" = congested (traffic), not breathless
    "kaki bengkak sikit",        # limb swelling is a HF monitoring item, not anaphylaxis
    "ambil darah minggu depan",  # routine blood draw
])
def test_tripwires_do_not_fire_on_benign_or_idiomatic_malay(text):
    assert tr.check_tripwires(text) is None


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


def test_reply_constants_differentiate_emergency_guidance():
    from agent.followup import triage as tr
    assert "999" in tr.TRIPWIRE_REPLY            # confirmed hazard → urgent
    assert "999" not in tr.ESCALATE_FALLBACK_REPLY  # LLM-failure fallback → no over-alarm
    assert "clinic" in tr.ESCALATE_FALLBACK_REPLY.lower()
