"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer C (re-ranker / dedup / boost) — MULTI-CONDITION
         →  Pipeline Stage 4 full path, on cross-CPG consultation cases
═══════════════════════════════════════════════════════════════════════════════
Why this exists (and why it differs from run_stage4_eval.py)
------------------------------------------------------------
run_stage4_eval.py runs Stage 4 against retrieval_gold.jsonl, whose rows are
SINGLE narrow queries scoped to ONE CPG. Stage 4 fans out 7 domain queries +
anchors designed for a FULL multi-comorbidity patient case, so on single-query
gold it fills the top-20 budget with chunks the narrow gold never labelled →
structurally negative lift (measured −0.173). That is a gold-set/harness artifact,
not a pipeline defect — the same class of artifact already found for Layer A1/A2.

This harness feeds Stage 4 the input it was BUILT for: Cases 8–12, each a
cross-CPG consultation (3–5 CPGs, full PatientCase with comorbidities + meds).
It builds REAL multi-DDx / multi-CPG stubs (not a single-query stub) so the
multi-query fan-out can genuinely help, and measures lift against a single
chief-complaint vector query scoped to the same CPGs.

Gold set
--------
  eval/gold_sets/stage4_multicondition_gold.jsonl
  relevant_chunk_ids populated by eval/label_stage4_multicondition_gold.py
  (LLM-judged across all clinical domains each case touches).

Run
---
  python -m eval.run_stage4_multicondition_eval
  python -m eval.run_stage4_multicondition_eval --queries-per-code 7 --chunks-per-query 5

Lift definition
---------------
  lift_r@20 = Stage-4 full-pipeline recall@20
            − single-query baseline recall@20
  where the baseline is ONE vector search on the chief complaint, scoped to the
  union of the case's CPG document UUIDs (i.e. retrieval WITHOUT the fan-out).
  Positive lift ⇒ the multi-query/dedup/boost machinery earns its complexity on
  the multi-condition input it was designed for.
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

GOLD_FILE = "stage4_multicondition_gold.jsonl"


def _build_patient_case(pc: dict) -> PatientCase:
    """Build a PatientCase from the rich multi-condition gold structure.

    Unlike run_stage4_eval._make_stubs (chief_complaint = a single gold query),
    this preserves the full case so _generate_retrieval_queries fans out over
    real comorbidities, medications, vitals and severity staging.
    """
    return PatientCase(
        chief_complaint=pc.get("chief_complaint") or "unspecified",
        age=pc.get("age"),
        sex=pc.get("sex") if pc.get("sex") in ("M", "F", "other") else None,
        comorbidities=pc.get("comorbidities", []),
        current_medications=pc.get("current_medications", []),
        allergies=pc.get("allergies", []),
        vitals={k: float(v) for k, v in (pc.get("vitals") or {}).items()
                if isinstance(v, (int, float))},
        severity_staging={k: str(v) for k, v in (pc.get("severity_staging") or {}).items()},
    )


async def _build_cpg_refs(expected_cpgs: list[str]) -> tuple[list[CPGDocRef], list[str]]:
    """Resolve each expected CPG filter to a CPGDocRef; return refs + union doc_ids."""
    refs: list[CPGDocRef] = []
    all_doc_ids: list[str] = []
    for cpg in expected_cpgs:
        doc_ids = await resolve_cpg_title_to_doc_ids(cpg)
        if not doc_ids:
            print(f"  [warn] no docs matched CPG filter {cpg!r}")
            continue
        all_doc_ids.extend(doc_ids)
        refs.append(CPGDocRef(
            cpg_name=cpg,
            document_id=doc_ids[0],
            document_ids=doc_ids,
            title=cpg,
            match_type="semantic_scope",
            score=1.0,
            matched_scope=cpg,
        ))
    return refs, all_doc_ids


async def single_query_recall(
    chief_complaint: str, doc_ids: list[str], relevant: list[str]
) -> float:
    """Recall@20 for a plain single vector search on the chief complaint, scoped
    to the case's CPGs — the no-fan-out baseline."""
    hits = await vector_search_tool(VectorSearchInput(
        query=chief_complaint, limit=20, document_id_filter=doc_ids or None,
    ))
    return recall_at_k([h.chunk_id for h in hits], relevant, 20)


async def run_item(item: dict, queries_per_code: int, chunks_per_query: int) -> dict | None:
    relevant = item.get("relevant_chunk_ids") or []
    if not relevant:
        print(f"[skip] {item['id']}: no relevant_chunk_ids "
              f"(run label_stage4_multicondition_gold.py first)")
        return None

    pc = item["patient_case"]
    case = _build_patient_case(pc)

    ddx = [DDxResult(code=d["code"], title=d["title"], similarity=1.0)
           for d in item.get("expected_ddx", [])]
    cpgs, doc_ids = await _build_cpg_refs(item["expected_cpgs"])
    if not cpgs:
        print(f"[skip] {item['id']}: no CPGs resolved")
        return None

    chunks = await stage_4_retrieve(
        case, ddx, cpgs,
        queries_per_code=queries_per_code,
        chunks_per_query=chunks_per_query,
    )
    retrieved = [c.chunk_id for c in chunks]

    baseline_r20 = await single_query_recall(case.chief_complaint, doc_ids, relevant)
    stage4_r20 = recall_at_k(retrieved, relevant, 20)

    return {
        "id":            item["id"],
        "source_case":   item.get("source_case", ""),
        "n_cpgs":        len(cpgs),
        "n_relevant":    len(relevant),
        "n_retrieved":   len(retrieved),
        "recall@20":     stage4_r20,
        "mrr":           mrr(retrieved, relevant),
        "ndcg@10":       ndcg_at_k(retrieved, relevant, 10, grades=item.get("relevance_grades")),
        "hit@10":        hit_rate_at_k(retrieved, relevant, 10),
        "baseline_r@20": baseline_r20,
        "lift_r@20":     stage4_r20 - baseline_r20,
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries-per-code", type=int, default=7,
                    help="LLM-generated queries per case (default 7)")
    ap.add_argument("--chunks-per-query", type=int, default=5,
                    help="Chunks fetched per query before dedup (default 5)")
    ap.add_argument("--item-delay", type=float, default=3.0,
                    help="Seconds between cases to avoid embedding-endpoint throttling")
    ap.add_argument("--only", default="", help="Run only this case id (e.g. mc_011)")
    args = ap.parse_args()

    gold = load_jsonl(GOLD_FILE)
    rows: list[dict] = []
    skipped = 0
    for i, item in enumerate(gold, 1):
        if args.only and item["id"] != args.only:
            continue
        print(f"[{i}/{len(gold)}] {item['id']} ({item.get('source_case','')}): "
              f"{item['patient_case'].get('chief_complaint','')[:60]}")
        result = await run_item(item, args.queries_per_code, args.chunks_per_query)
        if result is None:
            skipped += 1
        else:
            rows.append(result)
            print(f"        recall@20={result['recall@20']:.3f} "
                  f"baseline={result['baseline_r@20']:.3f} "
                  f"lift={result['lift_r@20']:+.3f}")
        await asyncio.sleep(args.item_delay)

    if not rows:
        print("\n[error] no cases scored — is the gold set labelled?")
        return

    summary = {
        "queries_per_code":   args.queries_per_code,
        "chunks_per_query":   args.chunks_per_query,
        "n":                  len(rows),
        "skipped":            skipped,
        "recall@20":          mean(r["recall@20"] for r in rows),
        "MRR":                mean(r["mrr"] for r in rows),
        "nDCG@10":            mean(r["ndcg@10"] for r in rows),
        "hit_rate@10":        mean(r["hit@10"] for r in rows),
        "baseline_recall@20": mean(r["baseline_r@20"] for r in rows),
        "mean_lift_r@20":     mean(r["lift_r@20"] for r in rows),
    }
    print_summary("Stage 4 multi-condition — Layer C eval", summary)
    write_results("stage4_multicondition", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
