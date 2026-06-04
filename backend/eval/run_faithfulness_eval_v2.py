"""
Layer D Faithfulness — v2 throttled runner with methodology fixes.

Addresses three flaws in `run_faithfulness_eval[_throttled].py`:

1. **Self-judge confound** — same MiMo model writes the plan AND judges it.
   v2 keeps the same provider (no new credit spend) but rewrites the judge
   prompt with a rigorous-critic framing that explicitly distances the judge
   from the author role: "ignore plausibility, only credit verbatim evidence,
   default to NOT_SUPPORTED when uncertain". This is the cheapest way to break
   the self-confirmation bias without paying for a different vendor.

2. **Binary verdict counted rate-limit failures as hallucinations.** v2 returns
   a three-way verdict {SUPPORTED, NOT_SUPPORTED, UNVERIFIED} — UNVERIFIED is
   reserved for judge-call exceptions and is *excluded* from the faithfulness
   denominator instead of being counted as hallucination.

3. **`any_hallucination = ≥1 unsupported claim`** is an unhelpful binary on
   multi-claim plans (a 30-claim plan with 1 mistake reads the same as one
   with 30 mistakes). v2 reports:
     - `mean_faithfulness` — % of claims supported (same as v1)
     - `unsupported_rate` — % of claims unsupported (1 − faithfulness − unverified-share)
     - `severe_hallucination_rate` — % of plans with ≥30% claims unsupported
       (clinically meaningful threshold: ≤1-in-3 unsupported is a real risk)

Run with the same throttling discipline as v1:

    python -m eval.run_faithfulness_eval_v2 --n 10 --concurrency 2 --sleep 4
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from typing import Literal

import openai

from agent.clinical_stages import (
    stage_2_ddx, stage_3_route, stage_4_retrieve, stage_5_synthesize,
)
from eval._helpers import to_patient_case, treatment_plan_claims
from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import mean


# Rigorous-critic prompt: explicit role distancing + default-to-NOT_SUPPORTED
# to counter the self-confirmation bias when judge == author. The structured
# three-way verdict prevents rate-limit failures from being counted as
# hallucinations.
JUDGE_PROMPT = """You are an independent clinical evidence auditor reviewing
a treatment-plan claim against the CPG passages the planning system retrieved.

You did NOT write this plan. Assume nothing about who did. Your only job is
to verify whether the CLAIM is directly supported by the EVIDENCE — not
whether it is *clinically plausible*, not whether it sounds *reasonable*.

EVIDENCE (retrieved CPG chunks):
{context}

CLAIM:
{claim}

Verdict rules (apply in order):
  1. "SUPPORTED"     — a passage in EVIDENCE entails the claim, including
                        paraphrases of the same fact. Numeric values, drug
                        doses, and thresholds must appear in EVIDENCE
                        verbatim to count as supported.
  2. "NOT_SUPPORTED" — no passage in EVIDENCE entails the claim, OR the
                        claim introduces a number / dose / threshold not in
                        EVIDENCE. Default to NOT_SUPPORTED when uncertain.
  3. (Never output a third verdict; if you cannot decide, choose
     NOT_SUPPORTED — the eval harness handles judge-call failures separately.)

Reply with strict JSON:
  {{"verdict": "SUPPORTED" | "NOT_SUPPORTED", "reason": "<one sentence>"}}
"""


Verdict = Literal["SUPPORTED", "NOT_SUPPORTED", "UNVERIFIED"]


def _judge_client() -> tuple[openai.AsyncOpenAI, str]:
    """Same resolution order as v1: JUDGE_LLM_* > STAGE5_LLM_* > LLM_*.
    Picking a different vendor here is the right long-term fix; v2 ships
    with the rigorous-critic prompt as the no-cost workaround."""
    base = (
        os.getenv("JUDGE_LLM_BASE_URL")
        or os.getenv("STAGE5_LLM_BASE_URL")
        or os.getenv("LLM_BASE_URL")
    )
    key = (
        os.getenv("JUDGE_LLM_API_KEY")
        or os.getenv("STAGE5_LLM_API_KEY")
        or os.getenv("LLM_API_KEY")
    )
    model = (
        os.getenv("JUDGE_LLM_CHOICE")
        or os.getenv("STAGE5_LLM_CHOICE")
        or os.getenv("LLM_CHOICE", "gpt-4o")
    )
    return openai.AsyncOpenAI(base_url=base, api_key=key), model


async def judge_claim(
    sem: asyncio.Semaphore,
    client: openai.AsyncOpenAI,
    model: str,
    context: str,
    claim: str,
    *,
    max_retries: int = 2,
    retry_base_s: float = 4.0,
) -> Verdict:
    """Return SUPPORTED, NOT_SUPPORTED, or UNVERIFIED (judge exception).

    Retries on 429 with exponential backoff. After max_retries exhausted,
    returns UNVERIFIED so the claim is *excluded* from the faithfulness
    denominator rather than counted as a hallucination.
    """
    async with sem:
        attempt = 0
        while True:
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": JUDGE_PROMPT.format(
                                context=context[:60000], claim=claim
                            ),
                        }
                    ],
                    temperature=0,
                    response_format={"type": "json_object"},
                )
                raw = resp.choices[0].message.content or ""
                parsed = json.loads(raw)
                verdict = str(parsed.get("verdict", "")).upper()
                if verdict in ("SUPPORTED", "NOT_SUPPORTED"):
                    return verdict  # type: ignore[return-value]
                # Malformed verdict counts as UNVERIFIED (judge failed to comply).
                return "UNVERIFIED"
            except openai.RateLimitError:
                attempt += 1
                if attempt > max_retries:
                    return "UNVERIFIED"
                await asyncio.sleep(retry_base_s * (2 ** (attempt - 1)))
            except Exception:
                # Any other transport / parse error → UNVERIFIED.
                return "UNVERIFIED"


def aggregate(rows: list[dict]) -> dict:
    """Compute v2 metrics across captured rows.

    mean_faithfulness — across all judged claims (supported / non-unverified)
    unsupported_rate  — across all judged claims (not_supported / non-unverified)
    severe_hallucination_rate
                       — % of plans where ≥30% of judged claims are unsupported
                         (clinically meaningful threshold)
    coverage_rate     — % of plans where ≥50% of claims got a real verdict
                         (signals whether the run had enough rate-limit headroom)
    """
    if not rows:
        return {}
    sup_total = sum(r["n_supported"] for r in rows)
    not_total = sum(r["n_not_supported"] for r in rows)
    unv_total = sum(r["n_unverified"] for r in rows)
    judged = sup_total + not_total
    severe = sum(1 for r in rows if r.get("severe_hallucination") == 1.0)
    well_covered = sum(1 for r in rows if r.get("coverage_ratio", 0.0) >= 0.5)
    return {
        "n":                        len(rows),
        "total_claims":             sup_total + not_total + unv_total,
        "claims_supported":         sup_total,
        "claims_not_supported":     not_total,
        "claims_unverified":        unv_total,
        "mean_faithfulness":        (sup_total / judged) if judged else 0.0,
        "unsupported_rate":         (not_total / judged) if judged else 0.0,
        "severe_hallucination_rate": severe / len(rows),
        "coverage_rate":            well_covered / len(rows),
    }


async def main(n: int, concurrency: int, between_cases_s: float):
    gold = load_jsonl("clinical_qa_gold.jsonl")[:n]
    judge_client, judge_model = _judge_client()
    sem = asyncio.Semaphore(concurrency)
    rows: list[dict] = []

    for idx, item in enumerate(gold, 1):
        gid = item.get("id") or f"row{idx}"
        print(f"[run] {idx}/{len(gold)}  {gid}", flush=True)
        try:
            case = to_patient_case(item["patient_case"])
            ddx = await stage_2_ddx(case, top_k=5)
            cpgs = await stage_3_route(ddx)
            evidence = await stage_4_retrieve(case, ddx, cpgs)
            plan = await stage_5_synthesize(case, ddx, cpgs, evidence)

            context_blob = "\n\n".join(c.content for c in evidence)
            claims = treatment_plan_claims(plan)
            n_claims = len(claims)

            verdicts: list[Verdict] = await asyncio.gather(*[
                judge_claim(sem, judge_client, judge_model, context_blob, c)
                for c in claims
            ])
            sup = sum(1 for v in verdicts if v == "SUPPORTED")
            nsup = sum(1 for v in verdicts if v == "NOT_SUPPORTED")
            unv = sum(1 for v in verdicts if v == "UNVERIFIED")
            judged = sup + nsup
            faith = (sup / judged) if judged else 0.0
            unsup_rate = (nsup / judged) if judged else 0.0
            severe = 1.0 if (judged and (nsup / judged) >= 0.30) else 0.0
            coverage = (judged / n_claims) if n_claims else 0.0

            rows.append({
                "id": gid,
                "n_claims": n_claims,
                "n_supported": sup,
                "n_not_supported": nsup,
                "n_unverified": unv,
                "faithfulness": round(faith, 4),
                "unsupported_rate": round(unsup_rate, 4),
                "severe_hallucination": severe,
                "coverage_ratio": round(coverage, 4),
            })
            print(
                f"[done] {gid}  sup={sup}/{n_claims}  not={nsup}  unv={unv}  "
                f"faith={faith:.3f}  severe={'Y' if severe else 'n'}",
                flush=True,
            )
        except Exception as exc:
            print(f"[fail] {gid}  {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            rows.append({
                "id": gid,
                "n_claims": 0,
                "n_supported": 0,
                "n_not_supported": 0,
                "n_unverified": 0,
                "faithfulness": 0.0,
                "unsupported_rate": 0.0,
                "severe_hallucination": 0.0,
                "coverage_ratio": 0.0,
                "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            })
        await asyncio.sleep(between_cases_s)

    summary = {
        "judge_model": judge_model,
        **aggregate(rows),
    }
    print_summary("Faithfulness v2 (rigorous critic prompt + three-way verdict)", summary)
    write_results("faithfulness_v2", rows, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="how many gold items to evaluate (default 10)")
    parser.add_argument("--concurrency", type=int, default=2, help="parallel judge calls per item (default 2)")
    parser.add_argument("--sleep", type=float, default=4.0, help="seconds between cases (default 4.0)")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.concurrency, args.sleep))
