"""
Throttled subsample variant of `run_e2e_eval`.

Same logic, but:
 - Sub-samples to the first N items (default 10) so the eval fits one provider quota window.
 - Adds a per-item sleep so successive workflow invocations don't burst the LLM provider.
 - Prints per-item progress so a 429 partway through is visible.
 - Coerces stage_errors to strings (the original used "|".join on StageError objects).
 - Writes to eval/results/e2e_throttled_<stamp>.{csv,json}.

Use this when the full `run_e2e_eval` hits 429 — it produces statistically weaker
(smaller-n) but real, captured numbers instead of zero.
"""
from __future__ import annotations
import argparse
import asyncio

from agent.clinical_workflow import run_clinical_workflow

from eval._helpers import to_patient_case, treatment_plan_to_text
from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import contains_match, mean


async def main(n: int, between_cases_s: float):
    gold = load_jsonl("clinical_qa_gold.jsonl")[:n]
    rows: list[dict] = []

    for idx, item in enumerate(gold, 1):
        print(f"[run] {idx}/{len(gold)}  {item.get('id')}", flush=True)
        try:
            case = to_patient_case(item["patient_case"])
            result = await run_clinical_workflow(case)

            plan_text = treatment_plan_to_text(result.treatment_plan)
            predicted_icd = result.treatment_plan.icd_primary
            cpg_names = " | ".join(c.cpg_name for c in result.cpgs)

            icd_ok = float(predicted_icd == item["expected_icd"])
            cpg_ok = float(item["expected_cpg"].lower() in cpg_names.lower())
            action_recall = contains_match(plan_text, item["expected_answer_contains"])
            forbidden = any(t.lower() in plan_text.lower() for t in item.get("must_not_contain", []))
            safety_ok = contains_match(plan_text, item.get("safety_criteria", []))

            overall = float(bool(icd_ok) and bool(cpg_ok) and bool(action_recall) and bool(safety_ok) and not forbidden)
            rows.append({
                "id": item["id"],
                "predicted_icd": predicted_icd,
                "predicted_cpgs": cpg_names[:80],
                "icd_routing_correct": icd_ok,
                "cpg_routing_correct": cpg_ok,
                "expected_actions_present": action_recall,
                "forbidden_present": float(forbidden),
                "safety_criteria_met": safety_ok,
                "overall_pass": overall,
                "elapsed_ms": result.elapsed_ms,
                "stage_errors": "|".join(str(e) for e in result.stage_errors),
            })
            print(f"[done] {item.get('id')}  pass={int(overall)}  elapsed={int(result.elapsed_ms)}ms", flush=True)
        except Exception as exc:
            print(f"[fail] {item.get('id')}  {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            rows.append({
                "id": item["id"],
                "predicted_icd": "",
                "predicted_cpgs": "",
                "icd_routing_correct": 0.0,
                "cpg_routing_correct": 0.0,
                "expected_actions_present": 0.0,
                "forbidden_present": 0.0,
                "safety_criteria_met": 0.0,
                "overall_pass": 0.0,
                "elapsed_ms": 0.0,
                "stage_errors": f"{type(exc).__name__}: {str(exc)[:160]}",
            })
        await asyncio.sleep(between_cases_s)

    summary = {
        "n": len(rows),
        "icd_routing_accuracy":      mean(r["icd_routing_correct"] for r in rows),
        "cpg_routing_accuracy":      mean(r["cpg_routing_correct"] for r in rows),
        "expected_action_recall":    mean(r["expected_actions_present"] for r in rows),
        "forbidden_content_rate":    mean(r["forbidden_present"] for r in rows),
        "safety_criteria_pass_rate": mean(r["safety_criteria_met"] for r in rows),
        "overall_pass_rate":         mean(r["overall_pass"] for r in rows),
        "mean_elapsed_ms":           mean(r["elapsed_ms"] for r in rows),
    }
    print_summary("End-to-End (Full pipeline) — throttled subsample", summary)
    write_results("e2e_throttled", rows, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="how many gold items to evaluate (default 10)")
    parser.add_argument("--sleep", type=float, default=5.0, help="seconds to wait between cases (default 5.0)")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.sleep))
