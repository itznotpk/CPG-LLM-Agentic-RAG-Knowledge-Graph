"""Delivery cover personalization + enqueue input hardening.

Pure unit tests — no DB, no SMTP, no network.
"""
from __future__ import annotations

from agent.delivery import _cover_body, _cover_html
from agent.api import DeliveryEnqueueRequest, _valid_email, _VALID_DELIVERY_LANGS


# ---------------------------------------------------------------------------
# Multilingual cover rendering
# ---------------------------------------------------------------------------

def test_cover_body_renders_each_language_distinctly():
    en = _cover_body("en", patient_name="Ali", date="2026-06-14", clinician_name="Dr Tan")
    ms = _cover_body("ms", patient_name="Ali", date="2026-06-14", clinician_name="Dr Tan")
    zh = _cover_body("zh", patient_name="Ali", date="2026-06-14", clinician_name="Dr Tan")
    assert "care plan" in en.lower()
    assert "pelan rawatan" in ms.lower()      # Malay
    assert "护理计划" in zh                      # Chinese
    assert en != ms != zh
    # dynamic fields interpolated in every language
    for txt in (en, ms, zh):
        assert "Ali" in txt and "Dr Tan" in txt and "2026-06-14" in txt


def test_cover_html_localized_and_personalized():
    zh = _cover_html("zh", patient_name="Mei", date="2026-06-14",
                     clinician_name="Dr Lee", clinic_name="ClearPath")
    assert "护理计划" in zh
    assert "Mei" in zh and "Dr Lee" in zh and "ClearPath" in zh


def test_cover_falls_back_to_english_for_unknown_language():
    fallback = _cover_body("xx", patient_name="Sam", date="2026-06-14", clinician_name="Dr Ng")
    english = _cover_body("en", patient_name="Sam", date="2026-06-14", clinician_name="Dr Ng")
    assert fallback == english


# ---------------------------------------------------------------------------
# Enqueue input hardening
# ---------------------------------------------------------------------------

def test_valid_email():
    assert _valid_email("jiaqi040204@gmail.com")
    assert not _valid_email("not-an-email")
    assert not _valid_email("missing@domain")
    assert not _valid_email("")
    assert not _valid_email("a b@x.com")


def test_supported_langs():
    assert _VALID_DELIVERY_LANGS == {"en", "ms", "zh"}


def test_request_accepts_language_and_defaults():
    r = DeliveryEnqueueRequest(consultation_id=1)
    assert r.language is None
    r2 = DeliveryEnqueueRequest(consultation_id=1, recipient="a@b.com", language="ms")
    assert r2.language == "ms"
