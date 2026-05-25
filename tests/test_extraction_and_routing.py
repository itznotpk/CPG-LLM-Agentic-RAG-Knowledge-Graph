"""
Unit tests for symptom extraction and comorbidity routing fixes.

_extract_symptom_phrase  (5 tests) — clinical_stages.py Task A
route_comorbidities      (6 tests) — clinical_workflow.py Task B

All fully mocked — no real LLM, no real DB, no real embeddings.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.clinical_stages import _extract_symptom_phrase
from agent.clinical_workflow import route_comorbidities
from agent.routing import CPGDocRef
from agent.models import StagedComorbidity


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

NOTES_LONG = (
    "58-year-old male presenting with chest pain radiating to left arm and jaw, "
    "associated with diaphoresis and nausea for 3 hours. No relief with rest. "
    "Mild exertional dyspnoea on climbing stairs for past 2 weeks."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client(response_text: str) -> MagicMock:
    """Return a mock AsyncOpenAI client whose completions.create resolves to response_text."""
    mock_msg = MagicMock()
    mock_msg.content = response_text
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_resp)
    return client


def _mock_client_raises(exc: Exception) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=exc)
    return client


def _make_cpg(name: str, match_type: str = "exact") -> CPGDocRef:
    return CPGDocRef(
        cpg_name=name,
        document_id="doc-001",
        document_ids=["doc-001"],
        title=f"{name} §1",
        match_type=match_type,
        score=0.8,
        matched_scope=name,
    )


def _ddx_hit(code: str, title: str, similarity: float) -> dict:
    return {"code": code, "title": title, "similarity": similarity}


# ---------------------------------------------------------------------------
# _extract_symptom_phrase — 5 tests
# ---------------------------------------------------------------------------

async def test_extraction_returns_compressed_phrase():
    phrase = "Chest pain radiating to left arm, diaphoresis, 3 hours"  # 9 words
    result, fell_back = await _extract_symptom_phrase(NOTES_LONG, _mock_client(phrase), "test-model")
    assert result == phrase
    assert fell_back is False


async def test_extraction_truncates_echoed_input():
    # LLM echoes full 34-word input → >25 words → truncated to 15
    result, fell_back = await _extract_symptom_phrase(NOTES_LONG, _mock_client(NOTES_LONG), "test-model")
    assert len(result.split()) == 15
    assert fell_back is False


async def test_extraction_falls_back_on_empty():
    result, fell_back = await _extract_symptom_phrase(NOTES_LONG, _mock_client(""), "test-model")
    assert result == NOTES_LONG
    assert fell_back is True


async def test_extraction_falls_back_on_exception():
    client = _mock_client_raises(Exception("mock API error"))
    result, fell_back = await _extract_symptom_phrase(NOTES_LONG, client, "test-model")
    assert result == NOTES_LONG
    assert fell_back is True


async def test_extraction_strips_quotes_and_trailing_period():
    # LLM returns quoted phrase with trailing period
    result, fell_back = await _extract_symptom_phrase(NOTES_LONG, _mock_client('"Chest pain, 3 hours."'), "test-model")
    assert result == "Chest pain, 3 hours"
    assert fell_back is False


# ---------------------------------------------------------------------------
# route_comorbidities — 6 tests
# ---------------------------------------------------------------------------

async def test_comorbidity_below_threshold_skipped():
    """Similarity 0.4 < 0.55 — no route_icd_to_cpgs call, empty result."""
    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock,
              return_value=[_ddx_hit("E11", "Type 2 DM", 0.4)]),
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock) as mock_route,
    ):
        result = await route_comorbidities(["Type 2 Diabetes Mellitus"], [], top_k=2)
        assert result == []
        mock_route.assert_not_called()


async def test_comorbidity_above_threshold_routed():
    """Similarity 0.78 ≥ 0.55 — CPG appended to result."""
    cpg = _make_cpg("Diabetes-Mellitus-T2(2023)")
    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock,
              return_value=[_ddx_hit("E11", "Type 2 DM", 0.78)]),
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[cpg]),
    ):
        result = await route_comorbidities(["Type 2 Diabetes Mellitus"], [], top_k=2)
        assert len(result) == 1
        assert result[0].cpg_name == "Diabetes-Mellitus-T2(2023)"


async def test_comorbidity_dedup_against_existing():
    """CPG already in existing_cpgs list is not added again."""
    existing = [_make_cpg("Hypertension(5th Edition)")]
    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock,
              return_value=[_ddx_hit("BA00", "Essential hypertension", 0.85)]),
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[_make_cpg("Hypertension(5th Edition)")]),
    ):
        result = await route_comorbidities(["Hypertension"], existing, top_k=2)
        assert result == []


async def test_comorbidity_empty_string_skipped():
    """Empty / whitespace-only entries are skipped; only 'Hypertension' triggers a DDx call."""
    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock,
              return_value=[_ddx_hit("BA00", "Essential hypertension", 0.85)]) as mock_ddx,
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[_make_cpg("Hypertension(5th Edition)")]),
    ):
        await route_comorbidities(["", "  ", "Hypertension"], [], top_k=2)
        assert mock_ddx.call_count == 1


async def test_comorbidity_capped_at_four():
    """5 comorbidities provided — only first 4 processed (cap=4)."""
    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock,
              return_value=[_ddx_hit("BA00", "x", 0.3)]) as mock_ddx,
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[]),
    ):
        await route_comorbidities(["A", "B", "C", "D", "E"], [], top_k=2)
        assert mock_ddx.call_count == 4


async def test_comorbidity_search_ddx_failure_continues():
    """First comorbidity DDx call raises; second comorbidity still processed."""
    cpg = _make_cpg("CKD-Management(2022)")
    call_count = 0

    async def flaky_ddx(condition, top_k):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("DB connection error")
        return [_ddx_hit("N18", "Chronic kidney disease", 0.82)]

    with (
        patch("ddx.search_ddx.search_ddx", new=flaky_ddx),
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[cpg]),
    ):
        result = await route_comorbidities(["CKD Stage 3", "Hypertension"], [], top_k=2)
        assert call_count == 2
        assert len(result) == 1
        assert result[0].cpg_name == "CKD-Management(2022)"


# ---------------------------------------------------------------------------
# staged_comorbidities short-circuit — 3 tests
# ---------------------------------------------------------------------------

async def test_comorbidity_icd_code_short_circuit_bypasses_ddx():
    """staged_comorbidity with confirmed icd_code bypasses search_ddx entirely."""
    cpg = _make_cpg("Diabetes-Mellitus-T2(2023)")
    staged = [StagedComorbidity(label="Type 2 Diabetes Mellitus", icd_code="E11")]

    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock) as mock_ddx,
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[cpg]) as mock_route,
    ):
        result = await route_comorbidities(
            comorbidities=[],
            existing_cpgs=[],
            top_k=2,
            staged_comorbidities=staged
        )
        assert len(result) == 1
        assert result[0].cpg_name == "Diabetes-Mellitus-T2(2023)"
        mock_ddx.assert_not_called()
        mock_route.assert_called_once_with("E11", top_k=2)


async def test_comorbidity_mixed_staged_and_legacy_deduplicated():
    """Mixed staged and legacy are deduplicated, and coded comorbidity takes precedence."""
    cpg = _make_cpg("Diabetes-Mellitus-T2(2023)")
    staged = [StagedComorbidity(label="Type 2 Diabetes Mellitus", icd_code="E11")]
    legacy = ["Type 2 Diabetes Mellitus"]  # Duplicate label name

    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock) as mock_ddx,
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[cpg]) as mock_route,
    ):
        result = await route_comorbidities(
            comorbidities=legacy,
            existing_cpgs=[],
            top_k=2,
            staged_comorbidities=staged
        )
        assert len(result) == 1
        assert result[0].cpg_name == "Diabetes-Mellitus-T2(2023)"
        mock_ddx.assert_not_called()
        mock_route.assert_called_once_with("E11", top_k=2)


async def test_comorbidity_staged_without_icd_falls_back():
    """staged_comorbidity without icd_code falls back to search_ddx."""
    cpg = _make_cpg("Diabetes-Mellitus-T2(2023)")
    staged = [StagedComorbidity(label="Type 2 Diabetes Mellitus", icd_code=None)]

    with (
        patch("ddx.search_ddx.search_ddx", new_callable=AsyncMock,
              return_value=[_ddx_hit("E11", "Type 2 DM", 0.85)]) as mock_ddx,
        patch("agent.clinical_workflow.route_icd_to_cpgs", new_callable=AsyncMock,
              return_value=[cpg]) as mock_route,
    ):
        result = await route_comorbidities(
            comorbidities=[],
            existing_cpgs=[],
            top_k=2,
            staged_comorbidities=staged
        )
        assert len(result) == 1
        assert result[0].cpg_name == "Diabetes-Mellitus-T2(2023)"
        mock_ddx.assert_called_once_with("Type 2 Diabetes Mellitus", top_k=3)
        mock_route.assert_called_once_with("E11", top_k=2)
