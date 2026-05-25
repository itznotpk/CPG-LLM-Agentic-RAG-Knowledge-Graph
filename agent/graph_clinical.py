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
from typing import Any, Dict, List, Optional, Literal
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
    trigger: Optional[str] = None   # raw condition string e.g. "eGFR<30", "in CKD Stage 4"
    evidence: str = ""
    evidence_list: List[str] = field(default_factory=list)  # all supporting evidence across CPGs
    source_document: str = ""
    cpg_chunk_id: Optional[str] = None
    cpg_chunk_ids: List[str] = field(default_factory=list)  # all source chunk UUIDs
    # Path B typed thresholds (populated when the KG edge has them — backfill or new ingest).
    threshold_param: Optional[str] = None     # e.g. "eGFR"
    threshold_op: Optional[str] = None        # "<", "<=", "=", ">=", ">", "between"
    threshold_value: Optional[float] = None
    threshold_value2: Optional[float] = None  # upper bound when op="between"
    threshold_unit: Optional[str] = None
    threshold_negated: Optional[bool] = None
    threshold_breach: Optional[bool] = None   # set by clinical_graph_lookup when patient_params provided


# ---------------------------------------------------------------------------
# Name normalisation (symmetric with graph_builder._normalize_entity_name)
# ---------------------------------------------------------------------------

from .graph_normalise import normalise_for_lookup as _norm  # symmetric with write side


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
# Threshold evaluation
# ---------------------------------------------------------------------------

# Map KG threshold_param canonical names -> keys to look up in patient_params.
# Patient_params is built from PatientCase.vitals + severity_staging + age.
_PARAM_ALIASES = {
    "egfr": ["egfr", "gfr"],
    "crcl": ["crcl", "creatinine_clearance"],
    "sbp": ["sbp", "systolic_bp", "systolic"],
    "dbp": ["dbp", "diastolic_bp", "diastolic"],
    "hr": ["hr", "heart_rate", "pulse"],
    "k+": ["k+", "potassium", "serum_potassium", "k"],
    "na+": ["na+", "sodium", "na"],
    "inr": ["inr"],
    "tsh": ["tsh"],
    "ldl": ["ldl", "ldl-c", "ldl_c"],
    "platelet": ["platelet", "platelets"],
    "age": ["age"],
    "weight": ["weight", "body_weight", "kg"],
    "hba1c": ["hba1c"],
    "lvef": ["lvef", "ef"],
}


def _resolve_patient_value(param: str, patient_params: Dict[str, Any]) -> Optional[float]:
    """Return the patient's numeric value for a threshold_param, or None if unknown."""
    if not param or not patient_params:
        return None
    p = param.lower().strip()
    # Normalise patient_params keys once.
    pp = {k.lower(): v for k, v in patient_params.items() if v is not None}
    # Direct match.
    if p in pp:
        try:
            return float(pp[p])
        except (TypeError, ValueError):
            return None
    # Alias match.
    for canonical, aliases in _PARAM_ALIASES.items():
        if p == canonical or p in aliases:
            for a in [canonical] + aliases:
                if a in pp:
                    try:
                        return float(pp[a])
                    except (TypeError, ValueError):
                        return None
    return None


def evaluate_threshold(
    param: Optional[str],
    op: Optional[str],
    value: Optional[float],
    value2: Optional[float],
    patient_params: Dict[str, Any],
) -> Optional[bool]:
    """Return True if the patient meets the threshold (breach), False if clearly not,
    or None if the patient's value for `param` is unknown / inputs invalid.

    A "breach" means the rule's condition is satisfied by the patient — i.e. the
    flag is actionable for THIS patient (e.g. drug requires dose-adjust if eGFR<30
    and the patient has eGFR=22 → breach=True; eGFR=80 → breach=False).
    """
    if not param or not op or value is None:
        return None
    pv = _resolve_patient_value(param, patient_params)
    if pv is None:
        return None
    try:
        v = float(value)
        v2 = float(value2) if value2 is not None else None
    except (TypeError, ValueError):
        return None
    if op == "<":
        return pv < v
    if op == "<=":
        return pv <= v
    if op == ">":
        return pv > v
    if op == ">=":
        return pv >= v
    if op == "=":
        return pv == v
    if op == "between" and v2 is not None:
        lo, hi = (v, v2) if v <= v2 else (v2, v)
        return lo <= pv <= hi
    return None


def build_patient_params(case: Any) -> Dict[str, Any]:
    """Flatten PatientCase.vitals + severity_staging + age into a single dict
    consumable by `evaluate_threshold`. Keys are lower-cased; missing fields are
    skipped silently."""
    out: Dict[str, Any] = {}
    if case is None:
        return out
    age = getattr(case, "age", None)
    if age is not None:
        out["age"] = age
    for source in ("vitals", "severity_staging"):
        d = getattr(case, source, None) or {}
        for k, v in d.items():
            if v is None:
                continue
            # severity_staging values may be strings like "30" or "30 mL/min" — try to extract leading number.
            if isinstance(v, str):
                m = re.search(r"-?\d+(?:\.\d+)?", v)
                if not m:
                    continue
                try:
                    v = float(m.group())
                except ValueError:
                    continue
            out[k.lower()] = v
    return out


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
           coalesce(r.cpg_chunk_ids, []) AS chunk_ids,
           r.threshold_param AS t_param, r.threshold_op AS t_op,
           r.threshold_value AS t_value, r.threshold_value2 AS t_value2,
           r.threshold_unit AS t_unit, r.threshold_negated AS t_negated
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
            threshold_param=record["t_param"],
            threshold_op=record["t_op"],
            threshold_value=record["t_value"],
            threshold_value2=record["t_value2"],
            threshold_unit=record["t_unit"],
            threshold_negated=record["t_negated"],
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
           r.trigger AS trigger,
           r.threshold_param AS t_param, r.threshold_op AS t_op,
           r.threshold_value AS t_value, r.threshold_value2 AS t_value2,
           r.threshold_unit AS t_unit, r.threshold_negated AS t_negated
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
            trigger=record["trigger"],
            evidence=record["evidence"],
            evidence_list=list(record["evidence_list"]),
            source_document=record["source"],
            cpg_chunk_id=record["chunk_id"],
            cpg_chunk_ids=list(record["chunk_ids"]),
            threshold_param=record["t_param"],
            threshold_op=record["t_op"],
            threshold_value=record["t_value"],
            threshold_value2=record["t_value2"],
            threshold_unit=record["t_unit"],
            threshold_negated=record["t_negated"],
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

async def match_plan_drugs(interventions: List[str]) -> dict:
    """Map plan intervention strings to KG Drug nodes by substring match on
    `name_normalised`.

    Used by the post-Stage-5 hybrid Safety Critic (upgraded Agent 1) to identify
    which drugs the synthesis LLM actually recommended, so we can run the existing
    KG interaction / contraindication / allergy queries against the *final* plan
    (rather than chunk-derived candidates, which is what the pre-screen does).

    Returns:
        {drug_name_normalised: first_intervention_index} — first intervention
        position that contained the drug. Caller maps that back to the
        `TreatmentPlan.recommendations` index. Returns {} on any failure.

    Notes:
    - We require `size(name_normalised) >= 4` to avoid short-name false positives
      (e.g. a 3-letter drug code substring-matching inside an unrelated word).
    - Match is `CONTAINS` on the lowercased intervention — same canonical form
      `_norm` uses on the write side.
    """
    interventions = [iv for iv in (interventions or []) if iv]
    if not interventions:
        return {}
    cypher = """
    UNWIND range(0, size($iv) - 1) AS i
    MATCH (d:Drug)
    WHERE d.name_normalised IS NOT NULL
      AND size(d.name_normalised) >= 4
      AND toLower($iv[i]) CONTAINS d.name_normalised
    RETURN d.name_normalised AS drug, min(i) AS idx
    """
    try:
        session_ctx = await _get_neo4j_session()
        async with session_ctx as session:
            result = await session.run(cypher, iv=interventions)
            mapping = {rec["drug"]: int(rec["idx"]) async for rec in result}
            logger.debug("match_plan_drugs: %d drugs from %d interventions", len(mapping), len(interventions))
            return mapping
    except Exception as e:
        logger.warning("match_plan_drugs failed: %s", e)
        return {}


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
# Referral lookup (used by Stage 5 post-validator)
# ---------------------------------------------------------------------------

@dataclass
class ReferralHit:
    """One KG-sourced referral recommendation matched to a patient condition."""

    condition: str          # matched Condition node display name
    specialty: str          # Specialty node display name
    urgency: str            # urgent | routine | consider
    trigger: Optional[str]  # condition that warrants referral, if any
    evidence: str           # one supporting CPG sentence
    cpg_source: str         # CPG document title

    def label(self) -> str:
        """Human-readable label for unresolved_questions / UI."""
        parts = [self.specialty]
        if self.urgency == "urgent":
            parts.append("(urgent)")
        elif self.urgency == "consider":
            parts.append("(consider)")
        out = " ".join(parts)
        if self.trigger:
            out = f"{out} — trigger: {self.trigger}"
        return out


async def lookup_referrals(condition_names: List[str]) -> List[ReferralHit]:
    """Look up KG-sourced referral recommendations for a patient's conditions.

    The match is symmetric to `match_plan_drugs`: substring match of the
    Condition node's `name_normalised` against the lowercased condition string.
    Requires `size(name_normalised) >= 4` to avoid 3-letter false positives
    (e.g. "AF" matching "AFI" or "AFP").

    Fail-open: returns [] on Neo4j error so the pipeline never blocks.
    """
    condition_names = [c for c in (condition_names or []) if c]
    if not condition_names:
        return []

    # Expand common clinical abbreviations so substring-match works on
    # "AF (CHA2DS2-VASc 4)" → "atrial fibrillation", "T2DM" → "type 2 diabetes
    # mellitus", etc. The expansions are *added* as extra needles, not
    # replacements, so original strings still match too.
    _ABBREV_MAP = {
        "af": "atrial fibrillation",
        "afib": "atrial fibrillation",
        "a-fib": "atrial fibrillation",
        "t2dm": "type 2 diabetes mellitus",
        "t1dm": "type 1 diabetes mellitus",
        "dm": "diabetes mellitus",
        "hfref": "heart failure with reduced ejection fraction",
        "hfpef": "heart failure with preserved ejection fraction",
        "hfmref": "heart failure with mildly reduced ejection fraction",
        "hf": "heart failure",
        "chf": "congestive heart failure",
        "ckd": "chronic kidney disease",
        "cad": "coronary artery disease",
        "cabg": "coronary artery bypass graft",
        "pci": "percutaneous coronary intervention",
        "acs": "acute coronary syndrome",
        "nstemi": "non-st elevation myocardial infarction",
        "stemi": "st elevation myocardial infarction",
        "mi": "myocardial infarction",
        "htn": "hypertension",
        "copd": "chronic obstructive pulmonary disease",
        "pah": "pulmonary arterial hypertension",
        "tia": "transient ischaemic attack",
        "cvd": "cardiovascular disease",
        "ihd": "ischaemic heart disease",
        "dkd": "diabetic kidney disease",
        "nafld": "non-alcoholic fatty liver disease",
        "gdm": "gestational diabetes mellitus",
        "pad": "peripheral arterial disease",
        "vte": "venous thromboembolism",
        "dvt": "deep vein thrombosis",
        "pe": "pulmonary embolism",
        "ie": "infective endocarditis",
        "ed": "erectile dysfunction",
        "npc": "nasopharyngeal carcinoma",
        "crc": "colorectal carcinoma",
    }
    import re as _re
    expanded: list[str] = []
    for raw in condition_names:
        expanded.append(raw)
        lowered = raw.lower()
        for tok in _re.findall(r"[a-z0-9-]+", lowered):
            full = _ABBREV_MAP.get(tok)
            if full and full not in expanded:
                expanded.append(full)
    condition_names = expanded

    cypher = """
    UNWIND $names AS raw
    WITH toLower(raw) AS needle
    MATCH (c:Condition)-[r:REQUIRES_REFERRAL]->(s:Specialty)
    WHERE c.name_normalised IS NOT NULL
      AND size(c.name_normalised) >= 4
      AND (needle CONTAINS c.name_normalised OR c.name_normalised CONTAINS needle)
    RETURN DISTINCT
        c.name           AS condition,
        s.name           AS specialty,
        r.urgency        AS urgency,
        r.trigger        AS trigger,
        r.evidence       AS evidence,
        r.source_document AS cpg_source
    """
    try:
        session_ctx = await _get_neo4j_session()
        async with session_ctx as session:
            result = await session.run(cypher, names=condition_names)
            hits: List[ReferralHit] = []
            async for rec in result:
                hits.append(ReferralHit(
                    condition=rec["condition"] or "",
                    specialty=rec["specialty"] or "",
                    urgency=(rec["urgency"] or "routine"),
                    trigger=rec["trigger"],
                    evidence=(rec["evidence"] or "")[:300],
                    cpg_source=rec["cpg_source"] or "",
                ))
            logger.info(
                "lookup_referrals: %d referral hit(s) for %d condition name(s)",
                len(hits), len(condition_names),
            )
            return hits
    except Exception as exc:
        logger.warning("lookup_referrals failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def clinical_graph_lookup(
    patient_meds: Optional[List[str]] = None,
    candidate_drugs: Optional[List[str]] = None,
    comorbidities: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    patient_params: Optional[Dict[str, Any]] = None,
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

            # Evaluate typed thresholds against patient parameters, when provided.
            if patient_params:
                breach_count = 0
                for f in unique_flags:
                    f.threshold_breach = evaluate_threshold(
                        f.threshold_param, f.threshold_op,
                        f.threshold_value, f.threshold_value2,
                        patient_params,
                    )
                    if f.threshold_breach is True:
                        breach_count += 1
                if breach_count:
                    logger.info(f"clinical_graph_lookup: {breach_count} threshold breach(es) confirmed against patient params")

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
        trigger_line = f"    Trigger: {f.trigger}\n" if f.trigger else ""
        # Use evidence_list when available (accumulates across CPGs); fall back to single evidence
        all_evidence = f.evidence_list if f.evidence_list else ([f.evidence] if f.evidence else [])
        evidence_block = "\n".join(f'    Evidence {i+1}: "{e[:200]}"' for i, e in enumerate(all_evidence[:3]))
        chunk_refs = ", ".join(f.cpg_chunk_ids[:3]) if f.cpg_chunk_ids else (f.cpg_chunk_id or "")
        lines.append(
            f"- {f.flag_type} {severity_str}: {f.subject} <-> {f.object}\n"
            f"    Relation: {f.relation}\n"
            f"{trigger_line}"
            f"{evidence_block}\n"
            f"    Source: {f.source_document}"
            + (f" (chunks: {chunk_refs})" if chunk_refs else "")
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Referral KG lookup (KG-first replacement for _ALWAYS_REFER_CONDITIONS dict)
# ---------------------------------------------------------------------------

@dataclass
class ReferralRecommendation:
    """A referral recommendation surfaced from the KG for a patient case."""

    condition: str            # display name of matched :Condition node
    specialty: str            # display name of matched :Specialty node
    urgency: str              # urgent | routine | consider
    trigger: Optional[str] = None
    triggers: List[str] = field(default_factory=list)
    evidence: str = ""
    evidence_list: List[str] = field(default_factory=list)
    source_document: str = ""
    icd_hint: Optional[str] = None


async def lookup_referrals(
    condition_names: List[str],
) -> List[ReferralRecommendation]:
    """Resolve referral edges in Neo4j for a patient's conditions.

    Matches symmetrically by substring on `:Condition.name_normalised`. Mirrors
    the `match_plan_drugs` pattern — name-based with length guard to avoid
    false positives on very short tokens.

    Args:
        condition_names: free-text condition strings (DDx titles + comorbidities).

    Returns:
        Deduplicated list of ReferralRecommendation, one per (specialty, condition).
        Returns [] on any failure — caller is expected to fall back to a static
        dict so the pipeline never goes silent.
    """
    names = [n for n in (condition_names or []) if n and n.strip()]
    if not names:
        return []

    _ABBREV_MAP = {
        "af": "atrial fibrillation", "afib": "atrial fibrillation", "a-fib": "atrial fibrillation",
        "t2dm": "type 2 diabetes mellitus", "t1dm": "type 1 diabetes mellitus", "dm": "diabetes mellitus",
        "hfref": "heart failure with reduced ejection fraction",
        "hfpef": "heart failure with preserved ejection fraction",
        "hfmref": "heart failure with mildly reduced ejection fraction",
        "hf": "heart failure", "chf": "congestive heart failure",
        "ckd": "chronic kidney disease", "cad": "coronary artery disease",
        "cabg": "coronary artery bypass graft", "pci": "percutaneous coronary intervention",
        "acs": "acute coronary syndrome",
        "nstemi": "non-st elevation myocardial infarction",
        "stemi": "st elevation myocardial infarction", "mi": "myocardial infarction",
        "htn": "hypertension", "copd": "chronic obstructive pulmonary disease",
        "pah": "pulmonary arterial hypertension", "tia": "transient ischaemic attack",
        "cvd": "cardiovascular disease", "ihd": "ischaemic heart disease",
        "dkd": "diabetic kidney disease", "nafld": "non-alcoholic fatty liver disease",
        "gdm": "gestational diabetes mellitus", "pad": "peripheral arterial disease",
        "vte": "venous thromboembolism", "dvt": "deep vein thrombosis",
        "pe": "pulmonary embolism", "ie": "infective endocarditis",
        "ed": "erectile dysfunction", "npc": "nasopharyngeal carcinoma",
        "crc": "colorectal carcinoma",
    }
    import re as _re
    expanded: list[str] = []
    for raw in names:
        expanded.append(raw)
        lowered = raw.lower()
        for tok in _re.findall(r"[a-z0-9-]+", lowered):
            full = _ABBREV_MAP.get(tok)
            if full and full not in expanded:
                expanded.append(full)
    names = expanded

    cypher = """
    UNWIND $names AS raw
    WITH toLower(raw) AS needle
    MATCH (c:Condition)-[r:REQUIRES_REFERRAL]->(s:Specialty)
    WHERE c.name_normalised IS NOT NULL
      AND size(c.name_normalised) >= 4
      AND (needle CONTAINS c.name_normalised OR c.name_normalised CONTAINS needle)
    RETURN
      c.name AS condition,
      s.name AS specialty,
      coalesce(r.urgency, 'routine') AS urgency,
      r.trigger AS trigger,
      coalesce(r.trigger_list, []) AS triggers,
      coalesce(r.evidence, '') AS evidence,
      coalesce(r.evidence_list, []) AS evidence_list,
      coalesce(r.source_document, '') AS source_document,
      r.icd_hint AS icd_hint
    """
    try:
        session_ctx = await _get_neo4j_session()
        async with session_ctx as session:
            result = await session.run(cypher, names=names)
            records = [dict(r) async for r in result]
    except Exception as exc:
        logger.warning("lookup_referrals failed: %s", exc)
        return []

    # Dedup by (specialty, condition); collapse multi-edge records by upgrading
    # urgency (urgent > routine > consider).
    _urgency_rank = {"urgent": 3, "routine": 2, "consider": 1}
    merged: Dict[tuple, ReferralRecommendation] = {}
    for rec in records:
        key = (rec["specialty"].lower(), rec["condition"].lower())
        new = ReferralRecommendation(
            condition=rec["condition"],
            specialty=rec["specialty"],
            urgency=rec["urgency"],
            trigger=rec.get("trigger"),
            triggers=list(rec.get("triggers") or []),
            evidence=rec.get("evidence") or "",
            evidence_list=list(rec.get("evidence_list") or []),
            source_document=rec.get("source_document") or "",
            icd_hint=rec.get("icd_hint"),
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = new
            continue
        # Keep the higher-urgency record; union evidence + triggers.
        if _urgency_rank.get(new.urgency, 0) > _urgency_rank.get(existing.urgency, 0):
            new.evidence_list = list({*existing.evidence_list, *new.evidence_list})
            new.triggers = list({*existing.triggers, *new.triggers})
            merged[key] = new
        else:
            existing.evidence_list = list({*existing.evidence_list, *new.evidence_list})
            existing.triggers = list({*existing.triggers, *new.triggers})

    out = list(merged.values())
    logger.info("lookup_referrals: %d recommendation(s) for %d input name(s)",
                len(out), len(names))
    return out
