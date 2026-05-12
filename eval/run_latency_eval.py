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
import time

from agent.clinical_stages import stage_2_ddx, stage_3_route, stage_4_retrieve, stage_5_synthesize

from eval._helpers import to_patient_case
from eval.io_utils import load_jsonl, write_results, print_summary


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
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    ddx = await stage_2_ddx(case, top_k=5)
    timings["stage2_ddx_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    cpgs = await stage_3_route(ddx)
    timings["stage3_route_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    evidence = await stage_4_retrieve(case, ddx, cpgs)
    timings["stage4_retrieve_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    await stage_5_synthesize(case, ddx, cpgs, evidence)
    timings["stage5_synth_ms"] = (time.perf_counter() - t0) * 1000

    timings["total_ms"] = sum(timings.values())
    return timings


async def main():
    gold = load_jsonl("clinical_qa_gold.jsonl")
    rows = []
    for item in gold:
        case = to_patient_case(item["patient_case"])
        try:
            t = await time_pipeline(case)
            rows.append({"id": item["id"], **t})
        except Exception as exc:
            print(f"[warn] {item['id']} failed: {exc}")

    if not rows:
        print("no rows — aborting")
        return

    summary: dict[str, float | int] = {"n": len(rows)}
    for key in ("stage2_ddx_ms", "stage3_route_ms", "stage4_retrieve_ms", "stage5_synth_ms", "total_ms"):
        pcts = percentiles([r[key] for r in rows])
        for pn, pv in pcts.items():
            summary[f"{key}_{pn}"] = pv

    print_summary("Latency / Cost", summary)
    write_results("latency", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
