"""
ICD-11 to CPG routing layer.

Maps a predicted ICD-11 code to CPG document groups via:
1. Exact document icd11_scope match.
2. ICD-11 parent hierarchy fallback up to depth 2.
3. ICD-11 sibling fallback.
4. Semantic fallback against documents.scope_embedding.

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

from .db_utils import db_pool, fetch_icd_ancestors, fetch_icd_siblings
from .tools import generate_embedding

logger = logging.getLogger(__name__)

ANCESTOR_MAX_DEPTH = 2
SEMANTIC_FALLBACK_THRESHOLD = 0.65
SEMANTIC_FALLBACK_TOP_K = 3

RouteMethod = Literal["exact", "ancestor_d1", "ancestor_d2", "sibling", "semantic"]


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
    match_type: Literal["exact", "ancestor_d1", "ancestor_d2", "sibling"],
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

    Returns (matched_documents, route_method), where route_method is one of:
    exact, ancestor_d1, ancestor_d2, sibling, none.
    """
    exact = await _scope_code_match(conn, code, match_type="exact")
    if exact:
        return exact, "exact"

    range_refs = await _range_match(conn, code)
    if range_refs:
        return range_refs, "exact"

    ancestors = await fetch_icd_ancestors(conn, code, max_depth=max_depth)
    for ancestor in ancestors:
        depth = int(ancestor["depth"])
        if depth > max_depth:
            continue
        route_method = "ancestor_d1" if depth == 1 else "ancestor_d2"
        refs = await _scope_code_match(
            conn,
            ancestor["code"],
            match_type=route_method,
            matched_scope=ancestor["code"],
        )
        if refs:
            return refs, route_method

    siblings = await fetch_icd_siblings(conn, code)
    for sibling_code in siblings:
        refs = await _scope_code_match(
            conn,
            sibling_code,
            match_type="sibling",
            matched_scope=sibling_code,
        )
        if refs:
            return refs, "sibling"

    return [], "none"


async def _semantic_fallback(
    conn,
    icd_code: str,
    top_k: int,
    threshold: float,
) -> list[CPGDocRef]:
    row = await conn.fetchrow(
        "SELECT title, description FROM icd11_codes WHERE code = $1",
        icd_code,
    )
    if not row:
        query_text = icd_code
    else:
        query_text = row["title"] or icd_code
        if row["description"]:
            query_text += ". " + row["description"]

    embedding = await generate_embedding(query_text)
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"

    candidate_rows = await conn.fetch(
        """
        SELECT
            id::text,
            title,
            metadata->>'cpg_name' AS cpg_name,
            1 - (scope_embedding <=> $1::vector) AS similarity
        FROM documents
        WHERE scope_verified = TRUE
          AND scope_embedding IS NOT NULL
        ORDER BY scope_embedding <=> $1::vector
        LIMIT $2
        """,
        embedding_str,
        max(top_k * 10, SEMANTIC_FALLBACK_TOP_K),
    )

    best_by_cpg: dict[str, dict] = {}
    for candidate in candidate_rows:
        score = float(candidate["similarity"])
        if score < threshold:
            continue
        cpg_name = candidate["cpg_name"] or candidate["id"]
        if cpg_name not in best_by_cpg or score > float(best_by_cpg[cpg_name]["similarity"]):
            best_by_cpg[cpg_name] = dict(candidate)

    if not best_by_cpg:
        return []

    cpg_names = list(best_by_cpg.keys())
    all_doc_rows = await conn.fetch(
        """
        SELECT id::text, title, metadata->>'cpg_name' AS cpg_name
        FROM documents
        WHERE scope_verified = TRUE
          AND COALESCE(metadata->>'cpg_name', id::text) = ANY($1::text[])
        ORDER BY title, id
        """,
        cpg_names,
    )

    ids_by_cpg: dict[str, list[str]] = defaultdict(list)
    for doc_row in all_doc_rows:
        ids_by_cpg[doc_row["cpg_name"] or doc_row["id"]].append(doc_row["id"])

    refs: list[CPGDocRef] = []
    for cpg_name, candidate in sorted(
        best_by_cpg.items(),
        key=lambda item: -float(item[1]["similarity"]),
    ):
        score = float(candidate["similarity"])
        refs.append(
            CPGDocRef(
                cpg_name=cpg_name,
                document_id=candidate["id"],
                document_ids=ids_by_cpg.get(cpg_name, [candidate["id"]]),
                title=candidate["title"] or cpg_name,
                match_type="semantic",
                score=score,
                matched_scope=f"semantic:{score:.2f}",
            )
        )

    return refs[:top_k]


async def route_icd_to_cpgs(
    icd_code: str,
    top_k: int = SEMANTIC_FALLBACK_TOP_K,
    semantic_threshold: float = SEMANTIC_FALLBACK_THRESHOLD,
) -> list[CPGDocRef]:
    """
    Map an ICD-11 code to up to top_k CPGs.

    Exact/ancestor/sibling routing is tried first. Semantic fallback fires only
    when the curated ICD routes return nothing.
    """
    async with db_pool.acquire() as conn:
        results, route_method = await find_cpgs_for_code(
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
        results = deduped

        if route_method == "none":
            results = await _semantic_fallback(
                conn,
                icd_code,
                top_k=top_k,
                threshold=semantic_threshold,
            )

    return results[:top_k]


if __name__ == "__main__":
    import asyncio

    async def _smoke():
        refs = await route_icd_to_cpgs("BC81.3")
        for ref in refs:
            print(ref)

    asyncio.run(_smoke())
