from agent.models import TreatmentPlan, Recommendation
from agent.clinical_stages import extract_plan_terms


def _plan(texts):
    return TreatmentPlan(
        icd_primary="BA41.1",
        summary="s",
        recommendations=[
            Recommendation(
                intervention=t,
                type="pharmacological",
                cpg_source="CPG Test §1",
                rationale="test rationale",
            )
            for t in texts
        ],
        # TreatmentPlan requires recommendations OR unresolved_questions to be
        # non-empty; carry a placeholder so an empty-recommendations plan
        # (used to test the empty-plan case) still passes model validation.
        unresolved_questions=[] if texts else ["no recommendations"],
        confidence=0.8,
    )


def test_extract_plan_terms_pulls_and_dedupes_and_caps():
    plan = _plan([
        "Start ticagrelor 90mg BD",
        "Continue ticagrelor",           # dup drug
        "Refer to cardiology for PCI",
    ])
    terms = extract_plan_terms(plan, max_terms=6)
    assert any("ticagrelor" in t.lower() for t in terms)
    # dedup: ticagrelor appears once
    assert sum("ticagrelor" in t.lower() for t in terms) == 1
    assert len(terms) <= 6


def test_extract_plan_terms_empty_plan():
    assert extract_plan_terms(_plan([]), max_terms=6) == []
