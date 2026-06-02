"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer C (re-ranker / dedup / boost)
         →  Pipeline Stage 4 full path
═══════════════════════════════════════════════════════════════════════════════
Runs the *actual* Stage 4 pipeline end-to-end:
  LLM multi-query generation (7 domains + condition anchors + universal anchors)
  → parallel vector search
  → chunk dedup
  → category-boost scoring
  → top-20 final selection

Compares the final top-20 against gold-set relevant_chunk_ids so the metrics
reflect what the production pipeline actually surfaces, not a single raw query.

Also reports a "multi-query lift" column: recall@20 of the full Stage 4 path
minus recall@20 of a single direct vector search with the gold query, so you
can see whether the complexity pays off per item.

Usage
-----
  python -m eval.run_stage4_eval
  python -m eval.run_stage4_eval --queries-per-code 7 --chunks-per-query 5

Gold-set note
-------------
  The retrieval_gold.jsonl entries only carry a document_filter (CPG title)
  and a plain query string — they have no PatientCase / DDx structure.
  We synthesise minimal stubs so Stage 4 can run:
    PatientCase : chief_complaint = gold query
    DDxResult   : code/title from the FILTER_TO_ICD map below (extend as needed)
    CPGDocRef   : doc UUIDs resolved via resolve_cpg_title_to_doc_ids
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import argparse
import asyncio

from agent.clinical_stages import stage_4_retrieve, DDxResult
from agent.models import PatientCase
from agent.routing import CPGDocRef
from agent.tools import vector_search_tool, VectorSearchInput

from eval.io_utils import load_jsonl, write_results, print_summary
from eval._helpers import resolve_cpg_title_to_doc_ids
from eval.metrics import recall_at_k, mrr, ndcg_at_k, hit_rate_at_k, mean


# ── minimal ICD stubs for condition anchors ───────────────────────────────────
# Maps the gold-set document_filter label → (icd_code, icd_title).
# The code is only used by _expected_pillars_for() to inject condition-specific
# anchor queries; an unrecognised code simply means no condition anchors fire
# (the 3 universal anchors always fire regardless).
_FILTER_TO_ICD: dict[str, tuple[str, str]] = {
    "STEMI":                              ("I21.0", "ST-elevation myocardial infarction"),
    "NSTE-ACS":                           ("I21.4", "Non-ST-elevation acute coronary syndrome"),
    "NSTEMI":                             ("I21.4", "Non-ST-elevation myocardial infarction"),
    "Heart Failure":                      ("I50.0", "Congestive heart failure"),
    "Hypertension":                       ("I10",   "Essential hypertension"),
    "Dyslipidaemia":                      ("E78.5", "Hyperlipidaemia"),
    "Atrial Fibrillation":                ("I48",   "Atrial fibrillation"),
    "Ischaemic Stroke":                   ("I63",   "Cerebral infarction"),
    "Stable Coronary Artery Disease":     ("I25.1", "Atherosclerotic heart disease"),
    "Percutaneous Coronary Intervention": ("I25.1", "Atherosclerotic heart disease"),
}


def _make_stubs(
    document_filter: str,
    query: str,
    doc_ids: list[str],
) -> tuple:
    """Return (PatientCase, [DDxResult], [CPGDocRef]) minimal stubs."""
    case = PatientCase(chief_complaint=query)

    icd_code, icd_title = _FILTER_TO_ICD.get(
        document_filter, ("Z99", document_filter)
    )
    ddx = [DDxResult(code=icd_code, title=icd_title, similarity=1.0)]

    cpg_name = document_filter
    cpgs = [
        CPGDocRef(
            cpg_name=cpg_name,
            document_id=doc_ids[0] if doc_ids else "",
            document_ids=doc_ids,
            title=cpg_name,
            match_type="semantic_scope",
            score=1.0,
            matched_scope=icd_code,
        )
    ]
    return case, ddx, cpgs


async def single_query_recall(
    query: str, doc_ids: list[str] | None, relevant: list[str]
) -> float:
    """Recall@20 for a plain single vector search — the Layer B baseline."""
    hits = await vector_search_tool(VectorSearchInput(
        query=query, limit=20, document_id_filter=doc_ids
    ))
    retrieved = [h.chunk_id for h in hits]
    return recall_at_k(retrieved, relevant, 20)


async def run_item(
    item: dict,
    queries_per_code: int,
    chunks_per_query: int,
) -> dict | None:
    relevant = item["relevant_chunk_ids"]
    if any(str(c).startswith("REPLACE_WITH_") for c in relevant):
        return None

    doc_ids: list[str] | None = None
    if item.get("document_filter"):
        doc_ids = await resolve_cpg_title_to_doc_ids(item["document_filter"])
        if not doc_ids:
            print(f"[warn] {item['id']}: no docs matched filter {item['document_filter']!r}")

    case, ddx, cpgs = _make_stubs(
        item.get("document_filter", ""),
        item["query"],
        doc_ids or [],
    )

    # Full Stage 4 pipeline
    chunks = await stage_4_retrieve(
        case, ddx, cpgs,
        queries_per_code=queries_per_code,
        chunks_per_query=chunks_per_query,
    )
    retrieved = [c.chunk_id for c in chunks]

    # Single-query baseline for lift calculation
    baseline_r20 = await single_query_recall(item["query"], doc_ids, relevant)

    stage4_r20 = recall_at_k(retrieved, relevant, 20)

    return {
        "id":             item["id"],
        "query":          item["query"][:60],
        "n_relevant":     len(relevant),
        "n_retrieved":    len(retrieved),
        "recall@20":      stage4_r20,
        "mrr":            mrr(retrieved, relevant),
        "ndcg@10":        ndcg_at_k(retrieved, relevant, 10),
        "hit@10":         hit_rate_at_k(retrieved, relevant, 10),
        "baseline_r@20":  baseline_r20,
        "lift_r@20":      stage4_r20 - baseline_r20,
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries-per-code", type=int, default=7,
                    help="LLM-generated queries per ICD code (default 7)")
    ap.add_argument("--chunks-per-query", type=int, default=5,
                    help="Chunks fetched per query before dedup (default 5)")
    ap.add_argument("--item-delay", type=float, default=3.0,
                    help="Seconds to sleep between gold items to avoid Bedrock throttling (default 3)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only run the first N gold items (0 = all, useful for smoke tests)")
    args = ap.parse_args()

    gold = load_jsonl("retrieval_gold.jsonl")
    if args.limit:
        gold = gold[: args.limit]

    # Run sequentially with a small inter-item pause.
    # Stage 4 fires ~10 parallel Bedrock embedding calls per item; without a
    # delay the burst across 120 items saturates the Bedrock rate limit.
    rows: list[dict] = []
    skipped = 0
    for i, item in enumerate(gold, 1):
        print(f"[{i}/{len(gold)}] {item['id']}: {item['query'][:60]}")
        result = await run_item(item, args.queries_per_code, args.chunks_per_query)
        if result is None:
            skipped += 1
        else:
            rows.append(result)
        await asyncio.sleep(args.item_delay)

    if skipped:
        print(f"[info] Skipped {skipped} unresolved gold entries (REPLACE_WITH_ placeholders)")

    summary = {
        "queries_per_code":  args.queries_per_code,
        "chunks_per_query":  args.chunks_per_query,
        "n":                 len(rows),
        "skipped_unresolved": skipped,
        "recall@20":         mean(r["recall@20"]     for r in rows),
        "MRR":               mean(r["mrr"]           for r in rows),
        "nDCG@10":           mean(r["ndcg@10"]       for r in rows),
        "hit_rate@10":       mean(r["hit@10"]        for r in rows),
        "baseline_recall@20": mean(r["baseline_r@20"] for r in rows),
        "mean_lift_r@20":    mean(r["lift_r@20"]     for r in rows),
    }
    print_summary("Stage 4 full pipeline — Layer C eval", summary)
    write_results("stage4_full", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
