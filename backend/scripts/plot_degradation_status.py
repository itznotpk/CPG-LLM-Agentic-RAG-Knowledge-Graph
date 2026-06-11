"""
Figure 4.11 — Silent-degradation / infrastructure robustness probe status.

The SIL/INF suite's value is the *discovery*: probing a failure mode the accuracy
evals are structurally blind to (the answer arrives, but a stage silently failed
and a fallback masked it) surfaced genuine fail-silent bugs. This figure shows the
6-probe status grid before and after the fail-loud guards shipped — the red→green
flip across four rows is the visual of "built probes, found four fail-silent bugs,
closed them."

Counts are read live from the on-disk run files so the figure cannot drift:
  pilot     SIL: degradation_sil_20260604_213407.json
            INF: degradation_inf_20260604_213451.json
  finalized SIL+INF: degradation_sil_inf_20260605_025438.json

Run:  cd backend; python scripts/plot_degradation_status.py
Out:  docs/report/figures/figure_4_12_degradation_status.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]               # backend/
RESULTS = ROOT / "eval" / "results"
OUT = ROOT.parent / "docs" / "report" / "figures" / "figure_4_11_degradation_status.png"

PILOT_SIL = RESULTS / "degradation_sil_20260604_213407.json"
PILOT_INF = RESULTS / "degradation_inf_20260604_213451.json"
FINAL = RESULTS / "degradation_sil_inf_20260605_025438.json"

ORDER = ["SIL-01", "SIL-02", "SIL-03", "INF-01", "INF-02", "INF-03"]
SCENARIO = {
    "SIL-01": "Stage-2 rerank returns garbage JSON",
    "SIL-02": "Stage-4 returns 0 chunks (no error)",
    "SIL-03": "KG critic crashes, LLM clears",
    "INF-01": "Neo4j outage",
    "INF-02": "Bedrock 429 kills Stage 4",
    "INF-03": "pgvector connection refused",
}

PASS = "#2e7d32"
FAIL = "#c0392b"


def _pass_map(*paths: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in paths:
        d = json.loads(p.read_text())
        for r in d.get("rows", []):
            out[r["id"]] = float(r.get("pass", 0.0))
    return out


def main():
    pilot = _pass_map(PILOT_SIL, PILOT_INF)
    final = _pass_map(FINAL)

    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    cols = [("Pilot", 0, pilot), ("With fail-loud guards", 1, final)]

    for label, x, m in cols:
        for row, pid in enumerate(ORDER):
            ok = m.get(pid, 0.0) >= 1.0
            ax.scatter(x, row, s=620, marker="s",
                       color=PASS if ok else FAIL, edgecolors="white", linewidths=1.5, zorder=2)
            ax.text(x, row, "PASS" if ok else "FAIL", ha="center", va="center",
                    color="white", fontsize=8.5, fontweight="bold", zorder=3)
        ax.text(x, len(ORDER) - 0.35, label, ha="center", va="bottom",
                fontsize=11, fontweight="bold")

    for row, pid in enumerate(ORDER):
        ax.text(-0.62, row, f"{pid}", ha="right", va="center", fontsize=9.5, fontweight="bold")
        ax.text(-0.50, row, f"  {SCENARIO[pid]}", ha="left", va="center", fontsize=8.5, color="#444444")

    n_pilot = int(sum(v >= 1.0 for v in pilot.values()))
    n_final = int(sum(v >= 1.0 for v in final.values()))
    ax.set_xlim(-2.4, 1.6)
    ax.set_ylim(-0.6, len(ORDER) + 0.2)
    ax.invert_yaxis()
    ax.axis("off")
    fig.suptitle(
        f"Figure 4.11 — Fail-loud robustness probes: {n_pilot}/6 pilot → {n_final}/6 with guards "
        f"(four fail-silent bugs found and closed)",
        fontsize=11.5, fontweight="bold", y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"pilot {n_pilot}/6 (passed: {[k for k in ORDER if pilot.get(k,0)>=1]}); "
          f"final {n_final}/6")


if __name__ == "__main__":
    main()
