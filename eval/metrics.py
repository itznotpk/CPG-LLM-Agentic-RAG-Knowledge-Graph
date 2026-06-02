"""
Shared metric functions used by every eval script.

Layer coverage:
- Recall@k, Precision@k, MRR, nDCG, Hit Rate  ── Layer B (Retrieval)
- top-k overlap / rank correlation             ── Layer C (Re-ranker)
- exact_match / contains_match                 ── Layer A2 (Routing), Layer E
- groundedness / citation_match (LLM-as-judge) ── Layer D (Generation)
"""

from __future__ import annotations
import math
from typing import Sequence, Iterable


# ─────────────────────────────────────────────────────────────────────────────
# Layer B — Retrieval metrics
# ─────────────────────────────────────────────────────────────────────────────

def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of gold-relevant items that appear in top-k retrieved."""
    relevant = set(relevant)
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / len(relevant)


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevant = set(relevant)
    if k == 0:
        return 0.0
    top_k = retrieved[:k]
    return sum(1 for r in top_k if r in relevant) / k


def hit_rate_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """1 if any relevant item is in top-k, else 0."""
    relevant = set(relevant)
    return 1.0 if any(r in relevant for r in retrieved[:k]) else 0.0


def mrr(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """Reciprocal rank of FIRST relevant retrieved item (0 if none)."""
    relevant = set(relevant)
    for i, r in enumerate(retrieved, start=1):
        if r in relevant:
            return 1.0 / i
    return 0.0


_GRADE_GAIN = {"primary": 2.0, "supporting": 1.0}


def ndcg_at_k(
    retrieved: Sequence[str],
    relevant: Iterable[str],
    k: int,
    grades: dict[str, str] | None = None,
) -> float:
    """nDCG@k. Binary by default; graded when `grades` (chunk_id -> 'primary'|
    'supporting') is supplied — gain 2 for primary, 1 for supporting, 0 otherwise.
    Any relevant id missing from `grades` falls back to gain 1 (supporting)."""
    relevant = set(relevant)

    def gain(cid: str) -> float:
        if cid not in relevant:
            return 0.0
        if grades is None:
            return 1.0
        return _GRADE_GAIN.get(grades.get(cid, "supporting"), 1.0)

    dcg = sum(gain(r) / math.log2(i + 1) for i, r in enumerate(retrieved[:k], start=1))
    ideal_gains = sorted((gain(c) for c in relevant), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 1) for i, g in enumerate(ideal_gains, start=1))
    return dcg / idcg if idcg > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# ICD-11 hierarchy-aware matching (Layer A1 — DDx)
#
# All dynamic: derived from the ICD-11 code string itself, no per-case tables.
#   - exact      : verbatim code equality
#   - lineage    : one code is an ancestor/descendant of the other (prefix chain)
#   - sibling    : same 4-char category stem but not lineage (e.g. 5C80.0 vs 5C80.2)
# ─────────────────────────────────────────────────────────────────────────────

def icd_stem(code: str) -> str:
    """4-char ICD-11 category stem — the part before the dot (BA41.0 → BA41)."""
    return (code or "").split(".")[0].strip().upper()


def _norm_code(code: str) -> str:
    return (code or "").strip().upper()


def is_lineage(pred: str, exp: str) -> bool:
    """True when `pred` equals, is an ancestor of, or is a descendant of `exp`.
    ICD-11 children extend the parent string (BC81.3 → BC81.3Y, BC81.30), so the
    ancestor/descendant relation is a pure prefix test — dynamic, no DB lookup.
    Deliberately excludes siblings (5C80.0 vs 5C80.2 share a parent but neither is
    a prefix of the other), so genuinely different sub-diagnoses are not credited."""
    p, e = _norm_code(pred), _norm_code(exp)
    if not p or not e:
        return False
    return p == e or p.startswith(e) or e.startswith(p)


def icd_relation_gain(pred: str, exp: str) -> float:
    """Graded gain for one (pred, exp) pair: 1.0 exact · 0.6 ancestor/descendant ·
    0.3 same-category sibling · 0.0 otherwise. Used for the graded A1 score."""
    p, e = _norm_code(pred), _norm_code(exp)
    if not p or not e:
        return 0.0
    if p == e:
        return 1.0
    if p.startswith(e) or e.startswith(p):
        return 0.6
    if icd_stem(p) == icd_stem(e):
        return 0.3
    return 0.0


def hit_at_k_pred(retrieved: Sequence[str], k: int, is_relevant) -> float:
    """Hit@k under a custom relevance predicate (callable code -> bool)."""
    return 1.0 if any(is_relevant(r) for r in retrieved[:k]) else 0.0


def mrr_pred(retrieved: Sequence[str], is_relevant) -> float:
    """Reciprocal rank of the first item satisfying `is_relevant` (0 if none)."""
    for i, r in enumerate(retrieved, start=1):
        if is_relevant(r):
            return 1.0 / i
    return 0.0


def graded_best_at_k(retrieved: Sequence[str], expected: Iterable[str], k: int) -> float:
    """Best graded gain found within top-k: max over retrieved[:k] × expected of
    `icd_relation_gain`. 1.0 = an exact code is in top-k; 0.6 = best is a family
    ancestor/descendant; 0.3 = best is a sibling; 0.0 = nothing related."""
    expected = list(expected)
    best = 0.0
    for r in retrieved[:k]:
        for e in expected:
            g = icd_relation_gain(r, e)
            if g > best:
                best = g
                if best >= 1.0:
                    return 1.0
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Layer A2 / Layer E — Match metrics for routing & exact-answer Q&A
# ─────────────────────────────────────────────────────────────────────────────

def exact_match(predicted: str, expected: str) -> float:
    return 1.0 if predicted.strip().lower() == expected.strip().lower() else 0.0


def contains_match(predicted: str, expected_terms: Iterable[str]) -> float:
    """1.0 if every expected term appears (case-insensitive substring) in predicted."""
    p = predicted.lower()
    return 1.0 if all(t.lower() in p for t in expected_terms) else 0.0


def set_overlap(predicted: Iterable[str], expected: Iterable[str]) -> dict:
    """For multi-label tasks (e.g. DDx returns multiple ICD codes)."""
    p, e = set(predicted), set(expected)
    if not e:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    tp = len(p & e)
    precision = tp / len(p) if p else 0.0
    recall = tp / len(e)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation helper
# ─────────────────────────────────────────────────────────────────────────────

def mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0
