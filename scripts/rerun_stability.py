"""Reproducibility / determinism harness for the DDx pipeline.

Reruns one of the canned eval cases N times against the live API and reports
top-K stability metrics. Designed to be a Chapter-4-reportable artifact:
output is a single `stability_<case>_<stamp>.json` with the metric table
plus the raw per-run top-5 codes, so the report can cite numbers (and a
reviewer can audit the raw runs).

This measures **determinism**, not clinical correctness. Diagnostic
accuracy requires a clinician-annotated gold-standard set — out of scope.

Usage:
    # default: case 9, 10 reruns, http://localhost:8058
    python scripts/rerun_stability.py

    # specific case + count + endpoint
    python scripts/rerun_stability.py --case 8 --n 10 --url http://localhost:8000

    # declare which codes MUST appear in top-5 every run (e.g. case 9 fixture)
    python scripts/rerun_stability.py --case 9 --n 10 --expected BA41.1,5A11,BC81.3
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import itertools
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tasks" / "eval_runs"

# Map a CLI --case value to the module that already exposes (CASE_*, stream_case).
# Re-use the existing runners so we don't duplicate case fixtures.
CASE_RUNNERS: dict[str, tuple[str, str]] = {
    "8": ("scripts.run_eval_case_08", "CASE_8"),
    "9": ("scripts.run_eval_case_09", "CASE_9"),
    "10": ("scripts.run_eval_case_10", "CASE_10"),
}


def _load_case_runner(case_id: str):
    if case_id not in CASE_RUNNERS:
        raise SystemExit(f"unknown --case {case_id!r}; supported: {sorted(CASE_RUNNERS)}")
    mod_name, case_attr = CASE_RUNNERS[case_id]
    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module(mod_name)
    return getattr(mod, case_attr), mod.stream_case


def _top_codes(final: dict, k: int) -> list[str]:
    ddx = (final or {}).get("ddx") or []
    out: list[str] = []
    for d in ddx[:k]:
        code = (d.get("code") or d.get("icd_code") or "").strip().upper()
        if code:
            out.append(code)
    return out


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 1.0


def _pairwise_jaccard(sets: list[list[str]]) -> float:
    if len(sets) < 2:
        return 1.0
    scores = [_jaccard(a, b) for a, b in itertools.combinations(sets, 2)]
    return statistics.fmean(scores)


def _plan_signature(final: dict) -> str:
    """Stable string signature for the final TreatmentPlan — used for same-plan rate."""
    plan = (final or {}).get("treatment_plan") or {}
    recs = []
    for r in plan.get("recommendations") or []:
        recs.append(
            f"{(r.get('action') or '').upper()}|{(r.get('intervention') or '').strip().lower()}"
        )
    recs.sort()
    return f"{plan.get('icd_primary','')}::" + "::".join(recs)


def _compute_metrics(runs: list[dict], expected_codes: list[str]) -> dict:
    top1 = [_top_codes(r["final"], 1) for r in runs]
    top3 = [_top_codes(r["final"], 3) for r in runs]
    top5 = [_top_codes(r["final"], 5) for r in runs]

    top1_codes = [t[0] for t in top1 if t]
    top1_unique = len(set(top1_codes))
    top1_stable = (top1_unique == 1) if top1_codes else False

    presence: dict[str, float] = {}
    for code in expected_codes:
        c = code.strip().upper()
        if not c:
            continue
        hits = sum(1 for t in top5 if c in t)
        presence[c] = round(hits / len(top5), 3) if top5 else 0.0

    signatures = [_plan_signature(r["final"]) for r in runs]
    sig_counts: dict[str, int] = {}
    for s in signatures:
        sig_counts[s] = sig_counts.get(s, 0) + 1
    modal_count = max(sig_counts.values()) if sig_counts else 0
    same_plan_rate = round(modal_count / len(signatures), 3) if signatures else 0.0

    wall_times = [r["wall_seconds"] for r in runs]

    return {
        "n_runs": len(runs),
        "top1_stability": {
            "unique_top1_codes": top1_unique,
            "stable": top1_stable,
            "values": top1_codes,
        },
        "top3_jaccard_mean": round(_pairwise_jaccard(top3), 3),
        "top5_jaccard_mean": round(_pairwise_jaccard(top5), 3),
        "expected_code_presence_rate": presence,
        "same_plan_rate": same_plan_rate,
        "wall_time_seconds": {
            "mean": round(statistics.fmean(wall_times), 1) if wall_times else 0.0,
            "stdev": round(statistics.stdev(wall_times), 1) if len(wall_times) >= 2 else 0.0,
            "min": round(min(wall_times), 1) if wall_times else 0.0,
            "max": round(max(wall_times), 1) if wall_times else 0.0,
        },
    }


def _pass_fail(metrics: dict, expected_codes: list[str]) -> dict:
    """Default Chapter-4 pass thresholds. Override at report-writing time if needed."""
    checks = {
        "top1_stable (== 1 unique)": metrics["top1_stability"]["stable"],
        "top3_jaccard >= 0.95": metrics["top3_jaccard_mean"] >= 0.95,
        "top5_jaccard >= 0.90": metrics["top5_jaccard_mean"] >= 0.90,
        "same_plan_rate >= 0.80": metrics["same_plan_rate"] >= 0.80,
    }
    if expected_codes:
        for code, rate in metrics["expected_code_presence_rate"].items():
            checks[f"{code} present in 100% of runs"] = rate >= 1.0
    return {
        "checks": checks,
        "overall_pass": all(checks.values()),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="9", choices=sorted(CASE_RUNNERS, key=int))
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--url", default="http://localhost:8058")
    parser.add_argument("--expected", default="",
                        help="Comma-separated ICD codes required in top-5 every run (e.g. BA41.1,5A11,BC81.3)")
    args = parser.parse_args()

    case, stream_case = _load_case_runner(args.case)
    expected = [c.strip().upper() for c in args.expected.split(",") if c.strip()]
    url = args.url.rstrip("/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"stability_case{args.case}_{stamp}.json"

    print(f"[stability] case={args.case} n={args.n} url={url} expected={expected or '(none)'}")
    runs: list[dict] = []
    for i in range(1, args.n + 1):
        print(f"[stability] run {i}/{args.n} starting …")
        t0 = time.monotonic()
        _events, final = await stream_case(url)
        elapsed = time.monotonic() - t0
        if not final:
            print(f"[stability] run {i} returned no final_result — aborting batch")
            return 1
        top5 = _top_codes(final, 5)
        print(f"[stability] run {i} OK in {elapsed:.1f}s top5={top5}")
        runs.append({"run": i, "wall_seconds": elapsed, "top5": top5, "final": final})

    metrics = _compute_metrics(runs, expected)
    gate = _pass_fail(metrics, expected)

    report = {
        "case_id": args.case,
        "case_chief_complaint": case.get("chief_complaint"),
        "n_runs": args.n,
        "url": url,
        "expected_codes": expected,
        "metrics": metrics,
        "gate": gate,
        "per_run_top5": [r["top5"] for r in runs],
        "per_run_wall_seconds": [r["wall_seconds"] for r in runs],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== STABILITY REPORT ===")
    print(f"top-1 stable:        {metrics['top1_stability']['stable']} "
          f"(unique={metrics['top1_stability']['unique_top1_codes']})")
    print(f"top-3 jaccard mean:  {metrics['top3_jaccard_mean']}")
    print(f"top-5 jaccard mean:  {metrics['top5_jaccard_mean']}")
    print(f"same-plan rate:      {metrics['same_plan_rate']}")
    if expected:
        print("expected presence:")
        for code, rate in metrics["expected_code_presence_rate"].items():
            print(f"  {code}: {rate}")
    wt = metrics["wall_time_seconds"]
    print(f"wall time: mean={wt['mean']}s stdev={wt['stdev']}s min={wt['min']}s max={wt['max']}s")
    print(f"\noverall pass: {gate['overall_pass']}")
    for chk, ok in gate["checks"].items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {chk}")
    print(f"\nReport: {out_path}")
    return 0 if gate["overall_pass"] else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
