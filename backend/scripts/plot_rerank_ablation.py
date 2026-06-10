"""
Figure 4.7 — Layer C category-boost re-ranker ablation (boost-off vs boost-on).

Reads the CANONICAL stored eval result
(eval/results/stage4_rerank_ablation_20260604_181825.json) and renders the
two-panel figure described in report §4.3.2.4. It does NOT re-run the eval: the
figure is drawn straight from the on-disk run that Table 4.10 cites, so the
chart, the table, and the text all trace to the same run and cannot drift.

  Left:  per-case nDCG@10 (boost-off vs boost-on) for all 5 cases, with the
         per-case lift annotated — the "identical pool, only ordering differs"
         visual that isolates the re-ranker.
  Right: mean nDCG@10 and MRR (off vs on) with the +6.0% / +10.0% lift called
         out — the net-positive summary.

Run:  cd backend; python scripts/plot_rerank_ablation.py
Out:  docs/report/figures/figure_4_7_rerank_ablation.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "eval" / "results" / "stage4_rerank_ablation_20260604_181825.json"
OUT = ROOT / "docs" / "report" / "figures" / "figure_4_7_rerank_ablation.png"

OFF = "#6c757d"     # boost off — raw vector order
ON = "#3b6ea5"      # boost on — category-boosted order
WIN = "#2e7d32"
LOSS = "#c0392b"

LABELS = {
    "mc_008": "mc_008\nHFrEF+T2DM+Obesity",
    "mc_010": "mc_010\nHTN-preg+GDM",
    "mc_011": "mc_011\nCAD+T2DM+ED",
    "mc_005": "mc_005\nHTN+T2DM+proteinuria",
    "mc_025": "mc_025\nED+T2DM+HTN",
}


def load():
    d = json.loads(SRC.read_text())
    return d["summary"], d["rows"]


def panel_percase(ax, rows):
    ids = [r["id"] for r in rows]
    off = [r["ndcg@10_off"] for r in rows]
    on = [r["ndcg@10_on"] for r in rows]
    lifts = [r["ndcg@10_lift"] for r in rows]

    x = range(len(ids))
    w = 0.38
    ax.bar([i - w / 2 for i in x], off, w, color=OFF, label="boost off (raw vector)")
    ax.bar([i + w / 2 for i in x], on, w, color=ON, label="boost on (category-boosted)")

    for i, (o, n, d) in enumerate(zip(off, on, lifts)):
        top = max(o, n)
        col = WIN if d > 0 else LOSS
        ax.text(i, top + 0.03, f"{d:+.3f}", ha="center", va="bottom",
                fontsize=8.5, fontweight="bold", color=col)

    ax.set_xticks(list(x))
    ax.set_xticklabels([LABELS[i] for i in ids], fontsize=8)
    ax.set_ylim(0, 0.78)
    ax.set_ylabel("nDCG@10")
    ax.set_title("Per-case lift on an identical pool (n = 5)", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right", fontsize=8.5, frameon=False)


def panel_mean(ax, s):
    groups = ["nDCG@10", "MRR"]
    off = [s["nDCG@10_boost_off"], s["MRR_boost_off"]]
    on = [s["nDCG@10_boost_on"], s["MRR_boost_on"]]
    lifts = [s["mean_nDCG@10_lift"], s["mean_MRR_lift"]]

    x = range(len(groups))
    w = 0.38
    b1 = ax.bar([i - w / 2 for i in x], off, w, color=OFF, label="boost off")
    b2 = ax.bar([i + w / 2 for i in x], on, w, color=ON, label="boost on")

    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.012,
                    f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=9)

    for i, d in enumerate(lifts):
        ax.text(i, max(off[i], on[i]) + 0.07, f"{d * 100:+.1f}%", ha="center", va="bottom",
                fontsize=11, fontweight="bold", color=WIN)

    ax.set_xticks(list(x))
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("mean score")
    ax.set_title("Mean lift — net positive", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", fontsize=9, frameon=False)


def main():
    s, rows = load()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.55, 1]})
    panel_percase(ax1, rows)
    panel_mean(ax2, s)

    fig.suptitle("Figure 4.7 — Layer C re-ranker: the category boost lifts ordering on an identical pool (+6.0% nDCG@10, +10.0% MRR)",
                 fontsize=12.5, fontweight="bold", y=1.0)
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"mean nDCG@10: {s['nDCG@10_boost_off']:.3f} -> {s['nDCG@10_boost_on']:.3f} "
          f"({s['mean_nDCG@10_lift'] * 100:+.1f}%); MRR {s['MRR_boost_off']:.2f} -> {s['MRR_boost_on']:.2f} "
          f"({s['mean_MRR_lift'] * 100:+.1f}%)")


if __name__ == "__main__":
    main()
