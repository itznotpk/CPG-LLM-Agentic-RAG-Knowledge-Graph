"""
Safety Critic Agent — post-Stage-5 independent medication safety review.

Generator → Evaluator pattern: this module receives only the TreatmentPlan and
PatientCase (never Stage 5's reasoning chain) and plays Devil's Advocate, checking
for allergy, interaction, dose, and contraindication concerns.

Fail-open: a failed critic call returns an empty SafetyReport so the clinician
always sees the care plan, and a warning is logged.
"""
from __future__ import annotations
import json
import logging
import os

import openai
from pydantic import ValidationError

from .models import PatientCase, TreatmentPlan, SafetyFlag, SafetyReport  # noqa: F401 re-export

logger = logging.getLogger(__name__)

SAFETY_CRITIC_SYSTEM = """You are a clinical pharmacist performing an independent medication safety review.

You have NOT seen the reasoning that produced this treatment plan. Your ONLY job is to find reasons it could harm THIS SPECIFIC patient. Do not justify the plan. Do not summarise it.

For each pharmacological recommendation (recommendations[*] where type == 'pharmacological'), check:

1. flag_type "drug_allergy" — Does the drug, its class, or a known cross-reactant conflict with any listed allergy?
   For sulfa/sulfonamide allergy specifically, check ALL of these sulfonamide-derived drugs even though they are
   not sulfa antibiotics: furosemide, hydrochlorothiazide, indapamide, chlorthalidone, gliclazide, glibenclamide,
   glipizide, celecoxib, acetazolamide, probenecid, sumatriptan. Flag as MODERATE (or MAJOR if history of
   anaphylaxis to sulfa).
   Example: sulfa allergy + furosemide → cross-reactivity risk → flag_type "drug_allergy" severity MODERATE
2. flag_type "drug_interaction" — Does the drug interact dangerously with any current medication?
   Example: warfarin + new NSAID → bleeding risk
3. flag_type "dose" — Is the implicit dose appropriate for the patient's renal/hepatic function inferred from comorbidities and vitals?
   Example: metformin standard dose + CKD Stage 4 eGFR<30 → contraindicated
4. flag_type "contraindication" — Is the drug contraindicated given any listed comorbidity or vital sign?
   Example: non-cardioselective beta-blocker + severe asthma → bronchospasm risk

Flag EVERY concern you find. Do not suppress concerns because the plan "looks reasonable overall". Conversely, do NOT invent concerns — return an empty flags array if you find none.

Severity scale:
- CRITICAL : life-threatening if the plan is enacted as written (e.g. PDE5i + nitrate)
- MAJOR    : significant harm likely without modification (e.g. wrong dose in renal failure)
- MODERATE : monitoring or dose adjustment warranted, not an outright stop

For each flag, set recommendation_index to the 0-based index of the recommendation in the input array. Provide a one-sentence patient-specific detail. Suggest an alternative only if one is clearly clinically supported.

Set safe_to_proceed = false if ANY CRITICAL or MAJOR flag is present, else true.

Return a valid SafetyReport JSON object with this exact shape — no markdown fences, no preamble:
{"flags": [{"severity": "CRITICAL|MAJOR|MODERATE", "recommendation_index": 0, "flag_type": "drug_allergy|drug_interaction|dose|contraindication", "detail": "...", "suggested_alternative": "...or null"}], "safe_to_proceed": true, "reviewer_notes": "...or null"}"""


async def run_safety_critic(
    case: PatientCase,
    plan: TreatmentPlan,
    emit=None,
) -> SafetyReport:
    """Adversarial post-hoc review of the TreatmentPlan for this patient.

    Returns an empty-flags SafetyReport if the critic call fails — fail-open
    rather than fail-closed, because a missing safety review must not block
    the clinician seeing the plan.
    """
    base_url = os.getenv("SAFETY_CRITIC_LLM_BASE_URL") or os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("SAFETY_CRITIC_LLM_API_KEY") or os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    # Prefer a cheaper/faster model for the critic; fall back to Stage 5 model
    stage5_model = os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")
    model = os.getenv("SAFETY_CRITIC_MODEL", stage5_model)

    client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)

    user_prompt = json.dumps({
        "patient": {
            "age": case.age,
            "sex": case.sex,
            "comorbidities": case.comorbidities,
            "current_medications": case.current_medications,
            "allergies": case.allergies,
            "vitals": case.vitals,
            "severity_staging": getattr(case, "severity_staging", {}) or {},
        },
        "recommendations": [
            {
                "index": i,
                "type": r.type,
                "action": getattr(r, "action", None),
                "intervention": r.intervention,
            }
            for i, r in enumerate(plan.recommendations)
        ],
    }, ensure_ascii=False)

    if emit:
        await emit("sub_step", {"stage": 6, "detail": "Safety review running…", "status": "running"})

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SAFETY_CRITIC_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw_json = resp.choices[0].message.content.strip()
        data = json.loads(raw_json)
        report = SafetyReport.model_validate(data)
        # Enforce the safe_to_proceed invariant regardless of LLM choice
        report.safe_to_proceed = not any(f.severity in ("CRITICAL", "MAJOR") for f in report.flags)
        return report
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning("Safety critic failed (%s); returning empty report (fail-open)", exc)
        return SafetyReport(
            flags=[],
            safe_to_proceed=True,
            reviewer_notes=f"Safety review unavailable: {exc.__class__.__name__}",
        )
