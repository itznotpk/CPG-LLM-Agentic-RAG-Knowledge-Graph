"""
Clinical Knowledge Graph Lookup — Structured Cypher queries for the clinical pipeline.

This module provides `clinical_graph_lookup()` which runs typed Cypher queries
against Neo4j to surface drug-drug interactions, allergy cross-reactivity,
and comorbidity-related flags.  It bypasses Graphiti's semantic search and
returns structured ClinicalFlag objects with evidence and citations.

Usage from clinical_stages.py:
    from .graph_clinical import clinical_graph_lookup, ClinicalFlag
    flags = await clinical_graph_lookup(
        patient_meds=["warfarin", "digoxin"],
        candidate_drugs=["amiodarone"],
        comorbidities=["heart failure", "renal impairment"],
        allergies=["sulfa"],
    )
"""

import os
import re
import logging
from typing import List, Optional, Literal
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ClinicalFlag:
    """A structured clinical safety flag returned by the KG lookup."""

    flag_type: str  # "INTERACTION", "ALLERGY_CROSS", "DOSE_ADJUSTMENT", "CONTRAINDICATION", "MONITORING"
    subject: str           # e.g., patient drug or condition
    object: str            # e.g., interacting drug / condition
    relation: str          # Neo4j relationship type
    severity: Optional[str] = None  # MAJOR / MODERATE / MINOR / UNSPECIFIED
    evidence: str = ""
    evidence_list: List[str] = field(default_factory=list)  # all supporting evidence across CPGs
    source_document: str = ""
    cpg_chunk_id: Optional[str] = None
    cpg_chunk_ids: List[str] = field(default_factory=list)  # all source chunk UUIDs


# ---------------------------------------------------------------------------
# Name normalisation (symmetric with graph_builder._normalize_entity_name)
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """Normalise a name for Cypher matching against name_normalised.

    Must produce the same canonical form as
    graph_builder._normalize_entity_name(name).lower()
    so that read queries hit the same MERGE key used at write time.

    Steps:
    - strip whitespace
    - remove parenthetical brand names: "sildenafil (Viagra)" -> "sildenafil"
    - remove trailing dose info: "warfarin 5 mg" -> "warfarin"
    - title-case then lowercase (same as write side)
    """
    s = name.strip()
    s = re.sub(r"\s*\([^)]*\)", "", s)        # strip parenthetical
    s = re.sub(r"\s+\d+\s*mg.*$", "", s, flags=re.IGNORECASE)  # strip trailing dose
    s = s.title()  # title-case first, matching _normalize_entity_name
    return s.lower().strip()


def _norm_list(names: List[str]) -> List[str]:
    """Normalise a list of names and deduplicate."""
    seen = set()
    out = []
    for n in names:
        normed = _norm(n)
        if normed and normed not in seen:
            seen.add(normed)
            out.append(normed)
    return out


# ---------------------------------------------------------------------------
# Neo4j session helper
# ---------------------------------------------------------------------------

async def _get_neo4j_session():
    """Get a Neo4j async session using the Graphiti driver (avoids second connection)."""
    try:
        from .graph_utils import graph_client
        if not graph_client._initialized:
            await graph_client.initialize()
        db_name = os.getenv("NEO4J_DATABASE") or None
        return graph_client.graphiti.driver.client.session(database=db_name)
    except Exception:
        # Fallback: create a standalone driver
        from neo4j import AsyncGraphDatabase
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        db = os.getenv("NEO4J_DATABASE") or None
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        return driver.session(database=db)


# ---------------------------------------------------------------------------
# Cypher queries
# ---------------------------------------------------------------------------

async def _query_drug_interactions(
    session,
    patient_meds: List[str],
    candidate_drugs: List[str],
) -> List[ClinicalFlag]:
    """
    Query 1: Drug-drug contraindications / interactions.

    Matches edges between drugs the patient is already on and drugs being
    considered from the CPG evidence.
    """
    if not patient_meds or not candidate_drugs:
        return []

    cypher = """
    MATCH (d1)-[r:CONTRAINDICATED_WITH|INTERACTS_WITH]-(d2)
    WHERE d1.name_normalised IN $meds AND d2.name_normalised IN $candidates
    RETURN d1.name AS subj, d2.name AS obj, type(r) AS rel,
           coalesce(r.evidence, '') AS evidence,
           coalesce(r.evidence_list, []) AS evidence_list,
           coalesce(r.source_document, '') AS source,
           coalesce(r.severity, 'UNSPECIFIED') AS severity,
           r.cpg_chunk_id AS chunk_id,
           coalesce(r.cpg_chunk_ids, []) AS chunk_ids
    """
    result = await session.run(
        cypher,
        meds=_norm_list(patient_meds),
        candidates=_norm_list(candidate_drugs),
    )
    flags = []
    async for record in result:
        flags.append(ClinicalFlag(
            flag_type="INTERACTION",
            subject=record["subj"],
            object=record["obj"],
            relation=record["rel"],
            severity=record["severity"],
            evidence=record["evidence"],
            evidence_list=list(record["evidence_list"]),
            source_document=record["source"],
            cpg_chunk_id=record["chunk_id"],
            cpg_chunk_ids=list(record["chunk_ids"]),
        ))
    return flags


async def _query_comorbidity_flags(
    session,
    candidate_drugs: List[str],
    comorbidities: List[str],
) -> List[ClinicalFlag]:
    """
    Query 2: Comorbidity-related dose adjustments and monitoring.

    Finds drugs that REQUIRE_MONITORING, are CONTRAINDICATED_WITH, or
    have specific dosing for a patient's existing conditions.
    """
    if not candidate_drugs or not comorbidities:
        return []

    cypher = """
    MATCH (d)-[r:REQUIRES_MONITORING|CONTRAINDICATED_WITH|HAS_DOSAGE|REQUIRES_DOSE_ADJUSTMENT]->(c)
    WHERE d.name_normalised IN $candidates AND c.name_normalised IN $comorbidities
    RETURN d.name AS subj, c.name AS obj, type(r) AS rel,
           coalesce(r.evidence, '') AS evidence,
           coalesce(r.evidence_list, []) AS evidence_list,
           coalesce(r.source_document, '') AS source,
           coalesce(r.severity, 'UNSPECIFIED') AS severity,
           r.cpg_chunk_id AS chunk_id,
           coalesce(r.cpg_chunk_ids, []) AS chunk_ids,
           r.trigger AS trigger
    """
    result = await session.run(
        cypher,
        candidates=_norm_list(candidate_drugs),
        comorbidities=_norm_list(comorbidities),
    )
    flags = []
    async for record in result:
        rel = record["rel"]
        flag_type = (
            "MONITORING" if rel == "REQUIRES_MONITORING"
            else "DOSE_ADJUSTMENT" if rel in ("HAS_DOSAGE", "REQUIRES_DOSE_ADJUSTMENT")
            else "CONTRAINDICATION"
        )
        flags.append(ClinicalFlag(
            flag_type=flag_type,
            subject=record["subj"],
            object=record["obj"],
            relation=rel,
            severity=record["severity"],
            evidence=record["evidence"],
            evidence_list=list(record["evidence_list"]),
            source_document=record["source"],
            cpg_chunk_id=record["chunk_id"],
            cpg_chunk_ids=list(record["chunk_ids"]),
        ))
    return flags


async def _query_allergy_cross_reactivity(
    session,
    candidate_drugs: List[str],
    allergies: List[str],
) -> List[ClinicalFlag]:
    """
    Query 3: Allergy cross-reactivity.

    Checks if any candidate drug is CONTRAINDICATED_WITH a known allergy.
    """
    if not candidate_drugs or not allergies:
        return []

    cypher = """
    MATCH (d)-[r:CONTRAINDICATED_WITH|CAUSES|CROSS_REACTS_WITH]-(a)
    WHERE d.name_normalised IN $candidates AND a.name_normalised IN $allergies
    RETURN d.name AS subj, a.name AS obj, type(r) AS rel,
           coalesce(r.evidence, '') AS evidence,
           coalesce(r.evidence_list, []) AS evidence_list,
           coalesce(r.source_document, '') AS source,
           r.cpg_chunk_id AS chunk_id,
           coalesce(r.cpg_chunk_ids, []) AS chunk_ids
    """
    result = await session.run(
        cypher,
        candidates=_norm_list(candidate_drugs),
        allergies=_norm_list(allergies),
    )
    flags = []
    async for record in result:
        flags.append(ClinicalFlag(
            flag_type="ALLERGY_CROSS",
            subject=record["subj"],
            object=record["obj"],
            relation=record["rel"],
            severity="MAJOR",  # allergy cross-reactivity is always safety-critical
            evidence=record["evidence"],
            evidence_list=list(record["evidence_list"]),
            source_document=record["source"],
            cpg_chunk_id=record["chunk_id"],
            cpg_chunk_ids=list(record["chunk_ids"]),
        ))
    return flags


# ---------------------------------------------------------------------------
# Candidate drug extraction from retrieved chunk IDs
# ---------------------------------------------------------------------------

async def extract_candidate_drugs_from_chunks(chunk_ids: List[str]) -> List[str]:
    """
    Given a list of cpg_chunk_ids from Stage 4 retrieval, return the names of
    Drug nodes whose edges were sourced from those chunks.

    This grounds candidate_drugs in the evidence the LLM is about to see,
    so interaction flags only fire for drugs the pipeline is actually considering.
    Returns [] on failure — never crashes the pipeline.
    """
    if not chunk_ids:
        return []

    cypher = """
    MATCH (d:Drug)-[r]->()
    WHERE r.cpg_chunk_id IN $chunk_ids
    RETURN DISTINCT d.name AS name
    """
    try:
        session_ctx = await _get_neo4j_session()
        async with session_ctx as session:
            result = await session.run(cypher, chunk_ids=chunk_ids)
            names = [record["name"] async for record in result]
            logger.debug("extract_candidate_drugs_from_chunks: %d drugs from %d chunks", len(names), len(chunk_ids))
            return names
    except Exception as e:
        logger.warning("extract_candidate_drugs_from_chunks failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def clinical_graph_lookup(
    patient_meds: Optional[List[str]] = None,
    candidate_drugs: Optional[List[str]] = None,
    comorbidities: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
) -> List[ClinicalFlag]:
    """
    Run structured Cypher queries against the KG and return clinical flags.

    This is the primary entry point for the clinical pipeline (Stage 4).
    It runs 3 queries in parallel and returns a deduplicated list of flags.

    Args:
        patient_meds: Drugs the patient is currently taking
        candidate_drugs: Drugs mentioned in retrieved CPG evidence
        comorbidities: Patient's existing conditions
        allergies: Patient's known allergies

    Returns:
        List of ClinicalFlag objects (may be empty — that is normal)
    """
    patient_meds = patient_meds or []
    candidate_drugs = candidate_drugs or []
    comorbidities = comorbidities or []
    allergies = allergies or []

    if not candidate_drugs:
        logger.debug("clinical_graph_lookup: no candidate drugs — skipping")
        return []

    try:
        session_ctx = await _get_neo4j_session()
        async with session_ctx as session:
            all_flags: List[ClinicalFlag] = []

            # Run queries sequentially — Neo4j async sessions do not
            # support concurrent reads on the same connection.  Each query
            # is a simple index-backed Cypher and completes in <10 ms.
            query_funcs = [
                ("drug_interactions", _query_drug_interactions, [session, patient_meds, candidate_drugs]),
                ("comorbidity_flags", _query_comorbidity_flags, [session, candidate_drugs, comorbidities]),
                ("allergy_cross", _query_allergy_cross_reactivity, [session, candidate_drugs, allergies]),
            ]

            for qname, qfunc, qargs in query_funcs:
                try:
                    flags = await qfunc(*qargs)
                    all_flags.extend(flags)
                except Exception as e:
                    logger.warning(f"Graph query {qname} failed: {e}")

            # Deduplicate by (flag_type, subject, object)
            seen = set()
            unique_flags = []
            for f in all_flags:
                key = (f.flag_type, f.subject.lower(), f.object.lower())
                if key not in seen:
                    seen.add(key)
                    unique_flags.append(f)

            logger.info(f"clinical_graph_lookup: {len(unique_flags)} flags found")
            return unique_flags

    except Exception as e:
        logger.error(f"clinical_graph_lookup failed: {e}")
        # Graceful degradation — return empty list, never crash the pipeline
        return []


def format_flags_for_prompt(flags: List[ClinicalFlag]) -> str:
    """
    Format clinical flags into a structured text block for injection into
    the Stage 5 synthesis prompt.

    Returns a string suitable for prepending to the evidence text.
    """
    if not flags:
        return "INTERACTION FLAGS: None detected by knowledge graph.\n"

    lines = ["INTERACTION FLAGS (graph-verified, MUST be addressed in response):"]
    for f in flags:
        severity_str = f"[{f.severity}]" if f.severity else ""
        # Use evidence_list when available (accumulates across CPGs); fall back to single evidence
        all_evidence = f.evidence_list if f.evidence_list else ([f.evidence] if f.evidence else [])
        evidence_block = "\n".join(f'    Evidence {i+1}: "{e[:200]}"' for i, e in enumerate(all_evidence[:3]))
        chunk_refs = ", ".join(f.cpg_chunk_ids[:3]) if f.cpg_chunk_ids else (f.cpg_chunk_id or "")
        lines.append(
            f"- {f.flag_type} {severity_str}: {f.subject} <-> {f.object}\n"
            f"    Relation: {f.relation}\n"
            f"{evidence_block}\n"
            f"    Source: {f.source_document}"
            + (f" (chunks: {chunk_refs})" if chunk_refs else "")
        )
    return "\n".join(lines) + "\n"
