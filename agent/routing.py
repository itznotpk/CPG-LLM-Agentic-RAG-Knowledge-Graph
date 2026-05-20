"""
ICD-11 to CPG routing layer.

Maps a predicted ICD-11 code to CPG document groups via:
1. Exact document icd11_scope match.
2. Sibling — same-parent codes incl. .Y and .Z variants.
3. ancestor_d1 — direct parent category.
4. ancestor_d1_sibling — peer categories of the parent.
5. ancestor_d1_sibling_child — children of those peer categories.
6. ancestor_d2 — grandparent block.
7. out_of_scope — no CPG matched.

Each CPGDocRef represents one CPG, not one section row. All section UUIDs for
that CPG are collected in document_ids so downstream vector searches can filter
against the full CPG.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

from .db_utils import (
    db_pool,
    fetch_icd_ancestors,
    fetch_icd_siblings,
    fetch_icd_ancestor_siblings,
    fetch_icd_ancestor_sibling_children,
)

logger = logging.getLogger(__name__)

ANCESTOR_MAX_DEPTH = 2
ROUTE_TOP_K = 3

RouteMethod = Literal[
    "exact",
    "sibling",
    "ancestor_d1",
    "ancestor_d1_sibling",
    "ancestor_d1_sibling_child",
    "ancestor_d2",
]


class CPGDocRef(BaseModel):
    cpg_name: str
    document_id: str
    document_ids: list[str]
    title: str
    match_type: RouteMethod
    score: float
    matched_scope: str


_RANGE_PATTERN = re.compile(r"^[A-Z0-9]{2,4}-[A-Z0-9]{2,4}$")


def _icd11_range_match(code: str, scope: list[str]) -> tuple[bool, str]:
    """Return (matched, entry) if code falls in any range entry of scope."""
    for entry in scope or []:
        if _RANGE_PATTERN.match(entry):
            low, high = entry.split("-", 1)
            if low <= code <= high:
                return True, entry
    return False, ""


def _group_document_rows(
    rows,
    match_type: RouteMethod,
    matched_scope: str,
    default_score: float = 1.0,
) -> list[CPGDocRef]:
    groups: dict[str, dict] = defaultdict(
        lambda: {"ids": [], "title": "", "score": default_score}
    )

    for row in rows:
        cpg_name = row["cpg_name"] or row["id"]
        group = groups[cpg_name]
        group["ids"].append(row["id"])
        if not group["title"]:
            group["title"] = row["title"] or cpg_name
        if "similarity" in row.keys():
            group["score"] = max(group["score"], float(row["similarity"]))

    return [
        CPGDocRef(
            cpg_name=cpg_name,
            document_id=data["ids"][0],
            document_ids=data["ids"],
            title=data["title"],
            match_type=match_type,
            score=data["score"],
            matched_scope=matched_scope,
        )
        for cpg_name, data in groups.items()
    ]


async def _scope_code_match(
    conn,
    scope_code: str,
    match_type: RouteMethod,
    matched_scope: str | None = None,
) -> list[CPGDocRef]:
    rows = await conn.fetch(
        """
        SELECT id::text, title, icd11_scope, metadata->>'cpg_name' AS cpg_name
        FROM documents
        WHERE scope_verified = TRUE
          AND $1 = ANY(icd11_scope)
        """,
        scope_code,
    )
    return _group_document_rows(
        rows,
        match_type=match_type,
        matched_scope=matched_scope or scope_code,
    )


async def _range_match(conn, icd_code: str) -> list[CPGDocRef]:
    rows = await conn.fetch(
        """
        SELECT id::text, title, icd11_scope, metadata->>'cpg_name' AS cpg_name
        FROM documents
        WHERE scope_verified = TRUE
        """
    )

    matched_rows = []
    matched_entry = ""
    for row in rows:
        matched, entry = _icd11_range_match(icd_code, row["icd11_scope"] or [])
        if matched:
            matched_rows.append(row)
            matched_entry = matched_entry or entry

    return _group_document_rows(
        matched_rows,
        match_type="exact",
        matched_scope=matched_entry,
    )


async def find_cpgs_for_code(
    code: str,
    conn,
    max_depth: int = ANCESTOR_MAX_DEPTH,
) -> tuple[list[CPGDocRef], str]:
    """
    Find CPGs for a predicted ICD-11 code.

    Returns (matched_documents, route_method). Lookup order:
    1. exact         — code or range directly in icd11_scope
    2. sibling       — same-parent codes incl. .Y / .Z variants
    3. ancestor_d1   — direct parent
    4. ancestor_d1_sibling       — peer categories of the parent
    5. ancestor_d1_sibling_child — children of those peer categories
    6. ancestor_d2   — grandparent block
    7. none          — D2 semantic fallback takes over
    """
    # 1. Exact
    exact = await _scope_code_match(conn, code, match_type="exact")
    if exact:
        return exact, "exact"

    range_refs = await _range_match(conn, code)
    if range_refs:
        return range_refs, "exact"

    # 2. Sibling (same parent, incl. .Y / .Z)
    siblings = await fetch_icd_siblings(conn, code)
    for sibling_code in siblings:
        refs = await _scope_code_match(
            conn, sibling_code, match_type="sibling", matched_scope=sibling_code,
        )
        if refs:
            return refs, "sibling"

    # 3. ancestor_d1 — direct parent only
    ancestors = await fetch_icd_ancestors(conn, code, max_depth=max_depth)
    for ancestor in ancestors:
        depth = int(ancestor["depth"])
        if depth == 1:
            refs = await _scope_code_match(
                conn, ancestor["code"], match_type="ancestor_d1", matched_scope=ancestor["code"],
            )
            if refs:
                return refs, "ancestor_d1"

    # 4. ancestor_d1_sibling — peer categories of the direct parent
    ancestor_siblings = await fetch_icd_ancestor_siblings(conn, code)
    for anc_sib_code in ancestor_siblings:
        refs = await _scope_code_match(
            conn, anc_sib_code, match_type="ancestor_d1_sibling", matched_scope=anc_sib_code,
        )
        if refs:
            return refs, "ancestor_d1_sibling"

    # 5. ancestor_d1_sibling_child — children of those peer categories
    ancestor_sibling_children = await fetch_icd_ancestor_sibling_children(conn, code)
    for child_code in ancestor_sibling_children:
        refs = await _scope_code_match(
            conn, child_code, match_type="ancestor_d1_sibling_child", matched_scope=child_code,
        )
        if refs:
            return refs, "ancestor_d1_sibling_child"

    # 6. ancestor_d2 — grandparent block
    for ancestor in ancestors:
        depth = int(ancestor["depth"])
        if depth == 2:
            refs = await _scope_code_match(
                conn, ancestor["code"], match_type="ancestor_d2", matched_scope=ancestor["code"],
            )
            if refs:
                return refs, "ancestor_d2"

    return [], "none"


async def route_icd_to_cpgs(
    icd_code: str,
    top_k: int = ROUTE_TOP_K,
) -> list[CPGDocRef]:
    """
    Map an ICD-11 code to up to top_k CPGs.

    Tries exact → sibling → ancestor_d1 → ancestor_d1_sibling →
    ancestor_d1_sibling_child → ancestor_d2 in order.
    Returns empty list if none match (out_of_scope).
    """
    async with db_pool.acquire() as conn:
        results, _ = await find_cpgs_for_code(
            icd_code,
            conn,
            max_depth=ANCESTOR_MAX_DEPTH,
        )

        seen_names: set[str] = set()
        deduped: list[CPGDocRef] = []
        for result in results:
            if result.cpg_name not in seen_names:
                seen_names.add(result.cpg_name)
                deduped.append(result)

    return deduped[:top_k]


if __name__ == "__main__":
    import asyncio

    async def _smoke():
        refs = await route_icd_to_cpgs("BC81.3")
        for ref in refs:
            print(ref)

    asyncio.run(_smoke())
