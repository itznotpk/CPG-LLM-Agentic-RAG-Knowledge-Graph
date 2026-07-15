import pytest
from agent.models import EbmEvidence, TreatmentPlan, Recommendation
from agent.ebm_lookup import evidence_tier_for, build_europepmc_query


def test_ebm_evidence_defaults_and_treatmentplan_field():
    ev = EbmEvidence(
        title="Ticagrelor vs Clopidogrel in NSTEMI",
        abstract_snippet="In this systematic review, ticagrelor reduced...",
        journal="Cochrane Database Syst Rev",
        year=2024,
        pub_type="systematic-review",
        evidence_tier="high",
        pmid="12345678",
        doi="10.1002/abc",
        url="https://europepmc.org/article/MED/12345678",
    )
    assert ev.cpg_gap is False
    plan = TreatmentPlan(
        icd_primary="BA41.1",
        summary="s",
        recommendations=[Recommendation(
            intervention="Start ticagrelor",
            type="pharmacological",
            cpg_source="CPG NSTEMI",
            rationale="Evidence-based therapy"
        )],
        confidence=0.8,
    )
    assert plan.ebm_evidence == []
    plan.ebm_evidence = [ev]
    assert plan.ebm_evidence[0].evidence_tier == "high"


@pytest.mark.parametrize("pub_types, expected", [
    (["systematic-review"], "high"),
    (["Meta-Analysis"], "high"),
    (["Randomized Controlled Trial"], "moderate"),
    (["Guideline"], "moderate"),
    (["Journal Article"], "low"),
    ([], "low"),
    (["case-reports"], "low"),
])
def test_evidence_tier_for(pub_types, expected):
    assert evidence_tier_for(pub_types) == expected


def test_build_query_combines_disease_terms_filters_and_recency():
    q = build_europepmc_query(["NSTEMI"], ["ticagrelor"], recency_years=7)
    assert "NSTEMI" in q and "ticagrelor" in q
    # pub-type pyramid filter present
    assert "systematic review" in q.lower()
    assert "randomized controlled trial" in q.lower()
    # recency filter present as a PUB_YEAR range
    assert "PUB_YEAR" in q
    # has-abstract constraint so we never feed empty abstracts to synthesis
    assert "HAS_ABSTRACT:Y" in q


def test_build_query_empty_terms_still_valid():
    q = build_europepmc_query(["Atrial Fibrillation"], [])
    assert "Atrial Fibrillation" in q
    assert q.strip() != ""
