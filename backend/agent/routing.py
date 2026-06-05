"""
ICD-11 to CPG routing layer.

Phase 1 — ICD structural routing (code-to-code, no text/embedding):
  1. exact                    — predicted code directly in icd11_scope
  2. sibling                  — same-parent siblings incl. .Y / .Z variants
  3. ancestor_d1              — one-decimal-digit parent (e.g. BA41 from BA41.0)
  4. ancestor_d1_sibling      — peer categories of that parent
  5. ancestor_d1_sibling_child— children of those peer categories
  6. ancestor_d2              — no-decimal block ancestor (e.g. BA00 from BA00.0)

  Example depth walk for grandchild code 5B80.00:
    exact → siblings of 5B80.00 → ancestor_d1 (5B80.0) → siblings of 5B80.0
    → children of those siblings → ancestor_d2 (5B80, the no-decimal block)

Phase 2 — text-form fallbacks (only after all 6 ICD levels exhaust):
  7. procedure_scope          — tag overlap with caller-supplied procedure context
                                (catches procedure-only CPGs with no icd11_scope)
  8. semantic_scope           — cosine(icd_embedding, scope_embedding) ≥ threshold
                                (catches cross-chapter conditions D1 misses)
  9. out_of_scope             — no CPG matched

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
# D2 semantic-fallback floor. CURRENT calibration (2026-05-25, after 7 clinician-
# edited CPG scopes were re-embedded against the 30-CPG corpus): min in-scope
# positive = 0.367 (CVD-Women best-code BA40.1), max unrelated orphan = 0.265
# (UTI GC08 -> IE-prophylaxis). 0.32 sits in the (0.265, 0.367) gap with ~0.05
# headroom each side. Probe: scripts/calibrate_semantic_scope_threshold.py.
# Titan-v1 cosine runs compressed — these absolute numbers are lower than they
# would be for normalised embeddings.
# History: 0.65 (initial spec draft, never gated traffic) -> 0.40 (2026-05-23,
# full-corpus calibration: thyroid 0.417 > valve 0.364) -> 0.32 (this calibration,
# after Heart-Pregnancy/Cancer-Pain/Colorectal/Stable-CAD/T2DM/T1DM/Growth-Hormone
# scope edits). See tasks/Next-Step/Last Step Improvement/DDx Gap/cpg_scope_review.md.
SEMANTIC_SCOPE_THRESHOLD = 0.32  # minimum cosine similarity for D2 semantic fallback

# Scope-confidence floor for the DISTANT hierarchy-walk tiers (ancestor_d1_sibling,
# ancestor_d1_sibling_child, ancestor_d2). A code that only reaches a CPG through
# these structural walks — never via its own code, a sibling, or its direct parent
# — is a weak match. Require it to clear the same scope-embedding confidence floor
# the semantic tier already uses; otherwise treat the tier as "no match" and keep
# walking (ultimately out_of_scope). Without this, an out-of-scope code is pulled
# into a distant CPG at near-zero relevance — e.g. migraine-without-aura (8A80.0)
# routed to Ischaemic-Stroke at cosine ~0.17 (TESTING_STRATEGY ADV-04). Direct
# tiers (exact / sibling / ancestor_d1) are NEVER floored: they are genuine scope
# hits. Calibration note: no routing_gold case routes via these distant tiers, so
# this gate changes only spurious far-walk matches.
SCOPE_FALLBACK_CONFIDENCE_FLOOR = SEMANTIC_SCOPE_THRESHOLD


RouteMethod = Literal[
    "exact",
    "sibling",
    "ancestor_d1",
    "ancestor_d1_sibling",
    "ancestor_d1_sibling_child",
    "ancestor_d2",
    "procedure_scope",
    "semantic_scope",
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


async def _procedure_scope_match(
    conn,
    procedure_tags: list[str],
) -> list[CPGDocRef]:
    """
    Return CPGs whose procedure_scope overlaps with the supplied tags.
    Uses Postgres array overlap (&&) so a single shared tag is enough.
    Only considers scope_verified CPGs.
    """
    if not procedure_tags:
        return []
    rows = await conn.fetch(
        """
        SELECT id::text, title, metadata->>'cpg_name' AS cpg_name
        FROM documents
        WHERE scope_verified = TRUE
          AND procedure_scope && $1::text[]
        """,
        procedure_tags,
    )
    return _group_document_rows(
        rows,
        match_type="procedure_scope",
        matched_scope="procedure:" + ",".join(procedure_tags[:3]),
    )


async def _semantic_scope_match(
    conn,
    code: str,
) -> list[CPGDocRef]:
    """
    Cosine similarity between icd11_codes.embedding and documents.scope_embedding.
    Returns the single best CPG if similarity >= SEMANTIC_SCOPE_THRESHOLD.
    Uses pgvector <=> operator (cosine distance = 1 - similarity).
    """
    # The scope_embedding ivfflat index (lists=16) at the default probes=1 scans
    # only ~1/16 of CPG rows and can miss the best semantic match — widen probes for
    # near-exact recall (only 30 CPGs, so cost is negligible).
    await conn.execute("SET ivfflat.probes = 100")

    # Compare entirely in SQL via a join — never round-trip the embedding through
    # Python. asyncpg returns a pgvector column as a *string* ("[0.1,0.2,...]"),
    # not a list, so re-serializing it with ",".join(map(str, ...)) corrupts it
    # into "[[,-,0,...]" and the cast to ::vector fails. Joining icd11_codes to
    # documents keeps the vector server-side and sidesteps that entirely.
    rows = await conn.fetch(
        """
        WITH icd AS (
            SELECT embedding FROM icd11_codes WHERE code = $1
        )
        SELECT DISTINCT ON (d.metadata->>'cpg_name')
               d.id::text, d.title,
               d.metadata->>'cpg_name' AS cpg_name,
               1 - (d.scope_embedding <=> icd.embedding) AS similarity
        FROM documents d, icd
        WHERE d.scope_embedding IS NOT NULL
          AND d.scope_verified = TRUE
          AND icd.embedding IS NOT NULL
        ORDER BY d.metadata->>'cpg_name', d.scope_embedding <=> icd.embedding
        """,
        code,
    )
    if not rows:
        return []

    # pick the single best-scoring CPG
    best = max(rows, key=lambda r: float(r["similarity"]))
    if float(best["similarity"]) < SEMANTIC_SCOPE_THRESHOLD:
        return []

    return _group_document_rows(
        [best],
        match_type="semantic_scope",
        matched_scope=f"semantic:{float(best['similarity']):.3f}",
        default_score=float(best["similarity"]),
    )


async def _score_refs_by_scope_embedding(
    conn,
    code: str,
    refs: list[CPGDocRef],
) -> list[CPGDocRef]:
    """
    Re-score candidate CPGs by cosine(ICD embedding, CPG scope embedding).
    The scope embedding is built from scope_rationale, icd11_scope, and
    procedure_scope, so direct disease/procedure CPGs should rank above broad
    catch-all CPGs when both have an exact ICD scope hit.
    """
    if not refs:
        return refs

    cpg_names = [ref.cpg_name for ref in refs]
    try:
        await conn.execute("SET ivfflat.probes = 100")
        rows = await conn.fetch(
            """
            WITH icd AS (
                SELECT embedding FROM icd11_codes WHERE code = $1
            )
            SELECT d.metadata->>'cpg_name' AS cpg_name,
                   MAX(1 - (d.scope_embedding <=> icd.embedding)) AS similarity
            FROM documents d, icd
            WHERE d.scope_verified = TRUE
              AND d.scope_embedding IS NOT NULL
              AND icd.embedding IS NOT NULL
              AND d.metadata->>'cpg_name' = ANY($2::text[])
            GROUP BY d.metadata->>'cpg_name'
            """,
            code,
            cpg_names,
        )
    except Exception as exc:
        logger.debug("scope-embedding candidate scoring skipped for %s: %s", code, exc)
        return refs

    scores = {}
    for row in rows:
        try:
            cpg_name = row["cpg_name"]
            similarity = row["similarity"]
        except (KeyError, TypeError):
            continue
        if cpg_name is not None and similarity is not None:
            scores[cpg_name] = float(similarity)
    for ref in refs:
        if ref.cpg_name in scores:
            ref.score = scores[ref.cpg_name]
            if ref.matched_scope and not ref.matched_scope.startswith("semantic:"):
                ref.matched_scope = f"{ref.matched_scope}; semantic:{ref.score:.3f}"
    return refs


def _passing_fallback_refs(refs: list[CPGDocRef]) -> list[CPGDocRef]:
    """Keep only distant-walk refs whose scope-embedding score clears the floor.

    Used by the ancestor_d1_sibling / ancestor_d1_sibling_child / ancestor_d2
    tiers. Returns [] when every candidate is below SCOPE_FALLBACK_CONFIDENCE_FLOOR
    so the caller falls through to the next (lower-confidence) tier rather than
    routing a spurious far-walk match. If scope-embedding scoring was skipped
    (score left at its 1.0 default), the ref passes — fail-open, never fail-loud.
    """
    return [r for r in refs if (r.score or 0.0) >= SCOPE_FALLBACK_CONFIDENCE_FLOOR]


async def find_cpgs_for_code(
    code: str,
    conn,
    max_depth: int = ANCESTOR_MAX_DEPTH,
    procedure_tags: list[str] | None = None,
) -> tuple[list[CPGDocRef], str]:
    """
    Find CPGs for a predicted ICD-11 code.

    Returns (matched_documents, route_method). Lookup order:
    1. exact               — code or range directly in icd11_scope
    2. sibling             — same-parent codes incl. .Y / .Z variants
    3. ancestor_d1         — direct parent
    4. ancestor_d1_sibling — peer categories of the parent
    5. ancestor_d1_sibling_child — children of those peer categories
    6. ancestor_d2         — grandparent block
    7. procedure_scope     — tag overlap with caller-supplied procedure context
    8. semantic_scope      — cosine(icd_embedding, scope_embedding) >= threshold
    9. out_of_scope
    """
    async def _with_procedure_refs(refs: list[CPGDocRef], route_method: str) -> tuple[list[CPGDocRef], str]:
        if not procedure_tags:
            return refs, route_method
        procedure_refs = await _procedure_scope_match(conn, procedure_tags)
        if not procedure_refs:
            return refs, route_method
        logger.debug(
            "procedure_scope merged: code=%s method=%s tags=%s cpgs=%d",
            code,
            route_method,
            procedure_tags,
            len(procedure_refs),
        )
        seen = {ref.cpg_name for ref in refs}
        merged = refs[:]
        for ref in procedure_refs:
            if ref.cpg_name not in seen:
                seen.add(ref.cpg_name)
                merged.append(ref)
        return await _score_refs_by_scope_embedding(conn, code, merged), route_method

    # 1. Exact
    exact = await _scope_code_match(conn, code, match_type="exact")
    if exact:
        return await _with_procedure_refs(
            await _score_refs_by_scope_embedding(conn, code, exact),
            "exact",
        )

    range_refs = await _range_match(conn, code)
    if range_refs:
        return await _with_procedure_refs(
            await _score_refs_by_scope_embedding(conn, code, range_refs),
            "exact",
        )

    # 2. Sibling (same parent, incl. .Y / .Z)
    siblings = await fetch_icd_siblings(conn, code)
    for sibling_code in siblings:
        refs = await _scope_code_match(
            conn, sibling_code, match_type="sibling", matched_scope=sibling_code,
        )
        if refs:
            return await _with_procedure_refs(
                await _score_refs_by_scope_embedding(conn, code, refs),
                "sibling",
            )

    # 3. ancestor_d1 — direct parent only
    ancestors = await fetch_icd_ancestors(conn, code, max_depth=max_depth)
    for ancestor in ancestors:
        depth = int(ancestor["depth"])
        if depth == 1:
            refs = await _scope_code_match(
                conn, ancestor["code"], match_type="ancestor_d1", matched_scope=ancestor["code"],
            )
            if refs:
                return await _with_procedure_refs(
                    await _score_refs_by_scope_embedding(conn, code, refs),
                    "ancestor_d1",
                )

    # 4. ancestor_d1_sibling — peer categories of the direct parent
    #    Distant walk: gate on the scope-confidence floor (see
    #    SCOPE_FALLBACK_CONFIDENCE_FLOOR). A below-floor sibling match is skipped
    #    so the walk falls through rather than routing a spurious far match.
    ancestor_siblings = await fetch_icd_ancestor_siblings(conn, code)
    for anc_sib_code in ancestor_siblings:
        refs = await _scope_code_match(
            conn, anc_sib_code, match_type="ancestor_d1_sibling", matched_scope=anc_sib_code,
        )
        if refs:
            scored = _passing_fallback_refs(
                await _score_refs_by_scope_embedding(conn, code, refs)
            )
            if scored:
                return await _with_procedure_refs(scored, "ancestor_d1_sibling")

    # 5. ancestor_d1_sibling_child — children of those peer categories
    ancestor_sibling_children = await fetch_icd_ancestor_sibling_children(conn, code)
    for child_code in ancestor_sibling_children:
        refs = await _scope_code_match(
            conn, child_code, match_type="ancestor_d1_sibling_child", matched_scope=child_code,
        )
        if refs:
            scored = _passing_fallback_refs(
                await _score_refs_by_scope_embedding(conn, code, refs)
            )
            if scored:
                return await _with_procedure_refs(scored, "ancestor_d1_sibling_child")

    # 6. ancestor_d2 — grandparent block
    for ancestor in ancestors:
        depth = int(ancestor["depth"])
        if depth == 2:
            refs = await _scope_code_match(
                conn, ancestor["code"], match_type="ancestor_d2", matched_scope=ancestor["code"],
            )
            if refs:
                scored = _passing_fallback_refs(
                    await _score_refs_by_scope_embedding(conn, code, refs)
                )
                if scored:
                    return await _with_procedure_refs(scored, "ancestor_d2")

    # 7. procedure_scope — tag overlap (catches procedure-only CPGs with no icd11_scope)
    if procedure_tags:
        refs = await _procedure_scope_match(conn, procedure_tags)
        if refs:
            logger.debug("procedure_scope match: code=%s tags=%s cpgs=%d", code, procedure_tags, len(refs))
            return await _score_refs_by_scope_embedding(conn, code, refs), "procedure_scope"

    # 8. semantic_scope — cosine fallback via scope_embedding (D2)
    refs = await _semantic_scope_match(conn, code)
    if refs:
        logger.debug("semantic_scope match: code=%s score=%s", code, refs[0].matched_scope)
        return refs, "semantic_scope"

    return [], "out_of_scope"


async def route_icd_to_cpgs(
    icd_code: str,
    top_k: int = ROUTE_TOP_K,
    procedure_tags: list[str] | None = None,
) -> list[CPGDocRef]:
    """
    Map an ICD-11 code to up to top_k CPGs.

    Tries exact → sibling → ancestor_d1 → ancestor_d1_sibling →
    ancestor_d1_sibling_child → ancestor_d2 → procedure_scope → semantic_scope.
    Returns empty list if none match (out_of_scope).

    procedure_tags: snake_case tags extracted from the clinical context
    (e.g. ["pre_op_assessment", "anaesthetic_planning"]) used to route
    procedure-only CPGs that have no icd11_scope.
    """
    async with db_pool.acquire() as conn:
        results, _ = await find_cpgs_for_code(
            icd_code,
            conn,
            max_depth=ANCESTOR_MAX_DEPTH,
            procedure_tags=procedure_tags,
        )

        seen_names: set[str] = set()
        deduped: list[CPGDocRef] = []
        for result in results:
            if result.cpg_name not in seen_names:
                seen_names.add(result.cpg_name)
                deduped.append(result)
        deduped.sort(key=lambda ref: (ref.score, ref.match_type == "exact", ref.cpg_name), reverse=True)

    return deduped[:top_k]


if __name__ == "__main__":
    import asyncio

    async def _smoke():
        refs = await route_icd_to_cpgs("BC81.3")
        for ref in refs:
            print(ref)

    asyncio.run(_smoke())
