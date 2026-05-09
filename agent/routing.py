"""
ICD-11 to CPG routing layer.

Maps an ICD-11 code to a shortlist of CPG documents (grouped by CPG name) via:
  1. Structural match (exact code, 3-char prefix, 4-char prefix, lexicographic range)
  2. Semantic fallback (embed code title, vector search against verified-document chunks)

Each CPGDocRef represents one *CPG*, not one section row.  All section UUIDs for
that CPG are collected in document_ids so that downstream vector searches can
filter against the full CPG.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

from .db_utils import db_pool, vector_search
from .tools import generate_embedding

logger = logging.getLogger(__name__)


class CPGDocRef(BaseModel):
    cpg_name: str                        # e.g. "STEMI(4th Edition)"
    document_id: str                     # first/representative section UUID
    document_ids: list[str]              # ALL section UUIDs for this CPG
    title: str                           # title of the representative section row
    match_type: Literal["exact", "parent", "semantic"]
    score: float
    matched_scope: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RANGE_PATTERN = re.compile(r'^[A-Z0-9]{2,4}-[A-Z0-9]{2,4}$')


def _icd11_range_match(code: str, scope: list[str]) -> tuple[bool, str]:
    """Return (matched, entry) if code falls in any range entry of scope."""
    for entry in scope:
        if _RANGE_PATTERN.match(entry):
            low, high = entry.split("-", 1)
            if low <= code <= high:
                return True, entry
    return False, ""


def _determine_match(icd_code: str, icd11_scope: list[str]) -> tuple[Literal["exact", "parent"], str]:
    """Return (match_type, matched_scope) for a row that already passed SQL filter."""
    if icd_code in icd11_scope:
        return "exact", icd_code
    prefixes = [s for s in icd11_scope if icd_code.startswith(s) and len(s) <= len(icd_code)]
    if prefixes:
        return "parent", max(prefixes, key=len)
    # Shouldn't reach here if SQL is correct, but be safe
    return "parent", icd11_scope[0] if icd11_scope else ""


async def _structural_match(conn, icd_code: str) -> list[CPGDocRef]:
    rows = await conn.fetch(
        """
        SELECT id::text, title, icd11_scope, metadata->>'cpg_name' AS cpg_name
        FROM documents
        WHERE scope_verified = TRUE
          AND (
              $1 = ANY(icd11_scope)
              OR LEFT($1, 3) = ANY(icd11_scope)
              OR LEFT($1, 4) = ANY(icd11_scope)
          )
        """,
        icd_code,
    )

    # Group rows by cpg_name
    groups: dict[str, dict] = defaultdict(
        lambda: {"ids": [], "title": "", "icd11_scope": [], "match_type": "parent", "matched": ""}
    )
    for row in rows:
        name: str = row["cpg_name"] or row["id"]
        g = groups[name]
        g["ids"].append(row["id"])
        if not g["title"]:
            g["title"] = row["title"]
        g["icd11_scope"] = row["icd11_scope"]  # same for all rows of a CPG

        mt, ms = _determine_match(icd_code, row["icd11_scope"])
        # Prefer "exact" over "parent" if any row gives exact
        if g["match_type"] != "exact":
            g["match_type"] = mt
            g["matched"] = ms

    return [
        CPGDocRef(
            cpg_name=name,
            document_id=v["ids"][0],
            document_ids=v["ids"],
            title=v["title"],
            match_type=v["match_type"],
            score=1.0,
            matched_scope=v["matched"],
        )
        for name, v in groups.items()
    ]


async def _range_match(conn, icd_code: str) -> list[CPGDocRef]:
    rows = await conn.fetch(
        """
        SELECT id::text, title, icd11_scope, metadata->>'cpg_name' AS cpg_name
        FROM documents WHERE scope_verified = TRUE
        """
    )

    groups: dict[str, dict] = defaultdict(
        lambda: {"ids": [], "title": "", "entry": ""}
    )
    for row in rows:
        matched, entry = _icd11_range_match(icd_code, row["icd11_scope"])
        if not matched:
            continue
        name: str = row["cpg_name"] or row["id"]
        g = groups[name]
        g["ids"].append(row["id"])
        if not g["title"]:
            g["title"] = row["title"]
        if not g["entry"]:
            g["entry"] = entry

    return [
        CPGDocRef(
            cpg_name=name,
            document_id=v["ids"][0],
            document_ids=v["ids"],
            title=v["title"],
            match_type="exact",
            score=1.0,
            matched_scope=v["entry"],
        )
        for name, v in groups.items()
    ]


async def _semantic_fallback(
    conn,
    icd_code: str,
    top_k: int,
    threshold: float,
) -> list[CPGDocRef]:
    row = await conn.fetchrow(
        "SELECT title, description FROM icd11_codes WHERE code = $1", icd_code
    )
    if not row:
        query_text = icd_code
    else:
        query_text = row["title"] or icd_code
        if row["description"]:
            query_text += ". " + row["description"]

    query_embedding = await generate_embedding(query_text)

    # Scope the vector search to verified documents
    verified = await conn.fetch(
        """
        SELECT id::text, title, metadata->>'cpg_name' AS cpg_name
        FROM documents WHERE scope_verified = TRUE
        """
    )
    id_list = [r["id"] for r in verified]
    # Build lookup: doc_id -> (cpg_name, title)
    doc_meta: dict[str, tuple[str, str]] = {
        r["id"]: (r["cpg_name"] or r["id"], r["title"] or "")
        for r in verified
    }

    chunk_results = await vector_search(
        embedding=query_embedding,
        limit=top_k * 5,
        document_id_filter=id_list,
    )

    # Group by cpg_name: best chunk score per CPG
    cpg_best: dict[str, dict] = {}
    for c in chunk_results:
        doc_id = str(c["document_id"])
        score = c["similarity"]
        cpg_name, doc_title = doc_meta.get(doc_id, (doc_id, ""))
        if cpg_name not in cpg_best or score > cpg_best[cpg_name]["score"]:
            cpg_best[cpg_name] = {
                "score": score,
                "title": doc_title or c["document_title"],
                "representative_id": doc_id,
            }

    # Collect all doc IDs per CPG (from the verified list, not just chunk hits)
    cpg_all_ids: dict[str, list[str]] = defaultdict(list)
    for doc_id, (cpg_name, _) in doc_meta.items():
        cpg_all_ids[cpg_name].append(doc_id)

    results = [
        CPGDocRef(
            cpg_name=cpg_name,
            document_id=v["representative_id"],
            document_ids=cpg_all_ids.get(cpg_name, [v["representative_id"]]),
            title=v["title"],
            match_type="semantic",
            score=v["score"],
            matched_scope=f"semantic:{v['score']:.2f}",
        )
        for cpg_name, v in sorted(cpg_best.items(), key=lambda x: -x[1]["score"])
        if v["score"] >= threshold
    ]
    return results[:top_k]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def route_icd_to_cpgs(
    icd_code: str,
    top_k: int = 3,
    semantic_threshold: float = 0.60,
) -> list[CPGDocRef]:
    """
    Map an ICD-11 code to up to top_k CPGs (each CPGDocRef = one CPG).

    Structural match (exact → prefix → range) is tried first;
    semantic fallback fires only when structural returns nothing.
    top_k refers to the number of distinct CPGs returned.
    """
    async with db_pool.acquire() as conn:
        results = await _structural_match(conn, icd_code)

        if not results:
            results = await _range_match(conn, icd_code)

        # Deduplicate by cpg_name
        seen_names: set[str] = set()
        deduped: list[CPGDocRef] = []
        for r in results:
            if r.cpg_name not in seen_names:
                seen_names.add(r.cpg_name)
                deduped.append(r)
        results = deduped

        if not results:
            results = await _semantic_fallback(conn, icd_code, top_k, semantic_threshold)

    return results[:top_k]


if __name__ == "__main__":
    import asyncio

    async def _smoke():
        refs = await route_icd_to_cpgs("BC81.3")
        for r in refs:
            print(r)

    asyncio.run(_smoke())
