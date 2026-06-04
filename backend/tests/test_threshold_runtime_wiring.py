"""Tests for runtime threshold evaluation (Stage 4.5 + Stage 6 wiring)."""
from types import SimpleNamespace

from agent.graph_clinical import (
    ClinicalFlag,
    evaluate_threshold,
    build_patient_params,
    _resolve_patient_value,
)
from agent.safety_critic import _kg_flag_to_safety


def test_evaluate_threshold_lt_breach():
    assert evaluate_threshold("eGFR", "<", 30, None, {"egfr": 22}) is True
    assert evaluate_threshold("eGFR", "<", 30, None, {"egfr": 80}) is False


def test_evaluate_threshold_between():
    assert evaluate_threshold("age", "between", 50, 69, {"age": 60}) is True
    assert evaluate_threshold("age", "between", 50, 69, {"age": 40}) is False


def test_evaluate_threshold_unknown_param_returns_none():
    assert evaluate_threshold("eGFR", "<", 30, None, {"sbp": 140}) is None
    assert evaluate_threshold("eGFR", "<", 30, None, {}) is None


def test_resolve_patient_value_via_alias():
    assert _resolve_patient_value("eGFR", {"gfr": 25}) == 25.0
    assert _resolve_patient_value("K+", {"potassium": 5.8}) == 5.8


def test_build_patient_params_extracts_numbers_from_strings():
    case = SimpleNamespace(
        age=72,
        vitals={"sbp": 165.0, "dbp": 95.0},
        severity_staging={"eGFR": "28 mL/min", "HbA1c": "9.2%"},
    )
    pp = build_patient_params(case)
    assert pp["age"] == 72
    assert pp["sbp"] == 165.0
    assert pp["egfr"] == 28.0
    assert pp["hba1c"] == 9.2


def _mk_flag(**kw):
    base = dict(
        flag_type="DOSE_ADJUSTMENT",
        subject="Metformin",
        object="Renal Impairment",
        relation="REQUIRES_DOSE_ADJUSTMENT",
        severity="MODERATE",
        evidence="Reduce metformin dose when eGFR <30",
        threshold_param="eGFR", threshold_op="<", threshold_value=30,
    )
    base.update(kw)
    return ClinicalFlag(**base)


def test_kg_flag_to_safety_escalates_on_breach():
    cf = _mk_flag(threshold_breach=True)
    sf = _kg_flag_to_safety(cf, drug_idx_map={"metformin": 0}, pharm_recommendation_indices=[0])
    assert sf.severity == "MAJOR"  # escalated from MODERATE
    assert "Patient meets threshold" in sf.detail
    assert "eGFR < 30" in sf.detail


def test_kg_flag_to_safety_informational_when_not_met():
    cf = _mk_flag(threshold_breach=False)
    sf = _kg_flag_to_safety(cf, drug_idx_map={"metformin": 0}, pharm_recommendation_indices=[0])
    assert sf.severity == "MODERATE"  # no escalation
    assert "not met" in sf.detail.lower()


def test_kg_flag_to_safety_unknown_patient_value_keeps_severity():
    cf = _mk_flag(threshold_breach=None)
    sf = _kg_flag_to_safety(cf, drug_idx_map={"metformin": 0}, pharm_recommendation_indices=[0])
    assert sf.severity == "MODERATE"
    assert "patient value unknown" in sf.detail.lower()


def test_kg_flag_to_safety_no_threshold_unchanged():
    cf = ClinicalFlag(
        flag_type="CONTRAINDICATION", subject="Warfarin", object="Pregnancy",
        relation="CONTRAINDICATED_WITH", severity="MAJOR", evidence="x",
    )
    sf = _kg_flag_to_safety(cf, drug_idx_map={"warfarin": 0}, pharm_recommendation_indices=[0])
    assert sf.severity == "MAJOR"
    assert "threshold" not in sf.detail.lower()
