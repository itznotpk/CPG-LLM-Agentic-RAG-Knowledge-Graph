from agent.models import EbmEvidence, TreatmentPlan, Recommendation


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
