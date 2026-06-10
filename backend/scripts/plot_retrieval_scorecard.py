"""
Figure 4.6 — Layer B retrieval scorecard (vector vs RRF-hybrid).

Reads the two CANONICAL stored eval results
(eval/results/retrieval_vector_20260602_200110.json and
 eval/results/retrieval_hybrid_20260602_200834.json) and renders the two-panel
figure described in report §4.3.2.3. It does NOT re-run the eval: the figure is
drawn straight from the on-disk runs that Table 4.8 cites, so the chart, the
table, and the text all trace to the same runs and cannot drift.

  Left:  Recall@k (k = 5/10/20) for vector vs hybrid with the >=0.85 Recall@10
         target line — the overlapping curves are the "RRF ties vector" visual.
  Right: grouped bars of Precision@5 / MRR / nDCG@10 / Hit@10 for both
         retrievers, with the Precision@5 structural ceiling (computed live from
         the gold rows' n_relevant) and the >=0.75 ranking target drawn in.

Run:  cd backend; python scripts/plot_retrieval_scorecard.py
Out:  docs/report/figures/figure_4_6_retrieval_scorecard.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC_VEC = ROOT / "backend" / "eval" / "results" / "retrieval_vector_20260602_200110.json"
SRC_HYB = ROOT / "backend" / "eval" / "results" / "retrieval_hybrid_20260602_200834.json"
OUT = ROOT / "docs" / "report" / "figures" / "figure_4_6_retrieval_scorecard.png"

VECTOR = "#2e7d32"   # retained retriever
HYBRID = "#3b6ea5"   # RRF-hybrid
TARGET = "#444444"
CEILING = "#c0392b"  # structural precision ceiling


def load(path):
    d = json.loads(path.read_text())
    return d["summary"], d["rows"]


def precision_ceiling(rows, k=5):
    """Max achievable Precision@k given each row has only n_relevant chunks."""
    return sum(min(r["n_relevant"], k) for r in rows) / len(rows) / k


def panel_recall(ax, sv, sh):
    ks = [5, 10, 20]
    vec = [sv["recall@5"], sv["recall@10"], sv["recall@20"]]
    hyb = [sh["recall@5"], sh["recall@10"], sh["recall@20"]]

    ax.plot(ks, vec, "-o", color=VECTOR, lw=2, ms=7, label="vector")
    ax.plot(ks, hyb, "--s", color=HYBRID, lw=2, ms=6, label="hybrid (RRF)")

    ax.axhline(0.85, ls="--", lw=1, color=TARGET)
    ax.text(20, 0.857, "Recall@10 target ≥ 0.85", fontsize=8, color=TARGET, va="bottom", ha="right")

    for k, v in zip(ks, vec):
        ax.text(k, v + 0.012, f"{v:.3f}", ha="center", va="bottom", fontsize=8.5, color=VECTOR)

    ax.set_xticks(ks)
    ax.set_xticklabels([f"@{k}" for k in ks], fontsize=11)
    ax.set_ylim(0.6, 1.02)
    ax.set_xlabel("recall cut-off k")
    ax.set_ylabel("recall")
    ax.set_title("Recall@k — RRF ties vector (n = 148)", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", fontsize=9, frameon=False)


def panel_ranking(ax, sv, sh, p_ceiling):
    labels = ["Precision@5", "MRR", "nDCG@10", "Hit@10"]
    vec = [sv["precision@5"], sv["MRR"], sv["nDCG@10"], sv["hit_rate@10"]]
    hyb = [sh["precision@5"], sh["MRR"], sh["nDCG@10"], sh["hit_rate@10"]]

    x = range(len(labels))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], vec, w, color=VECTOR, label="vector")
    b2 = ax.bar([i + w / 2 for i in x], hyb, w, color=HYBRID, label="hybrid (RRF)")

    # split ranking targets: MRR >= 0.70, nDCG@10 >= 0.75 (per VALIDATION_RESULTS.md)
    ax.plot([0.5, 2.5], [0.70, 0.70], ls=":", lw=1, color=TARGET)
    ax.text(0.55, 0.707, "MRR target ≥ 0.70", fontsize=8, color=TARGET, va="bottom", ha="left")
    ax.plot([1.5, 3.5], [0.75, 0.75], ls="--", lw=1, color=TARGET)
    ax.text(3.45, 0.757, "nDCG@10 target ≥ 0.75", fontsize=8, color=TARGET, va="bottom", ha="right")

    # structural Precision@5 ceiling, drawn only over the Precision@5 group
    ax.plot([-w - 0.04, w / 2 + 0.18], [p_ceiling, p_ceiling], color=CEILING, lw=1.6)
    ax.text(0, p_ceiling + 0.02, f"P@5 ceiling {p_ceiling:.3f}", fontsize=8,
            color=CEILING, va="bottom", ha="center")

    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.012,
                    f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("score")
    ax.set_title("Ranking quality — capped, not failing", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper center", fontsize=9, frameon=False, ncol=2)


def main():
    sv, rows = load(SRC_VEC)
    sh, _ = load(SRC_HYB)
    p_ceiling = precision_ceiling(rows, k=5)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.35]})
    panel_recall(ax1, sv, sh)
    panel_ranking(ax2, sv, sh, p_ceiling)

    fig.suptitle("Figure 4.6 — Layer B retrieval: recall clears the bar, RRF ties vector, precision is gold-capped",
                 fontsize=12.5, fontweight="bold", y=1.0)
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"precision@5 ceiling: {p_ceiling:.3f}  (vector P@5 = {sv['precision@5']:.3f}, "
          f"{sv['precision@5'] / p_ceiling:.0%} of ceiling)")


if __name__ == "__main__":
    main()
