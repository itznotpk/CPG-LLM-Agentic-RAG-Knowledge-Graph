"""
═══════════════════════════════════════════════════════════════════════════════
 Labeller:  Layer C multi-condition gold (stage4_multicondition_gold.jsonl)
═══════════════════════════════════════════════════════════════════════════════
Populates `relevant_chunk_ids` + `relevance_grades` for each multi-condition
case using an LLM-judge pass — the same method used for the 148-row Layer B
graded gold (`review_status: "llm_verified"`).

Why this is needed
------------------
Layer C (Stage-4 multi-query → dedup → boost → top-20) only *helps* when the
relevant evidence genuinely spans MANY clinical domains across MULTIPLE CPGs —
which is exactly the shape of Cases 8–12. The recall target must therefore span
all those domains too, or the lift metric just re-measures single-query recall.

How it works (per case)
-----------------------
  1. For each target CPG × clinical domain, run a domain-anchored vector search
     (scoped to that CPG's document UUIDs) to gather candidate chunks. The domain
     anchors mirror Stage-4's own universal anchors (investigations / lifestyle /
     referral) plus meds / monitoring / safety, so candidates cover the same
     surface the pipeline fans out over.
  2. Deduplicate candidates by chunk_id.
  3. LLM-judge each candidate against the full patient case → grade
     `primary | supporting | irrelevant`. Only primary/supporting are kept.
  4. Write relevant_chunk_ids (primary + supporting) + relevance_grades back into
     the gold file, with provenance (`review_status: "llm_verified"`).

Run
---
  python -m eval.label_stage4_multicondition_gold              # all cases
  python -m eval.label_stage4_multicondition_gold --only mc_011
  python -m eval.label_stage4_multicondition_gold --dry-run    # no file write

Review
------
This is a *labelling* pass — eyeball the written grades before trusting the lift
numbers. Each row keeps `llm_review.candidates_judged` so you can audit what was
dropped. Re-run with --only <id> to relabel a single case after editing anchors.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os

from agent.clinical_stages import _make_openai_client, stage_4_retrieve, DDxResult
from agent.tools import vector_search_tool, VectorSearchInput

from eval.io_utils import GOLD_DIR, load_jsonl
from eval._helpers import resolve_cpg_title_to_doc_ids
from eval.run_stage4_multicondition_eval import _build_patient_case, _build_cpg_refs

GOLD_FILE = "stage4_multicondition_gold.jsonl"

# Domain-anchored query templates. {cc} is filled with the case chief complaint so
# the search stays patient-relevant. These mirror Stage-4's universal anchors plus
# the meds/monitoring/safety domains, so candidate coverage matches the fan-out.
_DOMAIN_ANCHORS: dict[str, str] = {
    "medications":   "First-line and recommended drug therapy, doses, and medication choices for this patient: {cc}",
    "investigations":"Baseline investigations, tests, and imaging indicated for this patient: {cc}",
    "monitoring":    "Monitoring schedule, follow-up parameters, and bloods to track for this patient: {cc}",
    "lifestyle":     "Lifestyle, diet, exercise, weight, smoking, alcohol recommendations for this patient: {cc}",
    "referral":      "Specialist referrals indicated and their urgency for this patient: {cc}",
    "safety":        "Contraindications, drug interactions, and safety warnings relevant to this patient: {cc}",
}

_JUDGE_SYSTEM = """You are a clinical evidence reviewer building a retrieval gold set.
Given a full patient case and a candidate guideline chunk, decide how relevant the
chunk is for building this patient's care plan.

Grade exactly one of:
- "primary"     : directly answers a key management decision this patient needs
                  (e.g. the specific drug/dose, the contraindication, the referral threshold).
- "supporting"  : relevant background that a clinician would cite but is not the
                  decisive recommendation.
- "irrelevant"  : off-topic for THIS patient (wrong condition, wrong population,
                  or generic boilerplate).

Judge for THIS patient's actual comorbidities and medications — a chunk about a
condition the patient does not have is irrelevant even if clinically sound.
Respond with ONLY a JSON object: {"grade": "primary|supporting|irrelevant", "reason": "<short>"}"""


def _case_summary(pc: dict) -> str:
    return (
        f"Age/sex: {pc.get('age')}/{pc.get('sex')}\n"
        f"Chief complaint: {pc.get('chief_complaint')}\n"
        f"Comorbidities: {', '.join(pc.get('comorbidities', [])) or 'none'}\n"
        f"Current medications: {', '.join(pc.get('current_medications', [])) or 'none'}\n"
        f"Severity staging: {json.dumps(pc.get('severity_staging', {}))}"
    )


async def _gather_candidates(
    case_summary_cc: str,
    expected_cpgs: list[str],
    domains: list[str],
    chunks_per_anchor: int,
) -> dict[str, dict]:
    """Return {chunk_id: {content, document_title, ...}} deduped across CPG×domain."""
    candidates: dict[str, dict] = {}
    for cpg in expected_cpgs:
        doc_ids = await resolve_cpg_title_to_doc_ids(cpg)
        if not doc_ids:
            print(f"  [warn] no docs for CPG filter {cpg!r}")
            continue
        for domain in domains:
            anchor = _DOMAIN_ANCHORS.get(domain)
            if not anchor:
                continue
            query = anchor.format(cc=case_summary_cc)
            hits = await vector_search_tool(VectorSearchInput(
                query=query, limit=chunks_per_anchor, document_id_filter=doc_ids,
            ))
            for h in hits:
                if h.chunk_id not in candidates:
                    candidates[h.chunk_id] = {
                        "chunk_id": h.chunk_id,
                        "content": h.content,
                        "document_title": h.document_title,
                        "cpg": cpg,
                        "domain": domain,
                    }
            await asyncio.sleep(0.3)  # gentle on the embedding endpoint
    return candidates


async def _judge(client, model: str, case_summary: str, cand: dict) -> tuple[str, str]:
    user = (
        f"PATIENT CASE:\n{case_summary}\n\n"
        f"CANDIDATE CHUNK (from {cand['document_title']}):\n{cand['content'][:1500]}"
    )
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )
    raw = resp.choices[0].message.content.strip().strip("` \n")
    if raw.startswith("json"):
        raw = raw[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        obj = json.loads(raw)
        return obj.get("grade", "irrelevant"), obj.get("reason", "")
    except json.JSONDecodeError:
        return "irrelevant", f"parse-fail: {raw[:80]}"


async def _gather_candidates_from_pool(item: dict, chunks_per_query: int) -> dict[str, dict]:
    """Gather candidates from Stage 4's actual retrieval pool (pool-seeded mode).
    Only chunks the pipeline can retrieve are eligible — ensures gold is reachable."""
    case = _build_patient_case(item["patient_case"])
    ddx = [DDxResult(code=d["code"], title=d["title"], similarity=1.0)
           for d in item.get("expected_ddx", [])]
    cpgs, _ = await _build_cpg_refs(item["expected_cpgs"])
    _final, pool = await stage_4_retrieve(
        case, ddx, cpgs,
        queries_per_code=7, chunks_per_query=chunks_per_query,
        return_pool=True,
    )
    candidates: dict[str, dict] = {}
    for c in pool:
        candidates[c.chunk_id] = {
            "chunk_id": c.chunk_id,
            "content": c.content,
            "document_title": c.document_title,
            "cpg": "",
            "domain": "pool",
        }
    return candidates


async def label_case(
    client, model: str, item: dict, chunks_per_anchor: int,
    pool_seeded: bool = False, pool_chunks_per_query: int = 10,
) -> dict:
    pc = item["patient_case"]
    cc = pc.get("chief_complaint", "")
    summary = _case_summary(pc)

    if pool_seeded:
        print(f"[{item['id']}] gathering candidates from Stage-4 pool "
              f"(chunks_per_query={pool_chunks_per_query})...")
        candidates = await _gather_candidates_from_pool(item, pool_chunks_per_query)
    else:
        print(f"[{item['id']}] gathering candidates across "
              f"{len(item['expected_cpgs'])} CPGs x {len(item['domains'])} domains...")
        candidates = await _gather_candidates(
            cc, item["expected_cpgs"], item["domains"], chunks_per_anchor,
        )
    print(f"[{item['id']}] {len(candidates)} unique candidate chunks -> judging...")

    grades: dict[str, str] = {}
    judged: list[dict] = []
    for cand in candidates.values():
        grade, reason = await _judge(client, model, summary, cand)
        judged.append({
            "chunk_id": cand["chunk_id"], "cpg": cand["cpg"], "domain": cand["domain"],
            "title": cand["document_title"], "grade": grade, "reason": reason,
        })
        if grade in ("primary", "supporting"):
            grades[cand["chunk_id"]] = grade
        await asyncio.sleep(0.2)

    n_primary = sum(1 for g in grades.values() if g == "primary")
    n_support = sum(1 for g in grades.values() if g == "supporting")
    print(f"[{item['id']}] kept {len(grades)} relevant "
          f"({n_primary} primary, {n_support} supporting) of {len(candidates)}")

    item["relevant_chunk_ids"] = list(grades.keys())
    item["relevance_grades"] = grades
    item["review_status"] = "llm_verified"
    item["llm_review"] = {
        "model": model,
        "candidates_judged": judged,
        "n_candidates": len(candidates),
        "n_relevant": len(grades),
    }
    return item


def _write_gold(rows: list[dict]) -> None:
    path = GOLD_DIR / GOLD_FILE
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n[ok] wrote {len(rows)} labelled rows -> {path}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="Label only this case id (e.g. mc_011)")
    ap.add_argument("--chunks-per-anchor", type=int, default=4,
                    help="Candidate chunks fetched per CPG×domain anchor (default 4)")
    ap.add_argument("--pool-seeded", action="store_true",
                    help="Gather candidates from Stage-4 pool instead of domain anchors. "
                         "Use this to re-label cases where the domain-anchor gold "
                         "contains chunks unreachable by the pipeline.")
    ap.add_argument("--pool-chunks-per-query", type=int, default=10,
                    help="chunks_per_query passed to stage_4_retrieve when --pool-seeded (default 10)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Judge and print, but do not overwrite the gold file")
    args = ap.parse_args()

    # Judge ≠ author (project convention — see eval/run_faithfulness_eval.py):
    # prefer JUDGE_LLM_* so the relevance judge is a DIFFERENT model from the one
    # Stage 4 uses to generate its queries (STAGE4_LLM_*). Layer B's gold was judged
    # by mimo-v2.5-pro; set JUDGE_LLM_CHOICE=mimo-v2.5-pro to match. Falls back to
    # the stage4/base model only if no judge model is configured.
    base_url = (os.getenv("JUDGE_LLM_BASE_URL") or os.getenv("STAGE4_LLM_BASE_URL")
                or os.getenv("LLM_BASE_URL"))
    api_key = (os.getenv("JUDGE_LLM_API_KEY") or os.getenv("STAGE4_LLM_API_KEY")
               or os.getenv("LLM_API_KEY"))
    model = (os.getenv("JUDGE_LLM_CHOICE") or os.getenv("STAGE4_LLM_CHOICE")
             or os.getenv("LLM_CHOICE", "gpt-4o"))
    provider = os.getenv("JUDGE_LLM_PROVIDER") or os.getenv("STAGE4_LLM_PROVIDER", "")
    client = _make_openai_client(base_url=base_url, api_key=api_key, provider=provider)
    print(f"[judge] using model: {model}")

    rows = load_jsonl(GOLD_FILE)
    for i, item in enumerate(rows):
        if args.only and item["id"] != args.only:
            continue
        rows[i] = await label_case(
            client, model, item, args.chunks_per_anchor,
            pool_seeded=args.pool_seeded,
            pool_chunks_per_query=args.pool_chunks_per_query,
        )

    if args.dry_run:
        print("\n[dry-run] no file written. Summary:")
        for r in rows:
            print(f"  {r['id']}: {len(r.get('relevant_chunk_ids', []))} relevant "
                  f"({r.get('review_status')})")
    else:
        _write_gold(rows)


if __name__ == "__main__":
    asyncio.run(main())
