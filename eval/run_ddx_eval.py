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
import asyncio
import time

from agent.clinical_stages import stage_2_ddx
from agent.models import PatientCase

from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import hit_rate_at_k, mrr, set_overlap, mean


async def main():
    gold = load_jsonl("ddx_gold.jsonl")
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
        hits += int(hit5 == 1.0)
        rows.append({
            "id": item["id"],
            "expected": ",".join(expected),
            "predicted_top5": ",".join(predicted[:5]),
            "hit@5": hit5,
            "hit@10": hit_rate_at_k(predicted, expected, k=10),
            "mrr": mrr(predicted, expected),
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
        "mean_f1": mean(r["f1"] for r in rows),
    }
    print_summary("DDx (Stage 2)", summary)
    write_results("ddx", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
