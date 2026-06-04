"""
Throttled subsample variant of `run_ddx_eval` (Layer A1).

Same logic as `run_ddx_eval.py` (vignette → stage_2_ddx → metrics), but:
 - Sub-samples to the first N items (default 20) so the eval fits one provider quota window.
 - Adds a per-item sleep so the ~4 LLM calls per vignette don't pile into a 429 burst.
 - Prints per-item progress so a stall is visible instead of an empty output file.
 - Coerces any per-item failure to a 0-hit row so the aggregate still computes.
 - Writes to eval/results/ddx_throttled_<stamp>.{csv,json}.

Use this when the full `run_ddx_eval` is stuck in 60 s provider Retry-After loops
— it produces statistically weaker (smaller-n) but real, captured numbers
instead of an indefinite stall.
"""
from __future__ import annotations
import argparse
import asyncio

from agent.clinical_stages import stage_2_ddx
from agent.models import PatientCase

from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import hit_rate_at_k, mrr, set_overlap, mean


async def main(n: int, between_cases_s: float):
    gold = load_jsonl("ddx_gold.jsonl")[:n]
    rows: list[dict] = []

    for idx, item in enumerate(gold, 1):
        gid = item.get("id") or f"row{idx}"
        print(f"[run] {idx}/{len(gold)}  {gid}", flush=True)
        try:
            case = PatientCase(chief_complaint=item["vignette"])
            top_k = item.get("expected_top_k", 10)
            ddx_results = await stage_2_ddx(case, top_k=top_k, rerank=True)
            predicted = [d.code for d in ddx_results]
            expected = item["expected_icd11_codes"]

            overlap = set_overlap(predicted[:top_k], expected)
            row = {
                "id": gid,
                "expected": ",".join(expected),
                "predicted_top5": ",".join(predicted[:5]),
                "hit@5": hit_rate_at_k(predicted, expected, k=5),
                "hit@10": hit_rate_at_k(predicted, expected, k=10),
                "mrr": mrr(predicted, expected),
                "f1": overlap["f1"],  # set_overlap returns dict {precision, recall, f1}
            }
            rows.append(row)
            hit5 = "Y" if row["hit@5"] == 1.0 else "n"
            top1 = predicted[0] if predicted else "-"
            print(f"[done] {gid}  hit@5={hit5}  top1={top1}  expected={expected[0] if expected else '-'}", flush=True)
        except Exception as exc:
            print(f"[fail] {gid}  {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            rows.append({
                "id": gid,
                "expected": ",".join(item.get("expected_icd11_codes", [])),
                "predicted_top5": "",
                "hit@5": 0.0,
                "hit@10": 0.0,
                "mrr": 0.0,
                "f1": 0.0,
                "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            })
        await asyncio.sleep(between_cases_s)

    summary = {
        "n":           len(rows),
        "hit_rate@5":  mean(r["hit@5"] for r in rows),
        "hit_rate@10": mean(r["hit@10"] for r in rows),
        "MRR":         mean(r["mrr"]    for r in rows),
        "mean_f1":     mean(r["f1"]     for r in rows),
    }
    print_summary("DDx (Stage 2) — throttled subsample", summary)
    write_results("ddx_throttled", rows, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20, help="how many gold items to evaluate (default 20)")
    parser.add_argument("--sleep", type=float, default=5.0, help="seconds to wait between cases (default 5.0)")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.sleep))
