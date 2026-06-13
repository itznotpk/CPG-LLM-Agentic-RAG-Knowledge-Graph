"""
Pipeline stages 2–5 for the clinical RAG workflow.

  stage_2_ddx        — differential diagnosis via ICD-11 vector search
  stage_3_route      — map DDx codes to CPG documents
  stage_4_retrieve   — LLM-generated queries + scoped vector retrieval
  stage_5_synthesize — structured TreatmentPlan synthesis from evidence
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Literal

import openai
try:
    import tiktoken
except ImportError:  # pragma: no cover - only used before requirements are reinstalled
    tiktoken = None
from pydantic import BaseModel
from pydantic import ValidationError
from pydantic import model_validator

from .db_utils import db_pool
from .graph_clinical import ClinicalFlag, format_flags_for_prompt
from .models import ChunkResult, PatientCase, PriorVisitSummary, Recommendation, TreatmentPlan
from .routing import CPGDocRef, SEMANTIC_SCOPE_THRESHOLD, route_icd_to_cpgs
from .tools import VectorSearchInput, vector_search_tool
from .providers import make_vertex_client


def _make_openai_client(base_url: str, api_key: str, provider: str = "", **kwargs) -> openai.AsyncOpenAI:
    """Build AsyncOpenAI client, using Vertex ADC token when provider=='vertex'."""
    if provider.lower() == "vertex" or api_key == "vertex-adc":
        return make_vertex_client(base_url, **kwargs)
    return openai.AsyncOpenAI(base_url=base_url, api_key=api_key, **kwargs)

logger = logging.getLogger(__name__)


# Transient-error retry for LLM calls. Gemini's OpenAI-compat endpoint returns
# 503 ("This model is currently experiencing high demand") and 429 under load;
# these are recoverable spikes, not faults — yet every `stage_error` row in
# machine_signals was exactly one of these, uncaught, on the Stage-4 query-gen
# call. Retry with exponential backoff before letting the failure propagate.
_LLM_RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


def _is_transient_llm_error(exc: Exception) -> bool:
    """True for rate-limit / 5xx / timeout / connection blips worth retrying."""
    if isinstance(exc, (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
    )):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    return status in _LLM_RETRY_STATUS


async def _llm_call_with_retry(make_awaitable, *, what: str, attempts: int = 3, base_delay: float = 1.0):
    """Await ``make_awaitable()`` with exponential backoff on transient errors.

    ``make_awaitable`` is a zero-arg callable returning a *fresh* awaitable each
    invocation (a coroutine is single-use, so the call site must rebuild it).
    Non-transient errors re-raise immediately; transient ones retry up to
    ``attempts`` times (delays 1s, 2s, …) and re-raise the last on exhaustion.
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await make_awaitable()
        except Exception as exc:  # noqa: BLE001 — re-raised below unless transient
            if not _is_transient_llm_error(exc) or i == attempts - 1:
                raise
            last_exc = exc
            delay = base_delay * (2 ** i)
            logger.warning(
                "%s: transient LLM error (attempt %d/%d) — retrying in %.0fs: %s",
                what, i + 1, attempts, delay, exc,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None  # unreachable: loop either returns or raises
    raise last_exc


# Drug-class matcher used by the post-Stage-5 coverage-gap detector. Mirrors
# the JS DRUG_CLASS_KEYWORDS map in Doctor UI/src/components/sections/CarePlanSection.jsx
# — keep the two in sync when adding classes.
_PARSER_ERROR_DRUGS = {
    "pharmacological agent", "pharmacological", "drug", "agent",
    "pharmacological treatment", "medication", "medications",
}

# Specialist-initiated drugs: medication classes that require specialist ordering (Gap 7)
# Maps drug class/name → required specialty for initiation
_SPECIALIST_INITIATED_DRUGS: dict[str, list[str]] = {
    "rituximab": ["rheumatology", "oncology"],
    "biologic dmard": ["rheumatology"],
    "insulin": ["endocrinology", "diabetes"],
    "insulin pump": ["endocrinology"],
    "glp-1": ["endocrinology"],
    # ACE-i, MRA, SGLT2i are GP-initiable foundational therapy for HFrEF/T2DM/CKD
    # per Malaysian CPG; do not flag as specialist-only.
    "arni": ["cardiology"],
    "ivabradine": ["cardiology"],
    "sacubitril": ["cardiology"],
    "warfarin": ["cardiology", "haematology"],
    "doac": ["cardiology", "haematology"],
    "immunosuppressant": ["nephrology", "rheumatology", "gastroenterology"],
    "immunotherapy": ["oncology", "immunology"],
}

_DRUG_CLASS_KEYWORDS: dict[str, list[str]] = {
    "ace inhibitor": ["pril"],
    "angiotensin receptor blocker": ["sartan"],
    "arb": ["sartan"],
    "beta-blocker": ["olol", "carvedilol", "bisoprolol"],
    "b-blocker": ["olol"],
    "thiazide diuretic": ["thiazide", "chlorthalidone", "indapamide", "hydrochloro"],
    "thiazide diuretics": ["thiazide", "chlorthalidone", "indapamide", "hydrochloro"],
    "chlorthalidone": ["chlorthalidone"],
    "dihydropyridine ccb": ["dipine"],
    "long-acting calcium channel blocker": ["dipine", "amlodipine", "felodipine"],
    "ccb": ["dipine", "diltiazem", "verapamil", "amlodipine"],
    "calcium channel blocker": ["dipine", "diltiazem", "verapamil"],
    "k+ sparing diuretics": ["spironolactone", "amiloride", "eplerenone"],
    "dri": ["aliskiren"],
    "statin": ["statin"],
    "pcsk9 inhibitor": ["alirocumab", "evolocumab"],
    "basal insulin": ["insulin glargine", "insulin detemir", "insulin degludec",
                       "lantus", "tresiba", "levemir"],
    "metformin": ["metformin"],
    "sglt2 inhibitor": ["flozin"],
    "sglt2": ["flozin"],
    "glp-1 receptor agonist": ["glutide", "tide"],
    "glp-1": ["glutide"],
    "dpp-4 inhibitor": ["gliptin"],
    "sulfonylurea": ["gliclazide", "glimepiride", "glipizide", "glibenclamide"],
    "antiarrhythmic": ["amiodarone", "flecainide", "propafenone", "sotalol",
                       "dronedarone", "digoxin", "digitalis"],
    "antiarrhythmic medication": ["amiodarone", "flecainide", "propafenone", "sotalol",
                                  "dronedarone", "digoxin", "digitalis"],
    "class iii antiarrhythmic": ["amiodarone", "sotalol", "dronedarone"],
    "rate control": ["bisoprolol", "metoprolol", "atenolol", "diltiazem", "verapamil", "digoxin"],
    "rhythm control": ["amiodarone", "flecainide", "propafenone", "sotalol", "dronedarone"],
}


def _assess_case_severity(case: PatientCase) -> tuple[int, str]:
    """Assess patient case severity (0–3 scale) based on vitals, labs, staging.

    Returns: (severity_score, rationale) where:
      0 = stable/routine
      1 = moderate/monitoring needed
      2 = high/urgent intervention needed
      3 = critical/emergency

    Gap 5: Used for urgency-severity harmonization validation.
    """
    severity = 0
    rationale_parts = []

    # Check staging if available
    staging = getattr(case, "severity_staging", {}) or {}
    if staging:
        # Common critical stagings
        critical_stages = {"critical", "emergency", "acute decompensation", "unstable", "shock"}
        if any(str(v).lower() in critical_stages for v in staging.values()):
            severity = max(severity, 3)
            rationale_parts.append("critical staging detected")

    # Check vitals
    vitals = getattr(case, "vitals", {}) or {}
    if vitals:
        # Critical vital ranges
        hr = vitals.get("heart_rate")
        sbp = vitals.get("systolic_bp")
        o2 = vitals.get("oxygen_saturation")

        if hr and (hr > 120 or hr < 40):
            severity = max(severity, 2)
            rationale_parts.append(f"abnormal HR {hr}")
        if sbp and (sbp > 180 or sbp < 90):
            severity = max(severity, 2)
            rationale_parts.append(f"abnormal SBP {sbp}")
        if o2 and o2 < 90:
            severity = max(severity, 3)
            rationale_parts.append(f"hypoxia {o2}%")

    # Check comorbidities count (multiple comorbidities = higher complexity/urgency)
    comorbidities = getattr(case, "comorbidities", []) or []
    if len(comorbidities) >= 3:
        severity = max(severity, 1)
        rationale_parts.append(f"multiple comorbidities ({len(comorbidities)})")

    # Check history for acute events
    history = (getattr(case, "history", "") or "").lower()
    acute_terms = {"acute", "sudden", "emergency", "unstable", "decompensation", "infarction", "stroke"}
    if any(term in history for term in acute_terms):
        severity = max(severity, 2)
        rationale_parts.append("acute event in history")

    rationale = "; ".join(rationale_parts) if rationale_parts else "stable baseline"
    return severity, rationale


# Acute-presentation markers (Commandment-6 code-side counterpart). Time-critical
# problems whose visit should action the acute issue + safety-relevant interactions
# only — NOT a stable comorbidity's full chronic screening/maintenance programme.
_ACUTE_PRESENTATION_MARKERS = (
    "st elevation", "st-elevation", "stemi", "nstemi", "acute coronary",
    "acute mi", "myocardial infarction", "infarct", "chest pain",
    "stroke", "tia", "sepsis", "septic", "dka", "diabetic ketoacidosis",
    "anaphylaxis", "haemorrhage", "hemorrhage", "acute decompensation",
    "decompensated", "unstable", "hypoxia", "respiratory distress",
    "status epilepticus", "acute abdomen",
)


def _is_acute_presentation(case: PatientCase) -> bool:
    """True if the visit's PRIMARY reason is time-critical/emergent.

    Used to scope deterministic KG referral injection: on an acute visit, routine
    chronic-comorbidity referrals (e.g. newly-diagnosed-T2DM → ophthalmology/dental)
    are deferred to a future routine review rather than booked today. Mirrors the
    LLM-side Commandment 6 in stage5_synthesis.txt. Fail-open: if nothing matches,
    treat as non-acute (no suppression).
    """
    severity, _ = _assess_case_severity(case)
    if severity >= 2:
        return True
    parts: list[str] = []
    for attr in ("chief_complaint", "ecg", "history"):
        val = getattr(case, attr, None)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, (list, tuple)):
            parts.extend(str(x) for x in val)
    for x in (getattr(case, "symptoms", None) or []):
        parts.append(str(x))
    text = " ".join(parts).lower()
    return any(m in text for m in _ACUTE_PRESENTATION_MARKERS)


def _validate_urgency_severity_alignment(
    referral_urgency: str | None,
    case_severity: int,
) -> tuple[bool, str | None]:
    """Validate that referral urgency matches case severity (Gap 5).

    Returns: (is_aligned, recommendation) where:
      is_aligned: True if urgency matches severity
      recommendation: Suggested urgency upgrade if misaligned (None if aligned)

    Examples:
      - case_severity=3 (critical), urgency="routine" → (False, "urgent")
      - case_severity=1 (moderate), urgency="urgent" → (True, None)  [ok to be cautious]
      - case_severity=0 (stable), urgency="emergency" → (False, "routine")
    """
    urgency = (referral_urgency or "routine").strip().lower()
    urgency_priority = _referral_urgency_priority(urgency)

    # Map severity (0-3) to expected urgency priority (1-3)
    severity_to_priority = {0: 1, 1: 1, 2: 2, 3: 3}  # 0-1: routine ok, 2: urgent preferred, 3: emergency needed
    expected_min_priority = severity_to_priority.get(case_severity, 1)

    if urgency_priority >= expected_min_priority:
        # Aligned: urgency is sufficient for severity
        return True, None

    # Misaligned: urgency too low for severity
    priority_to_urgency = {1: "routine", 2: "urgent", 3: "emergency"}
    recommended = priority_to_urgency.get(expected_min_priority, "routine")
    return False, recommended


def _get_problematic_triggers(all_unresolved: list[str]) -> dict[str, int]:
    """Extract and aggregate unresolved referral triggers to identify patterns (Gap 6).

    Returns: dict of trigger_condition_pair → frequency count

    Analyzes unresolved_questions to find repeating trigger-condition failures.
    Used to warn about triggers with high historical failure rates.
    """
    trigger_failures: dict[str, int] = {}

    for question in all_unresolved:
        # Expected format: "Consider {specialty} referral ({urgency}) for {condition} IF: {trigger}"
        if "Consider" in question and "IF:" in question:
            try:
                # Extract trigger from "IF: {trigger}"
                trigger_part = question.split("IF:")[-1].strip()
                # Extract condition: "for {condition} IF"
                for_idx = question.find(" for ")
                if_idx = question.find(" IF:")
                if for_idx >= 0 and if_idx > for_idx:
                    condition = question[for_idx + 5 : if_idx].strip()
                    trigger_key = f"{condition}|{trigger_part}"
                    trigger_failures[trigger_key] = trigger_failures.get(trigger_key, 0) + 1
            except (IndexError, ValueError):
                pass

    return trigger_failures


def _assess_data_quality_issue(case: PatientCase, trigger: str) -> tuple[bool, str | None]:
    """Assess if trigger failure likely due to data quality (Gap 6).

    Returns: (is_data_quality_issue, issue_description)

    Checks if patient case has missing critical data that would prevent gate evaluation.
    """
    required_fields = []

    # Check what data the trigger likely needs
    trigger_lower = trigger.lower()

    if any(x in trigger_lower for x in ["hba1c", "glucose", "fasting", "blood sugar"]):
        labs = getattr(case, "labs", {}) or {}
        if not labs.get("hba1c") and not labs.get("glucose"):
            required_fields.append("HbA1c/glucose labs")

    if any(x in trigger_lower for x in ["bp", "blood pressure", "systolic", "diastolic"]):
        vitals = getattr(case, "vitals", {}) or {}
        if not vitals.get("systolic_bp") and not vitals.get("diastolic_bp"):
            required_fields.append("blood pressure vitals")

    if any(x in trigger_lower for x in ["egfr", "creatinine", "kidney"]):
        labs = getattr(case, "labs", {}) or {}
        if not labs.get("egfr") and not labs.get("creatinine"):
            required_fields.append("renal function labs")

    if any(x in trigger_lower for x in ["ejection fraction", "ef", "lvef", "cardiac"]):
        tests = getattr(case, "imaging", {}) or {}
        if not tests:
            required_fields.append("cardiac imaging/EF")

    if required_fields:
        return True, f"Missing critical data: {', '.join(required_fields)}"

    return False, None


_SWITCH_CONNECTORS = (
    "switch to ", "replace with ", "change to ", "substitute with ",
    "alternative: ", "alternative is ", "alternatives: ", "alternative from ",
    "use ", "consider ",
)


def _split_stop_switch_recs(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Materialise an explicit START rec when a STOP rec embeds a switch target.

    The synthesis LLM often emits a single `[STOP]` rec like
      'Discontinue Losartan — switch to Methyldopa 250-1000 mg ...; or Labetalol ...'
    which is clinically right but structurally collapses the swap. Downstream
    checks that scan for `action == "start"` of a pregnancy-safe agent then
    miss it. Walk each STOP rec; if its intervention names a switch target
    and no sibling START rec already exists for any extracted drug, emit a
    paired START rec citing the same source.

    Conservative: only splits STOP recs with an explicit switch connector,
    only extracts capitalised drug tokens (avoids splitting on prose), and
    skips when a START already names any extracted drug.
    """
    import re
    if not recommendations:
        return recommendations
    existing_starts = {
        _normalize_drug_name(r.intervention or "")
        for r in recommendations
        if r.type == "pharmacological" and (r.action or "").lower() == "start"
    }
    new_starts: list[Recommendation] = []
    for rec in recommendations:
        if rec.type != "pharmacological" or (rec.action or "").lower() != "stop":
            continue
        text = rec.intervention or ""
        low = text.lower()
        # find the earliest switch connector
        cut = -1
        for conn in _SWITCH_CONNECTORS:
            i = low.find(conn)
            if i >= 0 and (cut < 0 or i < cut):
                cut = i + len(conn)
        if cut < 0:
            continue
        tail = text[cut:]
        # Extract capitalised drug-name tokens (Methyldopa, Labetalol, Nifedipine).
        # Anything ALL-CAPS / regular word starting upper, ≥4 chars, not a stop word.
        candidates = re.findall(r"\b([A-Z][a-z]{3,}(?:-[A-Z][a-z]+)?)\b", tail)
        _STOP_WORDS = {"Table", "Discontinue", "Switch", "Replace", "Alternative",
                       "Consider", "From", "With", "Day", "Daily", "Orally", "Max",
                       "Doses", "Dose", "Extended", "Release", "Mg"}
        for name in candidates:
            if name in _STOP_WORDS:
                continue
            norm = name.lower().strip()
            if norm in existing_starts:
                continue
            existing_starts.add(norm)
            new_starts.append(Recommendation(
                intervention=name,
                type="pharmacological",
                action="start",
                evidence_grade=rec.evidence_grade,
                cpg_source=rec.cpg_source,
                rationale=f"Pregnancy-safe alternative to the STOPPED agent ({_normalize_drug_name(text) or 'previous drug'}); confirm dose with clinician. Auto-split from STOP rec.",
                contraindications_checked=[],
            ))
            # First named alternative is enough — clinician picks.
            break
    if new_starts:
        return list(recommendations) + new_starts
    return recommendations


_PRIMARY_CLAUSE_SPLITTERS = (
    " if ", "; if ", " when ", "; titrate", "; if blood ", " should be initiated if ",
    " should be considered if ", " initiate if ", " — if ",
)


def _primary_clause(text: str) -> str:
    """Return the primary prescribing clause (before any conditional escalation).

    Case-10 metformin intervention reads:
      'Metformin 500 mg OD initial dose — titrate to 1500 mg OD; if blood glucose
       targets not met within 1-2 weeks, initiate insulin therapy'
    The trailing 'initiate insulin' clause is contingent future therapy, not a
    current prescription. Matching `_SPECIALIST_INITIATED_DRUGS["insulin"]`
    against the whole string false-fires an endocrinology cross-check for a
    metformin rec. Trim at the first conditional connector to keep the check
    anchored to what is being prescribed *now*.
    """
    if not text:
        return ""
    low = text.lower()
    cut = len(low)
    for sep in _PRIMARY_CLAUSE_SPLITTERS:
        i = low.find(sep)
        if i >= 0 and i < cut:
            cut = i
    return text[:cut]


def _validate_specialist_medication_pairing(
    recommendations: list[Recommendation],
    case: PatientCase | None = None,
) -> list[str]:
    """Validate specialist-initiated drugs have referrals, and vice versa (Gap 7).

    Returns: List of validation warnings for unmet cross-references.

    Checks:
    1. Specialist-initiated drugs → ensure referral to required specialty exists
    2. Referrals for conditions needing specific meds → ensure medication present
    """
    warnings = []

    # Extract specialist referrals
    specialist_refs: dict[str, list[str]] = {}  # specialty → [conditions]
    specialist_recs = [r for r in recommendations if r.type == "referral"]
    for rec in specialist_recs:
        spec = (getattr(rec, "specialty", None) or "").strip().lower()
        cond = (getattr(rec, "condition", None) or "").strip().lower()
        if spec:
            if spec not in specialist_refs:
                specialist_refs[spec] = []
            if cond:
                specialist_refs[spec].append(cond)

    # Check medications against specialist-initiated mapping.
    # Only flag NEW initiations (action='start'). A drug the patient is already
    # taking (action='continue') was presumably initiated by a specialist on a
    # prior visit; flagging it here just creates noise without surfacing any
    # new risk. action='stop' and 'contraindicated' obviously need no referral.
    # action='change' is treated as a new initiation only when the change is to
    # dose/agent (heuristic: presence of "increase"/"decrease"/"titrate"/"switch"
    # in rationale) — otherwise it's effectively a continue.
    _NEW_INITIATION_ACTIONS = {"start"}
    _DOSE_CHANGE_KEYWORDS = ("increase", "decrease", "titrate", "switch", "uptitrate", "down-titrate")
    med_recs = [r for r in recommendations if r.type == "pharmacological"]

    # Residual 1: a drug counted as "already continuing" if any OTHER pharmacological
    # rec in the same plan has action='continue' and names it. A combined START
    # like "warfarin + aspirin + clopidogrel" then only flags the truly NEW
    # component(s) — warfarin is silenced because a parallel [CONTINUE] Warfarin
    # rec proves it was already specialist-initiated on a prior visit.
    continuing_tokens: set[str] = set()
    for r in med_recs:
        if (getattr(r, "action", None) or "").lower().strip() == "continue":
            for tok in (r.intervention or "").lower().replace(",", " ").replace("+", " ").split():
                tok = tok.strip(" .;:()[]")
                if len(tok) >= 4 and tok.isalpha():
                    continuing_tokens.add(tok)

    for med_rec in med_recs:
        action = (getattr(med_rec, "action", None) or "").lower().strip()
        rationale = (getattr(med_rec, "rationale", None) or "").lower()
        is_new_initiation = action in _NEW_INITIATION_ACTIONS
        if not is_new_initiation and action == "change":
            is_new_initiation = any(kw in rationale for kw in _DOSE_CHANGE_KEYWORDS)
        if not is_new_initiation:
            continue
        med_text = _primary_clause(med_rec.intervention or "").lower()

        # Check if this is a specialist-initiated drug — but ignore matches that
        # come from a drug class which is only present via an already-continuing
        # token (residual 1). Build the list of trigger classes whose match in
        # med_text is exclusively due to a continuing-token substring.
        required_specs = []
        for drug_class, specs in _SPECIALIST_INITIATED_DRUGS.items():
            if drug_class not in med_text:
                continue
            # If the drug_class name itself is a continuing token, skip.
            if drug_class in continuing_tokens:
                continue
            # If the only occurrence of drug_class in med_text is inside a
            # continuing-token name (e.g. "warfarin" continuing → skip warfarin
            # cross-check on a triple-therapy START), skip.
            class_token = drug_class.split()[0]
            if class_token in continuing_tokens and class_token == drug_class:
                continue
            required_specs.extend(specs)

        if required_specs:
            # Verify at least one required specialist is in referrals. Match
            # by substring rather than equality — clinicians often store
            # combined-team specialty strings like
            #   "obstetrician and endocrinologist/diabetologist"
            # which equality-match would miss for required_spec="endocrinology"
            # even though endocrinology IS represented in the referral team.
            # Use a token-based check: required spec name appears as substring
            # in any referral specialty, OR a referral specialty key appears
            # in any condition string (covers "Refer to ENDO for ..." patterns).
            specialist_ref_blob = " | ".join(
                [spec_key for spec_key in specialist_refs]
                + [c for conds in specialist_refs.values() for c in conds]
            ).lower()
            # Pregnancy context: GDM metformin/insulin are routinely
            # obstetrician-initiated when an obstetric referral is present, so
            # an "obstetric*" specialty satisfies an endocrinology requirement
            # for these drugs without needing a separate endo referral.
            pregnant = bool(case) and any(
                "pregnan" in (c or "").lower() or "gestational" in (c or "").lower()
                for c in (getattr(case, "comorbidities", []) or [])
            )
            obstetric_present = "obstetric" in specialist_ref_blob

            def _spec_satisfied(req: str) -> bool:
                if req in specialist_refs or req in specialist_ref_blob:
                    return True
                if req.rstrip("y") in specialist_ref_blob:  # endocrinology→endocrinolog (handles -ist forms)
                    return True
                if pregnant and obstetric_present and req in ("endocrinology", "diabetes"):
                    return True
                return False

            has_required = any(_spec_satisfied(req) for req in required_specs)
            if not has_required:
                warning = (
                    f"Specialist-initiated medication {med_text[:40]} recommended "
                    f"but no referral to {required_specs[0]} (requires specialist initiation)"
                )
                warnings.append(warning)

    return warnings


def _match_rule_to_med(med_name: str, rule_drug: str) -> bool:
    """Return True if a prescribed med matches a KG drug name or drug class."""
    if not med_name or not rule_drug:
        return False
    n = str(med_name).lower()
    d = str(rule_drug).lower().strip()
    if not d or d in _PARSER_ERROR_DRUGS:
        return False
    if len(d) >= 4 and (d in n or n in d):
        return True
    for kw in _DRUG_CLASS_KEYWORDS.get(d, []):
        if kw in n:
            return True
    return False


def _normalize_drug_name(intervention: str) -> str:
    """Extract and normalize the primary drug name from an intervention string.

    Examples:
      "Metformin 500mg BD" → "metformin"
      "Lisinopril 10mg daily — ACE inhibitor" → "lisinopril"
      "Beta-blocker (agent and dose not specified in CPG)" → "beta-blocker"

    Returns normalized drug name (lowercase, stripped), or empty string if unparseable.
    """
    if not intervention:
        return ""
    # Split on common separators and take the first part
    first_part = intervention.split(" — ")[0].split(":")[0].strip()
    if not first_part:
        return ""
    # Extract the word before the first digit/dash (dose/range)
    import re
    match = re.match(r"([a-zA-Z\-]+(?:\s+[a-zA-Z\-]+)?)", first_part)
    if match:
        return match.group(1).lower().strip()
    return first_part.lower().strip()


def _is_duplicate_medication(rec1: Recommendation, rec2: Recommendation, threshold: float = 0.85) -> bool:
    """Check if two pharmacological recommendations are for the same medication.

    Two meds are considered duplicates if:
    - They have the same normalized drug name (exact match)
    - OR their interventions share a high substring overlap (≥85%)

    Args:
        rec1, rec2: Recommendation objects with type="pharmacological"
        threshold: substring overlap ratio [0,1] for fuzzy matching (default 0.85)

    Returns: True if likely duplicates.
    """
    if rec1.type != "pharmacological" or rec2.type != "pharmacological":
        return False

    int1 = (rec1.intervention or "").strip()
    int2 = (rec2.intervention or "").strip()
    if not int1 or not int2:
        return False

    # Exact match on normalized drug names
    drug1 = _normalize_drug_name(int1)
    drug2 = _normalize_drug_name(int2)
    if drug1 and drug2 and drug1 == drug2:
        return True

    # Fuzzy substring overlap (for cases where dose/frequency varies slightly)
    # E.g., "Metformin 500mg BD" vs "Metformin 500mg daily" might be duplicates
    int1_lower = int1.lower()
    int2_lower = int2.lower()
    min_len = min(len(int1_lower), len(int2_lower))
    if min_len < 10:  # Skip very short strings
        return False

    # Count matching characters in order (simple overlap metric)
    matches = sum(1 for a, b in zip(int1_lower, int2_lower) if a == b)
    overlap_ratio = matches / max(len(int1_lower), len(int2_lower))
    return overlap_ratio >= threshold


def _dedup_pharmacological_recs(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Deduplicate pharmacological recommendations, preserving order and preferring specificity.

    For duplicate medications:
    - Keep the recommendation with more detail (longer intervention string)
    - Prefer recommendations with explicit evidence grades
    - Log dedup decisions at INFO level

    Args:
        recommendations: List of Recommendation objects (mixed types)

    Returns: Deduplicated list with same order but no duplicate medications.
    """
    if not recommendations:
        return recommendations

    deduped = []

    for rec in recommendations:
        if rec.type != "pharmacological":
            deduped.append(rec)
            continue

        # Check against existing pharmacological recommendations
        is_dup = False
        for j, existing_rec in enumerate(deduped):
            if existing_rec.type != "pharmacological":
                continue

            if _is_duplicate_medication(rec, existing_rec):
                # Prefer the one with longer intervention (more specific)
                len_rec = len((rec.intervention or "").strip())
                len_existing = len((existing_rec.intervention or "").strip())
                if len_rec > len_existing:
                    # Replace the existing one with the more detailed version
                    deduped[j] = rec
                    logger.info(
                        "medication dedup: replaced %r with more specific %r",
                        (existing_rec.intervention or "")[:60],
                        (rec.intervention or "")[:60],
                    )
                else:
                    logger.info(
                        "medication dedup: dropped duplicate %r (kept %r)",
                        (rec.intervention or "")[:60],
                        (existing_rec.intervention or "")[:60],
                    )
                is_dup = True
                break

        if not is_dup:
            deduped.append(rec)

    return deduped


import re as _re_mod

# Canonical multi-word specialties where 'team'/'professional'/'surgery' is part
# of the name and must not be stripped.
_CANONICAL_MULTIWORD_SPECIALTIES = frozenset({
    "multidisciplinary team",
    "oral health professional",
    "bariatric surgery",
    "vascular surgery",
    "cardiothoracic surgery",
    "general surgery",
    "diabetes nurse educator",
    "diabetes nurse",
    "renal team",
    "heart failure team",
    "palliative care",
    "infectious diseases",
    "internal medicine",
    "emergency medicine",
    "family medicine",
    "general medicine",
    "respiratory medicine",
    "geriatric medicine",
    "obstetrics and gynaecology",
    "obstetrics & gynaecology",
})

# Trailing tokens that follow a specialty noun and should be stripped so that
# "Cardiology review" and "Refer to Cardiology" both normalise to "cardiology".
# Not applied to canonical multi-word specialties above.
_REFERRAL_SPECIALTY_SUFFIXES = frozenset({
    "review", "consultation", "consult", "consultations",
    "service", "services", "team", "input",
    "opinion", "assessment", "evaluation", "referral",
    "follow", "followup", "follow-up", "clinic", "clinics",
    "specialist", "specialists", "department", "dept",
    "appointment", "visit", "advice",
})

# Stopwords that terminate the specialty phrase. Once one of these is hit,
# everything after it is non-specialty rationale ("for X", "if Y", "due to Z").
_REFERRAL_PHRASE_TERMINATORS = frozenset({
    "for", "if", "due", "to", "regarding", "re", "about",
    "with", "after", "before", "when", "trigger", "indicated",
    "consider", "urgent", "routine", "emergency",
})


def _normalise_specialty_phrase(phrase: str) -> str:
    """Reduce a referral phrase to a normalised specialty key.

    Strategy:
      1. Drop parenthetical qualifiers and leading "Refer(ral) to".
      2. If a canonical multi-word specialty appears as a prefix, return that.
      3. Walk tokens left-to-right; stop at any phrase terminator
         ('for', 'if', 'with', ...).
      4. Drop trailing suffix tokens ('review', 'consultation', 'team', ...).
      5. If a conjunction split two alternatives, keep the first.
    """
    p = (phrase or "").strip().lower()
    if not p:
        return ""
    # Strip parenthetical qualifier ('(consider)', '(routine)', ...).
    p = _re_mod.sub(r"\s*\([^)]*\)", " ", p).strip()
    # Strip leading 'refer to' / 'referral to' / 'consider'.
    p = _re_mod.sub(r"^(?:refer(?:ral)?\s+(?:to\s+)?|consider\s+)", "", p).strip()
    if not p:
        return ""
    # Canonical multi-word specialty prefix wins (handles 'multidisciplinary team',
    # 'bariatric surgery', 'oral health professional', etc.).
    for canonical in _CANONICAL_MULTIWORD_SPECIALTIES:
        if p == canonical or p.startswith(canonical + " "):
            return canonical
    # If a conjunction splits two alternatives, keep the first.
    for sep in (" or ", " and/or ", " / ", "/"):
        if sep in p:
            p = p.split(sep, 1)[0].strip()
            break
    # Walk tokens; stop at first phrase terminator.
    tokens: list[str] = []
    for tok in p.split():
        t = tok.strip(",.;:")
        if t in _REFERRAL_PHRASE_TERMINATORS:
            break
        if t:
            tokens.append(t)
    # Drop trailing suffix tokens.
    while len(tokens) > 1 and tokens[-1] in _REFERRAL_SPECIALTY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens).strip()


def _infer_referral_specialty(rec) -> str:
    """Best-effort specialty extraction from intervention text.

    The Stage 5 synthesis LLM emits referrals as free-text intervention strings
    like `"Refer to Cardiology — optimise foundational HF medications"` without
    populating a structured `specialty` field (the model doesn't even define one).
    Without this fallback, every empty-specialty referral normalises to ("","")
    and Tier 1 dedup collapses every distinct specialty into one bucket.
    """
    spec = (getattr(rec, "specialty", "") or "").strip()
    if spec:
        return _normalise_specialty_phrase(spec)
    intervention = (getattr(rec, "intervention", "") or "").strip()
    if not intervention:
        return ""
    # Take prefix before first hard separator (— – - : ( ; |).
    head = _re_mod.split(r"[—–\-:(;|]", intervention, maxsplit=1)[0].strip()
    if not head:
        head = intervention
    return _normalise_specialty_phrase(head[:120])


def _normalize_referral_key(specialty: str | None, condition: str | None) -> tuple[str, str]:
    """Normalize specialty and condition for dedup comparison."""
    spec = (specialty or "").strip().lower()
    cond = (condition or "").strip().lower()
    return (spec, cond)


def _referral_urgency_priority(urgency: str | None) -> int:
    """Return numeric priority for urgency level (higher is better)."""
    u = (urgency or "routine").strip().lower()
    urgency_map = {
        "emergency": 3,
        "urgent": 2,
        "routine": 1,
        "": 1,  # default to routine if empty
    }
    return urgency_map.get(u, 1)


_REFERRAL_STOPWORDS = frozenset({
    "with", "and", "or", "for", "of", "the", "a", "an", "to", "in", "on",
    "refer", "referral", "consider", "due", "secondary", "primary",
    "patient", "patients", "mellitus",  # T2DM ↔ "Type 2 Diabetes Mellitus" tokenises differently
})


def _referral_tokens(spec: str, cond: str, intervention: str) -> set[str]:
    """Tokenise a referral into a stopword-filtered, alpha-only set.

    Used by Tier-2 dedup so that word-order/conjunction variants collapse:
    "Ophthalmology for Obesity with T2DM" vs "Ophthalmology for T2DM with Obesity and Retinopathy"
    both contribute {ophthalmology, obesity, t2dm, ...}.
    """
    import re
    blob = f"{spec} {cond} {intervention}".lower()
    raw = re.findall(r"[a-z0-9]+", blob)
    return {t for t in raw if len(t) > 2 and t not in _REFERRAL_STOPWORDS}


def _is_duplicate_referral(rec1: Recommendation, rec2: Recommendation) -> bool:
    """Detect duplicate referrals by inferred specialty.

    Clinically a referral books ONE consultation per specialty per visit;
    multiple reasons get bundled into a single consult, not split into N
    separate appointments. So same inferred specialty == duplicate, regardless
    of condition. Distinct reasons are preserved by the merge in
    `_dedup_referral_recs` (rationale concatenation) — nothing is lost.

    Returns True iff both are referrals with the same inferred specialty.
    """
    if not rec1 or not rec2:
        return False
    if rec1.type != "referral" or rec2.type != "referral":
        return False
    spec1 = _infer_referral_specialty(rec1)
    spec2 = _infer_referral_specialty(rec2)
    # If we couldn't extract a specialty for either side, refuse to dedup —
    # better to keep a redundant referral than to silently lose a distinct one.
    if not spec1 or not spec2:
        return False
    return spec1 == spec2


def _merge_referral_into(kept: Recommendation, extra: Recommendation) -> None:
    """Fold `extra`'s rationale + cpg_source into `kept` in-place.

    Same specialty, distinct reasons → one entry with all reasons preserved.
    `kept` keeps its `intervention` headline; the new reason is appended to
    `rationale` (bullet-style) and the new source is added to `cpg_source`
    (semicolon-joined, deduped).
    """
    # Reason: prefer extra.rationale; fall back to its intervention tail.
    extra_rationale = (getattr(extra, "rationale", "") or "").strip()
    if not extra_rationale:
        intervention = (extra.intervention or "").strip()
        # take the text after the first separator as the reason
        for sep in ("—", "–", "-", ":"):
            if sep in intervention:
                extra_rationale = intervention.split(sep, 1)[1].strip()
                break
        if not extra_rationale:
            extra_rationale = intervention
    if extra_rationale:
        kept_rationale = (getattr(kept, "rationale", "") or "").strip()
        # Avoid duplicating a reason already captured.
        if extra_rationale and extra_rationale.lower() not in kept_rationale.lower():
            joined = (
                f"{kept_rationale}; also: {extra_rationale}"
                if kept_rationale and not kept_rationale.endswith(";")
                else f"{kept_rationale} also: {extra_rationale}".strip()
                if kept_rationale
                else extra_rationale
            )
            try:
                kept.rationale = joined
            except Exception:
                pass
    # Merge cpg_source (semicolon-separated, dedup-by-substring).
    extra_src = (getattr(extra, "cpg_source", "") or "").strip()
    if extra_src:
        kept_src = (getattr(kept, "cpg_source", "") or "").strip()
        if extra_src not in kept_src:
            try:
                kept.cpg_source = f"{kept_src}; {extra_src}" if kept_src else extra_src
            except Exception:
                pass


def _dedup_referral_recs(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Deduplicate referral recommendations by inferred specialty, merging reasons.

    Same specialty → one entry. Higher urgency wins for the kept entry. Distinct
    rationales and cpg sources are folded into the kept entry rather than discarded.
    Non-referral recommendations pass through untouched, preserving order.
    """
    if not recommendations:
        return recommendations

    deduped: list[Recommendation] = []

    for rec in recommendations:
        if rec.type != "referral":
            deduped.append(rec)
            continue

        is_dup = False
        for j, existing_rec in enumerate(deduped):
            if existing_rec.type != "referral":
                continue
            if not _is_duplicate_referral(rec, existing_rec):
                continue

            urgency_rec = _referral_urgency_priority(getattr(rec, "urgency", None))
            urgency_existing = _referral_urgency_priority(getattr(existing_rec, "urgency", None))
            len_rec = len((rec.intervention or "").strip())
            len_existing = len((existing_rec.intervention or "").strip())

            # Decide which entry stays as the "headline" (intervention text + urgency).
            keep_new_as_headline = (
                urgency_rec > urgency_existing
                or (urgency_rec == urgency_existing and len_rec > len_existing)
            )

            spec = _infer_referral_specialty(rec) or "(unknown)"
            if keep_new_as_headline:
                # New rec becomes the headline; fold old reason in.
                _merge_referral_into(rec, existing_rec)
                deduped[j] = rec
                logger.info(
                    "referral dedup [%s]: replaced headline %r with %r (reason merged)",
                    spec,
                    (existing_rec.intervention or "")[:60],
                    (rec.intervention or "")[:60],
                )
            else:
                # Existing rec stays as headline; fold new reason in.
                _merge_referral_into(existing_rec, rec)
                logger.info(
                    "referral dedup [%s]: merged reason from %r into kept %r",
                    spec,
                    (rec.intervention or "")[:60],
                    (existing_rec.intervention or "")[:60],
                )
            is_dup = True
            break

        if not is_dup:
            deduped.append(rec)

    return deduped


# Generic words that name *how* something is tracked rather than *what* is being
# tracked — excluded from the "subject" comparison so that "Body weight" and
# "Weight monitoring" collapse to the shared subject token {"weight"}.
_MONITORING_GENERIC_TOKENS = frozenset({
    "body", "level", "levels", "test", "testing", "monitoring", "monitor",
    "self", "function", "and", "the", "of", "for", "value", "values",
    "status", "parameter", "parameters", "daily", "routine", "regular",
})

# Verbs/nouns that signal a lifestyle rec is really describing a *measurement /
# surveillance* activity (i.e. it overlaps a monitoring parameter) rather than a
# therapeutic lifestyle change.
_MONITORING_ACTIVITY_TOKENS = frozenset({
    "monitor", "monitoring", "weigh", "weighing", "record", "recording",
    "measure", "measuring", "measurement", "track", "tracking", "check",
    "checking", "log", "logging", "report", "reporting", "self-monitor",
    "self-monitoring", "observe", "observing",
})


def _subject_tokens(text: str) -> set[str]:
    """Significant subject words in *text* (lowercased, >2 chars, non-generic)."""
    import re as _re
    toks = {t for t in _re.findall(r"[a-z]+", (text or "").lower()) if len(t) > 2}
    return toks - _MONITORING_GENERIC_TOKENS


def _numeric_signatures(text: str) -> set[str]:
    """Distinctive number+unit tokens (e.g. '2kg', '5mmol') from *text*.

    These act as strong duplicate signals: two entries that both mention the same
    quantitative threshold (">2kg in 2 days") are almost certainly the same advice.
    """
    import re as _re
    sigs: set[str] = set()
    for num, unit in _re.findall(r"(\d+(?:\.\d+)?)\s*([a-zA-Z%/]+)", (text or "").lower()):
        sigs.add(f"{num}{unit}")
    return sigs


def _dedup_lifestyle_vs_monitoring(
    recommendations: list[Recommendation],
    monitoring: list,
) -> list[Recommendation]:
    """Drop lifestyle recs that merely restate a structured monitoring parameter.

    The plan surfaces patient-facing lifestyle advice (``type == "lifestyle"``) and
    a separate structured monitoring table (``plan.monitoring``). The synthesis LLM
    sometimes emits the same surveillance action in both — e.g. a "Weight monitoring"
    lifestyle card and a "Body weight / report >2kg gain in 2 days" monitoring row.
    The monitoring row is the authoritative one (it carries schedule + target), so we
    suppress the lifestyle duplicate.

    Fully content-driven (no hardcoded subjects): a lifestyle rec is treated as a
    duplicate of a monitoring item when they share at least one significant subject
    token AND either (a) the lifestyle rec describes a measurement/surveillance
    activity, or (b) both entries share a distinctive numeric threshold (e.g. "2kg").
    Therapeutic lifestyle recs that merely share a subject word (e.g. "Weight
    management — caloric restriction") are preserved because they carry no monitoring
    activity token or shared threshold.
    """
    if not recommendations or not monitoring:
        return recommendations

    # Precompute subject tokens + numeric signatures for each monitoring parameter.
    monitor_index: list[tuple[set[str], set[str], str]] = []
    for item in monitoring:
        param = getattr(item, "parameter", "") or ""
        schedule = getattr(item, "schedule", "") or ""
        target = getattr(item, "target", "") or ""
        subj = _subject_tokens(param)
        nums = _numeric_signatures(f"{param} {schedule} {target}")
        if subj or nums:
            monitor_index.append((subj, nums, param))

    if not monitor_index:
        return recommendations

    kept: list[Recommendation] = []
    for rec in recommendations:
        if rec.type != "lifestyle":
            kept.append(rec)
            continue

        import re as _re
        rec_text = f"{rec.intervention or ''} {rec.rationale or ''}"
        rec_subjects = _subject_tokens(rec_text)
        rec_words = set(_re.findall(r"[a-z]+(?:-[a-z]+)*", rec_text.lower()))
        has_activity = bool(rec_words & _MONITORING_ACTIVITY_TOKENS)
        rec_nums = _numeric_signatures(rec_text)

        matched_param = None
        for subj, nums, param in monitor_index:
            shares_subject = bool(rec_subjects & subj)
            if not shares_subject:
                continue
            shares_number = bool(rec_nums & nums)
            if has_activity or shares_number:
                matched_param = param
                break

        if matched_param is not None:
            logger.info(
                "lifestyle/monitoring dedup: dropped lifestyle rec %r — duplicates "
                "monitoring parameter %r",
                (rec.intervention or "")[:60], matched_param,
            )
            continue
        kept.append(rec)

    return kept


def _surface_interacting_current_meds(
    recommendations: list[Recommendation],
    red_flags: list[str],
    current_medications: list[str],
) -> list[Recommendation]:
    """Surface a current medication ONLY when it is the existing side of a
    drug–drug contraindication the plan already raised.

    Stage 5 only emits recommendations for drugs it *acts on*, so a current med
    that merely *creates* a contraindication is invisible. The motivating case:
    the patient's long-acting nitrate (Isosorbide Mononitrate) is what makes a
    PDE5 inhibitor absolutely contraindicated — the plan flags the PDE5i, but the
    nitrate itself never gets a row, so the clinician sees only one side of the
    interaction. This pass gives that interacting current med its own row, tagged
    ``contraindicated`` so it sits alongside the contraindicated agent and the
    conflict is visible from both sides.

    Background meds the plan does not touch (aspirin, statin, etc. for ongoing
    secondary prevention) are deliberately NOT surfaced — they are assumed
    continued and would only add noise.

    Trigger = the current med's name appears in the text of an emitted
    ``contraindicated`` recommendation or an interaction red flag. Unresolved
    Questions are intentionally NOT a trigger: a drug named there may merely be a
    *swap candidate* (e.g. a β-blocker under ED-contribution review), and stamping
    it ``contraindicated`` would be clinically wrong.
    """
    if not current_medications:
        return recommendations

    def _primary_token(norm: str) -> str:
        return norm.split()[0] if norm else ""

    # Drugs already addressed by an emitted rec — never duplicate or relabel them.
    covered_full: set[str] = set()
    covered_tokens: set[str] = set()
    for r in recommendations:
        if r.type != "pharmacological":
            continue
        norm = _normalize_drug_name(r.intervention or "")
        if norm:
            covered_full.add(norm)
            covered_tokens.add(_primary_token(norm))

    # Interaction corpus: where the existing interacting drug would be named.
    corpus_parts: list[str] = []
    for r in recommendations:
        if r.type == "pharmacological" and (r.action or "") == "contraindicated":
            corpus_parts.append(r.intervention or "")
            corpus_parts.append(r.rationale or "")
    corpus_parts.extend(red_flags or [])
    corpus = " \n ".join(corpus_parts).lower()
    if not corpus.strip():
        return recommendations

    injected: list[Recommendation] = []
    for med in current_medications:
        med = (med or "").strip()
        if not med:
            continue
        norm = _normalize_drug_name(med)
        if not norm:
            continue
        token = _primary_token(norm)
        already = (
            norm in covered_full
            or (token and token in covered_tokens)
            or any(norm.startswith(c) or c.startswith(norm) for c in covered_full)
        )
        if already:
            continue
        # Only surface if this drug is actually named in the interaction corpus.
        if norm not in corpus and not (token and token in corpus):
            continue
        injected.append(
            Recommendation(
                intervention=(
                    f"{med} — interacting agent in a flagged drug–drug contraindication"
                ),
                type="pharmacological",
                action="contraindicated",
                evidence_grade=None,
                cpg_source="Patient medication reconciliation (drug interaction)",
                rationale=(
                    "Existing medication on the patient's active list that is the other side of "
                    "a drug–drug contraindication surfaced by this plan — shown so the conflict "
                    "is visible from both sides. The contraindication blocks co-prescribing the "
                    "flagged agent; it does NOT mean stop this drug reflexively. Manage via the "
                    "relevant specialty (e.g. cardiology review of nitrate necessity)."
                ),
                contraindications_checked=[],
            )
        )
        covered_full.add(norm)
        covered_tokens.add(token)

    if injected:
        logger.info(
            "stage_5: surfaced %d interacting current med(s) as contraindicated row(s)",
            len(injected),
        )
    return recommendations + injected


def _referral_evidence_quality(rec) -> tuple[str, str]:
    """Assess evidence quality for a KG referral and return (quality_level, audit_note).

    Args:
        rec: KG referral edge with evidence field

    Returns:
        Tuple of (quality_level, audit_note) where:
        - quality_level: "explicit" | "inferred" | "fallback" | "missing"
        - audit_note: Human-readable description for logging/audit
    """
    evidence = (getattr(rec, "evidence", None) or "").strip()
    condition = (getattr(rec, "condition", None) or "").strip()
    specialty = (getattr(rec, "specialty", None) or "").strip()

    if not evidence:
        # No explicit evidence field
        return ("missing", f"No evidence field in KG edge for {specialty}→{condition}")

    # Check evidence length (too short = likely generic/fallback)
    if len(evidence) < 20:
        return ("inferred", f"Evidence too brief for {specialty}→{condition}: {evidence}")

    # Check if evidence is meaningful (not just the condition name repeated)
    if condition.lower() in evidence.lower() and len(evidence) < 60:
        return ("inferred", f"Evidence likely inferred from structure for {specialty}→{condition}")

    # Good evidence
    return ("explicit", f"Explicit evidence for {specialty}→{condition}: {evidence[:80]}")


def _kg_referral_cpg_source(rec) -> str:
    """Build a UNIQUE cpg_source string per KG-sourced referral with evidence tracing.

    Bare `source_document` is the same for every referral edge from the same
    CPG (e.g. five T2DM referrals all stamp `T2-Diabetes-Mellitus(6th-Edition)`).
    The UI dedups CPG references by `cpg_source` raw string — identical strings
    collapse into one card with all interventions piled into `usedBy[]`, which
    then renders as a giant comma-separated paragraph.

    Appending the specialty (and where available a chunk marker) makes each
    referral's cpg_source unique, so each gets its own reference card. Includes
    evidence quality indicator for audit trail.

    Args:
        rec: KG referral edge (has source_document, specialty, cpg_chunk_id, evidence fields)

    Returns: Formatted CPG source string with traceability markers
    """
    doc = (getattr(rec, "source_document", None) or getattr(rec, "cpg_source", None) or "Neo4j KG").strip()
    specialty = (getattr(rec, "specialty", None) or "").strip()
    chunk_id = getattr(rec, "cpg_chunk_id", None) or None
    evidence = (getattr(rec, "evidence", None) or "").strip()

    # Build base citation
    parts = [doc]
    if specialty:
        parts.append(f"— {specialty} referral")

    out = " ".join(parts)

    # Add evidence quality marker (helps clinician distinguish explicit vs. inferred)
    if evidence:
        out = f"{out} [evidence: explicit]"
    else:
        out = f"{out} [evidence: inferred from KG structure]"

    # Add chunk traceability for explicit KG lookup
    if chunk_id:
        out = f"{out} [kg:{str(chunk_id)[:8]}]"

    return out


def _extract_recommendation_assumptions(
    recommendations: list, unresolved_questions: list
) -> list[tuple[str, str]]:
    """Extract load-bearing clinical assumptions that would flip recommendations if violated.

    Returns list of (recommendation_id, assumption_text) tuples flagged by LLM.
    Assumptions are embedded in rationale or unresolved_questions by synthesis stage.
    """
    assumptions = []

    # Check unresolved_questions for assumption flags
    for q in unresolved_questions:
        if "assumption" in q.lower():
            assumptions.append(("unresolved", q))

    # Check recommendation rationales for assumption markers
    for rec in recommendations:
        if not hasattr(rec, "rationale") or not rec.rationale:
            continue
        rationale = rec.rationale
        # LLM marks assumptions with "Assumption:" prefix per prompt instruction
        if "assumption" in rationale.lower():
            spec = getattr(rec, "specialty", None) or getattr(rec, "condition", None) or "unknown"
            assumptions.append((f"{spec}_{rec.type}", rationale))

    return assumptions


DDX_RERANK_MODEL = os.getenv("LLM_CHOICE", "gpt-4o")
EXCLUSION_PENALTY_WEIGHT = 0.3       # λ — applied in ddx/search_ddx.py; defined here for central reference
INCLUSION_BOOST_WEIGHT = 0.3         # mirrors ddx/search_ddx.py; weights the synonym-match addend
CC_BOOST_WEIGHT = 0.15               # calibrated for INFERRED dx (CC_BOOST_WEIGHT × conf, see scripts/calibrate_cc_boost.py)
CC_EXPLICIT_BOOST = 0.25             # flat boost when the clinician explicitly named the dx in CC/notes
CC_TIE_BREAK_EPSILON = 0.20          # when top-2 cc_explicit candidates final_scores are within this delta, force deterministic order (Fix B)
OUT_OF_SCOPE_INCL_THRESHOLD = 0.3
DDX_DISPLAY_FLOOR = 0.30
SCORE_TERM_DISPLAY_FLOOR = 0.50
RERANK_DISAGREEMENT_DELTA = 2

# Fixed seed for Stage-2 LLM calls (symptom phrase, condition hypotheses, CC hints).
# Stabilises the DDx vector-search candidate pool across reruns on Mode B
# (task-framed) visits where slight phrasing variance otherwise drops the
# correct named-disease code out of the pool entirely. Honoured by
# OpenAI-compatible servers (vLLM, mimo); ignored silently elsewhere.
DDX_DETERMINISTIC_SEED = int(os.getenv("DDX_DETERMINISTIC_SEED", "42"))


def _seed_kwargs(model: str | None) -> dict:
    """Return `{"seed": ...}` for OpenAI-compat backends that accept seed,
    `{}` for Gemini (which 400s on unknown `seed` field via its OpenAI-compat layer).
    """
    if model and "gemini" in model.lower():
        return {}
    return {"seed": DDX_DETERMINISTIC_SEED}

# Regex disease→canonical-name map for the deterministic CC-hint fallback.
# Augments (does NOT replace) `_extract_cc_icd_hints`: even when the LLM call
# drops a named diagnosis on a Mode-B (task-framed) visit, any of these aliases
# literally present in chief_complaint / history / comorbidities / meds resolves
# to a canonical disease name and forces the code into the candidate pool.
# Keep the alias side lowercase; word-boundary matched on combined case text.
# Treat injected hints as effectively explicit (confidence 0.90, explicit=True)
# since the alias was literally written by the clinician.
_DISEASE_ALIAS_MAP: dict[str, str] = {
    # Cardiology — ACS / IHD
    "nstemi": "Acute non-ST elevation myocardial infarction",
    "non-st elevation myocardial infarction": "Acute non-ST elevation myocardial infarction",
    "non-st-elevation myocardial infarction": "Acute non-ST elevation myocardial infarction",
    "stemi": "Acute ST elevation myocardial infarction",
    "st elevation myocardial infarction": "Acute ST elevation myocardial infarction",
    "acute coronary syndrome": "Acute coronary syndrome",
    "acs": "Acute coronary syndrome",
    "unstable angina": "Unstable angina",
    "stable angina": "Stable angina",
    "coronary artery disease": "Coronary artery disease",
    "ischaemic heart disease": "Ischaemic heart disease",
    "ischemic heart disease": "Ischaemic heart disease",
    # Cardiology — rhythm / failure
    "atrial fibrillation": "Atrial fibrillation",
    "afib": "Atrial fibrillation",
    "non-valvular atrial fibrillation": "Atrial fibrillation",
    "non-valvular af": "Atrial fibrillation",
    "atrial flutter": "Atrial flutter",
    "heart failure": "Heart failure",
    "hfref": "Heart failure with reduced ejection fraction",
    "hfpef": "Heart failure with preserved ejection fraction",
    "congestive heart failure": "Congestive heart failure",
    "chf": "Congestive heart failure",
    # Endocrine
    "type 2 diabetes mellitus": "Type 2 diabetes mellitus",
    "type 2 diabetes": "Type 2 diabetes mellitus",
    "t2dm": "Type 2 diabetes mellitus",
    "type 1 diabetes mellitus": "Type 1 diabetes mellitus",
    "t1dm": "Type 1 diabetes mellitus",
    "gestational diabetes": "Gestational diabetes mellitus",
    "gdm": "Gestational diabetes mellitus",
    "hypothyroidism": "Hypothyroidism",
    "hyperthyroidism": "Hyperthyroidism",
    # Hypertension / vascular
    "essential hypertension": "Essential hypertension",
    "hypertension": "Essential hypertension",
    "stroke": "Stroke",
    "ischaemic stroke": "Cerebral infarction",
    "ischemic stroke": "Cerebral infarction",
    "tia": "Transient ischaemic attack",
    "transient ischaemic attack": "Transient ischaemic attack",
    # Respiratory
    "copd": "Chronic obstructive pulmonary disease",
    "chronic obstructive pulmonary disease": "Chronic obstructive pulmonary disease",
    "asthma": "Asthma",
    "pulmonary embolism": "Pulmonary embolism",
    "pe": "Pulmonary embolism",
    # Renal / GI / Liver
    "chronic kidney disease": "Chronic kidney disease",
    "ckd": "Chronic kidney disease",
    "end stage renal disease": "End stage renal disease",
    "esrd": "End stage renal disease",
    "cirrhosis": "Cirrhosis of liver",
    # Mental health
    "major depressive disorder": "Major depressive disorder",
    "depression": "Major depressive disorder",
    "anxiety disorder": "Anxiety disorder",
    # Infections / can't-miss
    "sepsis": "Sepsis",
    "meningitis": "Meningitis",
    "oesophageal candidiasis": "Candidiasis of oesophagus",
    "esophageal candidiasis": "Candidiasis of oesophagus",
    # Urology
    "erectile dysfunction": "Erectile dysfunction",
    # Oncology / palliative — chronic cancer-related pain (named, not the MG30 parent)
    "cancer pain": "Chronic cancer related pain",
    "cancer-related pain": "Chronic cancer related pain",
    "cancer related pain": "Chronic cancer related pain",
    "malignancy-related pain": "Chronic cancer related pain",
    # Bahasa Malaysia / Manglish primary-care comorbidity terms (LNG robustness).
    # These are the documented Malaysian lay names for chronic comorbidities that
    # DDx vector search under-recalls (LNG-03 logged kencing manis / darah tinggi /
    # kolesterol tinggi skipped as weak matches). Disease terms only — symptom
    # phrases (e.g. "sakit dada") are intentionally left out so the passing
    # Manglish ACS cases (LNG-01/02) keep their current behaviour.
    "kencing manis": "Type 2 diabetes mellitus",
    "darah tinggi": "Essential hypertension",
    "tekanan darah tinggi": "Essential hypertension",
    "kolesterol tinggi": "Hyperlipidaemia",
    "lemak darah tinggi": "Hyperlipidaemia",
    "sakit jantung": "Ischaemic heart disease",
    "penyakit buah pinggang": "Chronic kidney disease",
    "strok": "Stroke",
    "asma": "Asthma",
    "lelah": "Asthma",
}
ScoreRouteMethod = Literal[
    "exact",
    "sibling",
    "ancestor_d1",
    "ancestor_d1_sibling",
    "ancestor_d1_sibling_child",
    "ancestor_d2",
    "procedure_scope",
    "semantic_scope",
    "out_of_scope",
]
DDX_THINKING_BUDGET = 5000   # tokens; sufficient for re-ranking ≤10 candidates


# ---------------------------------------------------------------------------
# Condition-expected therapy coverage (#1A) + always-refer set (#2)
#
# Both maps are keyed by ICD-11 code prefix. Prefix match is anchored, so a
# more-specific ICD code (e.g. "BD11.2") matches any registered shorter prefix
# (e.g. "BD11"). Add new conditions here as their gaps are identified — the
# Stage 4 anchor-query injector and the Stage 5 post-validator both read these
# tables, so a single entry covers retrieval seeding + synthesis check.
# ---------------------------------------------------------------------------

# Drug-class pillars expected for a condition. Each entry pairs:
#   - a clinician-facing pillar label (used in unresolved_questions)
#   - a list of substrings; the post-validator considers the pillar "present"
#     if ANY substring appears in ANY recommendation.intervention (case-insens)
#   - a retrieval query the Stage 4 injector seeds when no chunk for the
#     pillar has likely been retrieved
_CONDITION_EXPECTED_THERAPIES: dict[str, list[dict]] = {
    # HFrEF — four-pillar GDMT. BD11.0 / BD11.2 / BD11.Z all match the BD11 prefix.
    "BD11": [
        {
            "pillar": "ACE inhibitor or ARNI",
            "substrings": ["ace inhibitor", "ace-i", "acei", "arni", "sacubitril",
                           "ramipril", "perindopril", "enalapril", "lisinopril", "captopril"],
            "query": "ACE inhibitor or ARNI (sacubitril/valsartan) for heart failure with reduced ejection fraction",
        },
        {
            "pillar": "Beta-blocker (HFrEF-proven: bisoprolol, carvedilol, metoprolol succinate, nebivolol)",
            "substrings": ["beta-blocker", "beta blocker", "bisoprolol", "carvedilol",
                           "metoprolol", "nebivolol"],
            "query": "Beta-blocker bisoprolol carvedilol metoprolol succinate nebivolol for HFrEF mortality reduction",
        },
        {
            "pillar": "Mineralocorticoid receptor antagonist (spironolactone or eplerenone)",
            "substrings": ["mineralocorticoid", "spironolactone", "eplerenone", "mra "],
            "query": "Mineralocorticoid receptor antagonist spironolactone eplerenone for HFrEF — dose, potassium monitoring, eGFR threshold",
        },
        {
            "pillar": "SGLT2 inhibitor (dapagliflozin or empagliflozin)",
            "substrings": ["sglt2", "dapagliflozin", "empagliflozin"],
            "query": "SGLT2 inhibitor dapagliflozin empagliflozin for heart failure with reduced ejection fraction",
        },
    ],
}

# ICD prefixes for which a referral recommendation is expected. Maps prefix to
# the specialty label used when surfacing the missing referral.
_ALWAYS_REFER_CONDITIONS: dict[str, str] = {
    "BD11": "Cardiology (heart failure specialist) — newly diagnosed HFrEF requires GDMT optimisation and device-therapy assessment",
    "BC81": "Cardiology — atrial fibrillation requires risk-stratified anticoagulation and rate/rhythm strategy",
    "BA41": "Cardiology — acute coronary syndrome / NSTEMI requires invasive risk stratification",
    "GB61": "Nephrology — CKD stage ≥3 requires specialist co-management",
    "JB00": "Maternal-Foetal Medicine / Obstetrics — pregnancy with comorbidity requires multidisciplinary care",
}


def _matches_icd_prefix(icd_code: str, table: dict) -> str | None:
    """Return the prefix key in `table` that matches `icd_code`, or None."""
    if not icd_code:
        return None
    for prefix in table:
        if icd_code.startswith(prefix):
            return prefix
    return None


def _expected_pillars_for(icd_code: str) -> list[dict]:
    key = _matches_icd_prefix(icd_code, _CONDITION_EXPECTED_THERAPIES)
    return _CONDITION_EXPECTED_THERAPIES.get(key, []) if key else []


def _required_referral_for(icd_code: str) -> str | None:
    key = _matches_icd_prefix(icd_code, _ALWAYS_REFER_CONDITIONS)
    return _ALWAYS_REFER_CONDITIONS.get(key) if key else None


# ---------------------------------------------------------------------------
# DDxResult — pipeline-internal, not a user-facing schema type
# ---------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    base_similarity: float
    inclusion_match: float = 0.0
    inclusion_phrase: str | None = None
    cc_boost: float = 0.0              # weighted CC-derived confidence boost (CC_BOOST_WEIGHT × raw confidence)
    cc_boost_raw: float | None = None  # unweighted LLM confidence (0.0-1.0) for display
    exclusion_penalty: float = 0.0
    exclusion_phrase: str | None = None
    final_score: float
    # None until routing (stage 3) is known — the numeric scores are computed at
    # stage 2 so the top-5 can show "why this rank" immediately; the route badge
    # is filled in once stage_3_route resolves the match.
    route_method: ScoreRouteMethod | None = None

    @model_validator(mode="after")
    def validate_final_score(self) -> "ScoreBreakdown":
        # CC-boost is no longer in the math formula — it stays on the breakdown
        # purely as a soft signal that downstream stages (LLM rerank prompt,
        # trace badge) consume separately. final_score = base + incl − excl.
        expected = self.base_similarity + self.inclusion_match - self.exclusion_penalty
        if abs(self.final_score - expected) > 0.001:
            raise ValueError(
                "final_score must equal base_similarity + inclusion_match - exclusion_penalty"
            )
        return self


class DDxResult(BaseModel):
    code: str
    title: str
    similarity: float
    base_similarity: float | None = None
    final_score: float | None = None
    inclusion_match: bool = False
    matched_term: str | None = None
    inclusion_similarity: float | None = None
    exclusion_match: bool = False
    matched_exclusion: str | None = None
    exclusion_similarity: float | None = None
    exclusion_penalty: float = 0.0
    cc_boost: float = 0.0              # weighted CC boost (CC_BOOST_WEIGHT × cc_confidence, or CC_EXPLICIT_BOOST when explicit)
    cc_confidence: float | None = None # raw LLM confidence from CC hint extraction (0.0-1.0)
    cc_explicit: bool = False          # True when the clinician explicitly named this dx in CC/notes
    score_breakdown: ScoreBreakdown | None = None
    matched_cpg_title: str | None = None
    reasoning: list[str] = []
    math_rank: int | None = None
    llm_rank: int | None = None
    rank_delta: int | None = None
    override_reason: str | None = None


class OutOfScopeInfo(BaseModel):
    route_method: Literal["out_of_scope"] = "out_of_scope"
    icd_candidates_considered: list[dict]
    max_inclusion_score: float
    message: str


DDX_SCORE_EXPLAINER = """Each diagnosis is scored from four signals:
- Symptom match - how closely the patient's presentation matches the condition's official description.
- Known-term match - bonus when the patient's words match a recognised synonym for the condition.
- CC confidence - boost when the clinician's chief complaint strongly implies this specific diagnosis (dynamic, based on LLM confidence).
- Exclusion caution - the score is reduced when the presentation matches something the WHO guideline explicitly says this code is NOT. The diagnosis is not removed; it is ranked lower with the reason shown.

The CPG badge tells you HOW the guideline behind a diagnosis was found: an exact match is the strongest; a broader ancestor match indicates the guideline covers a parent or related category."""


def build_score_breakdown(
    result: DDxResult,
    route_method: ScoreRouteMethod | None = None,
) -> ScoreBreakdown:
    base_similarity = float(result.base_similarity if result.base_similarity is not None else result.similarity)
    # result.inclusion_similarity is the RAW synonym-match cosine; the actual score
    # contribution is weighted (mirrors search_ddx) so it can't dominate base or push
    # final past 1.0. exclusion_penalty is already weighted upstream.
    raw_inclusion = float(result.inclusion_similarity or 0.0)
    inclusion_match = round(INCLUSION_BOOST_WEIGHT * raw_inclusion, 4)
    # CC-boost — STILL EXTRACTED upstream and exposed to the LLM rerank prompt
    # as a soft signal, but no longer enters the math formula. The clinician-
    # facing breakdown is the simpler `base + inclusion − exclusion`. To revert,
    # change `final_score` below to `base + inclusion + cc_boost − exclusion`.
    cc_boost = round(float(result.cc_boost or 0.0), 4)  # preserved for trace transparency only
    cc_boost_raw = result.cc_confidence  # preserve the unweighted LLM confidence for display
    exclusion_penalty = float(result.exclusion_penalty or 0.0)
    final_score = round(base_similarity + inclusion_match - exclusion_penalty, 4)

    # Phrase is shown when the underlying MATCH (raw cosine) is strong — not the
    # weighted addend (which is always < the floor after weighting).
    inclusion_phrase = (
        result.matched_term
        if raw_inclusion >= SCORE_TERM_DISPLAY_FLOOR and result.matched_term
        else None
    )
    exclusion_phrase = (
        result.matched_exclusion
        if (result.exclusion_similarity or 0.0) >= SCORE_TERM_DISPLAY_FLOOR and exclusion_penalty > 0
        else None
    )

    return ScoreBreakdown(
        base_similarity=round(base_similarity, 4),
        inclusion_match=round(inclusion_match, 4),
        inclusion_phrase=inclusion_phrase,
        cc_boost=cc_boost,
        cc_boost_raw=cc_boost_raw,
        exclusion_penalty=round(exclusion_penalty, 4),
        exclusion_phrase=exclusion_phrase,
        final_score=final_score,
        route_method=route_method,
    )


def route_provenance_badge(route_method: ScoreRouteMethod | None) -> str:
    if route_method is None:
        return ""  # routing not resolved yet (stage 2) — no badge to show
    if route_method == "exact":
        return "✓ Exact guideline match"
    if route_method in {"ancestor_d1", "ancestor_d2"}:
        return "≈ Matched via broader category"
    if route_method == "sibling":
        return "≈ Matched via related code"
    if route_method == "ancestor_d1_sibling":
        return "≈ Matched via related category"
    if route_method == "ancestor_d1_sibling_child":
        return "≈ Matched via related subcode"
    if route_method == "procedure_scope":
        return "⚙ Matched via procedure context"
    if route_method == "semantic_scope":
        return "~ Matched via semantic scope similarity"
    return "✕ No guideline covers this"


def render_ddx_candidate(candidate: DDxResult, rank: int) -> str:
    breakdown = candidate.score_breakdown or build_score_breakdown(candidate)
    badge = route_provenance_badge(breakdown.route_method)
    # Clamp to [0,1] for display — a strong synonym boost can lift final_score above
    # 1.0, and "159% confidence" is nonsensical to a clinician.
    shown = max(0.0, min(breakdown.final_score, 1.0))
    confidence = f"{shown:.0%}"
    if breakdown.final_score < DDX_DISPLAY_FLOOR:
        confidence = f"{confidence} low confidence"

    cpg_title = candidate.matched_cpg_title or "No matched CPG"
    cpg_line = f"     CPG: {cpg_title}   [{badge}]" if badge else f"     CPG: {cpg_title}"
    lines = [
        f"#{rank}  {candidate.code} - {candidate.title}  confidence: {confidence}",
        cpg_line,
        "     Why this rank:",
        f"       ✓ Symptom match: {breakdown.base_similarity:.0%}",
    ]
    if breakdown.inclusion_phrase:
        lines.append(
            f'       ✓ Matched known term "{breakdown.inclusion_phrase}" '
            f"(+{breakdown.inclusion_match:.0%})"
        )
    if breakdown.cc_boost > 0:
        raw_pct = f"{breakdown.cc_boost_raw:.0%}" if breakdown.cc_boost_raw else "?"
        lines.append(
            f"       ✓ CC confidence boost: {raw_pct} confidence → +{breakdown.cc_boost:.0%} weighted"
        )
    if breakdown.exclusion_phrase:
        lines.append(
            f'       ⚠ WHO excludes "{breakdown.exclusion_phrase}" - '
            f"ranked lower (-{breakdown.exclusion_penalty:.0%})"
        )
    if candidate.rank_delta is not None and abs(candidate.rank_delta) >= RERANK_DISAGREEMENT_DELTA:
        direction = "up" if candidate.rank_delta > 0 else "down"
        math_r = candidate.math_rank or "?"
        llm_r = candidate.llm_rank or rank
        has_excl_override = (
            candidate.rank_delta > 0
            and candidate.matched_exclusion
            and candidate.exclusion_penalty > 0
        )
        glyph = "⚠ ↕" if has_excl_override else "↕"
        lines.append(f"   {glyph} Reasoning model moved this {direction} (math had it #{math_r}, now #{llm_r})")
        if candidate.override_reason:
            lines.append(f"     Reason: {candidate.override_reason}")
    return "\n".join(lines)


def render_ddx_top5(candidates: list[DDxResult]) -> str:
    return "\n\n".join(
        render_ddx_candidate(candidate, rank=i + 1)
        for i, candidate in enumerate(candidates[:5])
    )


# ---------------------------------------------------------------------------
# Stage 2 — DDx
# ---------------------------------------------------------------------------

def _format_prior_visit(prior) -> str:
    """Render PriorVisitSummary as a compact prompt block, or empty string when absent.

    Kept lean (~5 lines) so it doesn't dominate Stage 4/5 context windows.
    """
    if not prior:
        return ""
    fields = [
        ("visit_date", getattr(prior, "visit_date", None)),
        ("prior_icd_primary", getattr(prior, "prior_icd_primary", None)),
        ("prior_plan_summary", getattr(prior, "prior_plan_summary", None)),
        ("key_labs_delta", getattr(prior, "key_labs_delta", None)),
        ("what_changed", getattr(prior, "what_changed", None)),
    ]
    lines = [f"- {k}: {v}" for k, v in fields if v]
    if not lines:
        return ""
    return "prior_visit:\n" + "\n".join(lines) + "\n"


def _build_symptom_text(case: PatientCase) -> str:
    parts = [case.chief_complaint]
    if case.history:
        parts.append(case.history)
    if case.comorbidities:
        parts.append("Comorbidities: " + ", ".join(case.comorbidities))
    if case.vitals:
        vitals_str = ", ".join(f"{k}={v}" for k, v in case.vitals.items())
        parts.append("Vitals: " + vitals_str)
    return ". ".join(parts)


def _force_rerank_enabled() -> bool:
    """Gate for the deterministic Smoke-8 rerank harness. INERT in production.

    Requires `ALLOW_FORCE_RERANK=1` AND `APP_ENV` != 'production'. Either condition
    failing disables the harness, so production behaviour can never be altered by it.
    """
    if os.getenv("APP_ENV", "").strip().lower() == "production":
        return False
    return os.getenv("ALLOW_FORCE_RERANK", "").strip() == "1"


def _forced_rerank_spec(candidates: list[DDxResult]) -> list[dict] | None:
    """Test/staging-only: read a fixed rerank order from `FORCE_RERANK_ORDER` and
    return it shaped like the LLM's JSON output (list of {code, reasoning,
    override_reason}). Feeding it through the normal assembly path means llm_rank,
    rank_delta, the override-enforcement hard rule, and D6d telemetry all run
    unchanged — only the LLM call is skipped. This makes Smoke 8 deterministic.

    Returns None when the harness is disabled, unset, or invalid — so it can never
    change production behaviour. `FORCE_RERANK_ORDER` is a JSON list, ordered by
    intended rank (or carrying explicit `llm_rank`):
        [{"code": "BC81.3", "override_reason": "..."}, {"code": "BD11.0"}]
    """
    if not _force_rerank_enabled():
        return None
    raw = os.getenv("FORCE_RERANK_ORDER")
    if not raw:
        return None
    try:
        spec = json.loads(raw)
        assert isinstance(spec, list)
    except Exception:
        logger.warning("FORCE_RERANK_ORDER is not a valid JSON list — ignoring harness")
        return None
    valid = {c.code for c in candidates}
    entries = [e for e in spec if isinstance(e, dict) and e.get("code") in valid]
    if any("llm_rank" in e for e in entries):
        entries.sort(key=lambda e: e.get("llm_rank", 1_000))
    out = [
        {
            "code": e["code"],
            "reasoning": e.get("reasoning", "forced order (Smoke 8 harness)"),
            "override_reason": e.get("override_reason"),
        }
        for e in entries
    ]
    return out or None


def _collapse_sibling_clusters(reranked: list[DDxResult]) -> list[DDxResult]:
    """Demote sibling-cluster duplicates (same 4-char ICD-11 stem) below distinct-family codes.

    Deterministic safety net for the DISTINCT-DISEASE PREFERENCE rule in the
    Stage-2 prompt — the LLM sometimes still keeps two BA41.x or BC81.x variants
    inside the top-5. We keep the FIRST occurrence of each stem in place (LLM
    already picked its preferred representative), and push later same-stem
    siblings to the tail so genuinely distinct comorbidities can populate top-5.
    """
    if not reranked:
        return reranked
    seen_stems: set[str] = set()
    primaries: list[DDxResult] = []
    siblings: list[DDxResult] = []
    for r in reranked:
        code = (getattr(r, "code", "") or "").strip()
        stem = code[:4] if len(code) >= 4 else code
        if stem and stem in seen_stems:
            siblings.append(r)
        else:
            if stem:
                seen_stems.add(stem)
            primaries.append(r)
    if not siblings:
        return reranked
    logger.info(
        "DDx sibling-cluster collapse: demoted %d same-stem sibling(s) below distinct families",
        len(siblings),
    )
    return primaries + siblings


def _extract_rerank_list(raw_content: str) -> list:
    """Pull the ranked-candidate list out of a Stage-2 rerank response.

    The call sets response_format={"type":"json_object"}, so a well-behaved model
    returns {"ranking": [...]}. The old "find the first '['" parser handled that,
    but across adversarial inputs (ADV / INJ / LNG) we kept hitting "No JSON array
    found" and silently falling back to math order — which defeats the red-flag /
    specificity overrides those cases depend on. The recurring degraded shapes are:
      - a bare JSON array (legacy prompt contract / forced Smoke-8 harness)
      - an object keyed by some other field name (e.g. {"codes": [...]})
      - an object keyed by ICD code ({"BA41.1": {...}, ...}) with no array at all
    Handle all of them. Raise ValueError only when no candidate list can be
    recovered (e.g. empty content from a thinking-token budget blow-out) so the
    caller logs a genuine degradation instead of masking it.
    """
    raw = (raw_content or "").strip().strip("` \n")
    if raw.startswith("json"):
        raw = raw[4:].strip()

    # Preferred path: parse the whole payload as JSON.
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        # (a) array nested under any key (ranking / codes / results / ...).
        for value in parsed.values():
            if isinstance(value, list):
                return value
        # (b) object keyed by ICD code: {"BA41.1": {"confidence": ...}, ...}.
        #     Preserve insertion order (= the model's intended ranking).
        rebuilt = [
            {"code": code, **(meta if isinstance(meta, dict) else {})}
            for code, meta in parsed.items()
        ]
        if rebuilt:
            return rebuilt

    # Fallback: locate a bracketed array embedded in surrounding prose.
    bracket_idx = raw.find("[")
    if bracket_idx != -1:
        end_idx = raw.rfind("]")
        if end_idx > bracket_idx:
            try:
                return json.loads(raw[bracket_idx : end_idx + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(
        f"No rerank list found in output (len={len(raw_content or '')} chars). "
        f"First 200 chars: {(raw_content or '')[:200]!r}"
    )


async def _llm_rerank_ddx(
    case: PatientCase,
    candidates: list[DDxResult],
    emit=None,                      # async callable(event_type, data) | None
) -> list[DDxResult]:
    """
    Re-rank DDx candidates using Gemini 2.5 Flash extended thinking.

    Falls back to original order on any failure.
    When emit is provided, streams thinking tokens as thinking_delta SSE events.
    A deterministic test/staging harness (`FORCE_RERANK_ORDER` + `ALLOW_FORCE_RERANK`,
    see `_forced_rerank_spec`) can inject a fixed order, bypassing the LLM — inert in
    production.
    """
    if not candidates:
        return candidates

    # STAGE2_RERANK_LLM_* takes priority — allows re-rank to stay on a heavy model
    # (MiMo) while extraction/hypotheses move to a lighter model (Gemini Flash).
    # Falls back to STAGE2_LLM_* then the global LLM_* config.
    stage2_base = (
        os.getenv("STAGE2_RERANK_LLM_BASE_URL")
        or os.getenv("STAGE2_LLM_BASE_URL")
    )
    stage2_key = (
        os.getenv("STAGE2_RERANK_LLM_API_KEY")
        or os.getenv("STAGE2_LLM_API_KEY")
    )
    stage2_model = (
        os.getenv("STAGE2_RERANK_LLM_CHOICE")
        or os.getenv("STAGE2_LLM_CHOICE")
    )
    stage2_provider = os.getenv("STAGE2_RERANK_LLM_PROVIDER", "") or os.getenv("STAGE2_LLM_PROVIDER", "")
    using_override = bool(stage2_base and stage2_key and stage2_model)

    client = _make_openai_client(
        base_url=stage2_base or os.getenv("LLM_BASE_URL"),
        api_key=stage2_key or os.getenv("LLM_API_KEY"),
        provider=stage2_provider,
        timeout=120,
        max_retries=1,
    )
    active_model = stage2_model or DDX_RERANK_MODEL
    logger.info(
        "Stage 2 rerank using model=%s endpoint=%s (override=%s)",
        active_model,
        stage2_base or os.getenv("LLM_BASE_URL"),
        using_override,
    )

    # D6: assign math_rank before building the prompt
    for i, c in enumerate(candidates):
        c.math_rank = i + 1

    vitals_str = json.dumps(case.vitals) if case.vitals else "none"
    severity_str = (
        json.dumps(case.severity_staging)
        if getattr(case, "severity_staging", None)
        else "none"
    )

    def _candidate_block(i: int, c: DDxResult) -> str:
        n = i + 1
        lines = [
            f"  {n}. {c.code}  {c.title}",
            f"       math_rank: {n}  vector_score: {c.similarity:.3f}"
            f"  symptom_match: {(c.base_similarity or c.similarity):.3f}"
            f"  inclusion_match: {(c.inclusion_similarity or 0.0):.3f}",
        ]
        if (c.inclusion_similarity or 0.0) >= SCORE_TERM_DISPLAY_FLOOR and c.matched_term:
            lines.append(f'       known-term: "{c.matched_term}"')
        if (
            c.matched_exclusion
            and (c.exclusion_similarity or 0.0) >= SCORE_TERM_DISPLAY_FLOOR
            and c.exclusion_penalty > 0
        ):
            lines.append(
                f'       WHO exclusion: "{c.matched_exclusion}"'
                f"  penalty: {c.exclusion_penalty:.3f}"
            )
        if (c.cc_boost or 0.0) > 0:
            if getattr(c, "cc_explicit", False):
                lines.append(
                    f"       clinician-named: EXPLICIT  cc_boost: +{c.cc_boost:.3f}"
                    "  (clinician wrote this dx in the notes — do NOT demote below "
                    "top-3 unless contradicted by patient context)"
                )
            elif getattr(c, "cc_confidence", None) is not None:
                lines.append(
                    f"       cc-implied: {c.cc_confidence * 100:.0f}%  "
                    f"cc_boost: +{c.cc_boost:.3f}"
                )
        return "\n".join(lines)

    candidate_lines = "\n".join(_candidate_block(i, c) for i, c in enumerate(candidates))

    system_prompt = _load_prompt("stage2_ddx_rerank.txt")

    user_prompt = f"""Patient:
- Chief complaint: {case.chief_complaint}
- Age / sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Current medications: {", ".join(case.current_medications) or "none"}
- Allergies: {", ".join(case.allergies) or "none"}
- Vitals: {vitals_str}
- Severity staging / key labs: {severity_str}

Candidate ICD-11 codes (pre-ranked by math score — math_rank=1 is highest):
{candidate_lines}"""

    messages = (
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        if system_prompt
        else [{"role": "user", "content": user_prompt}]
    )

    try:
        raw_content = ""

        forced = _forced_rerank_spec(candidates)
        if forced is not None:
            # Deterministic Smoke-8 harness (test/staging only): skip the LLM and
            # feed the fixed order through the same parse/assembly/telemetry path.
            logger.info("D6 FORCE_RERANK harness active (test/staging only) — bypassing LLM")
            raw_content = json.dumps(forced)
        elif emit is not None:
            # Streaming path — capture thinking tokens
            # max_tokens caps total output. Bumped 4000 → 8000 because Gemini 2.5
            # Flash's thinking tokens count against this budget on the OpenAI-compat
            # endpoint and were truncating the JSON mid-string. response_format
            # forces server-side JSON closure even if budget is squeezed.
            stream = await client.chat.completions.create(
                model=active_model,
                messages=messages,
                temperature=0,
                **_seed_kwargs(active_model),
                max_tokens=8000,
                response_format={"type": "json_object"},
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # TEMP diagnostic — remove after confirming thinking field name
                delta_dict = delta.model_dump() if hasattr(delta, "model_dump") else delta.__dict__
                logger.debug("Stage 2 delta: %s", {k: v for k, v in delta_dict.items() if v})
                # Google native API exposes thinking as delta.reasoning or delta.thinking
                thinking_chunk = (
                    getattr(delta, "reasoning", None)
                    or getattr(delta, "thinking", None)
                    or getattr(delta, "reasoning_content", None)
                )
                if thinking_chunk:
                    await emit("thinking_delta", {
                        "stage": 2,
                        "node": "DDx Re-rank",
                        "chunk": thinking_chunk,
                    })
                if delta.content:
                    raw_content += delta.content
        else:
            # Non-streaming path — same JSON-mode enforcement as streaming so
            # both paths have the same parse-stability guarantees.
            resp = await client.chat.completions.create(
                model=active_model,
                messages=messages,
                temperature=0,
                **_seed_kwargs(active_model),
                max_tokens=8000,
                response_format={"type": "json_object"},
            )
            raw_content = resp.choices[0].message.content

        # Parse re-ranked list (shared by both paths). Robust to json_object-mode
        # wrappers, object-keyed-by-code outputs, and prose-prefixed arrays — see
        # _extract_rerank_list. Raises into the outer except (math-order fallback)
        # only when no candidate list can be recovered at all.
        ranked = _extract_rerank_list(raw_content)

        code_to_result = {c.code: c for c in candidates}
        reranked: list[DDxResult] = []
        for llm_pos, item in enumerate(ranked):
            code = item.get("code")
            if code and code in code_to_result:
                result = code_to_result[code].model_copy()
                llm_reason = item.get("reasoning", "")
                if llm_reason:
                    result.reasoning = result.reasoning + [f"LLM: {llm_reason}"]
                # D6: assign llm_rank and rank_delta
                result.llm_rank = llm_pos + 1
                result.rank_delta = (result.math_rank or 0) - result.llm_rank
                result.override_reason = item.get("override_reason") or None
                # D6 hard rule: exclusion-penalised candidate promoted >= RERANK_DISAGREEMENT_DELTA
                # without an override_reason → inject placeholder and warn
                if (
                    result.matched_exclusion
                    and (result.exclusion_similarity or 0.0) >= SCORE_TERM_DISPLAY_FLOOR
                    and result.exclusion_penalty > 0
                    and result.rank_delta >= RERANK_DISAGREEMENT_DELTA
                    and not result.override_reason
                ):
                    result.override_reason = "[override_reason required but not provided by LLM]"
                    logger.warning(
                        "D6 hard rule: exclusion-penalised candidate %s promoted %d positions "
                        "without override_reason — injecting placeholder",
                        code,
                        result.rank_delta,
                    )
                reranked.append(result)

        seen = {r.code for r in reranked}
        for c in candidates:
            if c.code not in seen:
                reranked.append(c)

        # D6d telemetry
        disagreements = sum(
            1 for r in reranked
            if r.rank_delta is not None and abs(r.rank_delta) >= RERANK_DISAGREEMENT_DELTA
        )
        exclusion_overrides = sum(
            1 for r in reranked
            if r.rank_delta is not None
            and r.rank_delta >= RERANK_DISAGREEMENT_DELTA
            and r.matched_exclusion
            and (r.exclusion_similarity or 0.0) >= SCORE_TERM_DISPLAY_FLOOR
            and r.exclusion_penalty > 0
        )
        logger.info(
            "D6 telemetry: model=%s disagreements=%d exclusion_overrides=%d",
            active_model,
            disagreements,
            exclusion_overrides,
        )

        reranked = _collapse_sibling_clusters(reranked)

        # Fix B — deterministic tie-breaker on co-equal-primary top-2.
        # When the top-2 are both clinician-named (cc_explicit) AND their final_scores
        # are within CC_TIE_BREAK_EPSILON, the LLM rerank's choice is dominated by
        # sampling noise (Gemini has no seed; even at temp=0 short structured outputs
        # can flip). Force (final_score DESC, code ASC) on those two slots so the
        # rank is reproducible. Preserves rerank's judgement when scores diverge.
        if len(reranked) >= 2:
            a, b = reranked[0], reranked[1]
            if (
                getattr(a, "cc_explicit", False)
                and getattr(b, "cc_explicit", False)
                and abs((a.final_score or 0.0) - (b.final_score or 0.0)) < CC_TIE_BREAK_EPSILON
            ):
                ordered = sorted([a, b], key=lambda r: (-(r.final_score or 0.0), r.code or ""))
                if ordered[0].code != a.code:
                    logger.info(
                        "Fix-B tie-break: top-2 within %.2f (cc_explicit both) — "
                        "swapped %s ↔ %s for deterministic order",
                        CC_TIE_BREAK_EPSILON, a.code, b.code,
                    )
                reranked[0], reranked[1] = ordered[0], ordered[1]

        logger.info("DDx re-ranked %d candidates via %s", len(reranked), active_model)
        return reranked

    except Exception as exc:
        logger.warning(
            "DDx LLM re-rank FAILED with model=%s endpoint=%s: %s — using original order",
            active_model,
            stage2_base or os.getenv("LLM_BASE_URL"),
            exc,
        )
        # Surface the silent degradation: the vector order we return is NOT a
        # judged ranking. Without this signal a malformed rerank response looks
        # identical to a successful one downstream (SIL-01).
        if emit is not None:
            try:
                await emit("sub_step", {
                    "stage": "Stage 2",
                    "badge": "degraded",
                    "detail": "DDx re-rank unavailable — fallback to vector order (ranking unverified)",
                })
            except Exception:
                pass
        return candidates


_TASK_FRAMED_MARKERS = (
    "post-pci", "post pci", "post-cabg", "post cabg", "post-op", "post op",
    "post-operative", "post operative", "medication review", "med review",
    "follow-up", "follow up", "review of", "review for", "anticoagulation review",
    "antithrombotic management", "antithrombotic review", "day 1 review",
    "post-discharge", "post discharge", "routine review", "annual review",
    # Antenatal / management-plan visits (case 10 booking visit, etc.) — these
    # framings carry no presenting symptom and are pure planning context, so
    # they belong to Mode B even though they aren't post-procedure reviews.
    "booking visit", "antenatal visit", "antenatal review", "antenatal booking",
    "newly diagnosed", "plan for", "management plan",
)


def _is_task_framed(notes: str) -> bool:
    """Cheap regex check for Mode-B (task-framed) visits.

    Returns True when the notes contain a procedural/review marker. Used to
    bypass the LLM symptom extractor in favour of deterministic phrase
    assembly from `case.history` + comorbidities, which is reproducible.
    """
    if not notes:
        return False
    n = notes.lower()
    return any(m in n for m in _TASK_FRAMED_MARKERS)


def _assemble_task_framed_phrase(case: PatientCase) -> str:
    """Deterministic Mode-B phrase: matched aliases + procedure marker + comorbidities.

    Skips the LLM entirely. Reads the same text the regex disease-hint fallback
    scans and stitches a stable short phrase. Always returns the same string
    for the same case, eliminating Mode-B drift between reruns.
    """
    text = " ".join([
        case.chief_complaint or "",
        case.history or "",
        ", ".join(case.comorbidities or []),
    ]).lower()
    procedure = next((m.replace("-", " ") for m in _TASK_FRAMED_MARKERS if m in text), "follow-up")
    diseases: list[str] = []
    seen: set[str] = set()
    for alias, canonical in _DISEASE_ALIAS_MAP.items():
        if canonical in seen:
            continue
        if alias in text:
            diseases.append(canonical)
            seen.add(canonical)
        if len(diseases) >= 4:
            break
    if diseases:
        phrase = f"{procedure} for {', '.join(diseases)}"
    else:
        phrase = f"{procedure} {(case.chief_complaint or '').strip()}"
    phrase = " ".join(phrase.split()[:15])
    return phrase or (case.chief_complaint or "follow-up")


_PHRASE_CACHE: dict[str, tuple[str, bool]] = {}


def _phrase_cache_key(notes: str, model: str) -> str:
    import hashlib
    h = hashlib.sha1(f"{model}::{notes}".encode("utf-8")).hexdigest()
    return h


async def _extract_symptom_phrase(
    notes: str,
    client: openai.AsyncOpenAI,
    model: str,
    extra_body: dict | None = None,
    case: PatientCase | None = None,
) -> tuple[str, bool]:
    """Compress clinical notes to a symptom-focused query string for DDx vector search.

    Long clinical narratives dilute the ICD-11 vector match. This pre-step extracts
    only the presenting symptoms relevant to differential diagnosis.

    extra_body is forwarded to the API call. For reasoning models (e.g. mimo) this
    MUST disable thinking — otherwise the model spends its whole token budget on
    hidden reasoning and returns empty content, forcing a fallback to raw notes.

    Returns (query, fell_back). fell_back=True means extraction produced nothing
    usable and the raw notes are used verbatim — which dilutes the vector match and
    is worth surfacing in the trace so a clinician/debugger knows the query wasn't
    distilled.
    """
    # Concise prompt without few-shot examples — MiMo follows direct instructions
    # better than imitating examples (which it can confuse with the expected output format).
    prompt = (
        "Rewrite these clinical notes as a single short phrase (max 15 words) for "
        "differential-diagnosis vector search.\n\n"
        "Choose the framing that best fits the notes:\n"
        "  (A) SYMPTOM-FRAMED visit (patient presents with a complaint): output the "
        "primary symptom + anatomical location/radiation + character + duration. "
        "Example: 'crushing central chest pain radiating to left arm, 2 hours'.\n"
        "  (B) TASK-FRAMED visit (post-procedure review, medication review, follow-up, "
        "or any consult with no presenting symptom): output the clinical management "
        "context — the procedure/condition driving the visit. "
        "Examples: 'post-PCI day 1 antithrombotic management for NSTEMI with AF', "
        "'post-operative anticoagulation review', 'newly diagnosed heart failure "
        "with reduced ejection fraction'.\n\n"
        "Rules for both modes:\n"
        "  - Exclude age, sex, vital signs, and unrelated comorbidities unless they "
        "are the visit's reason.\n"
        "  - NEVER return 'no symptom', 'asymptomatic', 'n/a', or empty — for "
        "task-framed visits use mode (B) instead.\n"
        "  - Output the phrase only — no preamble, no quotes, no explanation.\n\n"
        f"Notes: {notes}\n\n"
        "Phrase:"
    )
    # D — cache check (eliminates per-rerun jitter even when `seed` is ignored).
    cache_key = _phrase_cache_key(notes, model)
    if cache_key in _PHRASE_CACHE:
        cached = _PHRASE_CACHE[cache_key]
        logger.info("Symptom extraction cache HIT: key=%s → %r", cache_key[:8], cached[0])
        return cached

    # A — Mode-B rule-based bypass. Task-framed visits have no symptom to
    # extract; the LLM has to invent procedural prose which is non-deterministic
    # AND embeds poorly into ICD-11 disease space. Assemble deterministically.
    if case is not None and _is_task_framed(notes):
        phrase = _assemble_task_framed_phrase(case)
        logger.info("Symptom extraction: Mode-B rule-based bypass → %r", phrase)
        result = (phrase, False)
        _PHRASE_CACHE[cache_key] = result
        return result

    logger.info("Symptom extraction starting: model=%s notes_len=%d", model, len(notes))
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            **_seed_kwargs(model),
            **({"extra_body": extra_body} if extra_body else {}),
        )
        phrase = resp.choices[0].message.content.strip().strip('"').strip("'").rstrip(".")

        word_count = len(phrase.split())
        if word_count > 25:
            logger.warning(
                "Symptom extraction returned %d words (>25) — likely echoed input. "
                "Truncating to 15 words. Raw: %r",
                word_count, phrase[:120],
            )
            phrase = " ".join(phrase.split()[:15])

        if not phrase:
            logger.warning("Symptom extraction returned empty — falling back to raw notes")
            return notes, True

        lower_phrase = phrase.lower().strip(" .;,")
        negatives = ("no", "none", "n/a", "no symptoms", "no active symptoms", "asymptomatic", "no primary symptom", "no primary symptoms")
        if len(phrase.strip()) < 3 or lower_phrase in negatives or not any(char.isalpha() for char in phrase):
            logger.warning("Symptom extraction returned %r (too short, negative, or invalid) — falling back to raw notes", phrase)
            return notes, True

        logger.info("Symptom extraction OK: %r → %r (%d words)", notes[:60], phrase, len(phrase.split()))
        result = (phrase, False)
        _PHRASE_CACHE[cache_key] = result
        return result
    except Exception as exc:
        logger.warning("Symptom extraction FAILED (%s) — falling back to raw notes", exc)
        return notes, True


async def _generate_condition_hypotheses(
    notes: str,
    client: openai.AsyncOpenAI,
    model: str,
    extra_body: dict | None = None,
    max_n: int = 5,
) -> list[str]:
    """Ask the LLM for likely NAMED conditions for the presentation.

    The ICD-11 vector index maps disease *names* to codes far more reliably than
    symptom narratives (the symptom→disease gap: "palpitations, irregular pulse"
    embeds near symptom codes, not "atrial fibrillation"). Searching these named
    hypotheses alongside the symptom phrase surfaces disease codes the symptom
    query misses. Returns [] on any failure — the caller then relies on the
    symptom-phrase query alone, i.e. prior behaviour.
    """
    prompt = (
        "You are an expert clinical diagnostician.\n"
        "List the named medical conditions that are DIRECTLY SUPPORTED by the patient "
        "presentation below as complete, fully-qualified medical conditions (e.g., "
        "'Type 2 Diabetes Mellitus' instead of 'Type 2' or 'Diabetes', 'Cardiovascular "
        "Disease' instead of 'CVD').\n"
        "Grounding rules (CRITICAL — prevents hallucinated comorbidities):\n"
        "- Include a condition ONLY when the notes name it, OR a symptom/finding/lab/"
        "medication/vital in the notes directly implies it. Each condition must trace "
        "to something written below.\n"
        "- Do NOT add common co-travelling comorbidities that are not evidenced here "
        "(e.g. do NOT add 'Essential Hypertension' just because the patient has heart "
        "failure or diabetes — only if a high BP reading or anti-hypertensive is present).\n"
        "- Prefer fewer, well-grounded conditions over a long speculative list.\n"
        "Output rules:\n"
        "- Return ONLY a comma-separated list of the conditions\n"
        f"- Maximum {max_n} conditions\n"
        "- No numbering, no bullets, no explanation, no conversational filler\n\n"
        f"Presentation: {notes}\n\n"
        "Diagnoses:"
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            **_seed_kwargs(model),
            **({"extra_body": extra_body} if extra_body else {}),
        )
        txt = (resp.choices[0].message.content or "").strip()
        conds = [c.strip(" .;-\t") for c in txt.replace("\n", ",").split(",")]
        conds = [c for c in conds if c and 3 <= len(c) <= 60 and any(char.isalpha() for char in c)][:max_n]
        logger.info("Condition hypotheses: %s", conds)
        return conds
    except Exception as exc:
        logger.warning("Condition hypothesis generation failed (%s) — symptom query only", exc)
        return []


# Qualifier pairs where ICD-11 sibling leaves under one 4-char stem differ by a
# single discriminative word. When the LLM-emitted name carries one side of a
# pair, prefer the candidate whose title carries the same side — vector top-1
# can pick the wrong sibling because both leaves embed near-identically.
_QUALIFIER_PAIRS: tuple[tuple[str, ...], ...] = (
    ("reduced", "preserved", "mid-range", "mildly reduced"),
    ("acute", "chronic", "subacute"),
    ("with", "without"),
    ("primary", "secondary"),
    ("type 1", "type 2"),
    ("st elevation", "non-st elevation", "nstemi", "stemi"),
    ("left", "right", "bilateral"),
    ("benign", "malignant"),
)


def _pick_qualifier_match(name: str, hits: list[dict]) -> dict | None:
    """Sibling-leaf disambiguation for vector-resolved CC hints.

    Given a name and the top-K search_ddx hits, return the hit whose title best
    matches the qualifier carried by the name. Falls back to top-1 when no
    qualifier disambiguation applies.
    """
    if not hits:
        return None
    top = hits[0]
    if len(hits) < 2:
        return top

    name_l = name.lower()
    name_quals: set[str] = set()
    for pair in _QUALIFIER_PAIRS:
        for q in pair:
            if q in name_l:
                name_quals.add(q)
    if not name_quals:
        return top

    top_code = (top.get("code") or "").strip().upper()
    top_stem = top_code[:4]
    top_title_l = (top.get("title") or "").lower()
    if any(q in top_title_l for q in name_quals):
        return top  # top-1 already carries the right qualifier

    # Look for a same-stem sibling whose title carries one of the name's qualifiers
    # AND does NOT carry the opposing qualifier from the same pair.
    for cand in hits[1:]:
        cand_code = (cand.get("code") or "").strip().upper()
        if cand_code[:4] != top_stem:
            continue
        cand_title_l = (cand.get("title") or "").lower()
        for pair in _QUALIFIER_PAIRS:
            wanted = name_quals.intersection(pair)
            if not wanted:
                continue
            opposed = set(pair) - wanted
            if any(q in cand_title_l for q in wanted) and not any(q in cand_title_l for q in opposed):
                logger.info(
                    "CC hint qualifier-swap: %r → %s (was %s) on qualifier %s",
                    name, cand_code, top_code, sorted(wanted),
                )
                return cand
    return top


# Similarity margin within which a specific named-disease code is preferred over
# a vague Chapter-21 symptom / residual ".Y/.Z" code that the vector search
# happened to rank (marginally) higher. Resolving a chief-complaint diagnosis to
# the symptom code — e.g. "erectile dysfunction" → MF41 "Symptom or complaint of
# male sexual function" (0.705) instead of the disease code HA01.1 (0.704) —
# parks the CC-explicit boost on a code the demotion nets then sink, leaving the
# real disease unboosted and unable to out-rank a high-similarity background
# comorbidity (case 11: ED vs T2DM 0.824). Conservative: only near-ties swap.
SPECIFIC_OVER_VAGUE_MARGIN = 0.08


def _prefer_specific_hit(picked: dict | None, hits: list[dict]) -> dict | None:
    """If the resolver picked a vague Chapter-21/residual code, swap to the best
    non-vague code in `hits` within SPECIFIC_OVER_VAGUE_MARGIN of its similarity.

    Keeps the CC boost on a specific named disease (HA01.1) rather than its
    symptom/residual sibling (MF41), which `_demote_chapter21_codes` /
    `_demote_residual_subcodes` would otherwise sink — wasting the boost. Returns
    `picked` unchanged when it is already specific or no close non-vague code exists.
    """
    if not picked:
        return picked
    pcode = (picked.get("code") or "")
    if not (_is_chapter_21_code(pcode) or _is_residual_icd_code(pcode)):
        return picked
    picked_sim = float(picked.get("similarity") or 0.0)
    best = None
    for h in hits:
        code = (h.get("code") or "")
        if _is_chapter_21_code(code) or _is_residual_icd_code(code):
            continue
        sim = float(h.get("similarity") or 0.0)
        if sim >= picked_sim - SPECIFIC_OVER_VAGUE_MARGIN and (
            best is None or sim > float(best.get("similarity") or 0.0)
        ):
            best = h
    if best is not None and best is not picked:
        logger.info(
            "CC hint specific-over-vague: %s (%.3f) preferred over vague %s (%.3f)",
            best.get("code"), float(best.get("similarity") or 0.0), pcode, picked_sim,
        )
        return best
    return picked


async def _extract_cc_icd_hints(
    cc: str,
    client: openai.AsyncOpenAI,
    model: str,
    extra_body: dict | None = None,
    max_n: int = 6,
) -> list[dict]:
    """Extract high-confidence ICD-11 codes with per-code confidence from the
    chief complaint text alone.

    Returns a list of {"code": "BA41.0", "confidence": 0.92} dicts where
    confidence is the LLM's own calibrated assessment of how strongly the CC
    implies that specific diagnosis. The confidence is then used as a dynamic
    weight (CC_BOOST_WEIGHT × confidence) — never a hardcoded percentage.

    Confidence anchoring (same scale as the reranker):
      0.90+ : CC explicitly names the diagnosis or presents textbook syndrome
      0.70  : CC strongly suggests but one key finding is ambiguous
      0.50  : plausible but genuinely competing differentials
      <0.40 : should not be returned (below the "high confidence from CC" threshold)

    Returns [] on any failure — the caller falls back to the unmodified pool.
    """
    prompt = (
        "You are a clinical coding expert.\n"
        "Given the clinician's notes below (chief complaint + HPI + PE + their own "
        "diagnostic impressions), identify EVERY diagnosis a doctor would code — "
        "primary AND comorbid. Do not restrict to one 'primary' diagnosis.\n"
        "Rules:\n"
        "- Return a JSON array of objects: "
        "[{\"name\": \"Acute non-ST elevation myocardial infarction\", "
        "\"confidence\": 0.96, \"explicit\": true}]\n"
        "- `name` is the fully-qualified clinical diagnosis (NOT an ICD code — use "
        "the formal disease name as it appears in a textbook or guideline). "
        "Examples: 'Type 2 diabetes mellitus', 'Essential hypertension', "
        "'Atrial fibrillation', 'Acute non-ST elevation myocardial infarction'. "
        "Do NOT abbreviate — write 'Type 2 diabetes mellitus', not 'T2DM'.\n"
        "- `explicit` is true ONLY when the clinician has literally named the diagnosis "
        "in the notes (e.g. 'NSTEMI', 'newly diagnosed HFrEF', 'T2DM', 's/p PCI', "
        "'GDM', 'AF') — i.e. the doctor wrote it themselves, you are not inferring it.\n"
        "- When `explicit` is true, confidence MUST be >= 0.95 (the clinician's "
        "assertion is the evidence; do not hedge).\n"
        "- When `explicit` is false (you inferred the dx from symptoms/findings), "
        "confidence is YOUR calibrated probability that the notes imply that dx:\n"
        "    0.90+: textbook syndrome, no realistic competitor\n"
        "    0.70 : strongly suggests but one key finding ambiguous\n"
        "    0.50 : plausible but competing differentials\n"
        "- Include EVERY explicit clinician-named dx (no max for explicit codes).\n"
        "- For inferred dx, only include confidence >= 0.40. Combined total max 6 entries.\n"
        "- If the notes contain no nameable dx and are too vague to infer, return [].\n"
        "- Return ONLY the JSON array. No explanation.\n\n"
        f"Clinician's notes: {cc}\n\n"
        "JSON:"
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            **_seed_kwargs(model),
            **({"extra_body": extra_body} if extra_body else {}),
        )
        txt = (resp.choices[0].message.content or "").strip()
        # Parse JSON — robust to markdown fences
        raw = txt.strip().strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:].strip()
        
        try:
            hints = json.loads(raw)
        except Exception as json_exc:
            import re
            # Try to find array brackets [ ... ]
            match = re.search(r'\[\s*\{.*\}\s*\]', raw, re.DOTALL)
            if match:
                try:
                    hints = json.loads(match.group(0))
                except Exception:
                    logger.warning("Failed to parse CC ICD hints from bracket extraction. Raw content: %r", txt)
                    raise json_exc
            else:
                if "[]" in raw or "empty" in raw.lower() or "no codes" in raw.lower() or "none" in raw.lower():
                    hints = []
                else:
                    logger.warning("Failed to parse CC ICD hints JSON. Raw content: %r", txt)
                    raise json_exc

        if not isinstance(hints, list):
            return []

        # Collect (name, conf, explicit) triples; LLM only had to name the dx,
        # we resolve the code via vector search against the real ICD-11 corpus.
        # This avoids LLM code-hallucination (e.g. 8A11.1 instead of 5A11).
        named: list[tuple[str, float, bool]] = []
        for h in hints[:max_n]:
            if not isinstance(h, dict):
                continue
            name = (h.get("name") or "").strip()
            conf = float(h.get("confidence", 0))
            if not (name and 0.0 < conf <= 1.0 and 3 <= len(name) <= 120):
                continue
            named.append((name, round(conf, 3), bool(h.get("explicit", False))))

        if not named:
            logger.info("CC ICD hints: no named dx parsed from CC: %r", cc[:80])
            return []

        from ddx.search_ddx import search_ddx as _search_ddx
        # Resolve each name → top-1 ICD code in parallel.
        # Fetch top-5 so we can do qualifier-aware sibling disambiguation: when
        # two leaf codes share the same 4-char ICD stem and differ only by a
        # qualifier word (reduced/preserved, acute/chronic, with/without, etc.),
        # vector top-1 can pick the wrong leaf. Override the pick when the
        # emitted name explicitly carries the qualifier of the lower-ranked leaf.
        async def _resolve(name: str):
            try:
                hits = await _search_ddx(name, top_k=5)
                if not hits:
                    return None
                return _prefer_specific_hit(_pick_qualifier_match(name, hits), hits)
            except Exception as exc:
                logger.warning("CC hint resolve failed for %r: %s", name, exc)
                return None

        resolved = await asyncio.gather(*[_resolve(n) for n, _, _ in named])

        # Drop weak matches — kills hallucinated entities the corpus doesn't recognise.
        SIM_FLOOR = 0.55
        valid: list[dict] = []
        seen_codes: set[str] = set()
        for (name, conf, explicit), hit in zip(named, resolved):
            if not hit:
                continue
            sim = float(hit.get("similarity") or 0.0)
            code = (hit.get("code") or "").strip().upper()
            if not code or sim < SIM_FLOOR or code in seen_codes:
                continue
            seen_codes.add(code)
            valid.append({
                "code": code,
                "confidence": conf,
                "explicit": explicit,
                "resolved_name": name,
                "resolved_similarity": round(sim, 3),
            })

        logger.info("CC ICD hints: %s from CC: %r", valid, cc[:80])
        return valid
    except Exception as exc:
        logger.warning("CC ICD hint extraction failed (%s) — no pool injection", exc)
        return []


async def _regex_disease_hints(case: PatientCase) -> list[dict]:
    """Deterministic disease-name → ICD code resolver. Augments `_extract_cc_icd_hints`.

    Scans chief_complaint + history + comorbidities + current_medications for
    aliases in `_DISEASE_ALIAS_MAP` and resolves each canonical name to its
    top-1 ICD code via `search_ddx`. Output shape matches `_extract_cc_icd_hints`
    so callers can merge both lists transparently.

    Why this exists: on Mode-B (task-framed) visits the LLM symptom/hint
    extractors occasionally drop a literally-written diagnosis (e.g. "NSTEMI")
    from their output, knocking the right code out of the vector pool. A regex
    on the raw text guarantees the named code is always represented.
    """
    text_parts = [
        case.chief_complaint or "",
        case.history or "",
        ", ".join(case.comorbidities or []),
        ", ".join(case.current_medications or []),
    ]
    blob = " ".join(text_parts).lower()
    if not blob.strip():
        return []
    # Only the chief complaint carries the clinician's literal naming of the
    # reason-for-visit. A disease that appears only in the comorbidity list is a
    # documented background condition — high-confidence, but NOT "clinician-named
    # explicit". Marking those explicit lets a comorbidity (e.g. T2DM) claim the
    # same top-3/pin-to-#1 authority as the actual chief-complaint dx (HFrEF),
    # so we scope `explicit` to chief-complaint matches only.
    cc_blob = (case.chief_complaint or "").lower()
    import re as _re
    matched: list[tuple[str, bool]] = []
    seen_names: set[str] = set()
    for alias, canonical in _DISEASE_ALIAS_MAP.items():
        if canonical in seen_names:
            continue
        pattern = r"\b" + _re.escape(alias) + r"\b"
        if _re.search(pattern, blob):
            in_cc = bool(_re.search(pattern, cc_blob))
            matched.append((canonical, in_cc))
            seen_names.add(canonical)
    if not matched:
        return []

    from ddx.search_ddx import search_ddx as _search_ddx
    async def _resolve(name: str):
        try:
            hits = await _search_ddx(name, top_k=6)
            if not hits:
                return None
            return _prefer_specific_hit(hits[0], hits)
        except Exception as exc:
            logger.warning("Regex hint resolve failed for %r: %s", name, exc)
            return None
    resolved = await asyncio.gather(*[_resolve(n) for n, _ in matched])

    SIM_FLOOR = 0.55
    out: list[dict] = []
    seen_codes: set[str] = set()
    for (name, in_cc), hit in zip(matched, resolved):
        if not hit:
            continue
        sim = float(hit.get("similarity") or 0.0)
        code = (hit.get("code") or "").strip().upper()
        if not code or sim < SIM_FLOOR or code in seen_codes:
            continue
        seen_codes.add(code)
        out.append({
            "code": code,
            # Chief-complaint match → clinician-named (explicit, conf 0.95).
            # Chart/comorbidity-only match → high-confidence inferred (explicit=False).
            "confidence": 0.95 if in_cc else 0.90,
            "explicit": in_cc,
            "resolved_name": name,
            "resolved_similarity": round(sim, 3),
            "source": "regex_fallback",
        })
    if out:
        logger.info("Regex disease hints: %d code(s) injected — %s",
                    len(out), [(h["code"], h["resolved_name"]) for h in out])
    return out


# Vitals-driven can't-miss red-flag injection. Some time-critical syndromes are
# defined by PHYSIOLOGY, not by a named complaint: a patient who self-reports
# "dengue" while in septic shock (BP 80/50, HR 130, fever, altered mental status)
# must still surface sepsis in the DDx (TESTING_STRATEGY ADV-02). Vector search
# anchors on the chief-complaint text, and the icd11_codes corpus carries no
# general sepsis code, so neither retrieval nor the rerank red-flag override can
# introduce it. This deterministic guard injects a flagged can't-miss candidate
# straight into the pool when the vitals match a shock syndrome. The injected code
# is the recognised ICD-11 red-flag label; it has no CPG in the corpus and routes
# out_of_scope — which is the correct "escalate, no local care-plan" behaviour for
# an emergency outside the loaded guideline set. Each rule is intentionally narrow
# (full physiology triad) so it never fires on stable patients.
_REDFLAG_VITALS_RULES: tuple[dict, ...] = (
    {
        "name": "septic_shock",
        "code": "1G41.0",
        "title": "Sepsis with septic shock",
        # Hypotension + fever + tachycardia = shock physiology with an infective
        # driver. Altered mental status / rigors in the text strengthen but are
        # not required — the vitals triad alone is a can't-miss.
        "predicate": lambda v, _t: (
            v.get("sbp") is not None and v["sbp"] < 90
            and v.get("temp") is not None and v["temp"] >= 38.0
            and v.get("hr") is not None and v["hr"] > 100
        ),
        "reason": "hypotension + fever + tachycardia — septic shock cannot be missed",
    },
)


def _redflag_vitals_hints(case: PatientCase) -> list[dict]:
    """Synthetic can't-miss DDx candidates triggered by shock physiology.

    Returns pool-ready dicts (same shape stage_2_ddx feeds into DDxResult) for any
    red-flag rule whose vitals predicate matches. High base similarity (0.90) keeps
    the candidate in the top-K even if the LLM rerank degrades to math order, while
    override_reason marks it as a deliberate red-flag promotion for the trace.
    """
    vitals = case.vitals or {}
    text = " ".join([
        case.chief_complaint or "",
        case.history or "",
        ", ".join(case.comorbidities or []),
    ]).lower()
    out: list[dict] = []
    for rule in _REDFLAG_VITALS_RULES:
        try:
            if rule["predicate"](vitals, text):
                out.append({
                    "code": rule["code"],
                    "title": rule["title"],
                    "similarity": 0.90,
                    "base_similarity": 0.90,
                    "cc_boost": 0.0,
                    "cc_confidence": None,
                    "cc_explicit": False,
                    "reasoning": [f"RED-FLAG (vitals-driven): {rule['reason']}"],
                    "override_reason": f"red_flag_cant_miss: {rule['name']} from vitals",
                    "source": "redflag_vitals",
                })
        except Exception as exc:
            logger.warning("Red-flag vitals rule %r failed: %s", rule.get("name"), exc)
    return out


async def stage_2_ddx(
    case: PatientCase,
    top_k: int = 5,
    rerank: bool = True,
    emit=None,                      # async callable | None; passed through to _llm_rerank_ddx
) -> list[DDxResult]:
    """
    Return top-k ICD-11 differential diagnoses for the patient case.

    Pass 1: vector similarity + morbidity tabulation (search_ddx).
    Pass 2: Gemini 2.5 Flash thinking re-ranks by clinical probability.
    Set rerank=False to skip Pass 2 (e.g. in unit tests or latency-sensitive paths).
    When emit is provided, thinking tokens are streamed as thinking_delta events.
    """
    from ddx.search_ddx import search_ddx

    # Honour STAGE2_LLM_* override for extraction (same fallback as _llm_rerank_ddx).
    # When Google API is quota-exhausted, both rerank and extraction use MiMo.
    _s2_base = os.getenv("STAGE2_LLM_BASE_URL")
    _s2_key = os.getenv("STAGE2_LLM_API_KEY")
    _s2_model = os.getenv("STAGE2_LLM_CHOICE")
    _s2_provider = os.getenv("STAGE2_LLM_PROVIDER", "")
    _using_override = bool(_s2_base and _s2_key and _s2_model)

    client = _make_openai_client(
        base_url=_s2_base or os.getenv("LLM_BASE_URL"),
        api_key=_s2_key or os.getenv("LLM_API_KEY"),
        provider=_s2_provider,
        max_retries=0,   # extraction has a clean fallback; don't waste 3s on 429 retries
    )
    extraction_model = (
        _s2_model if _using_override
        else os.getenv("SYMPTOM_EXTRACT_MODEL", os.getenv("LLM_CHOICE", "gemini-2.0-flash"))
    )
    # mimo (and other reasoning models) must have thinking disabled for extraction, 
    # or they burn the whole token budget on hidden reasoning and return empty content 
    # → silent fallback to the raw, diluting notes.
    extraction_extra_body = (
        {"chat_template_kwargs": {"enable_thinking": False}} if "mimo" in extraction_model.lower() else None
    )
    query, extraction_fell_back = await _extract_symptom_phrase(
        case.chief_complaint, client, extraction_model,
        extra_body=extraction_extra_body, case=case,
    )

    if emit is not None:
        if extraction_fell_back:
            # Surface the silent fail-open: extraction produced nothing usable, so the
            # raw (diluting) notes are being searched verbatim. This is the indicator
            # that would have made the mimo-empty regression obvious in the UI.
            await emit("sub_step", {
                "stage": 2,
                "detail": f"⚠ Symptom extraction fell back to raw notes: \"{query}\"",
                "badge": "fallback",
            })
        else:
            await emit("sub_step", {
                "stage": 2,
                "detail": f"Extracted symptom query: \"{query}\"",
                "badge": "DDx",
            })

    fetch_k = top_k * 2 if rerank else top_k

    # Multi-query retrieval to bridge the symptom→disease gap. We search BOTH the
    # symptom phrase (recall on symptom codes) AND a few LLM-named condition
    # hypotheses (recall on disease codes). Disease names map to ICD codes far more
    # reliably than symptom narratives, so this surfaces e.g. atrial fibrillation
    # that the phrase alone misses. Candidates are pooled by code, keeping the best
    # similarity seen across queries. Fails open to the phrase-only query.
    hypotheses = await _generate_condition_hypotheses(
        _build_symptom_text(case), client, extraction_model, extra_body=extraction_extra_body
    )
    if hypotheses and emit is not None:
        await emit("sub_step", {
            "stage": 2,
            "detail": "Condition hypotheses: " + ", ".join(hypotheses),
            "badge": "DDx",
        })

    # CC-boosted ICD hint injection — extract high-confidence ICD-11 codes with
    # per-code confidence directly from the chief complaint. The confidence is the
    # LLM's own calibrated assessment (dynamic, not hardcoded). It becomes an additive
    # boost signal: cc_boost = CC_BOOST_WEIGHT × confidence, just like inclusion_match.
    cc_icd_hints = await _extract_cc_icd_hints(
        case.chief_complaint, client, extraction_model, extra_body=extraction_extra_body
    )
    # Build a lookup: code -> hint dictionary for pool injection
    cc_hints_map: dict[str, dict] = {}
    if cc_icd_hints:
        for hint in cc_icd_hints:
            cc_hints_map[hint["code"]] = hint

    # Deterministic regex fallback — augments (does NOT replace) the LLM CC
    # hints above. LLM-derived hints win on key collisions; regex codes only
    # fill in what the LLM missed. Stabilises the candidate pool across reruns
    # on Mode-B (task-framed) visits where the LLM extractor occasionally drops
    # literally-written diagnoses (NSTEMI, AF, T2DM) from its output.
    regex_hints = await _regex_disease_hints(case)
    regex_added: list[str] = []
    for hint in regex_hints:
        if hint["code"] not in cc_hints_map:
            cc_hints_map[hint["code"]] = hint
            regex_added.append(hint["code"])
    if regex_added and emit is not None:
        regex_items = [
            {"code": code, "name": cc_hints_map.get(code, {}).get("resolved_name")}
            for code in regex_added
        ]
        regex_label = ", ".join(
            f'{it["name"]} ({it["code"]})' if it["name"] else it["code"]
            for it in regex_items
        )
        await emit("sub_step", {
            "stage": 2,
            "kind": "regex_codes",
            "detail": "Extra codes caught by text-matching your notes: " + regex_label,
            "badge": "safety-net",
            "data": regex_items,
        })

    if cc_icd_hints:
        if emit is not None:
            cc_items = [
                {
                    "code": h["code"],
                    "name": h.get("resolved_name"),
                    "confidence": h["confidence"],
                    "explicit": bool(h.get("explicit")),
                }
                for h in cc_icd_hints
            ]
            detail_parts = []
            for it in cc_items:
                qual = "you named this" if it["explicit"] else f'AI {it["confidence"]:.0%} sure'
                label = f'{it["name"]} ({it["code"]})' if it["name"] else it["code"]
                detail_parts.append(f'{label} — {qual}')
            await emit("sub_step", {
                "stage": 2,
                "kind": "cc_priority",
                "detail": "Diagnoses the AI pulled from the chief complaint: " + ", ".join(detail_parts),
                "badge": "from chief complaint",
                "data": cc_items,
            })

    queries = [q for q in ([query] + hypotheses) if q and len(q.strip()) >= 3 and any(char.isalpha() for char in q)]
    if not queries:
        queries = [case.chief_complaint]
    search_results = await asyncio.gather(
        *(search_ddx(q, top_k=fetch_k) for q in queries),
        return_exceptions=True,
    )
    pool: dict[str, dict] = {}
    for res in search_results:
        if isinstance(res, Exception):
            logger.warning("A DDx sub-query failed: %s", res)
            continue
        for r in res:
            code = r.get("code")
            if not code:
                continue
            if code not in pool or r.get("similarity", 0) > pool[code].get("similarity", 0):
                pool[code] = r

    # Inject CC-hinted codes that are missing from the pool entirely.
    # We fetch them via search_ddx(code) to get the canonical DDx row with all fields.
    if cc_hints_map:
        missing_codes = [c for c in cc_hints_map if c not in pool]
        if missing_codes:
            fetch_results = await asyncio.gather(
                *(search_ddx(code, top_k=5) for code in missing_codes),
                return_exceptions=True,
            )
            for hint_code, hint_res in zip(missing_codes, fetch_results):
                if isinstance(hint_res, Exception):
                    continue
                matched = next((r for r in hint_res if r.get("code") == hint_code), None)
                if matched:
                    pool[hint_code] = matched
                    logger.info("CC-boost: injected missing code %s into pool", hint_code)
                else:
                    logger.info("CC-boost: code %s not found in DDx index", hint_code)

        # Apply the dynamic CC boost as an additive field on pool entries.
        # cc_boost = CC_EXPLICIT_BOOST if explicit else CC_BOOST_WEIGHT × confidence
        # This is stored as a field on the pool dict so DDxResult picks it up.
        for code, hint in cc_hints_map.items():
            if code in pool:
                conf = hint["confidence"]
                explicit = hint.get("explicit", False)
                boost_val = CC_EXPLICIT_BOOST if explicit else round(CC_BOOST_WEIGHT * conf, 4)
                pool[code]["cc_boost"] = boost_val
                pool[code]["cc_confidence"] = conf
                pool[code]["cc_explicit"] = explicit
                logger.info(
                    "CC-boost applied: %s confidence=%.2f explicit=%s → boost=+%.3f",
                    code, conf, explicit, boost_val,
                )

    # Vitals-driven can't-miss injection (e.g. septic-shock physiology). Runs
    # regardless of chief-complaint text because shock is defined by vitals, not
    # by what the patient self-reports. Injected straight into the pool so the
    # reranker and the clinician both see the red-flag candidate.
    for rf in _redflag_vitals_hints(case):
        code = rf["code"]
        if code not in pool:
            pool[code] = rf
            logger.info(
                "Red-flag vitals injection: %s (%s) added to DDx pool", code, rf["title"]
            )
            if emit is not None:
                await emit("sub_step", {
                    "stage": 2,
                    "detail": f"⚠ Red-flag vitals: {rf['title']} surfaced as can't-miss",
                    "badge": "red-flag",
                })

    # Sort by (similarity + cc_boost) so CC-boosted codes surface to top-K for
    # the LLM reranker. The cc_boost is additive — a high-confidence CC code with
    # moderate vector similarity will still outrank a low-relevance code with high
    # vector similarity alone.
    raw = sorted(
        pool.values(),
        key=lambda r: r.get("similarity", 0) + r.get("cc_boost", 0),
        reverse=True,
    )[: max(fetch_k, 10)]

    results: list[DDxResult] = []
    for r in raw:
        try:
            results.append(
                DDxResult(**{k: v for k, v in r.items() if k in DDxResult.model_fields})
            )
        except Exception as exc:
            logger.warning("Skipping malformed DDx result %r: %s", r, exc)

    # Compute full final_score (base + inclusion + cc_boost - exclusion) and re-sort
    # so math_rank reflects the complete composite score. Without this, pool sort order
    # (similarity + cc_boost only) would assign math_rank ignoring inclusion/exclusion
    # — e.g. a code with 0.65 sim + 0.23 inclusion = 0.88 final would be math_rank #3
    # behind codes with 0.69 sim but 0.69 final. The doctor sees 88% ranked below 69%.
    for r in results:
        if r.score_breakdown is None:
            r.score_breakdown = build_score_breakdown(r)
        r.final_score = r.score_breakdown.final_score
    results.sort(key=lambda r: r.final_score or 0, reverse=True)

    if rerank and results:
        results = await _llm_rerank_ddx(case, results, emit=emit)

    # Deterministic safety net: push Chapter 21 (symptoms / signs / findings)
    # codes below similarly-scored disease codes. Backstops case-11-style
    # mis-ranks where the LLM left `MF41` (symptom complaint) above the actual
    # disease code at near-identical score. Runs whether or not LLM rerank ran.
    results = _demote_chapter21_codes(results)

    # Deterministic: keep named categories above their '.Y/.Z' residual siblings
    # (e.g. BC81.3 above BC81.3Y). Order-only; no code injection.
    results = _demote_residual_subcodes(results)

    # Deterministic guarantee: a clinician-named chief-complaint dx owns #1, so a
    # boosted comorbidity can't steal the "AI top pick" slot (runs after all other
    # reordering so it has the final word on the primary).
    results = _pin_chief_complaint_primary(results)

    top = results[:top_k]
    # Attach the numeric score breakdown now (base / inclusion / exclusion / final)
    # so the streamed top-5 already shows "why this rank". route_method stays None
    # until stage_3_route resolves the match and rebuilds the breakdown with a badge.
    for r in top:
        if r.score_breakdown is None:
            r.score_breakdown = build_score_breakdown(r)
    return top


def _ddx_inclusion_score(result: DDxResult) -> float:
    if result.inclusion_similarity is not None:
        return float(result.inclusion_similarity)
    return 0.0


def build_out_of_scope_info(
    ddx: list[DDxResult],
    threshold: float = OUT_OF_SCOPE_INCL_THRESHOLD,
) -> OutOfScopeInfo | None:
    """
    Build a structured out-of-scope signal when DDx confidence is weak.

    Stage 3 calls this only after exact/ancestor/sibling/semantic routing returns
    no CPGs. The inclusion-score gate prevents a confident ICD hit with pending
    scope data from being over-labelled as out of scope.
    """
    considered = [
        {
            "code": d.code,
            "title": d.title,
            "similarity": d.similarity,
            "inclusion_score": _ddx_inclusion_score(d),
            "final_score": d.final_score,
        }
        for d in ddx
    ]
    max_inclusion = max((_ddx_inclusion_score(d) for d in ddx), default=0.0)
    if max_inclusion >= threshold:
        return None

    top_codes = ", ".join(f"{d.code} {d.title}" for d in ddx[:3]) or "none"
    return OutOfScopeInfo(
        icd_candidates_considered=considered,
        max_inclusion_score=round(max_inclusion, 3),
        message=(
            "No loaded CPG covers this query. "
            f"Top ICD-11 candidates: {top_codes}."
        ),
    )


# ---------------------------------------------------------------------------
# Stage 3 — Route
# ---------------------------------------------------------------------------

# Keyword → procedure_scope tag mapping.
# Keys are lowercase substrings searched in the clinical context text.
# Values are the canonical snake_case tags stored in documents.procedure_scope.
_PROCEDURE_KEYWORD_MAP: dict[str, str] = {
    "anaesthe": "anaesthetic_safety",
    "anesthet": "anaesthetic_safety",
    "sedation": "anaesthetic_safety",
    "pre-op": "pre_op_assessment",
    "preop": "pre_op_assessment",
    "pre op": "pre_op_assessment",
    "pre-anaesthe": "pre_op_assessment",
    "preanae": "pre_op_assessment",
    "preanaesthe": "pre_op_assessment",
    "anaesthetic planning": "anaesthetic_planning",
    "anaesthetic assessment": "pre_op_assessment",
    "perioperative": "pre_op_assessment",
    "peri-operative": "pre_op_assessment",
    "surgery": "pre_op_assessment",
    "surgical": "pre_op_assessment",
    "operation": "pre_op_assessment",
    "extraction": "pre_op_assessment",
    "dental procedure": "pre_op_assessment",
    "tooth extraction": "pre_op_assessment",
    "elective procedure": "pre_op_assessment",
    "biopsy": "pre_op_assessment",
    "endoscop": "pre_op_assessment",
    "colonoscop": "pre_op_assessment",
    "intubat": "anaesthetic_equipment_safety",
    "airway": "anaesthetic_equipment_safety",
    "anaesthetic equipment": "anaesthetic_equipment_safety",
    "medication safety": "anaesthetic_medication_safety",
    "drug labelling": "medication_labelling",
    "syringe label": "medication_labelling",
    "high alert": "high_alert_medication",
    "malignant hyperthermia": "malignant_hyperthermia_management",
    "coronary intervention": "percutaneous_coronary_intervention",
    "pci": "percutaneous_coronary_intervention",
    "angiograph": "coronary_angiography",
    "stent": "coronary_stenting",
    "thrombectom": "endovascular_thrombectomy",
    "stroke workflow": "stroke_workflow",
    "revasculariz": "revascularization",
    "cardiac rehab": "cardiac_rehabilitation",
    "rehabilitation": "cardiac_rehabilitation",
    "warfarin": "warfarin_initiation",
    "inr monitor": "inr_monitoring",
    "anticoagul": "warfarin_initiation",
}


def _extract_procedure_tags(clinical_text: str) -> list[str]:
    """
    Return unique procedure_scope tags inferred from free-text clinical context.
    Matches are case-insensitive substring checks against _PROCEDURE_KEYWORD_MAP.
    """
    if not clinical_text:
        return []
    lower = clinical_text.lower()
    found: set[str] = set()
    for keyword, tag in _PROCEDURE_KEYWORD_MAP.items():
        if keyword in lower:
            found.add(tag)
    return list(found)


# CPGs that apply to only one biological sex. Routing a male to an obstetric CPG
# (or a female to erectile-dysfunction) is never clinically valid — filter these
# out and surface the exclusion in the trace. Only fires for an explicit "M"/"F";
# sex None/"other" never filters, since we can't be sure.
_SEX_REQUIRED_CPGS: dict[str, str] = {
    "Heart-Disease-in-Pregnancy(2nd Edition)": "F",
    "Diabetes-in-Pregnancy(2017)": "F",
    "Cervical-Cancer(2nd Edition)": "F",
    "CVD-Prevention-Women(2016)": "F",
    "Erectile-Dysfunction(2024)": "M",
}


def _required_sex_for_cpg(cpg_name: str) -> str | None:
    """Return the sex a CPG is restricted to ('M'/'F'), or None if unrestricted."""
    if cpg_name in _SEX_REQUIRED_CPGS:
        return _SEX_REQUIRED_CPGS[cpg_name]
    # Robust catch for any obstetric CPG added later, even if not in the registry.
    low = cpg_name.lower()
    if "pregnancy" in low or "antenatal" in low or "obstetric" in low:
        return "F"
    return None


def sex_incompatible_reason(cpg_name: str, sex: str | None) -> str | None:
    """If this CPG is incompatible with the patient's sex, return a reason; else None."""
    if sex not in ("M", "F"):
        return None
    req = _required_sex_for_cpg(cpg_name)
    if req is not None and req != sex:
        who = "female" if req == "F" else "male"
        return f"{who}-only CPG (patient sex: {sex})"
    return None


_PREGNANCY_CONTEXT_KEYWORDS = (
    "pregnan",
    "gestation",
    "antenatal",
    "obstetric",
    "trimester",
    "gravida",
    "para",
    "foetal",
    "fetal",
)


def pregnancy_context_missing_reason(cpg_name: str, clinical_context: str | None) -> str | None:
    """Return a reason when a pregnancy CPG is routed for a non-pregnancy case."""
    low_name = cpg_name.lower()
    if not any(word in low_name for word in ("pregnancy", "antenatal", "obstetric")):
        return None
    low_context = (clinical_context or "").lower()
    if any(keyword in low_context for keyword in _PREGNANCY_CONTEXT_KEYWORDS):
        return None
    return "pregnancy CPG requires pregnancy/obstetric context"


def _case_cpg_priority(ref: CPGDocRef, ddx: list[DDxResult], clinical_context: str | None) -> tuple[float, int, str]:
    """Rank candidate CPGs by semantic fit to the selected ICD scope."""
    route_tie_break = {
        "exact": 4,
        "procedure_scope": 3,
        "sibling": 2,
        "ancestor_d1": 1,
        "ancestor_d1_sibling": 0,
        "ancestor_d1_sibling_child": 0,
        "ancestor_d2": 0,
        "semantic_scope": 0,
    }.get(ref.match_type, 0)
    return ref.score, route_tie_break, ref.cpg_name


# ---------------------------------------------------------------------------
# Chapter-21 (symptoms / signs / findings) demotion safety net
# ---------------------------------------------------------------------------
# ICD-11 Chapter 21 — "Symptoms, signs or clinical findings, not elsewhere
# classified" — uses stem codes prefixed with `M`. These describe complaints
# (e.g. MF41 "Symptom or complaint of male sexual function") rather than
# diseases. Stage 2 vector search and the LLM rerank sometimes leave a
# Chapter 21 candidate at rank 1 even when a similarly-scored disease code
# exists below — which lands the wrong "Major" code in the Major/Minor flow.
# This deterministic pairwise-swap pass is a safety net under the prompt's
# SPECIFICITY rule. It only fires when a disease candidate sits within
# CHAPTER21_DEMOTION_TOLERANCE of the symptom code's score, so a strongly
# scored symptom isn't yielded to a weakly scored disease code.

CHAPTER21_DEMOTION_TOLERANCE = float(os.getenv("CHAPTER21_DEMOTION_TOLERANCE", "0.05"))


def _is_chapter_21_code(code: str | None) -> bool:
    """ICD-11 Chapter 21 (Symptoms / signs / findings) stem codes start with `M`."""
    if not code:
        return False
    return code[0].upper() == "M"


def _demote_chapter21_codes(results: list[DDxResult]) -> list[DDxResult]:
    """Push Chapter 21 (symptoms / signs / findings) codes below similarly-
    scored disease codes via pairwise top-down swaps until stable.

    A swap fires only when the disease code's score is within
    `CHAPTER21_DEMOTION_TOLERANCE` of the Chapter 21 code above it — so a
    strongly-scored Chapter 21 code (e.g. when the symptom *is* the diagnosis,
    such as a vague presentation with no candidate disease close by) keeps its
    rank.
    """
    if not results:
        return results
    ordered = list(results)
    # Bounded outer loop — at worst we do O(n²) swaps to fully sort.
    for _ in range(len(ordered)):
        swapped = False
        for i in range(len(ordered) - 1):
            top, below = ordered[i], ordered[i + 1]
            if not _is_chapter_21_code(top.code):
                continue
            if _is_chapter_21_code(below.code):
                continue
            top_score = top.final_score if top.final_score is not None else top.similarity
            below_score = below.final_score if below.final_score is not None else below.similarity
            if top_score is None or below_score is None:
                continue
            if (top_score - below_score) <= CHAPTER21_DEMOTION_TOLERANCE:
                ordered[i], ordered[i + 1] = below, top
                # Record the demotion reason on the symptom code for trace
                # transparency. If it already has an override_reason, append.
                gap = top_score - below_score
                tag = f"chapter21_demotion: yielded to {below.code} (Δ={gap:.3f})"
                top.override_reason = (
                    f"{top.override_reason}; {tag}" if top.override_reason else tag
                )
                swapped = True
        if not swapped:
            break
    return ordered


def _is_residual_icd_code(code: str) -> bool:
    """ICD-11 residual marker: a code whose terminal character is 'Y' ("other
    specified") or 'Z' ("unspecified") — e.g. BC81.3Y, BA5Z, 8B1Y. Dynamic; no
    per-code table. These are intentionally vaguer than their named siblings."""
    c = (code or "").strip().upper()
    return bool(c) and c[-1] in ("Y", "Z")


def _demote_residual_subcodes(results: list[DDxResult]) -> list[DDxResult]:
    """Stable-demote residual '.Y'/'.Z' codes below any NON-residual code that
    shares their 4-char category stem. Returning "atrial fibrillation, unspecified"
    (BC81.3Y) above the named "atrial fibrillation" (BC81.3) is a mis-rank — the
    named category is strictly more informative. Fires only when a named same-stem
    code is actually present, so a lone residual (the only code for its family)
    keeps its rank. Dynamic, order-only — injects nothing, so it cannot conflict
    with sibling-collapse or perturb which codes exist for Stage 3."""
    if len(results) < 2:
        return results
    named_stems = {
        (r.code or "").strip().upper()[:4]
        for r in results
        if r.code and not _is_residual_icd_code(r.code)
    }
    keep: list[DDxResult] = []
    demote: list[DDxResult] = []
    for r in results:
        code = (r.code or "").strip().upper()
        if code and _is_residual_icd_code(code) and code[:4] in named_stems:
            tag = f"residual_demotion: '{code}' yielded to named same-stem code"
            r.override_reason = f"{r.override_reason}; {tag}" if r.override_reason else tag
            demote.append(r)
        else:
            keep.append(r)
    if not demote:
        return results
    logger.info(
        "DDx residual-subcode demotion: moved %d '.Y/.Z' residual(s) below named same-stem codes",
        len(demote),
    )
    return keep + demote


def _pin_chief_complaint_primary(results: list[DDxResult]) -> list[DDxResult]:
    """Guarantee a clinician-named (cc_explicit) diagnosis occupies rank #1.

    The LLM reranker's CLINICIAN-NAMED rule only promises explicit codes land in
    the *top-3* (see stage2_ddx_rerank.txt). That lets a high-inclusion comorbidity
    (e.g. "other specified essential hypertension", boosted by a WHO inclusion-term
    match) outrank the actual chief-complaint diagnosis and grab the UI "AI top pick"
    badge while the named dx sits at #2/#3. This deterministic post-pass lifts the
    highest-ranked explicit code to #1.

    Guards preserve legitimate exceptions:
      - A can't-miss red-flag promotion at #1 (override_reason="red_flag_cant_miss…")
        outranks everything and is left in place.
      - If #1 is already a specific explicit dx, nothing changes.
      - Only SPECIFIC explicit codes are pinned — a vague Chapter-21 symptom or
        '.Y/.Z' residual explicit code is never promoted over a named disease
        code, so this pass can't undo the demotion safety nets above it.
    """
    if len(results) < 2:
        return results
    top = results[0]
    if (top.override_reason or "").startswith("red_flag_cant_miss"):
        return results

    def _is_vague(code: str | None) -> bool:
        # A Chapter-21 symptom code (MF41) or a '.Y/.Z' residual is strictly
        # less informative than a named disease code.
        return _is_chapter_21_code(code) or _is_residual_icd_code(code or "")

    # Only pin a SPECIFIC clinician-named dx. The CC-hint resolver can resolve a
    # symptom phrase ("erectile dysfunction") to a vague code (MF41 "complaint of
    # male sexual function") and mark it cc_explicit; pinning that to #1 would
    # silently undo _demote_chapter21_codes / _demote_residual_subcodes — the
    # case-11 MF41 bug, where the symptom code outranked the actual HA01.x ED
    # codes. If no specific explicit dx exists, respect the demotion order rather
    # than resurrecting a vague code.
    if getattr(top, "cc_explicit", False) and not _is_vague(top.code):
        return results
    idx = next(
        (
            i
            for i, r in enumerate(results)
            if getattr(r, "cc_explicit", False) and not _is_vague(r.code)
        ),
        None,
    )
    if idx is None or idx == 0:
        return results
    promoted = results.pop(idx)
    tag = "cc_explicit_primary: clinician-named chief-complaint dx pinned to #1"
    promoted.override_reason = (
        f"{promoted.override_reason}; {tag}" if promoted.override_reason else tag
    )
    results.insert(0, promoted)
    logger.info(
        "CC-primary pin: promoted explicit %s to #1 (was rank %d, displaced %s)",
        promoted.code, idx + 1, top.code,
    )
    return results


# ---------------------------------------------------------------------------
# Major / Minor allocation helpers (T1–T3 in DDx_Top5_And_Major_Minor_Suggestion.md)
# ---------------------------------------------------------------------------

# Total CPG slots that Stage 3 may return after Major/Minor allocation.
# Single-code (Major only) keeps the historical cap of 3 to stay focused; once
# any Minor is picked, the quota lifts to 5 so each tier gets at least one slot.
STAGE3_MAX_CPGS = 5

# Headless auto-select rule. If the gap between rank-1 and rank-2 DDx codes is
# below this, treat rank-2 as a co-primary and route it as Minor; else route
# rank-1 alone. Default chosen against the existing eval traces — adjust via env
# `STAGE3_HEADLESS_GAP` if calibration changes.
STAGE3_HEADLESS_GAP = float(os.getenv("STAGE3_HEADLESS_GAP", "0.15"))


def _allocate_major_minor(n_minor: int) -> tuple[int, list[int]]:
    """Return `(major_allot, minor_allots)` per the T2 allocation table.

    Major code stays at 3 while 0–2 minors are picked, drops to 2 with 3 minors,
    and to 1 only in the all-five "worst case." Minor codes are always
    guaranteed at least 1 slot. Formula:
        major_allot   = max(1, min(3, 5 − n_minor))
        minor_allots  = `n_minor` copies of 1 (since 5 − major_allot ≤ n_minor
                        for n_minor ≤ 4 except n_minor=1 which gets the leftover 2)

    Concretely:
        n_minor=0 → (3, [])               total 3   (single-pillar)
        n_minor=1 → (3, [2])              total 5   (rank-1 minor gets 2)
        n_minor=2 → (3, [1, 1])           total 5
        n_minor=3 → (2, [1, 1, 1])        total 5
        n_minor=4 → (1, [1, 1, 1, 1])     total 5   (worst case)

    Args:
        n_minor: count of Minor-tier codes (0..4).
    Returns:
        (major_allot, minor_allots) where len(minor_allots) == n_minor.
    """
    if n_minor < 0:
        raise ValueError(f"n_minor must be ≥ 0, got {n_minor}")
    if n_minor > STAGE3_MAX_CPGS - 1:
        raise ValueError(
            f"n_minor must be ≤ {STAGE3_MAX_CPGS - 1} (got {n_minor}); "
            "Stage 2 caps DDx at 5 codes (1 major + 4 minors)"
        )

    if n_minor == 0:
        return 3, []

    major_allot = max(1, min(3, STAGE3_MAX_CPGS - n_minor))
    remaining = STAGE3_MAX_CPGS - major_allot
    # Distribute remaining evenly to minors. For n_minor ∈ [2..4] remaining // n_minor == 1.
    # For n_minor == 1, remaining is 2 so the single minor takes both leftover slots.
    base = remaining // n_minor
    extra = remaining - base * n_minor
    minor_allots = [base + (1 if i < extra else 0) for i in range(n_minor)]
    return major_allot, minor_allots


def _auto_select_codes(ddx: list[DDxResult]) -> tuple[list[str], str | None]:
    """Headless default policy — applies only when no clinician selection is supplied.

    Returns `(selected_codes, major_code)`:
      - rank-1 alone as Major when `prob_rank1 − prob_rank2 >= STAGE3_HEADLESS_GAP`
        (or only one candidate exists)
      - rank-1 Major + rank-2 Minor otherwise

    Returns `([], None)` for an empty DDx — caller treats this as out-of-scope
    rather than silently routing nothing.
    """
    if not ddx:
        return [], None

    rank1 = ddx[0]
    if len(ddx) == 1:
        return [rank1.code], rank1.code

    rank2 = ddx[1]
    gap = float(rank1.similarity) - float(rank2.similarity)
    if gap >= STAGE3_HEADLESS_GAP:
        return [rank1.code], rank1.code
    return [rank1.code, rank2.code], rank1.code


async def stage_3_route(
    ddx: list[DDxResult],
    top_k_codes: int | None = None,         # legacy — kept for backward-compat callers
    top_k_cpgs: int | None = None,          # legacy — kept for backward-compat callers
    emit=None,                              # async callable | None
    clinical_context: str | None = None,    # free-text query for procedure-scope routing
    patient_sex: str | None = None,         # "M"/"F"/"other"/None — drops sex-incompatible CPGs
    selected_codes: list[str] | None = None,  # Major + Minor codes the clinician picked
    major_code: str | None = None,          # exactly one of selected_codes (the primary dx)
) -> list[CPGDocRef]:
    """Map DDx codes to CPG document sets using Major / Minor allocation.

    Selection resolution order:
      1. `selected_codes` + `major_code` from the clinician (or upstream wrapper)
      2. legacy `top_k_codes` — first N codes of `ddx` with ddx[0] auto-marked Major
      3. headless default — `_auto_select_codes(ddx)` (top-2 if gap < 0.15 else top-1)

    Allocation table (`_allocate_major_minor(n_minor)`):
        n_minor=0 → Major 3                  total 3
        n_minor=1 → Major 3 + Minor 2        total 5
        n_minor=2 → Major 3 + Minor [1,1]    total 5
        n_minor=3 → Major 2 + Minor [1,1,1]  total 5
        n_minor=4 → Major 1 + Minor [1,1,1,1] total 5

    Quality floor (T2.3): each code's #1 CPG is always returned; its 2nd or 3rd
    CPG is admitted only if `ref.score >= SEMANTIC_SCOPE_THRESHOLD`. A code's #1
    CPG is *never* filtered — the clinician picked the code, so respect them.

    Cascade (T2.2): if a code under-fills its allotment (fewer matching CPGs than
    slots, or 2nd/3rd CPGs blocked by the floor), the unused slots cascade to the
    next under-filled code in selection order (Major first, then Minors), capped
    at 3 CPGs per code.

    T2.5: when the quality floor or under-availability drops a code below its
    expected allotment, emit a `stage3_quality_drop` event so the UI can flag
    "under-evidenced primary diagnosis" to the clinician.
    """
    procedure_tags = _extract_procedure_tags(clinical_context or "")
    excluded_names: set[str] = set()

    # --- Step 1: resolve which codes to route and which is Major ---
    if selected_codes is not None and major_code is not None:
        if major_code not in selected_codes:
            raise ValueError(
                f"major_code {major_code!r} must be one of selected_codes {selected_codes!r}"
            )
        chosen = list(selected_codes)
        chosen_major = major_code
        selection_source = "clinician"
    elif top_k_codes is not None:
        # Legacy path: treat ddx[0] as Major and ddx[1..top_k_codes-1] as Minors
        sliced = ddx[: max(1, top_k_codes)]
        chosen = [r.code for r in sliced]
        chosen_major = chosen[0] if chosen else None
        selection_source = "legacy_top_k"
    else:
        chosen, chosen_major = _auto_select_codes(ddx)
        selection_source = "headless_auto"

    if not chosen or chosen_major is None:
        if emit:
            await emit("sub_step", {
                "stage": 3,
                "detail": "No DDx codes available to route",
                "badge": "out_of_scope",
                "status": "complete",
            })
        return []

    # Cap selection to 5 (the allocation table's domain). Drop overflow with a
    # warning rather than raising — the upstream UI is the authoritative gate.
    if len(chosen) > STAGE3_MAX_CPGS:
        logger.warning(
            "Stage 3 selection of %d codes exceeds STAGE3_MAX_CPGS=%d; dropping tail",
            len(chosen), STAGE3_MAX_CPGS,
        )
        chosen = chosen[:STAGE3_MAX_CPGS]
        if chosen_major not in chosen:
            # Pull Major back in if it landed in the dropped tail
            chosen = [chosen_major] + [c for c in chosen if c != chosen_major][: STAGE3_MAX_CPGS - 1]

    # Build the ordered list: Major first, then Minors in selection order.
    minor_codes = [c for c in chosen if c != chosen_major]
    ordered_codes = [chosen_major] + minor_codes
    n_minor = len(minor_codes)
    major_allot, minor_allots = _allocate_major_minor(n_minor)
    allotments = {chosen_major: major_allot}
    for code, allot in zip(minor_codes, minor_allots):
        allotments[code] = allot

    logger.info(
        "Stage 3 selection: source=%s major=%s minors=%s allotments=%s",
        selection_source, chosen_major, minor_codes,
        {c: allotments[c] for c in ordered_codes},
    )

    # --- Step 2: per-code routing + sex / pregnancy filter ---
    # ddx_index lets _case_cpg_priority keep its existing tie-break behaviour.
    ddx_index = {r.code: r for r in ddx}
    ranked_by_code: dict[str, list[CPGDocRef]] = {}
    route_fetch_k = max(STAGE3_MAX_CPGS, 10)

    for code in ordered_codes:
        refs = await route_icd_to_cpgs(code, top_k=route_fetch_k, procedure_tags=procedure_tags or None)

        compat_refs: list[CPGDocRef] = []
        for ref in refs:
            reason = sex_incompatible_reason(ref.cpg_name, patient_sex)
            if reason is None:
                reason = pregnancy_context_missing_reason(ref.cpg_name, clinical_context)
            if reason is not None:
                if ref.cpg_name not in excluded_names:
                    excluded_names.add(ref.cpg_name)
                    logger.info("Stage 3 sex-filter excluded %s: %s", ref.cpg_name, reason)
                    if emit:
                        await emit("sub_step", {
                            "stage": 3,
                            "detail": f"Excluded {ref.cpg_name} — {reason}",
                            "badge": "excluded",
                            "status": "complete",
                        })
                continue
            compat_refs.append(ref)

        # Rank within this code by the existing priority (semantic score + match-type tiebreak).
        compat_refs.sort(
            key=lambda ref: _case_cpg_priority(ref, ddx, clinical_context),
            reverse=True,
        )

        # Update the DDx result's score_breakdown / matched_cpg_title from its own #1 match.
        if compat_refs and code in ddx_index:
            result = ddx_index[code]
            primary_ref = compat_refs[0]
            result.score_breakdown = build_score_breakdown(
                result,
                route_method=primary_ref.match_type,
            )
            result.matched_cpg_title = primary_ref.title

        ranked_by_code[code] = compat_refs

    # --- Step 3: Major-first allotment fill with quality floor and cascade ---
    chosen_refs: list[CPGDocRef] = []
    chosen_names: set[str] = set()
    per_code_picked: dict[str, int] = {c: 0 for c in ordered_codes}
    drop_events: list[dict] = []

    def _pull_from_code(code: str, slots: int) -> int:
        """Take up to `slots` CPGs from `code`'s ranked list under the quality
        floor and per-code 3-cap. Returns slots actually filled."""
        if slots <= 0:
            return 0
        per_code_cap = 3  # T2.3 per-code cap
        remaining_cap = per_code_cap - per_code_picked[code]
        target = min(slots, remaining_cap)
        if target <= 0:
            return 0

        filled = 0
        for ref in ranked_by_code.get(code, []):
            if filled >= target:
                break
            if ref.cpg_name in chosen_names:
                continue
            per_code_rank = per_code_picked[code] + 1  # 1-based per-code rank
            # Quality floor: first CPG always admitted; 2nd/3rd need to clear threshold.
            if per_code_rank >= 2 and ref.score < SEMANTIC_SCOPE_THRESHOLD:
                logger.info(
                    "Stage 3 quality-floor blocked %s for code %s (rank %d, score %.3f < %.3f)",
                    ref.cpg_name, code, per_code_rank, ref.score, SEMANTIC_SCOPE_THRESHOLD,
                )
                continue
            chosen_refs.append(ref)
            chosen_names.add(ref.cpg_name)
            per_code_picked[code] += 1
            filled += 1
        return filled

    # Pass 1 — give each code its own allotment in selection order (Major first).
    for code in ordered_codes:
        _pull_from_code(code, allotments[code])

    # Pass 2 — cascade unfilled slots to under-filled codes (Major first, then Minors).
    while True:
        used = sum(per_code_picked.values())
        budget = STAGE3_MAX_CPGS if n_minor > 0 else 3
        leftover = budget - used
        if leftover <= 0:
            break
        progressed = False
        for code in ordered_codes:
            if per_code_picked[code] >= 3:
                continue
            taken = _pull_from_code(code, 1)
            if taken:
                progressed = True
                leftover -= 1
                if leftover <= 0:
                    break
        if not progressed:
            break  # nothing left to cascade

    # T2.5 — record under-fills so the UI can surface them.
    for code in ordered_codes:
        expected = allotments[code]
        actual = per_code_picked[code]
        if actual < expected:
            tier = "major" if code == chosen_major else "minor"
            drop_events.append({
                "tier": tier,
                "code": code,
                "expected_slots": expected,
                "actual_slots": actual,
            })

    # --- Step 4: out-of-scope, telemetry, and tail accounting ---
    if not chosen_refs:
        out_of_scope = build_out_of_scope_info([ddx_index[c] for c in ordered_codes if c in ddx_index])
        if out_of_scope:
            logger.info(
                "Stage 3 out_of_scope: max_inclusion_score=%.3f candidates=%s",
                out_of_scope.max_inclusion_score,
                [c["code"] for c in out_of_scope.icd_candidates_considered],
            )
            if emit:
                await emit("sub_step", {
                    "stage": 3,
                    "detail": out_of_scope.message,
                    "badge": "out_of_scope",
                    "status": "complete",
                    "data": out_of_scope.model_dump(),
                })

    if emit:
        for ref in chosen_refs:
            await emit("sub_step", {
                "stage": 3,
                "detail": f"{ref.cpg_name}",
                "badge": ref.match_type,
                "status": "complete",
            })
        if drop_events:
            await emit("stage3_quality_drop", {
                "stage": 3,
                "drops": drop_events,
                "major_code": chosen_major,
                "selection_source": selection_source,
            })
            for d in drop_events:
                tier_label = "Primary" if d["tier"] == "major" else "Co-consideration"
                if d["actual_slots"] == 0:
                    # No CPG matched this code at all. Differentiate from a
                    # partial under-fill so the clinician sees a clear scope
                    # signal in the trace, not just a small number.
                    detail = f"{tier_label} {d['code']}: no CPG found in scope"
                    badge = "no_cpg_found"
                else:
                    detail = (
                        f"{tier_label} {d['code']} backed by {d['actual_slots']} CPG"
                        f"{'s' if d['actual_slots'] != 1 else ''} (expected {d['expected_slots']})"
                    )
                    badge = "under_evidenced"
                await emit("sub_step", {
                    "stage": 3,
                    "detail": detail,
                    "badge": badge,
                    "status": "complete",
                })

    # After routing is resolved, any DDx candidate still without a route_method
    # (stage-2 numeric-only breakdown, never matched a CPG) is out_of_scope.
    for result in ddx:
        if result.score_breakdown is None or result.score_breakdown.route_method is None:
            result.score_breakdown = build_score_breakdown(
                result,
                route_method="out_of_scope",
            )

    # Honour the legacy `top_k_cpgs` cap when explicitly passed — keeps existing
    # tests (and any older callers that wanted a tight 3-CPG return) working.
    # New callers should leave top_k_cpgs=None and let the allocation table decide.
    if top_k_cpgs is not None and len(chosen_refs) > top_k_cpgs:
        chosen_refs = chosen_refs[:top_k_cpgs]

    return chosen_refs


# ---------------------------------------------------------------------------
# Stage 4 — Retrieve
# ---------------------------------------------------------------------------

async def _generate_retrieval_queries(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    n: int = 3,
) -> list[str]:
    """Use the LLM to produce n focused retrieval queries for vector search."""
    # STAGE4_LLM_* vars override main LLM config (e.g. when primary API is blocked)
    base_url = os.getenv("STAGE4_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("STAGE4_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("STAGE4_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")
    provider = os.getenv("STAGE4_LLM_PROVIDER", "")

    client = _make_openai_client(
        base_url=base_url, api_key=api_key, provider=provider,
    )

    icd_summary = ", ".join(f"{d.code} ({d.title})" for d in ddx[:2])
    cpg_names = ", ".join(c.cpg_name for c in cpgs)
    vitals_str = json.dumps(case.vitals) if case.vitals else "none"
    staging_dict = case.severity_staging if case.severity_staging else {}
    severity_str = ", ".join(f"{k} {v}" for k, v in staging_dict.items()) or "not specified"
    prior_block = _format_prior_visit(getattr(case, "prior_visit", None))

    system_prompt = _load_prompt("stage4_query_generation.txt")

    user_content = f"""patient_context:
- Chief complaint: {case.chief_complaint}
- Age/sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Current medications: {", ".join(case.current_medications) or "none"}
- Vitals: {vitals_str}
{prior_block}
icd_codes: {icd_summary}
cpg_names: {cpg_names}
severity_staging: {severity_str}

Generate exactly {n} queries (one per domain as instructed)."""

    messages = (
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
        if system_prompt
        else [{"role": "user", "content": user_content}]
    )

    try:
        resp = await _llm_call_with_retry(
            lambda: client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
            ),
            what="Stage 4 query generation",
        )
    except Exception as exc:  # noqa: BLE001
        # Exhausted retries (or a hard error). Do NOT kill Stage 4 over the
        # query-gen LLM: stage_4_retrieve always prepends deterministic anchor
        # queries (investigations / lifestyle / referrals / condition pillars)
        # that drive real vector retrieval on their own. Returning [] degrades
        # to anchor-only retrieval — strictly better than a no-evidence plan.
        logger.error("stage_4: query generation failed after retries — falling back to anchors only: %s", exc)
        return []
    raw = resp.choices[0].message.content.strip()
    raw = raw.strip("` \n")
    if raw.startswith("json"):
        raw = raw[4:]
    # Gemini 2.5 Flash sometimes returns JSONL (one object per line) instead of
    # a single array — extract just the first valid JSON array if present.
    bracket_idx = raw.find("[")
    if bracket_idx != -1:
        end_idx = raw.find("]", bracket_idx)
        if end_idx != -1:
            raw = raw[bracket_idx:end_idx + 1]
    try:
        queries = json.loads(raw)
    except json.JSONDecodeError:
        # JSONL fallback: model returned one JSON value per line (no array wrapper)
        queries = []
        for line in raw.splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            try:
                val = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(val, str):
                queries.append(val)
            elif isinstance(val, list):
                queries.extend(v for v in val if isinstance(v, str))
        if not queries:
            logger.warning("stage_4: query JSON parse failed; raw head=%r", raw[:200])
    return [q for q in queries if isinstance(q, str)][:n]


# Category-boost weights for the Stage-4 re-rank (Layer C). Section categories
# carrying actionable guidance (Treatment/Assessment/Diagnosis) are promoted;
# background sections (Pathophysiology/Epidemiology/Methodology) are demoted.
# Module-level so the Layer C re-rank ablation can score the boosted vs raw order
# on the same pool without re-declaring the weights (single source of truth).
_CATEGORY_BOOST: dict[str, float] = {
    "Treatment": 1.4,
    "Supportive Treatment": 1.3,
    "Assessment": 1.2,
    "Diagnosis": 1.2,
    "Prevention": 1.2,
    "Special Populations": 1.1,
    "Reference": 1.0,
    "Introduction": 0.5,
    "Pathophysiology": 0.4,
    "Epidemiology": 0.4,
    "Methodology": 0.3,
}


def stage4_boosted_score(chunk: ChunkResult) -> float:
    """Category-boosted score for a chunk: raw vector score × max category weight,
    clamped to 1.0. Chunks with no category fall back to the raw score."""
    cats = chunk.metadata.get("category", [])
    if not cats:
        return chunk.score
    boost = max(_CATEGORY_BOOST.get(cat, 1.0) for cat in cats)
    return min(chunk.score * boost, 1.0)


def _meaningful_snippet(text: str, max_len: int = 240) -> str:
    """Trim a passage to a readable preview that ends on a sentence (or at worst
    a whole word) boundary — never mid-word — so the trace shows a complete
    thought rather than a hard character cut."""
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    window = text[:max_len]
    for end in (". ", "! ", "? "):
        idx = window.rfind(end)
        if idx >= 100:
            return window[: idx + 1].strip()
    sp = window.rfind(" ")
    return (window[:sp] if sp >= 100 else window).rstrip() + "…"


def _chunk_brief(c: ChunkResult) -> dict:
    """Compact, clinician-readable view of a retrieved chunk for the reasoning
    trace UI: which guideline it came from, the section heading if known, and a
    short plain-text preview of the passage."""
    section = None
    if isinstance(c.metadata, dict):
        section = (
            c.metadata.get("section_title")
            or c.metadata.get("title")
            or c.metadata.get("section")
        )
        sh = c.metadata.get("section_hierarchy")
        if not section and isinstance(sh, (list, tuple)) and sh:
            section = str(sh[-1])
        elif not section and isinstance(sh, str):
            section = sh
    snippet = _meaningful_snippet(c.content or "")
    return {
        "cpg": c.document_title,
        "section": section,
        "snippet": snippet,
        "score": round(float(c.score), 3),
    }


async def stage_4_retrieve(
    case: PatientCase,
    ddx: list[DDxResult],
    cpgs: list[CPGDocRef],
    queries_per_code: int = 7,
    chunks_per_query: int = 5,
    emit=None,                      # async callable | None
    return_pool: bool = False,      # eval hook: also return the pre-truncation candidate pool
) -> list[ChunkResult] | tuple[list[ChunkResult], list[ChunkResult]]:
    """Generate targeted queries and retrieve scoped evidence chunks.

    When ``return_pool`` is True returns ``(final_top20, all_candidates)`` where
    all_candidates is the deduped pool *before* the boost-sort + top-20 cut. Used
    by the Layer C re-rank ablation (eval/run_stage4_rerank_ablation.py) to compare
    raw-score vs category-boosted ordering on the identical candidate set. Default
    False preserves the plain list return for every production caller.
    """
    if not cpgs:
        logger.warning("stage_4_retrieve: no CPGs to scope search — returning empty")
        return []

    all_doc_ids = [doc_id for cpg in cpgs for doc_id in cpg.document_ids]

    if emit:
        await emit("sub_step", {
            "stage": 4,
            "detail": "Searching the matched guidelines with targeted questions…",
            "status": "running",
        })

    queries = await _generate_retrieval_queries(case, ddx, cpgs, n=queries_per_code)

    # Condition-anchor queries (#1A): prepend mandatory queries derived from
    # the primary DDx ICD so high-leverage drug classes (e.g. HFrEF MRA pillar)
    # are not silently omitted when the LLM doesn't seed a query for them.
    # Anchors are deduplicated against existing queries by exact substring match.
    primary_code = ddx[0].code if ddx else ""
    anchor_queries = [p["query"] for p in _expected_pillars_for(primary_code)]
    # Universal section anchors — fire on every case regardless of condition.
    # Generic phrasing intentional: vector search matches the patient context +
    # whichever CPGs were routed, so the same query pulls stroke lifestyle from
    # a stroke CPG and HFrEF lifestyle from an HF CPG. Closes the systematic
    # under-retrieval of investigation / lifestyle / referral sections.
    anchor_queries.extend([
        "Baseline investigations, tests, and imaging indicated for this patient's diagnosis",
        "Lifestyle modifications, diet, exercise, weight, smoking, alcohol recommendations for this patient",
        "Specialist referrals indicated and their urgency for this patient",
    ])
    if anchor_queries:
        existing_lower = [q.lower() for q in queries]
        for aq in anchor_queries:
            if not any(aq.lower()[:30] in eq for eq in existing_lower):
                queries.insert(0, aq)
        logger.info("Stage 4: injected %d anchor queries (condition + universal) for %s",
                    len(anchor_queries), primary_code)

    # Authoritative set of fixed-anchor query strings, so the trace can label
    # each emitted question as an always-asked anchor vs an AI-generated one
    # without the UI having to pattern-match text.
    anchor_set = set(anchor_queries)

    seen_chunk_ids: set[str] = set()
    all_chunks: list[ChunkResult] = []

    search_tasks = [
        vector_search_tool(VectorSearchInput(
            query=q,
            limit=chunks_per_query,
            document_id_filter=all_doc_ids,
        ))
        for q in queries
    ]
    results_per_query = await asyncio.gather(*search_tasks, return_exceptions=True)

    thin_queries: list[tuple[str, int, int]] = []
    for q, result in zip(queries, results_per_query):
        if isinstance(result, Exception):
            logger.warning("Query %r failed: %s", q, result)
            continue
        new_chunk_objs: list[ChunkResult] = []
        for chunk in result:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)
                new_chunk_objs.append(chunk)
        new_chunks = len(new_chunk_objs)
        # Instrumentation (5a deferral): flag a domain that came back thin so we
        # can later measure whether auto-re-query would have helped. <2 new
        # chunks per 5-chunk query means most hits were already-seen duplicates.
        if new_chunks < 2:
            thin_queries.append((q, new_chunks, len(result)))
        if emit:
            total = len(result)
            await emit("sub_step", {
                "stage": 4,
                "kind": "evidence_query",
                # Full question text (no truncation) so a clinician can read what
                # was actually asked of the guidelines.
                "detail": q,
                # True for the always-asked fixed anchors, False for the AI's
                # case-specific questions — drives the trace grouping.
                "anchor": q in anchor_set,
                "badge": f"+{new_chunks} new",
                "status": "complete",
                "data": {
                    "new": new_chunks,
                    "total": total,
                    "chunks": [_chunk_brief(c) for c in new_chunk_objs],
                },
            })

    all_chunks.sort(key=stage4_boosted_score, reverse=True)
    final = all_chunks[:20]

    if thin_queries:
        logger.info(
            "stage_4_thin_retrieval: %d/%d queries returned <2 new chunks: %s",
            len(thin_queries), len(queries),
            [{"q": q[:80], "new": n, "total": t} for q, n, t in thin_queries],
        )

    if emit:
        await emit("sub_step", {
            "stage": 4,
            "kind": "evidence_summary",
            # Plain count line only — the per-question rows above already let the
            # clinician drill into the passages each question pulled, so listing
            # all 20 again here is redundant noise.
            "detail": f"Selected {len(final)} guideline passages (duplicates removed)",
            "status": "complete",
        })

    if return_pool:
        return final, all_chunks
    return final


# ---------------------------------------------------------------------------
# Stage 5 — Synthesize
# ---------------------------------------------------------------------------

def _load_prompt(filename: str) -> str:
    """Load a prompt from agent/prompts/<filename>. Falls back to empty string on error."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    try:
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("Prompt file not found: %s", prompt_path)
        return ""


SYNTHESIS_SYSTEM = _load_prompt("stage5_synthesis.txt")
SYNTHESIS_SCHEMA = TreatmentPlan.model_json_schema()


# ---------------------------------------------------------------------------
# Prior-visit summariser — called once at consultation save-time.
# Output is stored as JSONB in Supabase consultations.prior_visit_summary and
# read back on the next visit as PatientCase.prior_visit.
# Uses PRIOR_VISIT_SUMMARISER_MODEL (env) — default mimo for cheap reasoning.
# ---------------------------------------------------------------------------

PRIOR_VISIT_SUMMARISER_PROMPT = _load_prompt("prior_visit_summariser.txt")
PREP_BRIEF_PROMPT = _load_prompt("prep_brief.txt")
REFERRAL_TRIGGER_GATE_PROMPT = _load_prompt("referral_trigger_gate.txt")
CONSULTATION_SUMMARISER_PROMPT = _load_prompt("consultation_summariser.txt")


async def gate_referral_triggers(
    case: PatientCase,
    candidates: list[dict],
) -> dict[int, tuple[str, str]]:
    """LLM evaluation of whether per-patient referral triggers are met.

    Args:
        case: the PatientCase (vitals, labs, severity_staging, comorbidities, history).
        candidates: list of {"index": int, "specialty": str, "condition": str, "trigger": str}.

    Returns:
        dict mapping candidate index -> (status, reason). status in {"met", "not_met", "unknown"}.
        Fail-open: returns {} on any error so caller falls back to conservative gating.
    """
    if not candidates or not REFERRAL_TRIGGER_GATE_PROMPT:
        return {}

    base_url = os.getenv("REFERRAL_GATE_BASE_URL") or os.getenv("PRIOR_VISIT_SUMMARISER_BASE_URL") or os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("REFERRAL_GATE_API_KEY") or os.getenv("PRIOR_VISIT_SUMMARISER_API_KEY") or os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    # Default must track the base_url chain above — the configured STAGE5/LLM
    # endpoint serves mimo-v2.5-pro, not the bare "xiaomimimo/MiMo-7B-RL" id
    # (which that endpoint rejects with 400 "Not supported model", failing the
    # gate and dumping every triggered referral into unresolved_questions).
    model = (
        os.getenv("REFERRAL_GATE_MODEL")
        or os.getenv("STAGE5_LLM_CHOICE")
        or os.getenv("LLM_CHOICE", "mimo-v2.5-pro")
    )

    patient_ctx = {
        "age": getattr(case, "age", None),
        "sex": getattr(case, "sex", None),
        "vitals": getattr(case, "vitals", {}) or {},
        "severity_staging": getattr(case, "severity_staging", {}) or {},
        "comorbidities": getattr(case, "comorbidities", []) or [],
        "current_medications": getattr(case, "current_medications", []) or [],
        "history": (getattr(case, "history", "") or "")[:1500],
        "chief_complaint": (getattr(case, "chief_complaint", "") or "")[:600],
    }
    user_payload = json.dumps(
        {"patient": patient_ctx, "candidates": candidates},
        ensure_ascii=False,
    )
    extra_body = (
        {"chat_template_kwargs": {"enable_thinking": False}} if "mimo" in model.lower() else None
    )

    try:
        client = _make_openai_client(base_url=base_url, api_key=api_key, max_retries=0)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": REFERRAL_TRIGGER_GATE_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.0,
            max_tokens=900,
            extra_body=extra_body,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        out: dict[int, tuple[str, str]] = {}
        for d in data.get("decisions", []) or []:
            try:
                idx = int(d.get("index"))
            except (TypeError, ValueError):
                continue
            status = (d.get("status") or "unknown").lower()
            if status not in ("met", "not_met", "unknown"):
                status = "unknown"
            reason = (d.get("reason") or "")[:200]
            out[idx] = (status, reason)
        met_count = sum(1 for s, _ in out.values() if s == "met")
        not_met_count = sum(1 for s, _ in out.values() if s == "not_met")
        unknown_count = sum(1 for s, _ in out.values() if s == "unknown")
        logger.info(
            "referral_trigger_gate: evaluated %d candidate(s); %d met, %d not_met, %d unknown (coverage: %.0f%%)",
            len(candidates),
            met_count,
            not_met_count,
            unknown_count,
            100.0 * met_count / len(candidates) if candidates else 0,
        )
        return out
    except json.JSONDecodeError as exc:
        logger.error(
            "referral_trigger_gate failed: JSON parsing error (%s); gate response malformed; falling back to conservative gating",
            exc,
        )
        return {}
    except (TimeoutError, asyncio.TimeoutError) as exc:
        logger.error(
            "referral_trigger_gate failed: TIMEOUT (%s); LLM response exceeded deadline; falling back to conservative gating",
            exc,
        )
        return {}
    except KeyError as exc:
        logger.error(
            "referral_trigger_gate failed: MISSING_FIELD (%s); response structure invalid; falling back to conservative gating",
            exc,
        )
        return {}
    except Exception as exc:
        logger.error(
            "referral_trigger_gate failed: %s (%s); falling back to conservative gating (all triggered referrals → unresolved_questions)",
            type(exc).__name__,
            exc,
        )
        return {}


async def summarise_prior_visit(
    consultation_date: str,
    clinical_notes: str,
    care_plan_summary: str | None = None,
    prior_icd_primary: str | None = None,
    medication_recommendations: dict | list | None = None,
) -> PriorVisitSummary:
    """Compress a saved consultation into a lean PriorVisitSummary.

    Idempotent and side-effect free — caller is responsible for persisting the
    result to Supabase. Falls back to a minimal summary on LLM failure rather
    than raising, so consultation save never blocks on the summariser.
    """
    base_url = os.getenv("PRIOR_VISIT_SUMMARISER_BASE_URL") or os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("PRIOR_VISIT_SUMMARISER_API_KEY") or os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    # Same rationale as referral_trigger_gate: align the default with the
    # endpoint the base_url chain resolves to (mimo-v2.5-pro), not an id the
    # configured server does not serve.
    model = (
        os.getenv("PRIOR_VISIT_SUMMARISER_MODEL")
        or os.getenv("STAGE5_LLM_CHOICE")
        or os.getenv("LLM_CHOICE", "mimo-v2.5-pro")
    )

    fallback = PriorVisitSummary(
        visit_date=consultation_date,
        prior_icd_primary=prior_icd_primary or None,
        prior_plan_summary=(care_plan_summary or "").strip()[:200] or None,
        key_labs_delta=None,
        what_changed=None,
    )

    if not PRIOR_VISIT_SUMMARISER_PROMPT:
        logger.warning("prior_visit_summariser: prompt file missing; returning fallback")
        return fallback

    client = _make_openai_client(base_url=base_url, api_key=api_key, max_retries=0)
    user_payload = json.dumps(
        {
            "consultation_date": consultation_date,
            "clinical_notes": clinical_notes or "",
            "care_plan_summary": care_plan_summary or "",
            "prior_icd_primary": prior_icd_primary or "",
            "medication_recommendations": medication_recommendations or {},
        },
        ensure_ascii=False,
    )

    extra_body = (
        {"chat_template_kwargs": {"enable_thinking": False}} if "mimo" in model.lower() else None
    )

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PRIOR_VISIT_SUMMARISER_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.1,
            max_tokens=400,
            extra_body=extra_body,
        )
        raw = (resp.choices[0].message.content or "").strip()
        # Strip markdown fence if any
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        # Enforce hard caps server-side as a belt-and-braces guard.
        for k, cap in (("prior_plan_summary", 200), ("key_labs_delta", 120), ("what_changed", 120)):
            v = data.get(k)
            if isinstance(v, str) and len(v) > cap:
                data[k] = v[:cap].rstrip()
        return PriorVisitSummary(
            visit_date=data.get("visit_date") or consultation_date,
            prior_icd_primary=data.get("prior_icd_primary") or (prior_icd_primary or None),
            prior_plan_summary=data.get("prior_plan_summary") or None,
            key_labs_delta=data.get("key_labs_delta") or None,
            what_changed=data.get("what_changed") or None,
        )
    except Exception as e:
        logger.warning("prior_visit_summariser failed (%s); using fallback", e)
        return fallback


async def summarise_consultation(labeled_transcript: str) -> str:
    """Summarise a diarized Doctor/Patient transcript into SOAP-style clinical notes.

    Uses CONSULTATION_SUMMARY_MODEL env var (default gemini-2.0-flash) via
    the Gemini AI Studio OpenAI-compatible endpoint.
    Falls back to an empty string on LLM failure so the caller can still
    return the raw transcript without losing the diarization work.
    """
    if not CONSULTATION_SUMMARISER_PROMPT:
        logger.warning("summarise_consultation: prompt file missing; returning empty summary")
        return ""

    base_url = os.getenv("GEMINI_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("CONSULTATION_SUMMARY_MODEL", "gemini-2.0-flash")

    client = _make_openai_client(base_url=base_url, api_key=api_key, max_retries=0)

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CONSULTATION_SUMMARISER_PROMPT},
                {"role": "user", "content": labeled_transcript},
            ],
            temperature=0.1,
            max_tokens=1200,
        )
        summary = (resp.choices[0].message.content or "").strip()
        return summary
    except Exception as e:
        logger.warning("summarise_consultation failed (%s); returning empty summary", e)
        return ""


_CURRENT_YEAR = 2026
_CPG_STALE_THRESHOLD_YEARS = 5


# Tiered evidence budgets for Stage 5 synthesis.
# Step 1 still receives whole markdown-header chunks. Keep each retrieved chunk
# intact whenever possible so late-section criteria, tables, and qualifiers remain
# visible to the synthesis LLM.
_CHILD_CHAR_LIMIT = 20_000
_PARENT_CHAR_LIMIT = 60_000
# Raised 60k → 90k: multi-CPG cases (e.g. Case 11: 5 target CPGs) were exhausting
# the evidence budget and dropping even small (~500-token) lower-ranked chunks that
# can carry safety-critical detail. 90k still leaves comfortable headroom under the
# 180k prompt ceiling (system prompt + plan schema + case ≈ 10-20k).
_TOTAL_TOKEN_BUDGET = 90_000
_PROMPT_TOKEN_LIMIT = 180_000
_ENC = None


class PromptOversizeError(RuntimeError):
    """Raised before an oversized synthesis prompt is sent to the LLM."""


def _get_token_encoder():
    global _ENC
    if _ENC is False:
        return None
    if _ENC is None and tiktoken is not None:
        try:
            _ENC = tiktoken.encoding_for_model("gpt-4")
        except Exception as exc:
            logger.warning("tiktoken encoder unavailable; using char proxy: %s", exc)
            _ENC = False
    return None if _ENC is False else _ENC


def _count_tokens(s: str) -> int:
    """Count tokens with tiktoken; fall back to a conservative char proxy."""
    if not s:
        return 0
    encoder = _get_token_encoder()
    if encoder is None:
        return max(1, len(s) // 4)
    return len(encoder.encode(s))


async def _prefetch_parent_content(chunks: list[ChunkResult]) -> None:
    """
    Populate parent_content (and section_content for h3 hits) for every chunk
    that has a parent_chunk_id. Walks the chain up to H1 in at most two hops.

    H2 / h1_leaf hit — one hop:
        chunk.parent_content = H1 text (windowed if > _PARENT_CHAR_LIMIT)

    H3 hit — two hops:
        chunk.section_content = cap-split H2 text (passed whole)
        chunk.parent_content  = H1 text with the H2 span replaced by a gap marker
                                (windowed if still > _PARENT_CHAR_LIMIT after slicing)
    """
    # Collect all direct parent IDs needed for the first hop
    first_hop_ids = {
        c.metadata["parent_chunk_id"]
        for c in chunks
        if c.metadata.get("parent_chunk_id")
    }
    if not first_hop_ids:
        return

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, content, chunk_level, start_char, end_char,
                   parent_chunk_id::text AS grandparent_id, metadata
            FROM chunks
            WHERE id = ANY($1::uuid[])
            """,
            list(first_hop_ids),
        )

    # Build lookup: id → full row dict
    parent_row_by_id: dict[str, dict] = {}
    for r in rows:
        parent_row_by_id[r["id"]] = {
            "content":       r["content"],
            "chunk_level":   r["chunk_level"],
            "start_char":    r["start_char"],
            "end_char":      r["end_char"],
            "grandparent_id": r["grandparent_id"],
            "metadata":      json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r["metadata"] or {}),
        }

    # Collect any grandparent IDs needed for H3 two-hop walk
    grandparent_ids = {
        parent_row_by_id[pid]["grandparent_id"]
        for pid in first_hop_ids
        if pid in parent_row_by_id and parent_row_by_id[pid].get("grandparent_id")
    }

    grandparent_row_by_id: dict[str, dict] = {}
    if grandparent_ids:
        async with db_pool.acquire() as conn:
            gp_rows = await conn.fetch(
                "SELECT id::text, content, chunk_level, start_char, end_char FROM chunks WHERE id = ANY($1::uuid[])",
                list(grandparent_ids),
            )
        for r in gp_rows:
            grandparent_row_by_id[r["id"]] = {
                "content":     r["content"],
                "chunk_level": r["chunk_level"],
                "start_char":  r["start_char"],
                "end_char":    r["end_char"],
            }

    for chunk in chunks:
        pid = chunk.metadata.get("parent_chunk_id")
        if not pid or pid not in parent_row_by_id:
            continue

        p = parent_row_by_id[pid]

        if p["chunk_level"] == "h2" and p.get("grandparent_id"):
            # H3 hit — p is the cap-split H2 intermediate; grandparent is H1
            gp_id = p["grandparent_id"]
            gp = grandparent_row_by_id.get(gp_id)

            # [SECTION] — cap-split H2 passed whole
            chunk.section_content = p["content"]

            if gp:
                h1_text  = gp["content"]
                h2_start = p["start_char"] or 0
                h2_end   = p["end_char"] or h2_start
                h2_title = p["metadata"].get("h2_title", "this section")
                gap      = f"\n\n[… {h2_title} shown above …]\n\n"
                h1_ctx   = h1_text[:h2_start] + gap + h1_text[h2_end:]

                if len(h1_ctx) > _PARENT_CHAR_LIMIT:
                    half         = _PARENT_CHAR_LIMIT // 2
                    window_start = max(0, h2_start - half)
                    window_end   = min(len(h1_ctx), h2_end + half)
                    h1_ctx       = h1_ctx[window_start:window_end]
                    logger.info(
                        "H1 window sliced for h3 chunk %s: [%d:%d] of %d-char H1",
                        chunk.chunk_id, window_start, window_end, len(h1_text),
                    )
                chunk.parent_content = h1_ctx
        else:
            # H2 / h1_leaf hit — p is the H1, one hop
            parent_text = p["content"]
            if len(parent_text) <= _PARENT_CHAR_LIMIT:
                chunk.parent_content = parent_text
            else:
                half         = _PARENT_CHAR_LIMIT // 2
                child_start  = chunk.start_char or 0
                child_end    = chunk.end_char or child_start
                window_start = max(0, child_start - half)
                window_end   = min(len(parent_text), child_end + half)
                chunk.parent_content = parent_text[window_start:window_end]
                logger.info(
                    "Parent window sliced for chunk %s: [%d:%d] of %d-char parent",
                    chunk.chunk_id, window_start, window_end, len(parent_text),
                )


async def _resolve_cross_refs(chunks: list[ChunkResult]) -> list[ChunkResult]:
    """
    Collect cross_refs from each chunk and its parent chain, fetch the best
    matching embedded child from each target file, and return them as extra
    ChunkResult objects to be appended to the evidence pack.

    Chain-aware: reads cross_refs from the hit child AND from its section/parent
    content metadata, so a marker placed on an unembedded cap-split H2 preamble
    still fires when one of its H3 children is the hit.

    Each resolved reference is capped at _CHILD_CHAR_LIMIT to avoid blowing
    the token budget. Duplicates (same chunk_id already in evidence) are skipped.
    """
    existing_ids = {c.chunk_id for c in chunks}
    refs_to_resolve: list[dict] = []

    for chunk in chunks:
        # Collect cross_refs from the hit chunk itself
        for ref in chunk.metadata.get("cross_refs", []):
            if ref.get("target_file"):
                refs_to_resolve.append(ref)
        # Also collect from parent chain metadata stored during prefetch
        # (covers markers that landed on an unembedded cap-split H2 preamble)
        for key in ("cap_split_h2_index",):
            pass  # chain metadata is in DB rows already fetched — read from parent_content metadata below

    if not refs_to_resolve:
        return []

    # Deduplicate by target_file + target_heading
    seen_refs: set[tuple] = set()
    unique_refs: list[dict] = []
    for ref in refs_to_resolve:
        key = (ref.get("target_file", ""), ref.get("target_heading", ""))
        if key not in seen_refs:
            seen_refs.add(key)
            unique_refs.append(ref)

    resolved: list[ChunkResult] = []

    async with db_pool.acquire() as conn:
        for ref in unique_refs:
            target_file    = ref.get("target_file", "")
            target_heading = ref.get("target_heading", "")
            target_kind    = ref.get("target_kind", "h1_section")

            if not target_file:
                continue

            # Find the document matching target_file (partial match on source path)
            doc_row = await conn.fetchrow(
                "SELECT id::text FROM documents WHERE source LIKE $1 LIMIT 1",
                f"%{target_file}%",
            )
            if not doc_row:
                logger.debug("cross_ref: no document found for target_file=%r", target_file)
                continue

            doc_id = doc_row["id"]

            # For h2_section / h3_section — find the specific embedded child by heading match
            if target_kind in ("h2_section", "h3_section") and target_heading:
                row = await conn.fetchrow(
                    """
                    SELECT c.id::text AS chunk_id, c.content, c.metadata,
                           d.title AS document_title, d.source AS document_source
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.document_id = $1::uuid
                      AND c.embedding IS NOT NULL
                      AND (
                          c.metadata->>'h2_title' ILIKE $2
                          OR c.metadata->>'h3_title' ILIKE $2
                          OR c.content ILIKE $3
                      )
                    LIMIT 1
                    """,
                    doc_id,
                    f"%{target_heading}%",
                    f"%{target_heading[:60]}%",
                )
            else:
                # h1_section / appendix / algorithm_flowchart — best embedded child
                # (prefer the first embedded child of the target document)
                row = await conn.fetchrow(
                    """
                    SELECT c.id::text AS chunk_id, c.content, c.metadata,
                           d.title AS document_title, d.source AS document_source
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.document_id = $1::uuid
                      AND c.embedding IS NOT NULL
                    ORDER BY c.chunk_index
                    LIMIT 1
                    """,
                    doc_id,
                )

            if not row:
                logger.debug(
                    "cross_ref: no embedded chunk found for target_file=%r heading=%r",
                    target_file, target_heading,
                )
                continue

            chunk_id = row["chunk_id"]
            if chunk_id in existing_ids:
                continue  # already in evidence pack

            existing_ids.add(chunk_id)
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
            content = row["content"][:_CHILD_CHAR_LIMIT]

            resolved.append(ChunkResult(
                chunk_id=chunk_id,
                document_id=doc_id,
                content=content,
                score=0.0,
                metadata={**meta, "_cross_ref_source": target_file},
                document_title=row["document_title"],
                document_source=row["document_source"],
            ))
            logger.info(
                "cross_ref resolved: %r → chunk %s (%d chars)",
                target_file, chunk_id, len(content),
            )

    return resolved


def build_parent_context(chunk: ChunkResult, include_parent: bool = True) -> str:
    """
    Return formatted evidence text for a chunk.

    H3 hit  → [CHILD] + [SECTION] + [PARENT]  (3 tiers, no duplicated text)
    H2 hit  → [CHILD] + [PARENT]               (2 tiers)
    No parent → child only (capped at _PARENT_CHAR_LIMIT)

    If include_parent is False (duplicate parent suppression), emit child only.
    """
    if not include_parent or chunk.parent_content is None:
        return chunk.content[:_PARENT_CHAR_LIMIT]

    child_block = f"[CHILD]\n{chunk.content}"

    if chunk.section_content is not None:
        # H3 hit — 3-tier, H1 already has the H2 span replaced by a gap marker
        section_block = f"[SECTION]\n{chunk.section_content}"
        parent_block  = f"[PARENT]\n{chunk.parent_content}"
        return f"{child_block}\n\n{section_block}\n\n{parent_block}"

    parent_block = f"[PARENT]\n{chunk.parent_content}"
    return f"{child_block}\n\n{parent_block}"


def _format_evidence(chunks: list[ChunkResult]) -> str:
    lines = []
    running_tokens = 0
    seen_documents: set[str] = set()
    for i, c in enumerate(chunks, 1):
        if running_tokens >= _TOTAL_TOKEN_BUDGET:
            break
        section = c.metadata.get("section_number", "")
        cpg = c.document_title or c.document_source
        # CPG currency warning — flag stale evidence so the synthesis LLM can
        # de-emphasise it or surface it in unresolved_questions.
        published_year = c.metadata.get("published_year")
        age_warning = ""
        if published_year:
            try:
                year_int = int(published_year)
                age = _CURRENT_YEAR - year_int
                if age > _CPG_STALE_THRESHOLD_YEARS:
                    age_warning = f"  ⚠ Published {year_int} ({age}y old — verify against current guidelines)"
            except (TypeError, ValueError):
                pass
        document_key = c.metadata.get("parent_chunk_id") or c.document_id
        include_parent = document_key not in seen_documents
        if include_parent:
            seen_documents.add(document_key)
        else:
            logger.debug(
                "Skipping duplicate parent context for document %s via chunk %s",
                document_key,
                c.chunk_id,
            )

        content = build_parent_context(c, include_parent=include_parent)
        content_tokens = _count_tokens(content)
        if len(content) > _CHILD_CHAR_LIMIT and running_tokens + content_tokens > _TOTAL_TOKEN_BUDGET:
            logger.info(
                "Skipping oversized child %s (%d chars, budget exhausted)",
                c.chunk_id,
                len(content),
            )
            continue
        if running_tokens + content_tokens > _TOTAL_TOKEN_BUDGET:
            logger.info(
                "Skipping chunk %s (%d tokens would exceed synthesis evidence budget)",
                c.chunk_id,
                content_tokens,
            )
            continue
        entry = f"[{i}] {cpg} §{section}{age_warning}\n{content}"
        lines.append(entry)
        running_tokens += content_tokens
    return "\n\n".join(lines)


def _guard_prompt_size(system_prompt: str, user_prompt: str) -> None:
    prompt_tokens = _count_tokens(system_prompt) + _count_tokens(user_prompt)
    if prompt_tokens > _PROMPT_TOKEN_LIMIT:
        logger.error(
            "Stage 5 prompt assembled to %d tokens; refusing send",
            prompt_tokens,
        )
        raise PromptOversizeError(
            f"Stage 5 prompt assembled to {prompt_tokens} tokens; "
            f"limit is {_PROMPT_TOKEN_LIMIT}"
        )


def _build_out_of_scope_plan(
    case: PatientCase,
    ddx: list[DDxResult],
    info: OutOfScopeInfo,
) -> TreatmentPlan:
    icd_primary = ddx[0].code if ddx else "Unknown"
    icd_alternates = [d.code for d in ddx[1:3]]
    top_titles = ", ".join(f"{d.code} {d.title}" for d in ddx[:3]) or "none"

    return TreatmentPlan(
        icd_primary=icd_primary,
        icd_alternates=icd_alternates,
        summary=(
            "No loaded Clinical Practice Guideline matched this presentation. "
            f"Top ICD-11 candidates considered: {top_titles}."
        ),
        recommendations=[
            Recommendation(
                intervention="Refer for clinician review using local non-CPG pathways",
                type="referral",
                evidence_grade=None,
                cpg_source="No loaded CPG match",
                rationale=(
                    "The routing layer found no exact, hierarchy, or sibling CPG "
                    f"match, and the maximum ICD inclusion score was {info.max_inclusion_score:.2f}."
                ),
                contraindications_checked=[],
            )
        ],
        monitoring=[],
        red_flags=[
            "Escalate urgently if the patient is clinically unstable or has red-flag symptoms.",
        ],
        follow_up=[
            "Reassess after specialist/local pathway review or after relevant CPG coverage is added.",
        ],
        confidence=0.2,
        unresolved_questions=[
            info.message,
            "No treatment recommendation should be inferred from unrelated loaded CPGs.",
        ],
    )


def _build_synthesis_failed_plan(
    ddx: list[DDxResult],
    evidence: list[ChunkResult],
) -> TreatmentPlan:
    """Degraded plan when the synthesis LLM returns nothing usable.

    Stage 5 is unrecoverable, so rather than crash the consultation we return an
    honest, low-confidence plan that names the predicted diagnosis, surfaces the
    failure in unresolved_questions, and tells the clinician to proceed on their
    own judgement / retry. No fabricated guideline citations.
    """
    icd_primary = ddx[0].code if ddx else "Unknown"
    title = ddx[0].title if ddx else "Unknown"
    return TreatmentPlan(
        icd_primary=icd_primary,
        icd_alternates=[d.code for d in ddx[1:3]],
        summary=(
            f"Automated care-plan synthesis was unavailable for {icd_primary} ({title}). "
            f"{len(evidence)} guideline evidence chunk(s) were retrieved but the synthesis "
            "model returned no output."
        ),
        recommendations=[],
        monitoring=[],
        red_flags=[
            "Escalate urgently if the patient is clinically unstable or has red-flag symptoms.",
        ],
        follow_up=[],
        confidence=0.0,
        unresolved_questions=[
            "Care-plan synthesis failed (model returned empty output) — retry, or proceed "
            "on clinical judgement using the retrieved guideline evidence directly.",
        ],
    )


async def stage_5_synthesize(
    case: PatientCase,
    ddx: list[DDxResult],
    _cpgs: list[CPGDocRef],
    evidence: list[ChunkResult],
    flags: list[ClinicalFlag] | None = None,
) -> TreatmentPlan:
    """Synthesise a structured TreatmentPlan from patient context and CPG evidence."""
    if not _cpgs and not evidence:
        out_of_scope = build_out_of_scope_info(ddx)
        if out_of_scope:
            logger.info(
                "stage_5_synthesize: returning deterministic out_of_scope plan "
                "without LLM synthesis"
            )
            return _build_out_of_scope_plan(case, ddx, out_of_scope)

    # STAGE5_LLM_* vars override main LLM config (e.g. when primary API is blocked)
    base_url = os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")

    client = openai.AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    await _prefetch_parent_content(evidence)
    cross_ref_chunks = await _resolve_cross_refs(evidence)
    if cross_ref_chunks:
        logger.info("cross_ref: appending %d referenced evidence chunks", len(cross_ref_chunks))
        evidence = evidence + cross_ref_chunks
    evidence_text = _format_evidence(evidence)

    flags_block = format_flags_for_prompt(flags or [])
    if flags:
        logger.info("stage_5_synthesize: injecting %d KG flags into prompt", len(flags))

    icd_primary = ddx[0].code if ddx else "Unknown"
    icd_alternates = [d.code for d in ddx[1:3]]

    user_prompt = f"""Patient Case:
- Chief complaint: {case.chief_complaint}
- Age/sex: {case.age or "unknown"} / {case.sex or "unknown"}
- History: {case.history or "none"}
- Comorbidities: {", ".join(case.comorbidities) or "none"}
- Medications: {", ".join(case.current_medications) or "none"}
- Allergies: {", ".join(case.allergies) or "none"}
- Vitals: {json.dumps(case.vitals) if case.vitals else "none"}
{_format_prior_visit(getattr(case, "prior_visit", None))}
Predicted ICD-11: {icd_primary} ({ddx[0].title if ddx else ""})
Alternate codes: {", ".join(icd_alternates) or "none"}

{flags_block}
Retrieved Evidence ({len(evidence)} chunks):
{evidence_text}

Produce a TreatmentPlan JSON object matching this schema:
{json.dumps(SYNTHESIS_SCHEMA, indent=2)}"""

    _guard_prompt_size(SYNTHESIS_SYSTEM, user_prompt)

    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYNTHESIS_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw_json = (resp.choices[0].message.content or "").strip()
    if not raw_json:
        # Reasoning models (e.g. mimo) can return empty content. Stage 5 is the
        # unrecoverable stage, so degrade gracefully to an honest "synthesis
        # unavailable" plan instead of crashing the whole consultation.
        logger.error("stage_5_synthesize: LLM returned empty content — degrading to safe plan")
        return _build_synthesis_failed_plan(ddx, evidence)

    data = json.loads(raw_json)

    # Ensure required fields are populated when LLM omits them
    data.setdefault("icd_primary", icd_primary)
    data.setdefault("icd_alternates", icd_alternates)
    data.setdefault("summary", f"ICD-11 {icd_primary}: {ddx[0].title if ddx else 'Unknown'}")
    data.setdefault("follow_up", [])

    try:
        plan = TreatmentPlan.model_validate(data)
    except ValidationError as exc:
        logger.error("TreatmentPlan validation failed. Raw JSON: %s", raw_json)
        raise RuntimeError(f"TreatmentPlan validation failed: {exc}") from exc

    # Deduplicate pharmacological recommendations from LLM synthesis
    initial_med_count = sum(1 for r in plan.recommendations if r.type == "pharmacological")
    plan.recommendations = _dedup_pharmacological_recs(plan.recommendations)
    final_med_count = sum(1 for r in plan.recommendations if r.type == "pharmacological")
    if initial_med_count != final_med_count:
        logger.info(
            "stage_5: medication dedup: %d initial → %d final pharmacological recs",
            initial_med_count, final_med_count,
        )

    # Instrumentation (5b deferral): log when Stage 5 emits empty mandatory
    # sections so we can measure whether auto-re-draft would have helped.
    empty_sections = [
        name for name, val in (
            ("monitoring", plan.monitoring),
            ("red_flags", plan.red_flags),
            ("follow_up", plan.follow_up),
        ) if not val
    ]
    if empty_sections:
        logger.info(
            "stage_5_empty_sections: %s (icd=%s, evidence_chunks=%d, flags=%d)",
            empty_sections, icd_primary, len(evidence), len(flags or []),
        )

    # Post-synthesis coverage validators (#1A + #2). Both are commandment-safe:
    # they surface gaps as unresolved_questions, never as fabricated recs.
    intervention_blob = " ".join(
        (r.intervention or "").lower() for r in plan.recommendations
    )
    # Coverage checks consider not just the primary DDx but the top-5 codes —
    # a patient with AF (BC81) + ACS (BA41) + CAD (BA52) may have CAD as primary
    # yet still require AF/ACS-driven referrals and pillar therapies.
    coverage_codes = [d.code for d in ddx[:5] if getattr(d, "code", None)]
    if icd_primary and icd_primary not in coverage_codes:
        coverage_codes.insert(0, icd_primary)

    missing_pillars: list[str] = []
    seen_pillar_labels: set[str] = set()
    for code in coverage_codes:
        for pillar in _expected_pillars_for(code):
            label = pillar["pillar"]
            if label in seen_pillar_labels:
                continue
            if not any(sub.lower() in intervention_blob for sub in pillar["substrings"]):
                missing_pillars.append(label)
                seen_pillar_labels.add(label)
    if missing_pillars:
        for label in missing_pillars:
            plan.unresolved_questions.append(
                f"Expected therapy not surfaced in plan: {label}. "
                "No supporting chunk retrieved — clinician should consider this "
                "explicitly before finalising the regimen."
            )
        logger.info(
            "stage_5 coverage: %d expected pillar(s) missing across %s — %s",
            len(missing_pillars), coverage_codes, missing_pillars,
        )

    if True:  # always run KG referrals; dedupe against LLM-produced ones below
        # KG-first: ask Neo4j what referrals exist for the patient's conditions.
        # Falls back to the static dict (_ALWAYS_REFER_CONDITIONS) for codes the
        # KG doesn't yet cover. Fail-open: KG errors degrade silently to dict.
        kg_specialty_messages: list[str] = []
        kg_recs = []
        try:
            from .graph_clinical import lookup_referrals as _lookup_referrals
            kg_inputs: list[str] = []
            for d in ddx[:5]:
                title = getattr(d, "title", None)
                if title:
                    kg_inputs.append(title)
            kg_inputs.extend(case.comorbidities or [])
            kg_recs = await _lookup_referrals(kg_inputs, cpgs=_cpgs) if kg_inputs else []

            # Demographic safety filters & CPG alignment filters for referrals
            filtered_recs = []
            is_male = str(getattr(case, "sex", "")).upper() in ("M", "MALE")
            is_adult = False
            age = getattr(case, "age", None)
            if age is not None:
                try:
                    is_adult = int(age) >= 18
                except (TypeError, ValueError):
                    pass

            # Compile routed CPG slugs to ensure referrals align with matched CPGs
            allowed_cpg_slugs = set()
            for c in (_cpgs or []):
                if getattr(c, "cpg_name", None):
                    allowed_cpg_slugs.add(c.cpg_name.lower().strip())
                if getattr(c, "title", None):
                    allowed_cpg_slugs.add(c.title.lower().strip())

            for rec in kg_recs:
                cond_lower = (rec.condition or "").lower()
                source_lower = (rec.source_document or "").lower().strip()
                spec_lower = (rec.specialty or "").lower()

                # CPG Routing check: Ensure referral originates from a CPG that was actually routed!
                if allowed_cpg_slugs:
                    is_routed = any(
                        slug in source_lower or source_lower in slug
                        for slug in allowed_cpg_slugs
                        if slug
                    )
                    if not is_routed:
                        logger.info("CPG Alignment Filter: Excluding referral from unrouted CPG '%s'", rec.source_document)
                        continue
                
                # Male check: exclude pregnancy/obstetric/maternal/foetal/gdm referrals
                if is_male:
                    pregnancy_keywords = ["pregnancy", "gestational", "maternal", "obstetrics", "foetal", "fetal", "obstetrician", "gdm", "antenatal"]
                    if any(kw in cond_lower or kw in source_lower or kw in spec_lower for kw in pregnancy_keywords):
                        logger.info("Demographic Filter: Excluding pregnancy referral '%s' for male patient", rec.specialty)
                        continue
                
                # Adult check: exclude paediatric/infant referrals
                if is_adult:
                    pediatric_keywords = ["paediatric", "pediatric", "child", "infant", "newborn", "paediatrician", "adolescent", "adolescents", "teenager"]
                    if any(kw in cond_lower or kw in source_lower or kw in spec_lower for kw in pediatric_keywords):
                        logger.info("Demographic Filter: Excluding paediatric referral '%s' for adult patient", rec.specialty)
                        continue

                filtered_recs.append(rec)
            kg_recs = filtered_recs

            logger.info("stage_5 KG lookup: %d input(s) -> %d referral(s) (after demographic filters)", len(kg_inputs), len(kg_recs))
            for rec in kg_recs:
                trig = f" (trigger: {rec.trigger})" if rec.trigger else ""
                msg = (
                    f"{rec.specialty} — {rec.condition}, urgency: {rec.urgency}{trig}. "
                    f"Evidence: {(rec.evidence or '')[:160]}"
                )
                kg_specialty_messages.append(msg)
        except Exception as exc:
            logger.warning("KG referral lookup failed in Stage 5 validator: %s", exc)

        if kg_recs:
            from .models import Recommendation as _Rec
            # Build a map of existing referrals by (specialty, condition) for urgency-aware dedup
            existing_referrals: dict[tuple[str, str], tuple] = {}  # (specialty, condition) -> (rec, urgency_priority)
            for existing in plan.recommendations:
                if existing.type == "referral":
                    spec = (getattr(existing, "specialty", None) or "").strip().lower()
                    cond = (getattr(existing, "condition", None) or "").strip().lower()
                    if spec or cond:
                        urgency = _referral_urgency_priority(getattr(existing, "urgency", None))
                        existing_referrals[(spec, cond)] = (existing, urgency)
            # Visit acuity flag — computed once; gates routine comorbidity referrals below.
            _acute_visit = _is_acute_presentation(case)
            # Tokens naming the acute PRIMARY diagnosis (ddx[0]) — used to spare the
            # acute problem's own routine referrals (post-STEMI cardiology follow-up,
            # cardiac rehab) from the visit-scope deferral, which targets STABLE
            # comorbidities only.
            _STOP_COND_TOKENS = {
                "acute", "chronic", "disease", "syndrome", "with", "and", "the",
                "unspecified", "other", "type", "due", "for", "not",
            }
            import re as _re_mod
            _re_cond = _re_mod.compile(r"[a-z0-9]+")
            def _cond_tokens(text: str | None) -> set[str]:
                return {
                    t for t in _re_cond.findall((text or "").lower())
                    if len(t) >= 4 and t not in _STOP_COND_TOKENS
                }
            _primary_cond_tokens = _cond_tokens(
                (getattr(ddx[0], "title", None) or getattr(ddx[0], "name", "")) if ddx else ""
            )
            if _acute_visit:
                logger.info(
                    "stage_5: acute presentation detected (primary=%s) — routine comorbidity KG referrals will be deferred",
                    sorted(_primary_cond_tokens),
                )

            # Triggers we treat as "universal" — patient is presumed to meet them by
            # virtue of having the condition (no per-patient gating needed).
            _UNIVERSAL_TRIGGERS = {
                "newly diagnosed", "new diagnosis", "at diagnosis", "on diagnosis",
                "at initial assessment", "initial assessment", "baseline",
            }
            def _is_universal(trig: str | None, trig_list: list[str] | None) -> bool:
                pool = []
                if trig:
                    pool.append(trig.strip().lower())
                for t in (trig_list or []):
                    if t:
                        pool.append(t.strip().lower())
                if not pool:
                    return True  # no trigger field = always-applicable referral
                return any(p in _UNIVERSAL_TRIGGERS for p in pool)

            # Age-mismatch pre-filter: triggers explicitly scoped to paediatric
            # populations are dropped without gating for adult patients (and vice
            # versa). Avoids "adolescents with severe obesity" surfacing for a 62yo.
            _PAEDIATRIC_MARKERS = (
                "child", "children", "paediatric", "pediatric", "adolescent",
                "infant", "neonat", "maturing child",
            )
            def _is_age_mismatched(trig: str | None, trig_list: list[str] | None) -> bool:
                age = getattr(case, "age", None)
                if age is None:
                    return False
                pool: list[str] = []
                if trig:
                    pool.append(trig.lower())
                for t in (trig_list or []):
                    if t:
                        pool.append(t.lower())
                text = " ".join(pool)
                if not text:
                    return False
                has_paed = any(m in text for m in _PAEDIATRIC_MARKERS)
                if has_paed and age >= 18:
                    return True
                return False

            # Qualifier negation pre-filter. Parses comorbidities for explicit
            # negation patterns ("non-<X>", "<X>-negative", "without <X>") and
            # drops triggers requiring the negated qualifier.
            # Example: comorbidity "Non-valvular Atrial Fibrillation" → negated={"valvular"};
            # any trigger mentioning "valvular" against an AF-related condition drops.
            # Generic — not case-specific. Covers HER2-negative, non-diabetic CKD,
            # non-pregnant, etc.
            import re as _re
            _NEG_PATTERNS = (
                _re.compile(r"\bnon[\s-]([a-z]+)", _re.IGNORECASE),
                _re.compile(r"\b([a-z]+)[\s-]negative\b", _re.IGNORECASE),
                _re.compile(r"\bwithout\s+([a-z]+)", _re.IGNORECASE),
            )
            _negated_qualifiers: set[str] = set()
            for _co in (getattr(case, "comorbidities", None) or []):
                _co_text = _co if isinstance(_co, str) else getattr(_co, "name", "") or ""
                for _pat in _NEG_PATTERNS:
                    for _m in _pat.finditer(_co_text):
                        _q = _m.group(1).lower().strip()
                        # Skip non-clinical stopwords that the patterns can accidentally
                        # capture (e.g. "non-smoker" → "smoker" is not a qualifier we want
                        # to use as a trigger blacklist).
                        if _q and len(_q) >= 4 and _q not in {"smoker", "drinker"}:
                            _negated_qualifiers.add(_q)
            if _negated_qualifiers:
                logger.info(
                    "stage_5: negated qualifiers from comorbidities: %s",
                    sorted(_negated_qualifiers),
                )

            def _is_qualifier_mismatched(trig: str | None, trig_list: list[str] | None) -> bool:
                if not _negated_qualifiers:
                    return False
                pool: list[str] = []
                if trig:
                    pool.append(trig.lower())
                for t in (trig_list or []):
                    if t:
                        pool.append(t.lower())
                text = " ".join(pool)
                if not text:
                    return False
                # Require the qualifier to appear as a whole word, not a substring,
                # to avoid e.g. "valvular" matching inside an unrelated drug name.
                for q in _negated_qualifiers:
                    if _re.search(rf"\b{_re.escape(q)}\b", text):
                        return True
                return False

            # First pass: classify each rec as universal vs triggered. Triggered ones
            # are dispatched to an LLM gate that evaluates each trigger against the
            # patient's vitals/labs/staging/history. The gate is fail-open: on any
            # error, all triggered recs fall back to unresolved_questions (Option-1
            # conservative behaviour).
            triggered_candidates: list[dict] = []
            triggered_meta: dict[int, tuple] = {}  # idx -> (rec, primary_trig, urgency_word)
            universal_recs: list[tuple] = []  # (rec, urgency_word)
            for rec in kg_recs:
                key = (rec.specialty.lower(), (rec.condition or "").lower())
                urgency_word = (rec.urgency or "routine").lower()
                urgency_priority = _referral_urgency_priority(rec.urgency)

                # Skip KG referral only if existing LLM referral has equal or higher urgency
                if key in existing_referrals:
                    existing_rec, existing_urgency = existing_referrals[key]
                    if existing_urgency >= urgency_priority:
                        # Existing referral has same/better urgency, skip KG version
                        logger.info(
                            "stage_5: KG referral skipped (LLM has %s, KG has %s): %s — %s",
                            existing_rec.urgency or "routine",
                            urgency_word,
                            rec.specialty, rec.condition,
                        )
                        continue
                    # Otherwise, KG has higher urgency — let it through for final dedup to handle upgrade
                    logger.info(
                        "stage_5: KG referral may upgrade urgency (%s → %s): %s — %s",
                        existing_rec.urgency or "routine",
                        urgency_word,
                        rec.specialty, rec.condition,
                    )
                trig_list = list(getattr(rec, "triggers", []) or [])
                if _is_age_mismatched(rec.trigger, trig_list):
                    logger.info(
                        "stage_5: KG referral dropped (paediatric trigger, adult patient): %s — %s (trigger=%r)",
                        rec.specialty, rec.condition, rec.trigger,
                    )
                    continue
                # Visit-scope discipline (Commandment-6 code-side): on an acute
                # presentation, defer ROUTINE chronic-comorbidity referrals (e.g.
                # newly-diagnosed-T2DM → ophthalmology/dental). Urgent/emergency KG
                # referrals (and the acute primary's own urgent referrals) survive;
                # the LLM still emits a "continue routine <comorbidity> care" line.
                # Defer ONLY routine referrals for a STABLE comorbidity — spare the
                # acute primary's own routine referrals (its condition shares tokens
                # with ddx[0], e.g. post-STEMI cardiology / cardiac rehab).
                if _acute_visit and urgency_word == "routine":
                    _is_primary = bool(_primary_cond_tokens & _cond_tokens(rec.condition))
                    if not _is_primary:
                        logger.info(
                            "stage_5: KG referral deferred (routine comorbidity referral on acute visit): %s — %s (trigger=%r)",
                            rec.specialty, rec.condition, rec.trigger,
                        )
                        continue
                if _is_qualifier_mismatched(rec.trigger, trig_list):
                    logger.info(
                        "stage_5: KG referral dropped (qualifier mismatch with comorbidity negation): %s — %s (trigger=%r)",
                        rec.specialty, rec.condition, rec.trigger,
                    )
                    continue
                if _is_universal(rec.trigger, trig_list):
                    universal_recs.append((rec, urgency_word))
                    continue
                primary_trig = (rec.trigger or (trig_list[0] if trig_list else "")).strip()
                idx = len(triggered_candidates)
                triggered_candidates.append({
                    "index": idx,
                    "specialty": rec.specialty,
                    "condition": rec.condition,
                    "trigger": primary_trig,
                })
                triggered_meta[idx] = (rec, primary_trig, urgency_word)

            gate_decisions = await gate_referral_triggers(case, triggered_candidates) if triggered_candidates else {}

            # If gate_decisions is empty but we had triggered candidates, the gate failed
            gate_failed = (len(triggered_candidates) > 0 and len(gate_decisions) == 0)
            if gate_failed:
                logger.warning(
                    "referral_trigger_gate returned empty result for %d triggered candidates; "
                    "gate failure likely due to LLM error, timeout, or malformed response; "
                    "conservatively routing all %d triggered referrals to unresolved_questions",
                    len(triggered_candidates),
                    len(triggered_meta),
                )

            injected_count = 0
            gated_count = 0
            dropped_count = 0
            gate_error_count = 0
            # Track unique unknown-gate referrals by (specialty, condition_norm) so
            # near-duplicate KG edges (e.g. 3 Ophthalmology edges for the same
            # patient) don't each spawn a "Consider X IF Y" entry in
            # unresolved_questions. First occurrence keeps the actionable IF line;
            # subsequent occurrences only append to gate_audit.
            unknown_seen_keys: set[tuple[str, str]] = set()
            # Same for not_met — KG can emit multiple edges that all resolve to the
            # same specialty+condition; one gate_audit line is enough.
            notmet_seen_keys: set[tuple[str, str]] = set()
            # Gap 8: per-source-CPG cap on audit lines. A single CPG covering a
            # broad comorbidity (e.g. T2DM) can fan out into 7+ different
            # (specialty, condition) gate failures; collectively they swamp the
            # audit panel with noise unrelated to the visit's chief complaint.
            # Cap at MAX_AUDIT_PER_CPG entries per source_document; once exceeded,
            # append a single summarising line instead of every individual edge.
            MAX_AUDIT_PER_CPG = 2
            audit_per_cpg: dict[str, int] = {}
            audit_overflow_logged: set[str] = set()

            def _audit_source(_rec) -> str:
                return (getattr(_rec, "source_document", None)
                        or getattr(_rec, "source", None)
                        or "unknown").strip()

            def _append_audit(line: str, _rec) -> None:
                src = _audit_source(_rec)
                count = audit_per_cpg.get(src, 0)
                if count < MAX_AUDIT_PER_CPG:
                    plan.gate_audit.append(line[:480])
                    audit_per_cpg[src] = count + 1
                elif src not in audit_overflow_logged:
                    audit_overflow_logged.add(src)
                    plan.gate_audit.append(
                        f"(+ further referral triggers from {src} suppressed — review CPG directly if needed)"[:480]
                    )

            for idx, (rec, primary_trig, urgency_word) in triggered_meta.items():
                status, reason = gate_decisions.get(idx, ("unknown", ""))
                if status == "met":
                    intervention = (
                        f"Refer to {rec.specialty} ({urgency_word}) — {rec.condition}"
                    )
                    if rec.trigger:
                        intervention += f"; trigger: {rec.trigger}"
                    # Enhanced evidence handling with quality attribution
                    evidence = (rec.evidence or "").strip()
                    if evidence:
                        rationale_base = evidence
                    else:
                        rationale_base = f"KG-sourced referral for {rec.condition}"
                    rationale = f"{rationale_base} [gate: {reason}]" if reason else rationale_base
                    # Log evidence quality for audit trail
                    quality, audit_note = _referral_evidence_quality(rec)
                    logger.info(
                        "Referral evidence quality: %s — %s (%s) [quality=%s, audit=%s]",
                        rec.specialty, rec.condition, urgency_word, quality, audit_note[:60],
                    )

                    # Gap 5: Validate urgency-severity alignment
                    case_severity, severity_rationale = _assess_case_severity(case)
                    is_aligned, recommended_urgency = _validate_urgency_severity_alignment(
                        rec.urgency, case_severity
                    )
                    if not is_aligned and recommended_urgency:
                        logger.warning(
                            "Urgency-severity mismatch: %s referral for %s has %s but case severity warrants %s (%s)",
                            rec.specialty, rec.condition, urgency_word, recommended_urgency, severity_rationale,
                        )
                        # Automatically upgrade urgency if severity is high
                        if case_severity >= 2:
                            urgency_word = recommended_urgency
                            logger.info(
                                "Auto-upgraded referral urgency to %s for %s — %s due to case severity",
                                urgency_word, rec.specialty, rec.condition,
                            )
                    elif is_aligned:
                        logger.debug(
                            "Urgency-severity aligned: %s referral for %s appropriate for severity=%d (%s)",
                            rec.specialty, rec.condition, case_severity, severity_rationale,
                        )

                    try:
                        plan.recommendations.append(
                            _Rec(
                                intervention=intervention,
                                type="referral",
                                action=None,
                                evidence_grade=None,
                                cpg_source=_kg_referral_cpg_source(rec),
                                rationale=rationale[:480],
                                contraindications_checked=[],
                            )
                        )
                        injected_count += 1
                        logger.info(
                            "Referral GATE=met → injected: %s — %s (trigger=%r, reason=%r)",
                            rec.specialty, rec.condition, primary_trig, reason,
                        )
                    except Exception as exc:
                        logger.warning("Triggered referral injection failed: %s", exc)
                elif status == "not_met":
                    dropped_count += 1
                    nm_key = _normalize_referral_key(rec.specialty, rec.condition)
                    if nm_key not in notmet_seen_keys:
                        notmet_seen_keys.add(nm_key)
                        audit_line = (
                            f"Ruled out {rec.specialty} referral for {rec.condition} — "
                            f"trigger '{primary_trig}' not met: {reason or 'no rationale'}"
                        )
                        _append_audit(audit_line, rec)
                    logger.info(
                        "Referral GATE=not_met → dropped: %s — %s (trigger=%r, reason=%r)",
                        rec.specialty, rec.condition, primary_trig, reason,
                    )
                else:  # unknown / missing
                    if gate_failed:
                        gate_error_count += 1
                    uk_key = _normalize_referral_key(rec.specialty, rec.condition)
                    # All unknown referrals route to gate_audit only — never to
                    # unresolved_questions. The "Awaiting data for X" line carries
                    # the same actionable info (specialty + condition + trigger
                    # value to obtain) more concisely, and keeps unresolved_questions
                    # focused on synthesis-level open issues rather than gate noise.
                    # Dedupe by (specialty, condition_norm) so near-duplicate KG
                    # edges don't fan out into N audit lines.
                    if uk_key not in unknown_seen_keys:
                        unknown_seen_keys.add(uk_key)
                        audit_line = (
                            f"Awaiting data for {rec.specialty} referral — {rec.condition}: "
                            f"trigger '{primary_trig}' unverified ({reason or 'no data in notes'})"
                        )
                        _append_audit(audit_line, rec)
                    gated_count += 1
                    log_func = logger.warning if gate_failed else logger.info
                    log_func(
                        "Referral GATE=unknown → unresolved_questions: %s — %s (trigger=%r)%s",
                        rec.specialty, rec.condition, primary_trig,
                        " [due to gate failure]" if gate_failed else "",
                    )

            for rec, urgency_word in universal_recs:
                # Gap 5: Validate urgency-severity alignment for universal referrals
                case_severity, severity_rationale = _assess_case_severity(case)
                is_aligned, recommended_urgency = _validate_urgency_severity_alignment(
                    rec.urgency, case_severity
                )
                if not is_aligned and recommended_urgency:
                    logger.warning(
                        "Urgency-severity mismatch: universal %s referral for %s has %s but case severity warrants %s (%s)",
                        rec.specialty, rec.condition, urgency_word, recommended_urgency, severity_rationale,
                    )
                    if case_severity >= 2:
                        urgency_word = recommended_urgency
                        logger.info(
                            "Auto-upgraded universal referral urgency to %s for %s — %s due to case severity",
                            urgency_word, rec.specialty, rec.condition,
                        )

                intervention = (
                    f"Refer to {rec.specialty} ({urgency_word}) — {rec.condition}"
                )
                if rec.trigger:
                    intervention += f"; trigger: {rec.trigger}"
                # Enhanced evidence handling with quality attribution
                evidence = (rec.evidence or "").strip()
                if evidence:
                    rationale = evidence
                else:
                    rationale = f"KG-sourced referral for {rec.condition}"
                try:
                    plan.recommendations.append(
                        _Rec(
                            intervention=intervention,
                            type="referral",
                            action=None,
                            evidence_grade=None,
                            cpg_source=_kg_referral_cpg_source(rec),
                            rationale=rationale[:480],
                            contraindications_checked=[],
                        )
                    )
                    injected_count += 1
                    quality, audit_note = _referral_evidence_quality(rec)
                    logger.info(
                        "Universal referral evidence quality: %s — %s (%s) [quality=%s, audit=%s]",
                        rec.specialty, rec.condition, urgency_word, quality, audit_note[:60],
                    )
                except Exception as exc:
                    logger.warning("KG referral injection failed (%s — %s): %s", rec.specialty, rec.condition, exc)
            logger.info(
                "stage_5 coverage (KG): %d injected (universal + gate=met), %d to unresolved_questions (gate=unknown, %d due to gate failure), %d dropped (gate=not_met)",
                injected_count, gated_count, gate_error_count, dropped_count,
            )
        else:
            # Static-dict fallback (covers conditions not yet in the KG).
            # Validate that required referrals are actually in the plan.
            seen_specialties: set[str] = set()
            existing_referral_specs: set[str] = set()
            for rec in plan.recommendations:
                if rec.type == "referral":
                    # The Recommendation model has NO `specialty` field — referrals
                    # live in `intervention` free text ("Refer to Cardiology — …").
                    # Reading getattr(rec,'specialty') always returned ""/None, so
                    # this set was permanently empty and EVERY required referral
                    # was reported "not surfaced" even when the LLM emitted it
                    # (consult-186 false positive). Infer + normalise from the
                    # intervention, matching how dedup keys referrals.
                    spec = _infer_referral_specialty(rec)
                    if spec:
                        existing_referral_specs.add(spec)

            for code in coverage_codes:
                referral_required = _required_referral_for(code)
                if not referral_required:
                    continue
                # Normalise the required specialty through the SAME function so the
                # comparison is key-vs-key (e.g. "Cardiology (heart failure
                # specialist) — …" → "cardiology"), not raw-string-vs-key.
                spec_part = _normalise_specialty_phrase(referral_required.split(" —")[0])
                if spec_part not in seen_specialties:
                    seen_specialties.add(spec_part)
                    if spec_part not in existing_referral_specs:
                        # Referral is required but missing from plan
                        plan.unresolved_questions.append(
                            f"Expected referral not surfaced in plan: {referral_required}. "
                            "No referral recommendation was emitted — clinician should "
                            "arrange specialist input."
                        )
                        logger.info(
                            "stage_5 coverage (dict fallback): required referral missing for %s — %s",
                            code, referral_required,
                        )
                    else:
                        logger.info(
                            "stage_5 coverage (dict fallback): required referral covered for %s — %s",
                            code, referral_required,
                        )

    # Final dedup of all recommendations (post-KG injection) to catch any duplicates
    # introduced by KG edge injection or LLM+KG overlap
    med_count_before_final = sum(1 for r in plan.recommendations if r.type == "pharmacological")
    plan.recommendations = _dedup_pharmacological_recs(plan.recommendations)
    med_count_after_final = sum(1 for r in plan.recommendations if r.type == "pharmacological")
    if med_count_before_final != med_count_after_final:
        logger.info(
            "stage_5: final medication dedup (post-KG): %d → %d pharmacological recs",
            med_count_before_final, med_count_after_final,
        )

    # Surface the existing side of a drug–drug contraindication. The LLM flags the
    # contraindicated agent (e.g. a PDE5i) but the current med that *creates* the
    # contraindication (e.g. the patient's long-acting nitrate) never gets a row,
    # so the clinician sees only one side of the conflict. This pass gives that
    # interacting current med a contraindicated row. Background meds the plan
    # doesn't touch are intentionally not surfaced. Runs after dedup so it sees the
    # final (incl. KG-injected) rec set.
    plan.recommendations = _surface_interacting_current_meds(
        plan.recommendations,
        plan.red_flags,
        getattr(case, "current_medications", []) or [],
    )

    # Final dedup of referrals (post-KG injection) to handle urgency conflicts
    # and duplicates introduced by LLM+KG overlap or KG itself
    ref_count_before_final = sum(1 for r in plan.recommendations if r.type == "referral")
    plan.recommendations = _dedup_referral_recs(plan.recommendations)
    ref_count_after_final = sum(1 for r in plan.recommendations if r.type == "referral")
    if ref_count_before_final != ref_count_after_final:
        logger.info(
            "stage_5: final referral dedup (post-KG): %d → %d referral recs",
            ref_count_before_final, ref_count_after_final,
        )

    # Cross-section dedup: a lifestyle rec that merely restates a structured
    # monitoring parameter (e.g. "Weight monitoring" vs the "Body weight" row) is
    # redundant. The monitoring table is authoritative (schedule + target), so the
    # lifestyle duplicate is dropped. Content-driven — see _dedup_lifestyle_vs_monitoring.
    lifestyle_before = sum(1 for r in plan.recommendations if r.type == "lifestyle")
    plan.recommendations = _dedup_lifestyle_vs_monitoring(
        plan.recommendations, plan.monitoring
    )
    lifestyle_after = sum(1 for r in plan.recommendations if r.type == "lifestyle")
    if lifestyle_before != lifestyle_after:
        logger.info(
            "stage_5: lifestyle/monitoring dedup: %d → %d lifestyle recs",
            lifestyle_before, lifestyle_after,
        )

    # Anti-hallucination guard: strip unresolved_questions that claim a
    # severity_staging / vitals field is "not provided" when the case actually
    # carries that field. The synthesis LLM occasionally contradicts itself
    # (e.g. uses eGFR=58 in the rationale + summary, then says "eGFR not provided"
    # in unresolved_questions). Such entries mislead clinicians into reordering
    # tests they already have.
    try:
        provided_keys: set[str] = set()
        for key, val in (getattr(case, "severity_staging", {}) or {}).items():
            if val not in (None, "", []):
                provided_keys.add(key.lower())
        for key, val in (getattr(case, "vitals", {}) or {}).items():
            if val not in (None, "", []):
                provided_keys.add(key.lower())
        if provided_keys:
            import re as _re
            absent_re = _re.compile(
                r"(?i)\b([a-z][a-z0-9+\-/() ]{0,40}?)\s+(?:not\s+(?:provided|available|reported|specified|known|documented|recorded|measured)|is\s+missing|unknown)\b"
            )
            kept: list[str] = []
            dropped: list[str] = []
            for q in plan.unresolved_questions or []:
                hit = False
                for m in absent_re.finditer(q or ""):
                    claimed = m.group(1).strip().lower()
                    tokens = {t for t in _re.findall(r"[a-z0-9+]+", claimed) if len(t) > 1}
                    for tok in tokens:
                        if tok in provided_keys or any(tok == k or tok in k for k in provided_keys):
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    dropped.append(q)
                else:
                    kept.append(q)
            if dropped:
                plan.unresolved_questions = kept
                for d in dropped:
                    logger.warning(
                        "stage_5 anti-hallucination: dropped unresolved_question claiming "
                        "missing field that IS in case input — %r",
                        d[:160],
                    )
    except Exception as e:
        logger.warning("stage_5 anti-hallucination guard failed (continuing): %s", e)

    # Coverage-gap detector: for each routed condition with a FIRST_LINE_FOR
    # rule in the KG, ensure the synthesised plan actually prescribes a med in
    # one of those classes. If not, surface one actionable warning per
    # uncovered condition. Single-question-per-condition; never fabricates a rx.
    try:
        prefer_flags = [
            f for f in (flags or [])
            if getattr(f, "flag_type", "") == "PREFER"
            and getattr(f, "relation", "") == "FIRST_LINE_FOR"
            and (getattr(f, "subject", "") or "").strip()
            and (getattr(f, "object", "") or "").strip()
        ]
        if prefer_flags:
            from collections import defaultdict
            first_line_by_cond: dict[str, list[str]] = defaultdict(list)
            for f in prefer_flags:
                drug = f.subject.strip()
                if drug.lower() in _PARSER_ERROR_DRUGS:
                    continue
                cond = f.object.strip()
                if drug not in first_line_by_cond[cond]:
                    first_line_by_cond[cond].append(drug)

            med_names = [
                (r.intervention or "")
                for r in plan.recommendations
                if (r.type or "").lower() == "pharmacological"
            ]
            # Residual 2: coverage check must also count drugs the patient is
            # already on. Otherwise a continuing rate-control agent (e.g.
            # amiodarone for AF) that the plan didn't re-emit as an explicit
            # [CONTINUE] rec gets falsely flagged as "no 1st-line prescribed".
            med_names.extend(case.current_medications or [])
            gap_count = 0
            for cond, classes in first_line_by_cond.items():
                if not classes:
                    continue
                covered = any(
                    _match_rule_to_med(med, drug)
                    for med in med_names
                    for drug in classes
                )
                if covered:
                    continue
                classes_str = ", ".join(classes[:6])
                question = (
                    f"No 1st-line agent prescribed for {cond}. "
                    f"Guideline 1st-line classes: {classes_str}. "
                    "Consider adding one or document the reason for deferral."
                )
                plan.unresolved_questions.append(question[:480])
                gap_count += 1
                logger.info(
                    "stage_5 coverage gap: %s missing 1st-line — alternatives: %s",
                    cond, classes_str,
                )
            if gap_count:
                logger.info(
                    "stage_5 coverage gap: %d condition(s) missing 1st-line therapy",
                    gap_count,
                )
    except Exception as exc:
        logger.warning("coverage-gap detector failed (non-fatal): %s", exc)

    # Gap 6: Analyze problematic triggers — feedback loop for KG refinement
    try:
        problematic_triggers = _get_problematic_triggers(plan.unresolved_questions)
        if problematic_triggers:
            # Find most problematic triggers (frequency > 1 would indicate pattern)
            # For this session, we log high-risk triggers for monitoring
            logger.info(
                "stage_5 trigger analysis: %d unique unresolved trigger-condition pairs identified",
                len(problematic_triggers),
            )
            # Log top problematic ones (if any repeat in this case)
            top_triggers = sorted(
                problematic_triggers.items(), key=lambda x: x[1], reverse=True
            )[:3]
            for trigger_pair, count in top_triggers:
                if count > 1:
                    logger.warning(
                        "stage_5 feedback: trigger-condition %r failed %d times; recommend KG review",
                        trigger_pair, count,
                    )

            # Gap 6: Assess data quality issues for trigger failures
            for question in plan.unresolved_questions:
                if "IF:" in question:
                    trigger = question.split("IF:")[-1].strip()
                    is_data_issue, issue_desc = _assess_data_quality_issue(case, trigger)
                    if is_data_issue:
                        logger.warning(
                            "stage_5 data quality: trigger %r failed likely due to: %s",
                            trigger, issue_desc,
                        )
    except Exception as exc:
        logger.debug("trigger analysis failed (non-fatal): %s", exc)

    # Gap D: split STOP recs that bundle a "switch to X" target into paired
    # STOP + START, so downstream checks (and the showcase scanner) see the
    # alternative as a structured START action.
    try:
        plan.recommendations = _split_stop_switch_recs(plan.recommendations)
    except Exception as exc:
        logger.debug("stop-switch split failed (non-fatal): %s", exc)

    # Gap 7: Specialist-medication cross-check validator
    try:
        cross_check_warnings = _validate_specialist_medication_pairing(plan.recommendations, case)
        if cross_check_warnings:
            for warning in cross_check_warnings:
                logger.warning("stage_5 cross-check: %s", warning)
                plan.unresolved_questions.append(f"Cross-check: {warning}")
            logger.info(
                "stage_5 specialist-medication cross-check: %d issues identified",
                len(cross_check_warnings),
            )
    except Exception as exc:
        logger.debug("specialist-medication cross-check failed (non-fatal): %s", exc)

    # Gap 8: Clinical assumption flagging — extract load-bearing assumptions
    try:
        assumptions = _extract_recommendation_assumptions(plan.recommendations, plan.unresolved_questions)
        if assumptions:
            logger.info("stage_5 assumption flags: %d load-bearing assumptions identified", len(assumptions))
            for source, assumption_text in assumptions:
                # Log with WARNING level if assumption is critical (contains "contraindicated" or "escalate")
                is_critical = any(
                    word in assumption_text.lower()
                    for word in ["contraindicated", "escalate", "critical", "emergency"]
                )
                log_func = logger.warning if is_critical else logger.info
                log_func(
                    "stage_5 assumption [%s]: %s",
                    source,
                    assumption_text[:120],  # Truncate for log readability
                )
    except Exception as exc:
        logger.debug("assumption extraction failed (non-fatal): %s", exc)

    return plan


# ---------------------------------------------------------------------------
# Pre-consultation prep brief (returning patients only)
# ---------------------------------------------------------------------------

async def generate_prep_brief(
    prior_visit: dict,
    current_medications: list,
    patient_age: int | None,
    patient_sex: str | None,
    comorbidities: list[str] | None,
) -> dict:
    """Generate a 3-bullet pre-consultation briefing for a returning patient.

    Returns dict with keys: since_last_visit, med_flags, ask_today.
    Falls back to a minimal dict on LLM failure — never raises.
    """
    # Prefer prep-brief-specific vars, then Gemini, then fall back to the active
    # LLM_* provider (MiMo). Without this fallback the client below raises when
    # only MiMo is configured — bypassing the graceful fallback and 500-ing.
    base_url = (os.getenv("PREP_BRIEF_LLM_BASE_URL") or os.getenv("GEMINI_BASE_URL")
                or os.getenv("LLM_BASE_URL"))
    api_key  = (os.getenv("PREP_BRIEF_LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
                or os.getenv("LLM_API_KEY"))
    model    = (os.getenv("PREP_BRIEF_LLM_MODEL") or os.getenv("LLM_CHOICE")
                or "gemini-2.5-flash")

    fallback = {
        "since_last_visit": prior_visit.get("what_changed") or "Prior visit data available — review chart.",
        "med_flags": None,
        "ask_today": (prior_visit.get("prior_plan_summary") or "")[:120] or None,
    }

    if not PREP_BRIEF_PROMPT:
        return fallback

    payload = json.dumps({
        "prior_visit": prior_visit,
        "current_medications": current_medications or [],
        "patient": {
            "age": patient_age,
            "sex": patient_sex,
            "comorbidities": comorbidities or [],
        },
    }, ensure_ascii=False)

    try:
        client = _make_openai_client(base_url=base_url, api_key=api_key, max_retries=0)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PREP_BRIEF_PROMPT},
                {"role": "user",   "content": payload},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        # Enforce caps
        for k in ("since_last_visit", "med_flags", "ask_today"):
            v = data.get(k)
            if isinstance(v, str) and len(v) > 120:
                data[k] = v[:120].rstrip()
        return {
            "since_last_visit": data.get("since_last_visit") or fallback["since_last_visit"],
            "med_flags":        data.get("med_flags"),
            "ask_today":        data.get("ask_today"),
        }
    except Exception as exc:
        logger.warning("prep_brief LLM failed (%s); returning fallback", exc)
        return fallback
