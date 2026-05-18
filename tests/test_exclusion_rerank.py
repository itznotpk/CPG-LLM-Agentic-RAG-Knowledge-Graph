from __future__ import annotations

import pytest

from ddx.backfill_exclusion_embeddings import _needs_processing
from ddx.search_ddx import (
    EXCLUSION_PENALTY_WEIGHT,
    apply_tabulation_filter,
)


def test_exclusion_backfill_needs_processing_when_key_missing():
    row = {
        "exclusions": ["type 1 diabetes mellitus", "secondary diabetes mellitus"],
        "exclusion_embeddings": {"type 1 diabetes mellitus": [1.0, 0.0]},
    }

    assert _needs_processing(row, force=False) is True


def test_exclusion_backfill_skips_when_all_terms_present():
    row = {
        "exclusions": ["type 1 diabetes mellitus", "secondary diabetes mellitus"],
        "exclusion_embeddings": {
            "type 1 diabetes mellitus": [1.0, 0.0],
            "secondary diabetes mellitus": [0.0, 1.0],
        },
    }

    assert _needs_processing(row, force=False) is False


def test_exclusion_backfill_force_recomputes_complete_row():
    row = {
        "exclusions": ["type 1 diabetes mellitus"],
        "exclusion_embeddings": {"type 1 diabetes mellitus": [1.0, 0.0]},
    }

    assert _needs_processing(row, force=True) is True


@pytest.mark.asyncio
async def test_exclusion_penalty_downranks_but_keeps_candidate():
    candidates = [
        {
            "code": "5A11",
            "title": "Type 2 diabetes mellitus",
            "description": "",
            "inclusions": [],
            "exclusions": ["type 1 diabetes mellitus"],
            "inclusion_embeddings": {},
            "exclusion_embeddings": {"type 1 diabetes mellitus": [1.0, 0.0]},
            "similarity": 0.90,
        },
        {
            "code": "5A10",
            "title": "Type 1 diabetes mellitus",
            "description": "",
            "inclusions": [],
            "exclusions": [],
            "inclusion_embeddings": {},
            "exclusion_embeddings": {},
            "similarity": 0.75,
        },
    ]

    ranked = await apply_tabulation_filter(
        candidates,
        query_symptoms="type 1 diabetes mellitus",
        query_embedding=[1.0, 0.0],
    )

    assert [c["code"] for c in ranked] == ["5A10", "5A11"]
    penalized = ranked[1]
    assert penalized["code"] == "5A11"
    assert penalized["exclusion_match"] is True
    assert penalized["matched_exclusion"] == "type 1 diabetes mellitus"
    assert penalized["exclusion_similarity"] == 1.0
    assert penalized["exclusion_penalty"] == EXCLUSION_PENALTY_WEIGHT
    assert penalized["final_score"] == pytest.approx(0.90 - EXCLUSION_PENALTY_WEIGHT)


@pytest.mark.asyncio
async def test_inclusion_boost_and_exclusion_penalty_are_both_in_final_score():
    candidates = [
        {
            "code": "X1",
            "title": "Candidate",
            "description": "",
            "inclusions": [],
            "exclusions": [],
            "inclusion_embeddings": {"matching inclusion": [1.0, 0.0]},
            "exclusion_embeddings": {"matching exclusion": [0.6, 0.8]},
            "similarity": 0.40,
        },
    ]

    ranked = await apply_tabulation_filter(
        candidates,
        query_symptoms="matching inclusion",
        query_embedding=[1.0, 0.0],
    )

    result = ranked[0]
    assert result["inclusion_match"] is True
    assert result["exclusion_match"] is True
    assert result["final_score"] == pytest.approx(0.40 + 1.0 - (EXCLUSION_PENALTY_WEIGHT * 0.6))
