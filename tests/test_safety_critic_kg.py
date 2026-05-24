"""Tests for hybrid Agent 1 (upgraded Safety Critic) — KG verification of the
FINAL plan merged into the SafetyReport alongside the LLM critic's flags.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models import PatientCase, TreatmentPlan, Recommendation, SafetyFlag, SafetyReport
from agent.graph_clinical import ClinicalFlag
from agent.safety_critic import run_safety_critic, _kg_verify_plan, _kg_flag_to_safety


def _case():
    return PatientCase(
        chief_complaint="palpitations",
        age=68, sex="M",
        comorbidities=["Atrial fibrillation"],
        current_medications=["aspirin"],
        allergies=[],
    )


def _plan_with_warfarin():
    return TreatmentPlan(
        icd_primary="BC81.3",
        summary="AF rate-control plan.",
        recommendations=[
            Recommendation(
                intervention="Start warfarin 5 mg OD for stroke prevention",
                type="pharmacological",
                cpg_source="AF CPG §4.2",
                rationale="CHA2DS2-VASc ≥2 → anticoagulation indicated",
            )
        ],
        confidence=0.85,
    )


# --- pure mapper unit -------------------------------------------------------

def test_kg_flag_maps_to_graph_sourced_safety_flag():
    cf = ClinicalFlag(
        flag_type="INTERACTION",
        subject="Warfarin",
        object="Aspirin",
        relation="INTERACTS_WITH",
        severity="MAJOR",
        evidence="Bleeding risk increases substantially when combined.",
    )
    sf = _kg_flag_to_safety(cf, drug_idx_map={"warfarin": 0}, pharm_recommendation_indices=[0])
    assert sf is not None
    assert sf.severity == "MAJOR"
    assert sf.flag_type == "drug_interaction"
    assert sf.recommendation_index == 0
    assert sf.source == "graph"
    assert "Warfarin" in sf.detail and "Aspirin" in sf.detail
    assert "Bleeding risk" in sf.detail


def test_kg_flag_monitoring_is_skipped():
    cf = ClinicalFlag(flag_type="MONITORING", subject="Warfarin", object="INR", relation="REQUIRES_MONITORING")
    assert _kg_flag_to_safety(cf, drug_idx_map={"warfarin": 0}, pharm_recommendation_indices=[0]) is None


# --- _kg_verify_plan integration (mocked KG) --------------------------------

@pytest.mark.asyncio
async def test_kg_verify_returns_graph_flags_for_known_interaction():
    """warfarin in plan + aspirin in current_meds → KG flag → SafetyFlag(source=graph)."""
    kg_flag = ClinicalFlag(
        flag_type="INTERACTION", subject="Warfarin", object="Aspirin",
        relation="INTERACTS_WITH", severity="MAJOR",
        evidence="Concurrent use raises bleeding risk.",
    )
    with patch("agent.safety_critic.match_plan_drugs",
               new=AsyncMock(return_value={"warfarin": 0})), \
         patch("agent.safety_critic.clinical_graph_lookup",
               new=AsyncMock(return_value=[kg_flag])):
        flags = await _kg_verify_plan(_case(), _plan_with_warfarin())
    assert len(flags) == 1
    assert flags[0].source == "graph"
    assert flags[0].flag_type == "drug_interaction"
    assert flags[0].severity == "MAJOR"


@pytest.mark.asyncio
async def test_kg_verify_returns_empty_when_no_pharmacological_recs():
    plan = TreatmentPlan(
        icd_primary="X", summary="lifestyle only",
        recommendations=[Recommendation(
            intervention="Salt restriction", type="lifestyle",
            cpg_source="X §1", rationale="reduces BP",
        )],
        confidence=0.5,
    )
    # No need to mock — should short-circuit on the empty pharm filter
    flags = await _kg_verify_plan(_case(), plan)
    assert flags == []


@pytest.mark.asyncio
async def test_kg_verify_fails_open_on_kg_error():
    """Transient KG failure → empty list, never raises (retry exhausted)."""
    with patch("agent.safety_critic.match_plan_drugs",
               new=AsyncMock(side_effect=RuntimeError("neo4j reset"))):
        flags = await _kg_verify_plan(_case(), _plan_with_warfarin())
    assert flags == []


# --- run_safety_critic merges LLM + KG --------------------------------------

@pytest.mark.asyncio
async def test_run_safety_critic_merges_llm_and_kg_flags():
    """The final SafetyReport contains BOTH LLM-source and graph-source flags,
    with safe_to_proceed recomputed across the merged list."""
    # Mock the LLM call to return one MODERATE LLM flag
    llm_payload = {
        "flags": [{
            "severity": "MODERATE",
            "recommendation_index": 0,
            "flag_type": "drug_interaction",
            "detail": "Warfarin requires INR monitoring (LLM-suggested).",
            "suggested_alternative": None,
        }],
        "safe_to_proceed": True,
        "reviewer_notes": None,
    }
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message = MagicMock(content='{"flags":[{"severity":"MODERATE","recommendation_index":0,"flag_type":"drug_interaction","detail":"Warfarin requires INR monitoring (LLM-suggested).","suggested_alternative":null}],"safe_to_proceed":true,"reviewer_notes":null}')

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    # KG returns one MAJOR interaction → should flip safe_to_proceed false
    kg_flag = ClinicalFlag(
        flag_type="INTERACTION", subject="Warfarin", object="Aspirin",
        relation="INTERACTS_WITH", severity="MAJOR", evidence="Bleeding risk.",
    )

    with patch("agent.safety_critic.openai.AsyncOpenAI", return_value=fake_client), \
         patch("agent.safety_critic.match_plan_drugs",
               new=AsyncMock(return_value={"warfarin": 0})), \
         patch("agent.safety_critic.clinical_graph_lookup",
               new=AsyncMock(return_value=[kg_flag])):
        report = await run_safety_critic(_case(), _plan_with_warfarin())

    # Both flags present
    sources = sorted(f.source for f in report.flags)
    assert sources == ["graph", "llm"]
    # MAJOR graph flag → safe_to_proceed must be False
    assert report.safe_to_proceed is False
    # reviewer_notes mentions the graph addition
    assert "graph-verified" in (report.reviewer_notes or "")
