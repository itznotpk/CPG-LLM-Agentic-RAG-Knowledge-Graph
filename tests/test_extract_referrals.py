"""Tests for ingestion/extract_referrals.py — filter + validator only.

The LLM call and Neo4j write paths are intentionally not covered here; they
are exercised by integration runs against a live ingestion model + Aura.
"""
from __future__ import annotations

import pytest

from ingestion.extract_referrals import (
    CANONICAL_SPECIALTIES,
    VALID_URGENCY,
    _normalise_specialty,
    _validate_triple,
    filter_referral_candidates,
)


# ---------------------------------------------------------------------------
# Pre-filter
# ---------------------------------------------------------------------------

def _row(content: str, category: str | None = "Treatment", cpg: str = "X") -> dict:
    return {
        "chunk_id": "c1",
        "content": content,
        "category": category,
        "cpg_source": cpg,
    }


def test_filter_keeps_obvious_referral_sentence():
    rows = [_row("All AF patients should be referred to cardiology.")]
    assert len(filter_referral_candidates(rows)) == 1


def test_filter_keeps_consult_phrasing():
    rows = [_row("Consultation with nephrology is recommended for eGFR <30.")]
    assert len(filter_referral_candidates(rows)) == 1


def test_filter_keeps_mdt_phrasing():
    rows = [_row("Multidisciplinary team discussion is advised.")]
    assert len(filter_referral_candidates(rows)) == 1


def test_filter_drops_chunk_without_signal():
    rows = [_row("Metformin should be reduced when eGFR falls below 30.")]
    assert filter_referral_candidates(rows) == []


def test_filter_drops_pure_negation():
    rows = [_row("CKD stage 3a does not require routine specialist referral.")]
    assert filter_referral_candidates(rows) == []


def test_filter_keeps_mixed_negation_and_positive():
    rows = [_row(
        "CKD stage 3a does not require routine referral. "
        "However, patients with stage 3b should be referred to nephrology."
    )]
    assert len(filter_referral_candidates(rows)) == 1


def test_filter_drops_off_whitelist_category():
    rows = [_row("Refer to cardiology.", category="Epidemiology")]
    assert filter_referral_candidates(rows) == []


def test_filter_keeps_null_category():
    rows = [_row("Refer to cardiology.", category=None)]
    assert len(filter_referral_candidates(rows)) == 1


# ---------------------------------------------------------------------------
# Specialty normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("cardiologist", "Cardiology"),
    ("nephrologist", "Nephrology"),
    ("Heart Failure Clinic", "Cardiology"),
    ("MDT", "Multidisciplinary Team"),
    ("dietitian", "Dietetics"),
    ("Maternal Fetal Medicine", "Maternal-Foetal Medicine"),
    ("Cardiology", "Cardiology"),
])
def test_normalise_specialty_canonical(raw, expected):
    assert _normalise_specialty(raw) == expected


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validate_triple_happy_path():
    raw = {
        "condition": "Heart Failure",
        "specialty": "Cardiology",
        "urgency": "routine",
        "trigger": "newly diagnosed",
        "evidence": "All patients with newly diagnosed HF should be referred to cardiology.",
        "icd_hint": "BD11",
    }
    t = _validate_triple(raw, chunk_id="c1", cpg_source="CPG-HF")
    assert t is not None
    assert t.specialty == "Cardiology"
    assert t.urgency == "routine"
    assert t.trigger == "newly diagnosed"
    assert t.icd_hint == "BD11"


def test_validate_triple_normalises_specialty_variant():
    raw = {
        "condition": "AF",
        "specialty": "cardiologist",
        "urgency": "routine",
        "evidence": "Refer to cardiologist.",
    }
    t = _validate_triple(raw, chunk_id="c1", cpg_source="X")
    assert t and t.specialty == "Cardiology"


def test_validate_triple_coerces_bad_urgency_to_routine():
    raw = {
        "condition": "AF",
        "specialty": "Cardiology",
        "urgency": "very urgent indeed",
        "evidence": "Refer.",
    }
    t = _validate_triple(raw, chunk_id="c1", cpg_source="X")
    assert t and t.urgency == "routine"


def test_validate_triple_rejects_missing_required_fields():
    # Missing specialty
    raw = {"condition": "AF", "urgency": "routine", "evidence": "refer"}
    assert _validate_triple(raw, "c1", "X") is None
    # Missing evidence
    raw = {"condition": "AF", "specialty": "Cardiology", "urgency": "routine"}
    assert _validate_triple(raw, "c1", "X") is None


def test_canonical_vocab_constants_sanity():
    assert "Cardiology" in CANONICAL_SPECIALTIES
    assert VALID_URGENCY == {"urgent", "routine", "consider"}
