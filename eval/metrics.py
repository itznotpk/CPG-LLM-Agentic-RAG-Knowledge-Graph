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


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Binary-relevance nDCG@k. For graded relevance, extend `rel` map."""
    relevant = set(relevant)
    dcg = 0.0
    for i, r in enumerate(retrieved[:k], start=1):
        if r in relevant:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


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
