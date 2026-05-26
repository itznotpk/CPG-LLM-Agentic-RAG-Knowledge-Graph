"""
Safety Critic Agent — post-Stage-5 independent medication safety review.

Generator → Evaluator pattern: this module receives only the TreatmentPlan and
PatientCase (never Stage 5's reasoning chain) and plays Devil's Advocate, checking
for allergy, interaction, dose, and contraindication concerns.

Fail-open: a failed critic call returns an empty SafetyReport so the clinician
always sees the care plan, and a warning is logged.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os

import openai
from pydantic import ValidationError

from .models import PatientCase, TreatmentPlan, SafetyFlag, SafetyReport  # noqa: F401 re-export
from .graph_clinical import clinical_graph_lookup, match_plan_drugs, ClinicalFlag, build_patient_params, _norm as _kg_norm
from .providers import make_vertex_client

logger = logging.getLogger(__name__)

def _load_prompt(filename: str) -> str:
    """Load a prompt from agent/prompts/<filename>. Falls back to empty string on error."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    try:
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("Prompt file not found: %s", prompt_path)
        return ""


SAFETY_CRITIC_SYSTEM = _load_prompt("stage6_safety_critic.txt")


# ---------------------------------------------------------------------------
# KG verification pass (hybrid Agent 1 — deterministic fact-check of FINAL plan)
# ---------------------------------------------------------------------------

# KG flag_type → SafetyFlag.flag_type. MONITORING was previously omitted as
# workflow guidance; surfacing it as `dose` (closest existing SafetyFlag bucket)
# lets renal/eGFR-tier rules reach the clinician without inventing a new flag
# type. If this proves noisy in practice, gate by `threshold_breach is True`.
_KG_FLAG_TYPE_MAP = {
    "INTERACTION":      "drug_interaction",
    "ALLERGY_CROSS":    "drug_allergy",
    "CONTRAINDICATION": "contraindication",
    "DOSE_ADJUSTMENT":  "dose",
    "MONITORING":       "dose",
}


def _kg_severity_to_safety(sev: str | None) -> str:
    """Map KG severity (MAJOR/MODERATE/MINOR/UNSPECIFIED/None) to SafetyFlag
    severity (CRITICAL/MAJOR/MODERATE). KG never emits CRITICAL today, so the
    conservative default for missing/MINOR is MODERATE."""
    if sev == "MAJOR":
        return "MAJOR"
    if sev == "MODERATE":
        return "MODERATE"
    return "MODERATE"


def _kg_flag_to_safety(
    cf: ClinicalFlag,
    drug_idx_map: dict,
    pharm_recommendation_indices: list[int],
) -> SafetyFlag | None:
    """Convert a KG ClinicalFlag into a SafetyFlag(source="graph"), mapping the
    drug back to the TreatmentPlan.recommendations index it came from."""
    safety_type = _KG_FLAG_TYPE_MAP.get(cf.flag_type)
    if safety_type is None:
        return None
    iv_idx = drug_idx_map.get(_kg_norm(cf.subject))
    if iv_idx is None or iv_idx >= len(pharm_recommendation_indices):
        rec_index = 0  # safe fallback — clinician still sees the flag
    else:
        rec_index = pharm_recommendation_indices[iv_idx]
    evidence_snippet = (cf.evidence or "").strip()[:160]
    relation_pretty = cf.relation.replace("_", " ").lower()
    detail = f"{cf.subject} {relation_pretty} {cf.object}."
    if evidence_snippet:
        detail = f"{detail} Evidence: {evidence_snippet}"

    severity = _kg_severity_to_safety(cf.severity)

    # Typed-threshold awareness: if the patient actually meets the rule's numeric
    # condition (breach=True), surface that fact and escalate one severity step.
    # If the patient clearly does not (breach=False), append a note so the clinician
    # understands why the flag is informational rather than actionable.
    if cf.threshold_param and cf.threshold_op and cf.threshold_value is not None:
        v2 = f"-{cf.threshold_value2}" if cf.threshold_value2 is not None else ""
        unit = f" {cf.threshold_unit}" if cf.threshold_unit else ""
        rule_str = f"{cf.threshold_param} {cf.threshold_op} {cf.threshold_value}{v2}{unit}".strip()
        if cf.threshold_breach is True:
            detail = f"{detail} Patient meets threshold ({rule_str}); rule is actionable."
            if severity == "MODERATE":
                severity = "MAJOR"
            elif severity == "MAJOR":
                severity = "CRITICAL"
        elif cf.threshold_breach is False:
            detail = f"{detail} Threshold ({rule_str}) not met by this patient — informational."
        else:
            detail = f"{detail} Threshold: {rule_str} (patient value unknown)."

    return SafetyFlag(
        title=f"{cf.subject} - {relation_pretty} caution",
        severity=severity,
        recommendation_index=rec_index,
        flag_type=safety_type,
        detail=detail,
        suggested_alternative=None,
        source="graph",
    )


async def _kg_verify_plan(case: PatientCase, plan: TreatmentPlan) -> list[SafetyFlag]:
    """Deterministic post-Stage-5 KG verification of the final TreatmentPlan.

    Different from the pre-Stage-5 `clinical_graph_lookup` in two ways:
    (1) the candidate drug set comes from the **final plan's recommendations**
        (what the patient would actually receive), not chunk-derived candidates;
    (2) the output is merged into the `SafetyReport` the clinician sees, not into
        the synthesis prompt the LLM consumes.

    Fail-open with one retry on transient errors — a Neo4j connection reset has
    been observed in the wild and shouldn't drop the whole safety pass.
    """
    pharm = [
        (i, r.intervention) for i, r in enumerate(plan.recommendations)
        if r.type == "pharmacological"
    ]
    if not pharm:
        return []
    pharm_recommendation_indices = [i for i, _ in pharm]
    interventions = [iv for _, iv in pharm]

    for attempt in (1, 2):
        try:
            drug_idx_map = await match_plan_drugs(interventions)
            if not drug_idx_map:
                return []
            kg_flags = await clinical_graph_lookup(
                patient_meds=case.current_medications,
                candidate_drugs=list(drug_idx_map.keys()),
                comorbidities=case.comorbidities,
                allergies=case.allergies,
                patient_params=build_patient_params(case),
            )
            out: list[SafetyFlag] = []
            for cf in kg_flags:
                sf = _kg_flag_to_safety(cf, drug_idx_map, pharm_recommendation_indices)
                if sf is not None:
                    out.append(sf)
            logger.info(
                "KG verify: %d graph-sourced safety flags from %d KG flags (plan drugs: %d)",
                len(out), len(kg_flags), len(drug_idx_map),
            )
            return out
        except Exception as exc:
            logger.warning(
                "KG verify attempt %d failed (%s)%s",
                attempt, exc, "; retrying" if attempt == 1 else "; giving up (fail-open)",
            )
    return []


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
    provider = os.getenv("SAFETY_CRITIC_LLM_PROVIDER", "")
    # Prefer a cheaper/faster model for the critic; fall back to Stage 5 model
    stage5_model = os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")
    model = os.getenv("SAFETY_CRITIC_MODEL", stage5_model)

    if provider.lower() == "vertex" or api_key == "vertex-adc":
        client = make_vertex_client(base_url)
    else:
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

    # Hybrid Agent 1: run the LLM adversarial critic AND the deterministic KG
    # verification of the final plan concurrently, then merge.
    async def _llm_critic() -> SafetyReport:
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
            raw_json = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw_json)
            rep = SafetyReport.model_validate(data)
            return rep
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            logger.warning("Safety critic LLM failed (%s); fail-open empty LLM report", exc)
            return SafetyReport(
                flags=[],
                safe_to_proceed=True,
                reviewer_notes=f"LLM safety review unavailable: {exc.__class__.__name__}",
            )

    llm_report, kg_flags = await asyncio.gather(
        _llm_critic(),
        _kg_verify_plan(case, plan),
        return_exceptions=False,  # both halves already fail-open internally
    )

    # Merge — keep BOTH sources (safety: don't hide concerns by deduping). Each
    # flag carries `source` so the UI can tag graph-verified ones distinctly.
    merged_flags = list(llm_report.flags) + list(kg_flags)
    safe_to_proceed = not any(f.severity in ("CRITICAL", "MAJOR") for f in merged_flags)

    notes = llm_report.reviewer_notes
    if kg_flags:
        graph_note = f"{len(kg_flags)} graph-verified flag(s) added from Neo4j KG"
        notes = f"{notes} | {graph_note}" if notes else graph_note

    return SafetyReport(flags=merged_flags, safe_to_proceed=safe_to_proceed, reviewer_notes=notes)
