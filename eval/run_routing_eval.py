"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer A2  →  Pipeline Stage 3 (ICD-11 → CPG routing)
═══════════════════════════════════════════════════════════════════════════════
Calls agent.routing.route_icd_to_cpgs(icd_code, top_k=3) — returns CPGDocRef
objects with .cpg_name, .match_type ("exact" | "parent" | "semantic"), .title.

We match on substring against expected_document_titles so the gold set can
say "STEMI" and accept "STEMI(4th Edition)" or similar real cpg_name values.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import asyncio

from agent.routing import route_icd_to_cpgs

from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import mean


def _matches_any(predicted_name: str, expected_titles: list[str]) -> bool:
    p = predicted_name.lower()
    return any(e.lower() in p for e in expected_titles)


async def main():
    gold = load_jsonl("routing_gold.jsonl")
    rows = []
    for item in gold:
        refs = await route_icd_to_cpgs(item["icd11_code"], top_k=3)
        predicted_names = [r.cpg_name for r in refs]
        expected = item["expected_document_titles"]

        top1_ok = float(bool(refs) and _matches_any(refs[0].cpg_name, expected))
        # For hit@3 we use substring-tolerant equality
        hit3 = float(any(_matches_any(p, expected) for p in predicted_names[:3]))

        rows.append({
            "id": item["id"],
            "icd": item["icd11_code"],
            "expected": ",".join(expected),
            "predicted_top3": " | ".join(predicted_names[:3]),
            "top1_match": top1_ok,
            "hit@3": hit3,
            "match_type": refs[0].match_type if refs else "none",
        })

    summary = {
        "n": len(rows),
        "top1_accuracy": mean(r["top1_match"] for r in rows),
        "hit_rate@3": mean(r["hit@3"] for r in rows),
        "pct_exact":     mean(1.0 if r["match_type"] == "exact" else 0.0 for r in rows),
        "pct_parent":    mean(1.0 if r["match_type"] == "parent" else 0.0 for r in rows),
        "pct_semantic":  mean(1.0 if r["match_type"] == "semantic" else 0.0 for r in rows),
    }
    print_summary("Routing (Stage 3)", summary)
    write_results("routing", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
