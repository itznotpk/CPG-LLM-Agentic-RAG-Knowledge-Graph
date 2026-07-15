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

PATIENT CASE (the patient's own presentation + existing regimen — an AUTHORITATIVE grounding
source for CONTINUE/maintain claims, NOT for new prescriptions):
{patient}

CLAIM:
{claim}

Reply with strict JSON: {{"supported": true|false, "reason": "<one sentence>"}}.

Judge the CLAIM's CORE clinical content — the parameter monitored, the drug/action recommended,
the intervention proposed — against EVIDENCE (and, for continue/maintain claims, PATIENT CASE).
Apply these rules:

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

4. CONTINUE / MAINTENANCE (be fair): if the claim is to CONTINUE, MAINTAIN, or keep an existing drug
   — and that drug (with its dose/frequency, if stated) appears in PATIENT CASE as something the
   patient is ALREADY ON — mark SUPPORTED. The dose is grounded in the patient's existing regimen and
   need NOT also appear in EVIDENCE. This exemption is ONLY for continue/maintain claims; a NEW
   start/initiate/switch drug or dose still must satisfy rule 1 against EVIDENCE.

Vague paraphrases of evidence are supported. When the core clinical claim is grounded and only an
operational/eligibility qualifier is missing, set supported=true and note the missing qualifier in reason."""


def _case_blob(case) -> str:
    """Compact patient-case context for the judge — chiefly the existing regimen,
    which is where 'continue current dose' claims get their grounding (the gold's
    doses live in `history`/`current_medications`, never in the CPG EVIDENCE)."""
    parts: list[str] = []
    if getattr(case, "chief_complaint", None):
        parts.append(f"Presentation: {case.chief_complaint}")
    if getattr(case, "history", None):
        parts.append(f"History: {case.history}")
    meds = getattr(case, "current_medications", None) or []
    if meds:
        parts.append("Current medications: " + "; ".join(str(m) for m in meds))
    comorb = getattr(case, "comorbidities", None) or []
    if comorb:
        parts.append("Comorbidities: " + "; ".join(str(c) for c in comorb))
    return "\n".join(parts) or "(no additional case context)"


def _judge_client() -> tuple[openai.AsyncOpenAI, str]:
    # Judge ≠ author: default to Gemini, NOT the STAGE5/LLM (MiMo) synthesis model,
    # so a model never grades its own plan. Explicit JUDGE_LLM_* still wins.
    base = os.getenv("JUDGE_LLM_BASE_URL") or os.getenv("GEMINI_BASE_URL")
    key = os.getenv("JUDGE_LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = os.getenv("JUDGE_LLM_CHOICE") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return openai.AsyncOpenAI(base_url=base, api_key=key), model


async def judge_claim(client: openai.AsyncOpenAI, model: str, context: str, claim: str, patient: str = "") -> tuple[bool, str, bool]:
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
                messages=[{"role": "user", "content": JUDGE_PROMPT.format(context=context[:60000], patient=patient[:4000], claim=claim)}],
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


def _cache_path(stamp: str) -> str:
    """Sibling of the result files; holds generated plans so a judge-only rerun
    is deterministic (same plans both runs → score delta is ONLY the judge change)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "results", f"faithfulness_plans_{stamp}.json")


async def _generate_cache(gold: list) -> list[dict]:
    """Run stages 2→5 once per case and capture {id, claims, context, patient}.

    This is the expensive, non-deterministic half (MiMo synthesis + Gemini rerank).
    Isolating it behind a cache lets us re-judge the SAME plans when only the judge
    changes — otherwise synthesis jitter (±13% seen on qa_009) swamps the A/B."""
    cache = []
    for item in gold:
        try:
            case = to_patient_case(item["patient_case"])
            ddx = await stage_2_ddx(case, top_k=5)
            cpgs = await stage_3_route(ddx)
            evidence = await stage_4_retrieve(case, ddx, cpgs)
            plan = await stage_5_synthesize(case, ddx, cpgs, evidence)
        except Exception as e:
            print(f"[skip] case {item['id']}: pipeline error {e}")
            continue
        cpg_evidence_texts = [c.content for c in evidence]
        # `plan` is the TreatmentPlan Pydantic object stage_5_synthesize returns
        # (not a dict), so ebm_evidence is a List[EbmEvidence] of attribute-access
        # objects, not dicts. Append their abstracts so literature-grounded claims
        # aren't judged "unsupported" for lacking CPG-text grounding.
        ebm_texts = [
            f"[Literature: {e.journal} {e.year or ''}] {e.title}. {e.abstract_snippet}"
            for e in (plan.ebm_evidence or [])
        ]
        evidence_for_judge = cpg_evidence_texts + ebm_texts
        cache.append({
            "id": item["id"],
            "claims": treatment_plan_claims(plan),
            "context": "\n\n".join(evidence_for_judge),
            "patient": _case_blob(case),
        })
    return cache


async def main(limit: int | None = None, from_cache: str | None = None, no_case_context: bool = False):
    judge_client, judge_model = _judge_client()
    sem = asyncio.Semaphore(4)  # cap concurrent judge calls — bursts of 20 trip Gemini 503

    async def _judge(context, c, patient):
        async with sem:
            return await judge_claim(judge_client, judge_model, context, c, patient)

    if from_cache:
        with open(from_cache, encoding="utf-8") as fh:
            cache = json.load(fh)
        print(f"[cache] re-judging {len(cache)} cached plans from {from_cache}")
    else:
        gold = load_jsonl("clinical_qa_gold.jsonl")
        if limit:
            gold = gold[:limit]
        cache = await _generate_cache(gold)
        from datetime import datetime
        path = _cache_path(datetime.now().strftime("%Y%m%d_%H%M%S"))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=1)
        print(f"[cache] saved {len(cache)} plans to {path} (re-judge with --from-cache)")

    rows = []
    for entry in cache:
        claims = entry["claims"]
        context_blob = entry["context"]
        # Lever A off (--no-case-context): blank the patient block so the judge
        # sees ONLY the CPG evidence, replicating the pre-Lever-A behaviour for a
        # clean, deterministic A/B against the same cached plans.
        patient_blob = "" if no_case_context else entry.get("patient", "")

        verdicts = await asyncio.gather(*[_judge(context_blob, c, patient_blob) for c in claims])
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
            "id": entry["id"],
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
    ap.add_argument("--from-cache", type=str, default=None,
                    help="Re-judge plans from a faithfulness_plans_*.json cache instead of "
                         "regenerating them. Use for a deterministic judge-only A/B.")
    ap.add_argument("--no-case-context", action="store_true",
                    help="Lever A OFF: hide the patient case from the judge (pre-Lever-A "
                         "behaviour). Pair with --from-cache for a clean A/B on identical plans.")
    args = ap.parse_args()
    asyncio.run(main(limit=args.limit, from_cache=args.from_cache, no_case_context=args.no_case_context))
