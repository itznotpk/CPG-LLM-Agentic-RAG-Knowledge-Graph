"""
Tests for ingestion/verify_cpg_scope.py — Step 04.

All DB interactions are mocked; no real DB or LLM calls.

Contract (post-2026-05-22): the review file is the source of truth. Both Approve
and Edit parse + write scope (icd11_scope, procedure_scope, scope_rationale) and
stamp scope_verified. scope_rationale comes from `cpg_scope_rationale` (the
DB-bound text); `icd11_rationale` and `ICD-11 hierarchy` are audit-only/ignored.
A CPG matching 0 documents rows is skipped (not yet ingested), not an error.
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
    validate_scope_section,
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
        "- icd11_rationale: Short audit note (ignored).\n"
        "- cpg_scope_rationale: Rich DB-bound scope description.\n"
        "- [x] Approve / [ ] Edit / [ ] Reject\n"
    )


def _edit_section(cpg_name: str = "Test-CPG", icd: str = "`BC81`, `BA02`", proc: str = "(none)") -> str:
    return (
        f"## {cpg_name}\n"
        "- Rows in DB: 5\n"
        f"- Proposed icd11_scope: {icd}\n"
        f"- Proposed procedure_scope: {proc}\n"
        "- icd11_rationale: Short audit note (ignored).\n"
        "- cpg_scope_rationale: Updated rich description.\n"
        "- [ ] Approve / [x] Edit / [ ] Reject\n"
    )


def _reject_section(cpg_name: str = "Test-CPG") -> str:
    return (
        f"## {cpg_name}\n"
        "- Rows in DB: 5\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- cpg_scope_rationale: Some reason.\n"
        "- [ ] Approve / [ ] Edit / [x] Reject\n"
    )


def _none_section(cpg_name: str = "Test-CPG") -> str:
    return (
        f"## {cpg_name}\n"
        "- Rows in DB: 5\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- cpg_scope_rationale: Some reason.\n"
        "- [ ] Approve / [ ] Edit / [ ] Reject\n"
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_parse_approve_section_now_parses_scope(tmp_path):
    """Approve now parses scope too (review file is source of truth)."""
    p = _make_tmp_review(tmp_path, _approve_section())
    results = parse_review_file(p)
    assert len(results) == 1
    sec = results[0]
    assert sec.decision == "approve"
    assert sec.new_icd11_scope == ["BC81"]
    assert sec.new_procedure_scope == []
    # rationale comes from cpg_scope_rationale, NOT icd11_rationale
    assert sec.new_rationale == "Rich DB-bound scope description."


def test_parse_edit_section_with_codes(tmp_path):
    p = _make_tmp_review(tmp_path, _edit_section())
    results = parse_review_file(p)
    assert len(results) == 1
    sec = results[0]
    assert sec.decision == "edit"
    assert sec.new_icd11_scope == ["BC81", "BA02"]
    assert sec.new_procedure_scope == []
    assert sec.new_rationale == "Updated rich description."


def test_icd11_rationale_is_ignored(tmp_path):
    """Only cpg_scope_rationale feeds new_rationale; icd11_rationale is audit-only."""
    body = (
        "## Test-CPG\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- icd11_rationale: THIS SHOULD NOT BE STORED.\n"
        "- cpg_scope_rationale: Stored description.\n"
        "- ICD-11 hierarchy: Chapter 11 > ... (ignored).\n"
        "- [x] Approve / [ ] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    sec = parse_review_file(p)[0]
    assert sec.new_rationale == "Stored description."


def test_cpg_scope_rationale_with_qualifier_and_multiple_lines(tmp_path):
    """Cancer-Pain style: qualified label + multiple cpg_scope_rationale lines concatenate."""
    body = (
        "## Cancer-Pain(2nd Edition)\n"
        "- Proposed icd11_scope: `MG30.1`\n"
        "- Proposed procedure_scope: `pain_assessment`\n"
        "- cpg_scope_rationale (adult, Part A): Adult description.\n"
        "- cpg_scope_rationale (paediatric, Part B): Paediatric description.\n"
        "- [x] Approve / [ ] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    sec = parse_review_file(p)[0]
    assert sec.new_rationale == "Adult description. Paediatric description."


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
        "- cpg_scope_rationale: test.\n"
        "- [X] Approve / [ ] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    results = parse_review_file(p)
    assert results[0].decision == "approve"


def test_parse_box_with_internal_whitespace(tmp_path):
    # [x ] Edit
    body = (
        "## Dyslipidaemia(6th-Edition)\n"
        "- Proposed icd11_scope: `5C80`\n"
        "- Proposed procedure_scope: (none)\n"
        "- cpg_scope_rationale: test.\n"
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
        "- cpg_scope_rationale: test.\n"
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
        "- cpg_scope_rationale: test.\n"
        "- [x] Approve / [x] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    with pytest.raises(ValueError, match="Multiple decisions"):
        parse_review_file(p)


def test_validate_drops_invalid_codes(tmp_path):
    body = _edit_section(icd="`BC81`, `INVALID`, `2C60`")
    p = _make_tmp_review(tmp_path, body)
    sec = parse_review_file(p)[0]
    assert sec.decision == "edit"
    validated = validate_scope_section(sec)
    assert "BC81" in validated.new_icd11_scope
    assert "2C60" in validated.new_icd11_scope
    assert "INVALID" not in validated.new_icd11_scope


def test_validate_all_invalid_raises(tmp_path):
    body = _edit_section(icd="`INVALID`, `BADCODE`", proc="(none)")
    p = _make_tmp_review(tmp_path, body)
    sec = parse_review_file(p)[0]
    with pytest.raises(ValueError):
        validate_scope_section(sec)


def test_validate_handles_none_string(tmp_path):
    body = _edit_section(icd="`BC81`", proc="(none)")
    p = _make_tmp_review(tmp_path, body)
    sec = parse_review_file(p)[0]
    validated = validate_scope_section(sec)
    assert validated.new_procedure_scope == []


def test_procedure_only_cpg_allows_empty_icd(tmp_path):
    body = (
        "## Anaesthesia-Medication-Safety\n"
        "- Proposed icd11_scope: (none)\n"
        "- Proposed procedure_scope: `medication_labelling`\n"
        "- cpg_scope_rationale: Procedure-only guideline.\n"
        "- [x] Approve / [ ] Edit / [ ] Reject\n"
    )
    p = _make_tmp_review(tmp_path, body)
    sec = parse_review_file(p)[0]
    validated = validate_scope_section(sec)  # must not raise
    assert validated.new_icd11_scope == []
    assert validated.new_procedure_scope == ["medication_labelling"]


def test_parse_ignores_extra_bullets(tmp_path):
    body = (
        "## Test-CPG\n"
        "- Rows in DB: 5\n"
        "- Last classified: 2026-05-08T14:00:00+00:00\n"
        "- Proposed icd11_scope: `BC81`\n"
        "- Proposed procedure_scope: (none)\n"
        "- cpg_scope_rationale: Some reason.\n"
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


def test_db_apply_approve_writes_scope():
    """Approve now writes scope columns (not just stamps verified)."""
    conn = _make_mock_conn("UPDATE 3")
    sec = CPGSectionDecision(
        cpg_name="Test-CPG", decision="approve",
        new_icd11_scope=["BC81"], new_procedure_scope=[], new_rationale="r",
        raw_section_text="",
    )

    result = asyncio.run(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    call_args = conn.execute.call_args_list
    assert len(call_args) == 1
    sql = call_args[0].args[0]
    assert "icd11_scope" in sql
    assert "scope_rationale" in sql
    assert "scope_verified" in sql and "TRUE" in sql
    assert len(result["approved"]) == 1


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

    asyncio.run(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    call_args = conn.execute.call_args_list
    assert len(call_args) == 1
    sql = call_args[0].args[0]
    assert "icd11_scope" in sql
    assert "procedure_scope" in sql
    positional_args = call_args[0].args
    assert ["BC81"] in positional_args


def test_db_apply_reject_does_not_call_update():
    conn = _make_mock_conn()
    sec = CPGSectionDecision(
        cpg_name="Test-CPG", decision="reject", raw_section_text=""
    )

    asyncio.run(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    conn.execute.assert_not_called()


def test_dry_run_makes_no_db_writes():
    conn = _make_mock_conn()
    secs = [
        CPGSectionDecision(
            cpg_name="A", decision="approve",
            new_icd11_scope=["BC81"], new_procedure_scope=[], new_rationale="r",
            raw_section_text="",
        ),
        CPGSectionDecision(
            cpg_name="B", decision="edit",
            new_icd11_scope=["BC81"], new_procedure_scope=[], new_rationale="r",
            raw_section_text="",
        ),
        CPGSectionDecision(cpg_name="C", decision="reject", raw_section_text=""),
    ]

    asyncio.run(
        apply_decisions(conn, secs, verifier="Tester", dry_run=True)
    )

    conn.execute.assert_not_called()


def test_zero_rows_is_skipped_not_error():
    """A CPG matching 0 documents rows (not yet ingested) is skipped, not fatal."""
    conn = _make_mock_conn("UPDATE 0")
    sec = CPGSectionDecision(
        cpg_name="Not-Yet-Ingested", decision="approve",
        new_icd11_scope=["BC81"], new_procedure_scope=[], new_rationale="r",
        raw_section_text="",
    )

    result = asyncio.run(
        apply_decisions(conn, [sec], verifier="Tester", dry_run=False)
    )

    assert "Not-Yet-Ingested" in result["skipped"]
    assert result["approved"] == []
    assert result["errors"] == []
