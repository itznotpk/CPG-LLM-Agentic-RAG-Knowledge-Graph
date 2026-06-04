"""
Regenerate tasks/cpg_scope_review.md from current DB state.

Use this when:
- The classifier's review file was wiped by a failed second run, or
- Manual SQL fixes (e.g. migration 002) changed scopes outside the classifier, or
- You just want a fresh artifact reflecting the DB without re-calling the LLM.

No LLM calls. Read-only against documents. Overwrites tasks/cpg_scope_review.md.

Usage:
    python -m ingestion.regenerate_scope_review
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = PROJECT_ROOT / "tasks" / "cpg_scope_review.md"


async def fetch_groups(conn: asyncpg.Connection) -> list[dict]:
    # Can't aggregate TEXT[] columns directly — Postgres rejects MIN /
    # ARRAY_AGG(DISTINCT ...) over arrays that contain '{}'. Pick one
    # representative row per group via DISTINCT ON, then join a separate
    # count/flags aggregate.
    rows = await conn.fetch(
        """
        WITH grouped AS (
            SELECT DISTINCT ON (metadata->>'cpg_name')
                metadata->>'cpg_name'  AS cpg_name,
                icd11_scope,
                procedure_scope,
                scope_rationale,
                classified_at
            FROM documents
            WHERE metadata->>'cpg_name' IS NOT NULL
            ORDER BY metadata->>'cpg_name', id
        ),
        agg AS (
            SELECT
                metadata->>'cpg_name'        AS cpg_name,
                COUNT(*)                     AS row_count,
                BOOL_AND(scope_verified)     AS all_verified,
                MAX(classified_at)           AS last_classified_at
            FROM documents
            WHERE metadata->>'cpg_name' IS NOT NULL
            GROUP BY metadata->>'cpg_name'
        )
        SELECT
            g.cpg_name,
            a.row_count,
            g.icd11_scope,
            g.procedure_scope,
            g.scope_rationale,
            a.all_verified,
            a.last_classified_at
        FROM grouped g
        JOIN agg a USING (cpg_name)
        ORDER BY g.cpg_name;
        """
    )
    return [dict(r) for r in rows]


def format_scope(scope: list[str] | None) -> str:
    if not scope:
        return "(none)"
    return ", ".join(f"`{s}`" for s in scope)


def render_section(group: dict) -> str:
    name = group["cpg_name"]
    icd = format_scope(group["icd11_scope"])
    proc = format_scope(group["procedure_scope"])
    rationale = group["scope_rationale"] or "(no rationale recorded)"
    rows = group["row_count"]
    classified = group["last_classified_at"]
    classified_s = classified.isoformat() if classified else "never"
    verified_marker = " ✅" if group["all_verified"] else ""

    return (
        f"## {name}{verified_marker}\n"
        f"- Rows in DB: {rows}\n"
        f"- Last classified: {classified_s}\n"
        f"- Proposed icd11_scope: {icd}\n"
        f"- Proposed procedure_scope: {proc}\n"
        f"- Rationale: {rationale}\n"
        f"- [ ] Approve / [ ] Edit / [ ] Reject\n"
    )


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in environment")

    conn = await asyncpg.connect(db_url)
    try:
        groups = await fetch_groups(conn)
    finally:
        await conn.close()

    if not groups:
        raise RuntimeError(
            "No documents have metadata->>'cpg_name' set. "
            "Run ingestion + classification first."
        )

    now = datetime.now(timezone.utc).isoformat()
    header = (
        f"# CPG Scope Review — regenerated {now}\n\n"
        "Source of truth is the `documents` table. Edit the lists below to "
        "correct any scope, then mark Approve / Edit / Reject. The Step 04 "
        "verifier will parse this file.\n\n"
        f"Groups: {len(groups)}\n\n"
        "---\n\n"
    )

    body = "\n---\n\n".join(render_section(g) for g in groups)

    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text(header + body + "\n", encoding="utf-8")

    logger.info(
        "Wrote %s — %d CPG groups, %d total rows.",
        REVIEW_PATH.relative_to(PROJECT_ROOT),
        len(groups),
        sum(g["row_count"] for g in groups),
    )


if __name__ == "__main__":
    asyncio.run(main())
