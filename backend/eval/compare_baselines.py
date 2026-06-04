"""
═══════════════════════════════════════════════════════════════════════════════
 Tests:  Comparative justification of your design (vs naive baselines)
═══════════════════════════════════════════════════════════════════════════════
Three variants on the SAME clinical_qa_gold.jsonl items:

  1. vanilla    — raw LLM, no retrieval at all
  2. naive_rag  — single unscoped vector search → context-stuff → LLM
                  (NO DDx routing, NO scope filter, NO Pydantic plan)
  3. full       — your full agentic workflow

Scoring is identical to run_e2e_eval (action recall, forbidden, safety) so
the rows of this CSV stack directly under the E2E numbers for your bar chart.

Variants 1 & 2 output free-form text (no TreatmentPlan), so we score against
the raw string. Variant 3 reuses treatment_plan_to_text().
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import asyncio
import json
import os

import openai

from agent.tools import vector_search_tool, VectorSearchInput
from agent.clinical_workflow import run_clinical_workflow

from eval._helpers import to_patient_case, treatment_plan_to_text
from eval.io_utils import load_jsonl, write_results, print_summary
from eval.metrics import contains_match, mean


def _llm_client() -> tuple[openai.AsyncOpenAI, str]:
    base = os.getenv("LLM_BASE_URL")
    key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_CHOICE", "gpt-4o")
    return openai.AsyncOpenAI(base_url=base, api_key=key), model


async def variant_vanilla(case_dict: dict) -> str:
    """Variant 1: raw LLM, NO retrieval."""
    client, model = _llm_client()
    prompt = (
        "You are a clinical assistant. Given this patient case, propose an evidence-based "
        "treatment plan. Cite which CPG you would use.\n\n"
        f"Patient case: {json.dumps(case_dict, indent=2)}"
    )
    resp = await client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}], temperature=0.1,
    )
    return resp.choices[0].message.content or ""


async def variant_naive_rag(case_dict: dict) -> str:
    """Variant 2: ONE vector search over ALL chunks → context → LLM. No routing."""
    client, model = _llm_client()
    case = to_patient_case(case_dict)
    query = case.chief_complaint
    hits = await vector_search_tool(VectorSearchInput(query=query, limit=10, document_id_filter=None))
    context = "\n\n".join(f"[{i+1}] {h.document_title}\n{h.content[:2000]}" for i, h in enumerate(hits))

    prompt = (
        "Use the CPG context below to propose an evidence-based treatment plan for the patient. "
        "Cite the CPG section by number.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"PATIENT:\n{json.dumps(case_dict, indent=2)}"
    )
    resp = await client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}], temperature=0.1,
    )
    return resp.choices[0].message.content or ""


async def variant_full(case_dict: dict) -> str:
    """Variant 3: your full pipeline (DDx → route → scoped retrieval → synth)."""
    case = to_patient_case(case_dict)
    result = await run_clinical_workflow(case)
    return treatment_plan_to_text(result.treatment_plan)


VARIANTS = {
    "vanilla":   variant_vanilla,
    "naive_rag": variant_naive_rag,
    "full":      variant_full,
}


def _score(plan_text: str, item: dict) -> dict:
    action_recall = contains_match(plan_text, item["expected_answer_contains"])
    forbidden = any(t.lower() in plan_text.lower() for t in item.get("must_not_contain", []))
    safety_ok = contains_match(plan_text, item.get("safety_criteria", []))
    return {
        "action_recall": action_recall,
        "forbidden": float(forbidden),
        "safety": safety_ok,
        "pass": float(bool(action_recall) and bool(safety_ok) and not forbidden),
    }


async def main():
    gold = load_jsonl("clinical_qa_gold.jsonl")
    rows = []
    for item in gold:
        row = {"id": item["id"]}
        for name, runner in VARIANTS.items():
            try:
                plan = await runner(item["patient_case"])
            except Exception as exc:
                print(f"[warn] {item['id']} {name} failed: {exc}")
                plan = ""
            s = _score(plan, item)
            for k, v in s.items():
                row[f"{name}_{k}"] = v
        rows.append(row)

    summary = {"n": len(rows)}
    for name in VARIANTS:
        summary[f"{name}_pass_rate"]      = mean(r[f"{name}_pass"] for r in rows)
        summary[f"{name}_action_recall"]  = mean(r[f"{name}_action_recall"] for r in rows)
        summary[f"{name}_safety"]         = mean(r[f"{name}_safety"] for r in rows)
        summary[f"{name}_forbidden_rate"] = mean(r[f"{name}_forbidden"] for r in rows)

    print_summary("Baseline comparison", summary)
    write_results("baselines", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
