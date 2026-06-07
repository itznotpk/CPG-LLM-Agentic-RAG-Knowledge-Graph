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
import csv
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
    "11": ("scripts.run_eval_case_11", "CASE_11"),
    "12": ("scripts.run_eval_case_12", "CASE_12"),
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


def _med_count(final: dict) -> int:
    plan = (final or {}).get("treatment_plan") or {}
    n = 0
    for r in plan.get("recommendations") or []:
        action = (r.get("action") or "").upper()
        if action in {"START", "CONTINUE", "SWITCH", "ADJUST"} and (r.get("intervention") or "").strip():
            n += 1
    return n


def _referral_count(final: dict) -> int:
    plan = (final or {}).get("treatment_plan") or {}
    return len(plan.get("referrals") or [])


def _safety_flag_set(final: dict) -> list[str]:
    sr = (final or {}).get("safety_report") or {}
    flags = sr.get("flags") or []
    out = []
    for f in flags:
        cat = (f.get("category") or f.get("type") or "").strip().lower()
        if cat:
            out.append(cat)
    return sorted(set(out))


def _plan_text_tokens(final: dict) -> set[str]:
    plan = (final or {}).get("treatment_plan") or {}
    parts: list[str] = []
    for r in plan.get("recommendations") or []:
        parts.append(str(r.get("intervention") or ""))
        parts.append(str(r.get("rationale") or ""))
    for r in plan.get("referrals") or []:
        parts.append(str(r.get("specialty") or ""))
        parts.append(str(r.get("reason") or ""))
    blob = " ".join(parts).lower()
    return {t for t in blob.split() if t.isalpha() and len(t) > 2}


def _aggregate_extras(runs: list[dict]) -> dict:
    med_counts = [_med_count(r["final"]) for r in runs]
    ref_counts = [_referral_count(r["final"]) for r in runs]
    flag_sets = [_safety_flag_set(r["final"]) for r in runs]
    text_tokens = [_plan_text_tokens(r["final"]) for r in runs]

    def _stat(xs):
        if not xs:
            return {"mean": 0.0, "stdev": 0.0}
        return {
            "mean": round(statistics.fmean(xs), 2),
            "stdev": round(statistics.stdev(xs), 2) if len(xs) >= 2 else 0.0,
        }

    flag_jaccard = (
        statistics.fmean(
            [_jaccard(a, b) for a, b in itertools.combinations(flag_sets, 2)]
        )
        if len(flag_sets) >= 2 else 1.0
    )
    text_jaccard = (
        statistics.fmean(
            [
                (len(a & b) / len(a | b)) if (a | b) else 1.0
                for a, b in itertools.combinations(text_tokens, 2)
            ]
        )
        if len(text_tokens) >= 2 else 1.0
    )

    return {
        "med_count": _stat(med_counts),
        "referral_count": _stat(ref_counts),
        "safety_flag_jaccard_mean": round(flag_jaccard, 3),
        "plan_text_jaccard_mean": round(text_jaccard, 3),
    }


def _write_csv_summary(csv_path: Path, rows: list[dict]) -> None:
    cols = [
        "case_id", "n_runs",
        "top1_stable", "top1_value",
        "top3_jaccard", "top5_jaccard",
        "same_plan_rate", "plan_text_jaccard",
        "med_count_mean", "med_count_stdev",
        "referral_count_mean", "referral_count_stdev",
        "safety_flag_jaccard",
        "wall_mean_s", "wall_stdev_s", "wall_min_s", "wall_max_s",
        "overall_pass",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})


async def _run_one_case(case_id: str, n: int, url: str, expected: list[str]) -> dict:
    case, stream_case = _load_case_runner(case_id)
    print(f"\n[stability] === case={case_id} n={n} url={url} expected={expected or '(none)'} ===")
    runs: list[dict] = []
    skipped: list[dict] = []
    for i in range(1, n + 1):
        print(f"[stability] case {case_id} run {i}/{n} starting …")
        t0 = time.monotonic()
        try:
            _events, final = await stream_case(url)
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"[stability] case {case_id} run {i} FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc} — skipping run")
            skipped.append({"run": i, "error": f"{type(exc).__name__}: {exc}", "elapsed": elapsed})
            continue
        elapsed = time.monotonic() - t0
        if not final:
            print(f"[stability] case {case_id} run {i} returned no final_result — skipping run")
            skipped.append({"run": i, "error": "no_final_result", "elapsed": elapsed})
            continue
        top5 = _top_codes(final, 5)
        print(f"[stability] case {case_id} run {i} OK in {elapsed:.1f}s top5={top5}")
        runs.append({"run": i, "wall_seconds": elapsed, "top5": top5, "final": final})

    if not runs:
        print(f"[stability] case {case_id}: all runs failed — no metrics")
        return {"case_id": case_id, "error": "all_runs_failed", "skipped": skipped}

    metrics = _compute_metrics(runs, expected)
    extras = _aggregate_extras(runs)
    gate = _pass_fail(metrics, expected)

    top1_values = metrics["top1_stability"]["values"]
    wt = metrics["wall_time_seconds"]
    summary_row = {
        "case_id": case_id,
        "n_runs": metrics["n_runs"],
        "top1_stable": metrics["top1_stability"]["stable"],
        "top1_value": top1_values[0] if top1_values and metrics["top1_stability"]["stable"] else "/".join(sorted(set(top1_values))),
        "top3_jaccard": metrics["top3_jaccard_mean"],
        "top5_jaccard": metrics["top5_jaccard_mean"],
        "same_plan_rate": metrics["same_plan_rate"],
        "plan_text_jaccard": extras["plan_text_jaccard_mean"],
        "med_count_mean": extras["med_count"]["mean"],
        "med_count_stdev": extras["med_count"]["stdev"],
        "referral_count_mean": extras["referral_count"]["mean"],
        "referral_count_stdev": extras["referral_count"]["stdev"],
        "safety_flag_jaccard": extras["safety_flag_jaccard_mean"],
        "wall_mean_s": wt["mean"],
        "wall_stdev_s": wt["stdev"],
        "wall_min_s": wt["min"],
        "wall_max_s": wt["max"],
        "overall_pass": gate["overall_pass"],
    }

    return {
        "case_id": case_id,
        "case_chief_complaint": case.get("chief_complaint"),
        "n_runs": n,
        "url": url,
        "expected_codes": expected,
        "metrics": metrics,
        "extras": extras,
        "gate": gate,
        "per_run_top5": [r["top5"] for r in runs],
        "per_run_wall_seconds": [r["wall_seconds"] for r in runs],
        "skipped_runs": skipped,
        "summary_row": summary_row,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default=None, choices=sorted(CASE_RUNNERS, key=int),
                        help="Single case (legacy). Use --cases for multi-case.")
    parser.add_argument("--cases", default=None,
                        help="Comma-separated list of cases, e.g. 8,9,10. Overrides --case.")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--url", default="http://localhost:8058")
    parser.add_argument("--expected", default="",
                        help="Comma-separated ICD codes required in top-5 every run (single-case mode only).")
    args = parser.parse_args()

    if args.cases:
        case_ids = [c.strip() for c in args.cases.split(",") if c.strip()]
        for c in case_ids:
            if c not in CASE_RUNNERS:
                raise SystemExit(f"unknown case in --cases: {c!r}")
    else:
        case_ids = [args.case or "9"]

    expected = [c.strip().upper() for c in args.expected.split(",") if c.strip()]
    if expected and len(case_ids) > 1:
        print("[stability] warning: --expected only applied to first case in multi-case run")

    url = args.url.rstrip("/")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_reports = []
    summary_rows = []
    for idx, cid in enumerate(case_ids):
        exp = expected if idx == 0 else []
        try:
            rep = await _run_one_case(cid, args.n, url, exp)
        except Exception as exc:
            print(f"[stability] case {cid} crashed: {type(exc).__name__}: {exc} — continuing to next case")
            rep = {"case_id": cid, "error": f"{type(exc).__name__}: {exc}"}
        all_reports.append(rep)
        if "summary_row" in rep:
            summary_rows.append(rep["summary_row"])

        out_path = OUT_DIR / f"stability_case{cid}_{stamp}.json"
        out_path.write_text(json.dumps(rep, indent=2), encoding="utf-8")
        print(f"[stability] wrote {out_path}")

    if len(case_ids) > 1:
        csv_path = OUT_DIR / f"stability_summary_{stamp}.csv"
        json_path = OUT_DIR / f"stability_summary_{stamp}.json"
        _write_csv_summary(csv_path, summary_rows)
        json_path.write_text(json.dumps({"cases": all_reports, "generated_at": datetime.now().isoformat(timespec="seconds")}, indent=2), encoding="utf-8")
        print(f"\n[stability] aggregate CSV: {csv_path}")
        print(f"[stability] aggregate JSON: {json_path}")

    print("\n=== STABILITY SUMMARY ===")
    print(f"{'case':<6}{'top1':<8}{'top3J':<8}{'top5J':<8}{'planJ':<8}{'samePR':<8}{'meds(m+/-s)':<14}{'refs(m+/-s)':<14}{'wall(s)':<14}{'PASS':<6}")
    for r in summary_rows:
        meds = f"{r['med_count_mean']}+/-{r['med_count_stdev']}"
        refs = f"{r['referral_count_mean']}+/-{r['referral_count_stdev']}"
        wall = f"{r['wall_mean_s']}+/-{r['wall_stdev_s']}"
        print(f"{r['case_id']:<6}{str(r['top1_stable']):<8}{r['top3_jaccard']:<8}{r['top5_jaccard']:<8}{r['plan_text_jaccard']:<8}{r['same_plan_rate']:<8}{meds:<14}{refs:<14}{wall:<10}{str(r['overall_pass']):<6}")

    overall = all(r["overall_pass"] for r in summary_rows) if summary_rows else False
    return 0 if overall else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
