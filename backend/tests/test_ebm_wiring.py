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


import pytest
from agent.models import EbmEvidence, PatientCase
import agent.clinical_stages as cs


def _ev():
    return EbmEvidence(title="t", abstract_snippet="a", journal="j", year=2024,
                       pub_type="systematic-review", evidence_tier="high",
                       pmid="1", url="u")


async def test_refine_no_ebm_returns_draft_unchanged(monkeypatch):
    called = {"llm": 0}
    async def _no_llm(*a, **k):
        called["llm"] += 1
        raise AssertionError("must not call LLM when no EBM")
    monkeypatch.setattr(cs, "_refine_llm_call", _no_llm, raising=False)
    draft = _plan(["Start aspirin"])
    case = PatientCase(chief_complaint="cp")
    out = await cs.stage_5_5_refine(case, [], draft, [])
    assert out is draft
    assert called["llm"] == 0


async def test_refine_with_ebm_attaches_evidence(monkeypatch):
    draft = _plan(["Start aspirin"])
    refined = _plan(["Start aspirin", "[Literature-based, no local CPG] add colchicine"])
    async def _fake_llm(*a, **k):
        return refined
    monkeypatch.setattr(cs, "_refine_llm_call", _fake_llm, raising=False)
    case = PatientCase(chief_complaint="cp")
    out = await cs.stage_5_5_refine(case, [], draft, [_ev()])
    assert out.ebm_evidence and out.ebm_evidence[0].pmid == "1"


async def test_resynth_emits_ebm_and_refines(monkeypatch):
    import agent.clinical_workflow as wf
    events = []
    async def emit(t, p=None): events.append((t, p))

    # stub the two-pass pieces
    draft = _plan(["Start aspirin"])
    monkeypatch.setattr(wf, "extract_plan_terms", lambda p, **k: ["aspirin"])
    async def _fetch(diseases, terms, **k): return [_ev()]
    monkeypatch.setattr(wf, "fetch_ebm_evidence", _fetch)
    async def _refine(case, ddx, dp, ebm, **k):
        dp.ebm_evidence = list(ebm); return dp
    monkeypatch.setattr(wf, "stage_5_5_refine", _refine)

    plan = await wf._apply_ebm_pass(  # small extracted helper (see Step 3)
        case=PatientCase(chief_complaint="cp"), ddx=[], draft_plan=draft,
        cpgs=[], emit=emit,
    )
    assert plan.ebm_evidence and plan.ebm_evidence[0].pmid == "1"
    assert any(t == "ebm_evidence" for t, _ in events)
