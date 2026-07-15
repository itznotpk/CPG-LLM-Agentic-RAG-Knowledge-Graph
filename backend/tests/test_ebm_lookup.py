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


# Tests for parse_europepmc_response
from agent.ebm_lookup import parse_europepmc_response

_SAMPLE = {
    "resultList": {"result": [
        {
            "id": "12345678", "pmid": "12345678", "doi": "10.1002/abc",
            "title": "Ticagrelor in NSTEMI: a systematic review",
            "journalTitle": "Cochrane Database Syst Rev", "pubYear": "2024",
            "abstractText": "A" * 900,
            "pubTypeList": {"pubType": ["Journal Article", "systematic-review"]},
        },
        {  # no abstract -> should be dropped
            "id": "999", "title": "No abstract paper", "pubYear": "2023",
            "pubTypeList": {"pubType": ["Journal Article"]},
        },
    ]}
}


def test_parse_builds_models_grades_and_truncates_and_drops_abstractless():
    out = parse_europepmc_response(_SAMPLE, snippet_chars=500)
    assert len(out) == 1
    ev = out[0]
    assert ev.pmid == "12345678"
    assert ev.evidence_tier == "high"
    assert len(ev.abstract_snippet) <= 500
    assert ev.url == "https://europepmc.org/article/MED/12345678"


def test_parse_empty_payload_returns_empty():
    assert parse_europepmc_response({}) == []
    assert parse_europepmc_response({"resultList": {"result": []}}) == []
