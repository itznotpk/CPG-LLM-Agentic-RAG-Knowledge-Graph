"""
Referral KG extraction — Pass 2 (selective LLM extraction of referral triples).

Builds `(:Condition)-[:REQUIRES_REFERRAL {urgency, trigger, evidence, ...}]->(:Specialty)`
edges in the existing Neo4j graph so Stage 5's coverage check no longer relies
on the hard-coded `_ALWAYS_REFER_CONDITIONS` dict.

Pipeline:
    1. Fetch candidate chunks from Postgres (category whitelist + content regex
       filter). Cheap — no LLM cost. Most chunks drop out here.
    2. For each surviving chunk, call the ingestion LLM with the referral
       extraction prompt and parse a JSON array of triples.
    3. MERGE each triple into Neo4j as :Condition/:Specialty/REQUIRES_REFERRAL,
       idempotently. Re-running over the same chunks appends evidence to the
       edge's `evidence_list`, never duplicates edges.

Modes (CLI):
    --dry-run   Filter only; print candidate counts. No LLM, no writes.
    --extract   Filter + LLM extract. Prints triples. No writes.
    --write     Filter + LLM extract + Neo4j write.

Selectivity rationale: extracting from every chunk would be ~10k LLM calls and
mostly empty results. The regex pre-filter typically retains <10% of chunks,
making this affordable to re-run after new CPG ingest.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Path bootstrap so `python ingestion/extract_referrals.py` works without -m.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("extract_referrals")

# ---------------------------------------------------------------------------
# Filter configuration
# ---------------------------------------------------------------------------

# Categories where referral language is plausible. Mirrors graph_builder's
# CLINICAL_CATEGORY_WHITELIST but tighter — Diagnosis/Pathophysiology rarely
# contain referral guidance, so they are dropped here.
REFERRAL_CATEGORY_WHITELIST: set[Optional[str]] = {
    "Treatment",
    "Supportive Treatment",
    "Management",
    "Special Populations",
    "Prevention",
    "Assessment",
    "Referral",
    "Monitoring",
    "Pharmacological Treatment",
    "Non-Pharmacological Treatment",
    None,  # legacy chunks with no category set — keep, may have content
}

# Pre-filter regex. Captures positive referral signal phrases. Tightly worded
# to avoid matching "self-referral", "internal reference", "referred to as".
_REFERRAL_KEYWORD_RE = re.compile(
    r"\b("
    r"refer(?:red|ral)?\s+(?:to|for)\b"
    r"|should\s+be\s+referred\b"
    r"|consult(?:ation)?\s+(?:with|to)\b"
    r"|specialist\s+(?:input|review|referral|consultation|involvement|management|opinion)\b"
    r"|multidisciplinary\s+(?:team|management|discussion|approach)\b"
    r"|\bMDT\b"
    r"|co[-\s]?manag(?:ed|ement)\b"
    r"|transfer\s+of\s+care\b"
    r"|escalat(?:e|ion)\s+to\b"
    r"|onward\s+referral\b"
    r"|cardiolog(?:y|ist)|nephrolog(?:y|ist)|endocrinolog(?:y|ist)"
    r"|neurolog(?:y|ist)|oncolog(?:y|ist)|haematolog(?:y|ist)"
    r"|gastroenterolog(?:y|ist)|hepatolog(?:y|ist)|pulmonolog(?:y|ist)"
    r"|rheumatolog(?:y|ist)|psychiatr(?:y|ist)|dermatolog(?:y|ist)"
    r"|ophthalmolog(?:y|ist)|urolog(?:y|ist)|gynaecolog(?:y|ist)"
    r"|obstetric(?:s|ian)|paediatric(?:s|ian)|geriatric(?:s|ian)"
    r"|bariatric\s+(?:surgery|surgeon)|orthopaedic|palliative\s+care"
    r"|maternal[-\s]foetal|maternal[-\s]fetal"
    r")\b",
    re.IGNORECASE,
)

# Hard exclusion: lines that are purely negations of referral. We let the LLM
# do the fine-grained call, but if every match in a chunk is negated, drop it
# at the filter stage to save a call.
_NEGATION_NEAR_REFERRAL_RE = re.compile(
    r"\b(no|not|does\s+not|do\s+not|without)\b[^.]{0,60}\breferr",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Canonical vocabularies (must match the prompt in
# agent/prompts/referral_extraction.txt)
# ---------------------------------------------------------------------------

CANONICAL_SPECIALTIES: set[str] = {
    "Cardiology", "Nephrology", "Endocrinology", "Neurology", "Oncology",
    "Haematology", "Gastroenterology", "Hepatology", "Pulmonology",
    "Rheumatology", "Infectious Diseases", "Psychiatry", "Dermatology",
    "Ophthalmology", "Otolaryngology", "Urology", "Gynaecology", "Obstetrics",
    "Maternal-Foetal Medicine", "Paediatrics", "Geriatrics", "General Surgery",
    "Cardiothoracic Surgery", "Vascular Surgery", "Bariatric Surgery",
    "Orthopaedics", "Neurosurgery", "Emergency Medicine", "Intensive Care",
    "Palliative Care", "Pain Medicine", "Anaesthesia", "Dietetics",
    "Physiotherapy", "Pharmacy", "Social Work", "Multidisciplinary Team",
}
VALID_URGENCY = {"urgent", "routine", "consider"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ReferralTriple:
    condition: str
    specialty: str
    urgency: str
    trigger: Optional[str]
    evidence: str
    icd_hint: Optional[str]
    cpg_chunk_id: str
    cpg_source: str

    def to_dict(self) -> dict:
        return {
            "condition": self.condition,
            "specialty": self.specialty,
            "urgency": self.urgency,
            "trigger": self.trigger,
            "evidence": self.evidence,
            "icd_hint": self.icd_hint,
            "cpg_chunk_id": self.cpg_chunk_id,
            "cpg_source": self.cpg_source,
        }


# ---------------------------------------------------------------------------
# Pass 1 — Pre-filter (Postgres + regex)
# ---------------------------------------------------------------------------

_FETCH_CHUNKS_SQL = """
SELECT
    c.id::text       AS chunk_id,
    c.content        AS content,
    c.metadata->>'category' AS category,
    coalesce(c.metadata->>'cpg_name', d.title) AS cpg_source
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE ($1::text IS NULL
       OR d.title ILIKE '%' || $1 || '%'
       OR c.metadata->>'cpg_name' ILIKE '%' || $1 || '%')
  AND length(c.content) > 60
ORDER BY d.title, c.chunk_index
LIMIT $2;
"""


async def fetch_candidate_chunks(
    cpg_filter: Optional[str], limit: int
) -> list[dict[str, Any]]:
    """Pass 1a: pull chunks from Postgres, optionally restricted to one CPG."""
    from agent.db_utils import db_pool

    await db_pool.initialize()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(_FETCH_CHUNKS_SQL, cpg_filter, limit)
    return [dict(r) for r in rows]


def _category_in_whitelist(raw_category: Any) -> bool:
    """`metadata.category` in this corpus is a JSON array (e.g.
    `["Treatment", "Prevention"]`), so `metadata->>'category'` returns a
    JSON-encoded string like '["Treatment"]'. A chunk passes when ANY of its
    category labels is whitelisted, or when the column is null/empty (legacy)."""
    if raw_category is None:
        return None in REFERRAL_CATEGORY_WHITELIST
    if isinstance(raw_category, list):
        cats = raw_category
    elif isinstance(raw_category, str):
        s = raw_category.strip()
        if not s:
            return None in REFERRAL_CATEGORY_WHITELIST
        if s.startswith("["):
            try:
                cats = json.loads(s)
                if not isinstance(cats, list):
                    cats = [s]
            except json.JSONDecodeError:
                cats = [s]
        else:
            cats = [s]
    else:
        cats = [str(raw_category)]
    return any(c in REFERRAL_CATEGORY_WHITELIST for c in cats)


def filter_referral_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pass 1b: category whitelist + regex match on content. Returns a
    subset of `rows`; non-destructive."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if not _category_in_whitelist(r.get("category")):
            continue
        text = r.get("content") or ""
        if not _REFERRAL_KEYWORD_RE.search(text):
            continue
        # If the only referral signal is inside a negation, drop. Conservative:
        # only drop when at least one negation AND no remaining positive hit
        # exists outside that negation context (160-char window).
        if _NEGATION_NEAR_REFERRAL_RE.search(text):
            # Cheap: re-check by removing negation spans.
            scrubbed = _NEGATION_NEAR_REFERRAL_RE.sub(" ", text)
            if not _REFERRAL_KEYWORD_RE.search(scrubbed):
                continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Pass 2 — LLM extraction
# ---------------------------------------------------------------------------

_PROMPT_PATH = ROOT / "agent" / "prompts" / "referral_extraction.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _normalise_specialty(raw: str) -> str:
    """Title-case and map common variants to canonical names."""
    if not raw:
        return ""
    s = raw.strip()
    # Common variants → canonical
    lowered = s.lower()
    variant_map = {
        "cardiologist": "Cardiology",
        "cardiology team": "Cardiology",
        "heart failure clinic": "Cardiology",
        "hf clinic": "Cardiology",
        "nephrologist": "Nephrology",
        "kidney specialist": "Nephrology",
        "renal team": "Nephrology",
        "endocrinologist": "Endocrinology",
        "diabetologist": "Endocrinology",
        "neurologist": "Neurology",
        "oncologist": "Oncology",
        "haematologist": "Haematology",
        "hematologist": "Haematology",
        "hematology": "Haematology",
        "gastroenterologist": "Gastroenterology",
        "hepatologist": "Hepatology",
        "pulmonologist": "Pulmonology",
        "respiratory physician": "Pulmonology",
        "rheumatologist": "Rheumatology",
        "psychiatrist": "Psychiatry",
        "dermatologist": "Dermatology",
        "ophthalmologist": "Ophthalmology",
        "urologist": "Urology",
        "gynaecologist": "Gynaecology",
        "obstetrician": "Obstetrics",
        "mfm": "Maternal-Foetal Medicine",
        "maternal fetal medicine": "Maternal-Foetal Medicine",
        "paediatrician": "Paediatrics",
        "geriatrician": "Geriatrics",
        "bariatric surgeon": "Bariatric Surgery",
        "orthopaedic surgeon": "Orthopaedics",
        "mdt": "Multidisciplinary Team",
        "dietitian": "Dietetics",
        "physiotherapist": "Physiotherapy",
        "pharmacist": "Pharmacy",
    }
    if lowered in variant_map:
        return variant_map[lowered]
    title = s.title() if s.islower() or s.isupper() else s
    return title


def _validate_triple(raw: dict, chunk_id: str, cpg_source: str) -> Optional[ReferralTriple]:
    """Validate one LLM-emitted triple. Returns None to drop."""
    try:
        condition = (raw.get("condition") or "").strip()
        specialty = _normalise_specialty((raw.get("specialty") or "").strip())
        urgency = (raw.get("urgency") or "routine").strip().lower()
        evidence = (raw.get("evidence") or "").strip()[:500]
        trigger = (raw.get("trigger") or None) or None
        icd_hint = (raw.get("icd_hint") or None) or None
    except (AttributeError, TypeError):
        return None

    if not condition or not specialty or not evidence:
        return None
    if urgency not in VALID_URGENCY:
        urgency = "routine"
    # Tolerate off-vocab specialties (keep them) but flag in log.
    if specialty not in CANONICAL_SPECIALTIES:
        logger.debug("Off-vocab specialty kept verbatim: %s", specialty)

    return ReferralTriple(
        condition=condition,
        specialty=specialty,
        urgency=urgency,
        trigger=trigger if isinstance(trigger, str) and trigger.strip() else None,
        evidence=evidence,
        icd_hint=icd_hint if isinstance(icd_hint, str) and icd_hint.strip() else None,
        cpg_chunk_id=chunk_id,
        cpg_source=cpg_source,
    )


async def extract_from_chunk(
    chunk: dict[str, Any], prompt: str, concurrency_sem: asyncio.Semaphore
) -> list[ReferralTriple]:
    """Call the ingestion LLM on one filtered chunk; parse triples."""
    from pydantic_ai import Agent

    try:
        from agent.providers import get_ingestion_model
        model = get_ingestion_model()
    except Exception as exc:
        logger.error("Could not load ingestion model: %s", exc)
        return []

    text = chunk["content"]
    chunk_id = chunk["chunk_id"]
    cpg_source = chunk.get("cpg_source") or ""
    full_prompt = f"{prompt}\n\n[FOCUS - extract referrals from this region only]\n{text}\n"

    async with concurrency_sem:
        agent = Agent(model)
        result_text = ""
        delay = 2.0
        for attempt in range(5):
            try:
                response = await agent.run(full_prompt)
                result_text = (response.output or "").strip()
                break
            except Exception as exc:
                is_throttle = "429" in str(exc) or "ThrottlingException" in str(exc) or "Too many requests" in str(exc)
                if is_throttle and attempt < 4:
                    logger.info("Throttle on chunk %s attempt %d, sleeping %.1fs", chunk_id, attempt + 1, delay)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30.0)
                    continue
                logger.warning("LLM call failed for chunk %s (attempt %d): %s", chunk_id, attempt + 1, exc)
                return []

    # Best-effort JSON extraction
    match = re.search(r"\[.*\]", result_text, re.DOTALL)
    if not match:
        return []
    try:
        arr = json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.debug("JSON parse failed for chunk %s: %s", chunk_id, exc)
        return []
    if not isinstance(arr, list):
        return []

    triples: list[ReferralTriple] = []
    for raw in arr:
        if not isinstance(raw, dict):
            continue
        t = _validate_triple(raw, chunk_id, cpg_source)
        if t:
            triples.append(t)
    return triples


# ---------------------------------------------------------------------------
# Pass 3 — Neo4j write (MERGE + idempotent)
# ---------------------------------------------------------------------------

_WRITE_CYPHER = """
MERGE (c:Condition {name_normalised: $cond_norm})
    ON CREATE SET c.name = $cond_display
MERGE (s:Specialty {name_normalised: $spec_norm})
    ON CREATE SET s.name = $spec_display
MERGE (c)-[r:REQUIRES_REFERRAL {urgency: $urgency}]->(s)
ON CREATE SET
    r.evidence       = $evidence,
    r.evidence_list  = [$evidence],
    r.trigger        = $trigger,
    r.trigger_list   = CASE WHEN $trigger IS NULL THEN [] ELSE [$trigger] END,
    r.icd_hint       = $icd_hint,
    r.cpg_chunk_id   = $cpg_chunk_id,
    r.cpg_chunk_ids  = [$cpg_chunk_id],
    r.source_document= $cpg_source,
    r.created_at     = datetime()
ON MATCH SET
    r.evidence_list = CASE
        WHEN $evidence IN coalesce(r.evidence_list, []) THEN r.evidence_list
        ELSE coalesce(r.evidence_list, [r.evidence]) + [$evidence]
    END,
    r.trigger_list = CASE
        WHEN $trigger IS NULL THEN coalesce(r.trigger_list, [])
        WHEN $trigger IN coalesce(r.trigger_list, []) THEN coalesce(r.trigger_list, [])
        ELSE coalesce(r.trigger_list, []) + [$trigger]
    END,
    r.cpg_chunk_ids = CASE
        WHEN $cpg_chunk_id IN coalesce(r.cpg_chunk_ids, []) THEN coalesce(r.cpg_chunk_ids, [])
        ELSE coalesce(r.cpg_chunk_ids, []) + [$cpg_chunk_id]
    END,
    r.icd_hint = CASE WHEN r.icd_hint IS NULL THEN $icd_hint ELSE r.icd_hint END
"""


async def write_triples_to_neo4j(triples: list[ReferralTriple]) -> int:
    """MERGE all triples. Returns count written. Fail-loud — caller decides."""
    if not triples:
        return 0
    from agent.graph_clinical import _get_neo4j_session

    session_ctx = await _get_neo4j_session()
    written = 0
    async with session_ctx as session:
        for t in triples:
            cond_display = t.condition.strip()
            spec_display = t.specialty.strip()
            await session.run(
                _WRITE_CYPHER,
                cond_norm=cond_display.lower(),
                cond_display=cond_display,
                spec_norm=spec_display.lower(),
                spec_display=spec_display,
                urgency=t.urgency,
                evidence=t.evidence,
                trigger=t.trigger,
                icd_hint=t.icd_hint,
                cpg_chunk_id=t.cpg_chunk_id,
                cpg_source=t.cpg_source,
            )
            written += 1
    return written


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run(
    mode: str,
    cpg_filter: Optional[str],
    limit: int,
    concurrency: int,
    output_json: Optional[Path],
) -> int:
    logger.info("Fetching candidate chunks (cpg=%s, limit=%d)…", cpg_filter, limit)
    rows = await fetch_candidate_chunks(cpg_filter, limit)
    logger.info("Pulled %d rows from Postgres", len(rows))

    candidates = filter_referral_candidates(rows)
    logger.info(
        "Pre-filter retained %d / %d chunks (%.1f%%)",
        len(candidates), len(rows), 100.0 * len(candidates) / max(1, len(rows)),
    )

    # Per-CPG breakdown helps spot CPGs with zero referral language (likely a
    # bad filter, not a real signal).
    by_cpg: dict[str, int] = {}
    for c in candidates:
        by_cpg[c["cpg_source"]] = by_cpg.get(c["cpg_source"], 0) + 1
    for cpg, n in sorted(by_cpg.items(), key=lambda kv: -kv[1])[:15]:
        logger.info("  %3d candidates from %s", n, cpg)

    if mode == "dry-run":
        return 0

    prompt = _load_prompt()
    sem = asyncio.Semaphore(concurrency)
    logger.info("Extracting triples (concurrency=%d)…", concurrency)
    results = await asyncio.gather(
        *(extract_from_chunk(c, prompt, sem) for c in candidates),
        return_exceptions=False,
    )
    triples: list[ReferralTriple] = [t for batch in results for t in batch]
    logger.info("Extracted %d triples from %d chunks", len(triples), len(candidates))

    # Per-specialty breakdown
    by_spec: dict[str, int] = {}
    for t in triples:
        by_spec[t.specialty] = by_spec.get(t.specialty, 0) + 1
    for spec, n in sorted(by_spec.items(), key=lambda kv: -kv[1]):
        logger.info("  %3d → %s", n, spec)

    if output_json:
        output_json.write_text(
            json.dumps([t.to_dict() for t in triples], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Wrote %d triples to %s", len(triples), output_json)

    if mode == "extract":
        return 0

    assert mode == "write"
    written = await write_triples_to_neo4j(triples)
    logger.info("Wrote %d triples to Neo4j", written)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract referral triples from CPG chunks and write to Neo4j",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_const", dest="mode", const="dry-run",
                       help="Filter only; print counts. No LLM, no writes.")
    group.add_argument("--extract", action="store_const", dest="mode", const="extract",
                       help="Filter + LLM extract. Prints triples; no Neo4j writes.")
    group.add_argument("--write", action="store_const", dest="mode", const="write",
                       help="Filter + LLM extract + write to Neo4j.")
    parser.add_argument("--cpg", default=None,
                        help="Restrict to documents whose title ILIKE %CPG%.")
    parser.add_argument("--limit", type=int, default=100_000,
                        help="Cap on chunks fetched from Postgres (default: all).")
    parser.add_argument("--concurrency", type=int, default=6,
                        help="Parallel LLM calls (default: 6).")
    parser.add_argument("--out", type=Path, default=None,
                        help="Optional path to write extracted triples as JSON.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    return asyncio.run(run(args.mode, args.cpg, args.limit, args.concurrency, args.out))


if __name__ == "__main__":
    sys.exit(main())
