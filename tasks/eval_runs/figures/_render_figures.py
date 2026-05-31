"""Render F1, F2, F3 PNGs from the stability_*.json artefacts."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent

FILES = {
    8:  ROOT / "stability_case8_20260531_172306.json",
    9:  ROOT / "stability_case9_20260531_180620.json",
    10: ROOT / "stability_case10_20260531_164044.json",
}
data = {c: json.load(open(p)) for c, p in FILES.items()}

# ---------- F1: top-K Jaccard by case ----------
cases = [8, 9, 10]
top1 = [len(set(data[c]["metrics"]["top1_stability"]["values"])) == 1 and 1.0
        or (max(data[c]["metrics"]["top1_stability"]["values"].count(v)
               for v in set(data[c]["metrics"]["top1_stability"]["values"]))
            / len(data[c]["metrics"]["top1_stability"]["values"]))
        for c in cases]
top3 = [data[c]["metrics"]["top3_jaccard_mean"] for c in cases]
top5 = [data[c]["metrics"]["top5_jaccard_mean"] for c in cases]

x = np.arange(len(cases))
w = 0.25
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(x - w, top1, w, label="top-1 modal rate", color="#4C72B0")
ax.bar(x,     top3, w, label="top-3 Jaccard",    color="#55A868")
ax.bar(x + w, top5, w, label="top-5 Jaccard",    color="#C44E52")
ax.axhline(0.95, ls="--", color="grey", lw=1, label="0.95 gate")
ax.set_xticks(x); ax.set_xticklabels([f"Case {c}" for c in cases])
ax.set_ylim(0, 1.05); ax.set_ylabel("Score (0-1)")
ax.set_title("F1 - DDx pool stability across N=10 replays")
ax.legend(loc="lower right"); ax.grid(axis="y", alpha=0.3)
for i, vals in enumerate(zip(top1, top3, top5)):
    for j, v in enumerate(vals):
        ax.text(x[i] + (j-1)*w, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig_jaccard_by_case.png", dpi=150)
plt.close(fig)

# ---------- F2: pairwise top-5 Jaccard heatmap, case 10 ----------
runs = data[10]["per_run_top5"]
n = len(runs)
mat = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        a, b = set(runs[i]), set(runs[j])
        mat[i, j] = len(a & b) / len(a | b) if (a | b) else 1.0

fig, ax = plt.subplots(figsize=(6.5, 5.5))
im = ax.imshow(mat, vmin=0, vmax=1, cmap="viridis")
ax.set_xticks(range(n)); ax.set_yticks(range(n))
ax.set_xticklabels([f"r{i+1}" for i in range(n)])
ax.set_yticklabels([f"r{i+1}" for i in range(n)])
ax.set_title(f"F2 - Case 10 pairwise top-5 Jaccard (N={n})")
for i in range(n):
    for j in range(n):
        ax.text(j, i, f"{mat[i,j]:.2f}", ha="center", va="center",
                color="white" if mat[i,j] < 0.7 else "black", fontsize=7)
fig.colorbar(im, ax=ax, label="Jaccard")
fig.tight_layout()
fig.savefig(OUT / "fig_case10_heatmap.png", dpi=150)
plt.close(fig)

# ---------- F3: substance vs prose, per case ----------
metrics = {
    "top-5 Jaccard\n(pool)":     [data[c]["metrics"]["top5_jaccard_mean"] for c in cases],
    "safety Jaccard\n(critic)":  [data[c]["extras"].get("safety_flag_jaccard_mean", 1.0) for c in cases],
    "med-count\nconsistency*":   [max(0.0, 1 - data[c]["extras"]["med_count"]["stdev"]
                                       / max(data[c]["extras"]["med_count"]["mean"], 1e-6))
                                  for c in cases],
    "plan_text Jaccard\n(prose)":[data[c]["extras"]["plan_text_jaccard_mean"] for c in cases],
}
labels = list(metrics.keys())
x = np.arange(len(cases))
w = 0.2
colors = ["#55A868", "#55A868", "#55A868", "#C44E52"]
fig, ax = plt.subplots(figsize=(9, 5))
for i, (label, vals) in enumerate(metrics.items()):
    ax.bar(x + (i-1.5)*w, vals, w, label=label, color=colors[i])
ax.set_xticks(x); ax.set_xticklabels([f"Case {c}" for c in cases])
ax.set_ylim(0, 1.1); ax.set_ylabel("Score (0-1)")
ax.set_title("F3 - Clinical substance is invariant; prose drifts (as expected)")
ax.axhline(0.95, ls="--", color="grey", lw=1)
ax.legend(loc="upper right", fontsize=8, ncol=2)
ax.grid(axis="y", alpha=0.3)
ax.text(0.01, -0.13,
        "* med-count consistency = 1 - (sigma / mean) of per-run medication count; green = clinically meaningful; red = cosmetic prose drift",
        transform=ax.transAxes, fontsize=7, color="grey")
fig.tight_layout()
fig.savefig(OUT / "fig_substance_vs_prose.png", dpi=150)
plt.close(fig)

print("wrote:")
for p in OUT.glob("*.png"):
    print(" ", p.name)
