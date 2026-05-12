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

from agent.clinical_stages import stage_2_ddx
from agent.models import PatientCase

from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import hit_rate_at_k, mrr, set_overlap, mean


async def main():
    gold = load_jsonl("ddx_gold.jsonl")
    rows = []
    for item in gold:
        case = PatientCase(chief_complaint=item["vignette"])
        top_k = item.get("expected_top_k", 10)
        # rerank=True matches production behaviour. Set False for a "retrieval-only" view.
        ddx_results = await stage_2_ddx(case, top_k=top_k, rerank=True)
        predicted = [d.code for d in ddx_results]
        expected = item["expected_icd11_codes"]
        overlap = set_overlap(predicted, expected)
        rows.append({
            "id": item["id"],
            "expected": ",".join(expected),
            "predicted_top5": ",".join(predicted[:5]),
            "hit@5": hit_rate_at_k(predicted, expected, k=5),
            "hit@10": hit_rate_at_k(predicted, expected, k=10),
            "mrr": mrr(predicted, expected),
            "f1": overlap["f1"],
        })

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
