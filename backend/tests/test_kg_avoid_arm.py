"""Stage 4.5 KG "avoid arm" data-flow tests.

Closes the one store->stage gap identified in Chapter 4 §4.3: the avoid arm
(`clinical_graph_lookup` / `_query_comorbidity_flags`) was only ever mocked,
never tested directly. This is the logic that lets the system catch a teratogen
the patient is ALREADY on (case-10 losartan in pregnancy) even when the
comorbidity is written with a gestational age — by (a) expanding a drug to its
KG class names so class-level edges fire, and (b) aliasing the comorbidity
string down to the canonical KG node name.

The expansion/alias helpers are pure (no DB); the avoid-arm query is tested
against a mocked Neo4j session, so the whole file runs with no live Aura.
"""

import pytest
from unittest.mock import AsyncMock

from agent.graph_clinical import (
    _expand_drugs_with_classes,
    _expand_comorbidities_with_aliases,
    _query_comorbidity_flags,
)


# --------------------------------------------------------------------------- #
# Pure-logic unit tests (no database)
# --------------------------------------------------------------------------- #

def test_losartan_expands_to_arb_class():
    """An ARB drug must surface its class names so a class-level
    (ARB)-[:CONTRAINDICATED_WITH]->(Pregnancy) edge can match."""
    out = [d.lower() for d in _expand_drugs_with_classes(["Losartan"])]
    assert "arb" in out
    assert "angiotensin receptor blocker" in out


def test_expand_drugs_preserves_original_first():
    """Original drug names stay first so an exact-name edge still wins
    when both an exact and a class edge exist."""
    out = _expand_drugs_with_classes(["Losartan"])
    assert out[0] == "Losartan"


def test_beta_blocker_and_statin_expand():
    out = [d.lower() for d in _expand_drugs_with_classes(["Bisoprolol", "Atorvastatin"])]
    assert "beta blocker" in out
    assert "statin" in out


def test_expand_drugs_empty_is_empty():
    assert _expand_drugs_with_classes([]) == []


def test_pregnancy_alias_strips_gestational_age():
    """`"Pregnancy 30 weeks (primigravida)"` must yield the canonical node
    name `pregnancy`, or the Cypher IN-clause never matches."""
    out = [c.lower() for c in _expand_comorbidities_with_aliases(
        ["Pregnancy 30 weeks (primigravida)"])]
    assert "pregnancy" in out


def test_alias_keeps_original_string():
    raw = "Pregnancy 30 weeks (primigravida)"
    assert raw in _expand_comorbidities_with_aliases([raw])


def test_expand_comorbidities_empty_is_empty():
    assert _expand_comorbidities_with_aliases([]) == []


# --------------------------------------------------------------------------- #
# Avoid-arm query against a mocked Neo4j session (no live Aura)
# --------------------------------------------------------------------------- #

class _FakeResult:
    """Minimal async-iterable stand-in for a Neo4j result cursor."""

    def __init__(self, rows):
        self._rows = rows

    def __aiter__(self):
        self._it = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


def _arb_pregnancy_edge():
    return {
        "subj": "Angiotensin Receptor Blocker",
        "obj": "Pregnancy",
        "rel": "CONTRAINDICATED_WITH",
        "evidence": "ARBs are contraindicated in pregnancy (teratogenic).",
        "evidence_list": [],
        "source": "Heart-Disease-in-Pregnancy",
        "severity": "MAJOR",
        "chunk_id": "chunk-123",
        "chunk_ids": [],
        "trigger": None,
        "t_param": None, "t_op": None, "t_value": None,
        "t_value2": None, "t_unit": None, "t_negated": None,
    }


@pytest.mark.asyncio
async def test_avoid_arm_fires_class_contraindication_for_existing_med():
    """End-to-end avoid-arm path: a patient already on Losartan with a
    pregnancy comorbidity must produce a CONTRAINDICATION flag from the
    class-level edge — even though no CPG-recommended drug mentions losartan."""
    session = AsyncMock()
    session.run = AsyncMock(return_value=_FakeResult([_arb_pregnancy_edge()]))

    flags = await _query_comorbidity_flags(
        session,
        candidate_drugs=[],                                   # no CPG-recommended drug
        comorbidities=["Pregnancy 30 weeks (primigravida)"],
        patient_meds=["Losartan"],                            # already-prescribed teratogen
    )

    assert any(f.flag_type == "CONTRAINDICATION" for f in flags)
    assert any("pregnan" in f.object.lower() for f in flags)


@pytest.mark.asyncio
async def test_avoid_arm_passes_expanded_class_and_alias_to_cypher():
    """The expansion/alias must actually reach the query parameters, not just
    exist as helpers — guards the wiring between the helpers and the Cypher."""
    session = AsyncMock()
    session.run = AsyncMock(return_value=_FakeResult([]))

    await _query_comorbidity_flags(
        session,
        candidate_drugs=[],
        comorbidities=["Pregnancy 30 weeks (primigravida)"],
        patient_meds=["Losartan"],
    )

    _, kwargs = session.run.call_args
    assert any("arb" in c.lower() for c in kwargs["candidates"])
    assert any("pregnan" in c.lower() for c in kwargs["comorbidities"])


@pytest.mark.asyncio
async def test_avoid_arm_noops_without_comorbidities():
    """No comorbidity -> no query, no flags (fail-open, not fail-loud)."""
    session = AsyncMock()
    session.run = AsyncMock(return_value=_FakeResult([]))

    flags = await _query_comorbidity_flags(
        session, candidate_drugs=["Losartan"], comorbidities=[], patient_meds=[])

    assert flags == []
    session.run.assert_not_called()
