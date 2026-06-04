"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Validation Layer E (End-to-end clinical correctness)
         →  Full pipeline: Stage 2 → 3 → 4 → 5 via run_clinical_workflow
═══════════════════════════════════════════════════════════════════════════════
For each clinical_qa_gold.jsonl item we run the full workflow and check:
  - ICD routing landed on expected ICD
  - CPG selection includes expected CPG title
  - TreatmentPlan text contains every expected action term
  - TreatmentPlan does not contain forbidden terms
  - All safety_criteria terms appear (red flags, monitoring, etc.)

The TreatmentPlan is flattened to a single string by _helpers.treatment_plan_to_text.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import asyncio

from agent.clinical_workflow import run_clinical_workflow

from eval._helpers import to_patient_case, treatment_plan_to_text
from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import contains_match, mean


async def main():
    gold = load_jsonl("clinical_qa_gold.jsonl")
    rows = []
    for item in gold:
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
            "stage_errors": "|".join(result.stage_errors),
        })

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
    print_summary("End-to-End (Full pipeline)", summary)
    write_results("e2e", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
