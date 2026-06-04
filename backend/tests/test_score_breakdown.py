from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.clinical_stages import (
    DDxResult,
    DDX_SCORE_EXPLAINER,
    ScoreBreakdown,
    build_score_breakdown,
    render_ddx_candidate,
    render_ddx_top5,
    route_provenance_badge,
    stage_3_route,
)
from agent.routing import CPGDocRef


def _ddx(**kwargs) -> DDxResult:
    defaults = {
        "code": "5A11",
        "title": "Type 2 diabetes mellitus",
        "similarity": 0.40,
        "base_similarity": 0.40,
        "inclusion_similarity": 0.70,
        "matched_term": "adult onset diabetes",
        "exclusion_similarity": 0.60,
        "matched_exclusion": "type 1 diabetes mellitus",
        "exclusion_penalty": 0.18,
    }
    defaults.update(kwargs)
    return DDxResult(**defaults)


def test_score_breakdown_enforces_final_score_formula():
    with pytest.raises(ValidationError):
        ScoreBreakdown(
            base_similarity=0.40,
            inclusion_match=0.70,
            exclusion_penalty=0.18,
            final_score=0.50,
            route_method="exact",
        )


def test_build_score_breakdown_names_score_contributors():
    breakdown = build_score_breakdown(_ddx(), route_method="exact")

    assert breakdown.base_similarity == 0.40
    # inclusion_match is the WEIGHTED addend (0.3 × raw 0.70); phrase still shows
    # because the RAW match (0.70) clears the display floor.
    assert breakdown.inclusion_match == pytest.approx(0.21)
    assert breakdown.inclusion_phrase == "adult onset diabetes"
    assert breakdown.exclusion_penalty == 0.18
    assert breakdown.exclusion_phrase == "type 1 diabetes mellitus"
    assert breakdown.final_score == pytest.approx(0.43)  # 0.40 + 0.21 − 0.18
    assert breakdown.route_method == "exact"


def test_build_score_breakdown_hides_low_term_matches():
    breakdown = build_score_breakdown(
        _ddx(
            inclusion_similarity=0.49,
            exclusion_similarity=0.49,
            exclusion_penalty=0.147,
        ),
        route_method="exact",
    )

    assert breakdown.inclusion_phrase is None
    assert breakdown.exclusion_phrase is None


@pytest.mark.parametrize(
    ("route_method", "expected"),
    [
        ("exact", "Exact guideline match"),
        ("ancestor_d1", "Matched via broader category"),
        ("ancestor_d2", "Matched via broader category"),
        ("sibling", "Matched via related code"),
        ("ancestor_d1_sibling", "Matched via related category"),
        ("ancestor_d1_sibling_child", "Matched via related subcode"),
        ("out_of_scope", "No guideline covers this"),
    ],
)
def test_badge_text_per_route_method(route_method, expected):
    assert expected in route_provenance_badge(route_method)


def test_render_ddx_candidate_shows_exclusion_caution_and_low_confidence():
    candidate = _ddx(
        code="X1",
        title="Candidate",
        similarity=0.25,
        base_similarity=0.25,
        inclusion_similarity=None,
        matched_term=None,
        exclusion_similarity=0.60,
        matched_exclusion="excluded presentation",
        exclusion_penalty=0.18,
    )
    candidate.score_breakdown = build_score_breakdown(candidate, route_method="out_of_scope")

    rendered = render_ddx_candidate(candidate, rank=1)

    assert "low confidence" in rendered
    assert "No guideline covers this" in rendered
    assert "WHO excludes \"excluded presentation\"" in rendered
    assert "ranked lower" in rendered


def test_render_ddx_top5_limits_to_five_candidates():
    candidates = [
        _ddx(code=f"X{i}", title=f"Candidate {i}", similarity=0.50, base_similarity=0.50)
        for i in range(6)
    ]
    for candidate in candidates:
        candidate.score_breakdown = build_score_breakdown(candidate, route_method="exact")

    rendered = render_ddx_top5(candidates)

    assert "#5" in rendered
    assert "#6" not in rendered


@pytest.mark.asyncio
async def test_stage3_attaches_route_provenance_to_ddx(monkeypatch):
    ddx = [_ddx(code="BC81.3", title="Atrial fibrillation")]
    ref = CPGDocRef(
        cpg_name="AF CPG",
        document_id="doc-1",
        document_ids=["doc-1"],
        title="Atrial Fibrillation CPG",
        match_type="exact",
        score=1.0,
        matched_scope="BC81.3",
    )

    async def mock_route(_code, top_k=3, procedure_tags=None):
        return [ref]

    monkeypatch.setattr("agent.clinical_stages.route_icd_to_cpgs", mock_route)

    result = await stage_3_route(ddx, top_k_codes=1, top_k_cpgs=1)

    assert result == [ref]
    assert ddx[0].matched_cpg_title == "Atrial Fibrillation CPG"
    assert ddx[0].score_breakdown is not None
    assert ddx[0].score_breakdown.route_method == "exact"


def test_score_explainer_mentions_all_three_signals():
    assert "Symptom match" in DDX_SCORE_EXPLAINER
    assert "Known-term match" in DDX_SCORE_EXPLAINER
    assert "Exclusion caution" in DDX_SCORE_EXPLAINER
