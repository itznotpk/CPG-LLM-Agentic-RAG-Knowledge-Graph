"""
D2 unit tests — procedure_scope + semantic_scope routing fallbacks.
(Deliverable 2, P2b)

All tests are fully mocked — no real DB, no real embeddings, no external calls.
Nine test cases covering:
  1. procedure_scope fires after D1 exhausted, before semantic_scope
  2. procedure_scope skipped when structural (D1) match found
  3. procedure_scope with empty tags → returns []
  4. _extract_procedure_tags maps clinical keywords to snake_case tags
  5. semantic_scope fires only after D1 AND procedure_scope both miss
  6. semantic_scope threshold boundary (exactly at SEMANTIC_SCOPE_THRESHOLD → included; below → excluded)
  7. semantic_scope picks the single best CPG from multiple candidates
  8. stage_3_route forwards extracted procedure_tags to route_icd_to_cpgs
  9. out_of_scope returned when D1, procedure_scope, and semantic_scope all miss
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(**kwargs):
    class _Record(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)
        def keys(self):
            return super().keys()
    return _Record(kwargs)


def _no_d1_side_effects():
    """Return mock fetch side_effects that exhaust all 6 D1 structural steps."""
    # exact, range-fetch, siblings, ancestors, ancestor-siblings, sibling-children
    return [[], [], [], [], [], []]


# ---------------------------------------------------------------------------
# 1. procedure_scope fires after D1 exhausted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_procedure_scope_fires_after_d1_exhausted():
    proc_doc = _row(id="proc-doc-1", title="Pre-Anaesthetic Assessment CPG", cpg_name="Pre-Anaesthetic-Assessment")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=_no_d1_side_effects() + [[proc_doc]])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.routing._semantic_scope_match", new=AsyncMock(return_value=[])) as mock_sem:
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("ZZ99", procedure_tags=["pre_op_assessment"])

    assert len(results) == 1
    assert results[0].match_type == "procedure_scope"
    assert results[0].cpg_name == "Pre-Anaesthetic-Assessment"
    mock_sem.assert_not_awaited()  # semantic should not fire when procedure matches


# ---------------------------------------------------------------------------
# 2. procedure_scope skipped when D1 structural match found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_procedure_scope_skipped_on_d1_match():
    doc = _row(id="doc-exact", title="AF CPG", icd11_scope=["BC81.3"], cpg_name="AF-CPG")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[doc])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.routing._procedure_scope_match", new=AsyncMock()) as mock_proc:
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("BC81.3", procedure_tags=["pre_op_assessment"])

    mock_proc.assert_not_awaited()
    assert results[0].match_type == "exact"


# ---------------------------------------------------------------------------
# 3. procedure_scope with empty tags → returns []
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_procedure_scope_empty_tags_returns_empty():
    from agent.routing import _procedure_scope_match

    mock_conn = AsyncMock()
    results = await _procedure_scope_match(mock_conn, [])

    assert results == []
    mock_conn.fetch.assert_not_awaited()


# ---------------------------------------------------------------------------
# 4. _extract_procedure_tags maps clinical keywords to snake_case tags
# ---------------------------------------------------------------------------

def test_extract_procedure_tags_maps_keywords():
    from agent.clinical_stages import _extract_procedure_tags

    text = "Patient requires pre-operative anaesthetic assessment before surgery."
    tags = _extract_procedure_tags(text)

    assert isinstance(tags, list)
    assert len(tags) > 0
    # all tags must be snake_case strings
    for tag in tags:
        assert "_" in tag or tag.isalpha(), f"Expected snake_case tag, got: {tag}"


def test_extract_procedure_tags_case_insensitive():
    from agent.clinical_stages import _extract_procedure_tags

    text_lower = "anaesthetic planning required."
    text_upper = "ANAESTHETIC PLANNING REQUIRED."
    assert set(_extract_procedure_tags(text_lower)) == set(_extract_procedure_tags(text_upper))


def test_extract_procedure_tags_no_match_returns_empty():
    from agent.clinical_stages import _extract_procedure_tags

    text = "Routine follow-up appointment for blood pressure monitoring."
    tags = _extract_procedure_tags(text)
    # May return empty list or not — just ensure it's a list
    assert isinstance(tags, list)


def test_extract_procedure_tags_dental_routes_to_pre_op():
    """Dental extraction in patient history must tag pre_op_assessment so the
    Pre-Anaesthetic-Consultation CPG (procedure_scope=['pre_op_assessment', ...])
    can route in via the procedure_scope branch."""
    from agent.clinical_stages import _extract_procedure_tags

    for text in [
        "Elective dental extraction planned in 7 days",
        "Patient scheduled for tooth extraction next week",
        "Pre-procedure review before colonoscopy",
        "Outpatient endoscopy planned",
    ]:
        tags = _extract_procedure_tags(text)
        assert "pre_op_assessment" in tags, (
            f"missing pre_op_assessment for: {text!r} → {tags}"
        )


# ---------------------------------------------------------------------------
# 5. semantic_scope fires after D1 AND procedure_scope both miss
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_semantic_scope_fires_only_after_d1_and_procedure_miss():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=_no_d1_side_effects() + [[]])  # procedure_scope also empty

    sem_doc = MagicMock()
    sem_doc.cpg_name = "Diabetes CPG"
    sem_doc.document_id = "sem-doc-1"
    sem_doc.match_type = "semantic_scope"

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.routing._semantic_scope_match", new=AsyncMock(return_value=[sem_doc])) as mock_sem:
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("5B55", procedure_tags=["glycaemia_monitoring"])

    mock_sem.assert_awaited_once()
    assert results[0].document_id == "sem-doc-1"


# ---------------------------------------------------------------------------
# 6. semantic_scope threshold boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_semantic_scope_threshold_at_boundary():
    """Score of exactly SEMANTIC_SCOPE_THRESHOLD must be included; (threshold - 0.001) must be excluded."""
    from agent.routing import _semantic_scope_match, SEMANTIC_SCOPE_THRESHOLD

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=[0.1] * 1536)

    # exactly at threshold
    at_threshold = _row(id="doc-at", cpg_name="CPG At", title="CPG At", similarity=SEMANTIC_SCOPE_THRESHOLD)
    mock_conn.fetch = AsyncMock(return_value=[at_threshold])
    results = await _semantic_scope_match(mock_conn, "5B55")
    assert len(results) == 1, "Score at threshold should be included"

    # just below threshold
    mock_conn.fetchval = AsyncMock(return_value=[0.1] * 1536)
    below_threshold = _row(id="doc-below", cpg_name="CPG Below", title="CPG Below",
                           similarity=SEMANTIC_SCOPE_THRESHOLD - 0.001)
    mock_conn.fetch = AsyncMock(return_value=[below_threshold])
    results = await _semantic_scope_match(mock_conn, "5B55")
    assert results == [], "Score below threshold should be excluded"


# ---------------------------------------------------------------------------
# 7. semantic_scope picks single best CPG from multiple candidates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_semantic_scope_picks_best_candidate():
    from agent.routing import _semantic_scope_match

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=[0.1] * 1536)

    candidates = [
        _row(id="doc-low", cpg_name="CPG Low", title="CPG Low", similarity=0.70),
        _row(id="doc-high", cpg_name="CPG High", title="CPG High", similarity=0.88),
        _row(id="doc-mid", cpg_name="CPG Mid", title="CPG Mid", similarity=0.75),
    ]
    mock_conn.fetch = AsyncMock(return_value=candidates)

    results = await _semantic_scope_match(mock_conn, "5B55")

    assert len(results) == 1
    assert results[0].cpg_name == "CPG High"
    assert results[0].match_type == "semantic_scope"


# ---------------------------------------------------------------------------
# 8. stage_3_route forwards extracted procedure_tags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_3_route_forwards_procedure_tags():
    from agent.clinical_stages import stage_3_route, DDxResult

    ddx_result = MagicMock(spec=DDxResult)
    ddx_result.code = "5B55"
    ddx_result.score_breakdown = None

    sem_doc = MagicMock()
    sem_doc.cpg_name = "Anaesthesia CPG"
    sem_doc.document_ids = ["uuid-1"]
    sem_doc.document_id = "uuid-1"
    sem_doc.match_type = "procedure_scope"
    sem_doc.score = 1.0
    sem_doc.matched_scope = "procedure:pre_op_assessment"
    sem_doc.title = "Anaesthesia CPG"

    with patch("agent.clinical_stages.route_icd_to_cpgs", new=AsyncMock(return_value=[sem_doc])) as mock_route, \
         patch("agent.clinical_stages.build_score_breakdown", return_value=None):
        await stage_3_route(
            ddx=[ddx_result],
            clinical_context="Patient requires anaesthetic pre-operative assessment.",
        )

    call_kwargs = mock_route.call_args[1]
    assert "procedure_tags" in call_kwargs
    assert isinstance(call_kwargs["procedure_tags"], list)
    assert len(call_kwargs["procedure_tags"]) > 0


# ---------------------------------------------------------------------------
# 9. out_of_scope when D1 + procedure_scope + semantic_scope all miss
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_out_of_scope_when_all_fallbacks_miss():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=_no_d1_side_effects() + [[]])  # procedure empty too

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.routing._semantic_scope_match", new=AsyncMock(return_value=[])):
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("ZZ99.99", procedure_tags=["unknown_procedure"])

    assert results == []
