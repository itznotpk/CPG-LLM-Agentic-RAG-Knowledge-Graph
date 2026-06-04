"""Path B backfill writer — applies approved typed threshold properties to existing KG edges.

Inputs:
  tasks/Path_B_auto_approved.jsonl   — Tier 1+2 (auto-approved)
  tasks/Path_B_t3_decisions.jsonl    — Tier 3 (per-row reviewed); only decision=='approve' applied

Properties set on each edge (only non-null values):
  threshold_param, threshold_op, threshold_value, threshold_value2,
  threshold_unit, threshold_negated, threshold_source='path_b_v1'

Modes:
  --dry-run (default): print Cypher diff + counts, write nothing.
  --write            : execute MERGE against Neo4j.

The MATCH is by elementId(r). If the edge is missing, that row is logged and skipped
(treat as upstream KG drift, not a fatal error).
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from agent.graph_clinical import _get_neo4j_session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "tasks")
APPROVED_PATH = os.path.join(TASKS, "Path_B_auto_approved.jsonl")
T3_DECISIONS_PATH = os.path.join(TASKS, "Path_B_t3_decisions.jsonl")
DIFF_OUT = os.path.join(TASKS, "Path_B_backfill_diff.md")

PROPS = ["threshold_param", "threshold_op", "threshold_value",
         "threshold_value2", "threshold_unit", "threshold_negated"]


def build_param_set(x: Dict[str, Any]) -> Dict[str, Any]:
    """Build the property map. Drop keys whose value is None."""
    out: Dict[str, Any] = {}
    for k in PROPS:
        v = x.get(k)
        if v is None:
            continue
        out[k] = v
    out["threshold_source"] = "path_b_v1"
    return out


def load_inputs() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    # T1+T2
    with open(APPROVED_PATH, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows.append({
                "edge_id": r["edge"]["edge_id"],
                "relation": r["edge"]["relation"],
                "subject": r["edge"]["subject"],
                "object": r["edge"]["object"],
                "tier": r.get("tier", "T?"),
                "props": build_param_set(r["extracted"]),
            })
    # T3 approved
    with open(T3_DECISIONS_PATH, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("decision") != "approve":
                continue
            rows.append({
                "edge_id": d["edge_id"],
                "relation": None,
                "subject": None,
                "object": None,
                "tier": "T3",
                "props": build_param_set(d["extracted"]),
            })
    return rows


CYPHER = """
MATCH ()-[r]->() WHERE elementId(r) = $edge_id
SET r += $props
RETURN elementId(r) AS id, type(r) AS rel
"""


async def run(write: bool):
    rows = load_inputs()
    print(f"Loaded {len(rows)} approved threshold rows")
    print("Tier counts:", Counter(r["tier"] for r in rows))

    # Write diff preview
    lines = [
        "# Path B backfill — preview",
        "",
        f"Total: **{len(rows)} edges** to enrich. Mode: {'WRITE' if write else 'DRY-RUN'}",
        "",
        "## Sample Cypher (first 5 rows)",
        "",
        "```cypher",
    ]
    for r in rows[:5]:
        lines.append(f"// edge_id={r['edge_id']} tier={r['tier']}")
        lines.append("MATCH ()-[r]->() WHERE elementId(r) = $edge_id")
        lines.append(f"SET r += {json.dumps(r['props'], ensure_ascii=False)}")
        lines.append("")
    lines.append("```")
    with open(DIFF_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Preview written -> {DIFF_OUT}")

    if not write:
        print("DRY-RUN: no writes performed. Pass --write to apply.")
        return

    updated = 0
    missing = 0
    errors = 0
    async with await _get_neo4j_session() as session:
        for r in rows:
            try:
                res = await session.run(CYPHER, edge_id=r["edge_id"], props=r["props"])
                rec = await res.single()
                if rec is None:
                    missing += 1
                else:
                    updated += 1
            except Exception as e:
                errors += 1
                print(f"ERROR edge_id={r['edge_id']}: {e}")
    print(f"Done. updated={updated} missing={missing} errors={errors}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Execute writes (default: dry-run)")
    args = ap.parse_args()
    asyncio.run(run(write=args.write))


if __name__ == "__main__":
    main()
