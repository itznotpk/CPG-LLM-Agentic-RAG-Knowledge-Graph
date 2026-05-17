"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer B (retrieval) + Layer C (re-ranker / dedup)
         →  Pipeline Stage 4 (Scoped CPG retrieval)
═══════════════════════════════════════════════════════════════════════════════
THE most important technical eval. Run vector / hybrid modes on the SAME
gold set; the delta justifies your design choice in the final report.

Wiring
------
- agent.tools.vector_search_tool(VectorSearchInput(query, limit, document_id_filter))
- agent.tools.hybrid_search_tool(HybridSearchInput(query, limit, text_weight, document_id_filter))
- document_id_filter takes UUIDs, but the gold set names a CPG by title;
  we resolve title → doc UUIDs once per query via eval._helpers.

How to use
----------
  python -m eval.run_retrieval_eval --mode vector
  python -m eval.run_retrieval_eval --mode hybrid
Run both, then tabulate.

GOLD-SET NOTE: relevant_chunk_ids placeholders MUST be replaced with real
chunk UUIDs from your `chunks` table for the metrics to mean anything.
Use the helper SQL printed at the bottom of this docstring to look them up.

  -- helper SQL (in psql against your Neon DB)
  SELECT c.id AS chunk_id, c.metadata->>'section_number' AS section,
         d.title AS cpg, LEFT(c.content, 80) AS preview
  FROM chunks c JOIN documents d ON d.id = c.document_id
  WHERE d.metadata->>'cpg_name' ILIKE '%STEMI%'
  ORDER BY (c.metadata->>'section_number')::text;
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import argparse
import asyncio

from agent.tools import vector_search_tool, hybrid_search_tool, VectorSearchInput, HybridSearchInput

from eval.io_utils import load_jsonl, write_results, print_summary
from eval._helpers import resolve_cpg_title_to_doc_ids
from eval.metrics import (
    recall_at_k, precision_at_k, mrr, ndcg_at_k, hit_rate_at_k, mean,
)


async def call_retriever(query: str, doc_ids: list[str] | None, top_k: int, mode: str) -> list[str]:
    if mode == "vector":
        hits = await vector_search_tool(VectorSearchInput(
            query=query, limit=top_k, document_id_filter=doc_ids
        ))
    elif mode == "hybrid":
        hits = await hybrid_search_tool(HybridSearchInput(
            query=query, limit=top_k, text_weight=0.3, document_id_filter=doc_ids
        ))
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return [h.chunk_id for h in hits]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["vector", "hybrid"], default="vector")
    ap.add_argument("--k_max", type=int, default=20)
    args = ap.parse_args()

    gold = load_jsonl("retrieval_gold.jsonl")
    rows = []
    skipped = 0
    for item in gold:
        # Skip entries whose chunk IDs haven't been resolved yet
        relevant = item["relevant_chunk_ids"]
        if any(str(cid).startswith("REPLACE_WITH_") for cid in relevant):
            skipped += 1
            continue

        doc_ids = None
        if item.get("document_filter"):
            doc_ids = await resolve_cpg_title_to_doc_ids(item["document_filter"])
            if not doc_ids:
                print(f"[warn] {item['id']}: no docs matched filter {item['document_filter']!r}")

        retrieved = await call_retriever(item["query"], doc_ids, args.k_max, args.mode)

        rows.append({
            "id": item["id"],
            "query": item["query"][:60],
            "n_relevant": len(relevant),
            "recall@5":  recall_at_k(retrieved, relevant, 5),
            "recall@10": recall_at_k(retrieved, relevant, 10),
            "recall@20": recall_at_k(retrieved, relevant, 20),
            "precision@5": precision_at_k(retrieved, relevant, 5),
            "mrr": mrr(retrieved, relevant),
            "ndcg@10": ndcg_at_k(retrieved, relevant, 10),
            "hit@10": hit_rate_at_k(retrieved, relevant, 10),
        })

    if skipped:
        print(f"[info] Skipped {skipped} unresolved gold entries (REPLACE_WITH_ placeholders)")

    summary = {
        "mode": args.mode,
        "n": len(rows),
        "skipped_unresolved": skipped,
        "recall@5":  mean(r["recall@5"]  for r in rows),
        "recall@10": mean(r["recall@10"] for r in rows),
        "recall@20": mean(r["recall@20"] for r in rows),
        "precision@5": mean(r["precision@5"] for r in rows),
        "MRR": mean(r["mrr"] for r in rows),
        "nDCG@10": mean(r["ndcg@10"] for r in rows),
        "hit_rate@10": mean(r["hit@10"] for r in rows),
    }
    print_summary(f"Retrieval (Stage 4) — mode={args.mode}", summary)
    write_results(f"retrieval_{args.mode}", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
