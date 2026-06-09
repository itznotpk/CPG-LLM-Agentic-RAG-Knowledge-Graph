"""
Figure 4.3 — Knowledge-graph scale and edge-type integrity.

Queries the LIVE Neo4j graph for node-label and relationship-type counts and
renders a two-panel horizontal bar chart, with the sparse INTERACTS_WITH bar
highlighted and annotated as the documented DDI-sparsity caveat (§4.3.1). Drawn
straight from Cypher `count` so the figure cannot drift from the real store.

Run:  cd backend; python scripts/plot_kg_composition.py
Out:  docs/report/figures/figure_4_3_kg_composition.png
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

OUT = Path(__file__).resolve().parents[2] / "docs" / "report" / "figures" / "figure_4_3_kg_composition.png"

NODE_BLUE = "#3b6ea5"
EDGE_GREY = "#6c757d"
HILITE = "#c0392b"  # INTERACTS_WITH sparsity highlight

# The clinically-meaningful edge types the Stage 4.5 / Stage 6 arms actually read
# (safety + prescribing + monitoring + referral) — NOT the epidemiological
# INCREASES_RISK_OF / ASSESSED_BY / CAUSES edges, which the pipeline ignores.
# Curated so the dense-vs-sparse contrast (CONTRAINDICATED_WITH vs INTERACTS_WITH)
# is the visible story, per §4.3.1 / Figure 4.3.
CLINICAL_EDGES = [
    "RECOMMENDED_FOR",
    "CONTRAINDICATED_WITH",
    "REQUIRES_MONITORING",
    "REQUIRES_REFERRAL",
    "FIRST_LINE_FOR",
    "INTERACTS_WITH",
    "SECOND_LINE_FOR",
]


async def fetch_counts():
    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        keep_alive=True, max_connection_lifetime=300,
    )
    db = os.getenv("NEO4J_DATABASE") or None
    nodes, edges = {}, {}
    try:
        async with driver.session(database=db) as s:
            r = await s.run("MATCH (n) UNWIND labels(n) AS l RETURN l AS k, count(*) AS c ORDER BY c DESC")
            async for row in r:
                nodes[row["k"]] = row["c"]
            r = await s.run("MATCH ()-[e]->() RETURN type(e) AS k, count(*) AS c ORDER BY c DESC")
            async for row in r:
                edges[row["k"]] = row["c"]
    finally:
        await driver.close()
    return nodes, edges


def _barh(ax, data: dict, title: str, base_color: str, drop=("OTHER", "Other"),
          top=8, highlight=None, keys=None):
    if keys is not None:
        # Explicit curated set, ordered by count so the bar chart still reads cleanly.
        items = sorted([(k, data.get(k, 0)) for k in keys], key=lambda kv: kv[1], reverse=True)
    else:
        items = [(k, v) for k, v in data.items() if k not in drop][:top]
    items.reverse()  # largest at top
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    colors = [HILITE if k == highlight else base_color for k in labels]
    bars = ax.barh(labels, values, color=colors)
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=10)
    xmax = max(values)
    for bar, v in zip(bars, values):
        ax.text(v + xmax * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{v:,}", va="center", fontsize=9)
    ax.set_xlim(0, xmax * 1.18)
    return dict(zip(labels, bars))


def main() -> None:
    nodes, edges = asyncio.run(fetch_counts())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2))
    _barh(ax1, nodes, "Node types", NODE_BLUE)
    barmap = _barh(ax2, edges, "Clinical relationship types (read by Stage 4.5 / Stage 6)",
                   EDGE_GREY, highlight="INTERACTS_WITH", keys=CLINICAL_EDGES)

    # Annotate the DDI-sparsity caveat on the INTERACTS_WITH bar.
    if "INTERACTS_WITH" in barmap:
        b = barmap["INTERACTS_WITH"]
        xmax = max(edges.get(k, 0) for k in CLINICAL_EDGES)
        ax2.annotate(
            "DDI sparsity (by design):\nedges extracted only from CPG prose\n→ Stage 6 also runs an independent LLM critic",
            xy=(edges["INTERACTS_WITH"], b.get_y() + b.get_height() / 2),
            xytext=(xmax * 0.40, b.get_y() + 1.3),
            fontsize=8.5, color=HILITE,
            arrowprops=dict(arrowstyle="->", color=HILITE, lw=1.2),
        )

    fig.suptitle("Figure 4.3 — Knowledge-graph composition and edge-type integrity (live Cypher count)",
                 fontsize=12.5, fontweight="bold", y=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved: {OUT}")
    print(f"nodes: {dict(list(nodes.items())[:6])}")
    print(f"edges: {dict(list(edges.items())[:8])}")


if __name__ == "__main__":
    main()
