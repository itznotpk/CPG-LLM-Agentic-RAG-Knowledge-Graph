"""
Tests for ddx/backfill_scope_embeddings._build_scope_text.

The scope-embedding text is built from cpg_scope_rationale (scope_rationale
column) + procedure_scope tags ONLY. ICD-11 condition titles are intentionally
excluded to avoid diluting broad-CPG embeddings. Pure function; no DB calls.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from ddx.backfill_scope_embeddings import _build_scope_text, backfill


def test_includes_rationale_and_procedure_tags():
    row = {
        "title": "Section 1",
        "scope_rationale": "This guideline covers atrial fibrillation management.",
        "icd11_scope": ["BC81.3", "BC81.30"],
        "procedure_scope": ["warfarin_initiation", "inr_monitoring"],
    }
    text = _build_scope_text(row)
    assert "atrial fibrillation management" in text
    assert "Procedures: warfarin_initiation; inr_monitoring." in text


def test_excludes_icd_condition_titles():
    """ICD codes/titles must NOT appear in the embedding text."""
    row = {
        "title": "Section 1",
        "scope_rationale": "Rationale text.",
        "icd11_scope": ["BC81.3", "BC81.30", "BC81.31"],
        "procedure_scope": [],
    }
    text = _build_scope_text(row)
    assert "BC81.3" not in text
    assert "Conditions covered" not in text
    assert text == "Rationale text."


def test_rationale_only_when_no_procedures():
    row = {
        "title": "Section 1",
        "scope_rationale": "Just the rationale.",
        "icd11_scope": [],
        "procedure_scope": [],
    }
    assert _build_scope_text(row) == "Just the rationale."


def test_falls_back_to_title_when_empty():
    row = {
        "title": "Section 7: Implementation",
        "scope_rationale": None,
        "icd11_scope": [],
        "procedure_scope": [],
    }
    assert _build_scope_text(row) == "Section 7: Implementation"


def test_procedure_only_cpg_has_no_rationale_dependency():
    """Procedure-only CPG (empty icd, has procedure tags) still produces text."""
    row = {
        "title": "Section 2",
        "scope_rationale": "Anaesthesia medication safety guidance.",
        "icd11_scope": [],
        "procedure_scope": ["medication_labelling", "high_alert_medication"],
    }
    text = _build_scope_text(row)
    assert "Anaesthesia medication safety guidance." in text
    assert "Procedures: medication_labelling; high_alert_medication." in text


def test_backfill_embeds_each_unique_text_once():
    """4 rows across 2 CPGs (2 unique scope texts) -> only 2 embedding calls."""
    rows = [
        # CPG A: 3 sections, identical scope_rationale -> 1 unique text
        {"id": "a1", "title": "A1", "scope_rationale": "Rationale A.",
         "icd11_scope": ["BC81.3"], "procedure_scope": [], "scope_verified": True,
         "scope_embedding": None},
        {"id": "a2", "title": "A2", "scope_rationale": "Rationale A.",
         "icd11_scope": ["BC81.3"], "procedure_scope": [], "scope_verified": True,
         "scope_embedding": None},
        {"id": "a3", "title": "A3", "scope_rationale": "Rationale A.",
         "icd11_scope": ["BC81.3"], "procedure_scope": [], "scope_verified": True,
         "scope_embedding": None},
        # CPG B: 1 section -> 1 unique text
        {"id": "b1", "title": "B1", "scope_rationale": "Rationale B.",
         "icd11_scope": ["BA00"], "procedure_scope": [], "scope_verified": True,
         "scope_embedding": None},
    ]

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")
    conn.fetch = AsyncMock(return_value=rows)
    conn.executemany = AsyncMock()
    conn.close = AsyncMock()

    embed = AsyncMock(return_value=[0.1] * 1536)

    with patch("ddx.backfill_scope_embeddings.asyncpg.connect", AsyncMock(return_value=conn)), \
         patch("ddx.backfill_scope_embeddings.generate_embedding", embed), \
         patch.dict("os.environ", {"DATABASE_URL": "postgresql://x"}):
        result = asyncio.get_event_loop().run_until_complete(
            backfill(force=False, dry_run=False, only_verified=True)
        )

    # 2 unique texts -> 2 embedding calls, but all 4 rows updated
    assert embed.call_count == 2
    assert result["embedding_calls"] == 2
    assert result["updated_rows"] == 4
    # all 4 rows written via executemany
    written = sum(len(call.args[1]) for call in conn.executemany.call_args_list)
    assert written == 4
