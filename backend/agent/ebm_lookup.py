"""Stage 4.6 — live Europe PMC evidence fetch. NOT ingested/chunked; fail-open."""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Literal

from .models import EbmEvidence

logger = logging.getLogger(__name__)

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
