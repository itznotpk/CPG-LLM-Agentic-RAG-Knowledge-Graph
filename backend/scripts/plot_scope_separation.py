"""
Figure 4.8 — Layer (scope) decision-boundary separation plot.

Renders the scope-refusal result described in report §4.3.2.5: the D2 cosine
similarity of each probe code to its nearest CPG scope embedding, with the
SEMANTIC_SCOPE_THRESHOLD = 0.32 boundary and the in-scope/orphan separation gap
drawn in. The figure is the classic "decision-boundary separation" view — the
whole story is that the two classes do not overlap and the threshold sits in the
gap between them.

Data is captured verbatim from the deterministic probe
`scripts/probe_d2_semantic_scope.py` console output (run 2026-06-09). The probe
is read-only and deterministic, so re-running it reproduces these values. Two
orphan codes (COPD `CA22`, peptic ulcer `DA60`) are absent from the ICD-11
embedding table and so carry no similarity score — they are refused because the
code is unknown, not by the threshold, and are noted on the plot rather than
plotted as points.

Run:  cd backend; python scripts/plot_scope_separation.py
Out:  docs/report/figures/figure_4_8_scope_separation.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "report" / "figures" / "figure_4_8_scope_separation.png"

THRESHOLD = 0.32
GAP = (0.265, 0.368)  # (highest orphan, lowest in-scope)

IN_SCOPE = [          # (label, code, similarity, label placement) — must route
    ("Diabetic retinopathy", "9B71.01", 0.368, "above"),
    ("Breast cancer", "2C61.0", 0.489, "below"),
    ("Ischaemic stroke", "8B11.0", 0.503, "above"),
    ("HFrEF", "BD11.0", 0.540, "below"),
    ("NSTEMI", "BA41.1", 0.711, "above"),
]
ORPHAN = [            # (label, code, similarity, label placement) — must refuse
    ("Epilepsy", "8A60", 0.185, "below"),
    ("Cardiac arrest", "BC91", 0.216, "above"),
    ("Migraine", "8A80", 0.220, "below"),
    ("UTI", "GC08", 0.265, "above"),
]
ORPHAN_ABSENT = ["COPD (CA22)", "Peptic ulcer (DA60)"]  # code not in icd11_codes

GREEN = "#2e7d32"   # in-scope (correctly routed)
RED = "#c0392b"     # orphan (correctly refused)
GAPC = "#bdbdbd"
LINE = "#222222"

Y_IN, Y_OR = 1.0, 0.0


def main():
    fig, ax = plt.subplots(figsize=(11, 4.6))

    # separation gap + threshold
    ax.axvspan(GAP[0], GAP[1], color=GAPC, alpha=0.35, zorder=0)
    ax.text(sum(GAP) / 2, 1.62, f"separation gap\n({GAP[0]:.3f}–{GAP[1]:.3f})",
            ha="center", va="bottom", fontsize=8.5, color="#555555")
    ax.axvline(THRESHOLD, ls="--", lw=1.4, color=LINE, zorder=1)
    ax.text(THRESHOLD, -0.62, f"threshold = {THRESHOLD}", ha="center", va="top",
            fontsize=9.5, fontweight="bold", color=LINE)

    # points (label placed directly above/below each dot — no connectors)
    def place(sim, y, color, marker, placement):
        ax.scatter(sim, y, s=120, color=color, marker=marker, zorder=3, edgecolor="white", linewidth=0.8)
        dy, va = (14, "bottom") if placement == "above" else (-14, "top")
        ax.annotate(f"{label}\n{sim:.3f}", (sim, y), textcoords="offset points",
                    xytext=(0, dy), ha="center", va=va, fontsize=8, color=color)

    for label, code, sim, placement in IN_SCOPE:
        place(sim, Y_IN, GREEN, "o", placement)
    for label, code, sim, placement in ORPHAN:
        place(sim, Y_OR, RED, "X", placement)

    ax.set_yticks([Y_OR, Y_IN])
    ax.set_yticklabels(["orphan\n(must refuse)", "in-scope\n(must route)"], fontsize=10)
    ax.set_ylim(-0.9, 1.9)
    ax.set_xlim(0.12, 0.78)
    ax.set_xlabel("D2 cosine similarity to nearest CPG scope embedding")
    ax.set_title("Figure 4.8 — Scope gate: in-scope and out-of-corpus codes separate cleanly, threshold sits in the gap",
                 fontsize=11.5, fontweight="bold", loc="left")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.text(0.5, 0.015, "COPD and peptic ulcer absent from ICD-11 table — refused without a score (see text).",
             ha="center", va="bottom", fontsize=8, color="#777777", style="italic")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"in-scope min = {min(r[2] for r in IN_SCOPE):.3f}, orphan max = {max(r[2] for r in ORPHAN):.3f}, "
          f"threshold = {THRESHOLD}; {len(ORPHAN_ABSENT)} orphans absent from ICD table")


if __name__ == "__main__":
    main()
