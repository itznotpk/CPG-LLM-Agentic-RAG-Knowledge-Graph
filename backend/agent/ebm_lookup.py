"""Stage 4.6 — live Europe PMC evidence fetch. NOT ingested/chunked; fail-open."""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

_HIGH = {"systematic-review", "systematic review", "meta-analysis", "meta analysis"}
_MODERATE = {"randomized controlled trial", "randomised controlled trial", "rct", "guideline", "practice guideline"}


def evidence_tier_for(pub_types: list[str]) -> Literal["high", "moderate", "low"]:
    """Map Europe PMC publication types onto a 3-tier evidence pyramid."""
    norm = {p.strip().lower() for p in pub_types if p}
    if norm & _HIGH:
        return "high"
    if norm & _MODERATE:
        return "moderate"
    return "low"
