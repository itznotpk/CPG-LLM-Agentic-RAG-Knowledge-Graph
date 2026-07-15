"""Stage 4.6 — live Europe PMC evidence fetch. NOT ingested/chunked; fail-open."""
from __future__ import annotations

import asyncio
import datetime as _dt
import httpx
import logging
from typing import Literal

from .models import EbmEvidence

logger = logging.getLogger(__name__)

_EUROPEPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EBM_CACHE: dict[str, list] = {}

_HIGH = {"systematic-review", "systematic review", "meta-analysis", "meta analysis"}
_MODERATE = {"randomized controlled trial", "randomised controlled trial", "rct", "guideline", "practice guideline"}

_PUB_TYPE_FILTER = (
    '(PUB_TYPE:"systematic review" OR PUB_TYPE:"meta-analysis" '
    'OR PUB_TYPE:"randomized controlled trial" OR PUB_TYPE:"guideline")'
)


def evidence_tier_for(pub_types: list[str]) -> Literal["high", "moderate", "low"]:
    """Map Europe PMC publication types onto a 3-tier evidence pyramid."""
    norm = {p.strip().lower() for p in pub_types if p}
    if norm & _HIGH:
        return "high"
    if norm & _MODERATE:
        return "moderate"
    return "low"


def build_europepmc_query(diseases: list[str], terms: list[str], *, recency_years: int = 7) -> str:
    """Build a Europe PMC search query scoped to graded, recent, abstract-bearing evidence."""
    diseases = [d.strip() for d in diseases if d and d.strip()]
    terms = [t.strip() for t in terms if t and t.strip()]
    disease_clause = " OR ".join(f'"{d}"' for d in diseases) or '""'
    parts = [f"({disease_clause})"]
    if terms:
        term_clause = " OR ".join(f'"{t}"' for t in terms)
        parts.append(f"({term_clause})")
    parts.append(_PUB_TYPE_FILTER)
    parts.append("HAS_ABSTRACT:Y")
    this_year = _dt.date.today().year
    parts.append(f"(PUB_YEAR:[{this_year - recency_years} TO {this_year}])")
    return " AND ".join(parts)


def parse_europepmc_response(payload: dict, *, snippet_chars: int = 500) -> list[EbmEvidence]:
    """Parse Europe PMC API response into graded EbmEvidence objects.

    Drops articles without abstracts (never feed empty abstracts to synthesis).
    Truncates abstracts to snippet_chars.
    """
    results = (payload or {}).get("resultList", {}).get("result", []) or []
    out: list[EbmEvidence] = []
    for r in results:
        abstract = (r.get("abstractText") or "").strip()
        if not abstract:
            continue  # never feed empty abstracts to synthesis
        pub_types = (r.get("pubTypeList") or {}).get("pubType", []) or []
        pmid = r.get("pmid") or r.get("id")
        year_raw = r.get("pubYear")
        try:
            year = int(year_raw) if year_raw else None
        except (TypeError, ValueError):
            year = None
        out.append(EbmEvidence(
            title=(r.get("title") or "").strip(),
            abstract_snippet=abstract[:snippet_chars],
            journal=(r.get("journalTitle") or "").strip(),
            year=year,
            pub_type=", ".join(pub_types),
            evidence_tier=evidence_tier_for(pub_types),
            pmid=pmid,
            doi=r.get("doi"),
            url=f"https://europepmc.org/article/MED/{pmid}" if pmid else "",
        ))
    return out


def _cache_key(diseases: list[str], terms: list[str], limit: int, recency_years: int) -> str:
    d = ",".join(sorted(x.strip().lower() for x in diseases if x))
    t = ",".join(sorted(x.strip().lower() for x in terms if x))
    return f"{d}|{t}|{limit}|{recency_years}"


async def fetch_ebm_evidence(
    diseases: list[str],
    terms: list[str],
    *,
    limit: int = 5,
    timeout_s: float = 4.0,
    recency_years: int = 7,
    attempts: int = 2,
) -> list["EbmEvidence"]:
    """Live Europe PMC fetch. FAIL-OPEN: returns [] on any error. Never raises."""
    diseases = [d for d in (diseases or []) if d and d.strip()]
    if not diseases:
        return []
    key = _cache_key(diseases, terms or [], limit, recency_years)
    if key in _EBM_CACHE:
        return _EBM_CACHE[key]

    query = build_europepmc_query(diseases, terms or [], recency_years=recency_years)
    params = {
        "query": query, "format": "json", "pageSize": str(limit),
        "resultType": "core", "sort": "P_PDATE_D desc",
    }
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.get(_EUROPEPMC_URL, params=params)
                resp.raise_for_status()
                parsed = parse_europepmc_response(resp.json())[:limit]
                _EBM_CACHE[key] = parsed
                logger.info("ebm: %d citations for %s", len(parsed), diseases)
                return parsed
        except Exception as e:  # noqa: BLE001 — fail-open by contract
            logger.warning("ebm fetch attempt %d/%d failed: %s", attempt + 1, attempts, e)
            if attempt + 1 < attempts:
                await asyncio.sleep(0.5 * (attempt + 1))
    return []
