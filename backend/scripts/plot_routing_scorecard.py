"""
Figure 4.5 — Layer A2 routing scorecard.

Reads the CANONICAL stored eval result (eval/results/routing_20260602_134121.json)
and renders the two-panel figure described in report §4.3.2.2. It does NOT re-run
the eval: the figure is drawn straight from the on-disk run that Table 4.7 cites,
so the chart, the table, and the text all trace to the same run and cannot drift.

  Left:  Top-1 and Hit@3 accuracy (both 1.000) with the >=0.85 and >=0.95 target
         lines overlaid — both metrics clear the bar.
  Right: stacked bar of how the 44 codes resolved — 39 exact + the 5-code
         fallback tail (sibling / ancestor_d1 / semantic_scope), classified live
         from the row data.

Run:  cd backend; python scripts/plot_routing_scorecard.py
Out:  docs/report/figures/figure_4_5_routing_scorecard.png
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "eval" / "results" / "routing_20260602_134121.json"
OUT = ROOT / "docs" / "report" / "figures" / "figure_4_5_routing_scorecard.png"

METRIC = "#2e7d32"   # achieved accuracy bars
EXACT = "#3b6ea5"    # D1 exact scope match
SIBLING = "#6c9bc4"
ANCESTOR = "#8db8d8"
SEMANTIC = "#b9d3e8"
TARGET = "#444444"

FALLBACK_COLORS = {"sibling": SIBLING, "ancestor_d1": ANCESTOR, "semantic_scope": SEMANTIC}
FALLBACK_LABELS = {
    "sibling": "sibling",
    "ancestor_d1": "ancestor (D1)",
    "semantic_scope": "semantic scope",
}


def load():
    d = json.loads(SRC.read_text())
    return d["summary"], d["rows"]


def match_type_counts(rows):
    """Ordered: exact first, then the fallback tiers as they appear."""
    c = collections.Counter(r["match_type"] for r in rows)
    return c


def panel_targets(ax, s):
    labels = ["Top-1\naccuracy", "Hit@3"]
    vals = [s["top1_accuracy"], s["hit_rate@3"]]
    bars = ax.bar(labels, vals, width=0.5, color=METRIC)

    ax.axhline(0.85, ls="--", lw=1, color=TARGET)
    ax.axhline(0.95, ls=":", lw=1, color=TARGET)
    ax.text(1.46, 0.855, "Top-1 target ≥ 0.85", fontsize=8, color=TARGET, va="bottom", ha="right")
    ax.text(1.46, 0.955, "Hit@3 target ≥ 0.95", fontsize=8, color=TARGET, va="bottom", ha="right")

    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015,
                f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylim(0, 1.12)
    ax.set_ylabel("routing accuracy")
    ax.set_title("Accuracy against target (n = 44)", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)


def panel_matchtypes(ax, counts):
    n_exact = counts.get("exact", 0)
    fallbacks = [(k, counts[k]) for k in ("sibling", "ancestor_d1", "semantic_scope") if counts.get(k)]
    total = n_exact + sum(v for _, v in fallbacks)

    left = 0
    seg = ax.barh([0], [n_exact], left=[left], color=EXACT, label=f"exact D1 scope ({n_exact})")
    ax.text(n_exact / 2, 0, str(n_exact), ha="center", va="center", color="white",
            fontsize=12, fontweight="bold")
    left += n_exact

    for k, v in fallbacks:
        ax.barh([0], [v], left=[left], color=FALLBACK_COLORS[k], label=f"{FALLBACK_LABELS[k]} ({v})")
        ax.text(left + v / 2, 0, str(v), ha="center", va="center", color="#1b3a52",
                fontsize=10, fontweight="bold")
        left += v

    ax.set_xlim(0, total)
    ax.set_yticks([])
    ax.set_xlabel(f"all {total} ICD codes — every one lands the correct CPG")
    ax.set_title("How each code resolved (the D1–D2 ladder)", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.55), ncol=2, fontsize=9, frameon=False)


def main():
    s, rows = load()
    counts = match_type_counts(rows)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.35]})
    panel_targets(ax1, s)
    panel_matchtypes(ax2, counts)

    fig.suptitle("Figure 4.5 — Layer A2 routing: the ladder routes 44/44, clearing both targets",
                 fontsize=12.5, fontweight="bold", y=1.0)
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"match_type: {dict(counts)} (total {sum(counts.values())})")


if __name__ == "__main__":
    main()
