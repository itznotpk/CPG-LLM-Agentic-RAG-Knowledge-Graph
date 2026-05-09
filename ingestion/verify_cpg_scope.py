"""
Step 04 — CPG Scope Review Verifier.

Parses tasks/cpg_scope_review.md and writes reviewer decisions back to `documents`.

Usage:
    python -m ingestion.verify_cpg_scope --verifier "Dr Smith"
    python -m ingestion.verify_cpg_scope --verifier "Dr Smith" --dry-run
    python -m ingestion.verify_cpg_scope --verifier "Dr Smith" --only "Atrial-Fibrillation(2012),STEMI(4th Edition)"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import asyncpg
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_PATH = PROJECT_ROOT / "tasks" / "cpg_scope_review.md"
REPORT_PATH = PROJECT_ROOT / "tasks" / "cpg_scope_verification_report.md"

# ICD-11 code pattern (from classify_cpg_scope.py)
_ICD_CODE_PATTERN = re.compile(
    r'^[0-9A-Z]{2,4}(\.[0-9A-Z]{1,2})?$|^[0-9A-Z]{2,4}-[0-9A-Z]{2,4}$'
)
_PROC_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')
_CHECKED_BOX = re.compile(r'\[\s*[xX]\s*\]')


class CPGSectionDecision(BaseModel):
    cpg_name: str
    decision: Literal["approve", "edit", "reject", "none"]
    new_icd11_scope: list[str] | None = None
    new_procedure_scope: list[str] | None = None
    new_rationale: str | None = None
    raw_section_text: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_scope_list(text: str) -> list[str]:
    """Parse a backtick-delimited scope list from a bullet line value."""
    text = text.strip()
    if re.match(r'^\(none\)$', text, re.IGNORECASE):
        return []
    # Extract items from backtick-quoted tokens or bare comma-separated words
    backtick_items = re.findall(r'`([^`]+)`', text)
    if backtick_items:
        return [item.strip() for item in backtick_items if item.strip()]
    # Fall back to comma-separated bare values
    return [item.strip() for item in text.split(',') if item.strip()]


def _detect_decision(decision_line: str) -> Literal["approve", "edit", "reject", "none"]:
    """Detect which checkbox is ticked in a decision line."""
    # Split into three segments by the decision keyword
    segments = {
        "approve": "",
        "edit": "",
        "reject": "",
    }
    # Find positions of each keyword
    lower = decision_line.lower()
    for key in segments:
        idx = lower.find(key)
        if idx == -1:
            continue
        # Find the checkbox immediately before the keyword
        before = decision_line[:idx]
        # Walk backward to find the last '[...]' pattern
        m = list(re.finditer(r'\[\s*[xX]?\s*\]', before))
        if m:
            segments[key] = m[-1].group(0)

    checked = [k for k, v in segments.items() if _CHECKED_BOX.fullmatch(v.strip())]
    if len(checked) > 1:
        raise ValueError(f"Multiple decisions marked: {checked}")
    if len(checked) == 0:
        return "none"
    return checked[0]  # type: ignore[return-value]


def parse_review_file(path: Path) -> list[CPGSectionDecision]:
    text = path.read_text(encoding="utf-8")
    # Split on section headings (## ...) — skip file-level header
    raw_sections = re.split(r'\n## ', text)
    sections: list[CPGSectionDecision] = []

    for raw in raw_sections[1:]:  # skip header block
        lines = raw.split('\n')
        # First line is the CPG name
        cpg_name = lines[0].strip()
        # Strip trailing ✅ marker
        cpg_name = re.sub(r'\s*✅\s*$', '', cpg_name).strip()

        # Find the decision line (contains Approve / Edit / Reject)
        decision_line = None
        for line in lines:
            if re.search(r'approve', line, re.IGNORECASE) and re.search(r'reject', line, re.IGNORECASE):
                decision_line = line
                break

        if decision_line is None:
            logger.info("%s: no decision line found, skipped", cpg_name)
            sections.append(CPGSectionDecision(
                cpg_name=cpg_name, decision="none", raw_section_text=raw
            ))
            continue

        try:
            decision = _detect_decision(decision_line)
        except ValueError as exc:
            raise ValueError(f"Multiple decisions marked for CPG '{cpg_name}': {exc}") from exc

        if decision == "none":
            logger.info("%s: no decision marked, skipped", cpg_name)
            sections.append(CPGSectionDecision(
                cpg_name=cpg_name, decision="none", raw_section_text=raw
            ))
            continue

        if decision in ("approve", "reject"):
            sections.append(CPGSectionDecision(
                cpg_name=cpg_name, decision=decision, raw_section_text=raw
            ))
            continue

        # decision == "edit": parse scope bullets
        icd11_scope: list[str] | None = None
        procedure_scope: list[str] | None = None
        rationale: str | None = None

        i = 1
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.lstrip('- ').strip()

            if re.match(r'Proposed icd11_scope\s*:', stripped, re.IGNORECASE):
                val = re.split(r'Proposed icd11_scope\s*:', stripped, flags=re.IGNORECASE, maxsplit=1)[1]
                icd11_scope = _parse_scope_list(val)

            elif re.match(r'Proposed procedure_scope\s*:', stripped, re.IGNORECASE):
                val = re.split(r'Proposed procedure_scope\s*:', stripped, flags=re.IGNORECASE, maxsplit=1)[1]
                procedure_scope = _parse_scope_list(val)

            elif re.match(r'Rationale\s*:', stripped, re.IGNORECASE):
                val = re.split(r'Rationale\s*:', stripped, flags=re.IGNORECASE, maxsplit=1)[1].strip()
                # Accumulate multi-line rationale (until next bullet or blank line)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].rstrip()
                    if next_line.lstrip().startswith('- ') or next_line.strip() == '':
                        break
                    val += ' ' + next_line.strip()
                    j += 1
                rationale = val.strip()
                i = j
                continue

            i += 1

        sections.append(CPGSectionDecision(
            cpg_name=cpg_name,
            decision="edit",
            new_icd11_scope=icd11_scope if icd11_scope is not None else [],
            new_procedure_scope=procedure_scope if procedure_scope is not None else [],
            new_rationale=rationale,
            raw_section_text=raw,
        ))

    return sections


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Procedure-only CPG names (empty icd11_scope is allowed)
_PROCEDURE_ONLY_CPGS = {"Patient-Safety-Minimal-Monitoring", "Pre-Anaesthetic-Assessment"}


def validate_edit_section(sec: CPGSectionDecision) -> CPGSectionDecision:
    """Validate and filter scope codes; returns updated section or raises."""
    assert sec.decision == "edit"

    valid_icd: list[str] = []
    for code in (sec.new_icd11_scope or []):
        if _ICD_CODE_PATTERN.match(code):
            valid_icd.append(code)
        else:
            logger.warning("%s: dropping invalid ICD-11 code %r", sec.cpg_name, code)

    valid_proc: list[str] = []
    for tag in (sec.new_procedure_scope or []):
        if _PROC_PATTERN.match(tag):
            valid_proc.append(tag)
        else:
            logger.warning("%s: dropping invalid procedure tag %r", sec.cpg_name, tag)

    if sec.cpg_name in _PROCEDURE_ONLY_CPGS:
        if not valid_proc:
            raise ValueError(f"{sec.cpg_name}: procedure-only CPG must have non-empty procedure_scope after filtering")
    else:
        if not valid_icd and not valid_proc:
            raise ValueError(f"{sec.cpg_name}: both icd11_scope and procedure_scope are empty after filtering")

    return sec.model_copy(update={"new_icd11_scope": valid_icd, "new_procedure_scope": valid_proc})


# ---------------------------------------------------------------------------
# DB application
# ---------------------------------------------------------------------------

async def apply_decisions(
    conn: asyncpg.Connection,
    decisions: list[CPGSectionDecision],
    verifier: str,
    dry_run: bool,
) -> dict:
    """Apply all decisions in a single transaction. Returns result summary dict."""
    approved: list[dict] = []
    edited: list[dict] = []
    rejected: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    # Validate edit sections first (non-fatal per section)
    validated: list[CPGSectionDecision] = []
    for sec in decisions:
        if sec.decision == "edit":
            try:
                validated.append(validate_edit_section(sec))
            except ValueError as exc:
                logger.error("Validation error for %s: %s", sec.cpg_name, exc)
                errors.append(f"{sec.cpg_name}: {exc}")
        else:
            validated.append(sec)

    if dry_run:
        for sec in validated:
            if sec.decision == "approve":
                approved.append({"cpg_name": sec.cpg_name, "rows": 0, "note": "dry-run"})
                logger.info("[DRY-RUN] Would APPROVE %s", sec.cpg_name)
            elif sec.decision == "edit":
                edited.append({
                    "cpg_name": sec.cpg_name,
                    "rows": 0,
                    "icd11": sec.new_icd11_scope,
                    "proc": sec.new_procedure_scope,
                })
                logger.info("[DRY-RUN] Would EDIT %s: icd11=%s proc=%s",
                            sec.cpg_name, sec.new_icd11_scope, sec.new_procedure_scope)
            elif sec.decision == "reject":
                rejected.append(sec.cpg_name)
                logger.info("[DRY-RUN] Would REJECT %s", sec.cpg_name)
            else:
                skipped.append(sec.cpg_name)
        return {"approved": approved, "edited": edited, "rejected": rejected, "skipped": skipped, "errors": errors}

    async with conn.transaction():
        for sec in validated:
            if sec.decision == "approve":
                result = await conn.execute(
                    """
                    UPDATE documents
                    SET scope_verified = TRUE,
                        verified_at    = NOW(),
                        verified_by    = $1
                    WHERE metadata->>'cpg_name' = $2
                      AND scope_verified = FALSE
                    """,
                    verifier, sec.cpg_name,
                )
                n = int(result.split()[-1])
                if n == 0:
                    # Check if already verified
                    already = await conn.fetchval(
                        "SELECT COUNT(*) FROM documents WHERE metadata->>'cpg_name' = $1 AND scope_verified = TRUE",
                        sec.cpg_name,
                    )
                    if already == 0:
                        raise RuntimeError(f"APPROVE: cpg_name '{sec.cpg_name}' matched no rows")
                    logger.info("%s: already verified (%d rows), skipping stamp", sec.cpg_name, already)
                    approved.append({"cpg_name": sec.cpg_name, "rows": 0, "note": "already verified"})
                else:
                    logger.info("%s: approved %d rows", sec.cpg_name, n)
                    approved.append({"cpg_name": sec.cpg_name, "rows": n})

            elif sec.decision == "edit":
                result = await conn.execute(
                    """
                    UPDATE documents
                    SET icd11_scope     = $1,
                        procedure_scope = $2,
                        scope_rationale = $3,
                        scope_verified  = TRUE,
                        verified_at     = NOW(),
                        verified_by     = $4,
                        classified_at   = COALESCE(classified_at, NOW())
                    WHERE metadata->>'cpg_name' = $5
                    """,
                    sec.new_icd11_scope,
                    sec.new_procedure_scope,
                    sec.new_rationale,
                    verifier,
                    sec.cpg_name,
                )
                n = int(result.split()[-1])
                logger.info("%s: edited %d rows", sec.cpg_name, n)
                edited.append({
                    "cpg_name": sec.cpg_name,
                    "rows": n,
                    "icd11": sec.new_icd11_scope,
                    "proc": sec.new_procedure_scope,
                })

            elif sec.decision == "reject":
                rejected.append(sec.cpg_name)
                logger.info("%s: rejected (no DB write)", sec.cpg_name)

            else:  # none
                skipped.append(sec.cpg_name)

    return {"approved": approved, "edited": edited, "rejected": rejected, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(
    results: dict,
    verifier: str,
    dry_run: bool,
    review_file: Path,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    mode_tag = " [DRY-RUN]" if dry_run else ""
    lines: list[str] = [
        f"# CPG Scope Verification Report{mode_tag}",
        f"- Run at: {now}",
        f"- Verifier: {verifier}",
        f"- Review file: {review_file}",
        "",
    ]

    approved = results["approved"]
    edited = results["edited"]
    rejected = results["rejected"]
    skipped = results["skipped"]
    errors = results["errors"]

    lines.append(f"## Approved ({len(approved)})")
    for item in approved:
        note = f" — {item['note']}" if item.get("note") else f" — {item['rows']} rows stamped"
        lines.append(f"- {item['cpg_name']}{note}")
    lines.append("")

    lines.append(f"## Edited ({len(edited)})")
    for item in edited:
        icd_n = len(item.get("icd11") or [])
        proc_n = len(item.get("proc") or [])
        lines.append(f"- {item['cpg_name']} — {item['rows']} rows updated; {icd_n} ICD-11 codes, {proc_n} procedure tags")
    lines.append("")

    lines.append(f"## Rejected ({len(rejected)})")
    for name in rejected:
        lines.append(f"- {name}")
    lines.append("")

    lines.append(f"## Skipped ({len(skipped)})")
    for name in skipped:
        lines.append(f"- {name}")
    lines.append("")

    if errors:
        lines.append(f"## Errors ({len(errors)})")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    REPORT_PATH.write_text('\n'.join(lines), encoding='utf-8')
    logger.info("Verification report written: %s", REPORT_PATH)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def run(
    verifier: str,
    dry_run: bool = False,
    only: list[str] | None = None,
    review_file: Path = DEFAULT_REVIEW_PATH,
) -> dict:
    logger.info("Parsing review file: %s", review_file)
    decisions = parse_review_file(review_file)

    if only:
        decisions = [d for d in decisions if d.cpg_name in only]
        logger.info("--only filter applied: %s", [d.cpg_name for d in decisions])

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in environment")

    conn = await asyncpg.connect(db_url)
    try:
        results = await apply_decisions(conn, decisions, verifier=verifier, dry_run=dry_run)
    finally:
        await conn.close()

    write_report(results, verifier=verifier, dry_run=dry_run, review_file=review_file)

    approved_n = len(results["approved"])
    edited_n = len(results["edited"])
    rejected_n = len(results["rejected"])
    skipped_n = len(results["skipped"])
    errors_n = len(results["errors"])

    logger.info(
        "Summary: %d approved, %d edited, %d rejected, %d skipped, %d errors",
        approved_n, edited_n, rejected_n, skipped_n, errors_n,
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CPG scope decisions from review markdown")
    parser.add_argument("--verifier", required=True, help="Name/email written to verified_by column")
    parser.add_argument("--dry-run", action="store_true", help="Parse + validate only; no DB writes")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated CPG names to process")
    parser.add_argument("--review-file", type=Path, default=DEFAULT_REVIEW_PATH,
                        help="Path to cpg_scope_review.md (default: tasks/cpg_scope_review.md)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    only = [k.strip() for k in args.only.split(',')] if args.only else None
    asyncio.run(run(
        verifier=args.verifier,
        dry_run=args.dry_run,
        only=only,
        review_file=args.review_file,
    ))


if __name__ == "__main__":
    main()
