"""
Tests for ddx/backfill_scope_embeddings._build_scope_text.

The scope-embedding text is built from cpg_scope_rationale (scope_rationale
column) + procedure_scope tags ONLY. ICD-11 condition titles are intentionally
excluded to avoid diluting broad-CPG embeddings. Pure function; no DB calls.
"""

from __future__ import annotations

from ddx.backfill_scope_embeddings import _build_scope_text


def test_includes_rationale_and_procedure_tags():
    row = {
        "title": "Section 1",
        "scope_rationale": "This guideline covers atrial fibrillation management.",
        "icd11_scope": ["BC81.3", "BC81.30"],
        "procedure_scope": ["warfarin_initiation", "inr_monitoring"],
    }
    text = _build_scope_text(row)
    assert "atrial fibrillation management" in text
    assert "Procedures: warfarin_initiation; inr_monitoring." in text


def test_excludes_icd_condition_titles():
    """ICD codes/titles must NOT appear in the embedding text."""
    row = {
        "title": "Section 1",
        "scope_rationale": "Rationale text.",
        "icd11_scope": ["BC81.3", "BC81.30", "BC81.31"],
        "procedure_scope": [],
    }
    text = _build_scope_text(row)
    assert "BC81.3" not in text
    assert "Conditions covered" not in text
    assert text == "Rationale text."


def test_rationale_only_when_no_procedures():
    row = {
        "title": "Section 1",
        "scope_rationale": "Just the rationale.",
        "icd11_scope": [],
        "procedure_scope": [],
    }
    assert _build_scope_text(row) == "Just the rationale."


def test_falls_back_to_title_when_empty():
    row = {
        "title": "Section 7: Implementation",
        "scope_rationale": None,
        "icd11_scope": [],
        "procedure_scope": [],
    }
    assert _build_scope_text(row) == "Section 7: Implementation"


def test_procedure_only_cpg_has_no_rationale_dependency():
    """Procedure-only CPG (empty icd, has procedure tags) still produces text."""
    row = {
        "title": "Section 2",
        "scope_rationale": "Anaesthesia medication safety guidance.",
        "icd11_scope": [],
        "procedure_scope": ["medication_labelling", "high_alert_medication"],
    }
    text = _build_scope_text(row)
    assert "Anaesthesia medication safety guidance." in text
    assert "Procedures: medication_labelling; high_alert_medication." in text
