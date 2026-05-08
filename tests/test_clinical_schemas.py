"""
Tests for PatientCase, Recommendation, and TreatmentPlan schemas (Step 01).
"""

import pytest
from pydantic import ValidationError

from agent.models import PatientCase, Recommendation, TreatmentPlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_recommendation(**overrides) -> dict:
    base = {
        "intervention": "Sildenafil 50 mg PRN",
        "type": "pharmacological",
        "cpg_source": "CPG ED Management §3.1",
        "rationale": "First-line PDE5 inhibitor per CPG recommendation",
    }
    base.update(overrides)
    return base


def _minimal_treatment_plan(**overrides) -> dict:
    base = {
        "icd_primary": "BC81.1",
        "recommendations": [_minimal_recommendation()],
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# PatientCase — valid construction
# ---------------------------------------------------------------------------

class TestPatientCaseValid:
    def test_minimal_required_fields(self):
        pc = PatientCase(chief_complaint="chest pain")
        assert pc.chief_complaint == "chest pain"
        assert pc.history is None
        assert pc.age is None
        assert pc.sex is None
        assert pc.comorbidities == []
        assert pc.current_medications == []
        assert pc.allergies == []
        assert pc.vitals == {}

    def test_all_fields_populated(self):
        pc = PatientCase(
            chief_complaint="palpitations and shortness of breath",
            history="10-year history of hypertension",
            age=55,
            sex="M",
            comorbidities=["hypertension", "type 2 diabetes"],
            current_medications=["metformin 500 mg BD", "amlodipine 5 mg OD"],
            allergies=["penicillin"],
            vitals={"sbp": 165.0, "dbp": 95.0, "hr": 110.0},
        )
        assert pc.age == 55
        assert pc.sex == "M"
        assert len(pc.comorbidities) == 2
        assert pc.vitals["sbp"] == 165.0

    def test_chief_complaint_stripped(self):
        pc = PatientCase(chief_complaint="  chest pain  ")
        assert pc.chief_complaint == "chest pain"

    def test_sex_female(self):
        pc = PatientCase(chief_complaint="abdominal pain", sex="F")
        assert pc.sex == "F"

    def test_sex_other(self):
        pc = PatientCase(chief_complaint="fatigue", sex="other")
        assert pc.sex == "other"

    def test_age_boundary_zero(self):
        pc = PatientCase(chief_complaint="neonatal jaundice", age=0)
        assert pc.age == 0

    def test_age_boundary_130(self):
        pc = PatientCase(chief_complaint="fatigue", age=130)
        assert pc.age == 130

    def test_json_round_trip(self):
        pc = PatientCase(
            chief_complaint="chest pain",
            age=55,
            sex="M",
            vitals={"sbp": 140.0},
        )
        restored = PatientCase.model_validate_json(pc.model_dump_json())
        assert restored == pc


# ---------------------------------------------------------------------------
# PatientCase — validation failures
# ---------------------------------------------------------------------------

class TestPatientCaseInvalid:
    def test_empty_chief_complaint(self):
        with pytest.raises(ValidationError):
            PatientCase(chief_complaint="")

    def test_whitespace_only_chief_complaint(self):
        with pytest.raises(ValidationError):
            PatientCase(chief_complaint="   ")

    def test_negative_age(self):
        with pytest.raises(ValidationError):
            PatientCase(chief_complaint="rash", age=-1)

    def test_age_over_130(self):
        with pytest.raises(ValidationError):
            PatientCase(chief_complaint="rash", age=131)

    def test_invalid_sex_literal(self):
        with pytest.raises(ValidationError):
            PatientCase(chief_complaint="rash", sex="X")


# ---------------------------------------------------------------------------
# Recommendation — valid construction
# ---------------------------------------------------------------------------

class TestRecommendationValid:
    def test_minimal_required_fields(self):
        rec = Recommendation(**_minimal_recommendation())
        assert rec.intervention == "Sildenafil 50 mg PRN"
        assert rec.type == "pharmacological"
        assert rec.evidence_grade is None
        assert rec.contraindications_checked == []

    def test_all_fields_populated(self):
        rec = Recommendation(
            intervention="Beta-blocker titration",
            type="pharmacological",
            evidence_grade="Grade A, Level 1",
            cpg_source="CPG AF Management §4.2",
            rationale="Rate control per CPG recommendation",
            contraindications_checked=["asthma", "bradycardia"],
        )
        assert rec.evidence_grade == "Grade A, Level 1"
        assert len(rec.contraindications_checked) == 2

    def test_all_type_literals(self):
        for t in ("pharmacological", "procedure", "lifestyle", "referral", "investigation"):
            rec = Recommendation(**_minimal_recommendation(type=t))
            assert rec.type == t

    def test_json_round_trip(self):
        rec = Recommendation(**_minimal_recommendation(evidence_grade="Grade B, Level 2"))
        restored = Recommendation.model_validate_json(rec.model_dump_json())
        assert restored == rec


# ---------------------------------------------------------------------------
# Recommendation — validation failures
# ---------------------------------------------------------------------------

class TestRecommendationInvalid:
    def test_bad_type_literal(self):
        with pytest.raises(ValidationError):
            Recommendation(**_minimal_recommendation(type="hocus_pocus"))

    def test_missing_intervention(self):
        data = _minimal_recommendation()
        del data["intervention"]
        with pytest.raises(ValidationError):
            Recommendation(**data)

    def test_missing_cpg_source(self):
        data = _minimal_recommendation()
        del data["cpg_source"]
        with pytest.raises(ValidationError):
            Recommendation(**data)

    def test_missing_rationale(self):
        data = _minimal_recommendation()
        del data["rationale"]
        with pytest.raises(ValidationError):
            Recommendation(**data)


# ---------------------------------------------------------------------------
# TreatmentPlan — valid construction
# ---------------------------------------------------------------------------

class TestTreatmentPlanValid:
    def test_minimal_required_fields(self):
        plan = TreatmentPlan(**_minimal_treatment_plan())
        assert plan.icd_primary == "BC81.1"
        assert len(plan.recommendations) == 1
        assert plan.confidence == 0.85
        assert plan.icd_alternates == []
        assert plan.monitoring == []
        assert plan.red_flags == []
        assert plan.unresolved_questions == []

    def test_all_fields_populated(self):
        plan = TreatmentPlan(
            icd_primary="BC81.1",
            icd_alternates=["BC81.0", "BC81.Z"],
            recommendations=[
                Recommendation(**_minimal_recommendation()),
                Recommendation(**_minimal_recommendation(type="lifestyle", intervention="Salt restriction")),
            ],
            monitoring=["heart rate at each visit", "INR monthly"],
            red_flags=["syncope", "stroke symptoms"],
            confidence=0.92,
            unresolved_questions=["Patient's renal function not provided"],
        )
        assert len(plan.recommendations) == 2
        assert len(plan.icd_alternates) == 2
        assert plan.confidence == 0.92

    def test_confidence_boundary_zero(self):
        plan = TreatmentPlan(**_minimal_treatment_plan(confidence=0.0))
        assert plan.confidence == 0.0

    def test_confidence_boundary_one(self):
        plan = TreatmentPlan(**_minimal_treatment_plan(confidence=1.0))
        assert plan.confidence == 1.0

    def test_json_round_trip(self):
        plan = TreatmentPlan(**_minimal_treatment_plan())
        restored = TreatmentPlan.model_validate_json(plan.model_dump_json())
        assert restored == plan

    def test_json_round_trip_full(self):
        plan = TreatmentPlan(
            icd_primary="BC81.1",
            icd_alternates=["BC81.0"],
            recommendations=[
                Recommendation(**_minimal_recommendation(evidence_grade="Grade A, Level 1")),
            ],
            monitoring=["ECG at 3 months"],
            red_flags=["acute chest pain"],
            confidence=0.9,
            unresolved_questions=["Thyroid function unknown"],
        )
        restored = TreatmentPlan.model_validate_json(plan.model_dump_json())
        assert restored == plan


# ---------------------------------------------------------------------------
# TreatmentPlan — validation failures
# ---------------------------------------------------------------------------

class TestTreatmentPlanInvalid:
    def test_empty_recommendations(self):
        with pytest.raises(ValidationError):
            TreatmentPlan(**_minimal_treatment_plan(recommendations=[]))

    def test_confidence_too_high(self):
        with pytest.raises(ValidationError):
            TreatmentPlan(**_minimal_treatment_plan(confidence=1.5))

    def test_confidence_negative(self):
        with pytest.raises(ValidationError):
            TreatmentPlan(**_minimal_treatment_plan(confidence=-0.1))

    def test_missing_icd_primary(self):
        data = _minimal_treatment_plan()
        del data["icd_primary"]
        with pytest.raises(ValidationError):
            TreatmentPlan(**data)

    def test_missing_confidence(self):
        data = _minimal_treatment_plan()
        del data["confidence"]
        with pytest.raises(ValidationError):
            TreatmentPlan(**data)
