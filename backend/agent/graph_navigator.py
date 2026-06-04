"""
Graph Navigator — pre-Stage-5 KG enrichment of preferred-agent guidance.

Path A (string-evidence) implementation of Agent 2 from
`tasks/Next-Step/Last Step Improvement/Agent_Architecture.md`.

Complement (not replacement) for `clinical_graph_lookup`:
- `clinical_graph_lookup` walks negative edges (INTERACTS_WITH,
  CONTRAINDICATED_WITH, REQUIRES_MONITORING, REQUIRES_DOSE_ADJUSTMENT,
  CROSS_REACTS_WITH) — the "what to AVOID" arm.
- This module walks positive edges (FIRST_LINE_FOR, SECOND_LINE_FOR,
  RECOMMENDED_FOR) keyed by the patient's DDx and comorbidities — the
  "what to PREFER" arm.

Output is a list of `ClinicalFlag` objects (reusing the existing dataclass so
they merge into the same Stage 5 evidence block, and the existing
`format_flags_for_prompt` renders them with the same source-cited shape).

Fail-open: any KG error returns [] and logs a warning — must never block
synthesis.
"""

from __future__ import annotations

import logging
import re
from typing import List, Set

from .graph_clinical import (
    ClinicalFlag,
    _get_neo4j_session,
    _norm_list,
)
from .models import PatientCase
from .clinical_stages import DDxResult
from .db_utils import db_pool

logger = logging.getLogger(__name__)


# Edges in the KG that express positive guideline guidance.
# Severity is intentionally left blank — these are "PREFER" rules, not safety
# concerns, and we don't want them to flip safe_to_proceed.
_PREFER_EDGES = ("FIRST_LINE_FOR", "SECOND_LINE_FOR", "RECOMMENDED_FOR")

# Detects a comparison-table row that the KG entity extractor wrongly turned
# into a relationship — e.g. `"Asthma | + | - | + | + | + | +"`. We require
# 3+ pipe separators with single-char (or 1–3 char) cells to avoid false
# positives on legitimate evidence sentences that happen to contain a pipe.
_TABLE_ROW_NOISE = re.compile(r"(?:\|\s*[+\-]{1,3}\$?\s*){3,}")


def _is_table_row_noise(evidence: str) -> bool:
    """Return True if `evidence` looks like a parser-error table-row extraction
    rather than prose. Used to drop PREFER edges that were derived from an
    extractor misreading a comparison table."""
    if not evidence:
        return False
    return bool(_TABLE_ROW_NOISE.search(evidence))


async def _fetch_routed_chunk_ids(document_ids: List[str]) -> Set[str]:
    """Return the set of chunk_ids belonging to the routed CPG document_ids.

    Used to scope PREFER rules to chunks from the active CPG context, so a
    HTN rule sourced from an AF CPG's secondary-prevention section is dropped
    when the active CPGs don't include that AF CPG.
    """
    if not document_ids:
        return set()
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text AS chunk_id FROM chunks WHERE document_id::text = ANY($1)",
                [str(d) for d in document_ids],
            )
        return {r["chunk_id"] for r in rows}
    except Exception as exc:
        logger.warning("_fetch_routed_chunk_ids failed (non-fatal, no scope filter applied): %s", exc)
        return set()


async def _query_preferred_agents(
    session,
    condition_names: List[str],
) -> List[ClinicalFlag]:
    """For each condition (DDx title + comorbidities), return drugs the KG
    recommends, with the CPG evidence snippet and chunk reference."""
    if not condition_names:
        return []

    cypher = """
    MATCH (d:Drug)-[r:FIRST_LINE_FOR|SECOND_LINE_FOR|RECOMMENDED_FOR]->(c)
    WHERE c.name_normalised IN $conditions
    RETURN d.name AS drug, c.name AS cond, type(r) AS rel,
           coalesce(r.evidence, '') AS evidence,
           coalesce(r.evidence_list, []) AS evidence_list,
           coalesce(r.source_document, '') AS source,
           r.cpg_chunk_id AS chunk_id,
           coalesce(r.cpg_chunk_ids, []) AS chunk_ids,
           r.trigger AS trigger
    """
    result = await session.run(cypher, conditions=_norm_list(condition_names))
    flags: List[ClinicalFlag] = []
    async for record in result:
        flags.append(ClinicalFlag(
            flag_type="PREFER",
            subject=record["drug"],
            object=record["cond"],
            relation=record["rel"],
            severity=None,  # informational — never a safety gate
            trigger=record["trigger"],
            evidence=record["evidence"],
            evidence_list=list(record["evidence_list"]),
            source_document=record["source"],
            cpg_chunk_id=record["chunk_id"],
            cpg_chunk_ids=list(record["chunk_ids"]),
        ))
    return flags


def _ddx_condition_names(ddx: List[DDxResult], limit: int = 3) -> List[str]:
    """Pull human-readable condition names from the top DDx for KG lookup.
    Top-N only — long DDx tails dilute the prefer-edge signal."""
    names = []
    for d in (ddx or [])[:limit]:
        title = getattr(d, "title", None)
        if title:
            names.append(title)
    return names


async def get_graph_constraints(
    case: PatientCase,
    ddx: List[DDxResult],
    cpgs: list = None,
) -> List[ClinicalFlag]:
    """Path-A Graph Navigator: pull preferred-agent rules from Neo4j keyed by
    the patient's top DDx titles + comorbidities.

    Returns ClinicalFlags with flag_type="PREFER" — merged alongside the
    negative-edge flags from `clinical_graph_lookup` into the Stage 5 prompt
    so the synthesis LLM sees both "avoid X because..." and "prefer Y because..."
    in one source-cited block.

    v1.1 filters applied before returning:
    - **Scope filter**: when `cpgs` is provided, drop edges whose `cpg_chunk_id`
      is not in the chunk set belonging to the routed CPG document_ids. Kills
      cross-CPG drift (e.g. an HTN rule sourced from the AF CPG's secondary-
      prevention section when AF isn't a routed CPG).
    - **Table-row noise filter**: drop edges whose evidence text matches the
      comparison-table-row shape — these are upstream KG-extractor errors
      where a table cell was extracted as a relationship.

    Fail-open: returns [] on any Neo4j error. Filter failures degrade to
    "no filtering" rather than blocking results.
    """
    conditions = _ddx_condition_names(ddx)
    conditions.extend(case.comorbidities or [])
    if not conditions:
        return []

    # Build the scope chunk-id set up front so we can short-circuit if PG fails
    routed_chunk_ids: Set[str] = set()
    if cpgs:
        doc_ids: List[str] = []
        for c in cpgs:
            doc_ids.extend(getattr(c, "document_ids", None) or [])
        routed_chunk_ids = await _fetch_routed_chunk_ids(doc_ids)

    try:
        session_ctx = await _get_neo4j_session()
        async with session_ctx as session:
            flags = await _query_preferred_agents(session, conditions)

        raw_count = len(flags)
        if routed_chunk_ids:
            flags = [
                f for f in flags
                if (f.cpg_chunk_id in routed_chunk_ids)
                or any(cid in routed_chunk_ids for cid in (f.cpg_chunk_ids or []))
            ]
        scoped_count = len(flags)
        flags = [f for f in flags if not _is_table_row_noise(f.evidence)]
        denoised_count = len(flags)

        logger.info(
            "graph_navigator: %d → %d (scope) → %d (denoise) preferred-agent rules from %d conditions",
            raw_count, scoped_count, denoised_count, len(conditions),
        )
        return flags
    except Exception as exc:
        logger.warning("graph_navigator failed (non-fatal): %s", exc)
        return []
