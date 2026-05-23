"""Tests for sex-incompatibility filtering of CPG routing.

A male patient must never be routed to an obstetric/female-only CPG (and vice
versa). The filter only fires for an explicit 'M'/'F'; None/'other' keeps all.
"""
import pytest
from unittest.mock import AsyncMock, patch

from agent.clinical_stages import (
    sex_incompatible_reason,
    stage_3_route,
    DDxResult,
)
from agent.routing import CPGDocRef


def _ref(name, match_type="exact"):
    return CPGDocRef(
        cpg_name=name, document_id="d1", document_ids=["d1"],
        title=name, match_type=match_type, score=0.9, matched_scope="X",
    )


# --- pure helper -----------------------------------------------------------

def test_male_blocked_from_pregnancy_cpg():
    assert sex_incompatible_reason("Heart-Disease-in-Pregnancy(2nd Edition)", "M")
    assert sex_incompatible_reason("Diabetes-in-Pregnancy(2017)", "M")


def test_female_allowed_pregnancy_cpg():
    assert sex_incompatible_reason("Heart-Disease-in-Pregnancy(2nd Edition)", "F") is None


def test_female_blocked_from_male_only_cpg():
    assert sex_incompatible_reason("Erectile-Dysfunction(2024)", "F")
    assert sex_incompatible_reason("Erectile-Dysfunction(2024)", "M") is None


def test_unknown_sex_never_filters():
    assert sex_incompatible_reason("Heart-Disease-in-Pregnancy(2nd Edition)", None) is None
    assert sex_incompatible_reason("Heart-Disease-in-Pregnancy(2nd Edition)", "other") is None


def test_substring_catches_unregistered_pregnancy_cpg():
    assert sex_incompatible_reason("Some-New-Pregnancy-Guideline(2030)", "M")


def test_unrestricted_cpg_passes():
    assert sex_incompatible_reason("Atrial-Fibrillation(2012)", "M") is None
    assert sex_incompatible_reason("Atrial-Fibrillation(2012)", "F") is None


# --- stage_3_route integration --------------------------------------------

@pytest.mark.asyncio
async def test_stage3_drops_pregnancy_cpg_for_male():
    ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.9)]
    routed = [
        _ref("Atrial-Fibrillation(2012)"),
        _ref("Heart-Disease-in-Pregnancy(2nd Edition)"),
    ]
    events = []

    async def emit(t, d):
        events.append((t, d))

    with patch("agent.clinical_stages.route_icd_to_cpgs", new=AsyncMock(return_value=routed)):
        cpgs = await stage_3_route(ddx, emit=emit, patient_sex="M")

    names = [c.cpg_name for c in cpgs]
    assert "Atrial-Fibrillation(2012)" in names
    assert "Heart-Disease-in-Pregnancy(2nd Edition)" not in names
    # The primary match used for the score breakdown must be the compatible one.
    assert ddx[0].matched_cpg_title == "Atrial-Fibrillation(2012)"
    # Exclusion surfaced in the trace.
    excl = [d for t, d in events if t == "sub_step" and d.get("badge") == "excluded"]
    assert len(excl) == 1
    assert "Heart-Disease-in-Pregnancy" in excl[0]["detail"]


@pytest.mark.asyncio
async def test_stage3_keeps_pregnancy_cpg_for_female():
    ddx = [DDxResult(code="BC81.3", title="AF", similarity=0.9)]
    routed = [_ref("Heart-Disease-in-Pregnancy(2nd Edition)")]

    with patch("agent.clinical_stages.route_icd_to_cpgs", new=AsyncMock(return_value=routed)):
        cpgs = await stage_3_route(ddx, patient_sex="F")

    assert [c.cpg_name for c in cpgs] == ["Heart-Disease-in-Pregnancy(2nd Edition)"]
