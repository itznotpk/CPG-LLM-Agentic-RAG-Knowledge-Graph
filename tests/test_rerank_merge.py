"""Tests for D6: math-signal rerank prompt, disagreement surfacing, telemetry."""
from __future__ import annotations

import json
import logging

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.clinical_stages import (
    DDxResult,
    _llm_rerank_ddx,
    render_ddx_candidate,
    build_score_breakdown,
    RERANK_DISAGREEMENT_DELTA,
    SCORE_TERM_DISPLAY_FLOOR,
)
from agent.models import PatientCase


def _ddx(
    code="5A11",
    title="T2DM",
    similarity=0.80,
    base_similarity=0.80,
    inclusion_similarity=0.0,
    matched_term=None,
    exclusion_similarity=0.0,
    matched_exclusion=None,
    exclusion_penalty=0.0,
):
    return DDxResult(
        code=code,
        title=title,
        similarity=similarity,
        base_similarity=base_similarity,
        inclusion_similarity=inclusion_similarity,
        matched_term=matched_term,
        exclusion_similarity=exclusion_similarity,
        matched_exclusion=matched_exclusion,
        exclusion_penalty=exclusion_penalty,
    )


def _make_candidates():
    return [
        _ddx("BC81.3", "AF", similarity=0.90, base_similarity=0.90),
        _ddx("BC81.1", "Paroxysmal AF", similarity=0.75, base_similarity=0.75),
        _ddx("BC82.0", "Flutter", similarity=0.60, base_similarity=0.60),
        _ddx("BA41.0", "STEMI", similarity=0.45, base_similarity=0.45),
    ]


def _make_case():
    return PatientCase(
        chief_complaint="palpitations",
        age=68,
        sex="M",
    )


def _mock_response(items: list[dict]) -> MagicMock:
    """Build a mock openai non-streaming response with given JSON items."""
    content = json.dumps(items)
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_rank_delta_computed():
    """LLM reverses order → math_rank, llm_rank, rank_delta all populated correctly."""
    candidates = _make_candidates()
    # LLM returns in reverse order
    reversed_items = [
        {"code": c.code, "confidence": 0.5, "reasoning": "r", "override_reason": None}
        for c in reversed(candidates)
    ]

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response(reversed_items)
        )

        result = await _llm_rerank_ddx(_make_case(), candidates)

    assert len(result) == 4
    # Original #1 (BC81.3) should now be at llm_rank=4
    bc81_3 = next(r for r in result if r.code == "BC81.3")
    assert bc81_3.math_rank == 1
    assert bc81_3.llm_rank == 4
    assert bc81_3.rank_delta == -3  # math_rank - llm_rank = 1 - 4

    # All should have rank fields populated
    for r in result:
        assert r.math_rank is not None
        assert r.llm_rank is not None
        assert r.rank_delta is not None


@pytest.mark.asyncio
async def test_disagreement_line_rendered_above_threshold():
    """render_ddx_candidate shows the disagreement line when |rank_delta| >= RERANK_DISAGREEMENT_DELTA."""
    candidate = _ddx("BC81.3", "AF", similarity=0.90, base_similarity=0.90)
    candidate.score_breakdown = build_score_breakdown(candidate, route_method="exact")
    candidate.math_rank = 3
    candidate.llm_rank = 1
    candidate.rank_delta = RERANK_DISAGREEMENT_DELTA  # exactly at threshold
    candidate.override_reason = "clinical reason"

    rendered = render_ddx_candidate(candidate, rank=1)

    assert "Reasoning model moved this" in rendered
    assert "clinical reason" in rendered


@pytest.mark.asyncio
async def test_disagreement_line_absent_below_threshold():
    """render_ddx_candidate omits the disagreement line when |rank_delta| < RERANK_DISAGREEMENT_DELTA."""
    candidate = _ddx("BC81.3", "AF", similarity=0.90, base_similarity=0.90)
    candidate.score_breakdown = build_score_breakdown(candidate, route_method="exact")
    candidate.math_rank = 2
    candidate.llm_rank = 1
    candidate.rank_delta = RERANK_DISAGREEMENT_DELTA - 1
    candidate.override_reason = "some reason"

    rendered = render_ddx_candidate(candidate, rank=1)

    assert "Reasoning model moved this" not in rendered


@pytest.mark.asyncio
async def test_override_reason_required_when_exclusion_promoted():
    """Hard rule: exclusion-penalised candidate promoted >= RERANK_DISAGREEMENT_DELTA with no override_reason → placeholder injected."""
    candidates = _make_candidates()
    # Make the last candidate (STEMI, math_rank=4) have an exclusion penalty
    candidates[3] = _ddx(
        "BA41.0", "STEMI",
        similarity=0.45, base_similarity=0.45,
        exclusion_similarity=SCORE_TERM_DISPLAY_FLOOR + 0.01,
        matched_exclusion="stable angina",
        exclusion_penalty=0.10,
    )

    # LLM promotes STEMI to rank 1 (math_rank=4 → llm_rank=1, rank_delta=3) with empty override_reason
    reordered_items = [
        {"code": "BA41.0", "confidence": 0.80, "reasoning": "fits", "override_reason": ""},
        {"code": "BC81.3", "confidence": 0.75, "reasoning": "r", "override_reason": None},
        {"code": "BC81.1", "confidence": 0.70, "reasoning": "r", "override_reason": None},
        {"code": "BC82.0", "confidence": 0.60, "reasoning": "r", "override_reason": None},
    ]

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response(reordered_items)
        )

        result = await _llm_rerank_ddx(_make_case(), candidates)

    promoted = next(r for r in result if r.code == "BA41.0")
    assert promoted.override_reason  # must be non-empty (injected placeholder)
    assert "required" in promoted.override_reason.lower() or "[override" in promoted.override_reason


@pytest.mark.asyncio
async def test_override_reason_not_required_for_small_moves():
    """No injection when the move is smaller than RERANK_DISAGREEMENT_DELTA."""
    candidates = _make_candidates()
    # Make candidate 2 have an exclusion penalty
    candidates[1] = _ddx(
        "BC81.1", "Paroxysmal AF",
        similarity=0.75, base_similarity=0.75,
        exclusion_similarity=SCORE_TERM_DISPLAY_FLOOR + 0.01,
        matched_exclusion="persistent AF",
        exclusion_penalty=0.10,
    )

    # LLM moves BC81.1 up by only RERANK_DISAGREEMENT_DELTA - 1 position (math=2 → llm=1)
    delta = RERANK_DISAGREEMENT_DELTA - 1
    # With 4 candidates, math_rank=2, promote to llm_rank = 2 - delta = 2 - 1 = 1
    reordered_items = [
        {"code": "BC81.1", "confidence": 0.80, "reasoning": "r", "override_reason": ""},
        {"code": "BC81.3", "confidence": 0.75, "reasoning": "r", "override_reason": None},
        {"code": "BC82.0", "confidence": 0.60, "reasoning": "r", "override_reason": None},
        {"code": "BA41.0", "confidence": 0.45, "reasoning": "r", "override_reason": None},
    ]

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response(reordered_items)
        )

        result = await _llm_rerank_ddx(_make_case(), candidates)

    promoted = next(r for r in result if r.code == "BC81.1")
    # rank_delta = math_rank(2) - llm_rank(1) = 1, which is < RERANK_DISAGREEMENT_DELTA
    assert promoted.rank_delta == 1
    assert promoted.override_reason != "[override_reason required but not provided by LLM]"


@pytest.mark.asyncio
async def test_exclusion_override_uses_caution_glyph():
    """render_ddx_candidate shows ⚠ ↕ glyph when exclusion-penalised candidate is promoted >= threshold."""
    candidate = _ddx(
        "BA41.0", "STEMI",
        similarity=0.45, base_similarity=0.45,
        exclusion_similarity=SCORE_TERM_DISPLAY_FLOOR + 0.01,
        matched_exclusion="stable angina",
        exclusion_penalty=0.10,
    )
    candidate.score_breakdown = build_score_breakdown(candidate, route_method="out_of_scope")
    candidate.math_rank = 4
    candidate.llm_rank = 1
    candidate.rank_delta = RERANK_DISAGREEMENT_DELTA  # promoted up, >= threshold
    candidate.override_reason = "clinical justification"

    rendered = render_ddx_candidate(candidate, rank=1)

    assert "⚠ ↕" in rendered


@pytest.mark.asyncio
async def test_final_order_is_llm_rank():
    """After reranking, position 0 has llm_rank=1, position 1 has llm_rank=2, etc."""
    candidates = _make_candidates()
    # LLM reverses the order
    reversed_items = [
        {"code": c.code, "confidence": 0.5, "reasoning": "r", "override_reason": None}
        for c in reversed(candidates)
    ]

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response(reversed_items)
        )

        result = await _llm_rerank_ddx(_make_case(), candidates)

    for i, r in enumerate(result):
        assert r.llm_rank == i + 1, f"Expected llm_rank={i+1} at position {i}, got {r.llm_rank}"


@pytest.mark.asyncio
async def test_rerank_prompt_includes_math_signals():
    """Prompt sent to LLM must contain math signal field names and exclusion phrase for penalised candidates."""
    candidates = [
        _ddx(
            "BC81.3", "AF",
            similarity=0.90, base_similarity=0.88,
            inclusion_similarity=SCORE_TERM_DISPLAY_FLOOR + 0.05,
            matched_term="atrial fibrillation",
        ),
        _ddx(
            "BA41.0", "STEMI",
            similarity=0.45, base_similarity=0.45,
            exclusion_similarity=SCORE_TERM_DISPLAY_FLOOR + 0.01,
            matched_exclusion="stable angina",
            exclusion_penalty=0.10,
        ),
    ]

    captured_prompt: list[str] = []

    async def capture_create(**kwargs):
        msgs = kwargs.get("messages", [])
        for m in msgs:
            captured_prompt.append(m.get("content", ""))
        # Return same-order items so no exception
        items = [
            {"code": c.code, "confidence": 0.5, "reasoning": "r", "override_reason": None}
            for c in candidates
        ]
        return _mock_response(items)

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = capture_create

        await _llm_rerank_ddx(_make_case(), candidates)

    full_prompt = "\n".join(captured_prompt)
    assert "symptom_match" in full_prompt
    assert "inclusion_match" in full_prompt
    assert "WHO exclusion" in full_prompt
    assert "stable angina" in full_prompt


@pytest.mark.asyncio
async def test_no_override_reason_when_llm_agrees():
    """When LLM returns same order, all rank_deltas are 0 and no disagreement line appears."""
    candidates = _make_candidates()
    same_order_items = [
        {"code": c.code, "confidence": 0.5, "reasoning": "r", "override_reason": None}
        for c in candidates
    ]

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response(same_order_items)
        )

        result = await _llm_rerank_ddx(_make_case(), candidates)

    for r in result:
        assert r.rank_delta == 0
        r.score_breakdown = build_score_breakdown(r, route_method="exact")
        rendered = render_ddx_candidate(r, rank=r.llm_rank or 1)
        assert "Reasoning model moved this" not in rendered


@pytest.mark.asyncio
async def test_telemetry_counts_logged(caplog):
    """D6 telemetry log line appears with correct disagreements count."""
    candidates = _make_candidates()
    # Reverse order so all 4 move — at least 2 will have |rank_delta| >= RERANK_DISAGREEMENT_DELTA
    reversed_items = [
        {"code": c.code, "confidence": 0.5, "reasoning": "r", "override_reason": None}
        for c in reversed(candidates)
    ]

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response(reversed_items)
        )

        with caplog.at_level(logging.INFO, logger="agent.clinical_stages"):
            result = await _llm_rerank_ddx(_make_case(), candidates)

    telemetry_lines = [r for r in caplog.records if "D6 telemetry" in r.getMessage()]
    assert telemetry_lines, "Expected a 'D6 telemetry' log line"

    msg = telemetry_lines[0].getMessage()
    # At least 1 disagreement (reversing 4 items produces disagreements at positions 1 and 4)
    assert "disagreements=" in msg
    # Extract the disagreements count and verify >= 1
    import re
    m = re.search(r"disagreements=(\d+)", msg)
    assert m and int(m.group(1)) >= 1
