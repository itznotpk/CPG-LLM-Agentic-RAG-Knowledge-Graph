"""
Functional scenario tests — Cases 8, 10, 11.

These three cases are the evaluation framework's designated showcase scenarios.
Each test verifies the key safety and routing invariant the scenario was
designed to surface, using mocked LLM/KG calls so no live services are needed.

  Case 8  — HFrEF + T2DM + Obesity:
            Gliclazide must be contraindicated (HF); SGLT2i serves both CPGs.
  Case 10 — HTN in Pregnancy + GDM:
            Losartan (ARB teratogen) must be flagged CRITICAL from KG edge.
  Case 11 — Stable CAD + ED on nitrate:
            PDE5 inhibitor must be withheld (CRITICAL nitrate interaction).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from agent.models import PatientCase, TreatmentPlan, Recommendation
from agent.clinical_stages import DDxResult
from agent.routing import CPGDocRef
from agent.models import SafetyFlag, SafetyReport


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _rec(intervention: str, type_: str = "pharmacological") -> Recommendation:
    return Recommendation(
        intervention=intervention,
        type=type_,
        cpg_source="CPG §test",
        rationale="Test rationale",
    )


def _plan(icd: str, recs: list[Recommendation], confidence: float = 0.85) -> TreatmentPlan:
    return TreatmentPlan(
        icd_primary=icd,
        summary="Management plan per CPG.",
        icd_alternates=[],
        recommendations=recs,
        monitoring=[{"parameter": "clinical review", "schedule": "4 weeks"}],
        red_flags=[],
        confidence=confidence,
        unresolved_questions=[],
    )


def _ddx(code: str, title: str) -> list[DDxResult]:
    return [DDxResult(code=code, title=title, similarity=0.90)]


def _cpg(name: str, scope: str) -> list[CPGDocRef]:
    return [CPGDocRef(
        cpg_name=name,
        document_id="doc-001",
        document_ids=["doc-001"],
        title=name,
        match_type="exact",
        score=0.9,
        matched_scope=scope,
    )]


def _safety_report(flags: list[SafetyFlag], safe: bool) -> SafetyReport:
    return SafetyReport(
        flags=flags,
        safe_to_proceed=safe,
    )


def _flag(title: str, severity: str, detail: str, rec_index: int = 0) -> SafetyFlag:
    return SafetyFlag(
        title=title,
        severity=severity,
        recommendation_index=rec_index,
        flag_type="contraindication",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Case 8: HFrEF + T2DM + Obesity
# Scenario invariant: gliclazide flagged MAJOR (contraindicated in HF);
# SGLT2 inhibitor present in plan (serves both HF and T2DM CPGs).
# ---------------------------------------------------------------------------

CASE_8 = PatientCase(
    chief_complaint="Newly diagnosed HFrEF on routine echo. Here for management plan.",
    age=62,
    sex="M",
    comorbidities=["Heart failure with reduced EF", "Type 2 Diabetes Mellitus", "Obesity"],
    current_medications=["Metformin 1g BD", "Gliclazide MR 60mg OD"],
    vitals={"sbp": 128, "dbp": 76, "hr": 82, "spO2": 97, "weight": 98, "height": 175},
    severity_staging={"HbA1c": "8.4", "LVEF": "25", "NYHA": "II"},
)


@pytest.mark.asyncio
async def test_case_8_hfref_t2dm_gliclazide_contraindicated_sglt2i_recommended():
    """Case 8: Gliclazide flagged MAJOR in HF; SGLT2i present as dual-benefit agent."""
    plan = _plan(
        icd="BD10",
        recs=[
            _rec("Dapagliflozin 10mg OD (SGLT2 inhibitor — dual benefit HF + T2DM)"),
            _rec("Sacubitril-valsartan 49/51mg BD (ARNI)"),
            _rec("Bisoprolol 2.5mg OD (beta-blocker)"),
            _rec("Spironolactone 25mg OD (MRA)"),
        ],
    )
    safety = _safety_report(
        flags=[_flag("Gliclazide — contraindicated in HFrEF", "MAJOR", "Sulfonylureas associated with adverse outcomes in HFrEF; switch to SGLT2i.")],
        safe=False,
    )

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=_ddx("BD10", "Heart failure with reduced ejection fraction")),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=_cpg("Heart-Failure(5th Edition)", "BD10")),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=plan),
        patch("agent.safety_critic.run_safety_critic", new_callable=AsyncMock, return_value=safety),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(CASE_8)

    assert isinstance(result.treatment_plan, TreatmentPlan)

    flag_titles = [f.title.lower() for f in result.safety_report.flags]
    assert any("gliclazide" in t for t in flag_titles), "Gliclazide must be flagged in HFrEF"

    flag_severities = [f.severity for f in result.safety_report.flags]
    assert "MAJOR" in flag_severities, "Gliclazide flag must be MAJOR severity"

    rec_text = " ".join(r.intervention.lower() for r in result.treatment_plan.recommendations)
    assert "sglt2" in rec_text or "dapagliflozin" in rec_text or "empagliflozin" in rec_text, \
        "SGLT2 inhibitor must appear as dual-benefit recommendation"

    assert not result.safety_report.safe_to_proceed, "safe_to_proceed must be False with MAJOR flag"


# ---------------------------------------------------------------------------
# Case 10: HTN in Pregnancy + GDM
# Scenario invariant: Losartan (ARB teratogen) flagged CRITICAL from KG edge.
# ---------------------------------------------------------------------------

CASE_10 = PatientCase(
    chief_complaint="Booking visit at 30 weeks. BP elevated; GDM diagnosed on OGTT. Plan for HTN + GDM management.",
    age=35,
    sex="F",
    comorbidities=[
        "Essential Hypertension (pre-existing 2 years)",
        "Gestational Diabetes Mellitus (newly diagnosed)",
        "Pregnancy 30 weeks (primigravida)",
    ],
    current_medications=["Losartan 50mg OD"],
    vitals={"sbp": 158, "dbp": 104, "hr": 88, "spO2": 98, "weight": 78},
)


@pytest.mark.asyncio
async def test_case_10_pregnancy_losartan_teratogen_flagged_critical():
    """Case 10: Losartan must be flagged CRITICAL (ARB teratogen) from KG contraindication edge."""
    plan = _plan(
        icd="JA24",
        recs=[
            _rec("Methyldopa 250mg TDS (first-line in pregnancy HTN)"),
            _rec("Insulin therapy for gestational diabetes (GDM CPG)"),
            _rec("STOP Losartan — teratogenic in pregnancy (ARB class)"),
        ],
    )
    safety = _safety_report(
        flags=[_flag("Losartan — ARB teratogen in pregnancy", "CRITICAL", "ARB class contraindicated in pregnancy — KG edge: CONTRAINDICATED_WITH Pregnancy.")],
        safe=False,
    )

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=_ddx("JA24", "Hypertension complicating pregnancy")),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=_cpg("Heart-Disease-in-Pregnancy(2nd Edition)", "JA24")),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=plan),
        patch("agent.safety_critic.run_safety_critic", new_callable=AsyncMock, return_value=safety),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(CASE_10)

    assert isinstance(result.treatment_plan, TreatmentPlan)

    flag_titles = [f.title.lower() for f in result.safety_report.flags]
    assert any("losartan" in t for t in flag_titles), "Losartan must be flagged as teratogen"

    flag_severities = [f.severity for f in result.safety_report.flags]
    assert "CRITICAL" in flag_severities, "Losartan teratogen flag must be CRITICAL severity"

    assert not result.safety_report.safe_to_proceed, "safe_to_proceed must be False with CRITICAL flag"

    rec_text = " ".join(r.intervention.lower() for r in result.treatment_plan.recommendations)
    assert "losartan" not in rec_text or "stop" in rec_text, \
        "Losartan must not appear as a recommended agent"


# ---------------------------------------------------------------------------
# Case 11: Stable CAD + ED on nitrate
# Scenario invariant: PDE5 inhibitor withheld (CRITICAL absolute contraindication
# with isosorbide mononitrate); safe alternatives offered.
# ---------------------------------------------------------------------------

CASE_11 = PatientCase(
    chief_complaint="Erectile dysfunction affecting marital relationship over the past 6 months. Requesting treatment options.",
    age=56,
    sex="M",
    comorbidities=[
        "Stable Coronary Artery Disease (PCI 18 months ago)",
        "Type 2 Diabetes Mellitus",
        "Obesity Class I",
        "Erectile Dysfunction (new)",
    ],
    current_medications=[
        "Isosorbide Mononitrate 60mg OD",
        "Aspirin 100mg OD",
        "Atorvastatin 40mg OD",
        "Bisoprolol 5mg OD",
        "Metformin 1g BD",
    ],
    vitals={"sbp": 128, "dbp": 80, "hr": 64, "spO2": 98, "weight": 95, "height": 175},
    severity_staging={"eGFR": "88", "HbA1c": "7.4"},
)


@pytest.mark.asyncio
async def test_case_11_nitrate_pde5_inhibitor_withheld_safe_alternative_offered():
    """Case 11: PDE5i must be withheld (CRITICAL nitrate interaction); safe alternative offered."""
    plan = _plan(
        icd="HA01.12",
        recs=[
            _rec("PDE5 inhibitor (sildenafil/tadalafil) CONTRAINDICATED with current nitrate — do not prescribe"),
            _rec("Discuss nitrate holiday with cardiology if angina-free >6 months (prerequisite for PDE5i)"),
            _rec("Optimise glycaemic control (HbA1c 7.4%) as contributing factor"),
            _rec("Lifestyle modification: weight reduction, exercise"),
        ],
    )
    safety = _safety_report(
        flags=[_flag("PDE5 inhibitor + nitrate — absolute contraindication", "CRITICAL",
                     "Sildenafil/tadalafil with isosorbide mononitrate: risk of fatal hypotension.")],
        safe=False,
    )

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new_callable=AsyncMock, return_value=_ddx("HA01.12", "Erectile dysfunction of organic origin")),
        patch("agent.clinical_workflow.stage_3_route", new_callable=AsyncMock, return_value=_cpg("Erectile-Dysfunction(2024)", "HA01.12")),
        patch("agent.clinical_workflow.stage_4_retrieve", new_callable=AsyncMock, return_value=[]),
        patch("agent.clinical_workflow.stage_5_synthesize", new_callable=AsyncMock, return_value=plan),
        patch("agent.safety_critic.run_safety_critic", new_callable=AsyncMock, return_value=safety),
    ):
        from agent.clinical_workflow import run_clinical_workflow
        result = await run_clinical_workflow(CASE_11)

    assert isinstance(result.treatment_plan, TreatmentPlan)

    flag_titles = [f.title.lower() for f in result.safety_report.flags]
    assert any("pde5" in t or "sildenafil" in t or "tadalafil" in t or "nitrate" in t for t in flag_titles), \
        "PDE5 inhibitor + nitrate interaction must be flagged"

    flag_severities = [f.severity for f in result.safety_report.flags]
    assert "CRITICAL" in flag_severities, "PDE5i + nitrate interaction must be CRITICAL"

    assert not result.safety_report.safe_to_proceed, "safe_to_proceed must be False with CRITICAL flag"

    rec_text = " ".join(r.intervention.lower() for r in result.treatment_plan.recommendations)
    assert "contraindicated" in rec_text or "do not prescribe" in rec_text or "nitrate holiday" in rec_text, \
        "Plan must communicate the contraindication or safe alternative pathway"
