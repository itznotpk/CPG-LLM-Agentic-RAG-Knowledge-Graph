"""
Figure 4.12 — Reproducibility / determinism panel (n = 10 replays per case).

Three small multiples, all read live from the on-disk stability captures so the
figure cannot drift from Table 4.18:
  (a) grouped bar of top-1 stability (family) and top-5 Jaccard (exact vs family)
      per case — cases 8/9 stable, case 10 flipping;
  (b) the case-10 pairwise top-5 Jaccard heatmap (10x10) visualising run-to-run
      churn on the near-tied obstetric case;
  (c) substance-vs-prose bar contrasting the stable safety-flag layer (Jaccard 1.0)
      with the variable plan-text Jaccard — why same-plan rate is the wrong metric.

Sources (the n=10 captures matching Table 4.18):
  case 8  : tasks/eval_runs/stability_case8_20260605_035748.json
  case 9  : backend/tasks/eval_runs/stability_case9_20260605_194430.json
  case 10 : backend/tasks/eval_runs/stability_case10_20260605_200903.json

Run:  cd backend; python scripts/plot_reproducibility.py
Out:  docs/report/figures/figure_4_12_reproducibility.png
"""
from __future__ import annotations

import itertools
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]               # backend/
REPO = ROOT.parent                                       # CPG LLM/
OUT = REPO / "docs" / "report" / "figures" / "figure_4_12_reproducibility.png"

FILES = {
    "8": REPO / "tasks" / "eval_runs" / "stability_case8_20260605_035748.json",
    "9": ROOT / "tasks" / "eval_runs" / "stability_case9_20260605_194430.json",
    "10": ROOT / "tasks" / "eval_runs" / "stability_case10_20260605_200903.json",
}
LABELS = {"8": "Case 8\nT2DM+HFrEF", "9": "Case 9\nAF+Post-PCI", "10": "Case 10\nHTN-preg+GDM"}

STABLE = "#2e7d32"
MID = "#f39c12"
WEAK = "#c0392b"
PROSE = "#7f8c8d"


def _jac(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 1.0


def _family(codes):
    return [c.split(".")[0] for c in codes]


def _pairwise_mean(runs, fam=False) -> float:
    if fam:
        runs = [_family(r) for r in runs]
    ps = [_jac(runs[i], runs[j]) for i, j in itertools.combinations(range(len(runs)), 2)]
    return statistics.mean(ps) if ps else 1.0


def _top1_family_stability(d) -> float:
    vals = [_family([c])[0] for c in d["metrics"]["top1_stability"]["values"]]
    n = len(vals)
    modal = max(set(vals), key=vals.count)
    return vals.count(modal) / n


def main():
    data = {c: json.loads(p.read_text()) for c, p in FILES.items()}

    fig, (axA, axB, axC) = plt.subplots(1, 3, figsize=(15, 4.6))

    # ---- (a) grouped bar: top-1 family stability, exact top-5 J, family top-5 J ----
    cases = ["8", "9", "10"]
    top1 = [_top1_family_stability(data[c]) for c in cases]
    exactJ = [data[c]["metrics"]["top5_jaccard_mean"] for c in cases]
    famJ = [_pairwise_mean(data[c]["per_run_top5"], fam=True) for c in cases]

    x = np.arange(len(cases))
    w = 0.26
    axA.bar(x - w, top1, w, label="Top-1 stability (family)", color=STABLE)
    axA.bar(x, exactJ, w, label="Top-5 Jaccard (exact)", color=MID)
    axA.bar(x + w, famJ, w, label="Top-5 Jaccard (family)", color="#2980b9")
    for xi, vals in zip(x, zip(top1, exactJ, famJ)):
        for off, v in zip((-w, 0, w), vals):
            axA.text(xi + off, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5)
    axA.set_xticks(x)
    axA.set_xticklabels([LABELS[c] for c in cases], fontsize=8.5)
    axA.set_ylim(0, 1.12)
    axA.set_ylabel("rate / mean Jaccard")
    axA.set_title("Figure 4.12a — Stability across n = 10 replays", fontsize=10.5, fontweight="bold")
    axA.legend(fontsize=7.6, loc="lower left")
    axA.grid(axis="y", alpha=0.25)

    # ---- (b) case-10 pairwise top-5 Jaccard heatmap (10x10) ----
    runs10 = data["10"]["per_run_top5"]
    n = len(runs10)
    mat = np.array([[_jac(runs10[i], runs10[j]) for j in range(n)] for i in range(n)])
    im = axB.imshow(mat, cmap="RdYlGn", vmin=0, vmax=1)
    axB.set_xticks(range(n)); axB.set_yticks(range(n))
    axB.set_xticklabels(range(1, n + 1), fontsize=7)
    axB.set_yticklabels(range(1, n + 1), fontsize=7)
    axB.set_xlabel("run"); axB.set_ylabel("run")
    axB.set_title("Figure 4.12b — Case 10 pairwise top-5 Jaccard\n(near-tied obstetric differential churns)",
                  fontsize=10.5, fontweight="bold")
    for i in range(n):
        for j in range(n):
            axB.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center",
                     fontsize=6, color="#222222")
    fig.colorbar(im, ax=axB, fraction=0.046, pad=0.04)

    # ---- (c) substance-vs-prose: safety-flag J vs plan-text J ----
    safe = [data[c].get("summary_row", {}).get("safety_flag_jaccard",
            data[c].get("extras", {}).get("safety_flag_jaccard_mean", 1.0)) for c in cases]
    prose = [data[c].get("summary_row", {}).get("plan_text_jaccard",
             data[c].get("extras", {}).get("plan_text_jaccard_mean", 0.0)) for c in cases]
    xc = np.arange(len(cases))
    wc = 0.34
    axC.bar(xc - wc / 2, safe, wc, label="Safety-flag set (substance)", color=STABLE)
    axC.bar(xc + wc / 2, prose, wc, label="Plan text (prose)", color=PROSE)
    for xi, s, p in zip(xc, safe, prose):
        axC.text(xi - wc / 2, s + 0.02, f"{s:.2f}", ha="center", va="bottom", fontsize=7.5)
        axC.text(xi + wc / 2, p + 0.02, f"{p:.2f}", ha="center", va="bottom", fontsize=7.5)
    axC.set_xticks(xc)
    axC.set_xticklabels([LABELS[c] for c in cases], fontsize=8.5)
    axC.set_ylim(0, 1.12)
    axC.set_ylabel("mean Jaccard")
    axC.set_title("Figure 4.12c — Substance is stable where prose is not", fontsize=10.5, fontweight="bold")
    axC.legend(fontsize=7.6, loc="upper right")
    axC.grid(axis="y", alpha=0.25)

    fig.suptitle(
        "Figure 4.12 — Reproducibility: determinism holds at top-1 where a dominant diagnosis exists; "
        "residual churn isolates to the near-tied case 10",
        fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"top1(family) {dict(zip(cases, [round(v,3) for v in top1]))}")
    print(f"exactJ {dict(zip(cases, exactJ))}  famJ {dict(zip(cases, [round(v,3) for v in famJ]))}")
    print(f"safeJ {dict(zip(cases, safe))}  proseJ {dict(zip(cases, prose))}")


if __name__ == "__main__":
    main()
