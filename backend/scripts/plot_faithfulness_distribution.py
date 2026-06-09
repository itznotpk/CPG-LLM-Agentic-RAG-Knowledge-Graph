"""
Figure 4.9 — Layer D synthesis-faithfulness distribution (n = 30, independent judge).

Reads the CANONICAL stored eval result
(eval/results/faithfulness_20260605_003723.json) and renders the per-case
faithfulness distribution described in report §4.3.3. It does NOT re-run the
eval: the figure is drawn straight from the on-disk run that Table 4.13 cites,
so the chart, the table, and the text all trace to the same run and cannot drift.

  A sorted per-case bar chart of all 30 plans' faithfulness scores with the mean
  (0.864) and the >=0.90 target drawn as horizontal lines. The worst three
  (qa_027/016/012) are flagged red, the four perfect plans (1.00) green, the rest
  blue. This is the standard "score distribution vs target" diagnostic.

Run:  cd backend; python scripts/plot_faithfulness_distribution.py
Out:  docs/report/figures/figure_4_9_faithfulness_distribution.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "eval" / "results" / "faithfulness_20260605_003723.json"
OUT = ROOT / "docs" / "report" / "figures" / "figure_4_9_faithfulness_distribution.png"

TARGET = 0.90
BAR = "#3b6ea5"      # plan faithfulness
PERFECT = "#2e7d32"  # 1.00 plans
WORST = "#c0392b"    # worst-3 triage targets
MEANC = "#444444"
TARGETC = "#c0392b"


def load():
    d = json.loads(SRC.read_text())
    return d["summary"], d["rows"]


def main():
    s, rows = load()
    rows = sorted(rows, key=lambda r: r["faithfulness"])
    n = len(rows)
    mean = s["mean_faithfulness"]

    ids = [r["id"] for r in rows]
    vals = [r["faithfulness"] for r in rows]
    worst3 = set(ids[:3])

    colors = [
        WORST if i in worst3 else (PERFECT if v >= 0.999 else BAR)
        for i, v in zip(ids, vals)
    ]

    fig, ax = plt.subplots(figsize=(13, 5.2))
    x = range(n)
    ax.bar(x, vals, width=0.74, color=colors)

    # reference lines
    ax.axhline(TARGET, ls="--", lw=1.4, color=TARGETC, zorder=4)
    ax.text(n - 0.4, TARGET + 0.008, f"target ≥ {TARGET:.2f}", fontsize=9,
            color=TARGETC, va="bottom", ha="right", fontweight="bold")
    ax.axhline(mean, ls=":", lw=1.4, color=MEANC, zorder=4)
    ax.text(-0.4, mean - 0.008, f"mean {mean:.3f}", fontsize=9,
            color=MEANC, va="top", ha="left", fontweight="bold")

    # value labels on the worst three only (keep the rest clean)
    for i, (cid, v) in enumerate(zip(ids, vals)):
        if cid in worst3:
            ax.text(i, v + 0.012, f"{v:.2f}", ha="center", va="bottom",
                    fontsize=8.5, fontweight="bold", color=WORST)

    ax.set_xticks(list(x))
    ax.set_xticklabels(ids, rotation=90, fontsize=7.5)
    ax.set_ylim(0, 1.06)
    ax.set_ylabel("per-plan faithfulness (supported / total claims)")
    ax.set_xlabel("30 gold plans, sorted ascending")
    ax.spines[["top", "right"]].set_visible(False)

    # legend
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=PERFECT, label="perfect (1.00) — 4 plans"),
        Patch(color=BAR, label="grounded, below target"),
        Patch(color=WORST, label="worst 3 — triage targets"),
    ], loc="upper left", fontsize=9, frameon=False)

    fig.suptitle("Figure 4.9 — Layer D synthesis faithfulness: 0.864 mean over 30 plans (849/979 claims grounded), below the 0.90 target",
                 fontsize=12.5, fontweight="bold", y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"mean {mean:.3f}, n={n}, perfect={sum(1 for v in vals if v >= 0.999)}, "
          f"worst3={ids[:3]}")


if __name__ == "__main__":
    main()
