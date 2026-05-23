"""D4 — out-of-scope detector tests.

D4 fires the structured "no CPG covers this" signal ONLY when:
  1. routing returned no CPG (D1 structural AND D2 procedure/semantic all missed), AND
  2. the top ICD candidates' inclusion confidence is below OUT_OF_SCOPE_INCL_THRESHOLD.

The inclusion gate stops a confident ICD hit (whose CPG scope is merely pending)
from being mislabelled out-of-scope.
"""
import pytest
from unittest.mock import AsyncMock, patch

from agent.clinical_stages import (
    build_out_of_scope_info,
    stage_3_route,
    DDxResult,
    OUT_OF_SCOPE_INCL_THRESHOLD,
)
from agent.routing import CPGDocRef


def _ddx(code, incl, sim=0.5):
    return DDxResult(code=code, title=f"{code} title", similarity=sim, inclusion_similarity=incl)


def _ref(name="AF CPG"):
    return CPGDocRef(
        cpg_name=name, document_id="d1", document_ids=["d1"],
        title=name, match_type="exact", score=0.9, matched_scope="X",
    )


# --- build_out_of_scope_info (pure) ----------------------------------------

def test_none_when_inclusion_confident():
    """A candidate at/above the inclusion threshold is NOT out-of-scope."""
    ddx = [_ddx("BC81.3", incl=OUT_OF_SCOPE_INCL_THRESHOLD + 0.2)]
    assert build_out_of_scope_info(ddx) is None


def test_info_when_all_inclusion_weak():
    ddx = [_ddx("X1", incl=0.05), _ddx("X2", incl=0.10)]
    info = build_out_of_scope_info(ddx)
    assert info is not None
    assert info.route_method == "out_of_scope"
    assert info.max_inclusion_score == 0.10
    assert "No loaded CPG covers this query" in info.message
    assert len(info.icd_candidates_considered) == 2


def test_empty_ddx_is_out_of_scope():
    info = build_out_of_scope_info([])
    assert info is not None
    assert info.max_inclusion_score == 0.0


def test_threshold_is_boundary_inclusive():
    """Exactly at the threshold counts as confident (not out-of-scope)."""
    ddx = [_ddx("X", incl=OUT_OF_SCOPE_INCL_THRESHOLD)]
    assert build_out_of_scope_info(ddx) is None


# --- stage_3_route D4 trigger (gated on D1+D2 both missing) -----------------

@pytest.mark.asyncio
async def test_stage3_emits_out_of_scope_when_routing_empty_and_weak():
    """No CPG from routing + weak inclusion → out_of_scope emitted, breakdown stamped."""
    ddx = [_ddx("ZZ99", incl=0.05)]
    events = []

    async def emit(t, d):
        events.append((t, d))

    with patch("agent.clinical_stages.route_icd_to_cpgs", new=AsyncMock(return_value=[])):
        cpgs = await stage_3_route(ddx, emit=emit)

    assert cpgs == []
    oos = [d for t, d in events if t == "sub_step" and d.get("badge") == "out_of_scope"]
    assert len(oos) == 1
    # The candidate's breakdown is stamped out_of_scope once routing resolves.
    assert ddx[0].score_breakdown.route_method == "out_of_scope"


@pytest.mark.asyncio
async def test_stage3_no_out_of_scope_when_a_cpg_matched():
    """If D1/D2 produced a CPG, D4 must NOT fire even on a single code."""
    ddx = [_ddx("BC81.3", incl=0.05)]
    events = []

    async def emit(t, d):
        events.append((t, d))

    with patch("agent.clinical_stages.route_icd_to_cpgs", new=AsyncMock(return_value=[_ref()])):
        cpgs = await stage_3_route(ddx, emit=emit)

    assert len(cpgs) == 1
    oos = [d for t, d in events if t == "sub_step" and d.get("badge") == "out_of_scope"]
    assert oos == []


@pytest.mark.asyncio
async def test_stage3_no_out_of_scope_when_inclusion_confident():
    """Routing empty BUT inclusion confident → suppressed (scope merely pending)."""
    ddx = [_ddx("BC81.3", incl=OUT_OF_SCOPE_INCL_THRESHOLD + 0.3)]
    events = []

    async def emit(t, d):
        events.append((t, d))

    with patch("agent.clinical_stages.route_icd_to_cpgs", new=AsyncMock(return_value=[])):
        await stage_3_route(ddx, emit=emit)

    oos = [d for t, d in events if t == "sub_step" and d.get("badge") == "out_of_scope"]
    assert oos == []
