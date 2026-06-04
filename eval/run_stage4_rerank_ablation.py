"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer C (re-ranker / category-boost) — CLEAN ISOLATION
         →  Pipeline Stage 4 boost-on vs boost-off, identical candidate pool
═══════════════════════════════════════════════════════════════════════════════
Why this is the honest Layer C metric
-------------------------------------
Layer C IS the re-ranker: Stage 4's category-boost (`stage4_boosted_score`,
agent/clinical_stages.py) promotes Treatment/Assessment/Diagnosis chunks and
demotes Pathophysiology/Methodology, then cuts top-20. VALIDATION_PLAN §"Layer C"
says: "Compare top-k before and after re-ranking. Show nDCG lift."

run_stage4_eval.py / run_stage4_multicondition_eval.py compare the FULL Stage-4
path against a single-query baseline — that conflates the multi-query fan-out
(a Layer B effect) with the boost (the actual Layer C effect), and is sensitive
to how the gold candidate pool was gathered.

This ablation isolates ONLY the re-rank:
  - Run the real Stage 4 path with return_pool=True → get the deduped candidate
    pool BEFORE the boost-sort + top-20 cut.
  - Order A (boost OFF): sort the pool by raw vector score → top-20.
  - Order B (boost ON) : sort the pool by stage4_boosted_score → top-20.
  - Score both against the gold relevant_chunk_ids; report nDCG@10 / MRR / recall@20.
  - lift = boost-ON − boost-OFF.

Both arms see the IDENTICAL chunk set, so the gold-construction bias and the
baseline-asymmetry that affect the lift harness cancel out — the only difference
is the ordering the re-ranker imposes. This is the defensible Layer C number.

Run
---
  python -m eval.run_stage4_rerank_ablation
  python -m eval.run_stage4_rerank_ablation --only mc_011

Gold
----
  eval/gold_sets/stage4_multicondition_gold.jsonl
  relevant_chunk_ids + relevance_grades populated by
  eval/label_stage4_multicondition_gold.py (LLM-judged). The ablation only needs
  the relevance labels — it does NOT depend on how the candidate pool was gathered.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import argparse
import asyncio

from agent.clinical_stages import stage_4_retrieve, stage4_boosted_score, DDxResult
from agent.models import PatientCase
from agent.routing import CPGDocRef

from eval.io_utils import load_jsonl, write_results, print_summary
from eval._helpers import resolve_cpg_title_to_doc_ids
from eval.metrics import recall_at_k, mrr, ndcg_at_k, hit_rate_at_k, mean

# Reuse the case/CPG builders from the lift harness — same gold, same stubs.
from eval.run_stage4_multicondition_eval import _build_patient_case, _build_cpg_refs

GOLD_FILE = "stage4_multicondition_gold.jsonl"


def _score(retrieved_ids, relevant, grades):
    return {
        "recall@20": recall_at_k(retrieved_ids, relevant, 20),
        "mrr":       mrr(retrieved_ids, relevant),
        "ndcg@10":   ndcg_at_k(retrieved_ids, relevant, 10, grades=grades),
        "hit@10":    hit_rate_at_k(retrieved_ids, relevant, 10),
    }


async def run_item(item: dict, queries_per_code: int, chunks_per_query: int) -> dict | None:
    relevant = item.get("relevant_chunk_ids") or []
    if not relevant:
        print(f"[skip] {item['id']}: no relevant_chunk_ids "
              f"(run label_stage4_multicondition_gold.py first)")
        return None
    grades = item.get("relevance_grades") or None

    case = _build_patient_case(item["patient_case"])
    ddx = [DDxResult(code=d["code"], title=d["title"], similarity=1.0)
           for d in item.get("expected_ddx", [])]
    cpgs, _doc_ids = await _build_cpg_refs(item["expected_cpgs"])
    if not cpgs:
        print(f"[skip] {item['id']}: no CPGs resolved")
        return None

    # Real Stage 4 path, but also hand back the pre-truncation candidate pool.
    _final, pool = await stage_4_retrieve(
        case, ddx, cpgs,
        queries_per_code=queries_per_code,
        chunks_per_query=chunks_per_query,
        return_pool=True,
    )

    # Two orderings of the SAME pool — the only variable is the re-rank.
    raw_order   = sorted(pool, key=lambda c: c.score, reverse=True)[:20]
    boost_order = sorted(pool, key=stage4_boosted_score, reverse=True)[:20]

    off = _score([c.chunk_id for c in raw_order], relevant, grades)
    on  = _score([c.chunk_id for c in boost_order], relevant, grades)

    return {
        "id":             item["id"],
        "source_case":    item.get("source_case", ""),
        "n_pool":         len(pool),
        "n_relevant":     len(relevant),
        "ndcg@10_off":    off["ndcg@10"],
        "ndcg@10_on":     on["ndcg@10"],
        "ndcg@10_lift":   on["ndcg@10"] - off["ndcg@10"],
        "mrr_off":        off["mrr"],
        "mrr_on":         on["mrr"],
        "mrr_lift":       on["mrr"] - off["mrr"],
        "recall@20_off":  off["recall@20"],
        "recall@20_on":   on["recall@20"],   # identical pool ⇒ recall@20 ties unless pool>20
        "hit@10_off":     off["hit@10"],
        "hit@10_on":      on["hit@10"],
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries-per-code", type=int, default=7)
    ap.add_argument("--chunks-per-query", type=int, default=5)
    ap.add_argument("--item-delay", type=float, default=3.0)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    gold = load_jsonl(GOLD_FILE)
    rows: list[dict] = []
    skipped = 0
    for i, item in enumerate(gold, 1):
        if args.only and item["id"] != args.only:
            continue
        print(f"[{i}/{len(gold)}] {item['id']} ({item.get('source_case','')})")
        result = await run_item(item, args.queries_per_code, args.chunks_per_query)
        if result is None:
            skipped += 1
        else:
            rows.append(result)
            print(f"        nDCG@10 off={result['ndcg@10_off']:.3f} "
                  f"on={result['ndcg@10_on']:.3f} lift={result['ndcg@10_lift']:+.3f} | "
                  f"MRR lift={result['mrr_lift']:+.3f}")
        await asyncio.sleep(args.item_delay)

    if not rows:
        print("\n[error] no cases scored — is the gold set labelled?")
        return

    summary = {
        "queries_per_code":  args.queries_per_code,
        "chunks_per_query":  args.chunks_per_query,
        "n":                 len(rows),
        "skipped":           skipped,
        "nDCG@10_boost_off": mean(r["ndcg@10_off"] for r in rows),
        "nDCG@10_boost_on":  mean(r["ndcg@10_on"] for r in rows),
        "mean_nDCG@10_lift": mean(r["ndcg@10_lift"] for r in rows),
        "MRR_boost_off":     mean(r["mrr_off"] for r in rows),
        "MRR_boost_on":      mean(r["mrr_on"] for r in rows),
        "mean_MRR_lift":     mean(r["mrr_lift"] for r in rows),
    }
    print_summary("Stage 4 re-rank ablation (boost on vs off) — Layer C", summary)
    write_results("stage4_rerank_ablation", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
