"""
Throttled subsample variant of `run_faithfulness_eval`.

Same logic, but:
 - Sub-samples to the first N items (default 10) so the eval fits one provider quota window.
 - Caps concurrency on the judge calls via asyncio.Semaphore (default 3) so the burst
   pattern doesn't trip the provider's per-minute rate limit.
 - Adds a small per-item sleep so successive cases don't queue up too fast.
 - Prints per-item progress so a 429 partway through is visible.
 - Writes to eval/results/faithfulness_throttled_<stamp>.{csv,json}.

Use this when the full `run_faithfulness_eval` hits 429 — it produces statistically
weaker (smaller-n) but real, captured numbers instead of zero.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys

import openai

from agent.clinical_stages import stage_2_ddx, stage_3_route, stage_4_retrieve, stage_5_synthesize
from eval._helpers import to_patient_case, treatment_plan_claims
from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import mean

JUDGE_PROMPT = """You are auditing whether a clinical recommendation is supported by the retrieved CPG evidence.

EVIDENCE:
{context}

CLAIM:
{claim}

Reply with strict JSON: {{"supported": true|false, "reason": "<one sentence>"}}.
A claim is "supported" only if a fact in EVIDENCE entails it. Vague paraphrases of evidence are supported; new drug names / doses / thresholds not in evidence are NOT supported."""


def _judge_client() -> tuple[openai.AsyncOpenAI, str]:
    base = os.getenv("JUDGE_LLM_BASE_URL") or os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    key = os.getenv("JUDGE_LLM_API_KEY") or os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("JUDGE_LLM_CHOICE") or os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")
    return openai.AsyncOpenAI(base_url=base, api_key=key), model


async def judge_claim(sem: asyncio.Semaphore, client: openai.AsyncOpenAI, model: str, context: str, claim: str) -> bool:
    async with sem:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": JUDGE_PROMPT.format(context=context[:60000], claim=claim)}],
                temperature=0,
                response_format={"type": "json_object"},
            )
            return bool(json.loads(resp.choices[0].message.content).get("supported", False))
        except Exception:
            # Treat any judge error (including 429) conservatively as not-supported so
            # the run can finish; aggregate metrics will visibly degrade if many fail.
            return False


async def main(n: int, concurrency: int, between_cases_s: float):
    gold = load_jsonl("clinical_qa_gold.jsonl")[:n]
    judge_client, judge_model = _judge_client()
    sem = asyncio.Semaphore(concurrency)
    rows: list[dict] = []

    for idx, item in enumerate(gold, 1):
        print(f"[run] {idx}/{len(gold)}  {item.get('id')}", flush=True)
        try:
            case = to_patient_case(item["patient_case"])
            ddx = await stage_2_ddx(case, top_k=5)
            cpgs = await stage_3_route(ddx)
            evidence = await stage_4_retrieve(case, ddx, cpgs)
            plan = await stage_5_synthesize(case, ddx, cpgs, evidence)

            context_blob = "\n\n".join(c.content for c in evidence)
            claims = treatment_plan_claims(plan)

            verdicts = await asyncio.gather(*[
                judge_claim(sem, judge_client, judge_model, context_blob, c) for c in claims
            ])
            supported = sum(1 for v in verdicts if v)
            n_claims = len(claims) or 1

            rows.append({
                "id": item["id"],
                "n_claims": n_claims,
                "n_supported": supported,
                "faithfulness": supported / n_claims,
                "any_hallucination": 1.0 if supported < n_claims else 0.0,
            })
            print(f"[done] {item.get('id')}  faith={supported}/{n_claims}", flush=True)
        except Exception as exc:
            print(f"[fail] {item.get('id')}  {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            rows.append({
                "id": item["id"],
                "n_claims": 0,
                "n_supported": 0,
                "faithfulness": 0.0,
                "any_hallucination": 1.0,
                "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            })
        await asyncio.sleep(between_cases_s)

    summary = {
        "n": len(rows),
        "judge_model": judge_model,
        "mean_faithfulness":   mean(r["faithfulness"] for r in rows),
        "hallucination_rate":  mean(r["any_hallucination"] for r in rows),
    }
    print_summary("Faithfulness (Stage 5) — throttled subsample", summary)
    write_results("faithfulness_throttled", rows, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="how many gold items to evaluate (default 10)")
    parser.add_argument("--concurrency", type=int, default=3, help="parallel judge calls per item (default 3)")
    parser.add_argument("--sleep", type=float, default=2.0, help="seconds to wait between cases (default 2.0)")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.concurrency, args.sleep))
