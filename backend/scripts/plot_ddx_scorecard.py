"""
Figure 4.4 — Layer A1 DDx three-granularity scorecard.

Reads the CANONICAL stored eval result (eval/results/ddx_20260602_194144.json) and
renders the two-panel figure described in report §4.3.2.1. It does NOT re-run the
eval: the figure is drawn straight from the on-disk run that Table 4.4 cites, so the
chart, the table, and the text all trace to the same run and cannot drift.

  Left:  grouped bars of Hit@5 and MRR at exact / lineage / graded, with the
         >=0.90 (Hit) and >=0.70 (MRR) target lines overlaid — lineage clears the
         bar, exact sits below it.
  Right: the 8 exact-misses split into lineage hits (correct family, wrong leaf)
         and the lone true miss (ddx_011), classified live from the row data.

Run:  cd backend; python scripts/plot_ddx_scorecard.py
Out:  docs/report/figures/figure_4_4_ddx_scorecard.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "eval" / "results" / "ddx_20260602_194144.json"
OUT = ROOT / "docs" / "report" / "figures" / "figure_4_4_ddx_scorecard.png"

EXACT = "#6c757d"   # strict / conservative
LINEAGE = "#3b6ea5"  # clinically-meaningful headline
GRADED = "#7aa6c2"   # partial-credit blend
HIT_GREEN = "#2e7d32"
MISS_RED = "#c0392b"
TARGET = "#444444"


def load():
    d = json.loads(SRC.read_text())
    return d["summary"], d["rows"]


def classify_exact_misses(rows):
    """Exact-misses (hit@5==0) split into lineage hits vs true misses, from row data."""
    lineage_hits, true_misses = [], []
    for r in rows:
        if r["hit@5"] == 0:
            (lineage_hits if r["lin_hit@5"] == 1 else true_misses).append(r["id"])
    return lineage_hits, true_misses


def panel_scores(ax, s):
    # Two metric groups; exact + lineage in both, graded only defined @5 (Hit).
    groups = ["Hit@5", "MRR"]
    x = range(len(groups))
    w = 0.26
    exact = [s["hit_rate@5"], s["MRR"]]
    lineage = [s["lin_hit_rate@5"], s["lin_MRR"]]
    graded = [s["graded@5"], None]

    b1 = ax.bar([i - w for i in x], exact, w, label="exact", color=EXACT)
    b2 = ax.bar(list(x), lineage, w, label="lineage", color=LINEAGE)
    b3 = ax.bar([i + w for i in x if graded[i] is not None], [graded[0]], w,
                label="graded@5", color=GRADED)

    ax.axhline(0.90, ls="--", lw=1, color=TARGET)
    ax.axhline(0.70, ls=":", lw=1, color=TARGET)
    ax.text(1.46, 0.905, "Hit@5 target ≥ 0.90", fontsize=8, color=TARGET, va="bottom", ha="right")
    ax.text(1.46, 0.705, "MRR target ≥ 0.70", fontsize=8, color=TARGET, va="bottom", ha="right")

    for bars in (b1, b2, b3):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.012,
                    f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=8.5)

    ax.set_xticks(list(x))
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("score")
    ax.set_title("Accuracy by match granularity (n = 35)", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", fontsize=9, frameon=False)


def panel_misses(ax, lineage_hits, true_misses):
    nl, nt = len(lineage_hits), len(true_misses)
    ax.barh([0], [nl], color=HIT_GREEN, label=f"lineage hit — correct family, wrong leaf ({nl})")
    ax.barh([0], [nt], left=[nl], color=MISS_RED,
            label=f"true family miss — {', '.join(true_misses)} ({nt})")

    ax.text(nl / 2, 0, str(nl), ha="center", va="center", color="white", fontsize=12, fontweight="bold")
    ax.text(nl + nt / 2, 0, str(nt), ha="center", va="center", color="white", fontsize=12, fontweight="bold")

    ax.set_xlim(0, nl + nt)
    ax.set_yticks([])
    ax.set_xlabel(f"the {nl + nt} exact-misses")
    ax.set_title("Where the exact-match gap comes from", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.55), fontsize=9, frameon=False)


def main():
    s, rows = load()
    lineage_hits, true_misses = classify_exact_misses(rows)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.35, 1]})
    panel_scores(ax1, s)
    panel_misses(ax2, lineage_hits, true_misses)

    fig.suptitle("Figure 4.4 — Layer A1 DDx scorecard: lineage clears the bar; the exact gap is leaf-specificity",
                 fontsize=12.5, fontweight="bold", y=1.0)
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"exact-misses: {len(lineage_hits) + len(true_misses)} "
          f"({len(lineage_hits)} lineage, {len(true_misses)} true: {true_misses})")


if __name__ == "__main__":
    main()
