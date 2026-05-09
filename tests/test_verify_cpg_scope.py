"""
Tests for ingestion/verify_cpg_scope.py — Step 04.

All DB interactions are mocked; no real DB or LLM calls.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.verify_cpg_scope import (
    CPGSectionDecision,
    apply_decisions,
    parse_review_file,
    validate_edit_section,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmp_review(tmp_path: Path, body: str) -> Path:
    """Write a minimal review file to a temp dir and return the path."""
    p = tmp_path / "review.md"
    header = "# CPG Scope Review\n\nGroups: 1\n\n---\n\n"
    p.write_text(header + body, encoding="utf-8")
    return p


def _approve_section(cpg_name: str = "Test-CPG") -> str:
    return (
        f"## {cpg_name}\n"
        "- Rows in DB: 5\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: Some reason.\n"
        "- [x] Approve / [ ] Edit / [ ] Reject\n"
    )


def _edit_section(cpg_name: str = "Test-CPG", icd: str = "`BC81`, `BA02`", proc: str = "(none)") -> str:
    return (
        f"## {cpg_name}\n"
        "- Rows in DB: 5\n"
        f"- Proposed icd11_scope: {icd}\n"
        f"- Proposed procedure_scope: {proc}\n"
        "- Rationale: Updated reason.\n"
        "- [ ] Approve / [x] Edit / [ ] Reject\n"
    )


def _reject_section(cpg_name: str = "Test-CPG") -> str:
    return (
        f"## {cpg_name}\n"
        "- Rows in DB: 5\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: Some reason.\n"
        "- [ ] Approve / [ ] Edit / [x] Reject\n"
    )


def _none_section(cpg_name: str = "Test-CPG") -> str:
    return (
        f"## {cpg_name}\n"
        "- Rows in DB: 5\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: Some reason.\n"
        "- [ ] Approve / [ ] Edit / [ ] Reject\n"
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_parse_approve_section(tmp_path):
    p = _make_tmp_review(tmp_path, _approve_section())
    results = parse_review_file(p)
    assert len(results) == 1
    sec = results[0]
    assert sec.decision == "approve"
    assert sec.new_icd11_scope is None
    assert sec.new_procedure_scope is None
    assert sec.new_rationale is None


def test_parse_edit_section_with_codes(tmp_path):
    p = _make_tmp_review(tmp_path, _edit_section())
    results = parse_review_file(p)
    assert len(results) == 1
    sec = results[0]
    assert sec.decision == "edit"
    assert sec.new_icd11_scope == ["BC81", "BA02"]
    assert sec.new_procedure_scope == []


def test_parse_reject_section(tmp_path):
    p = _make_tmp_review(tmp_path, _reject_section())
    results = parse_review_file(p)
    assert results[0].decision == "reject"


def test_parse_none_section(tmp_path):
    p = _make_tmp_review(tmp_path, _none_section())
    results = parse_review_file(p)
    assert results[0].decision == "none"


def test_parse_uppercase_X_box(tmp_path):
    body = (
        "## NSTEMI(2011)\n"
        "- Proposed icd11_scope: `BA41`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: test.\n"
        "- [X] Approve / [ ] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    results = parse_review_file(p)
    assert results[0].decision == "approve"


def test_parse_box_with_internal_whitespace(tmp_path):
    # [x ] Approve
    body = (
        "## Dyslipidaemia(6th-Edition)\n"
        "- Proposed icd11_scope: `5C80`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: test.\n"
        "- [ ] Approve / [x ] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    results = parse_review_file(p)
    assert results[0].decision == "edit"

    # [ x ] Approve
    body2 = (
        "## Dyslipidaemia(6th-Edition)\n"
        "- Proposed icd11_scope: `5C80`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: test.\n"
        "- [ x ] Approve / [ ] Edit / [ ] Reject\n"
    )
    p2 = _make_tmp_review(tmp_path, body2)
    results2 = parse_review_file(p2)
    assert results2[0].decision == "approve"


def test_parse_multiple_decisions_raises(tmp_path):
    body = (
        "## Test-CPG\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: test.\n"
        "- [x] Approve / [x] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    with pytest.raises(ValueError, match="Multiple decisions"):
        parse_review_file(p)


def test_parse_edit_drops_invalid_codes(tmp_path):
    body = _edit_section(icd="`BC81`, `INVALID`, `2C60`")
    p = _make_tmp_review(tmp_path, body)
    results = parse_review_file(p)
    sec = results[0]
    assert sec.decision == "edit"
    validated = validate_edit_section(sec)
    assert "BC81" in validated.new_icd11_scope
    assert "2C60" in validated.new_icd11_scope
    assert "INVALID" not in validated.new_icd11_scope


def test_parse_edit_all_invalid_raises(tmp_path):
    body = _edit_section(icd="`INVALID`, `BADCODE`", proc="(none)")
    p = _make_tmp_review(tmp_path, body)
    results = parse_review_file(p)
    sec = results[0]
    assert sec.decision == "edit"
    with pytest.raises(ValueError):
        validate_edit_section(sec)


def test_parse_edit_handles_none_string(tmp_path):
    body = _edit_section(icd="`BC81`", proc="(none)")
    p = _make_tmp_review(tmp_path, body)
    results = parse_review_file(p)
    sec = results[0]
    validated = validate_edit_section(sec)
    assert validated.new_procedure_scope == []


def test_parse_ignores_extra_bullets(tmp_path):
    body = (
        "## Test-CPG\n"
        "- Rows in DB: 5\n"
        "- Last classified: 2026-05-08T14:00:00+00:00\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- Rationale: Some reason.\n"
        "- ICD-11 hierarchy: Chapter 11 > ...\n"
        "- [x] Approve / [ ] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    results = parse_review_file(p)
    assert results[0].decision == "approve"
    assert results[0].cpg_name == "Test-CPG"


# ---------------------------------------------------------------------------
# DB application tests (mock pool)
# ---------------------------------------------------------------------------

def _make_mock_conn(execute_result="UPDATE 5"):
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=execute_result)
    conn.fetchval = AsyncMock(return_value=0)
    # transaction context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    return conn


def test_db_apply_approve_only_flips_metadata():
    """Approve UPDATE must not touch icd11_scope columns."""
    conn = _make_mock_conn("UPDATE 3")
    sec = CPGSectionDecision(
        cpg_name="Test-CPG", decision="approve", raw_section_text=""
    )

    asyncio.get_event_loop().run_until_complete(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    call_args = conn.execute.call_args_list
    assert len(call_args) == 1
    sql = call_args[0].args[0]
    assert "icd11_scope" not in sql
    assert "scope_verified = TRUE" in sql


def test_db_apply_edit_writes_new_scope():
    conn = _make_mock_conn("UPDATE 5")
    sec = CPGSectionDecision(
        cpg_name="Test-CPG",
        decision="edit",
        new_icd11_scope=["BC81"],
        new_procedure_scope=[],
        new_rationale="Edited reason.",
        raw_section_text="",
    )

    asyncio.get_event_loop().run_until_complete(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    call_args = conn.execute.call_args_list
    assert len(call_args) == 1
    sql = call_args[0].args[0]
    assert "icd11_scope" in sql
    assert "procedure_scope" in sql
    # Verify the new scope list was passed
    positional_args = call_args[0].args
    assert ["BC81"] in positional_args


def test_db_apply_reject_does_not_call_update():
    conn = _make_mock_conn()
    sec = CPGSectionDecision(
        cpg_name="Test-CPG", decision="reject", raw_section_text=""
    )

    asyncio.get_event_loop().run_until_complete(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    conn.execute.assert_not_called()


def test_dry_run_makes_no_db_writes():
    conn = _make_mock_conn()
    secs = [
        CPGSectionDecision(cpg_name="A", decision="approve", raw_section_text=""),
        CPGSectionDecision(
            cpg_name="B", decision="edit",
            new_icd11_scope=["BC81"], new_procedure_scope=[], new_rationale="r",
            raw_section_text="",
        ),
        CPGSectionDecision(cpg_name="C", decision="reject", raw_section_text=""),
    ]

    asyncio.get_event_loop().run_until_complete(
        apply_decisions(conn, secs, verifier="Tester", dry_run=True)
    )

    conn.execute.assert_not_called()


def test_idempotency_already_verified():
    """If DB returns 0 rows updated for approve, and already-verified count > 0, don't error."""
    conn = _make_mock_conn("UPDATE 0")
    conn.fetchval = AsyncMock(return_value=5)  # 5 rows already verified
    sec = CPGSectionDecision(
        cpg_name="Test-CPG", decision="approve", raw_section_text=""
    )

    result = asyncio.get_event_loop().run_until_complete(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    # Should not raise; the already-verified rows are logged and recorded
    assert len(result["approved"]) == 1
    assert result["approved"][0].get("note") == "already verified"
