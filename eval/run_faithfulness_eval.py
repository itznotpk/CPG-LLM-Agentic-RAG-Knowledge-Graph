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
import argparse
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

Judge the CLAIM's CORE clinical content — the parameter monitored, the drug/action recommended,
the intervention proposed — against EVIDENCE. Apply these rules:

1. SAFETY-CRITICAL (stay strict): mark UNSUPPORTED if the claim introduces a DRUG NAME, a
   DOSE/STRENGTH/FREQUENCY value, or a numeric DIAGNOSTIC/LAB THRESHOLD that does not appear in
   EVIDENCE, or that contradicts it. Fabricated doses and drugs are never acceptable.

2. OPERATIONAL QUALIFIER (be fair — parameter/schedule split): if the core parameter or action
   IS grounded in EVIDENCE, do NOT mark unsupported merely because a MONITORING SCHEDULE, TIMING
   INTERVAL, or SCREENING FREQUENCY is not stated verbatim (e.g. "serial at 0,3,6h", "12-lead",
   "annual", "every 2-4 weeks", "<2 g/day"). These are standard operational details, not new
   clinical facts. Supported = the monitored parameter / lifestyle target itself is evidence-linked.

3. ELIGIBILITY / ASSESSMENT (be fair): a recommendation to ASSESS, SCREEN, REFER FOR, or CONSIDER a
   guideline-standard intervention for the patient's condition is SUPPORTED if EVIDENCE links that
   intervention to the condition — even if the exact eligibility criterion/threshold is not quoted.
   Mark unsupported only if the intervention is ABSENT from EVIDENCE, or the claim quotes a
   FABRICATED probability/risk number as a patient prediction.

Vague paraphrases of evidence are supported. When the core clinical claim is grounded and only an
operational/eligibility qualifier is missing, set supported=true and note the missing qualifier in reason."""


def _judge_client() -> tuple[openai.AsyncOpenAI, str]:
    # Judge ≠ author: default to Gemini, NOT the STAGE5/LLM (MiMo) synthesis model,
    # so a model never grades its own plan. Explicit JUDGE_LLM_* still wins.
    base = os.getenv("JUDGE_LLM_BASE_URL") or os.getenv("GEMINI_BASE_URL")
    key = os.getenv("JUDGE_LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = os.getenv("JUDGE_LLM_CHOICE") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return openai.AsyncOpenAI(base_url=base, api_key=key), model


async def judge_claim(client: openai.AsyncOpenAI, model: str, context: str, claim: str) -> tuple[bool, str, bool]:
    """Return (supported, reason, errored).

    `errored=True` means the judge never gave a verdict (transient 429/503 that
    survived all retries). These are EXCLUDED from the metric — counting them as
    unsupported would corrupt faithfulness with provider noise. One unguarded
    503 previously aborted the whole run; retries + per-claim isolation fix that.
    """
    for attempt in range(5):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": JUDGE_PROMPT.format(context=context[:60000], claim=claim)}],
                temperature=0,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content)
            return bool(parsed.get("supported", False)), str(parsed.get("reason", "")), False
        except (openai.RateLimitError, openai.InternalServerError, openai.APITimeoutError, openai.APIConnectionError) as e:
            if attempt == 4:
                return False, f"<judge unavailable after retries: {e}>", True
            await asyncio.sleep(2 ** attempt)  # 1,2,4,8s backoff
        except Exception as e:
            return False, f"<judge parse error: {e}>", False
    return False, "<judge unavailable>", True


async def main(limit: int | None = None):
    gold = load_jsonl("clinical_qa_gold.jsonl")
    if limit:
        gold = gold[:limit]
    judge_client, judge_model = _judge_client()
    sem = asyncio.Semaphore(4)  # cap concurrent judge calls — bursts of 20 trip Gemini 503

    async def _judge(context, c):
        async with sem:
            return await judge_claim(judge_client, judge_model, context, c)

    rows = []

    for item in gold:
        try:
            case = to_patient_case(item["patient_case"])
            ddx = await stage_2_ddx(case, top_k=5)
            cpgs = await stage_3_route(ddx)
            evidence = await stage_4_retrieve(case, ddx, cpgs)
            plan = await stage_5_synthesize(case, ddx, cpgs, evidence)
        except Exception as e:
            # One case's pipeline failure must not discard already-judged rows.
            print(f"[skip] case {item['id']}: pipeline error {e}")
            continue

        context_blob = "\n\n".join(c.content for c in evidence)
        claims = treatment_plan_claims(plan)

        verdicts = await asyncio.gather(*[_judge(context_blob, c) for c in claims])
        # Exclude judge-errored claims from the denominator (provider noise, not hallucination).
        judged = [(claim, ok, reason) for claim, (ok, reason, err) in zip(claims, verdicts) if not err]
        n_errored = len(claims) - len(judged)
        supported = sum(1 for _, ok, _ in judged if ok)
        n = len(judged) or 1

        # Capture every unsupported claim + the judge's reason so we can inspect
        # WHICH lever (top-k, retrieval ranking, synthesis prompt) is worth pulling.
        failures = [
            {"claim": claim, "reason": reason}
            for claim, ok, reason in judged
            if not ok
        ]

        rows.append({
            "id": item["id"],
            "n_claims": n,
            "n_supported": supported,
            "n_errored": n_errored,
            "faithfulness": supported / n,
            "any_hallucination": 1.0 if supported < n else 0.0,
            "failures": failures,
        })

    summary = {
        "n": len(rows),
        "judge_model": judge_model,
        "mean_faithfulness":   mean(r["faithfulness"] for r in rows) if rows else 0.0,
        "hallucination_rate":  mean(r["any_hallucination"] for r in rows) if rows else 0.0,
        "total_judge_errored": sum(r["n_errored"] for r in rows),
    }
    print_summary("Faithfulness (Stage 5)", summary)
    write_results("faithfulness", rows, summary)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Subsample first N gold items (e.g. 10) to fit one quota window.")
    args = ap.parse_args()
    asyncio.run(main(limit=args.limit))
