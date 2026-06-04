"""
E2E smoke tests — three fixture cases, fully mocked (no real API calls).
Asserts output shape, not specific content.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from agent.models import PatientCase, TreatmentPlan, Recommendation
from agent.clinical_stages import DDxResult
from agent.routing import CPGDocRef


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_plan(icd_primary: str, icd_alternates: list[str], confidence: float,
              unresolved: list[str] | None = None) -> TreatmentPlan:
    return TreatmentPlan(
        icd_primary=icd_primary,
        summary="Management plan per CPG.",
        icd_alternates=icd_alternates,
        recommendations=[
            Recommendation(
                intervention="Rate control with bisoprolol 5mg OD",
                type="pharmacological",
                cpg_source="CPG Management §4.2",
                rationale="Guideline-recommended first-line therapy",
            )
        ],
        monitoring=[{"parameter": "clinical review", "schedule": "follow-up in 4 weeks"}],
        red_flags=["Haemodynamic compromise"],
        confidence=confidence,
        unresolved_questions=unresolved or [],
    )


def make_ddx(code: str, title: str) -> list[DDxResult]:
    return [DDxResult(code=code, title=title, similarity=0.90)]


def make_cpg(name: str) -> list[CPGDocRef]:
    return [CPGDocRef(
        cpg_name=name,
        document_id="doc-001",
        document_ids=["doc-001"],
        title=name,
        match_type="exact",
        score=0.9,
        matched_scope="BC81.3",
    )]


# ---------------------------------------------------------------------------
# Fixture 1: AF patient
# ---------------------------------------------------------------------------

af_case = PatientCase(
    chief_complaint="palpitations and irregular heartbeat for 2 weeks",
    age=68,
    sex="M",
    comorbidities=["hypertension"],
    current_medications=["amlodipine 5mg OD"],
    vitals={"sbp": 145, "dbp": 88, "hr": 110},
)


@pytest.mark.asyncio
async def test_af_case_returns_treatment_plan():
    """AF patient: icd_primary starts with BC81, AF CPG matched, ≥1 recommendation."""
    af_plan = make_plan(
        icd_primary="BC81.3",
        icd_alternates=["BC81.1"],
        confidence=0.91,
    )
    af_ddx = make_ddx("BC81.3", "Persistent atrial fibrillation")
    af_cpgs = make_cpg("CPG AF Management")

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=af_ddx),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=af_cpgs),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=af_plan),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(af_case)

    assert isinstance(result.treatment_plan, TreatmentPlan)
    assert result.treatment_plan.icd_primary.startswith("BC81")
    assert any("AF" in c.cpg_name for c in result.cpgs)
    assert len(result.treatment_plan.recommendations) >= 1


# ---------------------------------------------------------------------------
# Fixture 2: ED patient
# ---------------------------------------------------------------------------

ed_case = PatientCase(
    chief_complaint="erectile dysfunction for 6 months, unable to achieve erection",
    age=52,
    sex="M",
    comorbidities=["type 2 diabetes"],
    current_medications=["metformin 1g BD"],
    vitals={},
)


@pytest.mark.asyncio
async def test_ed_case_pharmacological_recommendation():
    """ED patient: icd_primary starts with HA01, ≥1 pharmacological recommendation."""
    ed_plan = make_plan(
        icd_primary="HA01.0",
        icd_alternates=[],
        confidence=0.78,
    )
    ed_ddx = make_ddx("HA01.0", "Erectile dysfunction")
    ed_cpgs = make_cpg("CPG ED Management")

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=ed_ddx),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=ed_cpgs),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=ed_plan),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(ed_case)

    assert isinstance(result.treatment_plan, TreatmentPlan)
    assert result.treatment_plan.icd_primary.startswith("HA01")
    pharmacological = [
        r for r in result.treatment_plan.recommendations
        if r.type == "pharmacological"
    ]
    assert len(pharmacological) >= 1


# ---------------------------------------------------------------------------
# Fixture 3: Out-of-scope (dermatology — no CPG match expected)
# ---------------------------------------------------------------------------

oos_case = PatientCase(
    chief_complaint="widespread itchy rash on trunk and limbs",
    age=35,
    sex="F",
    comorbidities=[],
    current_medications=[],
    vitals={},
)


@pytest.mark.asyncio
async def test_oos_case_no_crash():
    """Out-of-scope patient: TreatmentPlan returned, unresolved_questions non-empty OR confidence < 0.5."""
    oos_plan = make_plan(
        icd_primary="EA90",
        icd_alternates=[],
        confidence=0.32,
        unresolved=["No CPG available for this dermatological presentation"],
    )
    oos_ddx = make_ddx("EA90", "Urticaria")
    oos_cpgs: list[CPGDocRef] = []   # no CPG match

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=oos_ddx),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=oos_cpgs),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=oos_plan),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(oos_case)

    assert isinstance(result.treatment_plan, TreatmentPlan)
    plan = result.treatment_plan
    assert plan.unresolved_questions or plan.confidence < 0.5
