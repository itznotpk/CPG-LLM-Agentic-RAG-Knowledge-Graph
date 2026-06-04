"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Non-accuracy metrics  →  per-stage + end-to-end timing
═══════════════════════════════════════════════════════════════════════════════
Runs each stage of the pipeline manually with timestamps so you get a
per-stage latency breakdown — not just a total. Reports p50, p95, p99.

Use the SAME clinical_qa_gold.jsonl items as run_e2e_eval.py so latency and
accuracy numbers are directly comparable in your report.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import asyncio
import statistics

from agent.clinical_workflow import run_clinical_workflow

from eval._helpers import to_patient_case
from eval.io_utils import load_jsonl, write_results, print_summary

# Stage segments emitted by run_clinical_workflow.stage_timings, in pipeline order.
_STAGE_KEYS = [
    "stage_2_ddx",
    "stage_3_route",
    "stage_3_route_comorbidities",
    "stage_4_retrieve",
    "kg_lookup",
    "graph_navigator",
    "stage_5_synthesize",
    "stage_6_safety",
]


def percentiles(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    xs_sorted = sorted(xs)
    return {
        "p50": statistics.median(xs_sorted),
        "p95": xs_sorted[max(0, int(len(xs_sorted) * 0.95) - 1)],
        "p99": xs_sorted[max(0, int(len(xs_sorted) * 0.99) - 1)],
    }


async def time_pipeline(case) -> dict[str, float]:
    """Run the full workflow and pull its per-stage breakdown.

    Uses run_clinical_workflow so the timing covers the SAME path a real request
    takes — including KG lookup, graph navigator, comorbidity routing, and the
    Stage 6 safety review, which the old stage-2-to-5 timing missed entirely.
    """
    result = await run_clinical_workflow(case)
    timings: dict[str, float] = {
        f"{key}_ms": result.stage_timings.get(key, 0.0) for key in _STAGE_KEYS
    }
    timings["total_ms"] = result.elapsed_ms
    return timings


async def main(limit: int | None = None):
    gold = load_jsonl("clinical_qa_gold.jsonl")
    if limit is not None:
        gold = gold[:limit]
    rows = []
    for item in gold:
        case = to_patient_case(item["patient_case"])
        print(f"[run] {item['id']}…", flush=True)
        try:
            t = await time_pipeline(case)
            rows.append({"id": item["id"], **t})
            # Per-case breakdown so a single-case run gives an immediate answer.
            ordered = sorted(
                ((k, t[f"{k}_ms"]) for k in _STAGE_KEYS),
                key=lambda kv: kv[1], reverse=True,
            )
            print(f"[done] {item['id']} total={t['total_ms']:.0f}ms")
            for name, ms in ordered:
                pct = (ms / t["total_ms"] * 100) if t["total_ms"] else 0
                print(f"        {name:32s} {ms:8.0f}ms  ({pct:4.0f}%)")
        except Exception as exc:
            print(f"[warn] {item['id']} failed: {exc}")

    if not rows:
        print("no rows — aborting")
        return

    summary: dict[str, float | int] = {"n": len(rows)}
    for key in [f"{k}_ms" for k in _STAGE_KEYS] + ["total_ms"]:
        pcts = percentiles([r[key] for r in rows])
        for pn, pv in pcts.items():
            summary[f"{key}_{pn}"] = pv

    print_summary("Latency / Cost", summary)
    write_results("latency", rows, summary)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Run only the first N gold cases (e.g. --limit 1).")
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit))
