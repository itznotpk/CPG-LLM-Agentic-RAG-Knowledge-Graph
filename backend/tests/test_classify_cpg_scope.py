"""
Unit tests for ingestion/classify_cpg_scope.py.
No real LLM or DB calls are made.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.classify_cpg_scope import (
    DocumentRow,
    ScopeProposal,
    derive_group_key,
    parse_scope_proposal,
    update_group_scope,
    validate_icd_codes,
)


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

def test_group_key_from_path():
    assert derive_group_key("markdown/AF(2012)/section-7.md") == "AF(2012)"
    assert derive_group_key("markdown\\AF(2012)\\section-7.md") == "AF(2012)"
    assert derive_group_key("CPG X.md") == "CPG X"
    assert derive_group_key("weird-id-string") is None


def test_scope_proposal_validates_good_json():
    raw = json.dumps({
        "icd11_scope": ["BC81", "BC9Z"],
        "procedure_scope": [],
        "rationale": "Atrial fibrillation CPG.",
    })
    proposal = parse_scope_proposal(raw)
    assert proposal.icd11_scope == ["BC81", "BC9Z"]
    assert proposal.procedure_scope == []
    assert "Atrial" in proposal.rationale


def test_scope_proposal_strips_code_fence():
    raw = '```json\n{"icd11_scope": ["BC81"], "procedure_scope": [], "rationale": "test"}\n```'
    proposal = parse_scope_proposal(raw)
    assert proposal.icd11_scope == ["BC81"]


def test_invalid_icd_codes_are_dropped():
    codes = ["BC81", "not-a-code", "BA00-BA04", "??"]
    valid = validate_icd_codes(codes)
    assert valid == ["BC81", "BA00-BA04"]


def test_empty_scope_rejected():
    raw = json.dumps({"icd11_scope": [], "procedure_scope": [], "rationale": "nothing"})
    with pytest.raises((ValueError, Exception)):
        parse_scope_proposal(raw)


# ---------------------------------------------------------------------------
# DB mock tests
# ---------------------------------------------------------------------------

def _make_docs(n: int = 3) -> list[DocumentRow]:
    return [
        DocumentRow(
            id=f"00000000-0000-0000-0000-{i:012d}",
            source=f"markdown/TestCPG/section-{i}.md",
            title=f"Section {i}",
            cpg_name="TestCPG",
            file_path="",
        )
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_db_update_called_per_group():
    conn = AsyncMock()
    conn.execute = AsyncMock()

    docs = _make_docs(3)
    proposal = ScopeProposal(icd11_scope=["BC81"], procedure_scope=[], rationale="test")

    await update_group_scope(conn, docs, proposal, dry_run=False)

    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert call_args[1] == ["BC81"]
    assert call_args[4] == [doc.id for doc in docs]


@pytest.mark.asyncio
async def test_dry_run_makes_no_db_writes():
    conn = AsyncMock()
    conn.execute = AsyncMock()

    docs = _make_docs(3)
    proposal = ScopeProposal(icd11_scope=["BC81"], procedure_scope=[], rationale="test")

    rows = await update_group_scope(conn, docs, proposal, dry_run=True)

    conn.execute.assert_not_called()
    assert rows == 3
