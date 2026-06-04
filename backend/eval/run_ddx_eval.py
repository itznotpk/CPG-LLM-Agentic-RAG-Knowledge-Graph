"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer A1  →  Pipeline Stage 2 (Symptom → ICD-11 DDx)
═══════════════════════════════════════════════════════════════════════════════
Metric idea
-----------
For each vignette in ddx_gold.jsonl, call `stage_2_ddx(case)` and check
whether the expected ICD-11 code is in the returned top-k. Aggregate to
Hit@5, Hit@10, MRR and set-overlap F1.

Wiring
------
- agent.clinical_stages.stage_2_ddx(case: PatientCase, top_k, rerank, emit=None)
  returns list[DDxResult], each with .code .title .similarity
- PatientCase requires chief_complaint (non-empty); we plug the vignette there.

No clinician needed — the ICD-11 code IS the ground truth.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import argparse
import asyncio
import time

from agent.clinical_stages import stage_2_ddx
from agent.models import PatientCase

from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import (
    hit_rate_at_k, mrr, set_overlap, mean,
    is_lineage, hit_at_k_pred, mrr_pred, graded_best_at_k,
)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Only run the first N vignettes (0 = all; for smoke tests)")
    args = ap.parse_args()

    gold = load_jsonl("ddx_gold.jsonl")
    if args.limit:
        gold = gold[: args.limit]
    total = len(gold)
    rows = []
    hits = 0
    run_start = time.perf_counter()
    print(f"DDx eval: {total} vignettes — running stage_2_ddx (rerank=True)...", flush=True)
    for i, item in enumerate(gold, start=1):
        t0 = time.perf_counter()
        case = PatientCase(chief_complaint=item["vignette"])
        top_k = item.get("expected_top_k", 10)
        # rerank=True matches production behaviour. Set False for a "retrieval-only" view.
        ddx_results = await stage_2_ddx(case, top_k=top_k, rerank=True)
        predicted = [d.code for d in ddx_results]
        expected = item["expected_icd11_codes"]
        overlap = set_overlap(predicted, expected)
        hit5 = hit_rate_at_k(predicted, expected, k=5)
        # Lineage-aware (Lever 2, dynamic): credit a code that is an ancestor or
        # descendant of an expected code (ICD-11 prefix chain) — e.g. gold 2B90 vs
        # returned 2B90.30, or gold MG30.1 vs returned MG30. Excludes siblings
        # (5C80.0 vs 5C80.2), so genuinely different sub-diagnoses still miss.
        lin_rel = lambda code: any(is_lineage(code, e) for e in expected)  # noqa: E731
        hits += int(hit5 == 1.0)
        rows.append({
            "id": item["id"],
            "expected": ",".join(expected),
            "predicted_top10": ",".join(predicted[:10]),
            "hit@5": hit5,
            "hit@10": hit_rate_at_k(predicted, expected, k=10),
            "mrr": mrr(predicted, expected),
            "lin_hit@5": hit_at_k_pred(predicted, 5, lin_rel),
            "lin_hit@10": hit_at_k_pred(predicted, 10, lin_rel),
            "lin_mrr": mrr_pred(predicted, lin_rel),
            # Graded (Lever H): 1.0 exact · 0.6 lineage · 0.3 sibling · 0 else, best in top-5.
            "graded@5": graded_best_at_k(predicted, expected, 5),
            "f1": overlap["f1"],
        })
        elapsed = time.perf_counter() - t0
        mark = "HIT " if hit5 == 1.0 else "miss"
        print(
            f"[{i:2d}/{total}] {item['id']:8s} {mark} "
            f"exp={','.join(expected):16s} got={','.join(predicted[:5]):28s} "
            f"({elapsed:4.1f}s) running hit@5={hits}/{i}",
            flush=True,
        )
    print(f"DDx eval: done in {time.perf_counter() - run_start:.0f}s", flush=True)

    summary = {
        "n": len(rows),
        "hit_rate@5": mean(r["hit@5"] for r in rows),
        "hit_rate@10": mean(r["hit@10"] for r in rows),
        "MRR": mean(r["mrr"] for r in rows),
        "lin_hit_rate@5": mean(r["lin_hit@5"] for r in rows),
        "lin_hit_rate@10": mean(r["lin_hit@10"] for r in rows),
        "lin_MRR": mean(r["lin_mrr"] for r in rows),
        "graded@5": mean(r["graded@5"] for r in rows),
        "mean_f1": mean(r["f1"] for r in rows),
    }
    print_summary("DDx (Stage 2)", summary)
    if args.limit:
        print("[info] --limit set: skipping result-file write (smoke run)")
    else:
        write_results("ddx", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
