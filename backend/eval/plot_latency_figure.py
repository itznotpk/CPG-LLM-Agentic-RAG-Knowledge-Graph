"""
Generate Figure 4.19: End-to-end latency distribution and per-stage breakdown.

Left panel  — cumulative response-time percentile curve (Locust-style)
Right panel — horizontal stacked bar showing per-stage mean contribution

Usage:
    cd backend
    python -m eval.plot_latency_figure
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "docs" / "report" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Stage display config
# ---------------------------------------------------------------------------
STAGE_LABELS = {
    "stage_5_synthesize_ms": "Stage 5: Synthesise",
    "stage_4_retrieve_ms":   "Stage 4: Retrieve",
    "stage_2_ddx_ms":        "Stage 2: DDx",
    "stage_6_safety_ms":     "Stage 6: Safety Critic",
    "kg_lookup_ms":          "KG Lookup",
    "graph_navigator_ms":    "Graph Navigator",
    "stage_3_route_ms":      "Stage 3: Route",
}

STAGE_COLORS = [
    "#E63946",  # Stage 5 — red (dominant)
    "#F4A261",  # Stage 4 — orange
    "#2A9D8F",  # Stage 2 — teal
    "#457B9D",  # Stage 6 — blue
    "#A8DADC",  # KG Lookup — light blue
    "#B7B7B7",  # Graph Navigator — grey
    "#E9C46A",  # Stage 3 — yellow
]

CONSULTATION_BUDGET_S = 600  # 10 minutes


def load_latest_latency() -> dict:
    files = sorted(RESULTS_DIR.glob("latency_*.json"))
    if not files:
        raise FileNotFoundError(f"No latency result files found in {RESULTS_DIR}")
    path = files[-1]
    print(f"Loading: {path.name}")
    with open(path) as f:
        return json.load(f)


def build_figure(data: dict) -> plt.Figure:
    rows = data["rows"]
    n = len(rows)

    # --- Per-case total times in seconds (sorted for percentile curve) ---
    totals_s = sorted(r["total_ms"] / 1000 for r in rows)

    # Percentile x-axis: evenly spaced from 0..100 over n points
    pct_x = [100 * (i + 1) / n for i in range(n)]

    # --- Per-stage means (seconds) ---
    stage_keys = list(STAGE_LABELS.keys())
    stage_means_s = {
        k: np.mean([r.get(k, 0) for r in rows]) / 1000
        for k in stage_keys
    }
    total_mean_s = np.mean(totals_s)

    # Sort stages by mean descending for the bar
    sorted_stages = sorted(stage_keys, key=lambda k: stage_means_s[k], reverse=True)

    # ---------------------------------------------------------------------------
    fig, (ax_left, ax_right) = plt.subplots(
        1, 2,
        figsize=(14, 6),
        gridspec_kw={"width_ratios": [1.1, 1]},
    )
    fig.patch.set_facecolor("#FAFAFA")

    # ── LEFT: Cumulative percentile curve ───────────────────────────────────
    ax_left.set_facecolor("#F4F4F4")
    ax_left.plot(pct_x, totals_s, color="#E63946", linewidth=2.5,
                 marker="o", markersize=6, zorder=3, label="End-to-end")

    # p50 / p95 / p99 — compute directly from sorted data, deduplicate if values overlap
    y_max = max(totals_s) * 1.4
    summary = data["summary"]
    pct_annotations = [
        ("p50", summary["total_ms_p50"] / 1000, "#2A9D8F",  "--"),
        ("p95", summary["total_ms_p95"] / 1000, "#E9C46A",  "-."),
        ("p99", summary["total_ms_p99"] / 1000, "#E63946",  ":"),
    ]
    # Separate labels vertically so they don't overlap
    label_gap = y_max * 0.07
    placed = []
    for label, val_s, color, ls in pct_annotations:
        ax_left.axhline(val_s, linestyle=ls, linewidth=1.3, color=color, alpha=0.85)
        # Push label up if too close to a previously placed one
        y_label = val_s + y_max * 0.02
        for py in placed:
            if abs(y_label - py) < label_gap:
                y_label = py + label_gap
        placed.append(y_label)
        ax_left.text(
            2, y_label, f"{label} = {val_s:.0f}s",
            color=color, fontsize=8.5, fontweight="bold", va="bottom"
        )

    # Consultation budget line — annotate inside the plot area at bottom right
    ax_left.axhline(
        CONSULTATION_BUDGET_S, linestyle=":", linewidth=1.5,
        color="#264653", alpha=0.5, label=f"Budget (600s)"
    )

    ax_left.set_xlabel("Percentile (%)", fontsize=10)
    ax_left.set_ylabel("Response time (s)", fontsize=10)
    ax_left.set_title(
        f"Response Time Distribution\n(n = {n} cases, pilot)",
        fontsize=11, fontweight="bold", pad=10
    )
    ax_left.set_xlim(0, 105)
    ax_left.set_ylim(0, max(totals_s) * 1.4)
    ax_left.grid(True, linestyle="--", alpha=0.4)
    ax_left.legend(fontsize=8.5, loc="upper left")

    # ── RIGHT: Horizontal stacked bar ────────────────────────────────────────
    ax_right.set_facecolor("#F4F4F4")

    left_offset = 0.0
    legend_patches = []
    for idx, key in enumerate(sorted_stages):
        val = stage_means_s[key]
        pct = (val / total_mean_s * 100) if total_mean_s else 0
        color = STAGE_COLORS[idx % len(STAGE_COLORS)]
        bar = ax_right.barh(
            0, val, left=left_offset,
            color=color, edgecolor="white", linewidth=0.8, height=0.45
        )
        # Label segments wider than 5% of total
        if pct >= 5:
            ax_right.text(
                left_offset + val / 2, 0,
                f"{pct:.0f}%",
                ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white"
            )
        left_offset += val
        legend_patches.append(
            mpatches.Patch(color=color,
                           label=f"{STAGE_LABELS[key]}  {val:.1f}s ({pct:.0f}%)")
        )

    ax_right.set_xlim(0, total_mean_s * 1.25)
    ax_right.set_yticks([])
    ax_right.set_xlabel("Mean time (s)", fontsize=10)
    ax_right.set_title(
        f"Per-Stage Breakdown\n(mean total = {total_mean_s:.1f}s)",
        fontsize=11, fontweight="bold", pad=10
    )
    ax_right.axvline(total_mean_s, linestyle="--", color="#264653",
                     linewidth=1.2, alpha=0.7)
    ax_right.text(
        total_mean_s + 1, 0.25,
        f"Mean\n{total_mean_s:.0f}s",
        color="#264653", fontsize=8, va="center"
    )
    ax_right.legend(
        handles=legend_patches, fontsize=8.5,
        loc="upper right", framealpha=0.9,
        bbox_to_anchor=(1.0, -0.12), ncol=1
    )
    ax_right.grid(axis="x", linestyle="--", alpha=0.4)

    fig.suptitle(
        "Figure 4.19 — End-to-End Latency Distribution and Per-Stage Breakdown",
        fontsize=12, fontweight="bold", y=1.01
    )
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.32)
    return fig


def main():
    data = load_latest_latency()
    fig = build_figure(data)
    out_path = OUTPUT_DIR / "figure_4_19_latency.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved: {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
