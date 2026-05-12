"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer D (groundedness / hallucination)
         →  Pipeline Stage 5 (TreatmentPlan synthesis)
═══════════════════════════════════════════════════════════════════════════════
We run stages 2→3→4 to get the same evidence chunks the synthesiser saw, then
run stage 5 to produce the TreatmentPlan. Each atomic claim from the plan is
judged against the concatenated evidence by an LLM judge.

LLM judge defaults to whatever STAGE5_LLM_* / LLM_* env vars resolve to (same
client style as agent.clinical_stages). Override by setting JUDGE_LLM_* if you
want a different model from the synthesis model (best practice — judge ≠ author).

Outputs
-------
- mean faithfulness (% of claims supported)
- hallucination rate (% of plans with ≥1 unsupported claim)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import asyncio
import json
import os

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


async def judge_claim(client: openai.AsyncOpenAI, model: str, context: str, claim: str) -> bool:
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(context=context[:60000], claim=claim)}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        return bool(json.loads(resp.choices[0].message.content).get("supported", False))
    except Exception:
        return False


async def main():
    gold = load_jsonl("clinical_qa_gold.jsonl")
    judge_client, judge_model = _judge_client()
    rows = []

    for item in gold:
        case = to_patient_case(item["patient_case"])
        ddx = await stage_2_ddx(case, top_k=5)
        cpgs = await stage_3_route(ddx)
        evidence = await stage_4_retrieve(case, ddx, cpgs)
        plan = await stage_5_synthesize(case, ddx, cpgs, evidence)

        context_blob = "\n\n".join(c.content for c in evidence)
        claims = treatment_plan_claims(plan)

        verdicts = await asyncio.gather(*[
            judge_claim(judge_client, judge_model, context_blob, c) for c in claims
        ])
        supported = sum(1 for v in verdicts if v)
        n = len(claims) or 1

        rows.append({
            "id": item["id"],
            "n_claims": n,
            "n_supported": supported,
            "faithfulness": supported / n,
            "any_hallucination": 1.0 if supported < n else 0.0,
        })

    summary = {
        "n": len(rows),
        "judge_model": judge_model,
        "mean_faithfulness":   mean(r["faithfulness"] for r in rows),
        "hallucination_rate":  mean(r["any_hallucination"] for r in rows),
    }
    print_summary("Faithfulness (Stage 5)", summary)
    write_results("faithfulness", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
